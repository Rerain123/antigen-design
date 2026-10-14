"""Read one current-run snapshot and deployed HiMat contract without submission."""
import datetime
import json
import re
import sys
from pathlib import Path
import prepare_m1_p1_deploy as common
from version_bundle import encode

OUT=common.ROOT/'reports/controller-recovery-20261008'
REMOTE=r'''
import collections,datetime,json,sys,time,urllib.request
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.common import encode,sha,TERMINAL
credential=next(r for r in json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials'] if r['principal']=='himat-t01-test')
owner=Principal(credential['principal'],frozenset(credential['scopes']),'x')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
jid='t01p1r-job-a7c8933226744c669836b11858585246'
job=rt.get(jid);ex=rt.execution(jid);body=json.loads(rt._request_bytes(job));counts=collections.Counter();nodes=[]
for n,r in ex.get('nodes',{}).items():
 if r.get('job_id'):
  child=rt.get(r['job_id']);counts[(child['tool_id'],child['state'])]+=1
  if child['state'] not in TERMINAL:nodes.append(dict(node=n,job_id=child['job_id'],state=child['state'],started_at=child.get('started_at')))
started=time.monotonic()
req=urllib.request.Request('http://127.0.0.1:18083/v1/workflows/'+jid,headers={'Authorization':'Bearer '+credential['token']})
with urllib.request.urlopen(req,timeout=60) as response:status=json.load(response)
captures=[]
class Capture:
 def submit(self,principal,request):captures.append(request);return dict(job_id='captured',state='queued')
hi=HiMatIntegration(Capture(),'https://example.invalid',b'capture-only-test-key-32-bytes-long')
hi.submit_sequence(owner,body['protein_sequence'],body['host_species'])
from t01_phase1_real.development.workflow.policy import request as validate
validate(encode(captures[0]['request']))
assert captures[0]['request']['interaction_policy']=='PREAUTHORIZED_T4_CONTINUE_WITH_WARNING_V1'
print(json.dumps(dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 job={k:job.get(k) for k in ('job_id','run_id','state','error_code','updated_at','started_at','finished_at')},
 request_sha256=sha(rt._request_bytes(job)),controller_upgrade=ex.get('controller_upgrade'),
 controller_fault=ex.get('controller_fault'),pending_confirmation=ex.get('pending_confirmation'),
 active_nodes=nodes,counts=[dict(tool=k[0],state=k[1],count=v) for k,v in sorted(counts.items())],
 http_status=status['state'],http_controller=status.get('controller'),http_seconds=round(time.monotonic()-started,3),
 configured_interaction_policy=captures[0]['request']['interaction_policy'],new_submission=False,
 revision_state_present=bool(ex.get('revision_state')),fatal_error=ex.get('fatal_error'),fatal_detail=ex.get('fatal_detail'),
 continuation=ex.get('continuation'))))
'''

if __name__=='__main__':
    remote=REMOTE
    continuation=common.ROOT/'reports/controller-time-compensation-20261008/continuation-submission.json'
    if continuation.exists() and '--original' not in sys.argv:
        receipt=json.loads(continuation.read_bytes())
        assert re.fullmatch(r't01p1r-job-[0-9a-f]{32}',receipt['job_id'])
        assert receipt['source_job_id']=='t01p1r-job-a7c8933226744c669836b11858585246'
        remote=remote.replace("jid='t01p1r-job-a7c8933226744c669836b11858585246'",'jid='+repr(receipt['job_id']))
        OUT=continuation.parent
    value=common.remote(remote)
    name=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
    (OUT/(name+'.json')).write_bytes(encode(value))
    (OUT/'latest.json').write_bytes(encode(value))
    print(json.dumps(value,ensure_ascii=False))
