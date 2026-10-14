"""Read-only deployed hash and HiMat sequence-contract audit."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

import prepare_m1_p1_deploy as common
import prepare_himat_sequence_deploy as deployment


OUT = common.ROOT / "discovery/t01-phase1-real/m1-p4-20260922/himat-sequence-deployment-r04.json"


def main():
    service = common.remote("""import hashlib,json,urllib.request
from pathlib import Path
root=Path('/app/src/t01_phase1_real')
names=['service_api/transport.py','service_api/himat.py','development/workflow/policy.py',
       'development/esmfold2/policy.py','development/esmfold2/profile.json']
hashes={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}
doc=json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())
row=next(item for item in doc['credentials'] if item['principal']=='himat-t01-test')
def rpc(method,params,number):
    body=json.dumps({'jsonrpc':'2.0','id':number,'method':method,'params':params}).encode()
    req=urllib.request.Request('http://127.0.0.1:18083/mcp',data=body,headers={
        'Content-Type':'application/json','Authorization':'Bearer '+row['token']})
    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)
listed=rpc('tools/list',{},1)
denied=rpc('tools/call',{'name':'t01_phase1_real_service_v01.tool.workflow.submit_sequence',
    'arguments':{'protein_sequence':'ACDEFGHIK','host_species':'Homo sapiens'}},2)
old=rpc('tools/call',{'name':'t01_phase1_real_service_v01.tool.workflow.submit_test',
    'arguments':{}},3)
print(json.dumps({'hashes':hashes,'scopes':row['scopes'],
    'tools':[item['name'] for item in listed['result']['tools']],
    'submit_forbidden':denied['result']['structuredContent']['error']['code']=='FORBIDDEN',
    'fixed_sample_absent':'error' in old,
    'profile_max_aa':json.loads((root/'development/esmfold2/profile.json').read_bytes())['max_sequence_length']}))
""")
    worker_code = """import hashlib,json
from pathlib import Path
root=Path('/opt/t01/src/t01_phase1_real/development/esmfold2')
print(json.dumps({'policy_sha256':hashlib.sha256((root/'policy.py').read_bytes()).hexdigest(),
    'profile_sha256':hashlib.sha256((root/'profile.json').read_bytes()).hexdigest(),
    'profile_max_aa':json.loads((root/'profile.json').read_bytes())['max_sequence_length']}))
"""
    worker = json.loads(subprocess.check_output(common.K + ["exec", "deployment/antigen-design",
        "-c", "worker-unified-gpu", "--", "/opt/t01/supervisor/bin/python3.11", "-B", "-c", worker_code]))
    expected = deployment.hashes()
    if service["hashes"] != expected:
        raise RuntimeError("Service source hashes differ")
    if worker["policy_sha256"] != expected["development/esmfold2/policy.py"] or \
       worker["profile_sha256"] != expected["development/esmfold2/profile.json"]:
        raise RuntimeError("GPU Worker source hashes differ")
    if service["profile_max_aa"] != worker["profile_max_aa"] or service["profile_max_aa"] != 999:
        raise RuntimeError("ESMFold2 length admission differs")
    if set(service["scopes"]) != {"query", "download"} or not service["submit_forbidden"]:
        raise RuntimeError("Submission suspension was lost")
    if {name.rsplit(".", 1)[-1] for name in service["tools"]} != {"submit_sequence", "check"} or not service["fixed_sample_absent"]:
        raise RuntimeError("HiMat tool catalog differs")
    OUT.write_text(json.dumps({
        "status": "HIMAT_SEQUENCE_DEPLOYED_HASH_PASS",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "deployment": "him-ws/antigen-design", "source_hashes": expected,
        "gpu_worker_hashes": worker, "himat_scopes": service["scopes"],
        "himat_tools": service["tools"], "submission_suspended": True,
        "fixed_sample_tool_absent": True, "new_workflow_submitted": False,
        "scientific_gate": "CLOSED", "usable_for_pipeline": False,
        "production_status": "NOT_DEPLOYED",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("HIMAT_SEQUENCE_DEPLOYED_HASH_PASS", OUT)


if __name__ == "__main__":
    main()
