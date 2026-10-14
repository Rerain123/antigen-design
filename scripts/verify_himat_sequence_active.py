"""Audit active HiMat tool permissions without creating a workflow."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import prepare_m1_p1_deploy as common


OUT = common.ROOT / "discovery/t01-phase1-real/m1-p4-20260922/himat-sequence-activation-r04.json"


def main() -> None:
    state = common.idle()
    if state["active_jobs"] or state["gpu_state"]["phase"] != "idle":
        raise RuntimeError("Unexpected active backend work")
    observed = common.remote("""import json,urllib.request
from pathlib import Path
doc=json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())
row=next(item for item in doc['credentials'] if item['principal']=='himat-t01-test')
token=row['token']
def rpc(method,params,number):
    body=json.dumps({'jsonrpc':'2.0','id':number,'method':method,'params':params}).encode()
    request=urllib.request.Request('http://127.0.0.1:18083/mcp',data=body,
        headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    with urllib.request.urlopen(request,timeout=15) as response:return json.load(response)
init=rpc('initialize',{'protocolVersion':'2025-06-18','capabilities':{},
    'clientInfo':{'name':'himat-sequence-audit','version':'1'}},1)
listed=rpc('tools/list',{},2)
invalid=rpc('tools/call',{'name':'t01_phase1_real_service_v01.tool.workflow.submit_sequence',
    'arguments':{'protein_sequence':'ACDEFGHI','host_species':'Homo sapiens'}},3)
legacy=rpc('tools/call',{'name':'t01_phase1_real_service_v01.tool.workflow.report',
    'arguments':{'job_id':'t01p1r-job-'+'0'*32}},4)
print(json.dumps({'scopes':row['scopes'],
    'protocol_version':init['result']['protocolVersion'],
    'tools':[item['name'] for item in listed['result']['tools']],
    'invalid_sequence_code':invalid['result']['structuredContent']['error']['code'],
    'legacy_report_invisible':'error' in legacy}))
""")
    if set(observed["scopes"]) != {"submit", "query", "download"} or \
       {item.rsplit(".", 1)[-1] for item in observed["tools"]} != {"submit_sequence", "check"} or \
       observed["invalid_sequence_code"] != "INVALID_REQUEST" or not observed["legacy_report_invisible"]:
        raise RuntimeError("HiMat active contract differs")
    after = common.idle()
    if after["active_jobs"] or after["gpu_state"]["phase"] != "idle":
        raise RuntimeError("Audit created unexpected work")
    OUT.write_text(json.dumps({
        "status": "HIMAT_SEQUENCE_ACTIVE_NO_JOB_PASS",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "deployment": "him-ws/antigen-design", "principal": "himat-t01-test",
        "scopes": observed["scopes"], "protocol_version": observed["protocol_version"],
        "tools": observed["tools"], "invalid_sequence_code": observed["invalid_sequence_code"],
        "legacy_report_invisible": True, "active_jobs_before": [], "active_jobs_after": [],
        "gpu_phase_after": "idle", "new_workflow_submitted": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("HIMAT_SEQUENCE_ACTIVE_NO_JOB_PASS", OUT)


if __name__ == "__main__":
    main()
