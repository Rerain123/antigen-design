"""Prepare, drive, or assemble the Phase 1 M3 target acceptance evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from t01_phase1_mock.dify.runner import assemble_m3_result, build_submission_batch, combine_captures, drive_checkpoints, merge_captures
from t01_phase1_mock.jsonio import pretty_json_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--app-name", required=True)
    prepare.add_argument("--role", required=True)
    prepare.add_argument("--output", type=Path, required=True)
    drive = subparsers.add_parser("drive")
    drive.add_argument("--runtime-root", type=Path, required=True)
    drive.add_argument("--submissions", type=Path, required=True)
    drive.add_argument("--finalize-batch", type=Path, required=True)
    drive.add_argument("--driver-capture", type=Path, required=True)
    drive.add_argument("--app-name", required=True)
    drive.add_argument("--role", required=True)
    merge = subparsers.add_parser("merge")
    merge.add_argument("--primary", type=Path, required=True)
    merge.add_argument("--retry", type=Path, action="append", required=True)
    merge.add_argument("--output", type=Path, required=True)
    combine = subparsers.add_parser("combine")
    combine.add_argument("--capture", type=Path, action="append", required=True)
    combine.add_argument("--output", type=Path, required=True)
    assemble = subparsers.add_parser("assemble")
    assemble.add_argument("--manifest", type=Path, required=True)
    assemble.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        build_submission_batch(app_name=args.app_name, role=args.role, output_path=args.output)
    elif args.command == "drive":
        drive_checkpoints(
            runtime_root=args.runtime_root,
            submission_capture_path=args.submissions,
            finalize_batch_path=args.finalize_batch,
            driver_capture_path=args.driver_capture,
            app_name=args.app_name,
            role=args.role,
        )
    elif args.command == "merge":
        merged = merge_captures(args.primary, args.retry, args.output)
        print(json.dumps({"status": merged["status"], "transport_retries": merged["transport_retry_count"]}))
        return 0 if merged["status"] == "PASS" else 2
    elif args.command == "combine":
        combined = combine_captures(args.capture, args.output)
        print(json.dumps({"status": combined["status"], "invocations": combined["invocation_count"], "chunks": combined["chunk_count"]}))
        return 0 if combined["status"] == "PASS" else 2
    else:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        to_paths = lambda value: {key: Path(path) for key, path in value.items()}  # noqa: E731
        result = assemble_m3_result(
            main_paths=to_paths(manifest["main"]["captures"]),
            debug_paths=to_paths(manifest["debug"]["captures"]),
            main_runtime_root=Path(manifest["main"]["runtime_root"]),
            debug_runtime_root=Path(manifest["debug"]["runtime_root"]),
            workflow_facts=manifest["workflow_facts"],
            instance_mappings=manifest["instance_mappings"],
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(pretty_json_bytes(result))
        print(json.dumps({"status": result["status"], "blockers": result["blocker_failure_count"]}))
        return 0 if result["status"] == "PASS" else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
