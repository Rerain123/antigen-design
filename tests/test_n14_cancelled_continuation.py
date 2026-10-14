import copy
import pytest
from t01_phase1_real.common import encode,RuntimeFault
from t01_phase1_real.development.workflow import continuation
from test_n14_capacity import checkpoint,full_request


def cancelled(monkeypatch):
    rt,job,ex,checked=checkpoint(monkeypatch)
    job.update(state='cancelled',stop_reason='cancel',error_code='CANCELLED')
    ex.pop('fatal_error');ex['nodes']['stability']=dict(state='cancelled',job_id='foldx-child')
    child=dict(job_id='foldx-child',tool_id='t01.real.foldx',run_id='run',state='cancelled',stop_reason='cancel')
    get=rt.get;request=rt._request_bytes
    rt.get=lambda jid:child if jid=='foldx-child' else get(jid)
    rt._request_bytes=lambda j:encode(full_request(24,214)) if j['job_id']=='foldx-child' else request(j)
    return rt,job,ex,child


def test_only_cancelled_n14_is_rerun_and_old_checkpoint_is_immutable(monkeypatch):
    rt,job,ex,child=cancelled(monkeypatch);old=copy.deepcopy(ex)
    _,_,_,rows=continuation.prepare_stability(rt,'source')
    assert 'stability' not in rows and rows['c_s1_developability']['job_id']=='n10-child' and ex==old


@pytest.mark.parametrize('fault',['live','wrong_run','wrong_tool','failed_child','not_stopped','changed_request','downstream'])
def test_cancelled_resume_rejects_unsafe_sources(monkeypatch,fault):
    rt,job,ex,child=cancelled(monkeypatch)
    if fault=='live':job['state']='running'
    elif fault=='wrong_run':child['run_id']='other'
    elif fault=='wrong_tool':child['tool_id']='other'
    elif fault=='failed_child':child['state']='failed'
    elif fault=='not_stopped':
        old=rt.execution;rt.execution=lambda jid:dict(tree_stopped=False) if jid=='foldx-child' else old(jid)
    elif fault=='changed_request':
        old=rt._request_bytes;rt._request_bytes=lambda j:b'{}' if j['job_id']=='foldx-child' else old(j)
    else:ex['nodes']['variant_report']=dict(job_id='report')
    with pytest.raises(RuntimeFault):continuation.prepare_stability(rt,'source')
