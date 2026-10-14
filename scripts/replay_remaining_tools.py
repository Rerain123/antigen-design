"""Read-only archived N17 native-input replay, no task submission."""
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode

OUT=common.ROOT/'reports/remaining-tools-20260928'
REMOTE=r'''
import json,sqlite3,sys
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.wt_reference.source import sources
from t01_phase1_real.development.wt_reference.compute import evaluate
from t01_phase1_real.common import decode,RuntimeFault,sha
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
count=db.execute('select count(*) from jobs').fetchone()[0]
jobs=[]
for scope,raw in db.execute('select scope,data from jobs'):
    job=json.loads(raw)
    if job['tool_id']=='t01.real.wt_reference' and job['state']=='succeeded':jobs.append((scope,job))
out=[]
for scope,job in jobs:
    rt=Runtime('/var/lib/t01/runtime',scope=scope)
    try:
        body=decode(rt._request_bytes(job))
        if not any(body['upstream'][n] for n in ('foldx','thermompnn')):continue
        with rt._db() as source_db:files,values,receipts=sources(rt,source_db,body)
        result=evaluate(body,files)
        out.append(dict(job_id=job['job_id'],run_id=job['run_id'],status='PASS',reference=result,
            engine_counts={n:len(r['records']) for n,r in result['engines'].items()}))
    except (RuntimeFault,KeyError,ValueError) as e:
        out.append(dict(job_id=job['job_id'],status='BLOCKED',code=getattr(e,'code',type(e).__name__),reason=str(e)))
assert db.execute('select count(*) from jobs').fetchone()[0]==count
print(json.dumps(dict(mode='READ_ONLY_ARCHIVED_NATIVE_REPLAY',records=out,source_jobs=len(jobs),
    new_jobs=0,model_invocations=0,job_count=count)))
'''

if __name__=='__main__':
    value=common.remote(REMOTE)
    (OUT/'n17-native-replay.json').write_bytes(encode(value))
    print(json.dumps(dict(source_jobs=value['source_jobs'],new_jobs=value['new_jobs'],
        records=[{k:v for k,v in r.items() if k!='reference'} for r in value['records']])))
