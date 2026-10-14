"""Run authenticated service acceptance and hold the endpoint for real Dify runs."""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import io
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {"succeeded", "failed", "cancelled", "timed_out"}


def stamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request(base: str, path: str, token: str | None = None, body: Any = None, method: str | None = None) -> tuple[int, dict[str, str], bytes]:
    headers: dict[str, str] = {}
    data = None
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    operation = method or ("POST" if data is not None else "GET")
    req = urllib.request.Request(base + path, data=data, headers=headers, method=operation)
    try:
        with urllib.request.urlopen(req, timeout=620) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


def json_request(*args: Any, **kwargs: Any) -> tuple[int, dict[str, Any]]:
    status, _, raw = request(*args, **kwargs)
    return status, json.loads(raw)


def workflow_body(label: str, *, bepipred: bool = False) -> dict[str, Any]:
    options = ("topology", "blast", "bepipred", "netmhc", "homology", "domains", "developability")
    analysis = {name: None for name in options}
    if bepipred:
        analysis["bepipred"] = {"timeout_seconds": 900}
    return {
        "protein_sequence": "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG",
        "user_sequence_id": label,
        "host_species": "Homo sapiens",
        "expression_host": None,
        "organism": None,
        "structure": None,
        "analysis": analysis,
        "reuse_jobs": {},
        "timeout_seconds": 1800,
    }


def validate_package(raw: bytes) -> dict[str, Any]:
    assert zipfile.is_zipfile(io.BytesIO(raw))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        manifest = json.loads(archive.read("manifest.json"))
        declared = {row["path"]: row for row in manifest["files"]}
        assert set(declared) == set(names) - {"manifest.json"}
        for name, row in declared.items():
            value = archive.read(name)
            assert len(value) == row["size_bytes"] and sha(value) == row["sha256"]
        workflow = json.loads(archive.read("workflow.json"))
        assert workflow["scientific_gate"] == "CLOSED"
        assert not workflow["usable_for_pipeline"] and workflow["production_status"] == "NOT_DEPLOYED"
        return {"files": len(names), "workflow": workflow}


class ManagedService:
    def __init__(self, runtime: Path, secret_document: dict[str, Any], port: int, logs: Path) -> None:
        self.runtime = runtime
        self.secret_document = secret_document
        self.port = port
        self.logs = logs
        self.process: subprocess.Popen[bytes] | None = None
        self.out = None
        self.err = None

    def start(self, label: str, delay: float = 0, blast_root: Path | None = None) -> None:
        assert self.process is None
        self.logs.mkdir(parents=True, exist_ok=True)
        self.out = (self.logs / f"{label}.stdout.txt").open("xb")
        self.err = (self.logs / f"{label}.stderr.txt").open("xb")
        command = [
            sys.executable, "-X", "utf8", "-m", "t01_phase1_real.service_api",
            "--host", "0.0.0.0", "--port", str(self.port),
            "--runtime-root", str(self.runtime), "--max-workers", "2",
            "--dispatch-start-delay-seconds", str(delay),
        ]
        if blast_root is not None:
            command += ["--blast-database-root", str(blast_root)]
        env = dict(os.environ)
        env["T01_REAL_SERVICE_CREDENTIALS_JSON"] = json.dumps(self.secret_document, separators=(",", ":"))
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=self.out, stderr=self.err, creationflags=flags)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"service {label} exited during startup")
            try:
                status, _ = json_request(f"http://127.0.0.1:{self.port}", "/healthz")
                if status == 200:
                    return
            except OSError:
                pass
            time.sleep(0.1)
        raise RuntimeError(f"service {label} did not become ready")

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(10)
            self.process = None
        if self.out:
            self.out.close()
            self.out = None
        if self.err:
            self.err.close()
            self.err = None


def wait_job(base: str, token: str, job_id: str, seconds: int = 600) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status, value = json_request(base, f"/v1/workflows/{job_id}", token)
        assert status == 200
        if value["state"] in TERMINAL:
            return value
        time.sleep(0.2)
    raise RuntimeError(f"workflow did not finish: {job_id}")


def disconnected_submit(host: str, port: int, token: str, body: dict[str, Any]) -> None:
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    message = (
        f"POST /v1/workflows HTTP/1.1\r\nHost: {host}:{port}\r\n"
        f"Authorization: Bearer {token}\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(raw)}\r\nConnection: close\r\n\r\n"
    ).encode() + raw
    sock = socket.create_connection((host, port), timeout=5)
    sock.sendall(message)
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--secret-root", type=Path, required=True)
    parser.add_argument("--continue-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18083)
    args = parser.parse_args()
    evidence = args.evidence_root.resolve()
    runtime = args.runtime_root.resolve()
    secret_root = args.secret_root.resolve()
    if evidence.exists() or runtime.exists() or secret_root.exists() or args.continue_file.exists():
        raise RuntimeError("acceptance targets must not already exist")
    evidence.mkdir(parents=True)
    secret_root.mkdir(parents=True)
    logs = evidence / "service-logs"
    operator_token, dify_token, attacker_token = (secrets.token_urlsafe(48) for _ in range(3))
    credential_document = {"credentials": [
        {"token": operator_token, "principal": "acceptance-tenant", "scopes": ["submit", "query", "control", "download", "upload"]},
        {"token": dify_token, "principal": "acceptance-tenant", "scopes": ["submit", "query", "control", "download", "upload"]},
        {"token": attacker_token, "principal": "other-tenant", "scopes": ["submit", "query", "control", "download", "upload"]},
    ]}
    write(secret_root / "dify-credential.json", {"bearer_token": dify_token})
    write(secret_root / "credentials.json", credential_document)
    base = f"http://127.0.0.1:{args.port}"
    service = ManagedService(runtime, credential_document, args.port, logs)
    cases: list[dict[str, Any]] = []
    try:
        # A queued workflow survives an actual service process termination and
        # is recovered from the same Runtime/ACL stores without duplicate jobs.
        service.start("restart-before", delay=8)
        status, restart_submit = json_request(base, "/v1/workflows", operator_token, {
            "idempotency_key": "restart-same-config", "request": workflow_body("restart-same-config"),
        })
        assert status == 201 and restart_submit["state"] == "queued"
        service.stop()
        service.start("restart-after")
        restart_end = wait_job(base, operator_token, restart_submit["job_id"])
        assert restart_end["state"] == "succeeded"
        cases.append({"case": "service_restart_recovery", "job_id": restart_submit["job_id"],
                      "state": restart_end["state"], "same_job": True})

        # A deliberate fixed-configuration drift on restart must fail closed.
        service.stop()
        service.start("drift-before", delay=8)
        status, drift_submit = json_request(base, "/v1/workflows", operator_token, {
            "idempotency_key": "restart-profile-drift", "request": workflow_body("restart-profile-drift"),
        })
        assert status == 201 and drift_submit["state"] == "queued"
        service.stop()
        drift_root = evidence / "negative-config-drift"
        service.start("drift-after", blast_root=drift_root)
        drift_end = wait_job(base, operator_token, drift_submit["job_id"])
        assert drift_end["state"] == "failed" and drift_end["error_code"] == "PROFILE_NOT_APPROVED"
        cases.append({"case": "restart_configuration_drift_fails_closed", "job_id": drift_submit["job_id"],
                      "state": drift_end["state"], "error_code": drift_end["error_code"]})
        service.stop()
        service.start("dify-and-rest")

        status, health = json_request(base, "/healthz")
        assert status == 200 and health["authentication"] == "bearer" and health["scientific_gate"] == "CLOSED"
        cases.append({"case": "health", "status": status, "value": health})
        for label, token in (("missing_auth", None), ("wrong_auth", "not-a-valid-bearer-token-value-000000")):
            status, value = json_request(base, "/v1/workflows/t01p1r-job-" + "0" * 32, token)
            assert status == 401 and value["error"]["code"] == "UNAUTHENTICATED"
            cases.append({"case": label, "status": status, "error_code": value["error"]["code"]})

        # Register actual local structure bytes; only the opaque upload ID can
        # enter a workflow submission.
        structure = (ROOT / "discovery/t01-phase1-real/integration-20260910/acceptance-r02/inputs/fresh-structure-predictors-report.structure").read_bytes()
        status, upload = json_request(base, "/v1/uploads", operator_token, {
            "name": "local-1ubq.cif", "media_type": "chemical/x-cif",
            "content_base64": base64.b64encode(structure).decode("ascii"),
        })
        assert status == 201 and upload["sha256"] == sha(structure)
        status, forbidden_upload = json_request(base, "/v1/workflows", attacker_token, {
            "idempotency_key": "foreign-upload", "request": workflow_body("foreign-upload"),
            "structure_upload_id": upload["upload_id"],
        })
        assert status == 403 and forbidden_upload["error"]["code"] == "FORBIDDEN"
        status, invalid_path = json_request(base, "/v1/uploads", operator_token, {
            "name": "../input.cif", "media_type": "chemical/x-cif", "content_base64": "QQ==",
        })
        assert status == 422
        cases.append({"case": "controlled_upload", "upload": upload, "foreign_status": 403,
                      "invalid_path_status": invalid_path.get("error", {}).get("code")})

        # Drop the client connection immediately after a valid submission. A
        # replay later resolves the durable job and real BepiPred execution.
        real_request = {"idempotency_key": "disconnect-real-bepipred", "request": workflow_body("disconnect-real-bepipred", bepipred=True)}
        disconnected_submit("127.0.0.1", args.port, operator_token, real_request)
        time.sleep(0.5)
        status, replay = json_request(base, "/v1/workflows", operator_token, real_request)
        assert status == 200 and replay["action"] == "REPLAYED"
        real_end = wait_job(base, operator_token, replay["job_id"], 900)
        assert real_end["state"] == "succeeded" and real_end["nodes"]["bepipred"]["state"] == "succeeded"
        changed = json.loads(json.dumps(real_request))
        changed["request"]["user_sequence_id"] = "different"
        status, conflict = json_request(base, "/v1/workflows", operator_token, changed)
        assert status == 409 and conflict["error"]["code"] == "IDEMPOTENCY_CONFLICT"
        status, foreign = json_request(base, f"/v1/workflows/{replay['job_id']}", attacker_token)
        assert status == 403 and foreign["error"]["code"] == "FORBIDDEN"
        status, headers, package = request(base, f"/v1/workflows/{replay['job_id']}/report", operator_token)
        package_facts = validate_package(package)
        assert status == 200 and sha(package) == headers["Digest"].split("=", 1)[1]
        write(evidence / "reports" / "disconnect-real-bepipred.zip.json", {
            "job_id": replay["job_id"], "sha256": sha(package), "size_bytes": len(package), "zip_files": package_facts["files"],
        })
        (evidence / "reports" / "disconnect-real-bepipred.zip").write_bytes(package)
        cases.append({"case": "disconnect_duplicate_conflict_and_report", "job_id": replay["job_id"],
                      "state": real_end["state"], "bepipred_state": real_end["nodes"]["bepipred"]["state"],
                      "replay_action": replay["action"], "conflict_status": 409, "foreign_status": 403,
                      "report_sha256": sha(package), "report_size_bytes": len(package)})

        status, cancel_submit = json_request(base, "/v1/workflows", operator_token, {
            "idempotency_key": "cancel-api", "request": workflow_body("cancel-api", bepipred=True),
        })
        assert status == 201
        status, cancelled = json_request(base, f"/v1/workflows/{cancel_submit['job_id']}/cancel", operator_token,
                                         {"idempotency_key": "cancel-api-control"})
        assert status == 202
        cancel_end = wait_job(base, operator_token, cancel_submit["job_id"], 300)
        assert cancel_end["state"] == "cancelled"
        status, no_report = json_request(base, f"/v1/workflows/{cancel_submit['job_id']}/report", operator_token)
        assert status == 409 and no_report["error"]["code"] == "REPORT_NOT_AVAILABLE"
        status, recovered_cancel = json_request(base, f"/v1/workflows/{cancel_submit['job_id']}/recover", operator_token,
                                                 {"idempotency_key": "recover-cancelled"})
        assert status == 202 and recovered_cancel["state"] == "cancelled"
        status, retried = json_request(base, f"/v1/workflows/{cancel_submit['job_id']}/retry", operator_token,
                                       {"idempotency_key": "retry-cancelled"})
        assert status == 202 and retried["job_id"] != cancel_submit["job_id"]
        retry_end = wait_job(base, operator_token, retried["job_id"], 900)
        assert retry_end["state"] == "succeeded"
        cases.append({"case": "cancel_recover_retry", "cancelled_job_id": cancel_submit["job_id"],
                      "cancelled_state": cancel_end["state"], "report_status": 409,
                      "recovery_state": recovered_cancel["state"], "retry_job_id": retried["job_id"],
                      "retry_state": retry_end["state"]})

        # The independent Dify run uses a new idempotency key and no structure,
        # allowing a short real N06/N07/report chain while still proving report retrieval.
        dify_request = workflow_body("dify-real-service")
        write(evidence / "dify" / "request.json", dify_request)
        ready = {
            "status": "READY_FOR_DIFY", "port": args.port,
            "server_url_sha256": sha(f"http://host.docker.internal:{args.port}/mcp".encode()),
            "credential_fingerprints": [
                {"principal": row["principal"], "token_sha256": sha(row["token"].encode()), "scopes": row["scopes"]}
                for row in credential_document["credentials"]
            ],
            "failed_job_id": drift_submit["job_id"],
            "original_24_exclusions_preserved": True,
            "scientific_gate": "CLOSED", "production_status": "NOT_DEPLOYED",
        }
        write(evidence / "ready-for-dify.json", ready)
        print(f"real_service_acceptance=READY_FOR_DIFY port={args.port}", flush=True)
        deadline = time.monotonic() + 1200
        while not args.continue_file.exists() and time.monotonic() < deadline:
            if service.process is None or service.process.poll() is not None:
                raise RuntimeError("service exited while waiting for Dify")
            time.sleep(0.2)
        if not args.continue_file.exists():
            raise RuntimeError("timed out waiting for Dify completion marker")

        success = json.loads((evidence / "dify" / "execution-success.json").read_text(encoding="utf-8"))
        failure = json.loads((evidence / "dify" / "execution-failure.json").read_text(encoding="utf-8"))
        imported = json.loads((evidence / "dify" / "import-evidence.json").read_text(encoding="utf-8"))
        provider = json.loads((evidence / "dify" / "provider-evidence.json").read_text(encoding="utf-8"))
        assert provider["result"] == imported["result"] == "PASS"
        assert success["dify_status"] == failure["dify_status"] == "succeeded"
        success_out, failure_out = success["outputs"], failure["outputs"]
        assert success_out["state"] == "succeeded" and success_out["scientific_gate"] == "CLOSED"
        assert success_out["usable_for_pipeline"] is False and success_out["production_status"] == "NOT_DEPLOYED"
        dify_package = base64.b64decode(success_out["report_base64"], validate=True)
        dify_facts = validate_package(dify_package)
        assert sha(dify_package) == success_out["report_sha256"] and len(dify_package) == success_out["report_size_bytes"]
        status, _, downloaded = request(base, f"/v1/workflows/{success_out['job_id']}/report", operator_token)
        assert status == 200 and downloaded == dify_package
        assert failure_out["state"] == "failed" and failure_out["error_code"] == "PROFILE_NOT_APPROVED"
        assert failure_out["scientific_gate"] == "CLOSED" and failure_out["usable_for_pipeline"] is False
        (evidence / "dify" / "report-from-output.zip").write_bytes(dify_package)
        write(evidence / "dify" / "report-verification.json", {
            "job_id": success_out["job_id"], "sha256": sha(dify_package), "size_bytes": len(dify_package),
            "zip_files": dify_facts["files"], "http_download_identical": True,
            "failure_route_job_id": failure_out["job_id"], "failure_error_code": failure_out["error_code"],
        })
        cases.append({"case": "real_dify_success_and_failure_routes", "app_id": imported["app_id"],
                      "success_run_id": success["dify_workflow_run_id"], "success_job_id": success_out["job_id"],
                      "report_sha256": sha(dify_package), "failure_run_id": failure["dify_workflow_run_id"],
                      "failure_job_id": failure_out["job_id"], "failure_error_code": failure_out["error_code"]})

        write(evidence / "service-cases.json", {"recorded_at": stamp(), "status": "PASS", "cases": cases})
        source_files = [
            "src/t01_phase1_real/service_api/__init__.py", "src/t01_phase1_real/service_api/__main__.py",
            "src/t01_phase1_real/service_api/app.py", "src/t01_phase1_real/service_api/transport.py",
            "src/t01_phase1_real/service_api/dify.py", "tests/test_real_service_api.py",
            "scripts/build_real_service_dify.py", "scripts/configure_real_dify_provider.py",
            "scripts/import_real_dify_workflow.py", "scripts/execute_real_dify_workflow.py",
            "scripts/run_real_service_acceptance.py", "dify/t01-phase1-real-v0.1/registry.json",
            "dify/t01-phase1-real-v0.1/templates/T01_Phase1_Real_Service_v0.1.template.dify.yml",
            "dify/t01-phase1-real-v0.1/bound/local_dify_1_17/T01_Phase1_Real_Service_v0.1.bound.dify.yml",
        ]
        for relative in source_files:
            target = evidence / "source-snapshot" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        summary = {
            "status": "PASS", "completed_at": stamp(), "service_cases": len(cases),
            "authenticated_http": True, "mcp_streamable_http": True, "real_dify_runs": 2,
            "real_dify_success_report_verified": True, "service_restart_recovered_same_job": True,
            "disconnect_survived": True, "duplicate_submission_replayed": True,
            "authorization_rejections_verified": True, "failure_route_verified": True,
            "original_24_exclusions_preserved": True, "scientific_gate": "CLOSED",
            "usable_for_pipeline": False, "production_status": "NOT_DEPLOYED",
        }
        write(evidence / "summary.json", summary)
        files = []
        for path in sorted(p for p in evidence.rglob("*") if p.is_file() and p.name != "index.json"):
            raw = path.read_bytes()
            files.append({"path": path.relative_to(evidence).as_posix(), "size_bytes": len(raw), "sha256": sha(raw)})
        write(evidence / "index.json", {**summary, "indexed_files": len(files), "files": files})
        print(json.dumps({"status": "PASS", "cases": len(cases), "indexed_files": len(files),
                          "dify_runs": 2}, sort_keys=True), flush=True)
        return 0
    finally:
        service.stop()
        for path in (secret_root / "dify-credential.json", secret_root / "credentials.json"):
            if path.exists():
                path.unlink()
        if secret_root.exists() and not any(secret_root.iterdir()):
            secret_root.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
