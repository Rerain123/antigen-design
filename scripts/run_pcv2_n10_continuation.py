"""Explicit 2026-09-28 authorization: reuse N11/N12, restart candidate N10."""
import argparse
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode

OUT=common.ROOT/'reports/workflow-performance-20260928'
SOURCE='t01p1r-job-32323aee6d9e46baabc08b0fa257ed16'
REMOTE=r'''
import json,sys,time,urllib.request
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal,ServiceStore
from t01_phase1_real.common import decode
p=json.load(sys.stdin)
owner=Principal('himat-t01-test',frozenset(['query','submit']),'not-a-credential')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
store=ServiceStore(rt.root);store.authorize_job(owner,p['source'])
body=decode(rt._request_bytes(rt.get(p['source'])))
for k,v in body['configuration'].items():setattr(rt,k,Path(v) if v else None)
if p['action']=='start':
 credential=next(r for r in json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials'] if r['principal']==owner.principal_id)
 payload=dict(idempotency_key='pcv2-n10-performance-recover-20260928')
 req=urllib.request.Request('http://127.0.0.1:18083/v1/workflows/'+p['source']+'/candidate-analysis',headers={'Content-Type':'application/json','Authorization':'Bearer '+credential['token']},data=json.dumps(payload).encode())
 with urllib.request.urlopen(req,timeout=100) as response:reply=json.load(response)
 assert reply['action']=='CANDIDATE_ANALYSIS_SUBMITTED', 'Submission rejected'
 job=rt.get(reply['job_id'])
 print(json.dumps(dict(job_id=job['job_id'],run_id=job['run_id'],source_job_id=p['source'],
  boundary='c_s1_structure',same_candidates=True,new_generation=False,continuation=rt.execution(job['job_id'])['continuation'])))
else:
 job=rt.get(p['job_id']);ex=rt.execution(job['job_id']);rows=[]
 for n,r in ex.get('nodes',{}).items():
  if not n.startswith('c_s') or not r.get('job_id'):continue
  c=rt.get(r['job_id']);rows.append(dict(node=n,**{k:c.get(k) for k in ('job_id','state','started_at','finished_at','error_code')}))
 print(json.dumps(dict(parent={k:job.get(k) for k in ('job_id','run_id','state','error_code','started_at','finished_at')},
  n10=rows,pending_confirmation=ex.get('pending_confirmation'),phase=ex.get('phase'))))
'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','status'])
    action=parser.parse_args().action
    receipt=OUT/'continuation-submission.json'
    if action=='start':
        if receipt.exists():print(receipt.read_text(encoding='utf8'));return
        verified=json.loads((OUT/'deployment-verification.json').read_bytes())
        assert verified['status']=='PASS'
        assert not common.idle()['active_jobs']
        value=common.remote(REMOTE,dict(action=action,source=SOURCE))
        receipt.write_bytes(encode(value))
    else:
        submission=json.loads(receipt.read_bytes())
        value=common.remote(REMOTE,dict(action=action,source=SOURCE,job_id=submission['job_id']))
        (OUT/'continuation-status.json').write_bytes(encode(value))
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':main()
