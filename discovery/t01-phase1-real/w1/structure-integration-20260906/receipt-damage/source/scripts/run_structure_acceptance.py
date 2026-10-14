"""One reproducible local chain campaign; real originals and controlled fixtures stay distinct."""
import argparse
import copy
from pathlib import Path
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import decode, encode, now, sha
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.structure.policy import registered_profile, verify_assets, SLOT
from t01_phase1_real.winprocess import alive
from structure_integration_cases import write_cases
from run_deeptmhmm_acceptance import write, until


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True);p.add_argument('--batch',required=True)
    p.add_argument('--receipt-damage-only',action='store_true',help='Supplement an existing campaign with post-receipt integrity cases')
    a=p.parse_args();batch=Path(a.batch).absolute();root=Path(a.root)
    assert root.is_absolute() and not root.exists(),'Use a fresh absolute runtime root'
    assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w1') and not batch.exists(),'Use a fresh W1 batch'
    batch.mkdir(parents=True);rt=Runtime(root);profile=registered_profile();entries=[]
    sources=[f for d in ['src/t01_phase1_real/development','src/t01_structure_mapping'] for f in (REPO/d).rglob('*') if f.suffix in ('.py','.json')]
    sources += [REPO/'scripts'/n for n in ['t01_runtime.py','t01_development_supervisor.py','run_structure_acceptance.py','structure_integration_cases.py','run_deeptmhmm_acceptance.py','b1_engineering_cases.py','b1_freesasa_cases.py']]
    for source in sources:write(batch/'source'/source.relative_to(REPO),source.read_bytes())
    write(batch/'profile.json',profile);write(batch/'source-verification.json',verify_assets())
    cases=write_cases(batch/'inputs')

    def cli(name,args,expected=0):
        argv=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),*args]
        result=subprocess.run(argv,capture_output=True,timeout=160,creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch/'cli'/f'{name}.json',dict(argv=argv,exit_code=result.returncode,stdout=result.stdout.decode('utf-8'),stderr=result.stderr.decode('utf-8')))
        assert result.returncode==expected,(name,result.returncode,result.stderr,result.stdout[:500])
        return decode(result.stdout)

    def args(case,key):return ['structure','--structure-file',str(batch/'inputs'/(case+'.structure')),'--input',str(batch/'inputs'/(case+'.json')),'--key',key]

    def submit(name,case='normal-cif',fault=None,timeout=None):
        argv=args(case,name)
        if timeout:
            body=decode((batch/'inputs'/(case+'.json')).read_bytes());body['timeout_seconds']=timeout
            write(batch/'requests'/(name+'.json'),body);argv[argv.index('--input')+1]=str(batch/'requests'/(name+'.json'))
        job=cli(name+'-submit',argv)
        rt._development_fault=fault;rt.dispatch(job['job_id']);rt._development_fault=None
        return rt.get(job['job_id'])

    def finish(name,job,state='succeeded',error=None,expected=None,reference=None):
        final=rt.wait(job['job_id'],120)
        write(batch/'cases'/name/'job.json',final);write(batch/'cases'/name/'events.json',rt.events(job['job_id']))
        if final['attempt_id']:write(batch/'cases'/name/'execution.json',rt.execution(job['job_id']))
        result=None
        if final['artifacts']:
            result=cli(name+'-query',['result','--job-id',job['job_id']]);write(batch/'cases'/name/'result.json',result)
            for ref in final['artifacts']:
                raw=rt.artifact_bytes(job['job_id'],ref['artifact_id'])
                assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256']
                write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
            assert result['binding']['job_id']==job['job_id'] and not result['usable_for_pipeline'] and not result['automatic_handoff']
        assert final['state']==state and final['error_code']==error,(name,final['state'],final['error_code'],result and result.get('execution'))
        assert not final['usable_for_pipeline'] and final['review_required']
        if final['attempt_id']:
            assert rt.execution(job['job_id'])['tree_stopped'] is True
            assert not docker.owned(root,final,docker.inspect(root,SLOT))
        if expected:
            report=result['analysis'];sasa=report['freesasa'];rsa=report['rsa']
            if 'sasa' in expected:assert sasa['status']==expected['sasa'],(name,sasa,report['warnings'])
            if 'rsa' in expected:assert rsa['status']==expected['rsa'],(name,rsa)
            if 'reason' in expected:assert (report.get('error_code') or sasa['error_code'])==expected['reason'],(name,report)
            if 'confidence' in expected:assert report['quality']['quality']['confidence']==expected['confidence']
            if 'missing' in expected:
                assert rsa['missing_positions']==expected['missing']
                assert all(rsa['raw_normalized_ratios'][i-1] is None for i in expected['missing'])
            if 'outlier_position' in expected:
                assert expected['outlier_position'] in [r['sequence_position'] for r in rsa['out_of_domain']]
                assert rsa['development_result'] is None and rsa['normal_rsa_result'] is None
        entry=dict(case=name,job_id=final['job_id'],state=final['state'],error_code=final['error_code'],artifacts_verified=len(final['artifacts']),
            reference_kind=reference or 'CONTROLLED_LIFECYCLE_VALIDATION',controlled_fault=result.get('controlled_fault') if result else None)
        entries.append(entry);print(encode(entry).decode(),flush=True)
        return final,result

    def damage_cases():
        for damage in ['missing-output','damaged-output','damaged-receipt']:
            job=submit(damage,fault='crash_after_receipt')
            until(lambda:alive(rt.execution(job['job_id']).get('supervisor')) is False)
            folder=root/rt.attempt_path(job)
            target=folder/('receipt.json' if damage=='damaged-receipt' else 'output/result/raw_areas.json')
            raw=target.read_bytes();write(batch/'fault-originals'/(damage+'.bin'),raw)
            if damage=='missing-output':
                # Single verified file inside this fresh task workspace; preserve bytes above.
                assert target.resolve().is_relative_to(root.resolve())
                target.unlink()
            else:target.write_bytes(raw+b' controlled corruption')
            write(batch/'faults'/(damage+'.json'),dict(kind='CONTROLLED_POST_RECEIPT_DAMAGE',job_id=job['job_id'],path=str(target),original_sha256=sha(raw)))
            cli(damage+'-recover',['recover','--job-id',job['job_id']])
            _,value=finish(damage,job,'failed','OUTPUT_INVALID')
            assert value['analysis'] is None and value['execution']['diagnostic']
            assert any(r['path']=='stdout.txt' for r in value['raw_artifacts']),'Readable original diagnostics were discarded'

    def seal():
        assert docker.inspect(root,SLOT) is None and profile==registered_profile(),'Container left behind or code changed during acceptance'
        inventory={p.relative_to(batch).as_posix():dict(sha256=sha(p.read_bytes()),size_bytes=p.stat().st_size) for p in batch.rglob('*') if p.is_file()}
        write(batch/'index.json',dict(completed_at=now(),status='PASS',qualification='LOCAL_DEVELOPMENT_ONLY',scientific_signoff=None,
            usable_for_pipeline=False,production_status='NOT_DEPLOYED',runtime_root=str(root),profile=profile,cases=entries,files=inventory))
        print(encode(dict(status='PASS',cases=len(entries),index=str(batch/'index.json'))).decode(),flush=True)

    if a.receipt_damage_only:
        damage_cases();seal();return
    for case in cases:
        name=case['name'];expected=case['expected']
        full=cli(name+'-full',args(name,name)+['--run','--wait','120'])
        finish(name,full['job'],expected.get('job','succeeded'),'INVALID_REQUEST' if expected.get('job')=='failed' else None,expected,case['reference_kind'])
        if name=='normal-cif':first=full
    duplicate=cli('duplicate',args('normal-cif','normal-cif')+['--run','--wait','120']);assert duplicate==first
    conflict=cli('duplicate-conflict',args('normal-pdb','normal-cif'),20);assert conflict['error']['code']=='IDEMPOTENCY_CONFLICT'
    entries.append(dict(case='duplicate-and-conflict',state='PASS',same_attempt=True))
    for i,changes in enumerate([dict(protein_sequence='ACDEFGHIK*'),dict(host_species=''),dict(context_chain_ids=[]),dict(timeout_seconds=True)]):
        bad=decode((batch/'inputs/normal-cif.json').read_bytes());bad.update(changes);write(batch/'requests'/f'invalid-{i}.json',bad)
        argv=args('normal-cif','invalid-'+str(i));argv[argv.index('--input')+1]=str(batch/'requests'/f'invalid-{i}.json')
        assert cli('invalid-'+str(i),argv,20)['error']['code']=='INVALID_REQUEST'
    entries.append(dict(case='invalid-metadata',state='PASS',rejected_before_task_creation=4))
    queued=cli('queued-submit',args('normal-cif','queued'))
    cli('queued-cancel',['cancel','--job-id',queued['job_id'],'--key','queued-cancel']);finish('queued-cancel',queued,'cancelled','CANCELLED')
    running=submit('running-cancel',case='rsa-out-of-domain')
    until(lambda:(root/rt.attempt_path(running)/'start.json').is_file())
    cli('running-cancel',['cancel','--job-id',running['job_id'],'--key','running-cancel']);finish('running-cancel',running,'cancelled','CANCELLED')
    timed=submit('timeout',case='rsa-out-of-domain',timeout=1);finish('timeout',timed,'timed_out','TIMEOUT')
    failed=submit('tool-failure',fault='tool_failure');finish('tool-failure',failed,'failed','TOOL_FAILED')
    corrupt=submit('corrupt-output',fault='corrupt_output');finish('corrupt-output',corrupt,'failed','OUTPUT_INVALID')
    live=submit('live-recovery',case='rsa-out-of-domain')
    until(lambda:(root/rt.attempt_path(live)/'start.json').is_file())
    before=rt.get(live['job_id']);recovered=cli('live-recover',['recover','--job-id',live['job_id']])
    assert recovered['execution_identity']==before['execution_identity'] and recovered['lease_epoch']>before['lease_epoch']
    finish('live-recovery',live)
    crashed=submit('crash-after-start',fault='crash_after_start')
    until(lambda:alive(rt.execution(crashed['job_id']).get('supervisor')) is False)
    cli('crash-recover',['recover','--job-id',crashed['job_id']]);crashed,_=finish('crash-after-start',crashed,'failed','INTERRUPTED')
    retried=cli('retry',['retry','--job-id',crashed['job_id'],'--key','retry'])
    assert retried['retry_of_job_id']==crashed['job_id'] and retried['request_artifact']==crashed['request_artifact']
    rt.dispatch(retried['job_id']);finish('explicit-retry',retried)
    receipt=submit('crash-after-receipt',fault='crash_after_receipt')
    until(lambda:alive(rt.execution(receipt['job_id']).get('supervisor')) is False)
    cli('receipt-recover',['recover','--job-id',receipt['job_id']]);finish('crash-after-receipt',receipt)
    damage_cases();seal()


if __name__=='__main__':main()
