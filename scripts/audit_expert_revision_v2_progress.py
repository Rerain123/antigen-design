"""Read-only native scoring replay and observed resident progress."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode

REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
from t01_phase1_real.development.workflow import revision_controller as rc
jid=p['job_id'];job=rt.get(jid);body=decode(rt._request_bytes(job));data,reason=rc.inputs(rt,jid,body);assert reason is None
fact=rc.assemble(rt,jid,body,data);ex=rt.execution(jid);cheap=ex['nodes']['cheap0'];cj=rt.get(cheap['job_id']);cr=rt.result(cj['job_id'])
records=[dict(candidate_id=r['candidate_id'],sample_number=r['sample_number'],disposition=r['disposition'],
 mutation_count=len(r['mutations']),constraint=r['constraint_check'],esm_if1=r['esm_if1'],validation=r['validation'],
 structure_observations=r.get('structure_observations'),protection=r.get('protection'),l4=r.get('l4'),foldx=r.get('foldx'))
 for r in fact['formal_records'] if r['disposition']=='FORMAL_POOL']
msa=ex['nodes'].get('wt_msa');mjob=rt.get(msa['job_id']) if msa and msa.get('job_id') else None
mx=rt.execution(mjob['job_id']) if mjob else {}
observed=[]
if mx.get('resident_target'):
 root=Path(mx['resident_target'])
 observed=[dict(path=f.relative_to(root).as_posix(),size_bytes=f.stat().st_size)
  for f in sorted(root.rglob('*')) if f.is_file() and not f.name.endswith('.lock')]
print(json.dumps(dict(status='PASS_READ_ONLY_NATIVE_CHEAP_REPLAY',job_id=jid,run_id=job['run_id'],records=records,
 cheap=dict(job_id=cj['job_id'],state=cj['state'],started_at=cj['started_at'],finished_at=cj.get('finished_at'),
 result_sha256=next(a['sha256'] for a in cj['artifacts'] if a['role']=='result'),scoring=cr['scoring']),
 budget=fact['run_audit'],msa=dict(job=mjob,execution={k:mx.get(k) for k in
  ('phase','tree_stopped','resident_target','resident_diagnostic','backend')},observed_files=observed) if mjob else None,
 native_models_called_by_audit=False,scientific_gate='CLOSED')))
'''

if __name__=='__main__':
    submitted=run.active_submission()
    value=run.common.remote(REMOTE,dict(job_id=submitted['job_id'],owner=submitted['owner']))
    (run.OUT/'cheap-scoring-audit.json').write_bytes(encode(value)+b'\n')
    print(json.dumps(dict(status=value['status'],unique_candidates=len(value['records']),
        records=[dict(candidate_id=r['candidate_id'],mutations=r['mutation_count'],esm=r['esm_if1']) for r in value['records']],
        budget=value['budget'],msa=value['msa']['execution'] if value['msa'] else None),ensure_ascii=False))
