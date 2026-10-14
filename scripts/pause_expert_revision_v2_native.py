"""Save and stop the active v2 test at the user's explicit pause request."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode

REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
import time
from t01_phase1_real.common import TERMINAL,encode
jid=p['job_id'];before=rt.get(jid);saved=rt.execution(jid)
assert before['run_id']==p['run_id']
completed={n:rt.get(r['job_id']) for n,r in saved['nodes'].items()
 if r.get('job_id') and rt.get(r['job_id'])['state']=='succeeded'}
reply=rpc('workflow.cancel',dict(job_id=jid,idempotency_key=p['key']))
end=time.monotonic()+70
while time.monotonic()<end:
 job=rt.get(jid);ex=rt.execution(jid)
 children=[rt.get(r['job_id']) for r in ex['nodes'].values() if r.get('job_id')]
 if job['state'] in TERMINAL and ex.get('tree_stopped') is True and all(c['state'] in TERMINAL for c in children):break
 time.sleep(.5)
job=rt.get(jid);ex=rt.execution(jid)
children={n:rt.get(r['job_id']) for n,r in ex['nodes'].items() if r.get('job_id')}
stopped=job['state'] in TERMINAL and ex.get('tree_stopped') is True and all(c['state'] in TERMINAL for c in children.values())
assert all(rt.get(c['job_id'])==c for c in completed.values()),'Completed sources changed during pause'
print(json.dumps(dict(status='PAUSED_WITH_STOP_CONFIRMED' if stopped else 'PAUSE_STOP_REQUESTED',
 user_instruction=p['instruction'],job_id=jid,run_id=job['run_id'],paused_at=job.get('finished_at') or job.get('updated_at'),
 stop_implementation='Cancellation is the available backend stop operation; immutable checkpoint retained for a future explicit continuation.',
 before_job=before,saved_execution=saved,job=job,execution=ex,children=children,
 tree_stopped=stopped,source_request_sha256=sha(rt._request_bytes(job)),execution_sha256=sha(encode(ex)),
 completed_sources_unchanged=True,completed_children={n:c['job_id'] for n,c in completed.items()},response=reply,
 next_resume_boundary='After completed formal0 and cheap0; inspect cancelled WT MSA before new admission. Current pre-score continuation endpoint does not cover this later checkpoint.',
 automatic_resume=False,scientific_gate='CLOSED',production_status='NOT_DEPLOYED')))
'''

if __name__=='__main__':
    receipt=run.OUT/'pause-confirmation.json'
    submitted=run.active_submission()
    value=run.common.remote(REMOTE,dict(job_id=submitted['job_id'],run_id=submitted['run_id'],owner=submitted['owner'],
        key=run.KEY+'-user-pause-20260930',instruction='先保存当前状态并暂停。我后面会让你继续完成'))
    if receipt.exists():
        previous=json.loads(receipt.read_bytes())
        if previous['status']=='PAUSED_WITH_STOP_CONFIRMED':
            assert previous['job_id']==value['job_id'];value=previous
        else:receipt.write_bytes(encode(value)+b'\n')
    else:
        with receipt.open('xb') as stream:stream.write(encode(value)+b'\n')
    print(json.dumps(dict(status=value['status'],job_id=value['job_id'],run_id=value['run_id'],
        state=value['job']['state'],tree_stopped=value['tree_stopped'],completed_sources_unchanged=value['completed_sources_unchanged'],
        children={n:c['state'] for n,c in value['children'].items()},automatic_resume=False),ensure_ascii=False))
