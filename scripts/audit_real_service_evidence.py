"""Independently verify one completed authenticated-service/Dify evidence batch."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {"succeeded", "failed", "cancelled", "timed_out"}
SECRET_PATTERNS = (
    re.compile(rb"Authorization\s*:\s*Bearer\s+\S+", re.IGNORECASE),
    re.compile(rb'"bearer_token"\s*:', re.IGNORECASE),
    re.compile(rb'"credentials"\s*:\s*\[', re.IGNORECASE),
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_archive(raw: bytes, label: str, depth: int = 0) -> dict[str, int]:
    if depth > 4 or not zipfile.is_zipfile(io.BytesIO(raw)):
        raise AssertionError(f"invalid nested ZIP: {label}")
    archives = 1
    files = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        names = package.namelist()
        assert len(names) == len(set(names)), f"duplicate ZIP member: {label}"
        for name in names:
            path = PurePosixPath(name)
            assert name and "\\" not in name and not path.is_absolute() and ".." not in path.parts
        if "manifest.json" in names:
            manifest = json.loads(package.read("manifest.json"))
            declared = {row["path"]: row for row in manifest["files"]}
            assert set(declared) == set(names) - {"manifest.json"}
            for name, row in declared.items():
                member = package.read(name)
                assert len(member) == row["size_bytes"] and digest(member) == row["sha256"]
        for name in names:
            if name.endswith("/"):
                continue
            files += 1
            member = package.read(name)
            if zipfile.is_zipfile(io.BytesIO(member)):
                nested = verify_archive(member, f"{label}!/{name}", depth + 1)
                archives += nested["archives"]
                files += nested["files"]
    return {"archives": archives, "files": files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch.resolve()
    runtime_root = args.runtime_root.resolve()
    output = args.output.resolve()
    assert batch.is_dir() and runtime_root.is_dir()
    if output.exists():
        raise RuntimeError("audit output already exists")

    index = load(batch / "index.json")
    expected = {row["path"]: row for row in index["files"]}
    actual = {
        path.relative_to(batch).as_posix(): path
        for path in batch.rglob("*") if path.is_file() and path.name != "index.json"
    }
    assert index["status"] == "PASS" and index["indexed_files"] == len(expected) == 36
    assert set(actual) == set(expected)
    for name, row in expected.items():
        raw = actual[name].read_bytes()
        assert len(raw) == row["size_bytes"] and digest(raw) == row["sha256"]

    snapshot_root = batch / "source-snapshot"
    snapshots = [path for path in snapshot_root.rglob("*") if path.is_file()]
    for snapshot in snapshots:
        source = ROOT / snapshot.relative_to(snapshot_root)
        assert source.is_file() and source.read_bytes() == snapshot.read_bytes()

    registry = load(ROOT / "dify/t01-phase1-real-v0.1/registry.json")
    provider = load(batch / "dify/provider-evidence.json")
    imported = load(batch / "dify/import-evidence.json")
    success = load(batch / "dify/execution-success.json")
    failure = load(batch / "dify/execution-failure.json")
    report_check = load(batch / "dify/report-verification.json")
    assert provider["result"] == "PASS" and provider["authed"] is True
    assert provider["tool_count"] == len(provider["tool_ids"]) == 8
    assert sorted(provider["tool_ids"]) == sorted(registry["tool_ids"])
    assert provider["credential_value_recorded"] is False and provider["server_url_recorded"] is False
    assert imported["result"] == "PASS" and imported["node_count"] == 9
    assert imported["edge_count"] == 9 and imported["tool_node_count"] == 3
    assert imported["source_semantic_graph_sha256"] == imported["readback_semantic_graph_sha256"]
    assert imported["secret_finding_count"] == imported["mock_reference_count"] == 0
    assert success["dify_status"] == failure["dify_status"] == "succeeded"
    assert success["outputs"]["state"] == "succeeded"
    assert success["outputs"]["scientific_gate"] == "CLOSED"
    assert success["outputs"]["usable_for_pipeline"] is False
    assert success["outputs"]["production_status"] == "NOT_DEPLOYED"
    assert failure["outputs"]["state"] == "failed"
    assert failure["outputs"]["error_code"] == "PROFILE_NOT_APPROVED"

    dify_report = base64.b64decode(success["outputs"]["report_base64"], validate=True)
    stored_report = (batch / "dify/report-from-output.zip").read_bytes()
    assert dify_report == stored_report
    assert digest(dify_report) == success["outputs"]["report_sha256"] == report_check["sha256"]
    assert len(dify_report) == success["outputs"]["report_size_bytes"] == report_check["size_bytes"]
    assert report_check["http_download_identical"] is True
    dify_zip = verify_archive(dify_report, "dify-report")
    disconnect_zip = verify_archive((batch / "reports/disconnect-real-bepipred.zip").read_bytes(), "disconnect-report")

    cases = load(batch / "service-cases.json")
    names = {row["case"] for row in cases["cases"]}
    required = {
        "service_restart_recovery", "restart_configuration_drift_fails_closed", "health",
        "missing_auth", "wrong_auth", "controlled_upload",
        "disconnect_duplicate_conflict_and_report", "cancel_recover_retry",
        "real_dify_success_and_failure_routes",
    }
    assert cases["status"] == "PASS" and names == required
    summary = load(batch / "summary.json")
    for key in (
        "real_dify_success_report_verified", "service_restart_recovered_same_job", "disconnect_survived",
        "duplicate_submission_replayed", "authorization_rejections_verified", "failure_route_verified",
    ):
        assert summary[key] is True and index[key] is True
    assert summary["scientific_gate"] == "CLOSED" and summary["usable_for_pipeline"] is False
    assert summary["production_status"] == "NOT_DEPLOYED" and summary["real_dify_runs"] == 2

    leaked = []
    for name, path in actual.items():
        if name.startswith("source-snapshot/"):
            continue
        raw = path.read_bytes()
        if any(pattern.search(raw) for pattern in SECRET_PATTERNS):
            leaked.append(name)
    assert not leaked, leaked

    from t01_phase1_real.common import sha
    from t01_phase1_real.development import Runtime

    runtime = Runtime(runtime_root, scope="svc-" + sha(b"acceptance-tenant")[:24])
    job_ids = set()
    for row in cases["cases"]:
        job_ids.update(value for key, value in row.items() if key.endswith("job_id") and isinstance(value, str))
    for job_id in job_ids:
        assert runtime.get(job_id)["state"] in TERMINAL

    result = {
        "document_type": "T01_PHASE1_REAL_SERVICE_INDEPENDENT_AUDIT",
        "version": "0.1.0",
        "audited_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "PASS",
        "batch_index_sha256": digest((batch / "index.json").read_bytes()),
        "indexed_files_verified": len(expected),
        "source_snapshots_verified": len(snapshots),
        "runtime_jobs_verified": len(job_ids),
        "service_cases_verified": len(cases["cases"]),
        "dify_provider_tools_verified": provider["tool_count"],
        "dify_runs_verified": 2,
        "zip_archives_verified": dify_zip["archives"] + disconnect_zip["archives"],
        "zip_members_verified": dify_zip["files"] + disconnect_zip["files"],
        "secret_findings": 0,
        "scientific_gate": "CLOSED",
        "usable_for_pipeline": False,
        "production_status": "NOT_DEPLOYED",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
