"""Execute a prepared batch inside the target Dify API container.

This file intentionally imports only Dify internals and standard-library modules;
it is copied to the container temporary directory and never installed into Dify.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, "/app/api")

from app_factory import create_app
from core.app.entities.app_invoke_entities import InvokeFrom
from extensions.ext_database import db
from models import Account, App
from models.account import TenantAccountJoin
from services.app_generate_service import AppGenerateService
from services.workflow_service import WorkflowService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ordinals", type=int, nargs="*", help="Execute only selected one-based batch ordinals.")
    args = parser.parse_args()
    batch = json.loads(args.batch.read_text(encoding="utf-8"))
    batch_type = batch.get("document_type")
    if batch_type == "T01_PHASE1_MOCK_M3_DIFY_BATCH":
        evidence_family = "M3"
        campaign_id = None
    elif batch_type == "T01_PHASE1_MOCK_M4_DIFY_BATCH":
        evidence_family = "M4"
        campaign_id = batch.get("campaign_id")
        if not isinstance(campaign_id, str) or re.fullmatch(
            r"t01p1m-v01-reg-[0-9]{8}-[a-z][a-z0-9-]{0,31}", campaign_id
        ) is None:
            raise RuntimeError("M4 batch is missing a valid campaign identity")
        if re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            str(batch.get("expected_app_id", "")),
        ) is None or not isinstance(batch.get("stable_workflow_id"), str):
            raise RuntimeError("M4 batch is missing its exact application identity")
        if args.output.exists():
            raise RuntimeError("M4 target capture already exists and cannot be overwritten")
    else:
        raise RuntimeError(f"unsupported Dify batch type: {batch_type}")
    _, flask_app = create_app()
    for name in ("httpx", "httpcore", "core.mcp", "core.tools"):
        logging.getLogger(name).setLevel(logging.WARNING)
    context = flask_app.app_context()
    context.push()
    try:
        account = db.session.query(Account).first()
        join = db.session.query(TenantAccountJoin).filter(TenantAccountJoin.account_id == account.id).first()
        account.set_tenant_id_with_session(join.tenant_id, session=db.session)
        if evidence_family == "M4":
            named_apps = (
                db.session.query(App)
                .filter(
                    App.tenant_id == join.tenant_id,
                    App.name == batch["app_name"],
                    App.status == "normal",
                )
                .all()
            )
            if len(named_apps) != 1 or str(named_apps[0].id) != batch["expected_app_id"]:
                raise RuntimeError("M4 exact application identity/collision check failed")
            app = (
                db.session.query(App)
                .filter(
                    App.tenant_id == join.tenant_id,
                    App.id == batch["expected_app_id"],
                    App.status == "normal",
                )
                .one()
            )
            draft = WorkflowService().get_draft_workflow(
                app_model=app, session=db.session
            )
            if draft is None:
                raise RuntimeError("M4 exact application has no draft workflow")
        else:
            app = db.session.query(App).filter(App.name == batch["app_name"]).one()
            draft = None
        results = []
        selected = set(args.ordinals or [])
        for ordinal, invocation in enumerate(batch["invocations"], start=1):
            if selected and ordinal not in selected:
                continue
            submitted_request_id = None
            if invocation["operation"] == "SUBMIT":
                submitted_request = json.loads(invocation["request_json"])
                submitted_request_id = submitted_request.get("request_id")
            try:
                response = AppGenerateService.generate(
                    app_model=app,
                    user=account,
                    args={
                        "inputs": {
                            "operation": invocation["operation"],
                            "request_json": invocation["request_json"],
                            "run_id_override": invocation["run_id_override"],
                        },
                        "response_mode": "blocking",
                    },
                    invoke_from=InvokeFrom.DEBUGGER,
                    streaming=False,
                    session=db.session,
                )
                value = response if isinstance(response, dict) else response.model_dump(mode="json")
                data = value["data"]
                results.append(
                    {
                        "ordinal": ordinal,
                        "scenario_key": invocation["scenario_key"],
                        "submission_key": invocation["submission_key"],
                        "operation": invocation["operation"],
                        "submitted_request_id": submitted_request_id,
                        "dify_workflow_run_id": value["workflow_run_id"],
                        "dify_status": str(data["status"]),
                        "dify_error": data.get("error"),
                        "total_steps": data.get("total_steps"),
                        "outputs": data.get("outputs") or {},
                    }
                )
            except Exception as exc:
                db.session.rollback()
                results.append(
                    {
                        "ordinal": ordinal,
                        "scenario_key": invocation["scenario_key"],
                        "submission_key": invocation["submission_key"],
                        "operation": invocation["operation"],
                        "submitted_request_id": submitted_request_id,
                        "dify_workflow_run_id": None,
                        "dify_status": "failed",
                        "dify_error": f"{type(exc).__name__}: {exc}",
                        "total_steps": 0,
                        "outputs": {},
                    }
                )
        failed = [item for item in results if item["dify_status"] != "succeeded"]
        capture = {
            "document_type": f"T01_PHASE1_MOCK_{evidence_family}_DIFY_CAPTURE",
            "capture_version": f"T01-PHASE1-MOCK-{evidence_family}-DIFY-CAPTURE-v0.1",
            "app_name": batch["app_name"],
            "role": batch["role"],
            "status": "PASS" if not failed else "FAIL",
            "invocation_count": len(results),
            "failure_count": len(failed),
            "results": results,
        }
        if campaign_id is not None:
            capture["campaign_id"] = campaign_id
            capture["app_id"] = str(app.id)
            capture["draft_workflow_id"] = str(draft.id)
            capture["stable_workflow_id"] = batch["stable_workflow_id"]
        args.output.write_text(json.dumps(capture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"app_name": batch["app_name"], "invocations": len(results), "failures": len(failed)}))
        return 0 if not failed else 2
    finally:
        context.pop()


if __name__ == "__main__":
    raise SystemExit(main())
