"""W5 N11 real offline GPU generation and explicitly separate guard/lifecycle evidence."""
import argparse
import copy
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import RuntimeFault,encode,decode,sha,now
from t01_phase1_real.development import Runtime,docker
from t01_phase1_real.development.proteinmpnn import policy
from t01_phase1_real.winprocess import alive
from t01_structure_mapping.probe import parse_local
from run_deeptmhmm_acceptance import until
from structure_integration_cases import cases as structure_cases,metadata,geometry,cif,SEQUENCE


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(value if isinstance(value,bytes) else encode(value))


def request(sequence,ref,source_id,**changes):
    value=dict(protein_sequence=sequence,user_sequence_id=source_id,structure_artifact=ref,
        constraints=dict(purpose='ENGINEERING_EXPLICIT_MASKS',source_id=source_id,fixed_positions=[1,len(sequence)],
            restricted_positions=[dict(position=2,allowed_residues=''.join(sorted(set(sequence[1]+'A'))))],
            open_positions=list(range(3,len(sequence)))),n_designs=24,sampling_temperature=0.1,seed=17,timeout_seconds=180)
    value.update(changes);return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--batch',required=True);parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args();root=Path(args.root).absolute();batch=Path(args.batch).absolute()
    assert root.is_relative_to(REPO/'var/t01-phase1-real') and not root.exists()
    assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w5') and not batch.exists()
    batch.mkdir(parents=True);rt=Runtime(root);entries=[];guards=[]
    profile=policy.registered_profile();write(batch/'profile.json',profile);write(batch/'rules.json',policy.registered_rules())
    write(batch/'assets.json',policy.verify_assets())
    paths=[*policy.HERE.glob('*.py'),*policy.HERE.glob('*.json'),
        *[policy.HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py','docker.py','supervisor.py')],
        *list((REPO/'src/t01_structure_mapping').glob('*.py')),REPO/'requirements/proteinmpnn.Dockerfile',
        Path(__file__),REPO/'scripts/structure_integration_cases.py',REPO/'tests/test_proteinmpnn_development.py']
    for path in paths:write(batch/'source'/path.relative_to(REPO),path.read_bytes())

    def finish(name,job,state='succeeded',error=None,kind='REAL_NATIVE_GENERATION'):
        final=rt.wait(job['job_id'],900);value=rt.result(job['job_id']) if final['artifacts'] else None
        write(batch/'cases'/name/'job.json',final);write(batch/'cases'/name/'events.json',rt.events(job['job_id']))
        if final['attempt_id']:write(batch/'cases'/name/'execution.json',rt.execution(job['job_id']))
        if value:write(batch/'cases'/name/'result.json',value)
        for ref in final['artifacts']:
            raw=rt.artifact_bytes(final['job_id'],ref['artifact_id'])
            assert sha(raw)==ref['sha256'] and len(raw)==ref['size_bytes'];write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
        assert final['state']==state and final['error_code']==error,(name,final['state'],final['error_code'],value and value['execution'])
        assert not final['usable_for_pipeline']
        if value:
            assert not value['usable_for_pipeline'] and not value['automatic_handoff'] and value['production_status']=='NOT_DEPLOYED'
            if final['tool_id']==policy.TOOL:
                assert value['design_permissions'] is None and value['formal_candidates'] is None and value['scientific_gate']=='NOT_EVALUATED'
                if error:assert value['generation'] is None
        if final['attempt_id']:assert rt.execution(final['job_id'])['tree_stopped']
        generation=value and value.get('generation')
        row=dict(case=name,kind=kind,job_id=final['job_id'],tool_id=final['tool_id'],state=state,error_code=error,
            generated_count=generation and generation['generated_count'],
            tool_invoked=bool(generation and generation['engine_runtime']['tool_invoked']),artifacts_verified=len(final['artifacts']))
        entries.append(row);print(encode(row).decode(),flush=True);return final,value

    def submit(name,body,fault=None):
        write(batch/'requests'/(name+'.json'),body);job=rt.submit_sequence(encode(body),name,policy.TOOL)
        rt._development_fault=fault
        try:rt.dispatch(job['job_id'])
        finally:rt._development_fault=None
        return rt.get(job['job_id'])

    def run(name,body,**kwargs):return finish(name,submit(name,body),**kwargs)

    def structure(name,data,body,reference):
        write(batch/'inputs'/(name+'.structure'),data);write(batch/'inputs'/(name+'.json'),body)
        write(batch/'inputs'/(name+'-provenance.json'),reference)
        job=rt.submit_structure(encode(body),'structure-'+name,data);rt.dispatch(job['job_id'])
        job,_=finish('structure-'+name,job,kind='REAL_STRUCTURE_PARSER')
        return next(r for r in job['artifacts'] if r['role']=='result')

    def reject(name,body):
        write(batch/'rejected-requests'/(name+'.json'),body)
        try:rt.submit_sequence(encode(body),name,policy.TOOL)
        except RuntimeFault as exc:
            row=dict(case=name,state='PASS',error_code=exc.code,diagnostic=str(exc),rejected_before_admission=True)
            guards.append(row);print(encode(row).decode(),flush=True)
        else:raise AssertionError('Invalid N11 request accepted: '+name)

    fixtures={c['name']:c for c in structure_cases()}
    real=fixtures['rsa-out-of-domain'];original=REPO/real['expected']['reference'];original_data=original.read_bytes()
    # Established derivative changes only 28 occupancies and metadata; prove all original ATOM coordinates/order unchanged.
    before=[l for l in original_data.splitlines() if l.startswith(b'ATOM')]
    after=[l for l in real['data'].splitlines() if l.startswith(b'ATOM')]
    assert len(before)==len(after) and all(a[:54]==b[:54] and a[60:]==b[60:] for a,b in zip(before,after))
    ref=structure('1ubq-engineering',real['data'],real['request'],dict(kind='CONTROLLED_COORDINATE_PRESERVING_DERIVATIVE',
        original_path=str(original),original_sha256=sha(original_data),changes=real['expected']['occupancy_changes'],
        coordinates_unchanged=True,scientific_reference=False))
    body=request(real['request']['protein_sequence'],ref,'1UBQ engineering exact coordinates / explicit masks')
    main_job,main_value=run('real-1ubq-default24',body)
    assert main_value['generation']['generated_count']==24
    if args.smoke:
        write(batch/'smoke.json',dict(status='PASS',job=main_job['job_id']));return

    # Same input and seed must reproduce the original sample sequence set in the pinned environment.
    _,repeated=run('same-seed-repeat',body)
    assert main_value['generation']['records']==repeated['generation']['records']
    assert rt.submit_sequence(encode(body),'real-1ubq-default24',policy.TOOL)['job_id']==main_job['job_id']
    reject('invalid-sequence',dict(body,protein_sequence='X'+body['protein_sequence'][1:]))
    try:rt.submit_sequence(encode(dict(body,user_sequence_id='changed')),'real-1ubq-default24',policy.TOOL)
    except RuntimeFault as exc:assert exc.code=='IDEMPOTENCY_CONFLICT';guards.append(dict(case='idempotency-conflict',error_code=exc.code))
    else:raise AssertionError('Changed duplicate accepted')

    small={}
    for name in ('normal-pdb','normal-cif'):
        fixture=fixtures[name];sref=structure(name,fixture['data'],fixture['request'],dict(kind='SYNTHETIC_ENGINEERING_GEOMETRY'))
        small[name]=request(SEQUENCE,sref,name)
        _,value=run(name,small[name])
        assert value['generation']['conversion']['rows'][0]['author_resseq']=='42'
    # Explicit WT-only allowed sets test hard constraints and retention of duplicate/WT records.
    wt_only=copy.deepcopy(small['normal-pdb']);wt_only['constraints'].update(fixed_positions=[1],open_positions=[],
        restricted_positions=[dict(position=p,allowed_residues=SEQUENCE[p-1]) for p in range(2,len(SEQUENCE)+1)])
    _,wt=run('restricted-wt-only-retain24',wt_only)
    assert all(r['is_wt'] and r['duplicate_of_sample']==(None if r['sample_number']==1 else 1) for r in wt['generation']['records'])
    fixed=copy.deepcopy(wt_only);fixed['constraints'].update(fixed_positions=list(range(1,len(SEQUENCE)+1)),restricted_positions=[])
    _,none=run('no-designable-positions',fixed,kind='NATIVE_PARSER_AND_MASK_AUDIT_NO_GENERATION')
    assert none['status']=='not_generated_no_designable_positions' and none['generation']['generated_count']==0

    rows=geometry()
    for row in rows:
        pos=int(row['label_seq_id']);row.update(auth_asym_id='B',label_asym_id='LABEL_B',
            auth_seq_id='100' if pos in (1,2) else str(100+3*(pos-1)),pdbx_PDB_ins_code='A' if pos==2 else '.')
    context=[dict(r,auth_asym_id='A',label_asym_id='LABEL_A',label_comp_id='ALA',auth_comp_id='ALA',
        Cartn_y=str(float(r['Cartn_y'])+30)) for r in rows]
    multi_data=cif(context+rows);multi_meta=metadata(source='unknown',context=['A','B'],selection=dict(model_index=0,chain_selector='B'))
    mref=structure('multichain-insertion',multi_data,multi_meta,dict(kind='SYNTHETIC_ENGINEERING_GEOMETRY',target='B',fixed_chain='A'))
    _,multi=run('multichain-target-b-insertion',request(SEQUENCE,mref,'explicit target B, author100/100A/106'))
    conversion=multi['generation']['conversion'];target_rows=[r for r in conversion['rows'] if r['designed_chain']]
    assert conversion['target_chain']=='B' and conversion['fixed_chains']==['A']
    assert [(r['author_resseq'],r['insertion_code'],r['tool_position']) for r in target_rows[:3]]==[('100','',1),('100','A',2),('106','',3)]

    for name in ('missing-residue','ambiguous-chains'):
        fixture=fixtures[name];badref=structure(name,fixture['data'],fixture['request'],dict(kind='SYNTHETIC_NEGATIVE_STRUCTURE'))
        reject(name,request(SEQUENCE,badref,name))
    for name in ('5L33','6MRR'):
        path=REPO/'discovery/t01-phase1-real/w5/proteinmpnn-assets-20260908'/(name+'.pdb')
        inventory=parse_local(path);sequence=''.join(r['one_letter'] for r in inventory['models'][0]['chains'][0]['residues'] if r['one_letter'])
        sref=structure('original-'+name,path.read_bytes(),metadata(sequence,fmt='PDB',source='unknown',
            source_declaration=dict(kind='unknown',note='UNCHANGED official ProteinMPNN example at '+policy.COMMIT)),
            dict(kind='UNCHANGED_OFFICIAL_LOCAL_EXAMPLE',commit=policy.COMMIT,source='inputs/PDB_monomers/pdbs/'+name+'.pdb',sha256=sha(path.read_bytes())))
        reject('alternate-conformer-'+name,request(sequence,sref,'official original unsupported conformer'))
    for name,changed in [('missing-structure',dict(body,structure_artifact=None)),('sequence-mismatch',dict(body,protein_sequence='A'+body['protein_sequence'][1:]))]:reject(name,changed)
    for name,change in [('out-of-range',lambda c:c['fixed_positions'].append(1001)),('missing-permission',lambda c:c['open_positions'].pop())]:
        changed=copy.deepcopy(body);change(changed['constraints']);reject(name,changed)
    forged=copy.deepcopy(body);forged['structure_artifact']['sha256']='0'*64;reject('forged-source-hash',forged)

    for name,fault,error in [('tool-failure','tool_failure','TOOL_FAILED'),('corrupt-output','corrupt_output','OUTPUT_INVALID')]:
        failed,_=finish(name,submit(name,small['normal-pdb'],fault),'failed',error,'CONTROLLED_FAULT')
        if name=='tool-failure':
            retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=failed['job_id'],idempotency_key='retry')))
            rt.dispatch(retry['job_id']);finish('failure-retry',retry)
    queued=rt.submit_sequence(encode(body),'queued-cancel',policy.TOOL)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=queued['job_id'],idempotency_key='queued-cancel')))
    finish('queued-cancel',queued,'cancelled','CANCELLED','LIFECYCLE_NO_NATIVE_EXECUTION')
    running=submit('running-cancel',small['normal-pdb'],'slow_worker')
    until(lambda:(root/rt.attempt_path(running)/'output/runtime_started.json').is_file())
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=running['job_id'],idempotency_key='running-cancel')))
    finish('running-cancel',running,'cancelled','CANCELLED','CONTROLLED_SLOW_WORKER')
    finish('timeout',submit('timeout',dict(small['normal-pdb'],timeout_seconds=1),'slow_worker'),'timed_out','TIMEOUT','CONTROLLED_SLOW_WORKER')
    for fault in ('crash_after_start','crash_after_receipt'):
        crashed=submit(fault,small['normal-pdb'],fault)
        until(lambda:alive(rt.execution(crashed['job_id']).get('supervisor')) is False)
        rt.recover(crashed['job_id'])
        finish(fault,crashed,'failed' if fault=='crash_after_start' else 'succeeded','INTERRUPTED' if fault=='crash_after_start' else None,'CONTROLLED_SUPERVISOR_CRASH')

    def cli(name,args):
        argv=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),*args]
        process=subprocess.run(argv,capture_output=True,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch/'cli'/(name+'.json'),dict(argv=argv,exit_code=process.returncode,stdout=process.stdout.decode(),stderr=process.stderr.decode()))
        assert process.returncode==0;return decode(process.stdout)
    documented=batch/'requests/documented.json';write(documented,small['normal-pdb'])
    value=cli('documented',['proteinmpnn','--input',str(documented),'--key','documented','--run','--wait','180'])
    documented_job,_=finish('documented',value.get('job',value))
    assert cli('query',['result','--job-id',documented_job['job_id']])['generation']['generated_count']==24

    # Tamper only fresh acceptance copies, after preserving every original artifact in the batch.
    pending=rt.submit_sequence(encode(body),'late-source-tamper',policy.TOOL)
    source_ref=body['structure_artifact']
    with rt._db() as db:row=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(source_ref['artifact_id'],)).fetchone()
    with (root/row['relative_path']).open('ab') as stream:stream.write(b' controlled acceptance tamper')
    rt.dispatch(pending['job_id']);finish('late-source-tamper',pending,'failed','HASH_MISMATCH','CONTROLLED_SOURCE_TAMPER')
    result_ref=next(r for r in documented_job['artifacts'] if r['role']=='result')
    with rt._db() as db:row=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(result_ref['artifact_id'],)).fetchone()
    with (root/row['relative_path']).open('ab') as stream:stream.write(b' controlled acceptance tamper')
    try:rt.result(documented_job['job_id'])
    except RuntimeFault as exc:assert exc.code=='HASH_MISMATCH';guards.append(dict(case='published-artifact-tamper',error_code=exc.code))
    else:raise AssertionError('Tampered result accepted')
    assert profile==policy.registered_profile() and docker.inspect(root,policy.SLOT) is None
    write(batch/'guards.json',guards)
    files=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(batch.rglob('*')) if p.is_file()]
    write(batch/'index.json',dict(status='PASS',completed_at=now(),scope='N11_PROTEINMPNN_LOCAL_ENGINEERING',runtime_root=str(root),
        profile=profile,cases=entries,guards=guards,files=files,scientific_signoff=None,usable_for_pipeline=False,
        automatic_handoff=False,production_status='NOT_DEPLOYED',scientific_gate='NOT_EVALUATED'))
    print('N11_ENGINEERING_ACCEPTANCE_PASS',flush=True)


if __name__=='__main__':main()
