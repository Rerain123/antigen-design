"""Read and verify this fresh native run's completed results and audit binding."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode

REMOTE = run.REMOTE.split("if p['action']=='start':", 1)[0] + r'''
from t01_phase1_real.development.workflow.service import verified
jid=p['job_id'];job=rt.get(jid);body=decode(rt._request_bytes(job));ex=rt.execution(jid)
rows=ex['nodes'];evidence=[]
for name,row in rows.items():
 if not row.get('job_id') or row['state']!='succeeded':continue
 child=verified(rt,body,name,row['job_id'],job['run_id'],rows)
 result=rt.result(child['job_id']);execution=rt.execution(child['job_id'])
 evidence.append(dict(step=name,node_id=row['node_id'],job_id=child['job_id'],tool_id=child['tool_id'],
  state=child['state'],created_at=child.get('created_at'),updated_at=child.get('updated_at'),
  started_at=execution.get('started_at'),finished_at=execution.get('finished_at'),
  backend=execution.get('backend'),execution_identity=child.get('execution_identity'),
  result_sha256=next(a['sha256'] for a in child['artifacts'] if a['role']=='result'),
  execution_profile=child.get('execution_profile'),rule_profile=child.get('rule_profile')))
pending=ex.get('pending_confirmation');audit=None
if pending:
 audit_job=rt.get(pending['audit_job_id']);result=rt.result(audit_job['job_id'])['audit']
 ref=next(a for a in audit_job['artifacts'] if a['role']=='result')
 assert ref['sha256']==pending['audit_sha256']
 assert sha(__import__('t01_phase1_real.common',fromlist=['encode']).encode(result['pending_n11_request_draft']))==pending['draft_sha256']
 perm=result['permissions']
 audit=dict(confirmation_id=pending['confirmation_id'],audit_sha256=ref['sha256'],
  fixed=len(perm['fixed_positions']),restricted=len(perm['restricted_positions']),open=len(perm['open_positions']),
  mask_conversion_error=result['mask_conversion_error'],warning=pending['warning'],binding_verified=True)
print(json.dumps(dict(status='PASS_COMPLETED_EVIDENCE',job_id=jid,run_id=job['run_id'],
 completed_result_count=len(evidence),completed_results=evidence,pending_audit=audit,
 coverage='Completed child results only; pending and skipped steps are not successes',
 scientific_gate='CLOSED',production_status='NOT_DEPLOYED',new_jobs=0,models_called_by_audit=False)))
'''

if __name__ == '__main__':
    submitted = run.active_submission()
    value = run.common.remote(REMOTE, dict(job_id=submitted['job_id'], owner=submitted['owner']))
    name = 'wt-preflight-audit.json' if value['pending_audit'] else 'completed-evidence-audit.json'
    (run.OUT / name).write_bytes(encode(value) + b'\n')
    print(json.dumps({k: value[k] for k in ('status', 'job_id', 'completed_result_count', 'pending_audit')}, ensure_ascii=False))
