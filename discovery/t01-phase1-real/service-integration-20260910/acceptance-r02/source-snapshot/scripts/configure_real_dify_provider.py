"""Create or refresh only the dedicated authenticated Phase 1 real MCP provider.

Run this helper inside the selected Dify API container. The bearer token is read
from a temporary JSON file and is never printed or written to evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


PROVIDER_ID = "t01-phase1-real-service-v01"
PROVIDER_NAME = "T01 Phase1 Real Service v0.1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-provider-record-id")
    parser.add_argument("--dify-api-root", type=Path, default=Path("/app/api"))
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("provider evidence already exists")
    try:
        secret = json.loads(args.credential_file.read_text(encoding="utf-8"))
    finally:
        # The provider persists only Dify's encrypted credential. Remove the
        # plaintext transfer file immediately, including on malformed input.
        args.credential_file.unlink(missing_ok=True)
    if not isinstance(secret, dict) or set(secret) != {"bearer_token"}:
        raise RuntimeError("exact temporary credential document required")
    token = secret["bearer_token"]
    if not isinstance(token, str) or not 32 <= len(token) <= 512:
        raise RuntimeError("temporary bearer token is invalid")
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    expected_tools = sorted(registry["tool_ids"])
    headers = {"Authorization": "Bearer " + token}
    sys.path.insert(0, str(args.dify_api_root))

    from sqlalchemy.orm import Session
    from app_factory import create_app
    from core.entities.mcp_provider import MCPConfiguration
    from extensions.ext_database import db
    from models import Account
    from models.account import TenantAccountJoin
    from models.tools import MCPToolProvider
    from services.tools.mcp_tools_manage_service import MCPToolManageService

    _, flask_app = create_app()
    context = flask_app.app_context()
    context.push()
    try:
        with Session(db.engine, expire_on_commit=False) as session:
            account = session.query(Account).first()
            join = session.query(TenantAccountJoin).filter(TenantAccountJoin.account_id == account.id).first()
            tenant_id = str(join.tenant_id)
            account_id = str(account.id)
            matches = session.query(MCPToolProvider).filter(
                MCPToolProvider.tenant_id == tenant_id,
                MCPToolProvider.server_identifier == PROVIDER_ID,
            ).all()
            if len(matches) > 1:
                raise RuntimeError("dedicated provider identity is not unique")
            service = MCPToolManageService(session=session)
            created = not matches
            if created:
                service.create_provider(
                    tenant_id=tenant_id, name=PROVIDER_NAME, server_url=args.server_url,
                    user_id=account_id, icon="🔐", icon_type="emoji", icon_background="#E4FBCC",
                    server_identifier=PROVIDER_ID, headers=headers,
                    configuration=MCPConfiguration(timeout=300, sse_read_timeout=300),
                )
                session.flush()
                provider = service.get_provider(server_identifier=PROVIDER_ID, tenant_id=tenant_id)
            else:
                provider = matches[0]
                if args.expected_provider_record_id != str(provider.id):
                    raise RuntimeError("existing provider requires its exact expected record ID")
                expected_url_hash = hashlib.sha256(args.server_url.encode()).hexdigest()
                if provider.server_url_hash != expected_url_hash:
                    raise RuntimeError("existing provider URL differs; refuse implicit endpoint change")
                service.update_provider(
                    tenant_id=tenant_id, provider_id=str(provider.id), name=PROVIDER_NAME,
                    server_url=args.server_url, icon="🔐", icon_type="emoji", icon_background="#E4FBCC",
                    server_identifier=PROVIDER_ID, headers=headers,
                    configuration=MCPConfiguration(timeout=300, sse_read_timeout=300),
                )
            reconnect = MCPToolManageService.reconnect_with_url(
                server_url=args.server_url, headers=headers, timeout=300, sse_read_timeout=300,
            )
            actual_tools = sorted(item["name"] for item in json.loads(reconnect.tools))
            if actual_tools != expected_tools or not reconnect.authed:
                raise RuntimeError("authenticated provider tool enumeration differs")
            provider = service.get_provider(server_identifier=PROVIDER_ID, tenant_id=tenant_id)
            provider.authed = reconnect.authed
            provider.tools = reconnect.tools
            provider.encrypted_credentials = reconnect.encrypted_credentials
            provider.updated_at = datetime.now(UTC).replace(tzinfo=None)
            session.commit()
            evidence = {
                "document_type": "T01_PHASE1_REAL_SERVICE_PROVIDER_EVIDENCE",
                "version": "0.1.0", "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "provider_id": PROVIDER_ID, "provider_record_id": str(provider.id),
                "created": created, "authed": True, "authentication": "ENCRYPTED_BEARER_HEADER",
                "credential_value_recorded": False, "server_url_recorded": False,
                "server_url_sha256": hashlib.sha256(args.server_url.encode()).hexdigest(),
                "tool_count": len(actual_tools), "tool_ids": actual_tools,
                "dify_version": "1.17.0", "result": "PASS",
            }
            args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"status": "PASS", "provider_record_id": str(provider.id), "created": created, "tool_count": len(actual_tools)}))
            return 0
    finally:
        context.pop()


if __name__ == "__main__":
    raise SystemExit(main())
