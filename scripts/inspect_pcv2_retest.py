"""Read and hash-verify completed scientific artifacts for the current user retest."""
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode

OUT=common.ROOT/'reports/pcv2-full-20260928/r02'
REMOTE=r'''
import json,sys,hashlib
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
p=json.load(sys.stdin);owner=Principal('himat-t01-test',frozenset(['query','download']),'not-a-credential')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
parent=rt.get(p['job_id']);ex=rt.execution(p['job_id']);rows={}
for name,node in ex.get('nodes',{}).items():
 jid=node.get('job_id')
 if not jid:continue
 job=rt.get(jid);execution=rt.execution(jid);checks=[]
 for ref in job.get('artifacts',[]):
  raw=rt.artifact_bytes(jid,ref['artifact_id']);assert hashlib.sha256(raw).hexdigest()==ref['sha256']
  checks.append(dict(role=ref['role'],sha256=ref['sha256'],bytes=len(raw)))
 result=rt.result(jid) if job['state']=='succeeded' else None
 # The full raw predictions remain in the immutable artifact store.
 summary={k:v for k,v in (result or {}).items() if k in ('warnings','null_reason','status','execution','topology','summary','scores','scientific_status')}
 rows[name]=dict(job_id=jid,state=job['state'],created_at=job['created_at'],started_at=job.get('started_at'),
   finished_at=job.get('finished_at'),error_code=job.get('error_code'),result_keys=list((result or {}).keys()),
   artifacts_verified=checks,resident_receipt=execution.get('resident_receipt'),summary=summary)
print(json.dumps(dict(parent={k:parent.get(k) for k in ('job_id','run_id','state','created_at','started_at','finished_at','error_code')},
 nodes=rows,pending_confirmation=ex.get('pending_confirmation'))))
'''

if __name__=='__main__':
    receipt=json.loads((OUT/'submission.json').read_bytes())
    value=common.remote(REMOTE,dict(job_id=receipt['job_id']))
    (OUT/'backend-inspection.json').write_bytes(encode(value))
    print(json.dumps({name:dict(state=row['state'],artifacts=len(row['artifacts_verified']),warnings=row['summary'].get('warnings')) for name,row in value['nodes'].items()},ensure_ascii=False))
