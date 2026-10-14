"""Defined epitope permissions and complete, bounded regeneration decisions."""
import copy
import pytest

from t01_phase1_real.common import RuntimeFault,encode
from t01_phase1_real.development.workflow import design_rounds as rounds, policy as flow
from t01_phase1_real.development.design_backend import permissions
from t01_phase1_real.development.proteinmpnn import policy as mpnn
from test_design_backend_development import request,receipts,scales
from test_proteinmpnn_development import request as native_request


def result(n,passed=False):
    return dict(records=[dict(sample_number=i) for i in range(1,n+1)]),dict(
        engineering_rules=dict(records=[dict(sample_number=i,passed=passed) for i in range(1,n+1)]))


@pytest.mark.parametrize('count,temp',rounds.ROUNDS)
def test_native_expert_rounds(count,temp):
    assert mpnn.request(encode(native_request(n_designs=count,sampling_temperature=temp)))['n_designs']==count


@pytest.mark.parametrize('count,temp',[(65,.5),(48,.1),(24,.3),(64,.3),(True,.1)])
def test_invalid_rounds(count,temp):
    with pytest.raises(RuntimeFault):mpnn.request(encode(native_request(n_designs=count,sampling_temperature=temp)))


def test_missing_and_passed_are_never_all_eliminated():
    g,s=result(24)
    assert rounds.disposition(g,s)['status']=='ALL_REJECTED'
    s['engineering_rules']['records'][0]['passed']=None
    assert rounds.disposition(g,s)['status']=='VALIDATION_UNAVAILABLE'
    s['engineering_rules']['records'][0]['passed']=True
    assert rounds.disposition(g,s)['review_pool']==[1]
    s['engineering_rules']['records'].pop()
    with pytest.raises(RuntimeFault):rounds.disposition(g,s)
    g,s=result(24);s['engineering_rules']['records'][0]['passed']='false'
    with pytest.raises(RuntimeFault):rounds.disposition(g,s)


def test_round_request_replay_baseline_and_136_limit(monkeypatch):
    class Runtime:
        def __init__(self):self.jobs={};self.results={};self.requests={}
        def get(self,j):return self.jobs[j]
        def result(self,j):return self.results[j]
        def _request_bytes(self,j):return encode(self.requests[j['job_id']])
    rt=Runtime();rows={}
    for index,(count,temp) in enumerate(rounds.ROUNDS):
        prefix='' if index==0 else f'retry{index}_'
        for kind in ('design','rescore','design_audit'):
            name=prefix+kind;rows[name]=dict(job_id=name,state='succeeded')
            rt.jobs[name]=dict(job_id=name,artifacts=[dict(role='result',job_id=name)])
        g,s=result(count);rt.results[prefix+'design']=dict(generation=g);rt.results[prefix+'rescore']=s
        rt.requests[prefix+'design']=native_request(n_designs=count,sampling_temperature=temp)
        fact=dict(status='ALL_REJECTED',records=s['engineering_rules']['records'],review_pool=[],
            rejected=list(range(1,count+1)),unavailable=[],source_jobs=dict(design=dict(job_id=prefix+'design',
                artifact=rt.jobs[prefix+'design']['artifacts'][0])))
        rows[prefix+'validation']=dict(state='succeeded',fact=fact,
            validation_source=dict(workflow_job_id='flow',node=prefix+'validation'))
    from t01_phase1_real.development.workflow import validation
    monkeypatch.setattr(validation,'verified_fact',lambda rt,jid,name:rows[name]['fact'])
    rt.requests['rescore']=dict(n11_artifact={},baseline_artifact=None,sample_numbers=list(range(1,25)))
    rt.requests['design_audit']=dict(upstream=dict(n11=None,esm_if1=None),sample_numbers=list(range(1,25)))
    for index,count,temp in ((1,48,.3),(2,64,.5)):
        a,_=rounds.request(rt,{},rows,f'retry{index}_design')
        assert (a['n_designs'],a['sampling_temperature'])==(count,temp)
        assert a['constraints']==rt.requests['design']['constraints']
        assert rounds.request(rt,{},copy.deepcopy(rows),f'retry{index}_design')[0]==a
        b,_=rounds.request(rt,{},rows,f'retry{index}_rescore')
        assert len(b['sample_numbers'])==count and b['baseline_artifact']['job_id']=='rescore'
        c,_=rounds.request(rt,{},rows,f'retry{index}_design_audit')
        assert c['upstream']['n11']['job_id']==f'retry{index}_design'
    summary=rounds.summary(rt,rows)
    assert summary['exhausted'] and summary['total_generated']==136
    assert rounds.active(rows)['design']['job_id']=='retry2_design'
    assert rows['design']['job_id']=='design'
    rows['design']['confirmation']={'decision':True,'audit_job_id':'same-audit'}
    assert rounds.active(rows)['design']['confirmation']==rows['design']['confirmation']
    assert 'confirmation' not in rows['retry2_design']


def test_order_retries_precede_selection_only_in_current_backend_mode():
    order=flow.order(dict(engineering_design='BACKEND_EVIDENCE_V1'))
    assert order.index('design_audit')<order.index('retry1_design')<order.index('retry2_design_audit')<order.index('preselection')
    assert not set(rounds.NAMES)&set(flow.order(dict(m1_test={})))


def test_e4_is_single_contact_fixed_e3_remains_restricted_and_e2_is_preserved():
    e4=dict(start=3,end=3,sequence_position=3,epitope_level='E4-contact',evidence_source='IEDB',
        source_iedb_id='10',coordinate_sha256='c'*64,
        evidence_provenance=dict(source_iedb_id='10',reference_id='11',source_artifact={'sha256':'a'*64}))
    e3=dict(e4,start=2,end=5,epitope_level='E3-region')
    values=dict(epitope_map=dict(epitopes=dict(b_cell_epitope_map=dict(regions=[e3,e4]),
        b_cell_antigenic_hotspot_map=dict(hotspots=[dict(start=7,end=8)]))))
    p=permissions.assemble(request(),values,receipts(values),scales())
    assert p['fixed_positions']==[3]
    assert 'S27_E2_CONSENSUS' in p['per_residue'][6]['reasons']
    assert not p['scientific_release']
    e4['end']=4
    with pytest.raises(RuntimeFault):permissions.assemble(request(),values,receipts(values),scales())


def test_retry_child_admission_is_durable_idempotent_and_cancel_fenced(tmp_path,monkeypatch):
    from t01_phase1_real.development import Runtime
    from t01_phase1_real.development.workflow import service
    from t01_phase1_real.development.proteinmpnn import source
    from t01_phase1_real.common import now,decode
    from test_local_workflow import body
    rt=Runtime(tmp_path/'runtime');b=body();b['engineering_design']='BACKEND_EVIDENCE_V1'
    parent=rt.submit_workflow(encode(b),'rounds');jid=parent['job_id']
    with rt._tx() as db:
        old=rt._job(db,jid);j=dict(old,state='running',started_at=now())
        rt._store(db,j,old,'fixture')
        rt._execution_store(db,jid,dict(nodes={},started_at=now(),phase='scheduling',dispatcher=None))
    # Native computation is excluded; exercise real admission/transaction/restart.
    monkeypatch.setattr(source,'sources',lambda *a,**k:None)
    req=native_request(sequence=b['protein_sequence'],n_designs=48,sampling_temperature=.3)
    first=service._create_child(rt,jid,'retry1_design',req)
    assert rt.get(first)['run_id']==parent['run_id']
    restarted=Runtime(tmp_path/'runtime')
    assert service._create_child(restarted,jid,'retry1_design',req)==first
    assert decode(restarted._request_bytes(restarted.get(first)))['n_designs']==48
    with rt._tx() as db:rt._stop(db,rt._job(db,jid),'cancel')
    assert service._create_child(restarted,jid,'retry2_design',native_request(n_designs=64,sampling_temperature=.5)) is None
    service.stop_children(restarted,jid)
    assert restarted.get(first)['state']=='cancelled'
