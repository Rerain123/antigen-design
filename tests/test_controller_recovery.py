"""Controller failure recovery uses synthetic jobs, never native models."""
import copy
from contextlib import contextmanager
from types import SimpleNamespace
import threading
import pytest
from t01_phase1_real.common import RuntimeFault,encode,sha
from t01_phase1_real.service_api.app import Service
from t01_phase1_real.service_api import controller_recovery as upgrade
from t01_phase1_real.development.epitope_protection import source


@pytest.mark.parametrize('available',[False,True])
@pytest.mark.parametrize('damage',[None,'receipt','snapshot'])
def test_map_replay_distinguishes_failed_diagnostic_from_success(monkeypatch,available,damage):
    state='available' if available else 'upstream_unavailable'
    req={'netmhc_input':dict(state=state,artifact={'job_id':'mhc'},reason_code=None if available else 'TIMEOUT')}
    receipts={'netmhc':dict(state=state,upstream_error=None if available else 'TIMEOUT')}
    value=dict(epitopes={},blast_similarity={},blast_input={},execution={'source_receipts':copy.deepcopy(receipts)})
    native={'input/netmhc-result.json':b'prediction'} if available else {}
    if damage=='receipt':value['execution']['source_receipts']={}
    if damage=='snapshot':native['input/netmhc-result.json']=b'corrupted'
    class RT:
        def _job(self,*a):return {'job_id':'map'}
        def _epitope_sources(self,*a):return {},receipts
    monkeypatch.setattr(source,'raw_files',lambda *a:native)
    from t01_phase1_real.development.epitope_map import result
    monkeypatch.setattr(result,'_parse',lambda *a:value)
    monkeypatch.setattr(source,'registered',lambda *a,**kw:({'input/netmhc-result.json':b'prediction'},{},
        {'netmhc':{'state':'available' if available else 'failed'}}))
    files={'input/epitope_map-request.json':encode(req)}
    body=dict(protein_sequence='A'*20,upstream={'epitope_map':{'job_id':'map'}})
    if damage:
        with pytest.raises(RuntimeFault):source.side_enrich(RT(),None,body,files,{'epitope_map':value},{'epitope_map':{}})
    else:
        # No KeyError for a diagnostic; no failed prediction bytes are consumed.
        if available:
            native['input/netmhc-result.json']=encode({})
            monkeypatch.setattr(source,'registered',lambda *a,**kw:({'input/netmhc-result.json':encode({})},{},{'netmhc':{'state':'available'}}))
        out={'epitope_map':{}}
        source.side_enrich(RT(),None,body,files,{'epitope_map':value},out)
        assert out['epitope_map']['predictors']['netmhc']['state']==('available' if available else 'failed')


class DriverRuntime:
    def __init__(self,failures):self.failures=failures;self.calls=0;self.ex={};self.state='running'
    def get(self,jid):return dict(state=self.state,stop_reason=None)
    def execution(self,jid):return copy.deepcopy(self.ex)
    @contextmanager
    def _tx(self):yield None
    def _execution(self,*a):return copy.deepcopy(self.ex)
    def _execution_store(self,db,jid,value):self.ex=copy.deepcopy(value)
    def recover(self,jid):
        self.calls+=1
        if self.calls<=self.failures:raise KeyError('sensitive request text must not be logged')
        self.state='succeeded';return self.get(jid)


@pytest.mark.parametrize('failures,calls,status',[(1,2,'recovered'),(10,3,'blocked')])
def test_driver_retries_existing_identity_and_persists_failure(monkeypatch,caplog,failures,calls,status):
    from t01_phase1_real.service_api import app
    monkeypatch.setattr(app.time,'sleep',lambda _:None)
    rt=DriverRuntime(failures);service=Service.__new__(Service)
    service.config=SimpleNamespace(dispatch_start_delay_seconds=0)
    service.runtime=lambda _:rt;service._lock=threading.RLock();service._scheduled={('owner','job')}
    service._child_registration_pending=lambda *a:False
    service._drive(SimpleNamespace(principal_id='owner'),'job',True)
    assert rt.calls==calls and rt.ex['controller_fault']['status']==status
    assert rt.ex['controller_fault']['scientific_jobs_retried']==0 and not service._scheduled
    assert 'sensitive request text' not in caplog.text


def test_native_collection_does_not_wait_for_parent_replay_or_extend_deadline(monkeypatch):
    from t01_phase1_real.development.workflow import confirmation
    clock=[10];monkeypatch.setattr(confirmation,'elapsed',lambda _:clock[0])
    rows={'one':dict(job_id='child',origin='NEW_EXECUTION',state='running')}
    parent=dict(job_id='parent',run_id='run',state='running',stop_reason=None)
    child=dict(job_id='child',run_id='run',state='running')
    class RT:
        calls=[]
        def get(self,jid):return parent if jid=='parent' else child
        def execution(self,jid):return dict(nodes=rows,dispatcher=None)
        def _request_bytes(self,job):return encode({'timeout_seconds':20})
        def recover(self,jid):self.calls.append(jid);return child
    rt=RT()
    assert Service._reconcile_active_children(rt,'parent') and rt.calls==['child']
    child['state']='succeeded'
    assert not Service._reconcile_active_children(rt,'parent')
    child['state']='running';clock[0]=21
    assert not Service._reconcile_active_children(rt,'parent') and rt.calls==['child']
    clock[0]=10;child['run_id']='foreign'
    with pytest.raises(RuntimeFault):Service._reconcile_active_children(rt,'parent')


def test_owner_status_exposes_controller_failure_instead_of_running(tmp_path):
    from test_real_service_api import credentials,principal,ServiceConfig,body
    service=Service(ServiceConfig(runtime_root=tmp_path/'status'),credentials())
    owner=principal(service.credentials);rt=service.runtime(owner)
    try:
        job=rt.submit_workflow(encode(body()),'stalled');jid=job['job_id']
        service.store.register_submission(owner,'stalled','fingerprint',jid)
        with rt._tx() as db:
            old=rt._job(db,jid);rt._store(db,dict(old,state='running'),old,'fixture')
            rt._execution_store(db,jid,dict(nodes={}))
        Service._controller_fault(rt,jid,KeyError('private'),3)
        value=service.status(owner,jid)
        assert value['state']=='controller_error' and value['terminal'] is False
        assert value['controller']['code']=='CONTROLLER_RECONCILIATION_ERROR'
        assert 'private' not in str(value['controller'])
        from t01_phase1_real.service_api.himat import HiMatIntegration
        hi=HiMatIntegration.__new__(HiMatIntegration);hi.service=service;hi.is_himat=lambda _:True
        assert hi.check(owner,jid)['controller']==value['controller']
    finally:service.shutdown()


def test_upgrade_receipt_cannot_cover_a_different_job_or_profile():
    old=dict(id='controller',version='1',sha256='a'*64);new=dict(old,sha256='b'*64)
    job=dict(job_id='job',run_id='run',execution_profile=old,request_artifact={'sha256':'c'*64})
    receipt=dict(job_id='job',run_id='run',from_profile=old,to_profile=new,request_sha256='c'*64,
        authorization='USER_REQUESTED_CONTROLLER_REPAIR_20261008',checkpoint_sha256='d'*64)
    assert upgrade.accepted(job,{},old) and not upgrade.accepted(job,{},new)
    assert upgrade.accepted(job,{'controller_upgrade':receipt},new)
    for key in ('job_id','run_id','request_sha256','authorization','from_profile','to_profile'):
        bad=copy.deepcopy(receipt);bad[key]='different'
        assert not upgrade.accepted(job,{'controller_upgrade':bad},new)


@pytest.mark.parametrize('damage',[None,'checkpoint','dispatcher','stop','child'])
def test_operator_upgrade_preserves_identity_budget_and_requires_quiescence(tmp_path,damage):
    from t01_phase1_real.development import Runtime
    from test_local_workflow import body
    rt=Runtime(tmp_path/'runtime');job=rt.submit_workflow(encode(body()),'upgrade');jid=job['job_id']
    with rt._tx() as db:
        old=rt._job(db,jid);rt._store(db,dict(old,state='running'),old,'fixture')
        ex=dict(nodes={},started_at='2026-10-08T01:00:00Z',revision_ledger={'spent':10})
        if damage=='dispatcher':ex['dispatcher']={'pid':1}
        if damage=='stop':
            old=rt._job(db,jid);rt._store(db,dict(old,stop_reason='cancel'),old,'fixture')
        if damage=='child':ex['nodes']={'child':dict(job_id=jid)}
        rt._execution_store(db,jid,ex)
    original=rt.get(jid);target=dict(original['execution_profile'],sha256='b'*64)
    checkpoint=sha(encode(ex)) if damage!='checkpoint' else 'c'*64
    if damage:
        with pytest.raises(RuntimeFault):upgrade.authorize(rt,jid,target,checkpoint)
        assert rt.execution(jid)==ex
    else:
        receipt=upgrade.authorize(rt,jid,target,checkpoint)
        after=rt.execution(jid)
        assert {k:v for k,v in after.items() if k!='controller_upgrade'}==ex
        assert rt.get(jid)['request_artifact']==original['request_artifact']
        assert rt.get(jid)['execution_profile']==original['execution_profile']
        assert upgrade.accepted(rt.get(jid),after,target)
        assert receipt['budget_reset'] is False and receipt['deadline_reset'] is False
