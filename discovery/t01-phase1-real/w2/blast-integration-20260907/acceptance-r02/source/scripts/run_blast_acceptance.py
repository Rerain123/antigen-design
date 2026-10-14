"""Reproducible W2 N03 BLAST+ engine campaign using only an engineering FASTA database."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import RuntimeFault, decode, encode, now, sha
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.blast import policy
from t01_phase1_real.winprocess import alive
from run_deeptmhmm_acceptance import write as original_write, until

SEQ='MKWVTFISLLFLFSSAYSRGVFRRDTHKSEIAHRFKDLGE'


def write(path,value):
    raw=value if isinstance(value,bytes) else encode(value)
    if path.exists():
        assert path.read_bytes()==raw,'Cannot rewrite existing evidence: '+str(path)
        return
    original_write(path,raw)


def make_manifest(folder,database_id):
    files=[]
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.name=='manifest.json':continue
        raw=path.read_bytes();files.append(dict(path=path.name,role='source_fasta' if path.name=='source.fasta' else 'index',
            bytes=len(raw),sha256=sha(raw)))
    value=dict(schema_version='0.1.0',database_id=database_id,qualification='ENGINEERING_FIXTURE',
        purpose='N03 engine integration only; not a target or literature database',created_at=now(),
        source=dict(name='T-01 N03 engineering FASTA',version='2026-09-07',release_date='2026-09-07',
            license='project engineering fixture',reference='tests/fixtures/blast-engineering.fasta'),
        blast=dict(db_prefix='engineering',dbtype='prot',blastdb_version=5,title='t01-n03-engineering-fixture',
            sequence_count=3,makeblastdb_version='makeblastdb: 2.17.0+',builder_identity=policy.IMAGE),files=files)
    raw=encode(value);write(folder/'manifest.json',raw);return raw,value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--batch',required=True)
    args=parser.parse_args();root=Path(args.root).absolute();batch=Path(args.batch).absolute()
    assert root.is_absolute() and not root.exists(),'Use a fresh absolute runtime root'
    assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w2') and not batch.exists(),'Use a fresh W2 batch'
    batch.mkdir(parents=True);database_root=batch/'databases';database_root.mkdir();database=database_root/'engineering-n03';database.mkdir()
    write(database/'source.fasta',(REPO/'tests/fixtures/blast-engineering.fasta').read_bytes())
    runtime=Runtime(root,blast_database_root=database_root);profile=policy.registered_profile();entries=[]

    source_paths=list((REPO/'src/t01_phase1_real/development/blast').glob('*'))
    source_paths += [REPO/'src/t01_phase1_real/development'/name for name in
        ['docker.py','supervisor.py','runtime.py','registry.py','contracts.py','cli.py']]
    source_paths += [REPO/'scripts'/name for name in
        ['t01_runtime.py','t01_development_supervisor.py','run_blast_acceptance.py','run_deeptmhmm_acceptance.py']]
    source_paths += [REPO/'tests/test_blast_development.py',REPO/'tests/fixtures/blast-engineering.fasta']
    for path in source_paths:
        if path.is_file():write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    receipt=policy.verify_assets();image=docker.call(root,['image','inspect','--format','{{.Id}} {{.Architecture}} {{.Os}}',policy.IMAGE])
    assert image.returncode==0 and image.stdout.decode().strip()==policy.IMAGE+' amd64 linux'
    build_argv=docker.client(root)+['run','--rm','--network','none','--mount',f'type=bind,source={database},target=/db',
        receipt['image_reference'],'makeblastdb','-in','/db/source.fasta','-dbtype','prot','-parse_seqids','-blastdb_version','5',
        '-out','/db/engineering','-title','t01-n03-engineering-fixture']
    build=subprocess.run(build_argv,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    write(batch/'build/makeblastdb.json',dict(argv=build_argv,exit_code=build.returncode,
        stdout=build.stdout.decode('utf-8'),stderr=build.stderr.decode('utf-8')))
    assert build.returncode==0,(build.stdout,build.stderr)
    manifest_raw,manifest=make_manifest(database,'engineering-n03');manifest_sha=sha(manifest_raw)
    db_receipt=policy.verify_database(database_root,policy.request(encode(dict(protein_sequence=SEQ,user_sequence_id='verify',
        database_id='engineering-n03',database_manifest_sha256=manifest_sha,
        thresholds=dict(identity_percent_min=70.0,query_coverage_percent_min=80.0),timeout_seconds=30))))
    db_receipt.pop('mount_path');write(batch/'build/database-verified.json',db_receipt)
    write(batch/'profile.json',profile);write(batch/'assets-verified.json',receipt)
    write(batch/'environment.json',dict(image_inspect=image.stdout.decode().strip(),inference_network='none',
        database_kind='ENGINEERING_FIXTURE',target_database_validated=False,open_item='OI-028'))

    def request(sequence=SEQ,database_id='engineering-n03',digest=manifest_sha,timeout=30,identity=70.0,coverage=80.0,alias='W2 N03'):
        return dict(protein_sequence=sequence,user_sequence_id=alias,database_id=database_id,database_manifest_sha256=digest,
            thresholds=dict(identity_percent_min=identity,query_coverage_percent_min=coverage),timeout_seconds=timeout)

    def cli(name,values,expected=0):
        argv=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),
            '--blast-database-root',str(database_root),*values]
        run=subprocess.run(argv,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch/'cli'/(name+'.json'),dict(argv=argv,exit_code=run.returncode,
            stdout=run.stdout.decode('utf-8'),stderr=run.stderr.decode('utf-8')))
        assert run.returncode==expected,(name,run.returncode,run.stdout[:500],run.stderr[:500])
        return decode(run.stdout)

    def submit(name,value=None,fault=None):
        value=value or request(alias='W2 N03 '+name);path=batch/'requests'/(name+'.json');write(path,value)
        job=cli(name+'-submit',['blast','--input',str(path),'--key',name])
        runtime._development_fault=fault
        try:runtime.dispatch(job['job_id'])
        finally:runtime._development_fault=None
        return runtime.get(job['job_id'])

    def finish(name,job,state='succeeded',error=None,status=None,seconds=180):
        final=runtime.wait(job['job_id'],seconds)
        write(batch/'cases'/name/'job.json',final);write(batch/'cases'/name/'events.json',runtime.events(job['job_id']))
        if final['attempt_id']:write(batch/'cases'/name/'execution.json',runtime.execution(job['job_id']))
        value=runtime.result(job['job_id']) if final['artifacts'] else None
        if value:write(batch/'cases'/name/'result.json',value)
        for ref in final['artifacts']:
            raw=runtime.artifact_bytes(job['job_id'],ref['artifact_id'])
            assert sha(raw)==ref['sha256'] and len(raw)==ref['size_bytes'];write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
        assert final['state']==state and final['error_code']==error,(name,final['state'],final['error_code'])
        assert not final['usable_for_pipeline'] and final['review_required']
        if value:
            assert not value['usable_for_pipeline'] and not value['automatic_handoff'] and value['production_status']=='NOT_DEPLOYED'
            if status:assert value['status']==status,(name,value['status'])
        if final['attempt_id']:
            assert runtime.execution(job['job_id'])['tree_stopped']
            assert not docker.owned(root,final,docker.inspect(root,policy.SLOT))
        entry=dict(case=name,job_id=final['job_id'],state=state,error_code=error,result_status=value and value['status'],
            controlled_fault=value and value.get('controlled_fault'),artifacts_verified=len(final['artifacts']))
        entries.append(entry);print(encode(entry).decode(),flush=True);return final,value

    exact_path=batch/'requests/documented-exact.json';write(exact_path,request(alias='documented command'))
    exact=cli('documented-command',['blast','--input',str(exact_path),'--key','documented','--run','--wait','60'])
    exact_job=exact.get('job',exact)
    exact_final,exact_result=finish('exact-hit',exact_job,status='similarity_hits_unreviewed')
    assert exact_result['search']['search_status']=='hit' and exact_result['search']['qualifying_hsp_count']>=1
    assert exact_result['database']['qualification']=='ENGINEERING_FIXTURE' and exact_result['search']['iedb_hit'] is None
    duplicate=cli('duplicate',['blast','--input',str(exact_path),'--key','documented'])
    duplicate_job=duplicate.get('job',duplicate);assert duplicate_job['job_id']==exact_final['job_id']
    changed=request(alias='changed');changed_path=batch/'requests/conflict.json';write(changed_path,changed)
    assert cli('conflict',['blast','--input',str(changed_path),'--key','documented'],20)['error']['code']=='IDEMPOTENCY_CONFLICT'
    entries.append(dict(case='duplicate-and-conflict',state='PASS',same_attempt=True))

    invalid=request(sequence='ACDEFGHIKX');invalid_path=batch/'requests/invalid-sequence.json';write(invalid_path,invalid)
    assert cli('invalid-sequence',['blast','--input',str(invalid_path),'--key','invalid'],20)['error']['code']=='INVALID_REQUEST'
    entries.append(dict(case='invalid-sequence',state='PASS',rejected_before_admission=True))
    _,no_hit=finish('no-hit',submit('no-hit',request(sequence='P'*42)),status='no_qualifying_similarity_hit')
    assert no_hit['search']['search_status']=='no_hit' and no_hit['search']['qualifying_hsp_count']==0
    near=SEQ[:-2]+'AA';_,filtered=finish('raw-below-threshold',submit('raw-below-threshold',request(sequence=near,identity=99.9,coverage=99.9)),
        status='no_qualifying_similarity_hit')
    assert filtered['search']['raw_hsp_count']>=1 and filtered['search']['qualifying_hsp_count']==0

    finish('missing-database',submit('missing-database',request(database_id='missing-n03',digest='0'*64)),'failed','ASSET_MISSING','unreliable')
    finish('manifest-mismatch',submit('manifest-mismatch',request(digest='0'*64)),'failed','HASH_MISMATCH','unreliable')
    corrupt=database_root/'corrupt-n03';corrupt.mkdir()
    for path in database.iterdir():
        if path.is_file() and path.name!='manifest.json':shutil.copy2(path,corrupt/path.name)
    corrupt_raw,_=make_manifest(corrupt,'corrupt-n03');target=corrupt/'engineering.psq';target.write_bytes(target.read_bytes()+b'controlled damage')
    finish('corrupt-database',submit('corrupt-database',request(database_id='corrupt-n03',digest=sha(corrupt_raw))),
        'failed','HASH_MISMATCH','unreliable')
    finish('corrupt-output',submit('corrupt-output',fault='corrupt_output'),'failed','OUTPUT_INVALID','unreliable')
    failed,_=finish('tool-failure',submit('tool-failure',fault='tool_failure'),'failed','TOOL_FAILED','unreliable')
    retried=cli('tool-retry',['retry','--job-id',failed['job_id'],'--key','tool-retry'])
    runtime.dispatch(retried['job_id']);finish('tool-retry',retried,status='similarity_hits_unreviewed')

    queued=cli('queued-submit',['blast','--input',str(exact_path),'--key','queued'])
    cli('queued-cancel',['cancel','--job-id',queued['job_id'],'--key','queued-cancel'])
    finish('queued-cancel',queued,'cancelled','CANCELLED')
    running=submit('running-cancel',request(timeout=60),fault='slow_worker')
    until(lambda:(root/runtime.attempt_path(running)/'start.json').is_file())
    cli('running-cancel',['cancel','--job-id',running['job_id'],'--key','running-cancel'])
    finish('running-cancel',running,'cancelled','CANCELLED','unreliable')
    finish('timeout',submit('timeout',request(timeout=1),fault='slow_worker'),'timed_out','TIMEOUT','unreliable')

    crashed=submit('crash-after-start',fault='crash_after_start')
    until(lambda:alive(runtime.execution(crashed['job_id']).get('supervisor')) is False)
    cli('crash-recover',['recover','--job-id',crashed['job_id']])
    interrupted,_=finish('crash-after-start',crashed,'failed','INTERRUPTED','unreliable')
    retry=cli('crash-retry',['retry','--job-id',interrupted['job_id'],'--key','crash-retry'])
    runtime.dispatch(retry['job_id']);finish('crash-retry',retry,status='similarity_hits_unreviewed')

    tamper=submit('artifact-tamper');final,_=finish('artifact-tamper-original',tamper,status='similarity_hits_unreviewed')
    ref=next(item for item in final['artifacts'] if item['role']=='result');target=root/runtime.attempt_path(final)/'published'/(ref['artifact_id']+'.bin')
    original=target.read_bytes();write(batch/'controlled-damage/original-result.bin',original);target.write_bytes(original+b' controlled damage')
    try:runtime.result(final['job_id'])
    except RuntimeFault as exc:assert exc.code=='HASH_MISMATCH'
    else:raise AssertionError('Tampered result was readable')
    write(batch/'controlled-damage/detection.json',dict(job_id=final['job_id'],artifact_id=ref['artifact_id'],detected='HASH_MISMATCH'))
    entries.append(dict(case='artifact-tamper-detection',state='PASS',error_code='HASH_MISMATCH'))

    assert profile==policy.registered_profile() and docker.inspect(root,policy.SLOT) is None
    inventory={path.relative_to(batch).as_posix():dict(sha256=sha(path.read_bytes()),size_bytes=path.stat().st_size)
        for path in batch.rglob('*') if path.is_file()}
    write(batch/'index.json',dict(completed_at=now(),status='PASS',qualification='LOCAL_ENGINE_DEVELOPMENT_ONLY',
        scientific_signoff=None,usable_for_pipeline=False,automatic_handoff=False,production_status='NOT_DEPLOYED',
        runtime_root=str(root),profile=profile,engine=receipt,database_manifest_sha256=manifest_sha,
        database_qualification='ENGINEERING_FIXTURE',target_database_validated=False,open_item='OI-028',cases=entries,files=inventory))
    print(encode(dict(status='PASS',cases=len(entries),index=str(batch/'index.json'))).decode(),flush=True)


if __name__=='__main__':main()
