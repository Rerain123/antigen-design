import pytest
from scripts.run_esmfold2_cancel_acceptance import REMOTE, validate, process_probe

def fixture():
    identity=dict(pid=100,birth='42')
    value=dict(job=dict(state='cancelled',stop_confirmed=True,attempt_id='a',usable_for_pipeline=False),
        execution=dict(tree_stopped=True,resident_target='/target',resident_receipt=dict(stopped_confirmed=True,process_identity=identity,process_name='owned')),
        inference_started=True,recovery=dict(before=dict(attempt_id='a',target='/target',process_identity=identity)),result=dict(prediction=None))
    return value,dict(active=0,process_name='owned',process_identity=identity)

def test_probe_selects_persistent_registry_before_import():
    v,_=fixture();code=process_probe(v['execution']['resident_receipt'])
    compile(code,'probe','exec')
    assert code.index("os.environ['T01_PROCESS_REGISTRY']") < code.index('from t01_phase1_real.process_control.posix import')
    assert '/var/lib/t01/resident/esmfold2/.processes' in code
    assert 'create=False' in code and "record['leader']==expected" in code

def test_payload_compiles_and_complete_evidence_passes():
    compile(REMOTE,'remote','exec');validate(*fixture())

@pytest.mark.parametrize('damage',['active','name','attempt','inference','stop','prediction','gate'])
def test_incomplete_or_cross_execution_evidence_refused(damage):
    v,p=fixture()
    if damage=='active':p['active']=1
    elif damage=='name':p['process_name']='other'
    elif damage=='attempt':v['job']['attempt_id']='other'
    elif damage=='inference':v['inference_started']=False
    elif damage=='stop':v['execution']['tree_stopped']=False
    elif damage=='prediction':v['result']['prediction']={}
    else:v['job']['usable_for_pipeline']=True
    with pytest.raises(ValueError):validate(v,p)
