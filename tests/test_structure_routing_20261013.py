"""User-confirmed >10% routing and same-engine comparisons; fixture calculations."""
import copy
import pytest
from t01_phase1_real.common import RuntimeFault,encode,sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import revision_v2 as v,revision_contract as c,revision_structure as st
from test_expert_revision_v2 import record,observation
from test_expert_revision_v2_runtime import setup,drain
from test_s28_validation import resident_admission


def config():return v.config('routing-20261013',model_policy=st.SINGLE_MODEL_POLICY)


@pytest.mark.parametrize('length,count,engine',[
    (233,0,'af3'),(233,15,'af3'),(233,16,'af3'),
    (300,19,'af3'),(300,20,'af3'),(300,21,'af3'),(300,31,'esmfold2'),
    (100,9,'af3'),(100,10,'af3'),(100,11,'esmfold2'),
    (50,5,'af3'),(101,10,'af3'),(99,10,'esmfold2'),
    (200,20,'af3')])
def test_strict_fraction_boundary_without_absolute_count_limit(length,count,engine):
    assert st.route(length,count,config())==[engine]
    assert st.scheduled_engines(length,count,config())==[engine]


def test_old_policy_and_config_remain_distinct():
    old=v.config('old');before=copy.deepcopy(old);new=config()
    assert c.config(old)==old and c.config(new)==new
    assert st.route(233,16,old)==['af3','esmfold2']
    assert st.scheduled_engines(100,11,old)==[]
    assert old==before and sha(encode(old))!=sha(encode(new))
    assert new['policies']['s28']['supply_fallback'] is False
    new['policies']['s28']['supply_fallback']=True
    with pytest.raises(RuntimeFault,match='contract_incompatible'):c.config(new)


def test_new_policy_requires_af3_for_wt_but_preserves_historical_requests():
    from test_expert_revision_workflow import revised_body
    from t01_phase1_real.development.workflow import policy
    b=revised_body();b.update(structure=None,prediction=dict(engine='esmfold2',seed=1,timeout_seconds=600))
    b['revision_config']=v.config('old')
    assert policy.request(encode(b))['prediction']['engine']=='esmfold2'
    b['revision_config']=config()
    with pytest.raises(RuntimeFault,match='requires AF3'):policy.request(encode(b))
    b['prediction']['engine']='af3'
    assert policy.request(encode(b))['prediction']['engine']=='af3'


@pytest.mark.parametrize('count,engine',[(1,'af3'),(11,'esmfold2')])
@pytest.mark.parametrize('quality,status',[(.8,'PASS'),(.5,'PASS'),(.49,'FAIL'),(None,'NOT_ASSESSED')])
def test_only_routed_engine_can_supply_and_never_falls_back(count,engine,quality,status):
    other='esmfold2' if engine=='af3' else 'af3'
    obs={other:observation(.99)}
    if quality is not None:obs[engine]=observation(quality)
    r=record(count);v.s28(r,obs,config())
    assert r['checks']['chk_struct_quality']==status
    assert r['structure']==(obs[engine]['structure'] if quality is not None else None)
    assert r['structure_degraded'] is False
    assert v.supplier(r,obs,config())['selected']==(engine if quality is not None else None)


@pytest.mark.parametrize('length,count,engine',[(233,16,'af3'),(300,20,'af3')])
def test_new_policy_dispatches_one_engine_and_recovers_without_repeat(tmp_path,monkeypatch,resident_admission,length,count,engine):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch,length=length,count=count,model_policy=st.SINGLE_MODEL_POLICY)
    from t01_phase1_real.development.workflow import msa_reuse
    if engine=='esmfold2':monkeypatch.setattr(msa_reuse,'ready',lambda *a:pytest.fail('ESMFold must not request AF3 MSA'))
    assert drain(rt,jid,b,data,records)=='S28_ORIGINAL_PASS'
    assert [tool for tool in calls if tool in ('t01.real.af3','t01.real.esmfold2')]==['t01.real.'+engine]
    ex=copy.deepcopy(rt.execution(jid));r=records[0]
    assert ex['revision_allocations']['0']==[dict(candidate_id=r['candidate_id'],keys=['rx0_s1_'+engine])]
    planned=st.plan(records,{r['candidate_id']:r['esm_if1']},dict(reservations={}),b['revision_config'],None)
    assert planned[0]['engines']==[engine]
    assert r['evidence_supplier']=='primary' and set(r['structure_observations'])=={engine}
    # Passing fixture evidence must still reach downstream epitope prediction.
    assert 't01.real.bepipred' in calls and 't01.real.netmhc' in calls and 't01.real.epitope_map' in calls
    before=list(calls)
    assert drain(Runtime(tmp_path/'runtime'),jid,b,data,records)=='S28_ORIGINAL_PASS'
    assert calls==before and rt.execution(jid)==ex


@pytest.mark.parametrize('wt_engine,variant_engine,allowed',[
    ('af3','af3',True),('esmfold2','esmfold2',True),
    ('af3','esmfold2',False),('esmfold2','af3',False),(None,'af3',False),('af3',None,False)])
def test_different_or_unknown_engines_never_compute_geometry(monkeypatch,wt_engine,variant_engine,allowed):
    from test_expert_revision_core import fixture
    from test_expert_revision_v2 import side
    from t01_phase1_real.development.epitope_protection import compute
    _,snap,_,_=fixture(100);w=side();variant=copy.deepcopy(w)
    w['prediction_engine']=wt_engine;variant['prediction_engine']=variant_engine
    if not allowed:
        monkeypatch.setattr(compute,'geometry',lambda *a:pytest.fail('Cross-engine RMSD forbidden'))
        monkeypatch.setattr(compute,'rsa_delta',lambda *a:pytest.fail('Cross-engine RSA comparison forbidden'))
    p=v.protection('A'*100,record(),snap,w,variant,same_engine_required=True)
    assert p['structure_comparison']['allowed'] is allowed
    if not allowed:
        assert p['l3']['check_status']=='NOT_ASSESSED' and p['l3']['max_rmsd'] is None
        assert p['l2']['observation']['reason']=='SAME_ENGINE_WT_REFERENCE_REQUIRED'
        assert w['prediction_engine']==wt_engine  # original WT evidence stays untouched
    else:assert p['l3']['check_status']=='PASS'


def test_prediction_provenance_uses_registered_producer_not_source_note():
    from types import SimpleNamespace
    from t01_phase1_real.development.workflow.revision_v2_runtime import structure_engine
    jobs={'ingest':dict(job_id='ingest',tool_id='t01.real.ingest_structure'),
          'prediction':dict(job_id='prediction',tool_id='t01.real.esmfold2')}
    request=dict(structure_artifact=dict(job_id='prediction'),source_declaration=dict(note='AF3'))
    rt=SimpleNamespace(get=lambda jid:jobs[jid],_request_bytes=lambda j:encode(request))
    assert structure_engine(rt,dict(job_id='ingest'))=='esmfold2'
    request.pop('structure_artifact')
    assert structure_engine(rt,dict(job_id='ingest')) is None


def test_esm_candidate_waits_for_same_engine_wt_without_overwriting_af3(tmp_path,monkeypatch,resident_admission):
    # Widen the fixture mutation budget explicitly; production HiMat stays at 7%.
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch,length=100,count=11,model_policy=st.SINGLE_MODEL_POLICY,mutation_budget=.2)
    r=records[0]
    assert drain(rt,jid,b,data,records)=='S28_ORIGINAL_PASS'
    assert 't01.real.esmfold2' in calls and 't01.real.af3' not in calls
    p=r['protection']
    assert p['structure_comparison']==dict(wt_engine='af3',variant_engine='esmfold2',allowed=False,
                                         reason_code='SAME_ENGINE_WT_REFERENCE_REQUIRED')
    assert p['l3']['max_rmsd'] is None and 't01.real.bepipred' not in calls
    assert rt.execution(jid)['revision_v2_frozen']['wt_side']['prediction_engine']=='af3'
    from t01_phase1_real.service_api.native_report import build
    html=build({},dict(expert_revision=dict(formal_records=records)))['candidates']
    assert '未进行结构比较或后续表位预测复评' in html and '需补充原始蛋白的 ESMFold 结构' in html
