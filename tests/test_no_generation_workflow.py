"""A completed all-fixed preparation is not native candidate generation."""
import pytest
from t01_phase1_real.common import encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import service,m1,reporting
from test_local_workflow import body


def test_completed_all_fixed_result_records_no_generation(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);parent=rt.submit_workflow(encode(body()),'all-fixed')
    with rt._tx() as db:rt._execution_store(db,parent['job_id'],dict(nodes={}))
    monkeypatch.setattr(rt,'result',lambda _:dict(generation=dict(
        status='not_generated_no_designable_positions',records=[],reason_code='NO_DESIGNABLE_POSITIONS')))
    service._record(rt,parent['job_id'],'design',dict(state='succeeded',job_id='n11',reason_code=None))
    row=rt.execution(parent['job_id'])['nodes']['design']
    assert row['generated_count']==0 and row['reason_code']=='NO_DESIGNABLE_POSITIONS'
    fact=reporting.design_fact(dict(design=row))
    assert fact['status']=='NOT_EXECUTED' and '未执行' in reporting.text(fact)


@pytest.mark.parametrize('name',['rescore','design_audit','variant_report'])
def test_no_generation_does_not_request_nonexistent_samples(name):
    rows=dict(design=dict(state='succeeded',job_id='n11',
        generation_status='not_generated_no_designable_positions',generated_count=0))
    assert m1.request_for(None,body(),rows,name)==(None,'NO_DESIGNABLE_POSITIONS')


def test_successful_generated_result_still_reports_executed():
    fact=reporting.design_fact(dict(design=dict(state='succeeded',job_id='n11',
        generation_status='generated_unreviewed',generated_count=24)))
    assert fact['status']=='EXECUTED'


def test_public_status_projection_retains_no_generation_reason():
    fact=reporting.design_fact(dict(design=dict(state='succeeded',job_id='n11',
        reason_code='NO_DESIGNABLE_POSITIONS')))
    assert fact['status']=='NOT_EXECUTED' and '候选设计未执行' in reporting.text(fact)
