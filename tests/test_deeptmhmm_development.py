"""Current unified local Worker: admission, output guards and durable publication."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import subprocess

import pytest

from t01_phase1_real.common import REPO, RuntimeFault, decode, encode, profile, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development import docker, deeptmhmm
from t01_phase1_real.development.policy import TOOL, IMAGE, request, registered_profile, sequence_id
from t01_phase1_real.development.supervisor import collect_stopped, inspect_contract

SEQ='MQLRHIGDSVNHRVIQEHLAQEVGDVLAPFVALVFVRGQVLLRFFWNNHLL'
BATCH=REPO/'discovery/t01-phase1-real/w1/deeptmhmm-academic-boundaries-20260906'


def body(**changes):
    value=dict(protein_sequence=SEQ,user_sequence_id='用户 | ../ id\nno FASTA injection',timeout_seconds=900)
    value.update(changes);return encode(value)


@pytest.fixture
def rt(tmp_path):
    if os.name!='nt':pytest.skip('Current local runtime requires Windows')
    return Runtime(tmp_path/'runtime')


@pytest.fixture
def files():
    folder=BATCH/'runs/safe-id'
    return {p.relative_to(folder).as_posix():p.read_bytes() for p in folder.rglob('*') if p.is_file()}


@pytest.mark.parametrize('sequence',['','A'*8,'A'*1024,'ACDEFGHIK*','ACDEFGHIKX','acdefghik','ACDEFGHI K','ACDEFGHIK\n','A'*9+'\u200b',None])
def test_invalid_sequence_no_run_job_or_artifact(rt,sequence):
    with pytest.raises(RuntimeFault):rt.submit_sequence(body(protein_sequence=sequence),'invalid')
    with rt._db() as db:
        for table in ['runs','jobs','artifacts','idempotency']:
            assert db.execute('SELECT count(*) FROM '+table).fetchone()[0]==0


@pytest.mark.parametrize('changes',[{'timeout_seconds':True},{'timeout_seconds':0},{'timeout_seconds':901},{'user_sequence_id':'a'*513},{'user_sequence_id':None},{'command':'arbitrary'},{'protein_sequence':['A']}])
def test_exact_request_shape(changes):
    with pytest.raises(RuntimeFault):request(body(**changes))


@pytest.mark.parametrize('length',[9,1020,1021,1022,1023])
def test_explicit_local_coverage_length(length):
    assert len(request(body(protein_sequence='A'*length))['protein_sequence'])==length


def test_atomic_duplicate_requests_and_byte_conflict(rt):
    raw=body()
    with ThreadPoolExecutor(4) as pool:
        jobs=list(pool.map(lambda _:Runtime(rt.root).submit_sequence(raw,'same-key'),range(8)))
    assert len({j['job_id'] for j in jobs})==1
    assert jobs[0]['request_artifact']['evidence_kind']=='LOCAL_INPUT'
    with rt._db() as db:
        assert [db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['runs','jobs','artifacts']]==[1,1,1]
    with pytest.raises(RuntimeFault,match='different bytes'):rt.submit_sequence(raw+b' ','same-key')
    assert Runtime(rt.root).submit_sequence(raw,'same-key')['job_id']==jobs[0]['job_id']
    assert not jobs[0]['usable_for_pipeline'] and jobs[0]['review_required']
    assert sequence_id(SEQ)=='t01seq_'+sha(SEQ.encode())


def test_same_store_supports_engineering_and_development(rt):
    run=rt.create_run('engineering-run')['run_id']
    ref=rt.stage_request(run,encode(dict(mode='echo',payload='integration-regression',delay_seconds=0)))
    job=rt.submit(encode(dict(contract_version='0.1.0',run_id=run,request_id='engineering-request',idempotency_key='engineering',
        tool_id='t01.real.engineering_probe',node_id=None,run_mode='engineering_example',request_artifact=ref,execution_profile=profile(),rule_profile=None)))
    rt.dispatch(job['job_id']);done=rt.wait(job['job_id'],15)
    assert done['state']=='succeeded' and done['evidence_kind']=='ENGINEERING_FIXTURE'
    assert rt.submit_sequence(body(),'deep')['run_id']!=run


@pytest.mark.parametrize('change',[{'run_mode':'pipeline'},{'node_id':'N01'},{'tool_id':'t01.real.foldx'}, {'execution_profile':{'id':'fake','version':'0.1.0','sha256':'0'*64}}])
def test_registered_worker_and_scientific_gate(rt,change):
    job=rt.submit_sequence(body(),'original')
    fields=['contract_version','run_id','request_id','tool_id','node_id','run_mode','request_artifact','execution_profile','rule_profile']
    req={k:job[k] for k in fields};req.update(idempotency_key='forbidden',**change)
    with pytest.raises(RuntimeFault):rt.submit(encode(req))


def test_input_hash_tamper_blocks_before_dispatch(rt):
    job=rt.submit_sequence(body(),'tamper')
    with rt._db() as db:path=db.execute('SELECT relative_path FROM artifacts').fetchone()[0]
    (rt.root/path).write_bytes(body(protein_sequence='A'*51))
    done=rt.dispatch(job['job_id'])
    assert done['state']=='failed' and done['attempt_id'] is None and done['error_code']=='HASH_MISMATCH'


def test_queued_cancel_and_explicit_retry_preserve_lineage(rt):
    job=rt.submit_sequence(body(),'cancel-queued')
    command=lambda op,key:encode(dict(contract_version='0.1.0',operation=op,job_id=job['job_id'],idempotency_key=key))
    stopped=rt.control(command('cancel','cancel'))
    assert stopped['state']=='cancelled' and stopped['attempt_id'] is None
    retried=rt.control(command('retry','retry'))
    assert retried['job_id']!=job['job_id'] and retried['retry_of_job_id']==job['job_id']
    assert retried['request_artifact']==job['request_artifact']
    assert rt.control(command('retry','retry'))==retried


def test_parser_on_preexisting_real_safe_id_output(files):
    value=deeptmhmm.parse(files,SEQ)
    assert value['topology']==dict(labels=['inside']*51,segments=[dict(type='inside',start=1,end=51)],tm_count=0,outside_length=0,has_signal=False)
    assert value['token_observation']['token_count']==53 and value['probability']['rows']==51


@pytest.mark.parametrize('name',['predicted_topologies.3line','TMRs.gff3','deeptmhmm_results.md','plot.png', 'probabilities/'+sequence_id(SEQ)+'_probs.csv'])
def test_missing_output_is_rejected(files,name):
    del files['output/result/'+name]
    with pytest.raises(ValueError,match='Missing required artifact'):deeptmhmm.parse(files,SEQ)


@pytest.mark.parametrize('fault',['truncated','sequence','id','region','nan','probability-position','png-crc','report','token','runtime','extra-probability'])
def test_damaged_raw_cannot_be_parsed(files,fault):
    prefix='output/result/'
    prediction=prefix+'predicted_topologies.3line';prob=prefix+'probabilities/'+sequence_id(SEQ)+'_probs.csv'
    if fault=='truncated':files[prediction]=files[prediction][:-3]
    elif fault=='sequence':files[prediction]=files[prediction].replace(SEQ.encode(),b'A'*51)
    elif fault=='id':files[prediction]=files[prediction].replace(sequence_id(SEQ).encode(),b'foreign')
    elif fault=='region':files[prefix+'TMRs.gff3']=files[prefix+'TMRs.gff3'].replace(b'\t1\t51',b'\t2\t51')
    elif fault in ('nan','probability-position'):
        lines=files[prob].decode().splitlines();cells=lines[2].split(',');cells[1 if fault=='nan' else 0]='nan' if fault=='nan' else '1 M';lines[2]=','.join(cells);files[prob]='\n'.join(lines).encode()
    elif fault=='png-crc':raw=bytearray(files[prefix+'plot.png']);raw[-1]^=1;files[prefix+'plot.png']=bytes(raw)
    elif fault=='report':files[prefix+'deeptmhmm_results.md']=b'foreign'
    elif fault=='token':
        events=[json.loads(line) for line in files['output/token_trace.jsonl'].splitlines()];events[0]['decoded_tokens'][1]='<unk>';files['output/token_trace.jsonl']=b'\n'.join(encode(e) for e in events)
    elif fault=='runtime':value=decode(files['output/runtime.json']);value['network_interfaces'].append([2,'eth0']);files['output/runtime.json']=encode(value)
    else:files[prefix+'probabilities/foreign_probs.csv']=files[prob]
    with pytest.raises((ValueError,KeyError)):deeptmhmm.parse(files,SEQ)


def test_pb_is_null_without_label_substitution(files):
    # Explicit format fixture derived from raw bytes, never a scientific reference.
    prefix='output/result/';name=prefix+'predicted_topologies.3line'
    files[name]=files[name].replace(b'I'*51,b'P'*25+b'B'*26).replace(b'| GLOB',b'| BETA')
    ident=sequence_id(SEQ)
    files[prefix+'TMRs.gff3']=(f'##gff-version 3\n# {ident} Length: 51\n# {ident} Number of predicted TMRs: 1\n'
        +f'{ident}\tperiplasm\t1\t25\t\t\t\t\n{ident}\tBeta sheet\t26\t51\t\t\t\t\n//\n').encode()
    value=deeptmhmm.parse(files,SEQ)
    assert value['topology'] is None and value['status']=='unreliable'
    assert value['raw_record']['labels']=='P'*25+'B'*26
    assert value['warnings'][0]['severity']=='WARNING' and value['null_reason']=='PB_OUT_OF_DOMAIN'


@pytest.mark.parametrize('stderr',[b'Error: No such object: slot',b'error: no such object: slot',b'No such container: slot'])
def test_docker_absent_message_variants(rt,monkeypatch,stderr):
    monkeypatch.setattr(docker,'call',lambda *a,**kw:subprocess.CompletedProcess([],1,b'[]',stderr))
    assert docker.inspect(rt.root) is None


def test_docker_unknown_state_never_means_absent(rt,monkeypatch):
    monkeypatch.setattr(docker,'call',lambda *a,**kw:subprocess.CompletedProcess([],1,b'',b'permission denied'))
    with pytest.raises(RuntimeFault,match='permission denied'):docker.inspect(rt.root)


def test_foreign_container_cannot_be_stopped(rt,monkeypatch):
    job=rt.submit_sequence(body(),'foreign');job.update(attempt_id='attempt',execution_identity='exec')
    info=dict(Config=dict(Labels=docker.labels(rt.root,job),Image=IMAGE),State=dict(Running=True))
    assert docker.owned(rt.root,job,info)
    info['Config']['Labels']['t01.job_id']='other'
    monkeypatch.setattr(docker,'call',lambda *a,**kw:pytest.fail('Foreign stop attempted'))
    with pytest.raises(RuntimeFault,match='foreign'):docker.stop(rt.root,job,info)


def test_stopped_confirmation_and_artifact_binding(rt,files):
    job=rt.submit_sequence(body(),'publish')
    # Controlled lifecycle fixture; raw input comes from actual archived execution.
    from t01_phase1_real.common import new_id, now
    with rt._tx() as db:
        active=copy.deepcopy(job);active.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),lease_epoch=1,started_at=now())
        rt._store(db,active,job,'fixture-claimed');rt._execution_store(db,job['job_id'],{})
    report=decode(files['output/runtime.json']);report['native_output_sha256']={p[len('output/'):]:sha(raw) for p,raw in files.items() if p.startswith('output/result/')}
    files['output/runtime.json']=encode(report)
    result=deeptmhmm.result(active,request(body()),files,dict(exit_code=0,error_code=None,stopped_confirmed=True))
    assert not result['usable_for_pipeline'] and not result['automatic_handoff']
    with pytest.raises(RuntimeFault,match='stop must be confirmed'):rt._finish_development(job['job_id'],{},files,result)
    final=rt._finish_development(job['job_id'],dict(tree_stopped=True),files,result)
    assert final['state']=='succeeded' and rt.result(job['job_id'])['binding']['input_sha256']==sha(body())
    other=rt.submit_sequence(body(),'other')
    with pytest.raises(RuntimeFault):rt.artifact_bytes(other['job_id'],final['artifacts'][0]['artifact_id'])
    assert Runtime(rt.root).result(job['job_id'])['topology'] is not None
    with rt._db() as db:path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(final['artifacts'][-1]['artifact_id'],)).fetchone()[0]
    (rt.root/path).write_bytes(b'changed')
    with pytest.raises(RuntimeFault):rt.result(job['job_id'])


def reserved(rt):
    from t01_phase1_real.common import new_id, now
    from t01_phase1_real.winprocess import current_identity
    job=rt.submit_sequence(body(),'reserved')
    with rt._tx() as db:
        active=copy.deepcopy(job);active.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),lease_epoch=1,started_at=now())
        rt._store(db,active,job,'fixture-claimed')
        rt._execution_store(db,job['job_id'],dict(phase='spawn_intent',dispatcher=current_identity(),supervisor=None,tree_stopped=False))
    path=rt.root/rt.attempt_path(active);path.mkdir(parents=True)
    (path/'input.json').write_bytes(body());(path/'input.fasta').write_bytes(('>'+sequence_id(SEQ)+'\n'+SEQ+'\n').encode())
    return active,path


def test_recover_fences_launch_gap_and_late_supervisor(rt,monkeypatch):
    from t01_phase1_real.development.supervisor import supervise
    active,path=reserved(rt)
    monkeypatch.setattr(docker,'inspect',lambda *args:None)
    assert rt.reconcile(active['job_id'])['state']=='running'
    final=rt.recover(active['job_id'])
    assert final['state']=='failed' and final['error_code']=='INTERRUPTED'
    monkeypatch.setattr(docker,'call',lambda *a,**kw:pytest.fail('Fenced supervisor launched a model'))
    supervise(rt.root,rt.scope,active['job_id'])
    assert rt.get(active['job_id'])==final


@pytest.mark.parametrize('damage',['missing-inventory','inventory-hash','raw-bytes','input-fasta','receipt-bytes'])
def test_recovered_output_damage_retains_diagnostic_and_no_topology(rt,monkeypatch,damage):
    active,path=reserved(rt)
    inventory=encode({n:sha((path/n).read_bytes()) for n in ['input.json','input.fasta']})
    (path/'raw-inventory.json').write_bytes(inventory)
    receipt=dict(job_id=active['job_id'],attempt_id=active['attempt_id'],execution_identity=active['execution_identity'],
        stopped_confirmed=True,exit_code=0,oom_killed=False,error_code=None,raw_inventory_sha256=sha(inventory))
    (path/'receipt.json').write_bytes(encode(receipt))
    with rt._tx() as db:
        ex=rt._execution(db,active['job_id']);ex['receipt_sha256']=sha(encode(receipt));rt._execution_store(db,active['job_id'],ex)
    if damage=='missing-inventory':(path/'raw-inventory.json').unlink()
    elif damage=='inventory-hash':(path/'raw-inventory.json').write_bytes(inventory+b' ')
    elif damage=='raw-bytes':(path/'input.json').write_bytes(body()+b' ')
    elif damage=='input-fasta':(path/'input.fasta').write_bytes(b'>wrong\n'+SEQ.encode()+b'\n')
    else:(path/'receipt.json').write_bytes(b'corrupt receipt')
    monkeypatch.setattr(docker,'inspect',lambda *args:None)
    final=rt.recover(active['job_id'])
    assert final['state']=='failed' and final['error_code']=='OUTPUT_INVALID'
    result=rt.result(active['job_id'])
    assert result['topology'] is None and result['execution']['diagnostic']
    assert result['raw_artifacts']


def test_changed_native_embedding_hash_blocks_result(rt,files):
    job=rt.submit_sequence(body(),'embedding');job.update(attempt_id='test-attempt',execution_identity='test-exec')
    report=decode(files['output/runtime.json']);report['native_output_sha256']={p[len('output/'):]:sha(raw) for p,raw in files.items() if p.startswith('output/result/')}
    files['output/runtime.json']=encode(report)
    name=next(p for p in files if p.startswith('output/result/embeddings/'));files[name]=b'corrupted embedding'
    value=deeptmhmm.result(job,request(body()),files,dict(exit_code=0,error_code=None,stopped_confirmed=True))
    assert value['topology'] is None and value['execution']['error_code']=='OUTPUT_INVALID'
    assert 'Native output hash mismatch' in value['execution']['diagnostic']


@pytest.mark.parametrize('change',[{'exit_code':1},{'exit_code':None},{'exit_code':False},{'stopped_confirmed':False},{'oom_killed':True}])
def test_nonclean_execution_never_parses_reusable_outputs(rt,files,change):
    job=rt.submit_sequence(body(),'unclean');job.update(attempt_id='fixture',execution_identity='fixture')
    execution=dict(exit_code=0,stopped_confirmed=True,error_code=None);execution.update(change)
    value=deeptmhmm.result(job,request(body()),files,execution)
    assert value['topology'] is None and value['execution']['error_code']=='OUTPUT_INVALID'


def test_recovery_checks_immutable_container_id_even_if_name_disappears(rt,monkeypatch):
    job,path=reserved(rt)
    with rt._tx() as db:
        ex=rt._execution(db,job['job_id']);ex['container_id']='a'*64;rt._execution_store(db,job['job_id'],ex)
    checked=[]
    def inspect(root,identity=None):checked.append(identity);return None
    monkeypatch.setattr(docker,'inspect',inspect)
    assert rt.recover(job['job_id'])['state']=='failed'
    assert checked==['a'*64]
