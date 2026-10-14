"""Explicit user resume from the saved post-score stopped MSA checkpoint."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode,build,sha

OUT=run.common.ROOT/'reports/expert-revision-v2-resume-20260930'
REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
import urllib.error
from t01_phase1_real.common import encode
source=rt.get(p['job_id']);prior=rt.execution(p['job_id'])
assert source['state']=='cancelled' and source['run_id']==p['run_id'] and prior['tree_stopped'] is True
assert sha(encode(prior))==p['checkpoint_sha256']
def start():
 request=urllib.request.Request('http://127.0.0.1:18083/v1/workflows/'+p['job_id']+'/candidate-analysis',
  headers={'Content-Type':'application/json','Authorization':'Bearer '+credential['token']},
  data=json.dumps(dict(idempotency_key=p['key'])).encode())
 try:
  with urllib.request.urlopen(request,timeout=85) as response:return json.load(response)
 except urllib.error.HTTPError as exc:raise RuntimeError(exc.read().decode()) from None
first=start();second=start();assert first['job_id']==second['job_id']
job=rt.get(first['job_id']);ex=rt.execution(job['job_id'])
assert job['job_id']!=source['job_id'] and job['run_id']==source['run_id'] and job['request_artifact']==source['request_artifact']
assert ex['started_at']==prior['started_at'] and ex.get('confirmation_wait_seconds',0)==prior.get('confirmation_wait_seconds',0)
assert ex['revision_v2_frozen']==prior['revision_v2_frozen'] and ex['revision_allocations']==prior['revision_allocations']
assert ex['nodes']['design']['confirmation']==prior['nodes']['design']['confirmation']
assert ex['nodes']['cheap0']['job_id']==prior['nodes']['cheap0']['job_id']
for kind in ('reservations','attempts','observed_objects'):
 assert all(ex['revision_ledger'][kind][key]==value for key,value in prior['revision_ledger'][kind].items())
assert rt.get(p['job_id'])==source and sha(encode(rt.execution(p['job_id'])))==p['checkpoint_sha256']
old_msa=prior['nodes']['wt_msa']['job_id'];assert rt.get(old_msa)['state']=='cancelled'
if ex['nodes'].get('wt_msa',{}).get('job_id'):assert ex['nodes']['wt_msa']['job_id']!=old_msa
print(json.dumps(dict(status='USER_RESUMED_SAME_RUN_V2_TEST',job_id=job['job_id'],run_id=job['run_id'],
 owner=sha(owner.principal_id.encode()),source_job_id=p['job_id'],source_sha256=p['source_sha256'],
 request_sha256=sha(rt._request_bytes(job)),state=job['state'],idempotency_verified=True,new_run=False,new_parent=True,
 resumed_at=job['started_at'],user_authorization=p['authorization'],continuation=ex['continuation'],
 source_checkpoint_unchanged=True,original_deadline_preserved=True,total_budget_preserved=True,t4_preserved=True,
 generation_repeated=False,cheap_scoring_repeated=False,msa_restarted_explicitly=True,
 scientific_gate='CLOSED',production_status='NOT_DEPLOYED')))
'''

if __name__=='__main__':
    receipt=OUT/'continuation-submission.json'
    if receipt.exists():
        print(receipt.read_text(encoding='utf8'))
    else:
        deployed=json.loads((OUT/'deployment-verification.json').read_bytes())
        replay=json.loads((OUT/'checkpoint-replay.json').read_bytes())
        paused=json.loads((run.OUT/'pause-confirmation.json').read_bytes())
        previous=json.loads((run.common.ROOT/'reports/expert-revision-v2-bepi-fix-20260930/continuation-submission.json').read_bytes())
        digest=sha(encode(build(run.common.ROOT/'src')[1]))
        assert deployed['status']=='PASS' and deployed['source_sha256']==replay['prospective_source_sha256']==digest
        assert replay['status']=='PASS_READ_ONLY_POST_SCORE_CHECKPOINT' and replay['checkpoint_sha256']==paused['execution_sha256']
        assert not run.common.idle()['active_jobs']
        value=run.common.remote(REMOTE,dict(job_id=paused['job_id'],run_id=paused['run_id'],owner=previous['owner'],
            checkpoint_sha256=paused['execution_sha256'],source_sha256=digest,key=run.KEY+'-user-resume-after-score',
            authorization='2026-09-30：用户在明确暂停并保存检查点后要求继续本次真实测试'))
        with receipt.open('xb') as stream:stream.write(encode(value)+b'\n')
        print(json.dumps(value,ensure_ascii=False))
