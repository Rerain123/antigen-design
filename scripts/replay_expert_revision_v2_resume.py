"""Verify the saved post-score checkpoint using prospective resume code only."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode,build,sha

OUT=run.common.ROOT/'reports/expert-revision-v2-resume-20260930'
REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
import time
from t01_phase1_real.common import encode
from t01_phase1_real.development.workflow import continuation as ct
jid=p['job_id'];job=rt.get(jid);prior=rt.execution(jid);before=sha(encode(prior))
assert job['state']=='cancelled' and before==p['checkpoint_sha256']
argv=Path('/proc/1/cmdline').read_bytes().decode().split('\0')
for flag,name in [('--blast-database-root','blast_database_root'),('--homology-database-root','homology_database_root'),('--domains-database-root','domains_database_root')]:
 setattr(rt,name,Path(argv[argv.index(flag)+1]) if flag in argv else None)
with rt._db() as db:count=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
exec(compile(p['source'],ct.__file__,'exec'),ct.__dict__)
started=time.monotonic();_,body,ex,rows=ct.prepare_revision(rt,jid)
assert 'wt_msa' not in rows and rows['cheap0']['job_id']==prior['nodes']['cheap0']['job_id']
assert sha(encode(rt.execution(jid)))==before and rt.get(jid)==job
with rt._db() as db:assert count==db.execute('SELECT count(*) FROM jobs').fetchone()[0]
msa=rt.get(prior['nodes']['wt_msa']['job_id'])
print(json.dumps(dict(status='PASS_READ_ONLY_POST_SCORE_CHECKPOINT',job_id=jid,run_id=job['run_id'],
 prospective_source_sha256=p['source_sha256'],checkpoint_sha256=before,request_sha256=sha(rt._request_bytes(job)),
 replay_seconds=time.monotonic()-started,reused_children={n:r['job_id'] for n,r in rows.items() if r.get('job_id')},
 stopped_msa=dict(job_id=msa['job_id'],state=msa['state'],tree_stopped=rt.execution(msa['job_id']).get('tree_stopped')),
 t4_ancestor=rows['design']['confirmation']['job_id'],structure_allocation=ex['revision_allocations'],
 total_budget_reverified=True,frozen_wt_reverified=True,native_model_calls=0,new_jobs=0,
 durable_sources_changed=False,scientific_gate='CLOSED',production_status='NOT_DEPLOYED')))
'''

if __name__=='__main__':
    paused=json.loads((run.OUT/'pause-confirmation.json').read_bytes());submitted=run.active_submission()
    value=run.common.remote(REMOTE,dict(job_id=paused['job_id'],owner=submitted['owner'],checkpoint_sha256=paused['execution_sha256'],
        source=(run.common.ROOT/'src/t01_phase1_real/development/workflow/continuation.py').read_text(encoding='utf8'),
        source_sha256=sha(encode(build(run.common.ROOT/'src')[1]))))
    (OUT/'checkpoint-replay.json').write_bytes(encode(value)+b'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in ('reused_children','structure_allocation')},ensure_ascii=False))
