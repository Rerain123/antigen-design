"""User-authorized same-run N14 continuation through the authenticated service."""
import argparse
import json
import subprocess
import prepare_m1_p1_deploy as common
from version_bundle import encode,build,sha
from inspect_pcv2_n14_capacity import OUT,SOURCE

REMOTE=r'''
import json,sys,urllib.request,urllib.error
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal,ServiceStore
from t01_phase1_real.common import decode,encode,sha
p=json.load(sys.stdin)
owner=Principal('himat-t01-test',frozenset(['query','submit']),'not-a-credential')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
ServiceStore(rt.root).authorize_job(owner,p['source'])
if p['action']=='start':
 credential=next(r for r in json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials'] if r['principal']==owner.principal_id)
 req=urllib.request.Request('http://127.0.0.1:18083/v1/workflows/'+p['source']+'/candidate-analysis',
  headers={'Content-Type':'application/json','Authorization':'Bearer '+credential['token']},
  data=json.dumps(dict(idempotency_key='pcv2-n14-20260928-'+p['source'][-32:])).encode())
 try:
  with urllib.request.urlopen(req,timeout=850) as response:reply=json.load(response)
 except urllib.error.HTTPError as exc:raise RuntimeError(exc.read().decode()) from None
 assert reply['action']=='CANDIDATE_ANALYSIS_SUBMITTED'
 job=rt.get(reply['job_id']);ex=rt.execution(job['job_id'])
 print(json.dumps(dict(job_id=job['job_id'],run_id=job['run_id'],source_job_id=p['source'],continuation=ex['continuation'])))
else:
 job=rt.get(p['job_id']);ex=rt.execution(job['job_id']);row=ex['nodes'].get('stability',{})
 report=dict(parent={k:job.get(k) for k in ('job_id','run_id','state','error_code','started_at','finished_at')},
  pending_confirmation=ex.get('pending_confirmation'),fatal_error=ex.get('fatal_error'),fatal_detail=ex.get('fatal_detail'),
  stability=row,n10_completed=sum(n.startswith('c_s') and n.endswith('_developability') and r['state']=='succeeded' for n,r in ex['nodes'].items()),
  downstream={n:r for n,r in ex['nodes'].items() if n in ('variant_report','codon','wt_reference','local_delivery')})
 if row.get('job_id'):
  child=rt.get(row['job_id']);ce=rt.execution(child['job_id']);request=decode(rt._request_bytes(child))
  report['foldx']=dict(job={k:child.get(k) for k in ('job_id','state','error_code','started_at','finished_at')},
   request_bytes=child['request_artifact']['size_bytes'],variants=len(request['variants']),
   phase=ce.get('phase'),tree_stopped=ce.get('tree_stopped'),resident_target=ce.get('resident_target'),
   diagnostic=ce.get('resident_diagnostic'))
  if ce.get('resident_target'):
   native=Path(ce['resident_target'])/'output/native'
   report['foldx']['native_files']=[dict(path=f.relative_to(native).as_posix(),size=f.stat().st_size) for f in sorted(native.rglob('*')) if f.is_file()]
  if child['state'] in ('succeeded','failed','timed_out','cancelled'):
   value=rt.result(child['job_id']);report['foldx']['result']={k:value.get(k) for k in ('status','null_reason','variant_ddg','native_completeness','warnings','execution')}
 print(json.dumps(report))
'''

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','status'])
    parser.add_argument('--projection',action='store_true');parser.add_argument('--parallel',action='store_true');args=parser.parse_args();action=args.action
    if args.projection:
        OUT=common.ROOT/'reports/n14-projection-20260928'
        SOURCE='t01p1r-job-ae3efda979474d0ea4054053ae341afa'
    if args.parallel:
        OUT=common.ROOT/'reports/n14-performance-20260928'
        SOURCE='t01p1r-job-2c5c0ec9925e47409c3a4a3817446f71'
    receipt=OUT/'continuation-submission.json';payload=dict(action=action,source=SOURCE)
    if action=='start':
        if receipt.exists():print(receipt.read_text(encoding='utf8'));raise SystemExit
        assert json.loads((OUT/'deployment-verification.json').read_bytes())['status']=='PASS'
        replay=json.loads((OUT/'checkpoint-replay.json').read_bytes())
        assert replay['status']=='PASS' and replay['source_sha256']==sha(encode(build(common.ROOT/'src')[1]))
        assert not common.idle()['active_jobs']
    else:payload['job_id']=json.loads(receipt.read_bytes())['job_id']
    done=subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',REMOTE],
        input=json.dumps(payload).encode(),capture_output=True,timeout=900)
    if done.returncode:raise RuntimeError(done.stderr.decode(errors='replace')[-2500:])
    value=json.loads(done.stdout)
    (receipt if action=='start' else OUT/'continuation-status.json').write_bytes(encode(value))
    if action=='start':print(json.dumps({k:v for k,v in value.items() if k!='continuation'}))
    else:print(json.dumps(value,ensure_ascii=False))
