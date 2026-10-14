"""Read-only audit of the deployed HiMat MCP authentication and tool catalog."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import prepare_himat_mcp_route as deployment
import prepare_m1_p1_deploy as common


OUT = common.ROOT / "discovery/t01-phase1-real/m1-p4-20260922/himat-mcp-route-deployment-r05.json"


def main() -> None:
    before = common.idle()
    if before["active_jobs"]:
        raise RuntimeError("Unexpected active work before MCP audit")
    observed = common.remote("""import hashlib,json,urllib.request
from pathlib import Path
source=Path('/app/src/t01_phase1_real/service_api/transport.py')
rows=json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials']
row=next(item for item in rows if item['principal']=='himat-t01-test')
def rpc(method,params,number):
    body=json.dumps({'jsonrpc':'2.0','id':number,'method':method,'params':params}).encode()
    req=urllib.request.Request('http://127.0.0.1:18083/mcp',data=body,headers={
        'Content-Type':'application/json',
        'Authorization':'Bearer '+('x'*48),
        'X-T01-MCP-Authorization':'Bearer '+row['token']})
    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)
init=rpc('initialize',{'protocolVersion':'2024-11-05','capabilities':{},
    'clientInfo':{'name':'himat-mcp-audit','version':'1'}},1)
listed=rpc('tools/list',{},2)
invalid=rpc('tools/call',{'name':'workflow_submit_sequence',
    'arguments':{'protein_sequence':'ACDEFGHI','host_species':'Homo sapiens'}},3)
old=rpc('tools/call',{'name':'t01_phase1_real_service_v01.tool.workflow.submit_sequence',
    'arguments':{}},4)
print(json.dumps({'transport_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'scopes':row['scopes'],'protocol_version':init['result']['protocolVersion'],
    'tools':[item['name'] for item in listed['result']['tools']],
    'invalid_sequence_code':invalid['result']['structuredContent']['error']['code'],
    'old_name_invisible':'error' in old}))
""")
    after = common.idle()
    if observed["transport_sha256"] != deployment.source_hash():
        raise RuntimeError("Deployed MCP transport hash differs")
    if set(observed["scopes"]) != {"submit", "query", "download"}:
        raise RuntimeError("HiMat scopes differ")
    if set(observed["tools"]) != {"workflow_submit_sequence", "workflow_check"}:
        raise RuntimeError("HiMat MCP names differ")
    if observed["invalid_sequence_code"] != "INVALID_REQUEST" or not observed["old_name_invisible"]:
        raise RuntimeError("HiMat MCP dispatch boundary differs")
    if after["active_jobs"] or before["gpu_state"]["phase"] != "idle" or after["gpu_state"]["phase"] != "idle":
        raise RuntimeError("MCP audit changed backend work state")
    OUT.write_text(json.dumps({
        "status": "HIMAT_MCP_ROUTE_DEPLOYED_PASS",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "deployment": "him-ws/antigen-design", "transport_sha256": observed["transport_sha256"],
        "protocol_version": observed["protocol_version"], "himat_scopes": observed["scopes"],
        "himat_tools": observed["tools"], "invalid_sequence_code": observed["invalid_sequence_code"],
        "old_name_invisible": True, "custom_header_authenticated": True,
        "active_jobs_before": [], "active_jobs_after": [], "gpu_phase_after": "idle",
        "new_workflow_submitted": False, "scientific_gate": "CLOSED",
        "usable_for_pipeline": False, "production_status": "NOT_DEPLOYED",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("HIMAT_MCP_ROUTE_DEPLOYED_PASS", OUT)


if __name__ == "__main__":
    main()
