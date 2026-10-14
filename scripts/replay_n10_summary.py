"""Replay registered historical N10 native files; never invoke tools or alter jobs."""
import json
from pathlib import Path
import prepare_m1_p1_deploy as common

REMOTE='''import json,sqlite3
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import decode,sha,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow.candidate_developability import verified_value
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
count=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
jobs=[(scope,json.loads(raw)) for scope,raw in db.execute('SELECT scope,data FROM jobs')]
jobs=[(s,j) for s,j in jobs if j['tool_id']=='t01.real.developability' and j['state']=='succeeded']
jobs.sort(key=lambda pair:pair[1]['finished_at'],reverse=True)
results=[]
for scope,j in jobs[:6]:
    rt=Runtime('/var/lib/t01/runtime',scope=scope)
    before=rt.get(j['job_id']);request=decode(rt._request_bytes(j))
    ref=next(a for a in j['artifacts'] if a['role']=='result')
    raw=rt.artifact_bytes(j['job_id'],ref['artifact_id']);source_sha256=sha(raw)
    result=dict(job_id=j['job_id'],run_id=j['run_id'],source_sha256=source_sha256)
    try:
        with rt._db() as con:value=verified_value(rt,con,dict(job_id=j['job_id'],artifact=ref),request['protein_sequence'],j['run_id'])
        d=value['developability']
        assert d['weight_policy']=='S40_EQUAL_INITIAL_PENDING_BACKTEST' if request.get('dimension_weights') is None else d['weight_policy']=='EXPLICIT'
        if not d['dimensions']['solubility']['reliable']:assert d['overall_score'] is None
        result.update(status='PASS',sequence_length=len(request['protein_sequence']),summary=d)
    except RuntimeFault as exc:
        result.update(status='BLOCKED_HISTORICAL_SOURCE',reason_code=exc.code,detail=str(exc))
    assert rt.get(j['job_id'])==before and sha(rt.artifact_bytes(j['job_id'],ref['artifact_id']))==source_sha256
    results.append(result)
assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==count
assert any(r['status']=='PASS' for r in results),'No matching native N10 evidence'
print(json.dumps(dict(status='PASS',records=results,new_jobs=0,models_executed=False,source_bytes_unchanged=True)))
'''

if __name__=='__main__':
    result=common.remote(REMOTE)
    out=common.ROOT/'reports/n10-summary-20260927/native-replay.json'
    with out.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status=result['status'],passed=sum(r['status']=='PASS' for r in result['records']),
        historical_blocked=sum(r['status']!='PASS' for r in result['records']),new_jobs=0)))
