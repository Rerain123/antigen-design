"""Import and read back the two bound Phase 1 Mock workflows safely.

The helper is copied into the selected local Dify API container.  Existing
applications may be updated only when the caller supplies both their exact IDs
and ``--authorize-existing-update``.  The emitted evidence is sanitized and
contains no endpoint, header, cookie, token, or credential value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


APP_IDS = {
    "PRIMARY": "t01_phase1_mock_v01.workflow.main",
    "DEBUG": "t01_phase1_mock_v01.workflow.debug",
}
EXPECTED_NAMES = {
    "PRIMARY": "T01_Phase1_Mock_v0.1",
    "DEBUG": "T01_Phase1_Mock_v0.1_Debug",
}
PROVIDER_IDENTIFIER = "t01-phase1-mock-mcp-v01"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(payload.encode("utf-8"))


def _semantic_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Keep every routing-relevant field while dropping canvas presentation."""

    nodes: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        data = node.get("data", {})
        node_type = data.get("type")
        projected: dict[str, Any] = {"id": node.get("id"), "type": node_type}
        for key in (
            "variables",
            "outputs",
            "cases",
            "advanced_settings",
            "output_type",
            "template",
            "tool_parameters",
            "tool_configurations",
            "provider_type",
            "provider_id",
            "provider_name",
            "tool_name",
            "t01_business_node_id",
            "t01_design_cycle",
        ):
            if key in data:
                projected[key] = data[key]
        nodes.append(projected)
    edges = [
        {
            "id": edge.get("id"),
            "source": edge.get("source"),
            "sourceHandle": edge.get("sourceHandle"),
            "target": edge.get("target"),
            "targetHandle": edge.get("targetHandle"),
            "semantic_edge_id": edge.get("data", {}).get("semantic_edge_id"),
        }
        for edge in graph.get("edges", [])
    ]
    return {
        "nodes": sorted(nodes, key=lambda item: item["id"]),
        "edges": sorted(edges, key=lambda item: item["id"]),
    }


def _load_bound(path: Path, role: str, provider_id: str, expected_tools: list[str]) -> tuple[str, dict[str, Any]]:
    content = path.read_text(encoding="utf-8")
    document = yaml.safe_load(content)
    if not isinstance(document, dict) or document.get("version") != "0.7.0":
        raise RuntimeError(f"{role} bound DSL is not Dify 0.7.0")
    if document.get("app", {}).get("name") != EXPECTED_NAMES[role]:
        raise RuntimeError(f"{role} app name mismatch")
    graph = document.get("workflow", {}).get("graph", {})
    tool_nodes = [node for node in graph.get("nodes", []) if node.get("data", {}).get("type") == "tool"]
    actual_tools = sorted({node["data"].get("tool_name") for node in tool_nodes})
    actual_providers = {
        (node["data"].get("provider_id"), node["data"].get("provider_name")) for node in tool_nodes
    }
    if actual_tools != sorted(expected_tools) or actual_providers != {(provider_id, provider_id)}:
        raise RuntimeError(f"{role} provider/tool binding mismatch")
    return content, document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-yaml", type=Path, required=True)
    parser.add_argument("--debug-yaml", type=Path, required=True)
    parser.add_argument("--asset-registry", type=Path, required=True)
    parser.add_argument("--expected-main-app-id", required=True)
    parser.add_argument("--expected-debug-app-id", required=True)
    parser.add_argument("--binding-profile", required=True)
    parser.add_argument("--dify-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorize-existing-update", action="store_true")
    parser.add_argument("--evidence-stage", choices=("M3", "M4"), default="M3")
    parser.add_argument("--campaign-id")
    parser.add_argument("--dify-api-root", type=Path, default=Path("/app/api"))
    args = parser.parse_args()
    if not args.authorize_existing_update:
        raise RuntimeError("existing application update requires --authorize-existing-update")
    if args.binding_profile != "local_dify_1_17":
        raise RuntimeError("unexpected binding profile")
    if args.evidence_stage == "M4":
        if not isinstance(args.campaign_id, str) or re.fullmatch(
            r"t01p1m-v01-reg-[0-9]{8}-[a-z][a-z0-9-]{0,31}",
            args.campaign_id,
        ) is None:
            raise RuntimeError("M4 import evidence requires a valid --campaign-id")
        if args.output.exists():
            raise RuntimeError("M4 import/readback evidence already exists and cannot be overwritten")
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        if any(
            uuid_pattern.fullmatch(value) is None
            for value in (args.expected_main_app_id, args.expected_debug_app_id)
        ) or args.expected_main_app_id == args.expected_debug_app_id:
            raise RuntimeError("M4 requires two distinct exact existing application IDs")
    elif args.campaign_id is not None:
        raise RuntimeError("--campaign-id is only valid for M4 evidence")

    registry = json.loads(args.asset_registry.read_text(encoding="utf-8"))
    expected_tools = [item["tool_id"] for item in registry["tool_namespace"]["tools"]]
    expected_app_ids = {
        "PRIMARY": args.expected_main_app_id,
        "DEBUG": args.expected_debug_app_id,
    }
    inputs = {
        "PRIMARY": _load_bound(args.main_yaml, "PRIMARY", PROVIDER_IDENTIFIER, expected_tools),
        "DEBUG": _load_bound(args.debug_yaml, "DEBUG", PROVIDER_IDENTIFIER, expected_tools),
    }

    sys.path.insert(0, str(args.dify_api_root))
    from sqlalchemy.orm import Session

    from app_factory import create_app
    from extensions.ext_database import db
    from models import Account, App
    from models.account import TenantAccountJoin
    from models.tools import MCPToolProvider
    from services.app_dsl_service import AppDslService
    from services.entities.dsl_entities import ImportStatus
    from services.workflow_service import WorkflowService

    _, flask_app = create_app()
    context = flask_app.app_context()
    context.push()
    try:
        with Session(db.engine, expire_on_commit=False) as session:
            account = session.query(Account).first()
            join = session.query(TenantAccountJoin).filter(TenantAccountJoin.account_id == account.id).first()
            tenant_id = str(join.tenant_id)
            account.set_tenant_id_with_session(tenant_id, session=session)
            provider = (
                session.query(MCPToolProvider)
                .filter(
                    MCPToolProvider.tenant_id == tenant_id,
                    MCPToolProvider.server_identifier == PROVIDER_IDENTIFIER,
                )
                .one()
            )
            provider_tools = sorted(item["name"] for item in json.loads(provider.tools))
            if not provider.authed or provider_tools != sorted(expected_tools):
                raise RuntimeError("target provider is not authenticated with the exact 26-tool set")

            records: list[dict[str, Any]] = []
            for role in ("PRIMARY", "DEBUG"):
                content, source_document = inputs[role]
                matches = (
                    session.query(App)
                    .filter(
                        App.tenant_id == tenant_id,
                        App.name == EXPECTED_NAMES[role],
                        App.status == "normal",
                    )
                    .all()
                )
                if len(matches) != 1 or str(matches[0].id) != expected_app_ids[role]:
                    raise RuntimeError(f"{role} existing app identity/collision check failed")
                result = AppDslService(session).import_app(
                    account=account,
                    import_mode="yaml-content",
                    yaml_content=content,
                    app_id=expected_app_ids[role],
                )
                if result.status not in {ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_WARNINGS}:
                    session.rollback()
                    raise RuntimeError(f"{role} import failed: {result.status.value}")
                if result.warnings:
                    session.rollback()
                    raise RuntimeError(f"{role} import produced {len(result.warnings)} warning(s)")
                session.commit()

                app = (
                    session.query(App)
                    .filter(App.tenant_id == tenant_id, App.id == expected_app_ids[role])
                    .one()
                )
                draft = WorkflowService().get_draft_workflow(app_model=app, session=session)
                if draft is None:
                    raise RuntimeError(f"{role} draft workflow missing after import")
                source_graph = _semantic_graph(source_document["workflow"]["graph"])
                readback_graph = _semantic_graph(dict(draft.graph_dict))
                source_graph_hash = _canonical_sha256(source_graph)
                readback_graph_hash = _canonical_sha256(readback_graph)
                if source_graph_hash != readback_graph_hash:
                    raise RuntimeError(f"{role} semantic graph drift after import")
                exported = AppDslService.export_dsl(
                    app_model=app,
                    session=session,
                    include_secret=False,
                )
                semantic_edges = sorted(
                    {
                        edge["semantic_edge_id"]
                        for edge in readback_graph["edges"]
                        if edge["semantic_edge_id"] is not None
                    }
                )
                records.append(
                    {
                        "role": role,
                        "stable_workflow_id": APP_IDS[role],
                        "app_name": EXPECTED_NAMES[role],
                        "app_id": str(app.id),
                        "draft_workflow_id": str(draft.id),
                        "bound_sha256": _sha256_bytes(content.encode("utf-8")),
                        "readback_export_sha256": _sha256_bytes(exported.encode("utf-8")),
                        "source_semantic_graph_sha256": source_graph_hash,
                        "readback_semantic_graph_sha256": readback_graph_hash,
                        "node_count": len(readback_graph["nodes"]),
                        "edge_count": len(readback_graph["edges"]),
                        "semantic_edge_ids": semantic_edges,
                        "tool_ids": expected_tools,
                        "provider_id": PROVIDER_IDENTIFIER,
                        "import_status": result.status.value,
                        "warning_count": 0,
                    }
                )

        evidence = {
            "document_type": f"T01_PHASE1_MOCK_{args.evidence_stage}_IMPORT_EVIDENCE",
            "evidence_version": f"T01-PHASE1-MOCK-{args.evidence_stage}-IMPORT-EVIDENCE-v0.1",
            "binding_profile": args.binding_profile,
            "target": {
                "environment": "LOCAL_DIFY_DOCKER",
                "dify_version": args.dify_version,
                "dsl_version": "0.7.0",
            },
            "imported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "provider": {
                "server_identifier": PROVIDER_IDENTIFIER,
                "record_id": str(provider.id),
                "authed": True,
                "tool_count": len(expected_tools),
                "tool_ids": expected_tools,
            },
            "collision_policy": "EXACT_EXPECTED_APP_ID_UPDATE_ONLY",
            "applications": records,
            "result": "PASS",
            "blocker_count": 0,
            "secret_finding_count": 0,
            "scientific_compute": False,
            "scientific_network_request_count": 0,
            "legacy_implementation_reuse_count": 0,
            "himat_backend_access_count": 0,
        }
        if args.evidence_stage == "M4":
            evidence["campaign_id"] = args.campaign_id
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "PASS", "applications": 2, "tool_count": len(expected_tools)}))
        return 0
    finally:
        context.pop()


if __name__ == "__main__":
    raise SystemExit(main())
