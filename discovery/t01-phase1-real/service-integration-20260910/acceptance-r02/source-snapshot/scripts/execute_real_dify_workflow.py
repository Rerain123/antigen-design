"""Invoke the exact real-service Dify application and capture sanitized outputs."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path


APP_NAME = "T01_Phase1_Real_Service_v0.1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--operation", choices=("SUBMIT", "GET_EXISTING"), required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--idempotency-key", default="")
    parser.add_argument("--job-id", default="")
    parser.add_argument("--wait-timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dify-api-root", type=Path, default=Path("/app/api"))
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("Dify execution capture already exists")
    if args.operation == "SUBMIT" and (args.request is None or not args.idempotency_key or args.job_id):
        raise RuntimeError("SUBMIT requires request and idempotency key only")
    if args.operation == "GET_EXISTING" and (not args.job_id or args.request is not None or args.idempotency_key):
        raise RuntimeError("GET_EXISTING requires job ID only")
    request_json = args.request.read_text(encoding="utf-8") if args.request else ""
    if request_json:
        parsed = json.loads(request_json)
        request_json = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sys.path.insert(0, str(args.dify_api_root))

    from app_factory import create_app
    from core.app.entities.app_invoke_entities import InvokeFrom
    from extensions.ext_database import db
    from models import Account, App
    from models.account import TenantAccountJoin
    from services.app_generate_service import AppGenerateService
    from services.workflow_service import WorkflowService

    _, flask_app = create_app()
    for name in ("httpx", "httpcore", "core.mcp", "core.tools"):
        logging.getLogger(name).setLevel(logging.WARNING)
    context = flask_app.app_context()
    context.push()
    try:
        account = db.session.query(Account).first()
        join = db.session.query(TenantAccountJoin).filter(TenantAccountJoin.account_id == account.id).first()
        account.set_tenant_id_with_session(join.tenant_id, session=db.session)
        app = db.session.query(App).filter(
            App.tenant_id == join.tenant_id, App.id == args.app_id,
            App.name == APP_NAME, App.status == "normal",
        ).one()
        draft = WorkflowService().get_draft_workflow(app_model=app, session=db.session)
        if draft is None:
            raise RuntimeError("exact Dify app has no draft workflow")
        try:
            response = AppGenerateService.generate(
                app_model=app, user=account,
                args={"inputs": {
                    "operation": args.operation, "request_json": request_json,
                    "idempotency_key": args.idempotency_key, "job_id": args.job_id,
                    "wait_timeout_seconds": args.wait_timeout_seconds,
                }, "response_mode": "blocking"},
                invoke_from=InvokeFrom.DEBUGGER, streaming=False, session=db.session,
            )
            value = response if isinstance(response, dict) else response.model_dump(mode="json")
            data = value["data"]
            outputs = data.get("outputs") or {}
            capture = {
                "document_type": "T01_PHASE1_REAL_SERVICE_DIFY_EXECUTION",
                "version": "0.1.0", "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "app_name": APP_NAME, "app_id": str(app.id), "draft_workflow_id": str(draft.id),
                "operation": args.operation, "dify_workflow_run_id": value["workflow_run_id"],
                "dify_status": str(data["status"]), "dify_error": data.get("error"),
                "total_steps": data.get("total_steps"), "outputs": outputs,
                "credential_recorded": False,
            }
        except Exception as exc:
            db.session.rollback()
            capture = {
                "document_type": "T01_PHASE1_REAL_SERVICE_DIFY_EXECUTION",
                "version": "0.1.0", "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "app_name": APP_NAME, "app_id": str(app.id), "draft_workflow_id": str(draft.id),
                "operation": args.operation, "dify_workflow_run_id": None,
                "dify_status": "failed", "dify_error": f"{type(exc).__name__}: {exc}",
                "total_steps": 0, "outputs": {}, "credential_recorded": False,
            }
        args.output.write_text(json.dumps(capture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": capture["dify_status"], "workflow_run_id": capture["dify_workflow_run_id"],
                          "total_steps": capture["total_steps"]}))
        return 0 if capture["dify_status"] == "succeeded" else 2
    finally:
        context.pop()


if __name__ == "__main__":
    raise SystemExit(main())
