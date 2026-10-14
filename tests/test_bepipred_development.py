"""N04 admission, native score identity, postprocessing closure and lifecycle regression."""
from concurrent.futures import ThreadPoolExecutor
import copy
import csv
import io
import os

import pytest

from t01_phase1_real.common import REPO, RuntimeFault, decode, encode, new_id, now, sha, validate as old_validate
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.contracts import validate
from t01_phase1_real.development.bepipred import policy
from t01_phase1_real.development.bepipred.result import parse, result
from t01_phase1_real.development.supervisor import inspect_contract

SEQ='MQLRHIGDSVNHRVIQEHLAQEVGDVLAPFVALVFVRGQVLLRFFWNNHLL'
BATCH=REPO/'discovery/t01-phase1-real/w2/bepipred-integration-20260906'


def body(**changes):
    value=dict(protein_sequence=SEQ,user_sequence_id='../id | 用户\n metadata only',timeout_seconds=180)
    value.update(changes);return encode(value)


@pytest.fixture
def rt(tmp_path):
    if os.name!='nt':pytest.skip('Current trusted-local task runtime requires Windows')
    return Runtime(tmp_path/'runtime')


@pytest.fixture
def files():
    folder=BATCH/'raw-runs/safe51'
    return {p.relative_to(folder).as_posix():p.read_bytes() for p in folder.rglob('*') if p.is_file()}


@pytest.mark.parametrize('sequence',['','A'*8,'A'*1023,'acdefghik','ACDEFGHIKX','ACDEFGHIK*','ACDEFGHIK\n','ACDEFGHI K','ACDEFGHIK\u200b',None])
def test_invalid_bepi_sequence_precedes_task_admission(rt,sequence):
    with pytest.raises(RuntimeFault):rt.submit_sequence(body(protein_sequence=sequence),'bad',policy.TOOL)
    with rt._db() as db:
        assert all(db.execute('SELECT count(*) FROM '+name).fetchone()[0]==0 for name in ['runs','jobs','artifacts','idempotency'])


@pytest.mark.parametrize('changes',[dict(timeout_seconds=True),dict(timeout_seconds=0),dict(timeout_seconds=901),dict(user_sequence_id=None),
    dict(user_sequence_id='x'*513),dict(threshold=.1),dict(add_seq_len=True),dict(structure='local.pdb'),dict(command='arbitrary')])
def test_exact_request_does_not_enable_unreviewed_parameters(changes):
    with pytest.raises(RuntimeFault):policy.request(body(**changes))


@pytest.mark.parametrize('length',[9,30,1022])
def test_declared_local_bounds(length):
    assert len(policy.request(body(protein_sequence='A'*length))['protein_sequence'])==length


@pytest.mark.parametrize('raw',[b'[]',b'null',b'{bad',b'{"protein_sequence":"A","protein_sequence":"B"}'])
def test_malformed_submit_has_contract_error(rt,raw):
    with pytest.raises(RuntimeFault):rt.submit(raw)


def test_atomic_bepi_duplicates_preserve_original_alias_and_bytes(rt):
    raw=body()
    with ThreadPoolExecutor(4) as pool:
        jobs=list(pool.map(lambda _:Runtime(rt.root).submit_sequence(raw,'same',policy.TOOL),range(8)))
    assert len({j['job_id'] for j in jobs})==1
    job=jobs[0];assert job['tool_id']==policy.TOOL and job['node_id']=='N04'
    assert rt._request_bytes(job)==raw and not job['usable_for_pipeline'] and job['review_required']
    with rt._db() as db:assert [db.execute('SELECT count(*) FROM '+n).fetchone()[0] for n in ['runs','jobs','artifacts']]==[1,1,1]
    with pytest.raises(RuntimeFault) as exc:rt.submit_sequence(raw+b' ','same',policy.TOOL)
    assert exc.value.code=='IDEMPOTENCY_CONFLICT'
    assert rt.submit_sequence(raw,'same')['tool_id']=='t01.real.deeptmhmm'  # Separate operation idempotency domain.


def envelope(job,**changes):
    fields=['contract_version','run_id','request_id','tool_id','node_id','run_mode','request_artifact','execution_profile','rule_profile']
    value={k:job[k] for k in fields};value.update(idempotency_key='explicit-submit',**changes);return value


def test_additive_registration_keeps_original_w1_schema_closed(rt):
    job=rt.submit_sequence(body(),'one',policy.TOOL)
    validate(job,'job');validate(envelope(job),'submit')
    with pytest.raises(RuntimeFault):old_validate(job,'job')
    with pytest.raises(RuntimeFault):old_validate(envelope(job),'submit')
    other=rt.submit(encode(envelope(job,request_id='explicit-bepi')))
    assert other['node_id']=='N04' and other['tool_id']==policy.TOOL and other['request_artifact']==job['request_artifact']


@pytest.mark.parametrize('changes',[dict(node_id='N02'),dict(run_mode='pipeline'),dict(tool_id='t01.real.foldx'),
    dict(execution_profile=dict(id='wrong',version='0.1.0',sha256='0'*64))])
def test_bepi_science_and_arbitrary_worker_admission_closed(rt,changes):
    job=rt.submit_sequence(body(),'one',policy.TOOL)
    with pytest.raises(RuntimeFault):rt.submit(encode(envelope(job,**changes)))


def test_cross_run_request_ref_and_changed_input_rejected(rt):
    job=rt.submit_sequence(body(),'one',policy.TOOL);other=rt.create_run('other')
    with pytest.raises(RuntimeFault):rt.submit(encode(envelope(job,run_id=other['run_id'])))
    with rt._db() as db:path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(job['request_artifact']['artifact_id'],)).fetchone()[0]
    (rt.root/path).write_bytes(body(protein_sequence='A'*51))
    final=rt.dispatch(job['job_id'])
    assert final['state']=='failed' and final['error_code']=='HASH_MISMATCH' and final['attempt_id'] is None


def test_cancel_retry_n04_history_preserves_identity(rt):
    job=rt.submit_sequence(body(),'one',policy.TOOL)
    def control(op,key):return rt.control(encode(dict(contract_version='0.1.0',operation=op,job_id=job['job_id'],idempotency_key=key)))
    stopped=control('cancel','cancel');assert stopped['state']=='cancelled' and stopped['attempt_id'] is None
    retried=control('retry','retry');assert retried['retry_of_job_id']==job['job_id'] and retried['request_artifact']==job['request_artifact']
    assert retried['node_id']=='N04' and retried['tool_id']==policy.TOOL
    assert [e['snapshot']['revision'] for e in rt.events(job['job_id'])]==[0,1]
    with rt._tx() as db:
        with pytest.raises(RuntimeFault):rt._store(db,dict(stopped,state='running'),stopped)


def test_original_native_scores_remain_distinct_from_project_peaks(files):
    value=parse(files,SEQ)
    assert len(value['raw_scores'])==51
    assert value['raw_scores'][0]==dict(sequence_position=1,residue='M',ensemble_probability=0.20961466431617737,linear_epitope_score=0.13565340803729165)
    assert value['raw_record']['embedding_shape']==[51,1280] and len(value['raw_record']['classification_fastas'])==3


def recalc_inventory(files):
    runtime=decode(files['output/runtime.json'])
    runtime['native_output_sha256']={p[len('output/'):]:sha(raw) for p,raw in files.items() if p.startswith('output/') and p!='output/runtime.json'}
    files['output/runtime.json']=encode(runtime)


@pytest.mark.parametrize('name',['raw_output.csv','Bcell_epitope_preds.fasta','Bcell_epitope_top_20pct_preds.fasta',
    'Bcell_linepitope_top_20pct_preds.fasta','output_interactive_figures.html'])
def test_missing_native_product_is_not_a_no_epitope_success(files,name):
    del files['output/result/'+name]
    recalc_inventory(files)  # Even a coherent shortened inventory is invalid.
    with pytest.raises(RuntimeFault):parse(files,SEQ)


@pytest.mark.parametrize('damage',['length','long','sequence','id','columns','nan','infinity','negative','over-one','score','smooth'])
def test_native_csv_semantics_checked_after_hashes(files,damage):
    path='output/result/raw_output.csv';rows=list(csv.reader(io.StringIO(files[path].decode())))
    if damage=='length':rows.pop()
    elif damage=='long':rows.append(rows[-1])
    elif damage=='sequence':rows[1][1]='A'
    elif damage=='id':rows[1][0]='foreign'
    elif damage=='columns':rows[0][2]='BepiPred 2 score'
    else:rows[1][3 if damage=='smooth' else 2]={'nan':'nan','infinity':'inf','negative':'-0.1','over-one':'1.01','score':'0.99','smooth':'0.99'}[damage]
    out=io.StringIO();csv.writer(out).writerows(rows);files[path]=out.getvalue().encode();recalc_inventory(files)
    with pytest.raises((RuntimeFault,ValueError)):parse(files,SEQ)


@pytest.mark.parametrize('damage',['mask','top','linear-top','html','embedding','shape','fold-count','weights','variant','network','package','native-hash','runtime-json'])
def test_other_native_provenance_and_output_guards(files,damage):
    def modify(path,action):
        value=decode(files[path]);action(value);files[path]=encode(value)
    fasta_names={'mask':'Bcell_epitope_preds.fasta','top':'Bcell_epitope_top_20pct_preds.fasta','linear-top':'Bcell_linepitope_top_20pct_preds.fasta'}
    if damage in fasta_names:
        name='output/result/'+fasta_names[damage];lines=files[name].decode().splitlines();lines[1]=lines[1][0].swapcase()+lines[1][1:];files[name]='\n'.join(lines).encode()
    elif damage=='html':files['output/result/output_interactive_figures.html']=b'<div>truncated'
    elif damage=='embedding':files[next(p for p in files if p.startswith('output/encodings/'))]=b'changed'
    elif damage=='shape':modify('output/observations.json',lambda v:v['records'][0].update(embedding_shape=[50,1280]))
    elif damage=='fold-count':modify('output/observations.json',lambda v:v['records'][0]['fold_probabilities'].pop())
    elif damage=='weights':modify('output/observations.json',lambda v:v['folds'][0].update(sha256='0'*64))
    elif damage=='variant':modify('output/observations.json',lambda v:v.update(add_seq_len=True))
    elif damage=='network':modify('output/runtime.json',lambda v:v['network_interfaces'].append([2,'eth0']))
    elif damage=='package':modify('output/runtime.json',lambda v:v['packages'].update(bp3='0.0.12.8'))
    elif damage=='native-hash':files['output/result/raw_output.csv']+=b' '
    elif damage=='runtime-json':files['output/runtime.json']=b'{broken'
    if damage not in ('native-hash','runtime-json'):recalc_inventory(files)
    with pytest.raises((RuntimeFault,ValueError)):parse(files,SEQ)


def active(rt):
    job=rt.submit_sequence(body(),'publish',policy.TOOL);value=copy.deepcopy(job)
    value.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),lease_epoch=1,started_at=now())
    with rt._tx() as db:rt._store(db,value,job,'fixture-claimed');rt._execution_store(db,job['job_id'],{})
    return value


def test_publication_qualification_and_scoped_artifact_access(rt,files):
    job=active(rt);execution=dict(exit_code=0,error_code=None,stopped_confirmed=True,image_id=policy.IMAGE)
    value=result(job,policy.request(body()),files,execution)
    assert value['status']=='raw_scores_unreviewed' and value['postprocessing']['status']=='computed_pending_calibration'
    assert value['postprocessing']['linear_scores']==[r['ensemble_probability'] for r in value['raw_scores']]
    assert value['postprocessing']['linear_peaks']==value['postprocessing']['linear_peaks_threshold']
    assert not value['usable_for_pipeline'] and value['production_status']=='NOT_DEPLOYED'
    with pytest.raises(RuntimeFault):rt._finish_development(job['job_id'],{},files,value)
    final=rt._finish_development(job['job_id'],dict(tree_stopped=True),files,value)
    assert final['state']=='succeeded' and rt.result(job['job_id'])['binding']['input_sha256']==sha(body())
    other=rt.submit_sequence(body(),'foreign',policy.TOOL)
    with pytest.raises(RuntimeFault):rt.artifact_bytes(other['job_id'],final['artifacts'][0]['artifact_id'])
    with rt._db() as db:path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(final['artifacts'][-1]['artifact_id'],)).fetchone()[0]
    (rt.root/path).write_bytes(b'changed')
    with pytest.raises(RuntimeFault):rt.result(job['job_id'])


@pytest.mark.parametrize('error',['TOOL_FAILED','CANCELLED','TIMEOUT','OUTPUT_INVALID','INTERRUPTED'])
def test_failures_have_null_scores_and_explicit_a3_halt(rt,files,error):
    value=result(active(rt),policy.request(body()),files,dict(error_code=error,diagnostic='controlled failure',stopped_confirmed=True,exit_code=1))
    assert value['raw_scores'] is None and value['raw_record'] is None and value['failure_policy']=='A3_UNAVAILABLE_HALT'
    assert value['postprocessing']['linear_peaks'] is None and value['null_reason']==error


def test_n04_stop_wins_over_already_parsed_native_results(rt,files):
    job=active(rt);value=result(job,policy.request(body()),files,dict(error_code=None,stopped_confirmed=True,exit_code=0,image_id=policy.IMAGE))
    with rt._tx() as db:rt._stop(db,rt._job(db,job['job_id']),'cancel')
    final=rt._finish_development(job['job_id'],dict(tree_stopped=True),files,value)
    assert final['state']=='cancelled' and rt.result(job['job_id'])['raw_scores'] is None


def test_native_container_contract_and_cross_worker_ownership(rt,files):
    info=decode(files['inspect.json'])[0];inspect_contract(info,policy.TOOL)
    job=active(rt);info['Config']['Labels']=docker.labels(rt.root,job)
    assert docker.owned(rt.root,job,info)
    info['Config']['Labels']['t01.worker']='deeptmhmm-development'
    assert not docker.owned(rt.root,job,info)
    info['HostConfig']['NetworkMode']='bridge'
    with pytest.raises(RuntimeFault):inspect_contract(info,policy.TOOL)
