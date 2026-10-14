"""Continue the authorized test via the existing authenticated operator API."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode,build,sha

OUT=run.common.ROOT/'reports/expert-revision-v2-bepi-fix-20260930'
REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
from t01_phase1_real.common import encode
from t01_phase1_real.service_api.app import ServiceStore
source=rt.get(p['job_id']);prior=rt.execution(p['job_id'])
assert source['run_id']==p['run_id'] and source['state']=='cancelled' and prior['tree_stopped'] is True
assert sha(encode(prior))==p['source_execution_sha256']
ServiceStore(rt.root).authorize_job(owner,p['job_id'])
def start():
 request=urllib.request.Request('http://127.0.0.1:18083/v1/workflows/'+p['job_id']+'/candidate-analysis',
  headers={'Content-Type':'application/json','Authorization':'Bearer '+credential['token']},
  data=json.dumps(dict(idempotency_key=p['key'])).encode())
 with urllib.request.urlopen(request,timeout=85) as response:return json.load(response)
first=start();second=start();assert first['job_id']==second['job_id']
job=rt.get(first['job_id']);ex=rt.execution(job['job_id'])
assert job['run_id']==source['run_id'] and job['job_id']!=source['job_id']
assert job['request_artifact']==source['request_artifact'] and job['execution_profile']!=source['execution_profile']
assert ex['started_at']==prior['started_at'] and ex.get('confirmation_wait_seconds',0)==prior.get('confirmation_wait_seconds',0)
assert ex['revision_v2_frozen']==prior['revision_v2_frozen']
assert ex['nodes']['design']['confirmation']==prior['nodes']['design']['confirmation']
for kind in ('reservations','attempts','observed_objects'):
 assert all(ex['revision_ledger'][kind][key]==value for key,value in prior['revision_ledger'][kind].items())
assert sha(encode(rt.execution(p['job_id'])))==p['source_execution_sha256'] and rt.get(p['job_id'])==source
assert all(ex['nodes'][name]['job_id']==row['job_id'] for name,row in prior['nodes'].items() if row.get('job_id'))
print(json.dumps(dict(status='SAME_RUN_V2_CHECKPOINT_SUBMITTED',job_id=job['job_id'],run_id=job['run_id'],
 owner=sha(owner.principal_id.encode()),source_job_id=p['job_id'],request_sha256=sha(rt._request_bytes(job)),
 source_sha256=p['source_sha256'],state=job['state'],idempotency_verified=True,new_parent=True,new_run=False,
 continuation=ex['continuation'],source_checkpoint_unchanged=True,original_deadline_preserved=True,
 prior_budget_preserved=True,t4_receipt_preserved=True,scientific_gate='CLOSED',production_status='NOT_DEPLOYED')))
'''

if __name__=='__main__':
    receipt=OUT/'continuation-submission.json'
    if receipt.exists():
        print(receipt.read_text(encoding='utf8'))
    else:
        deployed=json.loads((OUT/'deployment-verification.json').read_bytes())
        stopped=json.loads((OUT/'checkpoint-stop.json').read_bytes())
        submitted=json.loads((run.OUT/'submission.json').read_bytes())
        digest=sha(encode(build(run.common.ROOT/'src')[1]))
        assert deployed['status']=='PASS' and deployed['source_sha256']==digest
        assert stopped['job_id']==submitted['job_id'] and stopped['run_id']==submitted['run_id']
        assert not run.common.idle()['active_jobs']
        value=run.common.remote(REMOTE,dict(job_id=submitted['job_id'],run_id=submitted['run_id'],owner=submitted['owner'],
            key=run.KEY+'-verified-interface-continuation',source_execution_sha256=stopped['source_execution_sha256'],source_sha256=digest))
        with receipt.open('xb') as stream:stream.write(encode(value)+b'\n')
        print(json.dumps(value,ensure_ascii=False))
