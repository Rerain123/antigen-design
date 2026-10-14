"""N10 partial engineering acceptance with real structure, A3D and PROPKA outputs."""
import argparse
import copy
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import RuntimeFault, encode, decode, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.developability import policy
from structure_integration_cases import cases as structure_cases

SEQ='ACDEFGHIKLMNPQRSTVWY'
ABSENT=dict(state='not_provided',artifact=None,reason_code=None)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(value if isinstance(value,bytes) else encode(value))


def request(sequence=SEQ,structure=None,**changes):
    value=dict(protein_sequence=sequence,user_sequence_id='N10 engineering',structure_input=copy.deepcopy(structure or ABSENT),
        target_ph=None,target_ph_range=[4.0,8.0],dimension_weights=None,timeout_seconds=60)
    value.update(changes);return value


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True);parser.add_argument('--batch',required=True)
    a=parser.parse_args();root=Path(a.root).absolute();batch=Path(a.batch).absolute()
    assert not root.exists() and not batch.exists() and batch.is_relative_to(REPO/'discovery/t01-phase1-real/w4')
    batch.mkdir(parents=True);rt=Runtime(root);results=[];upstreams=[]
    write(batch/'profile.json',policy.registered_profile());write(batch/'rules.json',policy.registered_rules())
    for path in [*policy.HERE.glob('*.py'),*[policy.HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py')],
            Path(__file__),REPO/'tests/test_developability_development.py',REPO/'requirements/developability.txt']:
        if path.is_file():write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    def collect(name,job,state='succeeded',error=None,group='cases'):
        job=rt.wait(job['job_id'],900);write(batch/group/name/'job.json',job);write(batch/group/name/'events.json',rt.events(job['job_id']))
        value=rt.result(job['job_id']) if job['artifacts'] else None
        if value:write(batch/group/name/'result.json',value)
        for ref in job['artifacts']:
            raw=rt.artifact_bytes(job['job_id'],ref['artifact_id'])
            assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256'];write(batch/group/name/'artifacts'/ref['artifact_id'],raw)
        assert job['state']==state and job['error_code']==error,(name,job['state'],job['error_code'])
        assert not job['usable_for_pipeline']
        if value:assert not value['automatic_handoff'] and value['production_status']=='NOT_DEPLOYED'
        row=dict(case=name,job_id=job['job_id'],state=state,error_code=error,artifacts_verified=len(job['artifacts']))
        (upstreams if group=='upstreams' else results).append(row);print(encode(row).decode(),flush=True)
        return job,value
    def run(name,body=None,fault=None,state='succeeded',error=None):
        body=body or request();write(batch/'requests'/(name+'.json'),body)
        job=rt.submit_sequence(encode(body),name,policy.TOOL);rt._development_fault=fault
        try:rt.dispatch(job['job_id'])
        finally:rt._development_fault=None
        return collect(name,job,state,error)
    def source(job):return dict(state='available',artifact=next(x for x in job['artifacts'] if x['role']=='result'),reason_code=None)

    baseline,base_value=run('no-structure')
    assert base_value['developability']['dev_dims_available']==1
    assert base_value['developability']['overall_score'] is None and not base_value['developability']['n10_complete']
    assert base_value['steps']['tag_exposure']['status']=='unknown'
    assert base_value['steps']['aggregation']['reason_code']=='STRUCTURE_NOT_AVAILABLE_SEQUENCE_AGGRESCAN_ASSET_NOT_REGISTERED'

    fixtures={row['name']:row for row in structure_cases()}
    for name in ('normal-cif','normal-pdb','quality-unknown-source','rsa-out-of-domain'):
        fixture=fixtures[name]
        job=rt.submit_structure(encode(fixture['request']),'structure-'+name,fixture['data']);rt.dispatch(job['job_id'])
        job,value=collect(name,job,group='upstreams')
        linked=request(fixture['request']['protein_sequence'],source(job))
        _,n10=run('linked-'+name,linked)
        tag=n10['steps']['tag_exposure']
        if name in ('normal-cif','normal-pdb'):
            assert tag['status']=='computed_unreviewed' and tag['n_term'] is not None and not tag['reliable']
            assert n10['developability']['dev_dims_available']==4 and n10['developability']['dev_dims_reliable']==1
            ph=n10['steps']['ph_stability'];assert ph['execution']['status']=='executed'
            assert ph['status']=='unreliable' and ph['dg_curve'] and ph['method']['propka_version']=='3.5.1'
            assert next(row for row in ph['dg_curve'] if row['pH']==7.0)['dG_kcal_mol']==0.0
            expected_mode='verified_n02_atom_ledger_pdb_projection' if name=='normal-cif' else 'unchanged_source_pdb'
            assert ph['execution']['command']['input_mode']==expected_mode
            aggregation=n10['steps']['aggregation']
            assert aggregation['status']=='computed_unreviewed' and not aggregation['reliable']
            assert aggregation['execution']['status']=='executed' and aggregation['mode']=='structure'
            assert aggregation['execution']['command']['input_mode']=='target_chain_atom_projection_from_'+expected_mode
            assert aggregation['per_residue']
        elif name=='quality-unknown-source':
            assert tag['reason_code']=='STRUCTURE_QUALITY_LOW'
            assert n10['steps']['aggregation']['reason_code']=='STRUCTURE_QUALITY_LOW_SEQUENCE_AGGRESCAN_ASSET_NOT_REGISTERED'
        else:
            assert tag['reason_code']=='OUTPUT_INVALID'
            assert n10['steps']['ph_stability']['execution']['status']=='executed'
            assert n10['steps']['aggregation']['execution']['status']=='executed'

    run('explicit-weights-still-no-overall',request(dimension_weights={name:1 for name in policy.DIMENSIONS}))
    run('compute-failure',fault='compute_failure',state='failed',error='TOOL_FAILED')
    run('corrupt-output',fault='corrupt_output',state='failed',error='OUTPUT_INVALID')
    queued=rt.submit_sequence(encode(request()),'queued-cancel',policy.TOOL)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=queued['job_id'],idempotency_key='cancel')))
    collect('queued-cancel',queued,'cancelled','CANCELLED')
    interrupted=rt.submit_sequence(encode(request()),'interrupted',policy.TOOL);rt._development_fault='interrupt_after_claim'
    try:rt.dispatch(interrupted['job_id'])
    finally:rt._development_fault=None
    rt.recover(interrupted['job_id']);collect('interrupted',interrupted,'failed','INTERRUPTED')
    retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=interrupted['job_id'],idempotency_key='retry')))
    rt.dispatch(retry['job_id']);collect('retry',retry)
    assert rt.submit_sequence(encode(request()),'no-structure',policy.TOOL)['job_id']==baseline['job_id']
    try:rt.submit_sequence(encode(request(user_sequence_id='changed')),'no-structure',policy.TOOL)
    except RuntimeFault as exc:assert exc.code=='IDEMPOTENCY_CONFLICT'
    else:raise AssertionError('Changed duplicate accepted')

    documented=request();write(batch/'requests/documented.json',documented)
    argv=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),'developability',
        '--input',str(batch/'requests/documented.json'),'--key','documented','--run']
    proc=subprocess.run(argv,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    write(batch/'documented-command.json',dict(argv=argv,exit_code=proc.returncode,stdout=proc.stdout.decode(),stderr=proc.stderr.decode()))
    assert proc.returncode==0;collect('documented',decode(proc.stdout)['job'])

    fixture=fixtures['normal-cif']
    source_job=rt.submit_structure(encode(fixture['request']),'structure-tamper-source',fixture['data']);rt.dispatch(source_job['job_id'])
    source_job,_=collect('tamper-source',source_job,group='upstreams')
    linked=request(fixture['request']['protein_sequence'],source(source_job))
    pending=rt.submit_sequence(encode(linked),'late-structure-tamper',policy.TOOL);ref=linked['structure_input']['artifact']
    with rt._db() as db:path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    with (root/path).open('ab') as stream:stream.write(b'controlled acceptance tamper')
    rt.dispatch(pending['job_id']);collect('late-structure-tamper',pending,'failed','HASH_MISMATCH')

    write(batch/'guards.json',dict(partial_only=True,complete_n10=False,overall_score_emitted=False,design_gate_evaluated=False,
        real_structure_artifact_linked=True,scientific_consumption=False,camsol_parameters_complete=False,
        aggregation_structure_asset_registered=True,aggregation_sequence_asset_registered=False,
        aggregation_spatial_signoff_complete=False,propka_asset_registered=True,propka_gui_benchmark_complete=False))
    files=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
        for p in sorted(batch.rglob('*')) if p.is_file()]
    write(batch/'index.json',dict(status='PASS',scope='N10_S36A_S37_STRUCTURE_S38_DEVELOPMENT_S39_S40_PARTIAL_ENGINEERING',cases=results,upstreams=upstreams,
        files=files,n10_complete=False,overall_score_emitted=False,design_gate_evaluated=False,scientific_signoff=None,
        usable_for_pipeline=False,production_status='NOT_DEPLOYED'))
    print('N10_PARTIAL_ENGINEERING_ACCEPTANCE_PASS',flush=True)


if __name__=='__main__':main()
