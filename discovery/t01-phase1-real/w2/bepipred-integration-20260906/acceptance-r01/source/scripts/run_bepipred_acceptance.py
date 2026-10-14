"""Reproducible W2 BepiPred local development campaign, never scientific acceptance."""
import argparse
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import decode, encode, now, sha
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.bepipred.policy import TOOL, PACKAGE, SLOT, registered_profile, verify_assets
from t01_phase1_real.winprocess import alive
from run_deeptmhmm_acceptance import write, until

SEQ='MQLRHIGDSVNHRVIQEHLAQEVGDVLAPFVALVFVRGQVLLRFFWNNHLL'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True);p.add_argument('--batch',required=True)
    a=p.parse_args();root=Path(a.root);batch=Path(a.batch).absolute()
    assert root.is_absolute() and not root.exists(),'Use a fresh absolute runtime root'
    assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w2') and not batch.exists(),'Use a fresh W2 batch'
    batch.mkdir(parents=True);rt=Runtime(root);profile=registered_profile();entries=[]
    sources=[p for p in (REPO/'src/t01_phase1_real/development').rglob('*') if p.suffix in ('.py','.json')]
    sources += [REPO/'scripts'/name for name in ['t01_runtime.py','t01_development_supervisor.py','run_bepipred_acceptance.py','run_deeptmhmm_acceptance.py']]
    for path in sources:write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    write(batch/'profile.json',profile);write(batch/'assets-verified.json',verify_assets())
    reference=PACKAGE/'example_antigens/example_antigens.fasta';native=reference.read_bytes()
    pairs={record.splitlines()[0]:''.join(record.splitlines()[1:]) for record in native.decode().split('>') if record}
    example=pairs['4ypg_D']
    write(batch/'reference.json',dict(path=reference.relative_to(REPO).as_posix(),sha256=sha(native),accession='4ypg_D',sequence=example,
        qualification='UPSTREAM_PACKAGE_ASSOCIATED_SAMPLE; not independent scientific holdout',safe51=SEQ,
        synthetic_cases={'short9':'ACDEFGHIK','local-upper1022':'A'*1022}))

    def cli(name,args,expected=0):
        argv=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),*args]
        run=subprocess.run(argv,capture_output=True,timeout=220,creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch/'cli'/(name+'.json'),dict(argv=argv,exit_code=run.returncode,stdout=run.stdout.decode('utf-8'),stderr=run.stderr.decode('utf-8')))
        assert run.returncode==expected,(name,run.returncode,run.stdout[:500],run.stderr)
        return decode(run.stdout)

    def submit(name,seq=SEQ,timeout=180,fault=None):
        body=dict(protein_sequence=seq,user_sequence_id='W2 用户 | ../别名\n'+name,timeout_seconds=timeout)
        write(batch/'requests'/(name+'.json'),body)
        job=cli(name+'-submit',['bepipred','--input',str(batch/'requests'/(name+'.json')),'--key',name])
        rt._development_fault=fault;rt.dispatch(job['job_id']);rt._development_fault=None
        return rt.get(job['job_id'])

    def finish(name,job,state='succeeded',error=None,seq=SEQ,kind='CONTROLLED_LIFECYCLE_VALIDATION'):
        final=rt.wait(job['job_id'],210)
        write(batch/'cases'/name/'job.json',final);write(batch/'cases'/name/'events.json',rt.events(job['job_id']))
        if final['attempt_id']:write(batch/'cases'/name/'execution.json',rt.execution(job['job_id']))
        result=None
        if final['artifacts']:
            result=cli(name+'-query',['result','--job-id',job['job_id']]);write(batch/'cases'/name/'result.json',result)
            assert result['binding']['job_id']==job['job_id'] and not result['usable_for_pipeline'] and not result['automatic_handoff']
            for ref in final['artifacts']:
                raw=rt.artifact_bytes(job['job_id'],ref['artifact_id'])
                assert sha(raw)==ref['sha256'] and len(raw)==ref['size_bytes'];write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
            assert result['postprocessing']['linear_peaks'] is None and result['postprocessing']['linear_scores'] is None
        assert final['state']==state and final['error_code']==error,(name,final['state'],final['error_code'],result and result['execution'])
        assert not final['usable_for_pipeline'] and final['review_required']
        if state=='succeeded':
            assert result['status']=='raw_scores_unreviewed' and len(result['raw_scores'])==len(seq)
            assert ''.join(r['residue'] for r in result['raw_scores'])==seq
            assert [r['sequence_position'] for r in result['raw_scores']]==list(range(1,len(seq)+1))
        elif result:assert result['raw_scores'] is None and result['raw_record'] is None
        if final['attempt_id']:
            assert rt.execution(job['job_id'])['tree_stopped'] and not docker.owned(root,final,docker.inspect(root,SLOT))
        entry=dict(case=name,job_id=final['job_id'],state=state,error_code=error,artifacts_verified=len(final['artifacts']),
            reference_kind=kind,controlled_fault=result.get('controlled_fault') if result else None)
        entries.append(entry);print(encode(entry).decode(),flush=True)
        return final,result

    first_args=['bepipred','--sequence',example,'--user-id','4ypg_D | 原包参考','--key','native-example','--run','--wait','210']
    first=cli('native-example-full',first_args)
    finish('native-example',first['job'],seq=example,kind='UPSTREAM_PACKAGE_ASSOCIATED_SAMPLE')
    assert cli('same-key-duplicate',first_args)==first
    assert cli('same-key-conflict',['bepipred','--sequence',SEQ,'--key','native-example'],20)['error']['code']=='IDEMPOTENCY_CONFLICT'
    entries.append(dict(case='duplicate-and-conflict',state='PASS',same_attempt=True))
    for name,seq in [('short9','ACDEFGHIK'),('local-upper1022','A'*1022)]:
        job=submit(name,seq);finish(name,job,seq=seq,kind='CONTROLLED_ENGINEERING_INPUT')
    for i,seq in enumerate(['A'*8,'A'*1023,'ACDEFGHIK*','ACDEFGHIKX','acdefghik','ACDEFGHIK\n']):
        assert cli('invalid-'+str(i),['bepipred','--sequence',seq,'--key','invalid-'+str(i)],20)['error']['code']=='INVALID_REQUEST'
    entries.append(dict(case='invalid-inputs',state='PASS',rejected_before_admission=6))
    queued=cli('queued-submit',['bepipred','--sequence',SEQ,'--key','queued'])
    cli('queued-cancel',['cancel','--job-id',queued['job_id'],'--key','queued-cancel']);finish('queued-cancel',queued,'cancelled','CANCELLED')
    running=submit('running-cancel');until(lambda:(root/rt.attempt_path(running)/'start.json').is_file())
    cli('running-cancel',['cancel','--job-id',running['job_id'],'--key','running-cancel']);finish('running-cancel',running,'cancelled','CANCELLED')
    timed=submit('timeout',timeout=1);finish('timeout',timed,'timed_out','TIMEOUT')
    failed=submit('tool-failure',fault='tool_failure');finish('tool-failure',failed,'failed','TOOL_FAILED')
    damaged=submit('corrupt-output',fault='corrupt_output');finish('corrupt-output',damaged,'failed','OUTPUT_INVALID')
    live=submit('live-recovery');until(lambda:(root/rt.attempt_path(live)/'start.json').is_file())
    before=rt.get(live['job_id']);recovered=cli('live-recover',['recover','--job-id',live['job_id']])
    assert recovered['execution_identity']==before['execution_identity'] and recovered['lease_epoch']>before['lease_epoch']
    finish('live-recovery',live)
    crashed=submit('crash-after-start',fault='crash_after_start');until(lambda:alive(rt.execution(crashed['job_id']).get('supervisor')) is False)
    cli('crash-recover',['recover','--job-id',crashed['job_id']]);finish('crash-after-start',crashed,'failed','INTERRUPTED')
    retried=cli('explicit-retry',['retry','--job-id',crashed['job_id'],'--key','retry'])
    assert retried['retry_of_job_id']==crashed['job_id'] and retried['request_artifact']==crashed['request_artifact']
    rt.dispatch(retried['job_id']);finish('explicit-retry',retried)
    for name,damage in [('crash-after-receipt',None),('missing-score-output','missing'),('damaged-receipt','receipt')]:
        job=submit(name,fault='crash_after_receipt');until(lambda:alive(rt.execution(job['job_id']).get('supervisor')) is False)
        if damage:
            folder=root/rt.attempt_path(job);target=folder/('receipt.json' if damage=='receipt' else 'output/result/raw_output.csv')
            raw=target.read_bytes();write(batch/'fault-originals'/(name+'.bin'),raw)
            assert target.resolve().is_relative_to(root.resolve())
            if damage=='missing':target.unlink()
            else:target.write_bytes(raw+b' controlled corruption')
            write(batch/'faults'/(name+'.json'),dict(kind='CONTROLLED_POST_RECEIPT_DAMAGE',path=str(target),original_sha256=sha(raw)))
        cli(name+'-recover',['recover','--job-id',job['job_id']])
        _,value=finish(name,job,'failed' if damage else 'succeeded','OUTPUT_INVALID' if damage else None)
        if damage:assert value['execution']['diagnostic'] and any(r['path']=='stdout.txt' for r in value['raw_artifacts'])
    assert profile==registered_profile() and docker.inspect(root,SLOT) is None
    inventory={p.relative_to(batch).as_posix():dict(sha256=sha(p.read_bytes()),size_bytes=p.stat().st_size) for p in batch.rglob('*') if p.is_file()}
    write(batch/'index.json',dict(completed_at=now(),status='PASS',qualification='LOCAL_DEVELOPMENT_ONLY',scientific_signoff=None,
        usable_for_pipeline=False,production_status='NOT_DEPLOYED',runtime_root=str(root),profile=profile,cases=entries,files=inventory))
    print(encode(dict(status='PASS',cases=len(entries),index=str(batch/'index.json'))).decode(),flush=True)


if __name__=='__main__':main()
