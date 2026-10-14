"""Reverify registered P2 sources and real computations without rerunning models."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import run_m1_p2_probe as p
import prepare_m1_p2_deploy as deployment

EXECUTION_CHECKS=r'''
def execution_checks(jobs,native_execution,offline,expected_count=4):
    gpu=[dict(name=n,**jobs[n]) for n in native_execution]
    gpu.sort(key=lambda r:r['started_at'])
    resident={n for n,j in jobs.items() if j.get('backend')=='resident-process' and j['state']=='succeeded'}
    return dict(
        required_real_gpu_jobs=len(gpu)==expected_count,
        serial_gpu_intervals=bool(gpu) and all(r['started_at'] and r['finished_at'] and r['stopped'] is True
            and r['resident_stopped'] is True for r in gpu)
            and all(a['finished_at']<=b['started_at'] for a,b in zip(gpu,gpu[1:])),
        native_offline=bool(resident) and all(offline.get(n)=='seccomp-local-sockets-only-v1' for n in resident))
'''

AUDIT=EXECUTION_CHECKS+r'''
from t01_phase1_real.common import sha,RuntimeFault
from t01_phase1_real.development.variant_report.source import sources
from t01_phase1_real.development.variant_report.compute import evaluate
import copy
jobs={};verified=0
ensure(parent==task['p1_parent_snapshot'],'OUTPUT_INVALID','Terminal P1 parent changed')
native_execution={};offline={}
for name,jid in task['jobs'].items():
    j=rt.get(jid);ensure(j['run_id']==run_id,'FORBIDDEN','Foreign evidence job')
    for ref in j['artifacts']:rt.artifact_bytes(jid,ref['artifact_id']);verified+=1
    v=rt.result(jid) if j['artifacts'] else None
    if v and j['state']=='succeeded':
        for item in v['raw_artifacts']:
            if item['path']=='resident/executor-observation.json':
                offline[name]=decode(rt.artifact_bytes(jid,item['artifact']['artifact_id'])).get('network_restriction')
            if item['path']=='output/raw/execution.json' and j['tool_id']=='t01.real.esmfold2':
                native_execution[name]=decode(rt.artifact_bytes(jid,item['artifact']['artifact_id']))
            if item['path']=='output/runtime.json' and j['tool_id']=='t01.real.esm_if1':
                native_execution[name]=decode(rt.artifact_bytes(jid,item['artifact']['artifact_id']))
    jobs[name]=dict(job_id=jid,run_id=j['run_id'],state=j['state'],error_code=j['error_code'],
        started_at=j['started_at'],finished_at=j['finished_at'],artifact_count=len(j['artifacts']),
        execution_profile=j['execution_profile'],result=source(j) if j['state']=='succeeded' else None,
        backend=(v or {}).get('execution',{}).get('backend'),
        stopped=(v or {}).get('execution',{}).get('stopped_confirmed'),
        resident_stopped=((v or {}).get('execution',{}).get('resident_receipt') or {}).get('stopped_confirmed'))
final=rt.get(task['jobs']['final-report']);body=decode(rt._request_bytes(final))
with rt._db() as db:
    files,values,receipts=sources(rt,db,body)
rebuilt=evaluate(body,files);published=rt.result(final['job_id'])
ensure(rebuilt==published['report'],'OUTPUT_INVALID','P2 final report differs from registered source rebuild')
test=rebuilt['m1_test'];rows=test['records'];representatives=[r for r in rows if r['selected_for_recomputation']]
completed=[];facts=[]
for r in representatives:
    label=r['candidate_id'];q=r['prediction']['prediction']['quality']['structure']
    expected_names=[label+'-'+n for n in ('prediction','structure','bepipred','netmhc','epitope-map','glycosylation','developability')]
    complete=all(jobs[n]['state']=='succeeded' and jobs[n]['stopped'] is True for n in expected_names)
    complete=complete and r['foldx'] is not None and r['foldx']['runs']==5 and len(r['foldx']['native_ddg_runs'])==5
    complete=complete and r['n13'] is not None and r['esm_if1']['esm_if1_score'] is not None
    if complete:completed.append(label)
    facts.append(dict(candidate_id=label,sequence_sha256=r['sequence_sha256'],esm_if1=r['esm_if1'],
        mean_plddt=q['mean_plddt'],foldx=r['foldx'],disposition=r['disposition'],debug_only=r['debug_only'],
        n13=r['n13'],developability_dimensions={k:dict(status=v['status'],value=v['value'] if k=='expressibility' else None,
            reason=v['exclusion_reason']) for k,v in r['developability']['dimensions'].items()},
        n12_n15_complete=complete))
# Read-only adversarial checks use request copies, never altered artifacts.
negative={}
for case in ('duplicate_representative','wrong_variant_structure','wrong_wt_structure'):
    bad=copy.deepcopy(body)
    if case=='duplicate_representative':bad['m1_test']['representatives'][1]=bad['m1_test']['representatives'][0]
    elif case=='wrong_variant_structure':bad['m1_test']['representatives'][0]['structure']=bad['m1_test']['representatives'][1]['structure']
    else:bad['m1_test']['wt']['developability']=bad['m1_test']['representatives'][0]['developability']
    try:
        with rt._db() as db:sources(rt,db,bad)
    except RuntimeFault as exc:negative[case]=dict(rejected=True,code=exc.code)
    else:negative[case]=dict(rejected=False)
scored=rt.result(task['jobs']['esm-if1-r08'])
checks=dict(same_run=True,registered_hashes_verified=True,report_rebuilt=True,
    p1_parent_unchanged=True,
    scored_24=len(scored['scoring']['records'])==24 and all(r['score'] is not None for r in scored['scoring']['records']),
    real_wt_baseline=scored['baseline'] is not None and scored['baseline']['score'] is not None,
    representatives_at_most_3=1<=len(representatives)<=3,non_wt_n12_n15_completed=len(completed)>=1,
    all_requested_representatives_completed=len(completed)==len(representatives),
    independent_recompute=len({jobs[r['candidate_id']+'-bepipred']['job_id'] for r in representatives})==len(representatives),
    formal_closed=published['usable_for_pipeline'] is False and published['automatic_handoff'] is False
        and published['production_status']=='NOT_DEPLOYED' and test['scientific_release_gate']=='CLOSED'
        and rebuilt['ranked_candidates'] is None and rebuilt['pareto_front'] is None and rebuilt['best_candidate'] is None
        and all(r['scientific_eligible'] is False for r in rows),
    exclusions_preserved=all(r['disposition']=='EXCLUDED' and r['esm_if1']['passed'] is False for r in rows),
    not_selected_distinct=sum(r['recomputation_state']=='NOT_SELECTED_NOT_COMPUTED' for r in rows)==24-len(representatives),
    source_negative_checks=all(r['rejected'] for r in negative.values()),
    baseline_computed_once_per_scoring_task=all(native_execution[n]['baseline_model_calls']==1 for n in ('esm-if1','esm-if1-r08')),
    native_variant_calls_24_per_scoring_task=all(native_execution[n]['variant_model_calls']==24 for n in ('esm-if1','esm-if1-r08')),
    native_a100=all(v.get('gpu_name')=='NVIDIA A100-SXM-64GB' for v in native_execution.values()),
    all_native_processes_stopped=all(j['stopped'] is True for name,j in jobs.items() if 'failed-' not in name))
checks.update(execution_checks(jobs,native_execution,offline,expected_count=5))
print(json.dumps(dict(status='M1_P2_N12_N15_PASS' if all(checks.values()) else 'M1_P2_INCOMPLETE',
    checks=checks,run_id=run_id,p1_parent_job_id=parent['job_id'],verified_artifacts=verified,
    candidate_count=len(rows),completed_candidates=completed,representatives=facts,
    baseline_score=scored['baseline']['score'],jobs=jobs,negative_checks=negative,native_execution=native_execution,
    scientific_release_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED',
    offline_receipts=offline,report_api_called=False,p3_p4_executed=False)))
'''


def main():
    task=p.context();original=json.loads((p.OUT/'continuation.json').read_bytes())
    assert task==original,'P1 evidence changed'
    task['jobs']={}
    task['p1_parent_snapshot']=json.loads((p.P1/'workflow-snapshot.json').read_bytes())['job']
    for f in p.OUT.glob('*.json'):
        row=json.loads(f.read_bytes())
        if isinstance(row,dict) and row.get('job'):task['jobs'][f.stem]=row['job']['job_id']
    result=p.deploy.remote(p.PREAMBLE+AUDIT,task)
    result['checks']['p1_evidence_unchanged']=p.context()==original
    result['p1_evidence_sha256']=original['p1_evidence_sha256']
    p.save('audit-summary.json',result)
    print(json.dumps(dict(status=result['status'],checks=result['checks'],completed_candidates=result['completed_candidates'],verified_artifacts=result['verified_artifacts']),indent=2))


if __name__=='__main__':main()
