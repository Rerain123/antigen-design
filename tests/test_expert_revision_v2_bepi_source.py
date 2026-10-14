"""L4 consumes the actual N04 raw-result contract and pinned native artifacts."""
import copy
import pytest
from t01_phase1_real.common import RuntimeFault,decode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow.revision_v2_runtime import bp
from t01_phase1_real.development.bepipred import policy
from t01_phase1_real.development.bepipred.result import result,parse
from test_bepipred_development import files,active,body,SEQ


@pytest.fixture
def native_source(tmp_path,files):
    rt=Runtime(tmp_path/'runtime');job=active(rt)
    files['input.json']=body()
    value=result(job,policy.request(body()),files,
        dict(exit_code=0,error_code=None,stopped_confirmed=True,image_id=policy.IMAGE))
    assert value['raw_scores'] is not None and 'rule_profile' not in value['binding']
    job=rt._finish_development(job['job_id'],dict(tree_stopped=True),files,value)
    ref=dict(job_id=job['job_id'],artifact=next(a for a in job['artifacts'] if a['role']=='result'))
    return rt,job,ref,files


def test_real_raw_bepipred_binding_without_rule_profile(native_source):
    rt,job,ref,files=native_source
    scores,provenance=bp(rt,ref,SEQ,job['run_id'])
    assert scores==[r['ensemble_probability'] for r in parse(files,SEQ)['raw_scores']]
    assert provenance==dict(execution=job['execution_profile'],rule=None,parameters={})
    # The BepiPred fix does not weaken the scored N12 source contract.
    from t01_phase1_real.development.esm_if1.source import registered
    with rt._db() as db:
        with pytest.raises(KeyError):registered(rt,db,ref['artifact'],policy.TOOL)


@pytest.mark.parametrize('damage',['input','sequence','request','execution','profile','rule','scores','record','runtime','duplicate','foreign'])
def test_bepi_identity_and_published_observation_guards(native_source,monkeypatch,damage):
    rt,job,ref,files=native_source;original=rt._registered_result_artifact
    def changed(*args):
        j,raw,value=original(*args);value=copy.deepcopy(value)
        binding=value['binding']
        if damage=='input':binding['input_sha256']='0'*64
        elif damage=='sequence':binding['sequence_sha256']='0'*64
        elif damage=='request':binding['request_id']='foreign'
        elif damage=='execution':binding['execution_identity']='foreign'
        elif damage=='profile':binding['execution_profile']['sha256']='0'*64
        elif damage=='rule':binding['rule_profile']={'id':'foreign'}
        elif damage=='scores':value['raw_scores'][0]['ensemble_probability']=.99
        elif damage=='record':value['raw_record']['embedding_shape']=[1,1]
        elif damage=='runtime':value['runtime_observation']['backend']='foreign'
        elif damage=='duplicate':value['raw_artifacts'].append(value['raw_artifacts'][0])
        elif damage=='foreign':value['raw_artifacts'][0]['artifact']['artifact_id']='foreign'
        return j,raw,value
    monkeypatch.setattr(rt,'_registered_result_artifact',changed)
    with pytest.raises(RuntimeFault):bp(rt,ref,SEQ,job['run_id'])


@pytest.mark.parametrize('damage',['run','sequence','job','native_hash','executed_request'])
def test_bepi_scope_and_actual_artifact_hash_guards(native_source,damage):
    rt,job,ref,files=native_source;seq=SEQ;run=job['run_id']
    if damage=='run':run='foreign'
    elif damage=='sequence':seq='A'*len(SEQ)
    elif damage=='job':
        other=rt.submit_sequence(body(),'other',policy.TOOL)
        with rt._tx() as db:
            running=dict(other,state='running');rt._store(db,running,other,'fixture-start')
            rt._store(db,dict(running,state='succeeded'),running,'fixture-complete')
        ref=dict(ref,job_id=other['job_id'])
    else:
        path='input.json' if damage=='executed_request' else 'output/result/raw_output.csv'
        item=next(r for r in rt.result(job['job_id'])['raw_artifacts'] if r['path']==path)
        with rt._db() as db:
            relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(item['artifact']['artifact_id'],)).fetchone()[0]
        (rt.root/relative).write_bytes(b'changed')
    with pytest.raises(RuntimeFault):bp(rt,ref,seq,run)


def test_missing_or_unfinished_predictor_preserves_unknown(native_source):
    rt,job,ref,files=native_source
    assert bp(rt,None,SEQ,job['run_id'])==(None,None)
    other=rt.submit_sequence(body(),'unfinished',policy.TOOL)
    assert bp(rt,dict(ref,job_id=other['job_id']),SEQ,job['run_id'])==(None,None)
