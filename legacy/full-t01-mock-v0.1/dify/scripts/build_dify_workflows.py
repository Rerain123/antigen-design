"""Generate, bind, and validate T-01 Dify workflow DSL files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from t01_dify_workflows import (
    bind_debug_templates,
    bind_master_template,
    bind_stage_templates,
    bind_templates,
    generate_debug_templates,
    generate_templates,
    load_workflows,
    validate_workflow_set,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="regenerate placeholder templates")
    generate.add_argument("--output", type=Path, default=Path("dify/templates"))

    generate_debug = subparsers.add_parser(
        "generate-debug", help="generate standalone one-click Mock debug templates"
    )
    generate_debug.add_argument("--output", type=Path, default=Path("dify/debug/templates"))

    bind = subparsers.add_parser("bind", help="bind instance-specific Dify provider IDs")
    bind.add_argument("--templates", type=Path, default=Path("dify/templates"))
    bind.add_argument("--bindings", type=Path, required=True)
    bind.add_argument("--output", type=Path, default=Path("dify/bound"))

    bind_stages = subparsers.add_parser("bind-stages", help="bind only the eight MCP stage workflows")
    bind_stages.add_argument("--templates", type=Path, default=Path("dify/templates"))
    bind_stages.add_argument("--mcp-provider-id", required=True)
    bind_stages.add_argument("--output", type=Path, default=Path("dify/bound/stages"))

    bind_debug = subparsers.add_parser(
        "bind-debug", help="bind standalone Mock debug templates"
    )
    bind_debug.add_argument("--templates", type=Path, default=Path("dify/debug/templates"))
    bind_debug.add_argument("--mcp-provider-id", required=True)
    bind_debug.add_argument("--output", type=Path, default=Path("dify/debug/bound"))

    bind_master = subparsers.add_parser("bind-master", help="bind the master after stages are published as tools")
    bind_master.add_argument("--templates", type=Path, default=Path("dify/templates"))
    bind_master.add_argument("--bindings", type=Path, required=True)
    bind_master.add_argument("--output", type=Path, default=Path("dify/bound/master"))

    validate = subparsers.add_parser("validate", help="validate a generated workflow directory")
    validate.add_argument("--path", type=Path, required=True)
    validate.add_argument("--allow-placeholders", action="store_true")

    args = parser.parse_args()
    if args.command == "generate":
        paths = generate_templates(args.output)
    elif args.command == "generate-debug":
        paths = generate_debug_templates(args.output)
    elif args.command == "bind":
        bindings = json.loads(args.bindings.read_text(encoding="utf-8"))
        paths = bind_templates(args.templates, args.output, bindings)
    elif args.command == "bind-stages":
        paths = bind_stage_templates(args.templates, args.output, args.mcp_provider_id)
    elif args.command == "bind-debug":
        paths = bind_debug_templates(args.templates, args.output, args.mcp_provider_id)
    elif args.command == "bind-master":
        bindings = json.loads(args.bindings.read_text(encoding="utf-8"))
        paths = [bind_master_template(args.templates, args.output, bindings)]
    else:
        paths = sorted(args.path.glob("*.dify.yml"))
        validate_workflow_set(
            load_workflows(paths),
            allow_placeholders=args.allow_placeholders,
        )
    print(f"workflow_count={len(paths)}")
    for path in paths:
        print(path)
    print("status=PASS")


if __name__ == "__main__":
    main()
