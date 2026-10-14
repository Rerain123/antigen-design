"""Diagnose cross-release BepiPred profile comparisons without changing results."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode

OUT=run.common.ROOT/'reports/expert-revision-v2-resume-20260930'
REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
from t01_phase1_real.development.workflow.service import source
from t01_phase1_real.development.workflow.revision_v2_runtime import bp
job=rt.get(p['job_id']);ex=rt.execution(job['job_id']);rows=[]
for name,node in ex['nodes'].items():
 if name!='bepipred' and not name.endswith('_bepipred'):continue
 child=rt.get(node['job_id']);sequence=decode(rt._request_bytes(child))['protein_sequence']
 scores,profile=bp(rt,source(rt,node),sequence,job['run_id'])
 rows.append(dict(step=name,job_id=child['job_id'],profile=profile,native_scores=len(scores)))
wt=next(r for r in rows if r['step']=='bepipred')
print(json.dumps(dict(status='PASS_READ_ONLY_PROFILE_DIAGNOSIS',profiles=rows,
 comparison=[dict(step=r['step'],execution_match=r['profile']['execution']==wt['profile']['execution'],
 rule_match=r['profile']['rule']==wt['profile']['rule'],parameters_match=r['profile']['parameters']==wt['profile']['parameters'])
 for r in rows if r is not wt],native_models_called=False,published_results_changed=False)))
'''

if __name__=='__main__':
    submitted=run.active_submission()
    value=run.common.remote(REMOTE,dict(job_id=submitted['job_id'],owner=submitted['owner']))
    initial=json.loads((run.common.ROOT/'deploy/expert-revision-v2/r01/preflight.json').read_bytes())['source_hashes']
    current=json.loads((OUT/'tested-source.json').read_bytes())['source_hashes']
    changed=[n for n in sorted(initial.keys()|current.keys()) if initial.get(n)!=current.get(n)]
    predictors=[n for n in initial if n.startswith('t01_phase1_real/development/bepipred/')]
    assert all(initial[n]==current[n] for n in predictors)
    value.update(changed_source_files_since_wt=changed,bepipred_source_files_unchanged=predictors,
        profile_scope='registered_profile hashes all development modules and the base runtime, not only predictor files',
        observed_effect='L4 PREDICTOR_PROFILE_MISMATCH; original NOT_ASSESSED conclusions retained',
        recommendation='Keep historical results immutable. Assess versioned predictor-specific identity and cross-release compatibility separately; no scientific release or new model task inferred.',
        scientific_gate='CLOSED')
    (OUT/'predictor-profile-diagnosis.json').write_bytes(encode(value)+b'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='bepipred_source_files_unchanged'},ensure_ascii=False))
