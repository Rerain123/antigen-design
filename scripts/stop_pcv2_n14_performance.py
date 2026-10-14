"""User-authorized cancellation with original native evidence retained."""
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode

OUT=common.ROOT/'reports/n14-performance-20260928'
SOURCE='t01p1r-job-2c5c0ec9925e47409c3a4a3817446f71'
REMOTE=r'''
import json,sys,datetime
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.common import encode,decode,TERMINAL
from t01_phase1_real.development.workflow import service
p=json.load(sys.stdin)
rt=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset(['query']),'x').runtime_scope)
job=rt.get(p['source']);ex=rt.execution(job['job_id']);body=decode(rt._request_bytes(job))
for k,v in body['configuration'].items():setattr(rt,k,Path(v) if v else None)
child=rt.get(ex['nodes']['stability']['job_id']);ce=rt.execution(child['job_id'])
req=decode(rt._request_bytes(child));target=Path(ce['resident_target'])
native=target/'output/native'
files=[dict(path=f.relative_to(native).as_posix(),bytes=f.stat().st_size,mtime=f.stat().st_mtime)
       for f in sorted(native.rglob('*')) if f.is_file()]
before=dict(parent=job,child=child,child_execution=ce,request=req,files=files,
            worker_request=json.loads((target/'request.json').read_bytes()))
if job['state'] not in TERMINAL:
 rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=job['job_id'],idempotency_key='user-n14-performance-stop-20260928')))
 service.stop_children(rt,job['job_id'])
 rt.reconcile(job['job_id'])
print(json.dumps(dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),before=before,
 parent=rt.get(job['job_id']),child=rt.get(child['job_id']),execution=rt.execution(job['job_id']))))
'''

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    value=common.remote(REMOTE,dict(source=SOURCE))
    path=OUT/('stop.json' if not (OUT/'stop.json').exists() else 'stop-confirmation.json')
    path.write_bytes(encode(value))
    print(json.dumps(dict(parent={k:value['parent'][k] for k in ('job_id','state','error_code')},
        child={k:value['child'][k] for k in ('job_id','state','error_code')},
        tree_stopped=value['execution'].get('tree_stopped'),native_files=value['before']['files'])))
