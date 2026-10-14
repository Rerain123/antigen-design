"""Run, assemble, regress, freeze, or verify an independent M4 campaign."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from t01_phase1_mock.dify.campaign import (
    M4_PARTITION_RESULT_VERSION,
    _load_campaign,
    assemble_campaign_result,
    campaign_root,
    create_freeze_manifest,
    drive_campaign_role,
    prepare_campaign,
    verify_freeze_manifest,
)
from t01_phase1_mock.jsonio import ContractError, load_json, pretty_json_bytes, sha256_bytes
from t01_phase1_mock.paths import PROJECT_ROOT


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _health_check(url: str) -> dict[str, object]:
    if url != "http://127.0.0.1:18081/healthz":
        raise ContractError("M4 only accepts the frozen localhost Mock health endpoint")
    try:
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - fixed localhost URL.
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ContractError(f"M4 Mock transport health check failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContractError("M4 Mock transport health response must be an object")
    return payload


def _run_partition(
    *,
    partition_id: str,
    command: list[str],
    display_command: list[str],
    cwd: Path,
    count_pattern: str,
    log_path: Path,
) -> dict[str, object]:
    if log_path.exists():
        raise ContractError(f"M4 partition log already exists: {log_path}")
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    elapsed = round(time.perf_counter() - started, 3)
    output = completed.stdout + completed.stderr
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    matches = re.findall(count_pattern, output)
    count = int(matches[-1]) if matches else None
    return {
        "partition_id": partition_id,
        "status": "PASS" if completed.returncode == 0 and count is not None else "FAIL",
        "exit_code": completed.returncode,
        "passed_count": count,
        "command": display_command,
        "working_directory": cwd.relative_to(PROJECT_ROOT).as_posix() or ".",
        "duration_seconds": elapsed,
        "output_log": {
            "path": log_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": sha256_bytes(log_path.read_bytes()),
        },
    }


def record_partitions(campaign_id: str) -> dict[str, object]:
    root, _ = _load_campaign(campaign_id)
    result_path = root / "T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json"
    result = load_json(result_path)
    if result.get("status") != "PASS" or result.get("blocker_failure_count") != 0:
        raise ContractError("M4 partitions require a passing assembled campaign result")
    python = sys.executable
    checks = root / "checks"
    partition_path = root / "regression-partitions.json"
    if checks.exists() or partition_path.exists():
        raise ContractError(
            "M4 partition evidence already exists; choose a new campaign instead of overwriting"
        )
    definitions = (
        (
            "documentation",
            [python, str(PROJECT_ROOT / "scripts" / "check_docs.py")],
            ["python", "scripts/check_docs.py"],
            PROJECT_ROOT,
            r"markdown_files=(\d+)",
        ),
        (
            "current_phase1",
            [python, "-m", "pytest", "-q", "-o", "addopts="],
            ["python", "-m", "pytest", "-q", "-o", "addopts="],
            PROJECT_ROOT,
            r"(\d+) passed",
        ),
        (
            "legacy_full_mock",
            [python, "-m", "pytest", "-q", "-o", "addopts="],
            ["python", "-m", "pytest", "-q", "-o", "addopts="],
            PROJECT_ROOT / "legacy" / "full-t01-mock-v0.1",
            r"(\d+) passed",
        ),
        (
            "legacy_s07",
            [python, "-m", "pytest", "-q", "-o", "addopts="],
            ["python", "-m", "pytest", "-q", "-o", "addopts="],
            PROJECT_ROOT / "legacy" / "s07",
            r"(\d+) passed",
        ),
    )
    records = [
        _run_partition(
            partition_id=partition_id,
            command=command,
            display_command=display,
            cwd=cwd,
            count_pattern=pattern,
            log_path=checks / f"{partition_id}.log",
        )
        for partition_id, command, display, cwd, pattern in definitions
    ]
    counts = {item["partition_id"]: item["passed_count"] for item in records}
    passed = (
        all(item["status"] == "PASS" for item in records)
        and isinstance(counts["documentation"], int)
        and counts["documentation"] >= 113
        and isinstance(counts["current_phase1"], int)
        and counts["current_phase1"] >= 164
        and counts["legacy_full_mock"] == 74
        and counts["legacy_s07"] == 41
    )
    result: dict[str, object] = {
        "document_type": "T01_PHASE1_MOCK_M4_PARTITION_RESULT",
        "result_version": M4_PARTITION_RESULT_VERSION,
        "campaign_id": campaign_id,
        "status": "PASS" if passed else "FAIL",
        "partition_count": 4,
        "partitions": records,
    }
    partition_path.write_bytes(pretty_json_bytes(result))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--campaign-id", required=True)
    prepare.add_argument(
        "--health-url", default="http://127.0.0.1:18081/healthz"
    )
    drive = subparsers.add_parser("drive")
    drive.add_argument("--campaign-id", required=True)
    drive.add_argument("--role", choices=("main", "debug"), required=True)
    assemble = subparsers.add_parser("assemble")
    assemble.add_argument("--campaign-id", required=True)
    partitions = subparsers.add_parser("record-partitions")
    partitions.add_argument("--campaign-id", required=True)
    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--campaign-id", required=True)
    subparsers.add_parser("verify")
    args = parser.parse_args(argv)

    if args.command == "prepare":
        result = prepare_campaign(
            args.campaign_id,
            transport_health=_health_check(args.health_url),
            prepared_at=_utc_now(),
        )
        summary = {"state": result["state"], "campaign_id": result["campaign_id"]}
    elif args.command == "drive":
        result = drive_campaign_role(args.campaign_id, args.role)
        summary = {
            "campaign_id": result["campaign_id"],
            "role": result["role"],
            "checkpoint_count": result["checkpoint_count"],
        }
    elif args.command == "assemble":
        result = assemble_campaign_result(args.campaign_id)
        summary = {
            "status": result["status"],
            "campaign_id": result["campaign_id"],
            "blockers": result["blocker_failure_count"],
        }
    elif args.command == "record-partitions":
        result = record_partitions(args.campaign_id)
        summary = {"status": result["status"], "campaign_id": result["campaign_id"]}
    elif args.command == "freeze":
        result = create_freeze_manifest(args.campaign_id, frozen_at=_utc_now())
        summary = {
            "state": result["release_state"],
            "campaign_id": result["campaign_id"],
            "assets": result["frozen_asset_count"],
        }
    else:
        summary = verify_freeze_manifest()
        result = summary
    print(json.dumps(summary, ensure_ascii=False))
    if result.get("status") == "FAIL":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
