"""Read-only native generation replay and independent mutation-count audit."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode

REMOTE = run.REMOTE.split("if p['action']=='start':", 1)[0] + r'''
from collections import Counter
from t01_phase1_real.common import encode
from t01_phase1_real.development.workflow.revision_controller import generation,inputs
from t01_phase1_real.development.workflow.revision_sampling import inspect
from t01_phase1_real.development.workflow.revision_budget import summary
jid=p['job_id'];job=rt.get(jid);body=decode(rt._request_bytes(job));ex=rt.execution(jid);rows=ex['nodes']
data,reason=inputs(rt,jid,body);assert reason is None
wt=body['protein_sequence'];snap=data['snapshot'];b=snap['mutation_budget']['B'];batches=[];records=[]
for name,row in rows.items():
 if not name.startswith(('proposal','formal')) or row.get('state')!='succeeded':continue
 generated,ref,child=generation(rt,body,rows,name,job['run_id'])
 req=decode(rt._request_bytes(child));stage=req['revision_context']['stage'];constraints=req['constraints']
 opened=set(constraints['open_positions'])|{r['position'] for r in constraints['restricted_positions']}
 counts=[];reasons=Counter();checks=[]
 for record in generated['records']:
  sequence=record['sequence'];n=sum(a!=bb for a,bb in zip(wt,sequence))
  assert len(sequence)==len(wt) and len(record['mutations'])==n
  checked=inspect(snap,sequence,opened,proposal=stage=='proposal_only',scales=data['scales'])
  assert checked['mutation_count']==n
  counts.append(n);reasons.update(checked['reason_codes']);checks.append(checked['check_status'])
  records.append(dict(batch=name,stage=stage,sample_number=record['sample_number'],
   content_hash=sha(sequence.encode()),mutation_count=n,check_status=checked['check_status'],
   reasons=checked['reason_codes'],mutated_positions=[m['position'] for m in checked['mutations']],
   generation_ref=ref))
 batches.append(dict(step=name,job_id=child['job_id'],stage=stage,requested=req['n_designs'],
  generated=len(counts),seed=req['seed'],temperature=req['sampling_temperature'],
  fixed=len(constraints['fixed_positions']),restricted=len(constraints['restricted_positions']),open=len(constraints['open_positions']),
  independent_mutation_min=min(counts) if counts else None,independent_mutation_max=max(counts) if counts else None,
  constraint_states=dict(Counter(checks)),reason_counts=dict(reasons),native_tool_invoked=generated['engine_runtime']['tool_invoked'],
  request_sha256=sha(rt._request_bytes(child)),result_ref=ref))
budget=summary(ex['revision_ledger'],body['revision_config']) if ex.get('revision_ledger') else {}
print(json.dumps(dict(status='PASS_READ_ONLY_NATIVE_GENERATION_REPLAY',job_id=jid,run_id=job['run_id'],
 mutation_budget_B=b,design_site_budget_K=snap['mutation_budget']['K'],batches=batches,records=records,budget=budget,
 frozen_wt=ex.get('revision_v2_frozen'),round_outcomes=ex.get('revision_round_outcomes',{}),
 allocations=ex.get('revision_allocations',{}),downstream_allocations=ex.get('revision_v2_allocations',{}),
 models_called_by_audit=False,new_jobs=0,scientific_gate='CLOSED',production_status='NOT_DEPLOYED')))
'''

if __name__ == '__main__':
    submitted = run.active_submission()
    value = run.common.remote(REMOTE, dict(job_id=submitted['job_id'], owner=submitted['owner']))
    (run.OUT / 'generation-audit.json').write_bytes(encode(value) + b'\n')
    print(json.dumps({k: value[k] for k in ('status', 'mutation_budget_B', 'design_site_budget_K', 'batches', 'budget', 'round_outcomes')}, ensure_ascii=False))
