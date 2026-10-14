import copy
import pytest
from t01_phase1_real.common import RuntimeFault
from t01_phase1_real.development import n12_prediction_evidence as adapter

@pytest.fixture
def setup(monkeypatch):
    row=dict(sample_number=1,sequence='ACDEFGHIK',mutations=[],score=-2.0)
    body=dict(sample_numbers=[1],n11_artifact={'id':'n11'},structure_artifact={'id':'wt'})
    value=dict(binding={},execution={},scoring=dict(records=[row]),baseline={},engineering_rules=dict(threshold=.2,records=[dict(sample_number=1,passed=False)]),usable_for_pipeline=False,automatic_handoff=False)
    fresh=copy.deepcopy(value);files={'native/payload':b'verified'};calls=[]
    monkeypatch.setattr(adapter.policy,'artifact',lambda r:None)
    monkeypatch.setattr(adapter.policy,'request',lambda r:None)
    monkeypatch.setattr(adapter,'registered',lambda *a:({'run_id':'same-run'},None,value,body,files))
    source_calls=[]
    def source_check(*args,**kwargs):
        source_calls.append((args,kwargs))
        return {'native/payload':b'verified'},{}
    monkeypatch.setattr(adapter,'sources',source_check)
    monkeypatch.setattr(adapter,'rebuild',lambda *a:fresh)
    def prediction(*args,**kwargs):
        calls.append((args,kwargs));return {'prediction_job_id':'prediction'}
    monkeypatch.setattr(adapter,'verified_prediction',prediction)
    return value,fresh,files,calls,source_calls

def test_binds_exact_variant_and_preserves_exclusion(setup):
    value,_,_,calls,source_calls=setup;before=copy.deepcopy(value)
    result=adapter.inspect(None,None,{},1,'prediction','Homo sapiens')
    assert source_calls[0][1]=={'expected_run_id':'same-run'}
    assert calls[0][0][2:]==('prediction','ACDEFGHIK','Homo sapiens','same-run')
    assert calls[0][1]=={'include_quality':True}
    assert result['r35_original']['passed'] is False and result['validation'] is None
    assert result['usable_for_pipeline'] is False and result['automatic_handoff'] is False
    assert result['scientific_gate']=='CLOSED'
    assert result['engine_selection']=='EXPLICIT_ENGINEERING_ONLY_NOT_R04'
    assert value==before

@pytest.mark.parametrize('damage',['input','score','gate','sample','failed'])
def test_invalid_scoring_cannot_link_prediction(setup,damage):
    value,fresh,files,calls,_=setup
    sample=1
    if damage=='input':files['native/payload']=b'tampered'
    elif damage=='score':value['scoring']['records'][0]['score']=-3
    elif damage=='gate':value['usable_for_pipeline']=True
    elif damage=='sample':sample=2
    else:
        fresh['scoring']['records'][0]['score']=None
        value['scoring']['records'][0]['score']=None
    with pytest.raises(RuntimeFault):adapter.inspect(None,None,{},sample,'prediction','Homo sapiens')
    assert calls==[]

def test_cross_run_or_upstream_provenance_failure_is_fail_closed(setup,monkeypatch):
    _,_,_,calls,_=setup
    def reject(*args,**kwargs):
        raise RuntimeFault('FORBIDDEN','N11/ESM-IF1 source belongs to another run')
    monkeypatch.setattr(adapter,'sources',reject)
    with pytest.raises(RuntimeFault) as exc:
        adapter.inspect(None,None,{},1,'prediction','Homo sapiens')
    assert exc.value.code=='FORBIDDEN'
    assert calls==[]

def test_prediction_provenance_failure_is_fail_closed(setup,monkeypatch):
    _,_,_,calls,_=setup
    def reject(*args,**kwargs):
        raise RuntimeFault('FORBIDDEN','Prediction must be a successful task in the current run')
    monkeypatch.setattr(adapter,'verified_prediction',reject)
    with pytest.raises(RuntimeFault) as exc:
        adapter.inspect(None,None,{},1,'prediction','wrong host')
    assert exc.value.code=='FORBIDDEN'
    assert calls==[]

def test_automatic_handoff_cannot_be_reopened(setup):
    value,_,_,calls,_=setup
    value['automatic_handoff']=True
    with pytest.raises(RuntimeFault):
        adapter.inspect(None,None,{},1,'prediction','Homo sapiens')
    assert calls==[]
