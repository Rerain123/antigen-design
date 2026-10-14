"""Import and read back only the independent Phase 1 real-service workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


APP_NAME = "T01_Phase1_Real_Service_v0.1"
WORKFLOW_ID = "t01_phase1_real_service_v01.workflow.main"
PROVIDER_ID = "t01-phase1-real-service-v01"


def canonical(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def graph(value: dict[str, Any]) -> dict[str, Any]:
    source = value["workflow"]["graph"] if "workflow" in value else value
    nodes = []
    for node in source.get("nodes", []):
        data = node.get("data", {})
        row = {"id": node.get("id")}
        for key in ("type", "variables", "outputs", "cases", "advanced_settings", "output_type",
                    "tool_parameters", "provider_type", "provider_id", "provider_name", "tool_name"):
            if key in data:
                row[key] = data[key]
        nodes.append(row)
    edges = [{key: edge.get(key) for key in ("id", "source", "sourceHandle", "target", "targetHandle")}
             for edge in source.get("edges", [])]
    return {"nodes": sorted(nodes, key=lambda row: row["id"]), "edges": sorted(edges, key=lambda row: row["id"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yaml", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-app-id")
    parser.add_argument("--authorize-existing-update", action="store_true")
    parser.add_argument("--dify-api-root", type=Path, default=Path("/app/api"))
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("import evidence already exists")
    content = args.yaml.read_text(encoding="utf-8")
    source = yaml.safe_load(content)
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    if source.get("version") != "0.7.0" or source.get("app", {}).get("name") != APP_NAME:
        raise RuntimeError("unexpected real-service DSL identity")
    source_graph = graph(source)
    tools = [row for row in source_graph["nodes"] if row.get("type") == "tool"]
    if {row.get("provider_id") for row in tools} != {PROVIDER_ID}:
        raise RuntimeError("real-service provider binding differs")
    if not {row.get("tool_name") for row in tools} <= set(registry["tool_ids"]):
        raise RuntimeError("workflow tool binding is not registered")
    if any("mock" in str(row).lower() for row in tools):
        raise RuntimeError("Mock provider/tool reference is forbidden")
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
            provider = session.query(MCPToolProvider).filter(
                MCPToolProvider.tenant_id == tenant_id,
                MCPToolProvider.server_identifier == PROVIDER_ID,
            ).one()
            if not provider.authed or sorted(item["name"] for item in json.loads(provider.tools)) != sorted(registry["tool_ids"]):
                raise RuntimeError("dedicated provider is not authenticated with exact tool inventory")
            matches = session.query(App).filter(
                App.tenant_id == tenant_id, App.name == APP_NAME, App.status == "normal",
            ).all()
            if len(matches) > 1:
                raise RuntimeError("real-service application name is not unique")
            created = not matches
            if created:
                if args.expected_app_id is not None or args.authorize_existing_update:
                    raise RuntimeError("new app creation must not carry update authorization")
                app_id = None
            else:
                if not args.authorize_existing_update or args.expected_app_id != str(matches[0].id):
                    raise RuntimeError("existing app update requires exact ID and explicit authorization")
                app_id = str(matches[0].id)
            result = AppDslService(session).import_app(
                account=account, import_mode="yaml-content", yaml_content=content, app_id=app_id,
            )
            if result.status not in {ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_WARNINGS} or result.warnings:
                session.rollback()
                raise RuntimeError(f"Dify import failed or warned: {result.status.value}")
            session.commit()
            app = session.query(App).filter(App.tenant_id == tenant_id, App.id == result.app_id).one()
            draft = WorkflowService().get_draft_workflow(app_model=app, session=session)
            if draft is None:
                raise RuntimeError("imported app has no draft workflow")
            readback_graph = graph(dict(draft.graph_dict))
            if canonical(source_graph) != canonical(readback_graph):
                raise RuntimeError("Dify readback graph differs from bound source")
            exported = AppDslService.export_dsl(app_model=app, session=session, include_secret=False)
            if "Bearer " in exported or "Authorization" in exported:
                raise RuntimeError("export unexpectedly contains credential material")
            evidence = {
                "document_type": "T01_PHASE1_REAL_SERVICE_DIFY_IMPORT_EVIDENCE",
                "version": "0.1.0", "imported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "workflow_id": WORKFLOW_ID, "app_name": APP_NAME, "app_id": str(app.id),
                "draft_workflow_id": str(draft.id), "created": created,
                "provider_id": PROVIDER_ID, "provider_record_id": str(provider.id),
                "bound_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "readback_export_sha256": hashlib.sha256(exported.encode()).hexdigest(),
                "source_semantic_graph_sha256": canonical(source_graph),
                "readback_semantic_graph_sha256": canonical(readback_graph),
                "node_count": len(readback_graph["nodes"]), "edge_count": len(readback_graph["edges"]),
                "tool_node_count": len(tools), "secret_finding_count": 0,
                "mock_reference_count": 0, "result": "PASS",
            }
            args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"status": "PASS", "app_id": str(app.id), "created": created,
                              "nodes": len(readback_graph["nodes"]), "edges": len(readback_graph["edges"])}))
            return 0
    finally:
        context.pop()


if __name__ == "__main__":
    raise SystemExit(main())
