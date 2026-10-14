"""Stop only this dormant pre-score parent before a verified source rollout."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode

OUT=run.common.ROOT/'reports/expert-revision-v2-bepi-fix-20260930'
REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
import time
from t01_phase1_real.common import TERMINAL,encode
jid=p['job_id'];job=rt.get(jid);ex=rt.execution(jid)
assert job['run_id']==p['run_id'] and not ex.get('dispatcher') and not ex.get('pending_confirmation')
assert not any(n.startswith(('cheap','rx','z','formal1','formal2')) for n in ex['nodes'])
assert all(ex['nodes'][n]['state']=='succeeded' for n in ('proposal0','proposal1','formal0'))
children={n:rt.get(r['job_id']) for n,r in ex['nodes'].items() if r.get('job_id')}
assert all(c['state'] in TERMINAL and rt.execution(c['job_id']).get('tree_stopped') is True for c in children.values())
reply=rpc('workflow.cancel',dict(job_id=jid,idempotency_key=p['key']))
job=rt.get(jid)
if job['state'] not in TERMINAL:
 job=rt.recover(jid)
for _ in range(120):
 if job['state'] in TERMINAL and rt.execution(jid).get('tree_stopped') is True:break
 time.sleep(.25);job=rt.get(jid)
assert job['state']=='cancelled' and rt.execution(jid).get('tree_stopped') is True
assert all(rt.get(c['job_id'])==c for c in children.values())
print(json.dumps(dict(status='STOPPED_FOR_VERIFIED_INTERFACE_FIX',job_id=jid,run_id=job['run_id'],state=job['state'],
 tree_stopped=True,source_execution_sha256=sha(encode(rt.execution(jid))),request_sha256=sha(rt._request_bytes(job)),
 completed_children_unchanged=True,completed_children={n:c['job_id'] for n,c in children.items()},
 generation_repeated=False,old_cancelled_pcv2_resumed=False,user_authorization=p['authorization'],response=reply)))
'''

if __name__=='__main__':
    receipt=OUT/'checkpoint-stop.json'
    if receipt.exists():
        print(receipt.read_text(encoding='utf8'))
    else:
        replay=json.loads((OUT/'checkpoint-replay.json').read_bytes())
        assert replay['status']=='PASS_READ_ONLY_REAL_CHECKPOINT'
        submitted=json.loads((run.OUT/'submission.json').read_bytes())
        value=run.common.remote(REMOTE,dict(job_id=submitted['job_id'],run_id=submitted['run_id'],owner=submitted['owner'],
            key=run.KEY+'-interface-fix-stop',authorization='User authorized deployment and real v2 test; explicit T4 continue. Stop dormant controller for source-fix rollout, then verified same-run continuation.'))
        with receipt.open('xb') as stream:stream.write(encode(value)+b'\n')
        print(json.dumps(value,ensure_ascii=False))
