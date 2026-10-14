"""Apply explicit user consent to this v2 run's reviewed T4 audit only."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode

REMOTE = run.REMOTE.split("if p['action']=='start':", 1)[0] + r'''
from t01_phase1_real.development.workflow.confirmation import decide
job=rt.get(p['job_id']);assert job['run_id']==p['run_id']
ex=rt.execution(p['job_id']);pending=ex.get('pending_confirmation')
prior=ex.get('nodes',{}).get('design',{}).get('confirmation')
reviewed=p['reviewed']
if pending:
 assert pending['confirmation_id']==reviewed['confirmation_id']
 assert pending['audit_sha256']==reviewed['audit_sha256']
 assert pending['fixed_count']==reviewed['fixed']==0
 assert pending['restricted_count']==reviewed['restricted']==214
 assert pending['open_count']==reviewed['open']==0
 assert pending['warning']==reviewed['warning']
else:
 assert prior and prior['confirmation_id']==reviewed['confirmation_id'] and prior['decision'] is True
first=decide(rt,p['job_id'],reviewed['confirmation_id'],True,owner.principal_id)
second=decide(rt,p['job_id'],reviewed['confirmation_id'],True,owner.principal_id)
assert first['job_id']==second['job_id']
consent=rt.execution(p['job_id'])['nodes']['design']['confirmation']
assert consent['decision'] is True and consent['audit_sha256']==reviewed['audit_sha256']
continued=rpc('workflow.recover',dict(job_id=p['job_id'],idempotency_key=p['key']))
print(json.dumps(dict(job_id=p['job_id'],run_id=p['run_id'],confirmation_id=consent['confirmation_id'],
 decision=True,consent=consent,idempotency_verified=True,continuation=continued,
 user_authorization=p['user_authorization'],reviewed_warning=reviewed['warning'],
 scientific_gate='CLOSED',production_status='NOT_DEPLOYED',new_workflow=False)))
'''

if __name__ == '__main__':
    receipt = run.OUT / 't4-confirmation.json'
    if receipt.exists():
        print(receipt.read_text(encoding='utf8'))
    else:
        submitted = json.loads((run.OUT / 'submission.json').read_bytes())
        reviewed = json.loads((run.OUT / 'wt-preflight-audit.json').read_bytes())['pending_audit']
        value = run.common.remote(REMOTE, dict(job_id=submitted['job_id'], run_id=submitted['run_id'],
            owner=submitted['owner'], reviewed=reviewed, key=run.KEY + '-t4-continue',
            user_authorization='2026-09-30：同意本次继续生成，接受上述限制'))
        with receipt.open('xb') as stream:
            stream.write(encode(value) + b'\n')
        print(json.dumps(value, ensure_ascii=False))
