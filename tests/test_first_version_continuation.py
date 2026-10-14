"""First-version gaps preserve real failures and still assemble available facts."""
import copy
import pytest

from t01_phase1_real.common import encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import service,m1
from test_local_workflow import body


@pytest.mark.parametrize('name',['rep1_prediction','rep3_prediction','developability','rep2_developability','stability'])
def test_only_operational_failures_of_optional_calculations_continue(name):
    b=dict(engineering_design='BACKEND_EVIDENCE_V1')
    assert service.recoverable_child_failure(b,name,dict(state='failed',error_code='TOOL_FAILED'))
    for error in ('HASH_MISMATCH','OUTPUT_INVALID','FORBIDDEN','PROFILE_NOT_APPROVED','CANCELLED'):
        assert not service.recoverable_child_failure(b,name,dict(state='failed',error_code=error))
    assert not service.recoverable_child_failure({},name,dict(state='failed',error_code='TOOL_FAILED'))
    assert not service.recoverable_child_failure(b,'prediction',dict(state='failed',error_code='TOOL_FAILED'))


@pytest.mark.parametrize('crash',[False,True])
def test_failed_n10_is_preserved_through_resume_and_delivery(tmp_path,monkeypatch,crash):
    rt=Runtime(tmp_path);b=body();b['engineering_design']='BACKEND_EVIDENCE_V1'
    b['analysis']['developability']=dict(target_ph=None,target_ph_range=[4.,8.],dimension_weights=None,timeout_seconds=30)
    parent=rt.submit_workflow(encode(b),'first-version');original=rt.dispatch
    def dispatch(jid):
        if rt.get(jid)['tool_id']=='t01.real.developability':
            rt._development_fault='compute_failure'
            try:result=original(jid)
            finally:rt._development_fault=None
            if crash:raise KeyboardInterrupt()
            return result
        return original(jid)
    monkeypatch.setattr(rt,'dispatch',dispatch)
    if crash:
        with pytest.raises(KeyboardInterrupt):rt.dispatch(parent['job_id'])
        monkeypatch.undo();end=rt.recover(parent['job_id'])
    else:end=rt.dispatch(parent['job_id'])
    assert end['state']=='succeeded'
    snap=rt.workflow(parent['job_id']);nodes=snap['nodes']
    assert nodes['developability']['state']=='failed'
    assert nodes['local_delivery']['state']=='succeeded'
    assert snap['scientific_gate']=='CLOSED' and not snap['usable_for_pipeline']
    delivery=rt.result(nodes['local_delivery']['job_id'])
    report=next(r['artifact'] for r in delivery['raw_artifacts'] if r['path']=='output/report.md')
    assert b'TOOL_FAILED' in rt.artifact_bytes(nodes['local_delivery']['job_id'],report['artifact_id'])


class Facts:
    def get(self,jid):
        return dict(job_id=jid,artifacts=[dict(role='diagnostic' if jid=='stability' else 'result',job_id=jid)])


def inputs():
    b=body();b['engineering_design']='BACKEND_EVIDENCE_V1'
    b['analysis']['developability']=dict(target_ph=None,target_ph_range=[4.,8.],dimension_weights=None,timeout_seconds=30)
    record=dict(sample_number=1,id='sample-1',sequence=b['protein_sequence'],mutations=[])
    rows={n:dict(state='succeeded',job_id=n) for n in ('design','design_audit','structure','protection')}
    rows['preselection']=dict(state='succeeded',fact=dict(kind='N12_REPRESENTATIVE_PRESELECTION',sample_numbers=[1],selected=[record]))
    rows['rep1_prediction']=dict(state='failed',job_id='rep1_prediction',reason_code='TOOL_FAILED')
    rows['rep1_structure']=dict(state='skipped',job_id=None,reason_code='VARIANT_PREDICTION_UNAVAILABLE_S28_WARNING')
    return b,rows


def test_failed_prediction_does_not_dereference_absent_structure():
    b,rows=inputs();rt=Facts()
    assert m1.request_for(rt,b,rows,'rep1_structure')==(None,'VARIANT_PREDICTION_UNAVAILABLE_S28_WARNING')
    req,reason=m1.request_for(rt,b,rows,'rep1_developability')
    assert reason is None and req['structure_input']['state']=='not_provided'
    assert req['structure_input']['artifact'] is None
    req,_=m1.request_for(rt,b,rows,'protection')
    assert req['pairs'][0]['variant']['structure'] is None


@pytest.mark.parametrize('state',['failed','skipped'])
def test_missing_foldx_keeps_available_candidate_facts_in_base_report(state):
    b,rows=inputs();rows['stability']=dict(state=state,job_id='stability' if state=='failed' else None)
    req,reason=m1.request_for(Facts(),b,rows,'variant_report')
    assert reason is None and req['upstream']['design_audit']['job_id']=='design_audit'
    assert req['foldx_bindings']==[] and 'm1_test' not in req
    assert req['n13_source']['job_id']=='protection'
    assert bool(req['upstream']['foldx'])==(state=='failed')
    legacy=copy.deepcopy(b);legacy.pop('engineering_design');legacy['m1_test']={}
    assert m1.request_for(Facts(),legacy,rows,'variant_report')[1]=='N13_OR_N14_NOT_COMPLETE'


def test_codon_does_not_read_a_skipped_report():
    b,rows=inputs()
    assert m1.request_for(Facts(),b,rows,'codon')==(None,'N15_NOT_COMPLETE')
