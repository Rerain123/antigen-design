"""Fresh N11 to N12 offline GPU integration with baseline provenance and lifecycle."""
import argparse
import copy
from pathlib import Path
import subprocess
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import RuntimeFault,decode,encode,sha,now
from t01_phase1_real.development import Runtime,docker
from t01_phase1_real.development.esm_if1 import policy
from t01_phase1_real.development.esm_if1.rules import evaluate
from t01_phase1_real.development.proteinmpnn import policy as mpnn
from t01_phase1_real.winprocess import alive
from run_deeptmhmm_acceptance import until
from run_proteinmpnn_acceptance import write,request as mpnn_request
from structure_integration_cases import cases,geometry,cif,metadata,SEQUENCE


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True);parser.add_argument('--batch',required=True)
    parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    root=Path(args.root).absolute();batch=Path(args.batch).absolute()
    assert root.is_relative_to(REPO/'var/t01-phase1-real') and not root.exists()
    assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w5') and not batch.exists()
    batch.mkdir(parents=True);rt=Runtime(root);entries=[];guards=[];profile=policy.registered_profile()
    write(batch/'profile.json',profile);write(batch/'rules.json',policy.registered_rules());write(batch/'assets.json',policy.verify_assets())
    paths=[*policy.HERE.glob('*.py'),*policy.HERE.glob('*.json'),*mpnn.HERE.glob('*.py'),*mpnn.HERE.glob('*.json'),
        *[policy.HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py','docker.py','supervisor.py')],
        *list((REPO/'src/t01_structure_mapping').glob('*.py')),Path(__file__),REPO/'requirements/esm_if1.Dockerfile']
    for path in paths:write(batch/'source'/path.relative_to(REPO),path.read_bytes())

    def finish(name,job,state='succeeded',error=None,kind='REAL_OFFLINE_TOOL'):
        final=rt.wait(job['job_id'],900);value=rt.result(job['job_id']) if final['artifacts'] else None
        write(batch/'cases'/name/'job.json',final);write(batch/'cases'/name/'events.json',rt.events(job['job_id']))
        if final['attempt_id']:write(batch/'cases'/name/'execution.json',rt.execution(job['job_id']))
        if value:write(batch/'cases'/name/'result.json',value)
        for ref in final['artifacts']:
            raw=rt.artifact_bytes(final['job_id'],ref['artifact_id']);assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256']
            write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
        assert final['state']==state and final['error_code']==error,(name,final['state'],final['error_code'],value and value['execution'])
        if value:
            assert value['scientific_signoff'] is None and not value['usable_for_pipeline'] and not value['automatic_handoff']
            if final['tool_id']==policy.TOOL:
                assert value['validation'] is None and value['formal_candidates'] is None and value['structure_recheck']['status']=='NOT_EXECUTED'
        if final['attempt_id']:assert rt.execution(final['job_id'])['tree_stopped']
        runtime=None
        if value and final['tool_id']==policy.TOOL:
            ref=next((r['artifact'] for r in value['raw_artifacts'] if r['path']=='output/runtime.json'),None)
            if ref:runtime=decode(rt.artifact_bytes(final['job_id'],ref['artifact_id']))
        row=dict(case=name,kind=kind,job_id=final['job_id'],tool_id=final['tool_id'],state=state,error_code=error,
            artifacts_verified=len(final['artifacts']),baseline_model_calls=runtime and runtime['baseline_model_calls'],
            variant_model_calls=runtime and runtime['variant_model_calls'])
        entries.append(row);print(encode(row).decode(),flush=True);return final,value

    def submit(name,body,tool=policy.TOOL,fault=None):
        write(batch/'requests'/(name+'.json'),body);job=rt.submit_sequence(encode(body),name,tool);rt._development_fault=fault
        try:rt.dispatch(job['job_id'])
        finally:rt._development_fault=None
        return rt.get(job['job_id'])

    def run(name,body,**kwargs):return finish(name,submit(name,body),**kwargs)
    def ref(job):return next(r for r in job['artifacts'] if r['role']=='result')
    def structure(name,data,body,provenance):
        write(batch/'inputs'/(name+'.structure'),data);write(batch/'inputs'/(name+'.json'),body);write(batch/'inputs'/(name+'-provenance.json'),provenance)
        job=rt.submit_structure(encode(body),name,data);rt.dispatch(job['job_id']);return finish(name,job)[0]
    def reject(name,body):
        write(batch/'rejected-requests'/(name+'.json'),body)
        try:rt.submit_sequence(encode(body),name,policy.TOOL)
        except RuntimeFault as exc:
            guards.append(dict(case=name,code=exc.code,diagnostic=str(exc),kind='REQUEST_OR_SOURCE_GUARD'));print(name,exc.code,flush=True)
        else:raise AssertionError('Invalid N12 accepted: '+name)
    def body_for(n11job,sequence,structure_ref,selection=None,baseline=None):
        return dict(protein_sequence=sequence,user_sequence_id='N12 explicit engineering verification',structure_artifact=structure_ref,
            n11_artifact=ref(n11job),sample_numbers=selection if selection is not None else list(range(1,25)),baseline_artifact=baseline,timeout_seconds=180)

    original=next(c for c in cases() if c['name']=='rsa-out-of-domain')
    parent=REPO/original['expected']['reference'];data=parent.read_bytes()
    before=[l for l in data.splitlines() if l.startswith(b'ATOM')];after=[l for l in original['data'].splitlines() if l.startswith(b'ATOM')]
    assert len(before)==len(after) and all(a[:54]==b[:54] and a[60:]==b[60:] for a,b in zip(before,after))
    sj=structure('structure-real-1ubq',original['data'],original['request'],dict(kind='CONTROLLED_COORDINATE_PRESERVING_DERIVATIVE',
        source=str(parent),source_sha256=sha(data),occupancy_changes=original['expected']['occupancy_changes'],coordinates_unchanged=True))
    seq=original['request']['protein_sequence'];n11body=mpnn_request(seq,ref(sj),'N12 engineering source 1UBQ')
    n11,_=finish('n11-real24',submit('n11-real24',n11body,mpnn.TOOL))
    body=body_for(n11,seq,ref(sj));main_job,main_value=run('native-baseline-and24',body)
    assert main_value['baseline'] is not None and main_value['scoring']['baseline_status']=='computed_once'
    assert len(main_value['scoring']['records'])==24
    if args.smoke:
        write(batch/'smoke.json',dict(status='PASS',job_id=main_job['job_id']));return
    reuse=dict(body,baseline_artifact=ref(main_job),sample_numbers=[2,5,1])
    reuse_job,reused=run('cross-call-baseline-reuse',reuse)
    assert reused['baseline']==main_value['baseline'] and reused['scoring']['baseline_status']=='verified_reuse'
    for r in reused['scoring']['records']:
        old=next(v for v in main_value['scoring']['records'] if v['sample_number']==r['sample_number'])
        assert abs(old['score']-r['score'])<2e-6
    _,empty=run('empty-selection',dict(body,sample_numbers=[]))
    assert empty['status']=='not_scored_empty_selection' and empty['baseline'] is None
    assert rt.submit_sequence(encode(body),'native-baseline-and24',policy.TOOL)['job_id']==main_job['job_id']
    try:rt.submit_sequence(encode(dict(body,user_sequence_id='changed')),'native-baseline-and24',policy.TOOL)
    except RuntimeFault as exc:assert exc.code=='IDEMPOTENCY_CONFLICT';guards.append(dict(case='changed-duplicate',code=exc.code))
    else:raise AssertionError('Idempotency conflict not rejected')

    for name,fault,error,state in [('partial-variant-failure','first_variant_failure',None,'succeeded'),
        ('all-variants-failure','all_variants_failure','TOOL_FAILED','failed'),('tool-failure','tool_failure','TOOL_FAILED','failed'),
        ('corrupt-output','corrupt_output','OUTPUT_INVALID','failed')]:
        job,value=finish(name,submit(name,dict(reuse,sample_numbers=[1,2,3]),fault=fault),state,error,'CONTROLLED_FAULT')
        if name=='partial-variant-failure':
            assert value['scoring']['records'][0]['score'] is None and value['engineering_rules']['relaxation_history']==[]
            assert sum(r['score'] is not None for r in value['scoring']['records'])==2
        if name=='tool-failure':
            retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=job['job_id'],idempotency_key='tool-retry')))
            rt.dispatch(retry['job_id']);finish('tool-retry',retry)
    queued=rt.submit_sequence(encode(reuse),'queued-cancel',policy.TOOL)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=queued['job_id'],idempotency_key='queued-cancel')))
    finish('queued-cancel',queued,'cancelled','CANCELLED','LIFECYCLE')
    running=submit('running-cancel',reuse,fault='slow_worker')
    until(lambda:(root/rt.attempt_path(running)/'output/runtime_started.json').is_file())
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=running['job_id'],idempotency_key='running-cancel')))
    finish('running-cancel',running,'cancelled','CANCELLED','CONTROLLED_SLOW_WORKER')
    finish('timeout',submit('timeout',dict(reuse,timeout_seconds=1),fault='slow_worker'),'timed_out','TIMEOUT','CONTROLLED_SLOW_WORKER')
    for fault in ('crash_after_start','crash_after_receipt'):
        job=submit(fault,reuse,fault=fault);until(lambda:alive(rt.execution(job['job_id']).get('supervisor')) is False)
        rt.recover(job['job_id'])
        finish(fault,job,'failed' if fault=='crash_after_start' else 'succeeded','INTERRUPTED' if fault=='crash_after_start' else None,'CONTROLLED_SUPERVISOR_CRASH')

    # Real multi-chain context and nonconsecutive/iCode numbering, explicitly engineered.
    rows=geometry()
    for row in rows:
        pos=int(row['label_seq_id']);row.update(auth_asym_id='B',label_asym_id='LABEL_B',auth_seq_id='100' if pos<=2 else str(100+pos*3),pdbx_PDB_ins_code='A' if pos==2 else '.')
    context=[dict(r,auth_asym_id='A',label_asym_id='LABEL_A',auth_comp_id='ALA',label_comp_id='ALA',Cartn_y=str(float(r['Cartn_y'])+30)) for r in rows]
    ms=structure('structure-multichain',cif(context+rows),metadata(source='unknown',context=['A','B'],selection=dict(model_index=0,chain_selector='B')),
        dict(kind='SYNTHETIC_MULTICHAIN_GEOMETRY',target='B'))
    mb=mpnn_request(SEQUENCE,ref(ms),'N12 multi-chain WT-only engineering');mb['constraints'].update(fixed_positions=[1],open_positions=[],
        restricted_positions=[dict(position=p,allowed_residues=SEQUENCE[p-1]) for p in range(2,len(SEQUENCE)+1)])
    mj,_=finish('n11-multichain-wt-only',submit('n11-multichain-wt-only',mb,mpnn.TOOL))
    multi=body_for(mj,SEQUENCE,ref(ms),[1,2]);_,mv=run('multichain-wt-identical',multi)
    assert all(abs(r['delta_pct'])<.001 for r in mv['engineering_rules']['records'])
    reject('wrong-baseline-structure',dict(multi,baseline_artifact=ref(main_job)))
    reject('wrong-explicit-structure',dict(body,structure_artifact=ref(ms)))
    reject('float-baseline',dict(body,baseline_artifact=-2.0))
    reject('wrong-wt',dict(body,protein_sequence='A'+seq[1:]))
    reject('sample-outside-set',dict(body,sample_numbers=[25]))
    reject('duplicate-selection',dict(body,sample_numbers=[1,1]))
    reject('caller-model-override',dict(body,model='different'))
    forged=copy.deepcopy(reuse);forged['baseline_artifact']['sha256']='0'*64;reject('forged-baseline',forged)

    # Numeric engineering rule fixtures: never attributed to naturally observed model distribution.
    numeric=[]
    for name,scores in [('negative-worse',[-2.5]),('negative-better',[-1.9]),('boundary10',[-2.2]),
        ('relaxed15',[-2.3]),('minimal20',[-2.36]),('boundary20',[-2.4]),('all-excluded',[-2.4001])]:
        numeric.append(dict(case=name,kind='DETERMINISTIC_RULE_FIXTURE',result=evaluate(-2.0,[dict(sample_number=i+1,score=s,error_code=None) for i,s in enumerate(scores)])))
    assert numeric[4]['result']['quality_flag']=='minimal' and numeric[-1]['result']['failure_report']
    write(batch/'numeric-rule-fixtures.json',numeric)
    documented=batch/'requests/documented.json';write(documented,dict(reuse,sample_numbers=[1]))
    def cli(name,parameters):
        argv=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),*parameters]
        p=subprocess.run(argv,capture_output=True,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch/'cli'/(name+'.json'),dict(argv=argv,exit_code=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode()))
        assert p.returncode==0;return decode(p.stdout)
    out=cli('documented',['esm-if1','--input',str(documented),'--key','documented','--run','--wait','180'])
    dj,_=finish('documented',out.get('job',out));assert cli('query',['result','--job-id',dj['job_id']])['baseline']==main_value['baseline']

    # Damage only fresh acceptance root copies after preserving all published bytes in batch.
    pending=rt.submit_sequence(encode(body),'late-n11-tamper',policy.TOOL)
    with rt._db() as db:path=root/db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref(n11)['artifact_id'],)).fetchone()[0]
    with path.open('ab') as stream:stream.write(b' controlled N11 source damage')
    rt.dispatch(pending['job_id']);finish('late-n11-tamper',pending,'failed','HASH_MISMATCH','CONTROLLED_SOURCE_TAMPER')
    with rt._db() as db:path=root/db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref(dj)['artifact_id'],)).fetchone()[0]
    with path.open('ab') as stream:stream.write(b' controlled publication damage')
    try:rt.result(dj['job_id'])
    except RuntimeFault as exc:assert exc.code=='HASH_MISMATCH';guards.append(dict(case='published-result-tamper',code=exc.code))
    else:raise AssertionError('Published tamper accepted')
    assert profile==policy.registered_profile() and docker.inspect(root,policy.SLOT) is None
    write(batch/'guards.json',guards)
    inventory=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(batch.rglob('*')) if p.is_file()]
    write(batch/'index.json',dict(status='PASS',completed_at=now(),scope='N12_ESM_IF1_INDEPENDENT_ENGINEERING',runtime_root=str(root),
        profile=profile,cases=entries,guards=guards,files=inventory,scientific_signoff=None,usable_for_pipeline=False,
        automatic_handoff=False,production_status='NOT_DEPLOYED',complete_n12=False,scientific_gate='NOT_EVALUATED'))
    print('N12_ESM_IF1_ENGINEERING_PASS',flush=True)


if __name__=='__main__':main()
