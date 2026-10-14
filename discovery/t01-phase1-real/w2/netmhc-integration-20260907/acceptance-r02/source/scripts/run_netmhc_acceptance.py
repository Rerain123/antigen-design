"""Reproducible W2 NetMHC local-development campaign; never scientific acceptance."""
import argparse
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import decode, encode, now, sha
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.netmhc.policy import PACKAGE, SLOT, registered_profile, verify_assets
from t01_phase1_real.winprocess import alive
from run_deeptmhmm_acceptance import write as original_write, until

SEQ='MRYGFVRKKHRGLFLTTVAALPIWNPISEFVKWYKSHKLSQHCIRICGHLCQKHLDMFLSVIGQRWPIDVFSSVFDHQVSAIGSDIIWWFLKLFLVSFFFFF'
I_ALLELE='HLA-A02:01'
II_ALLELE='HLA-DPA10202-DPB11901'


def write(path,value):
    raw=value if isinstance(value,bytes) else encode(value)
    if path.exists():
        assert path.read_bytes()==raw,'Cannot rewrite existing evidence: '+str(path)
        return
    original_write(path,raw)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--batch',required=True)
    args=parser.parse_args();root=Path(args.root);batch=Path(args.batch).absolute()
    assert root.is_absolute() and not root.exists(),'Use a fresh absolute runtime root'
    assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w2') and not batch.exists(),'Use a fresh W2 batch'
    batch.mkdir(parents=True);runtime=Runtime(root);profile=registered_profile();entries=[]

    source_paths=list((REPO/'src/t01_phase1_real/development/netmhc').glob('*'))
    source_paths += [REPO/'src/t01_phase1_real/development'/name for name in
        ['docker.py','supervisor.py','runtime.py','registry.py','contracts.py','cli.py']]
    source_paths += [REPO/'scripts'/name for name in
        ['t01_runtime.py','t01_development_supervisor.py','run_netmhc_acceptance.py','run_deeptmhmm_acceptance.py']]
    source_paths += [REPO/'tests/test_netmhc_development.py']
    for path in source_paths:
        if path.is_file():write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    receipt=verify_assets()
    for item in receipt['original_archives']:
        raw=(PACKAGE/item['path']).read_bytes()
        assert len(raw)==item['bytes'] and sha(raw)==item['sha256']
    image=docker.call(root,['image','inspect','--format','{{.Id}} {{.Architecture}} {{.Os}}',receipt['image_id']])
    assert image.returncode==0 and image.stdout.decode().strip()==receipt['image_id']+' amd64 linux'
    write(batch/'profile.json',profile);write(batch/'assets-verified.json',receipt)
    write(batch/'environment.json',dict(image_inspect=image.stdout.decode().strip(),archive_hashes_verified=True,
        inference_network='none',qualification='LOCAL_ACADEMIC_DEVELOPMENT_ONLY'))

    def cli(name,values,expected=0):
        argv=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),*values]
        run=subprocess.run(argv,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch/'cli'/(name+'.json'),dict(argv=argv,exit_code=run.returncode,
            stdout=run.stdout.decode('utf-8'),stderr=run.stderr.decode('utf-8')))
        assert run.returncode==expected,(name,run.returncode,run.stdout[:500],run.stderr[:500])
        return decode(run.stdout)

    def submit(name,timeout=180,fault=None):
        body=dict(protein_sequence=SEQ,user_sequence_id='W2 NetMHC | 用户别名 ../ '+name,
            host_species='Homo sapiens',mhc_i_alleles=[I_ALLELE],mhc_ii_alleles=[II_ALLELE],
            timeout_seconds=timeout)
        request=batch/'requests'/(name+'.json');write(request,body)
        job=cli(name+'-submit',['netmhc','--input',str(request),'--key',name])
        runtime._development_fault=fault
        try:runtime.dispatch(job['job_id'])
        finally:runtime._development_fault=None
        return job

    def finish(name,job,state='succeeded',error=None,status=None):
        final=runtime.wait(job['job_id'],180)
        write(batch/'cases'/name/'job.json',final);write(batch/'cases'/name/'events.json',runtime.events(job['job_id']))
        if final['attempt_id']:write(batch/'cases'/name/'execution.json',runtime.execution(job['job_id']))
        value=runtime.result(job['job_id']) if final['artifacts'] else None
        if value:write(batch/'cases'/name/'result.json',value)
        for ref in final['artifacts']:
            raw=runtime.artifact_bytes(job['job_id'],ref['artifact_id'])
            assert sha(raw)==ref['sha256'] and len(raw)==ref['size_bytes']
            write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
        assert final['state']==state and final['error_code']==error,(name,final['state'],final['error_code'])
        assert not final['usable_for_pipeline'] and final['review_required']
        if value:
            assert value['binding']['job_id']==job['job_id'] and not value['usable_for_pipeline']
            assert not value['automatic_handoff'] and value['production_status']=='NOT_DEPLOYED'
            if status:assert value['status']==status,(name,value['status'])
        if final['attempt_id']:
            assert runtime.execution(job['job_id'])['tree_stopped']
            assert not docker.owned(root,final,docker.inspect(root,SLOT))
        entry=dict(case=name,job_id=final['job_id'],state=state,error_code=error,
            result_status=value and value['status'],controlled_fault=value and value.get('controlled_fault'),
            artifacts_verified=len(final['artifacts']))
        entries.append(entry);print(encode(entry).decode(),flush=True)
        return final,value

    normal=submit('normal');normal_final,normal_result=finish('normal',normal,status='raw_predictions_unreviewed')
    assert normal_result['channels']['mhc_i']['observed_rows']==644
    assert len(normal_result['channels']['mhc_i']['hits'])==644
    assert normal_result['channels']['mhc_ii']['observed_rows']==88
    assert len(normal_result['channels']['mhc_ii']['hits'])+normal_result['channels']['mhc_ii']['skipped_inverted_rows']==88
    assert all(hit['end']==hit['start']+len(hit['peptide_seq'])-1 for channel in normal_result['channels'].values() for hit in channel['hits'])
    duplicate=cli('duplicate',['netmhc','--input',str(batch/'requests/normal.json'),'--key','normal'])
    duplicate_job=duplicate.get('job',duplicate)
    assert duplicate_job['job_id']==normal['job_id'] and duplicate_job['attempt_id']==normal_final['attempt_id']
    changed=dict(decode((batch/'requests/normal.json').read_bytes()));changed['user_sequence_id']='changed'
    write(batch/'requests/conflict.json',changed)
    assert cli('conflict',['netmhc','--input',str(batch/'requests/conflict.json'),'--key','normal'],20)['error']['code']=='IDEMPOTENCY_CONFLICT'
    entries.append(dict(case='duplicate-and-conflict',state='PASS',same_attempt=True))

    invalid=dict(changed);invalid['user_sequence_id']='invalid';invalid['mhc_i_alleles']=['HLA-NOT-REAL']
    write(batch/'requests/invalid-allele.json',invalid)
    assert cli('invalid-allele',['netmhc','--input',str(batch/'requests/invalid-allele.json'),'--key','invalid'],20)['error']['code']=='INVALID_REQUEST'
    entries.append(dict(case='invalid-allele',state='PASS',rejected_before_admission=True))

    _,partial=finish('mhc-i-unavailable',submit('mhc-i-unavailable',fault='mhc_i_failure'),status='partial_unreliable')
    assert partial['channels']['mhc_i']['status']=='unavailable' and partial['channels']['mhc_ii']['status']=='parsed_unreviewed'
    _,corrupt=finish('corrupt-output',submit('corrupt-output',fault='corrupt_output'),status='partial_unreliable')
    assert corrupt['channels']['mhc_i']['status']=='unavailable' and corrupt['channels']['mhc_ii']['status']=='parsed_unreviewed'
    _,unavailable=finish('both-unavailable',submit('both-unavailable',fault='both_channels_failure'),status='unreliable')
    assert all(channel['status']=='unavailable' for channel in unavailable['channels'].values())
    finish('tool-failure',submit('tool-failure',fault='tool_failure'),'failed','TOOL_FAILED','unreliable')

    queued_body=batch/'requests/queued-cancel.json'
    write(queued_body,dict(protein_sequence=SEQ,user_sequence_id='queued',host_species='Homo sapiens',
        mhc_i_alleles=[I_ALLELE],mhc_ii_alleles=[II_ALLELE],timeout_seconds=180))
    queued=cli('queued-submit',['netmhc','--input',str(queued_body),'--key','queued'])
    cli('queued-cancel',['cancel','--job-id',queued['job_id'],'--key','queued-cancel'])
    finish('queued-cancel',queued,'cancelled','CANCELLED')
    running=submit('running-cancel');until(lambda:(root/runtime.attempt_path(running)/'start.json').is_file())
    cli('running-cancel',['cancel','--job-id',running['job_id'],'--key','running-cancel'])
    finish('running-cancel',running,'cancelled','CANCELLED','unreliable')
    finish('timeout',submit('timeout',timeout=1),'timed_out','TIMEOUT','unreliable')

    crashed=submit('crash-after-start',fault='crash_after_start')
    until(lambda:alive(runtime.execution(crashed['job_id']).get('supervisor')) is False)
    cli('crash-recover',['recover','--job-id',crashed['job_id']])
    failed,_=finish('crash-after-start',crashed,'failed','INTERRUPTED','unreliable')
    retried=cli('retry',['retry','--job-id',failed['job_id'],'--key','retry'])
    assert retried['retry_of_job_id']==failed['job_id'] and retried['request_artifact']==failed['request_artifact']
    runtime.dispatch(retried['job_id']);finish('explicit-retry',retried,status='raw_predictions_unreviewed')

    assert profile==registered_profile() and docker.inspect(root,SLOT) is None
    inventory={path.relative_to(batch).as_posix():dict(sha256=sha(path.read_bytes()),size_bytes=path.stat().st_size)
        for path in batch.rglob('*') if path.is_file()}
    write(batch/'index.json',dict(completed_at=now(),status='PASS',qualification='LOCAL_DEVELOPMENT_ONLY',
        scientific_signoff=None,usable_for_pipeline=False,production_status='NOT_DEPLOYED',runtime_root=str(root),
        profile=profile,cases=entries,files=inventory))
    print(encode(dict(status='PASS',cases=len(entries),index=str(batch/'index.json'))).decode(),flush=True)


if __name__=='__main__':main()
