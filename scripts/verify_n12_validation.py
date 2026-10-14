"""Deployed-byte and real historical-source replay; no job submission or model execution."""
import json
import subprocess
import prepare_m1_p1_deploy as common
import prepare_n12_validation as deploy
from t01_phase1_real.common import sha

REMOTE='''import json,sys
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import sha,decode,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import validation,policy,service
from t01_phase1_real.development.n12_prediction_evidence import verified_prediction
from t01_phase1_real.development.variant_report.m1 import verified_preselection
p=json.load(sys.stdin)
hashes={n:sha((Path('/app/src/t01_phase1_real')/n).read_bytes()) for n in p['hashes']}
assert hashes==p['hashes']
rt=Runtime('/var/lib/t01/runtime',scope='svc-'+p['owner'][:24],blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
before=rt.get(p['job_id']);execution=rt.execution(p['job_id']);rows=execution['nodes']
b=decode(rt._request_bytes(before))
fact=validation.assemble(rt,b,rows,'validation',before['run_id'])
assert len(fact['records'])==24 and fact['status']=='ALL_REJECTED'
assert fact['rejected']==list(range(1,25)) and not fact['review_pool'] and not fact['unavailable']
assert all(r['reason']=='R35_DETERIORATION_EXCEEDED' and r['mutation_burden'] for r in fact['records'])
score=service.source(rt,rows['rescore'])['artifact']
prediction=rows['rep1_prediction']['job_id']
with rt._db() as db:
    # r16 predates the persisted preselection node. Rebuild its historical
    # selection from the verified audit; never invent a new validation fact
    # or write this old selection back into the archived workflow.
    historical_selection=verified_preselection(rt,db,b['protein_sequence'],b['user_sequence_id'],
        service.source(rt,rows['design_audit']))
    selected=historical_selection['selected'][0]
    sequence=next(g['sequence'] for g in rt.result(rows['design']['job_id'])['generation']['records']
        if g['sample_number']==selected['sample_number'])
    # The legacy score payload binds its original execution profile. This
    # deployment replays the full audit above and separately verifies the
    # prediction's exact sequence/run/host/native bytes. It does not relabel
    # the old scoring payload as a newly prepared current-profile input.
    linked=dict(sample_number=selected['sample_number'],sequence_sha256=sha(sequence.encode()),
        scoring_artifact=score,historical_audit_replayed=True,
        current_profile_scoring_restage='NOT_APPLICABLE_HISTORICAL_PROFILE')
    try:
        linked['prediction']=verified_prediction(rt,db,prediction,sequence,b['host_species'],before['run_id'],include_quality=True)
    except RuntimeFault as exc:
        if exc.code!='OUTPUT_INVALID':raise
        linked.update(status='HISTORICAL_PREDICTION_REPLAY_BLOCKED',error=str(exc),prediction_job_id=prediction)
    count_after=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
assert rt.get(p['job_id'])==before and rt.execution(p['job_id'])==execution
from t01_phase1_real.service_api.app import Principal
recent=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset(['query']),'none').runtime_scope)
recent_job=recent.get(p['recent_job_id']);recent_body=decode(recent._request_bytes(recent_job))
recent_prediction=recent.execution(recent_job['job_id'])['nodes']['prediction']['job_id']
with recent._db() as db:
    recent_link=verified_prediction(recent,db,recent_prediction,recent_body['protein_sequence'],
        recent_body['host_species'],recent_job['run_id'],include_quality=True)
assert recent.get(recent_job['job_id'])==recent_job
order=policy.order(dict(engineering_design='BACKEND_EVIDENCE_V1'))
assert order.index('validation')<order.index('retry1_design')<order.index('retry1_validation')<order.index('retry2_design')<order.index('retry2_validation')<order.index('preselection')
print(json.dumps(dict(status='S28_DEPLOYED_REAL_SOURCE_REPLAY_PASS',source_hashes=hashes,
    historical_parent=p['job_id'],historical_run=before['run_id'],archived_state_unchanged=True,
    real_round_replay=fact,real_prediction_link=linked,total_registered_jobs=count_after,
    recent_wt_prediction=dict(parent_job_id=recent_job['job_id'],run_id=recent_job['run_id'],
        sequence_length=len(recent_body['protein_sequence']),prediction=recent_link,
        purpose='Independent native prediction adapter replay; not a designed candidate or part of r16'),
    native_new_designs=0,native_48_64_generation='NOT_EXECUTED',new_workflow_started=False,
    historical_control_only=True,scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')))
'''


def main():
    before=common.idle();assert not before['active_jobs'] and before['gpu_state']['phase']=='idle'
    batch=json.loads((common.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/r16/batch.json').read_bytes())
    hashes={n:sha((common.ROOT/'src/t01_phase1_real'/n).read_bytes()) for n in deploy.FILES}
    recent=json.loads((common.ROOT/'reports/n05-duration-20260926/host-panel-flow-submit-r02.json').read_bytes())
    result=common.remote(REMOTE,dict(hashes=hashes,owner=batch['owner'],job_id=batch['job_id'],recent_job_id=recent['job_id']))
    code='''import json,hashlib
from pathlib import Path
from t01_phase1_real.development.af3 import policy
from t01_phase1_real.development.af3.primitives import encode
names=('policy.py','result.py','source.py')
hashes={'development/af3/'+n:hashlib.sha256((policy.HERE/n).read_bytes()).hexdigest() for n in names}
lengths=(77,233,500,999)
for n in lengths:
    policy.request(encode(dict(protein_sequence='A'*n,user_sequence_id='admission-only',host_species='pig',seed=1,timeout_seconds=7200)))
print(json.dumps(dict(source_hashes=hashes,admission_lengths=lengths,native_inference=False)))
'''
    worker=json.loads(subprocess.check_output(common.K+['exec','deployment/antigen-design','-c','worker-unified-gpu',
        '--','/opt/t01/supervisor/bin/python3.11','-B','-c',code]))
    assert worker['source_hashes']=={n:h for n,h in hashes.items() if n.startswith('development/af3/')}
    result['af3_worker']=worker
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['metadata']['generation']==live['status']['observedGeneration']
    assert live['status'].get('readyReplicas')==live['status'].get('updatedReplicas')==1
    result['generation']=live['metadata']['generation'];result['idle']=common.idle()
    assert not result['idle']['active_jobs'] and result['idle']['gpu_state']['phase']=='idle'
    with (deploy.EVIDENCE/'deployment-r01.json').open('x',encoding='utf8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status=result['status'],generation=result['generation'],
        real_samples=len(result['real_round_replay']['records']),
        linked_prediction=result['recent_wt_prediction']['prediction']['prediction_job_id'],
        historical_prediction=result['real_prediction_link'].get('status','PASS'))))


if __name__=='__main__':main()
