"""Prospective consumer replay in an isolated process; no store/model mutations."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode,build,sha

OUT=run.common.ROOT/'reports/expert-revision-v2-bepi-fix-20260930'
REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
import time
from t01_phase1_real.common import encode
from t01_phase1_real.development.workflow import revision_v2_runtime as vr,revision_controller as rc
jid=p['job_id'];job=rt.get(jid);body=decode(rt._request_bytes(job));ex=rt.execution(jid)
prior=sha(encode(ex));request_hash=sha(rt._request_bytes(job))
with rt._db() as db:count=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
# Only this isolated reader uses the proposed code. The installed service,
# workflow profiles, raw results and durable source checkpoint remain intact.
exec(compile(p['source'],vr.__file__,'exec'),vr.__dict__)
started=time.monotonic();data,reason=rc.inputs(rt,jid,body);assert reason is None
fact=rc.assemble(rt,jid,body,data)
assert sha(encode(rt.execution(jid)))==prior and sha(rt._request_bytes(rt.get(jid)))==request_hash
with rt._db() as db:assert count==db.execute('SELECT count(*) FROM jobs').fetchone()[0]
records=fact['formal_records']
print(json.dumps(dict(status='PASS_READ_ONLY_REAL_CHECKPOINT',job_id=jid,run_id=job['run_id'],
 prospective_source_sha256=p['source_sha256'],source_execution_sha256=prior,request_sha256=request_hash,
 replay_seconds=time.monotonic()-started,formal_records=len(records),
 disposition_counts={k:sum(r['disposition']==k for r in records) for k in sorted({r['disposition'] for r in records})},
 formal_checks=[dict(candidate_id=r['candidate_id'],content_hash=r['content_hash'],mutation_count=len(r['mutations']),
  constraint=r['constraint_check']['check_status'],s28=r['validation']['check_status'],
  protection=r.get('protection',{}).get('check_status'),l4=r.get('l4',{}).get('check_status'),
  disposition=r['disposition']) for r in records],
 current_state=job['state'],native_model_calls=0,new_jobs=0,durable_sources_changed=False,
 scientific_gate='CLOSED',production_status='NOT_DEPLOYED')))
'''

if __name__=='__main__':
    submitted=json.loads((run.OUT/'submission.json').read_bytes())
    value=run.common.remote(REMOTE,dict(job_id=submitted['job_id'],owner=submitted['owner'],
        source=(run.common.ROOT/'src/t01_phase1_real/development/workflow/revision_v2_runtime.py').read_text(encoding='utf8'),
        source_sha256=sha(encode(build(run.common.ROOT/'src')[1]))))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'checkpoint-replay.json').write_bytes(encode(value)+b'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='formal_checks'},ensure_ascii=False))
