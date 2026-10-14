"""Run one discovery CLI command and capture immutable execution evidence.

This helper is for controlled campaign commands only. It is not exposed through
MCP and must never receive secrets on its command line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Non-secret environment override to record with the exchange.",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    return args


def main() -> int:
    args = parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty evidence directory: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    executable = Path(args.command[0]).resolve()
    if not executable.is_file():
        raise SystemExit(f"executable does not exist: {executable}")

    stdout_path = args.output_dir / "stdout.txt"
    stderr_path = args.output_dir / "stderr.txt"
    started_at = utc_now()
    started = time.perf_counter()
    timed_out = False
    environment = os.environ.copy()
    environment_overrides: dict[str, str] = {}
    for item in args.env:
        if "=" not in item:
            raise SystemExit(f"invalid --env value: {item}")
        key, value = item.split("=", 1)
        if not key:
            raise SystemExit("environment variable name cannot be empty")
        environment[key] = value
        environment_overrides[key] = value
    try:
        completed = subprocess.run(
            args.command,
            capture_output=True,
            text=True,
            check=False,
            timeout=args.timeout_seconds,
            cwd=args.cwd,
            env=environment,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    duration_ms = round((time.perf_counter() - started) * 1000)
    finished_at = utc_now()
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    record = {
        "exchange_id": args.exchange_id,
        "classification": "discovery_evidence",
        "production_deployment_status": "NOT_DEPLOYED",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "command": args.command,
        "executable": {
            "name": executable.name,
            "size_bytes": executable.stat().st_size,
            "sha256": sha256_file(executable),
        },
        "timeout_seconds": args.timeout_seconds,
        "working_directory": str(args.cwd) if args.cwd else None,
        "environment_overrides": environment_overrides,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "stdout": {
            "file": stdout_path.name,
            "size_bytes": stdout_path.stat().st_size,
            "sha256": sha256_file(stdout_path),
        },
        "stderr": {
            "file": stderr_path.name,
            "size_bytes": stderr_path.stat().st_size,
            "sha256": sha256_file(stderr_path),
        },
    }
    (args.output_dir / "exchange.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 124 if timed_out else int(exit_code or 0)


if __name__ == "__main__":
    sys.exit(main())
