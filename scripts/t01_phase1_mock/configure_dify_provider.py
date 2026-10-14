"""Safely repoint the dedicated Phase 1 Mock MCP provider inside Dify.

This helper is intended to be copied into the local Dify API container.  It
updates only the already-created, tenant-scoped Phase 1 Mock provider, validates
the new URL through Dify's own MCP client, and refuses any tool-set drift.
It never prints the URL, headers, credentials, or decrypted database fields.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


PROVIDER_IDENTIFIER = "t01-phase1-mock-mcp-v01"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--expected-tools-json", type=Path, required=True)
    parser.add_argument("--dify-api-root", type=Path, default=Path("/app/api"))
    args = parser.parse_args()
    registry = json.loads(args.expected_tools_json.read_text(encoding="utf-8"))
    expected_ids = sorted(item["tool_id"] for item in registry["tool_namespace"]["tools"])
    sys.path.insert(0, str(args.dify_api_root))

    # Dify imports stay inside main so repository-side unit tests do not need a
    # Dify installation.
    from sqlalchemy.orm import Session

    from app_factory import create_app
    from extensions.ext_database import db
    from models import Account
    from models.account import TenantAccountJoin
    from services.tools.mcp_tools_manage_service import MCPToolManageService

    _, flask_app = create_app()
    context = flask_app.app_context()
    context.push()
    try:
        with Session(db.engine, expire_on_commit=False) as session:
            account = session.query(Account).first()
            join = session.query(TenantAccountJoin).filter(TenantAccountJoin.account_id == account.id).first()
            tenant_id = str(join.tenant_id)
            service = MCPToolManageService(session=session)
            provider = service.get_provider(server_identifier=PROVIDER_IDENTIFIER, tenant_id=tenant_id)
            provider_record_id = str(provider.id)
            validation_data = service.get_provider_for_url_validation(
                tenant_id=tenant_id,
                provider_id=provider_record_id,
            )

        validation = MCPToolManageService.validate_server_url_standalone(
            tenant_id=tenant_id,
            new_server_url=args.server_url,
            validation_data=validation_data,
        )
        reconnect = validation.reconnect_result
        if reconnect is None:
            # An unchanged URL still needs a fresh enumeration for this command
            # to be evidence-bearing.
            reconnect = MCPToolManageService.reconnect_with_url(
                server_url=args.server_url,
                headers=validation_data.headers,
                timeout=validation_data.timeout,
                sse_read_timeout=validation_data.sse_read_timeout,
            )
        tools = json.loads(reconnect.tools)
        actual_ids = sorted(item["name"] for item in tools)
        if actual_ids != expected_ids:
            raise RuntimeError(
                f"provider tool set mismatch: expected={len(expected_ids)} actual={len(actual_ids)}"
            )
        if not reconnect.authed:
            raise RuntimeError("provider did not authenticate to the no-credential mock endpoint")

        with Session(db.engine, expire_on_commit=False) as session:
            service = MCPToolManageService(session=session)
            provider = service.get_provider(server_identifier=PROVIDER_IDENTIFIER, tenant_id=tenant_id)
            if validation.encrypted_server_url and validation.server_url_hash:
                provider.server_url = validation.encrypted_server_url
                provider.server_url_hash = validation.server_url_hash
            provider.authed = reconnect.authed
            provider.tools = reconnect.tools
            provider.encrypted_credentials = reconnect.encrypted_credentials
            provider.updated_at = datetime.now(UTC).replace(tzinfo=None)
            session.commit()

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "provider_identifier": PROVIDER_IDENTIFIER,
                    "provider_record_id": provider_record_id,
                    "tool_count": len(actual_ids),
                    "authed": True,
                    "url_recorded": False,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        context.pop()


if __name__ == "__main__":
    raise SystemExit(main())
