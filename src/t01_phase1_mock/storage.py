"""Namespaced stores for deterministic run, checkpoint, and idempotency state."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol

from .constants import NAMESPACE_ROOT, RUN_ID_PATTERN
from .jsonio import ContractError, load_json, pretty_json_bytes, sha256_bytes
from .paths import DEFAULT_RUNTIME_ROOT, PROJECT_ROOT


class RunStore(Protocol):
    def get_record(self, run_id: str) -> dict[str, Any] | None: ...

    def put_record(self, record: dict[str, Any]) -> None: ...

    def get_idempotency(self, key: str) -> dict[str, str] | None: ...

    def bind_idempotency(self, key: str, fingerprint: str, run_id: str) -> None: ...

    def run_ids(self) -> tuple[str, ...]: ...


class InMemoryRunStore:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._idempotency: dict[str, dict[str, str]] = {}

    def get_record(self, run_id: str) -> dict[str, Any] | None:
        record = self._records.get(run_id)
        return None if record is None else deepcopy(record)

    def put_record(self, record: dict[str, Any]) -> None:
        _validate_record_identity(record)
        self._records[record["run_id"]] = deepcopy(record)

    def get_idempotency(self, key: str) -> dict[str, str] | None:
        item = self._idempotency.get(key)
        return None if item is None else deepcopy(item)

    def bind_idempotency(self, key: str, fingerprint: str, run_id: str) -> None:
        _validate_binding(key, fingerprint, run_id)
        existing = self._idempotency.get(key)
        value = {"fingerprint": fingerprint, "run_id": run_id}
        if existing is not None and existing != value:
            raise ContractError("idempotency binding is append-only")
        self._idempotency[key] = value

    def run_ids(self) -> tuple[str, ...]:
        return tuple(self._records)


def _validate_record_identity(record: dict[str, Any]) -> None:
    if record.get("record_namespace") != NAMESPACE_ROOT:
        raise ContractError("run record namespace mismatch")
    run_id = record.get("run_id")
    if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ContractError(f"invalid run record identity: {run_id}")
    required = {
        "document_type",
        "record_namespace",
        "record_version",
        "run_id",
        "scenario_key",
        "request",
        "canonical_request_fingerprint",
        "checkpoint_index",
        "checkpoint_fact",
        "recovery_of_run_id",
        "control_emission_count",
        "terminal",
        "envelope",
    }
    if set(record) != required:
        raise ContractError("run record fields are incomplete or unexpected")
    if record["document_type"] != "T01_PHASE1_MOCK_RUN_RECORD":
        raise ContractError("run record document type mismatch")
    if record["record_version"] != "T01-PHASE1-MOCK-M2-RUN-RECORD-v0.1":
        raise ContractError("run record version mismatch")
    if not isinstance(record["scenario_key"], str) or not record["scenario_key"]:
        raise ContractError("run record scenario key is invalid")
    if not isinstance(record["request"], dict) or not isinstance(record["envelope"], dict):
        raise ContractError("run record request/envelope is invalid")
    fingerprint = record["canonical_request_fingerprint"]
    if not _is_sha256(fingerprint):
        raise ContractError("run record fingerprint is invalid")
    if not isinstance(record["checkpoint_index"], int) or isinstance(
        record["checkpoint_index"], bool
    ) or record["checkpoint_index"] < 0:
        raise ContractError("run record checkpoint index is invalid")
    if not isinstance(record["checkpoint_fact"], str) or not record["checkpoint_fact"]:
        raise ContractError("run record checkpoint fact is invalid")
    recovery = record["recovery_of_run_id"]
    if recovery is not None and (
        not isinstance(recovery, str) or RUN_ID_PATTERN.fullmatch(recovery) is None
    ):
        raise ContractError("run record recovery identity is invalid")
    if not isinstance(record["control_emission_count"], int) or isinstance(
        record["control_emission_count"], bool
    ) or record["control_emission_count"] < 0:
        raise ContractError("run record control emission count is invalid")
    if not isinstance(record["terminal"], bool):
        raise ContractError("run record terminal flag is invalid")
    if record["envelope"].get("run_id") != run_id:
        raise ContractError("run record envelope identity mismatch")


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_binding(key: str, fingerprint: str, run_id: str) -> None:
    if not isinstance(key, str) or not key:
        raise ContractError("idempotency key must be non-empty")
    if not _is_sha256(fingerprint):
        raise ContractError("idempotency fingerprint must be SHA-256")
    if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ContractError("idempotency run identity is invalid")


class FilesystemRunStore:
    """Small local JSON store used for restart/resume tests and local M2 operation."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or DEFAULT_RUNTIME_ROOT).resolve()
        legacy = (PROJECT_ROOT / "legacy").resolve()
        try:
            self.root.relative_to(legacy)
        except ValueError:
            pass
        else:
            raise ContractError("current-phase runtime store cannot enter legacy")
        self.runs_root = self.root / "runs"
        self.index_path = self.root / "idempotency-index.json"
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def _record_path(self, run_id: str) -> Path:
        if RUN_ID_PATTERN.fullmatch(run_id) is None:
            raise ContractError(f"invalid run_id for storage path: {run_id}")
        candidate = (self.runs_root / run_id / "record.json").resolve()
        try:
            candidate.relative_to(self.runs_root.resolve())
        except ValueError as exc:
            raise ContractError("run storage path escaped namespace") from exc
        return candidate

    @staticmethod
    def _atomic_write(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = pretty_json_bytes(value)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(payload)
        if sha256_bytes(temporary.read_bytes()) != sha256_bytes(payload):
            raise ContractError(f"temporary run record verification failed: {path}")
        temporary.replace(path)

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {
                "document_type": "T01_PHASE1_MOCK_IDEMPOTENCY_INDEX",
                "record_namespace": NAMESPACE_ROOT,
                "entries": {},
            }
        index = load_json(self.index_path)
        if (
            index.get("document_type") != "T01_PHASE1_MOCK_IDEMPOTENCY_INDEX"
            or index.get("record_namespace") != NAMESPACE_ROOT
            or not isinstance(index.get("entries"), dict)
        ):
            raise ContractError("invalid idempotency index")
        for key, value in index["entries"].items():
            if not isinstance(value, dict) or set(value) != {"fingerprint", "run_id"}:
                raise ContractError("invalid idempotency index entry")
            _validate_binding(key, value["fingerprint"], value["run_id"])
        return index

    def get_record(self, run_id: str) -> dict[str, Any] | None:
        path = self._record_path(run_id)
        if not path.exists():
            return None
        record = load_json(path)
        _validate_record_identity(record)
        if record["run_id"] != run_id:
            raise ContractError("run record path/identity mismatch")
        return record

    def put_record(self, record: dict[str, Any]) -> None:
        _validate_record_identity(record)
        self._atomic_write(self._record_path(record["run_id"]), record)

    def get_idempotency(self, key: str) -> dict[str, str] | None:
        item = self._load_index()["entries"].get(key)
        return None if item is None else deepcopy(item)

    def bind_idempotency(self, key: str, fingerprint: str, run_id: str) -> None:
        _validate_binding(key, fingerprint, run_id)
        index = self._load_index()
        existing = index["entries"].get(key)
        value = {"fingerprint": fingerprint, "run_id": run_id}
        if existing is not None and existing != value:
            raise ContractError("idempotency binding is append-only")
        index["entries"][key] = value
        self._atomic_write(self.index_path, index)

    def run_ids(self) -> tuple[str, ...]:
        result: list[str] = []
        if not self.runs_root.exists():
            return ()
        for directory in sorted(self.runs_root.iterdir()):
            if directory.is_dir() and RUN_ID_PATTERN.fullmatch(directory.name):
                if (directory / "record.json").exists():
                    result.append(directory.name)
        return tuple(result)
