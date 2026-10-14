"""Read-only replay of the failed N14 request; no scientific job submission."""
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode

OUT=common.ROOT/'reports/n14-capacity-20260928'
SOURCE='t01p1r-job-f24ecd15def7472b94926403f7a3ed68'
REMOTE=r'''
import json,sys,copy
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.common import decode,encode,sha
from t01_phase1_real.development.workflow import service,m1
p=json.load(sys.stdin)
rt=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset(['query']),'x').runtime_scope)
job=rt.get(p['source']);ex=rt.execution(job['job_id']);body=decode(rt._request_bytes(job))
for k,v in body['configuration'].items():setattr(rt,k,Path(v) if v else None)
req,why=service.request_for(rt,body,ex['nodes'],'stability')
fresh=m1.preselection(rt,body,ex['nodes']);old=ex['nodes']['preselection']['fact']
print(json.dumps(dict(parent={k:job[k] for k in ('job_id','state','error_code','run_id')},
 tree_stopped=ex.get('tree_stopped'),stability=ex['nodes']['stability'],request_bytes=len(encode(req)),
 request_sha256=sha(encode(req)),reason=why,variants=len(req['variants']),
 mutations=[len(v['mutations']) for v in req['variants']],
 preselection_changed_fields=[k for k in set(old)|set(fresh) if old.get(k)!=fresh.get(k)],
 old_validation_source=old.get('validation_source'),current_validation_source=fresh.get('validation_source'))))
'''
if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    value=common.remote(REMOTE,dict(source=SOURCE))
    (OUT/'diagnosis.json').write_bytes(encode(value))
    print(json.dumps(value,ensure_ascii=False))
