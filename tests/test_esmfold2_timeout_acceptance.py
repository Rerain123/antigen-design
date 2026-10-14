import pytest
from scripts.run_esmfold2_timeout_acceptance import REMOTE, validate

def fixture():
    identity=dict(pid=100,birth='42')
    v=dict(job=dict(state='timed_out',error_code='TIMEOUT',stop_confirmed=True,usable_for_pipeline=False),
        execution=dict(tree_stopped=True,timeout_seconds=30,resident_receipt=dict(state='timed_out',stopped_confirmed=True,process_identity=identity,process_name='owned')),
        resident_request=dict(timeout_seconds=30),native_request_started=True,cancel_file_present=False,
        observation=dict(network_restriction='seccomp-local-sockets-only-v1'),result=dict(prediction=None))
    return v,dict(active=0,process_name='owned',process_identity=identity)

def test_complete_evidence_and_payload():
    compile(REMOTE,'timeout','exec');validate(*fixture())
    assert 'rt.control(' not in REMOTE and 'time.sleep(' not in REMOTE

@pytest.mark.parametrize('damage',['cancel','not_started','state','receipt','deadline','active','identity','prediction','offline'])
def test_false_timeout_evidence_refused(damage):
    v,p=fixture()
    if damage=='cancel':v['cancel_file_present']=True
    elif damage=='not_started':v['native_request_started']=False
    elif damage=='state':v['job']['state']='succeeded'
    elif damage=='receipt':v['execution']['resident_receipt']['state']='cancelled'
    elif damage=='deadline':v['resident_request']['timeout_seconds']=600
    elif damage=='active':p['active']=1
    elif damage=='identity':p['process_identity']={}
    elif damage=='prediction':v['result']['prediction']={}
    else:v['observation']=None
    with pytest.raises(ValueError):validate(v,p)
