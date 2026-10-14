"""Synthetic clock/transaction tests; no native computation or live jobs."""
import copy
import importlib.util
from pathlib import Path
import pytest
from t01_phase1_real.common import RuntimeFault,encode,sha,new_id
from t01_phase1_real.development import Runtime
from test_expert_revision_workflow import revised_body
from t01_phase1_real.development.workflow import revision_v2 as v

spec=importlib.util.spec_from_file_location('compensation',Path(__file__).parents[1]/'scripts/controller_time_compensation.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def evidence(job,ex):
    return dict(authorization=m.AUTHORIZATION,job_id=job['job_id'],run_id=job['run_id'],
                checkpoint_sha256=sha(encode(ex)),outage_start='2026-10-08T02:00:00Z',
                outage_end='2026-10-08T05:00:00Z')


@pytest.mark.parametrize('damage',[None,'negative','outside','identity','checkpoint'])
def test_compensates_only_proven_outage_not_all_elapsed_time(damage):
    job=dict(job_id='old',run_id='run',finished_at='2026-10-08T08:10:00Z')
    ex=dict(started_at='2026-10-08T00:00:00Z',confirmation_wait_seconds=600)
    ev=evidence(job,ex)
    if damage=='negative':ev['outage_end']='2026-10-08T01:00:00Z'
    if damage=='outside':ev['outage_end']='2026-10-08T09:00:00Z'
    if damage=='identity':ev['job_id']='other'
    if damage=='checkpoint':ev['checkpoint_sha256']='changed'
    if damage:
        with pytest.raises(RuntimeFault):m.remaining_time(job,ex,{'timeout_seconds':28800},ev)
    else:
        clock=m.remaining_time(job,ex,{'timeout_seconds':28800},ev)
        assert clock['remaining_seconds']==10800
        assert clock['consumed_effective_seconds']==18000


def fixture(tmp_path):
    rt=Runtime(tmp_path/'runtime');body=revised_body();body['revision_config']=v.config('compensation');body['timeout_seconds']=28800
    source=rt.submit_workflow(encode(body),'source');jid=source['job_id']
    with rt._tx() as db:
        j=rt._job(db,jid);rt._store(db,dict(j,state='running'),j,'fixture-start')
        rt._stop(db,rt._job(db,jid),'timeout')
        j=rt._job(db,jid)
        source=dict(j,state='timed_out',stop_reason='timeout',error_code='TIMEOUT',
                    started_at='2026-10-08T00:00:00Z',finished_at='2026-10-08T08:10:00Z')
        rt._store(db,source,j,'fixture')
        old=dict(nodes={'design':{'confirmation':{'decision':True,'job_id':jid}}},
                 started_at=source['started_at'],confirmation_wait_seconds=600,tree_stopped=True,
                 revision_ledger={'costs':12},revision_v2_frozen={'frozen':True},revision_bindings={'ids':'stable'})
        rt._execution_store(db,jid,old)
    source=rt.get(jid);body=m.policy.request(rt._request_bytes(source))
    source=rt.get(jid);ev=evidence(source,old)
    prepared=(source,body,old,copy.deepcopy(old['nodes']),m.remaining_time(source,old,body,ev),{})
    return rt,source,ev,prepared


def test_same_run_new_parent_preserves_sources_and_budget_and_is_idempotent(tmp_path):
    rt,source,ev,prepared=fixture(tmp_path);old=copy.deepcopy(rt.execution(source['job_id']))
    fresh=m.create(rt,source['job_id'],ev,prepared);ex=rt.execution(fresh['job_id'])
    assert fresh['job_id']!=source['job_id'] and fresh['run_id']==source['run_id']
    assert rt.get(source['job_id'])==source and rt.execution(source['job_id'])==old
    assert m.create(rt,source['job_id'],ev,prepared)==fresh
    before=m.policy.request(rt._request_bytes(source));after=m.policy.request(rt._request_bytes(fresh))
    assert after.pop('timeout_seconds')==10800
    before.pop('timeout_seconds');assert before==after
    for key in ('nodes','revision_ledger','revision_v2_frozen','revision_bindings'):assert ex[key]==old[key]
    assert ex['confirmation_wait_seconds']==0 and ex['started_at']==fresh['started_at']
    assert ex['continuation']['clock']['consumed_effective_seconds']==18000
    assert ex['continuation']['scientific_budgets_reset'] is False
    bad=dict(ev,outage_end='2026-10-08T06:00:00Z')
    with pytest.raises(RuntimeFault):m.create(rt,source['job_id'],bad,prepared)


def test_changed_checkpoint_blocks_creation(tmp_path):
    rt,source,ev,prepared=fixture(tmp_path)
    with rt._tx() as db:
        changed=rt._execution(db,source['job_id']);changed['revision_ledger']['costs']=13
        rt._execution_store(db,source['job_id'],changed)
    with pytest.raises(RuntimeFault):m.create(rt,source['job_id'],ev,prepared)
