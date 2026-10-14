"""Execute bounded local integration cases through the current entry/runtime, never scientific acceptance."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import TERMINAL, RuntimeFault, decode, encode, now, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development import docker
from t01_phase1_real.development.policy import registered_profile, sequence_id
from t01_phase1_real.development.raw_format import fasta
from t01_phase1_real.files import within
from t01_phase1_real.winprocess import alive

SEQ='MQLRHIGDSVNHRVIQEHLAQEVGDVLAPFVALVFVRGQVLLRFFWNNHLL'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(value if isinstance(value,bytes) else encode(value))


def until(predicate,seconds=120):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        value=predicate()
        if value:return value
        time.sleep(.1)
    raise AssertionError('Expected lifecycle observation did not arrive')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True);p.add_argument('--batch',required=True)
    a=p.parse_args();batch=Path(a.batch).absolute()
    assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w1') and not batch.exists(),'Use a fresh evidence batch within current W1 discovery'
    batch.mkdir(parents=True)
    rt=Runtime(a.root);profile=registered_profile();entries=[]
    sources=list((REPO/'src/t01_phase1_real/development').glob('*.py'))+list((REPO/'src/t01_phase1_real/development').glob('*.json'))
    sources += [REPO/'scripts'/n for n in ['t01_runtime.py','t01_development_supervisor.py','run_deeptmhmm_acceptance.py']]
    for source in sources:write(batch/'source'/source.relative_to(REPO),source.read_bytes())
    write(batch/'profile.json',profile)
    coverage=REPO/'discovery/t01-phase1-real/w1/deeptmhmm-academic-20260905/inputs/coverage.fasta'
    pb=fasta(coverage.read_text())['Q9HVD1|BETA']
    write(batch/'references.json',dict(qualification='DEVELOPMENT_ONLY; package-associated references, not independent scientific holdout',
        coverage_path=coverage.relative_to(REPO).as_posix(),coverage_sha256=sha(coverage.read_bytes()),sequences={'safe51':SEQ,'pb173':pb}))

    def cli(name,args,expected=0):
        argv=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(rt.root),*args]
        result=subprocess.run(argv,capture_output=True,timeout=160,creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch/'cli'/f'{name}.json',dict(argv=argv,exit_code=result.returncode,stdout=result.stdout.decode('utf-8'),stderr=result.stderr.decode('utf-8')))
        assert result.returncode==expected,(name,result.returncode,result.stderr,result.stdout[:500])
        return decode(result.stdout)

    def submit(name,seq=SEQ,timeout=900,fault=None):
        raw=encode(dict(protein_sequence=seq,user_sequence_id='开发 | ../用户\n'+name,timeout_seconds=timeout))
        write(batch/'requests'/f'{name}.json',raw)
        job=cli(name+'-submit',['deeptmhmm','--input',str(batch/'requests'/f'{name}.json'),'--key',name])
        rt._development_fault=fault
        rt.dispatch(job['job_id']);rt._development_fault=None
        return rt.get(job['job_id'])

    def control(job,op,key):return cli(key,[op,'--job-id',job['job_id'],'--key',key])

    def finish(name,job,expected,error=None,check=None):
        final=rt.wait(job['job_id'],120)
        write(batch/'cases'/name/'job.json',final)
        write(batch/'cases'/name/'events.json',rt.events(job['job_id']))
        if final['attempt_id']:write(batch/'cases'/name/'execution.json',rt.execution(job['job_id']))
        assert final['state']==expected,(name,final['state'],final['error_code'])
        assert final['error_code']==error,(name,final['error_code'])
        assert final['usable_for_pipeline'] is False and final['review_required']
        result=None
        if final['artifacts']:
            result=cli(name+'-query',['result','--job-id',job['job_id']])
            write(batch/'cases'/name/'result.json',result)
            assert result['binding']['job_id']==job['job_id'] and not result['automatic_handoff'] and not result['usable_for_pipeline']
            for ref in final['artifacts']:
                raw=rt.artifact_bytes(job['job_id'],ref['artifact_id'])
                assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256']
                write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
        if final['attempt_id']:
            assert rt.execution(job['job_id'])['tree_stopped'] is True
            assert not docker.owned(rt.root,final,docker.inspect(rt.root))
        if check:check(final,result)
        entry=dict(case=name,job_id=job['job_id'],state=final['state'],error_code=final['error_code'],artifacts_verified=len(final['artifacts']),
            result_status=result['status'] if result else None,controlled_fault=result.get('controlled_fault') if result else None)
        entries.append(entry);print(encode(entry).decode(),flush=True)
        return final,result

    # A full command returns both the task and the parsed/queryable result.
    first=cli('safe-full-command',['deeptmhmm','--sequence',SEQ,'--user-id','安全 ID | ../别名\n保留', '--key','safe-full','--run','--wait','120'])
    assert 'result' in first
    safe,_=finish('safe-full',first['job'],'succeeded',check=lambda j,r: check_safe(r))
    duplicate=cli('safe-duplicate',['deeptmhmm','--sequence',SEQ,'--user-id','安全 ID | ../别名\n保留','--key','safe-full','--run','--wait','120'])
    assert duplicate==first
    conflict=cli('duplicate-conflict',['deeptmhmm','--sequence',SEQ+'A','--user-id','安全 ID | ../别名\n保留','--key','safe-full'],20)
    assert conflict['error']['code']=='IDEMPOTENCY_CONFLICT'
    entries.append(dict(case='duplicate-and-conflict',job_id=safe['job_id'],state='PASS',same_attempt=True))
    for index,bad in enumerate(['ACDEFGHIK*','ACDEFGHIKX','A'*8,'A'*1024]):
        rejected=cli('invalid-'+str(index),['deeptmhmm','--sequence',bad,'--key','invalid-'+str(index)],20)
        assert rejected['error']['code']=='INVALID_REQUEST'
    entries.append(dict(case='invalid-inputs',state='PASS',rejected_before_task_creation=4))
    pbjob=submit('pb173',pb)
    finish('pb173',pbjob,'succeeded',check=lambda j,r:check_pb(r))
    queued=cli('queued',['deeptmhmm','--sequence',SEQ,'--key','queued'])
    control(queued,'cancel','cancel-queued')
    finish('queued-cancel',queued,'cancelled','CANCELLED')
    running=submit('running-cancel')
    until(lambda:(rt.root/rt.attempt_path(running)/'start.json').is_file())
    control(running,'cancel','cancel-running')
    finish('running-cancel',running,'cancelled','CANCELLED')
    timed=submit('timeout',timeout=2)
    finish('timeout',timed,'timed_out','TIMEOUT')
    failed=submit('tool-failure',fault='tool_failure')
    finish('tool-failure',failed,'failed','TOOL_FAILED')
    corrupt=submit('corrupt-output',fault='corrupt_output')
    finish('corrupt-output',corrupt,'failed','OUTPUT_INVALID')
    live=submit('live-recovery')
    until(lambda:(rt.root/rt.attempt_path(live)/'start.json').is_file())
    before=rt.get(live['job_id']);reattached=cli('live-recover',['recover','--job-id',live['job_id']])
    assert reattached['execution_identity']==before['execution_identity'] and reattached['lease_epoch']>before['lease_epoch']
    finish('live-recovery',live,'succeeded',check=lambda j,r:check_safe(r))
    crashed=submit('crash-after-start',fault='crash_after_start')
    until(lambda:alive(rt.execution(crashed['job_id']).get('supervisor')) is False)
    cli('crash-recover',['recover','--job-id',crashed['job_id']])
    crashed,_=finish('crash-after-start',crashed,'failed','INTERRUPTED')
    retried=control(crashed,'retry','explicit-retry')
    assert retried['retry_of_job_id']==crashed['job_id'] and retried['request_artifact']==crashed['request_artifact']
    rt.dispatch(retried['job_id'])
    finish('explicit-retry',retried,'succeeded',check=lambda j,r:check_safe(r))
    receipt=submit('crash-after-receipt',fault='crash_after_receipt')
    until(lambda:alive(rt.execution(receipt['job_id']).get('supervisor')) is False)
    cli('receipt-recover',['recover','--job-id',receipt['job_id']])
    finish('crash-after-receipt',receipt,'succeeded',check=lambda j,r:check_safe(r))
    assert docker.inspect(rt.root) is None
    assert registered_profile()==profile,'Code changed during acceptance'
    inventory={p.relative_to(batch).as_posix():dict(sha256=sha(p.read_bytes()),size_bytes=p.stat().st_size) for p in batch.rglob('*') if p.is_file()}
    value=dict(completed_at=now(),status='PASS',qualification='LOCAL_DEVELOPMENT_ONLY',scientific_signoff=None,
        usable_for_pipeline=False,production_status='NOT_DEPLOYED',runtime_root=str(rt.root),profile=profile,cases=entries,files=inventory)
    write(batch/'index.json',value)
    print(encode(dict(status='PASS',cases=len(entries),index=str(batch/'index.json'))).decode(),flush=True)


def check_safe(result):
    assert result['topology']['labels']==['inside']*51 and result['token_observation']['token_count']==53
    assert result['internal_sequence_id']==sequence_id(SEQ)


def check_pb(result):
    assert result['topology'] is None and result['status']=='unreliable' and result['null_reason']=='PB_OUT_OF_DOMAIN'
    assert set('PB')<=set(result['raw_record']['labels']) and result['warnings'][0]['severity']=='WARNING'


if __name__=='__main__':main()
