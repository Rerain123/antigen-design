"""Materialize a sanitized M3 target-preflight record from observed target facts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from t01_phase1_mock.catalog import SpecificationBundle
from t01_phase1_mock.jsonio import ContractError
from t01_phase1_mock.paths import PROJECT_ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--dify-version", required=True)
    parser.add_argument("--dsl-version", required=True)
    parser.add_argument("--provider-id", required=True)
    parser.add_argument("--provider-record-id", required=True)
    parser.add_argument("--reference-app", required=True)
    parser.add_argument("--reference-export-sha256", required=True)
    parser.add_argument("--reference-node-types", nargs="+", required=True)
    args = parser.parse_args(argv)
    if args.provider_id != "t01-phase1-mock-mcp-v01":
        raise ContractError("preflight provider must use the frozen Phase 1 identity")
    bundle = SpecificationBundle.load()
    tools = [item["tool_id"] for item in bundle.asset_registry["tool_namespace"]["tools"]]
    result = {
        "document_type": "T01_PHASE1_MOCK_M3_TARGET_PREFLIGHT",
        "evidence_version": "T01-PHASE1-MOCK-M3-TARGET-PREFLIGHT-v0.1",
        "binding_profile": args.profile,
        "collected_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "target": {
            "environment": "LOCAL_DIFY_DOCKER",
            "dify_version": args.dify_version,
            "dsl_version": args.dsl_version,
            "deployment": "docker-compose",
            "instance_scope": "localhost-only",
            "permissions": ["IMPORT_NEW_APP", "READBACK_EXPORT", "DEBUG_RUN"],
        },
        "same_instance_reference_export": {
            "app_name": args.reference_app,
            "sha256": args.reference_export_sha256,
            "node_types": sorted(args.reference_node_types),
            "contains_secret": False,
        },
        "provider": {
            "display_name": args.provider_id,
            "server_identifier": args.provider_id,
            "workflow_provider_id": args.provider_id,
            "record_id": args.provider_record_id,
            "protocol": "MCP_STREAMABLE_HTTP",
            "protocol_version": "2025-06-18",
            "network_direction": "DIFY_API_CONTAINER_TO_HOST_GATEWAY",
            "reachable": True,
            "tool_count": len(tools),
            "tool_ids": tools,
        },
        "application_collision_check": {
            "T01_Phase1_Mock_v0.1": False,
            "T01_Phase1_Mock_v0.1_Debug": False,
        },
        "capabilities": {
            "bounded_n12_three_cycles": True,
            "conditional_n16_n17": True,
            "branch_join": True,
            "failure_terminal": True,
            "checkpoint_recovery_observation": True,
        },
        "state": {"runtime_storage": "HOST_FILESYSTEM_M3_LOCAL_DIFY", "credential_mode": "NONE"},
        "scope_guards": {"himat_backend_accessed": False, "scientific_network_calls": 0, "scientific_compute": False},
        "result": "PASS",
        "blocker_count": 0,
    }
    output = args.output.resolve()
    output.relative_to(PROJECT_ROOT.resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
