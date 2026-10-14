"""Authorization, ownership and background control over the existing Runtime.

This layer stores access-control and upload metadata only. Canonical workflow,
job, attempt, event and artifact state remains in the existing Runtime SQLite
database and is never reimplemented here.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from t01_phase1_real.common import TERMINAL, RuntimeFault, encode, identifier, now, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.structure import policy as structure_policy
from t01_phase1_real.files import no_links, publish, read_verified, runtime_root, within


ALL_SCOPES = frozenset({"submit", "query", "control", "download", "upload"})
ACTIVE_STATES = frozenset({"queued", "running", "stop_requested", "reconciling"})
SERVICE_DB_VERSION = 1
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_REPORT_BYTES = 32 * 1024 * 1024


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)

    def envelope(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message}}


@dataclass(frozen=True)
class Principal:
    principal_id: str
    scopes: frozenset[str]
    token_sha256: str

    @property
    def runtime_scope(self) -> str:
        return "svc-" + sha(self.principal_id.encode("utf-8"))[:24]


class Credentials:
    """Constant-time bearer lookup loaded from process environment only."""

    def __init__(self, rows: list[tuple[bytes, Principal]]) -> None:
        if not rows:
            raise ServiceError("CONFIGURATION_INVALID", "At least one credential is required", 500)
        self._rows = tuple(rows)

    @classmethod
    def from_document(cls, document: Any) -> "Credentials":
        if not isinstance(document, dict) or set(document) != {"credentials"}:
            raise ServiceError("CONFIGURATION_INVALID", "Exact credentials document required", 500)
        values = document["credentials"]
        if not isinstance(values, list) or not values:
            raise ServiceError("CONFIGURATION_INVALID", "Credential list is empty", 500)
        rows: list[tuple[bytes, Principal]] = []
        identities: set[str] = set()
        token_hashes: set[str] = set()
        for value in values:
            if not isinstance(value, dict) or set(value) != {"token", "principal", "scopes"}:
                raise ServiceError("CONFIGURATION_INVALID", "Exact credential fields required", 500)
            token = value["token"]
            principal_id = value["principal"]
            scopes = value["scopes"]
            if not isinstance(token, str) or not 32 <= len(token) <= 512:
                raise ServiceError("CONFIGURATION_INVALID", "Bearer token length is invalid", 500)
            try:
                identifier(principal_id)
            except RuntimeFault as exc:
                raise ServiceError("CONFIGURATION_INVALID", "Principal identity is invalid", 500) from exc
            if not isinstance(scopes, list) or not scopes or not all(isinstance(item, str) for item in scopes):
                raise ServiceError("CONFIGURATION_INVALID", "Credential scopes are invalid", 500)
            scope_set = frozenset(scopes)
            if not scope_set <= ALL_SCOPES:
                raise ServiceError("CONFIGURATION_INVALID", "Credential contains an unknown scope", 500)
            token_raw = token.encode("utf-8")
            token_hash = sha(token_raw)
            if token_hash in token_hashes:
                raise ServiceError("CONFIGURATION_INVALID", "Duplicate bearer token", 500)
            token_hashes.add(token_hash)
            identities.add(principal_id)
            rows.append((token_raw, Principal(principal_id, scope_set, token_hash)))
        return cls(rows)

    @classmethod
    def from_environment(cls, name: str = "T01_REAL_SERVICE_CREDENTIALS_JSON") -> "Credentials":
        raw = os.environ.get(name)
        if raw is None:
            raise ServiceError("CONFIGURATION_INVALID", f"{name} is required", 500)
        try:
            value = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise ServiceError("CONFIGURATION_INVALID", "Credential JSON is malformed", 500) from exc
        return cls.from_document(value)

    def authenticate(self, authorization: str | None, required_scope: str) -> Principal:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            raise ServiceError("UNAUTHENTICATED", "Bearer authentication is required", 401)
        candidate = authorization[7:].encode("utf-8")
        match: Principal | None = None
        for token, principal in self._rows:
            if hmac.compare_digest(candidate, token):
                match = principal
        if match is None:
            raise ServiceError("UNAUTHENTICATED", "Bearer authentication failed", 401)
        if required_scope not in match.scopes:
            raise ServiceError("FORBIDDEN", "Credential lacks the required scope", 403)
        return match

    def inventory(self) -> list[dict[str, Any]]:
        return [
            {"principal": principal.principal_id, "scopes": sorted(principal.scopes), "token_sha256": principal.token_sha256}
            for _, principal in self._rows
        ]


@dataclass(frozen=True)
class ServiceConfig:
    runtime_root: Path
    blast_database_root: Path | None = None
    homology_database_root: Path | None = None
    domains_database_root: Path | None = None
    max_workers: int = 2
    dispatch_start_delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_root", runtime_root(self.runtime_root))
        for name in ("blast_database_root", "homology_database_root", "domains_database_root"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, Path(value).resolve())
        if type(self.max_workers) is not int or not 1 <= self.max_workers <= 16:
            raise ServiceError("CONFIGURATION_INVALID", "max_workers must be 1..16", 500)
        if not isinstance(self.dispatch_start_delay_seconds, (int, float)) or not 0 <= self.dispatch_start_delay_seconds <= 30:
            raise ServiceError("CONFIGURATION_INVALID", "dispatch delay must be 0..30 seconds", 500)

    def runtime(self, principal: Principal) -> Runtime:
        return Runtime(
            self.runtime_root,
            scope=principal.runtime_scope,
            blast_database_root=self.blast_database_root,
            homology_database_root=self.homology_database_root,
            domains_database_root=self.domains_database_root,
        )

    def public_profile(self) -> dict[str, Any]:
        roots = {
            name: sha(str(getattr(self, name)).casefold().encode("utf-8")) if getattr(self, name) is not None else None
            for name in ("blast_database_root", "homology_database_root", "domains_database_root")
        }
        return {
            "runtime_root_sha256": sha(str(self.runtime_root).casefold().encode("utf-8")),
            "database_root_sha256": roots,
            "max_workers": self.max_workers,
        }


class ServiceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.db_path = root / "service.sqlite3"
        self._initialize()

    def _db(self) -> sqlite3.Connection:
        for suffix in ("", "-wal", "-shm"):
            no_links(Path(str(self.db_path) + suffix))
        db = sqlite3.connect(self.db_path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _initialize(self) -> None:
        with self._db() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SERVICE_DB_VERSION):
                raise ServiceError("CONFIGURATION_INVALID", "Unsupported service database version", 500)
            if version == 0:
                db.executescript(
                    """BEGIN IMMEDIATE;
CREATE TABLE uploads(id TEXT PRIMARY KEY, principal TEXT NOT NULL, name TEXT NOT NULL,
  media_type TEXT NOT NULL, relative_path TEXT UNIQUE NOT NULL, sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE workflows(job_id TEXT PRIMARY KEY, principal TEXT NOT NULL,
  idempotency_key TEXT, fingerprint TEXT, retry_of_job_id TEXT, created_at TEXT NOT NULL,
  UNIQUE(principal,idempotency_key));
CREATE TABLE controls(principal TEXT NOT NULL, operation TEXT NOT NULL, key TEXT NOT NULL,
  fingerprint TEXT NOT NULL, response TEXT NOT NULL,
  PRIMARY KEY(principal,operation,key));
PRAGMA user_version=1;
COMMIT;"""
                )

    def upload(self, principal: Principal, name: str, media_type: str, raw: bytes) -> dict[str, Any]:
        upload_id = "t01p1r-upload-" + uuid4().hex
        relative = f"service/uploads/{principal.runtime_scope}/{upload_id}.bin"
        publish(self.root, relative, raw)
        value = {
            "upload_id": upload_id,
            "name": name,
            "media_type": media_type,
            "sha256": sha(raw),
            "size_bytes": len(raw),
            "created_at": now(),
        }
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT INTO uploads VALUES(?,?,?,?,?,?,?,?)",
                    (upload_id, principal.principal_id, name, media_type, relative, value["sha256"], len(raw), value["created_at"]),
                )
                db.commit()
        except BaseException:
            # Materialized but unregistered bytes are never resolvable by ID.
            raise
        return value

    def upload_bytes(self, principal: Principal, upload_id: str) -> tuple[dict[str, Any], bytes]:
        if not isinstance(upload_id, str) or re.fullmatch(r"t01p1r-upload-[0-9a-f]{32}", upload_id) is None:
            raise ServiceError("INVALID_REQUEST", "Registered upload ID required", 422)
        with self._db() as db:
            row = db.execute("SELECT * FROM uploads WHERE id=?", (upload_id,)).fetchone()
        if row is None:
            raise ServiceError("UPLOAD_NOT_FOUND", "Upload is not registered", 404)
        if row["principal"] != principal.principal_id:
            raise ServiceError("FORBIDDEN", "Upload belongs to another principal", 403)
        raw = read_verified(self.root, row["relative_path"], row["sha256"], row["size_bytes"], structure_policy.MAX_STRUCTURE_BYTES)
        return {
            "upload_id": row["id"],
            "name": row["name"],
            "media_type": row["media_type"],
            "sha256": row["sha256"],
            "size_bytes": row["size_bytes"],
            "created_at": row["created_at"],
        }, raw

    def submission(self, principal: Principal, key: str) -> sqlite3.Row | None:
        with self._db() as db:
            return db.execute(
                "SELECT * FROM workflows WHERE principal=? AND idempotency_key=?", (principal.principal_id, key)
            ).fetchone()

    def register_submission(self, principal: Principal, key: str, fingerprint: str, job_id: str) -> bool:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM workflows WHERE principal=? AND idempotency_key=?", (principal.principal_id, key)
            ).fetchone()
            if row:
                db.rollback()
                if row["fingerprint"] != fingerprint:
                    raise ServiceError("IDEMPOTENCY_CONFLICT", "Idempotency key has different input bytes", 409)
                if row["job_id"] != job_id:
                    raise ServiceError("INTEGRITY_ERROR", "Idempotency mapping differs from Runtime", 500)
                return False
            db.execute(
                "INSERT INTO workflows VALUES(?,?,?,?,?,?)",
                (job_id, principal.principal_id, key, fingerprint, None, now()),
            )
            db.commit()
            return True

    def register_retry(self, principal: Principal, job_id: str, retry_of: str) -> None:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT principal,retry_of_job_id FROM workflows WHERE job_id=?", (job_id,)).fetchone()
            if row:
                db.rollback()
                if row["principal"] != principal.principal_id or row["retry_of_job_id"] != retry_of:
                    raise ServiceError("INTEGRITY_ERROR", "Retry ownership mapping differs", 500)
                return
            db.execute(
                "INSERT INTO workflows VALUES(?,?,?,?,?,?)",
                (job_id, principal.principal_id, None, None, retry_of, now()),
            )
            db.commit()

    def authorize_job(self, principal: Principal, job_id: str) -> None:
        if not isinstance(job_id, str) or re.fullmatch(r"t01p1r-job-[0-9a-f]{32}", job_id) is None:
            raise ServiceError("INVALID_REQUEST", "Canonical workflow job ID required", 422)
        with self._db() as db:
            row = db.execute("SELECT principal FROM workflows WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise ServiceError("JOB_NOT_FOUND", "Workflow job is not registered to this service", 404)
        if row["principal"] != principal.principal_id:
            raise ServiceError("FORBIDDEN", "Workflow belongs to another principal", 403)

    def jobs_for_principal(self, principal: Principal) -> list[str]:
        with self._db() as db:
            return [row[0] for row in db.execute("SELECT job_id FROM workflows WHERE principal=?", (principal.principal_id,))]

    def control(
        self,
        principal: Principal,
        operation: str,
        key: str,
        fingerprint: str,
        action: Any,
    ) -> tuple[dict[str, Any], bool]:
        identifier(key)
        with self._db() as db:
            row = db.execute(
                "SELECT fingerprint,response FROM controls WHERE principal=? AND operation=? AND key=?",
                (principal.principal_id, operation, key),
            ).fetchone()
        if row:
            if row["fingerprint"] != fingerprint:
                raise ServiceError("IDEMPOTENCY_CONFLICT", "Control key has different input bytes", 409)
            return json.loads(row["response"]), False
        response = action()
        raw = json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT INTO controls VALUES(?,?,?,?,?)",
                    (principal.principal_id, operation, key, fingerprint, raw),
                )
                db.commit()
                return response, True
            except sqlite3.IntegrityError:
                db.rollback()
        return self.control(principal, operation, key, fingerprint, action)


class Service:
    _SUPERVISOR_REGISTRATION_GRACE_SECONDS = 15.0

    def __init__(self, config: ServiceConfig, credentials: Credentials) -> None:
        self.config = config
        self.credentials = credentials
        # Establish the canonical Runtime marker/database before adding the
        # service ACL database to the same registered root.
        Runtime(config.runtime_root, scope="svc-bootstrap")
        self.store = ServiceStore(config.runtime_root)
        self._executor = ThreadPoolExecutor(max_workers=config.max_workers, thread_name_prefix="t01-service")
        self._scheduled: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def runtime(self, principal: Principal) -> Runtime:
        return self.config.runtime(principal)

    def recover_active(self) -> int:
        count = 0
        for credential in self.credentials.inventory():
            principal = Principal(
                credential["principal"], frozenset(credential["scopes"]), credential["token_sha256"]
            )
            for job_id in self.store.jobs_for_principal(principal):
                try:
                    if self.runtime(principal).get(job_id)["state"] in ACTIVE_STATES:
                        self.schedule(principal, job_id, recovering=True)
                        count += 1
                except RuntimeFault:
                    continue
        return count

    def schedule(self, principal: Principal, job_id: str, recovering: bool = False) -> None:
        key = (principal.principal_id, job_id)
        with self._lock:
            if key in self._scheduled:
                return
            self._scheduled.add(key)
        self._executor.submit(self._drive, principal, job_id, recovering)

    def _drive(self, principal: Principal, job_id: str, recovering: bool) -> None:
        key = (principal.principal_id, job_id)
        try:
            if self.config.dispatch_start_delay_seconds:
                time.sleep(self.config.dispatch_start_delay_seconds)
            rt = self.runtime(principal)
            while True:
                job = rt.get(job_id)
                if job["state"] in TERMINAL:
                    return
                # A model child is first durably reserved and only then starts a
                # separate supervisor. Do not interpret that short registration
                # window as a crashed supervisor merely because the service can
                # poll faster than the new process can publish its identity.
                if self._child_registration_pending(rt, job_id):
                    time.sleep(0.25)
                    continue
                job = rt.recover(job_id) if recovering or job["state"] != "queued" else rt.dispatch(job_id)
                recovering = True
                if job["state"] in TERMINAL:
                    return
                time.sleep(0.25)
        except BaseException:
            # Durable Runtime state remains recoverable after process/thread loss.
            return
        finally:
            with self._lock:
                self._scheduled.discard(key)

    def _child_registration_pending(self, rt: Runtime, workflow_job_id: str) -> bool:
        try:
            rows = rt.execution(workflow_job_id).get("nodes", {})
            for row in rows.values():
                child_id = row.get("job_id")
                if not child_id:
                    continue
                child = rt.get(child_id)
                if child["state"] not in ACTIVE_STATES or child["state"] == "queued":
                    continue
                execution = rt.execution(child_id)
                if execution.get("supervisor") is not None or execution.get("container_started"):
                    continue
                if execution.get("phase") not in {"reserved", "spawn_intent"}:
                    continue
                started_at = child.get("started_at")
                if not isinstance(started_at, str):
                    continue
                started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - started).total_seconds()
                if age < self._SUPERVISOR_REGISTRATION_GRACE_SECONDS:
                    return True
        except (KeyError, TypeError, ValueError, RuntimeFault):
            # Canonical recovery remains the fail-closed authority once a
            # snapshot is incomplete or the bounded grace period has elapsed.
            return False
        return False

    @staticmethod
    def _exact_object(value: Any, fields: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
        if not isinstance(value, dict) or not (set(value) <= fields | optional and fields <= set(value)):
            raise ServiceError("INVALID_REQUEST", "Exact request fields required", 422)
        return value

    def upload(self, principal: Principal, body: Any) -> dict[str, Any]:
        body = self._exact_object(body, {"name", "media_type", "content_base64"})
        name, media_type, encoded = body["name"], body["media_type"], body["content_base64"]
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name) is None:
            raise ServiceError("INVALID_REQUEST", "Safe structure filename required", 422)
        if media_type not in {"chemical/x-pdb", "chemical/x-cif", "application/octet-stream"}:
            raise ServiceError("INVALID_REQUEST", "Unsupported structure media type", 422)
        if not isinstance(encoded, str):
            raise ServiceError("INVALID_REQUEST", "Base64 structure content required", 422)
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ServiceError("INVALID_REQUEST", "Malformed base64 structure", 422) from exc
        if not 0 < len(raw) <= structure_policy.MAX_STRUCTURE_BYTES:
            raise ServiceError("INVALID_REQUEST", "Structure must be 1 byte..4 MiB", 422)
        return self.store.upload(principal, name, media_type, raw)

    def submit(self, principal: Principal, body: Any) -> dict[str, Any]:
        body = self._exact_object(body, {"idempotency_key", "request"}, {"structure_upload_id"})
        key = body["idempotency_key"]
        try:
            identifier(key)
        except RuntimeFault as exc:
            raise ServiceError("INVALID_REQUEST", "Invalid idempotency key", 422) from exc
        if not isinstance(body["request"], dict):
            raise ServiceError("INVALID_REQUEST", "Workflow request must be an object", 422)
        raw = encode(body["request"])
        upload_id = body.get("structure_upload_id")
        structure_data = None
        upload_sha = None
        if upload_id is not None:
            upload, structure_data = self.store.upload_bytes(principal, upload_id)
            upload_sha = upload["sha256"]
        fingerprint = sha(encode({"request_sha256": sha(raw), "structure_sha256": upload_sha}))
        prior = self.store.submission(principal, key)
        if prior:
            if prior["fingerprint"] != fingerprint:
                raise ServiceError("IDEMPOTENCY_CONFLICT", "Idempotency key has different input bytes", 409)
            job = self.runtime(principal).get(prior["job_id"])
            self.schedule(principal, job["job_id"], recovering=True)
            return self._job_response(job, "REPLAYED")
        try:
            job = self.runtime(principal).submit_workflow(raw, key, structure_data)
        except RuntimeFault as exc:
            raise self._runtime_error(exc) from exc
        created = self.store.register_submission(principal, key, fingerprint, job["job_id"])
        self.schedule(principal, job["job_id"])
        return self._job_response(job, "CREATED" if created else "REPLAYED")

    @staticmethod
    def _job_response(job: dict[str, Any], action: str | None = None) -> dict[str, Any]:
        value = {
            "job_id": job["job_id"],
            "run_id": job["run_id"],
            "state": job["state"],
            "error_code": job["error_code"],
            "revision": job["revision"],
            "terminal": job["state"] in TERMINAL,
            "report_ready": job["state"] == "succeeded",
            "scientific_gate": "CLOSED",
            "usable_for_pipeline": False,
            "production_status": "NOT_DEPLOYED",
        }
        if action is not None:
            value["action"] = action
        return value

    def status(self, principal: Principal, job_id: str, node: str | None = None) -> dict[str, Any]:
        self.store.authorize_job(principal, job_id)
        rt = self.runtime(principal)
        try:
            job = rt.get(job_id)
            snapshot = rt.workflow(job_id)
        except RuntimeFault as exc:
            raise self._runtime_error(exc) from exc
        if node is not None:
            if node not in snapshot["nodes"]:
                raise ServiceError("INVALID_REQUEST", "Unknown workflow node", 422)
            row = snapshot["nodes"][node]
            return {
                "job_id": job_id,
                "node": node,
                "node_id": row["node_id"],
                "child_job_id": row.get("job_id"),
                "state": row["state"],
                "reason_code": row.get("reason_code") or row.get("error_code"),
                "origin": row.get("origin"),
                "scientific_gate": "CLOSED",
            }
        value = self._job_response(job)
        value["nodes"] = {
            name: {
                "node_id": row["node_id"],
                "job_id": row.get("job_id"),
                "state": row["state"],
                "reason_code": row.get("reason_code") or row.get("error_code"),
                "origin": row.get("origin"),
            }
            for name, row in snapshot["nodes"].items()
        }
        return value

    def wait(self, principal: Principal, job_id: str, timeout_seconds: int) -> dict[str, Any]:
        if type(timeout_seconds) is not int or not 0 <= timeout_seconds <= 600:
            raise ServiceError("INVALID_REQUEST", "wait timeout must be 0..600 seconds", 422)
        deadline = time.monotonic() + timeout_seconds
        while True:
            value = self.status(principal, job_id)
            if value["terminal"] or time.monotonic() >= deadline:
                value["wait_timed_out"] = not value["terminal"]
                return value
            time.sleep(0.1)

    def cancel(self, principal: Principal, job_id: str, key: str) -> dict[str, Any]:
        return self._control(principal, job_id, key, "cancel")

    def retry(self, principal: Principal, job_id: str, key: str) -> dict[str, Any]:
        self.store.authorize_job(principal, job_id)
        fingerprint = sha(encode({"job_id": job_id, "operation": "retry"}))

        def action() -> dict[str, Any]:
            rt = self.runtime(principal)
            try:
                job = rt.control(encode({
                    "contract_version": "0.1.0", "operation": "retry", "job_id": job_id,
                    "idempotency_key": "svc-" + sha((principal.principal_id + ":retry:" + key).encode())[:48],
                }))
            except RuntimeFault as exc:
                raise self._runtime_error(exc) from exc
            self.store.register_retry(principal, job["job_id"], job_id)
            self.schedule(principal, job["job_id"])
            return self._job_response(job, "RETRY_CREATED")

        value, created = self.store.control(principal, "retry", key, fingerprint, action)
        if not created:
            value = copy.deepcopy(value)
            value["action"] = "RETRY_REPLAYED"
        return value

    def recover(self, principal: Principal, job_id: str, key: str) -> dict[str, Any]:
        self.store.authorize_job(principal, job_id)
        fingerprint = sha(encode({"job_id": job_id, "operation": "recover"}))

        def action() -> dict[str, Any]:
            try:
                job = self.runtime(principal).recover(job_id)
            except RuntimeFault as exc:
                raise self._runtime_error(exc) from exc
            if job["state"] not in TERMINAL:
                self.schedule(principal, job_id, recovering=True)
            return self._job_response(job, "RECOVERY_REQUESTED")

        value, created = self.store.control(principal, "recover", key, fingerprint, action)
        if not created:
            value = copy.deepcopy(value)
            value["action"] = "RECOVERY_REPLAYED"
        return value

    def _control(self, principal: Principal, job_id: str, key: str, operation: str) -> dict[str, Any]:
        self.store.authorize_job(principal, job_id)
        fingerprint = sha(encode({"job_id": job_id, "operation": operation}))

        def action() -> dict[str, Any]:
            try:
                job = self.runtime(principal).control(encode({
                    "contract_version": "0.1.0", "operation": operation, "job_id": job_id,
                    "idempotency_key": "svc-" + sha((principal.principal_id + ":" + operation + ":" + key).encode())[:48],
                }))
            except RuntimeFault as exc:
                raise self._runtime_error(exc) from exc
            if job["state"] not in TERMINAL:
                self.schedule(principal, job_id, recovering=True)
            return self._job_response(job, operation.upper() + "_REQUESTED")

        value, created = self.store.control(principal, operation, key, fingerprint, action)
        if not created:
            value = copy.deepcopy(value)
            value["action"] = operation.upper() + "_REPLAYED"
        return value

    def report(self, principal: Principal, job_id: str) -> dict[str, Any]:
        self.store.authorize_job(principal, job_id)
        rt = self.runtime(principal)
        try:
            rt.workflow(job_id)
            result = rt.result(job_id)
            by_path = {row["path"]: row["artifact"] for row in result["raw_artifacts"]}
            if "output/package.zip" not in by_path:
                raise ServiceError("REPORT_NOT_AVAILABLE", "Verified workflow package is not available", 409)
            package_ref = by_path["output/package.zip"]
            package = rt.artifact_bytes(job_id, package_ref["artifact_id"])
            report_ref = by_path.get("output/workflow-report.md")
            report_raw = rt.artifact_bytes(job_id, report_ref["artifact_id"]) if report_ref else b""
        except ServiceError:
            raise
        except RuntimeFault as exc:
            raise self._runtime_error(exc) from exc
        if len(package) > MAX_REPORT_BYTES:
            raise ServiceError("REPORT_TOO_LARGE", "Workflow report exceeds service limit", 413)
        return {
            "job_id": job_id,
            "filename": f"{job_id}.zip",
            "media_type": "application/zip",
            "sha256": sha(package),
            "size_bytes": len(package),
            "content": package,
            "report_markdown": report_raw.decode("utf-8"),
            "scientific_gate": "CLOSED",
            "usable_for_pipeline": False,
            "production_status": "NOT_DEPLOYED",
        }

    def report_for_json(self, principal: Principal, job_id: str) -> dict[str, Any]:
        value = self.report(principal, job_id)
        raw = value.pop("content")
        value["content_base64"] = base64.b64encode(raw).decode("ascii")
        return value

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=not wait)

    @staticmethod
    def _runtime_error(exc: RuntimeFault) -> ServiceError:
        status = {
            "FORBIDDEN": 403,
            "JOB_NOT_FOUND": 404,
            "IDEMPOTENCY_CONFLICT": 409,
            "INVALID_STATE": 409,
            "HASH_MISMATCH": 409,
            "OUTPUT_INVALID": 409,
            "INVALID_REQUEST": 422,
            "PROFILE_NOT_APPROVED": 422,
        }.get(exc.code, 500)
        return ServiceError(exc.code, exc.message, status)
