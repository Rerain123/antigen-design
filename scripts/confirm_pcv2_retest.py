"""Apply the user's explicit T4 decision for the reviewed 214-aa audit only."""
import json
import run_pcv2_slot_retest as retest
from version_bundle import encode

runner=retest.runner
CONFIRMATION='t4-4df3a9b40525ff9b4547f23f98f52868c12c4208bd13e4d85b81f5bd0bd5971a'
REMOTE=runner.REMOTE.split("if p['action']=='start':",1)[0]+r'''
before=rpc('workflow_check',dict(job_id=p['job_id']))
pending=rt.execution(p['job_id']).get('pending_confirmation')
assert pending and pending['confirmation_id']==p['confirmation_id']
assert pending['fixed_count']==0 and pending['restricted_count']==214 and pending['open_count']==0
args=dict(job_id=p['job_id'],confirmation_id=p['confirmation_id'],decision=True)
first=rpc('workflow_confirm_design',args)
second=rpc('workflow_confirm_design',args)
print(json.dumps(dict(job_id=p['job_id'],confirmation_id=p['confirmation_id'],decision=True,first=first,repeat=second,
 user_authorization=p['user_authorization'],reviewed_warning=pending['warning'])))
'''

if __name__=='__main__':
    path=runner.OUT/'t4-confirmation.json'
    if path.exists():
        print('T4 decision already recorded locally')
    else:
        jid=json.loads((runner.OUT/'submission.json').read_bytes())['job_id']
        value=runner.common.remote(REMOTE,dict(job_id=jid,confirmation_id=CONFIRMATION,
            user_authorization='允许本次继续生成候选，接受上述限制'))
        path.write_bytes(encode(value));print(json.dumps(value,ensure_ascii=False))
