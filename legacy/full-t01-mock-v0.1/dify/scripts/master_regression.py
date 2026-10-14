from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from t01_dify_workflows.regression import (  # noqa: E402
    collect_local_editor_campaign,
    collect_local_traces,
    evaluate_campaign,
    prepare_campaign,
    read_json,
    render_markdown,
    run_campaign,
    write_json,
)


DEFAULT_EXPECTATIONS = ROOT / "dify" / "regression" / "master_expected_25.json"
DEFAULT_INPUT = ROOT / "dify" / "fixtures" / "master_input.example.json"


def _default_run_dir(campaign: str) -> Path:
    return ROOT / "dify" / "regression" / "runs" / campaign


def command_prepare(args: argparse.Namespace) -> int:
    output_dir = args.output_dir or _default_run_dir(args.campaign)
    manifest_path, csv_path = prepare_campaign(
        expectations_path=args.expectations,
        base_input_path=args.base_input,
        campaign=args.campaign,
        output_dir=output_dir,
    )
    print(f"manifest={manifest_path.resolve()}")
    print(f"csv={csv_path.resolve()}")
    print("case_count=25")
    return 0


def command_run(args: argparse.Namespace) -> int:
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(
            f"Missing API key in environment variable {args.api_key_env}. "
            "The key is never stored in project files.",
            file=sys.stderr,
        )
        return 2
    records = run_campaign(
        manifest_path=args.manifest,
        results_path=args.results,
        base_url=args.base_url,
        api_key=api_key,
        user=args.user,
        timeout=args.timeout,
        resume=not args.no_resume,
    )
    print(f"results={args.results.resolve()}")
    print(f"record_count={len(records)}")
    return 0


def command_collect(args: argparse.Namespace) -> int:
    document = collect_local_traces(
        results_path=args.results,
        traces_path=args.traces,
        docker_bin=args.docker_bin,
        db_container=args.db_container,
        db_user=args.db_user,
        db_name=args.db_name,
    )
    print(f"traces={args.traces.resolve()}")
    print(f"trace_record_count={len(document['records'])}")
    return 0


def command_collect_editor(args: argparse.Namespace) -> int:
    results, document = collect_local_editor_campaign(
        manifest_path=args.manifest,
        results_path=args.results,
        traces_path=args.traces,
        docker_bin=args.docker_bin,
        db_container=args.db_container,
        db_user=args.db_user,
        db_name=args.db_name,
    )
    print(f"results={args.results.resolve()}")
    print(f"traces={args.traces.resolve()}")
    print(f"completed_run_count={len(results)}")
    print(f"trace_record_count={len(document['records'])}")
    return 0


def command_report(args: argparse.Namespace) -> int:
    manifest = read_json(args.manifest)
    results = []
    if args.results.exists():
        for line in args.results.read_text(encoding="utf-8").splitlines():
            if line.strip():
                import json

                results.append(json.loads(line))
    traces = read_json(args.traces) if args.traces and args.traces.exists() else None
    report = evaluate_campaign(
        manifest=manifest,
        result_records=results,
        trace_document=traces,
        require_trace=not args.allow_missing_trace,
    )
    write_json(args.report_json, report)
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"report_json={args.report_json.resolve()}")
    print(f"report_md={args.report_md.resolve()}")
    print(
        "total={total} passed={passed} failed={failed}".format(**report["summary"])
    )
    return 0 if report["summary"]["failed"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare, run, collect, and assess T01 Master Mock regressions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Generate 25-case manifest and CSV.")
    prepare.add_argument("--campaign", required=True)
    prepare.add_argument("--expectations", type=Path, default=DEFAULT_EXPECTATIONS)
    prepare.add_argument("--base-input", type=Path, default=DEFAULT_INPUT)
    prepare.add_argument("--output-dir", type=Path)
    prepare.set_defaults(handler=command_prepare)

    run = subparsers.add_parser("run", help="Run the manifest through Dify Workflow API.")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--results", type=Path, required=True)
    run.add_argument("--base-url", default="http://localhost")
    run.add_argument("--api-key-env", default="DIFY_API_KEY")
    run.add_argument("--user", default="t01-master-regression")
    run.add_argument("--timeout", type=float, default=180.0)
    run.add_argument("--no-resume", action="store_true")
    run.set_defaults(handler=command_run)

    collect = subparsers.add_parser(
        "collect", help="Collect local Dify workflow/node traces from PostgreSQL."
    )
    collect.add_argument("--results", type=Path, required=True)
    collect.add_argument("--traces", type=Path, required=True)
    collect.add_argument("--docker-bin", default="docker")
    collect.add_argument("--db-container", default="docker-db_postgres-1")
    collect.add_argument("--db-user", default="postgres")
    collect.add_argument("--db-name", default="dify")
    collect.set_defaults(handler=command_collect)

    collect_editor = subparsers.add_parser(
        "collect-editor",
        help="Collect editor-launched runs and traces from local PostgreSQL.",
    )
    collect_editor.add_argument("--manifest", type=Path, required=True)
    collect_editor.add_argument("--results", type=Path, required=True)
    collect_editor.add_argument("--traces", type=Path, required=True)
    collect_editor.add_argument("--docker-bin", default="docker")
    collect_editor.add_argument("--db-container", default="docker-db_postgres-1")
    collect_editor.add_argument("--db-user", default="postgres")
    collect_editor.add_argument("--db-name", default="dify")
    collect_editor.set_defaults(handler=command_collect_editor)

    report = subparsers.add_parser("report", help="Compare results and traces to expectations.")
    report.add_argument("--manifest", type=Path, required=True)
    report.add_argument("--results", type=Path, required=True)
    report.add_argument("--traces", type=Path)
    report.add_argument("--report-json", type=Path, required=True)
    report.add_argument("--report-md", type=Path, required=True)
    report.add_argument("--allow-missing-trace", action="store_true")
    report.set_defaults(handler=command_report)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
