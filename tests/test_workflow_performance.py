"""Controller performance and source preservation; no model execution."""
import copy
import pytest
from t01_phase1_real.common import encode,now,new_id,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import service,policy,continuation
from test_local_workflow import body,run


def running(rt):
    job=rt.submit_workflow(encode(body()),'source')
    with rt._tx() as db:
        value=copy.deepcopy(job)
        value.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-test',
                     lease_epoch=1,started_at=now())
        rt._store(db,value,job,'test_claim')
        rt._execution_store(db,job['job_id'],dict(started_at=value['started_at'],nodes={},tree_stopped=False))
    return value


@pytest.mark.parametrize('cancel_at',[None,50])
def test_completed_slot_traversal_does_not_reload_large_snapshot(tmp_path,monkeypatch,cancel_at):
    rt=Runtime(tmp_path);job=running(rt);jid=job['job_id']
    names=tuple('unused'+str(i) for i in range(570))
    with rt._tx() as db:
        ex=rt._execution(db,jid)
        ex['nodes']={n:dict(job_id=None,state='skipped',detail='x'*1000) for n in names}
        rt._execution_store(db,jid,ex)
    monkeypatch.setattr(policy,'order',lambda b:names)
    original=rt.execution;reads=[]
    def read(key):
        reads.append(key);return original(key)
    monkeypatch.setattr(rt,'execution',read)
    original_get=rt.get;gets=[]
    def get(key):
        gets.append(key)
        if cancel_at and len(gets)==cancel_at:
            with rt._tx() as db:rt._stop(db,rt._job(db,jid),'cancel')
        return original_get(key)
    monkeypatch.setattr(rt,'get',get)
    monkeypatch.setattr(service,'finish',lambda rt,jid,error=None:rt.get(jid))
    end=service.dispatch(rt,jid)
    assert len(reads)==1
    assert end['stop_reason']==('cancel' if cancel_at else None)
    if cancel_at:assert len(gets)<570


def test_status_does_not_replay_science_but_export_stays_verified(tmp_path,monkeypatch):
    from test_real_service_api import credentials,principal,Service,ServiceConfig
    s=Service(ServiceConfig(runtime_root=tmp_path),credentials());owner=principal(s.credentials)
    try:
        rt=s.runtime(owner);j=run(rt)
        s.store.register_submission(owner,'test-status','fingerprint',j['job_id'])
        calls=[];original=service.snapshot
        def snapshot(rt,jid,verify=True):
            calls.append(verify);return original(rt,jid,verify)
        monkeypatch.setattr(service,'snapshot',snapshot)
        assert s.status(owner,j['job_id'])['state']=='succeeded'
        assert calls==[False]
        rt.workflow(j['job_id']);assert calls[-1] is True
    finally:s.shutdown()


def test_continuation_is_new_same_run_job_and_idempotent(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);source=running(rt);jid=source['job_id']
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=jid,idempotency_key='stop')))
    source=service.finish(rt,jid)
    old=rt.execution(jid);b=policy.request(rt._request_bytes(source))
    rows={'design':{'job_id':'fixture','state':'succeeded','confirmation':{'decision':True,'job_id':jid}}}
    monkeypatch.setattr(continuation,'prepare',lambda *a:(source,b,old,rows))
    child=continuation.restart_candidate_analysis(rt,jid,'continue-n10')
    assert child['job_id']!=jid and child['run_id']==source['run_id'] and child['retry_of_job_id']==jid
    assert rt.get(jid)==source and rt.execution(jid)==old
    ex=rt.execution(child['job_id'])
    assert ex['continuation']['scientific_consent_added'] is False
    assert ex['nodes']['design']['confirmation']['job_id']==jid
    monkeypatch.setattr(continuation,'prepare',lambda *a:pytest.fail('Duplicate source replay'))
    assert continuation.restart_candidate_analysis(rt,jid,'continue-n10')['job_id']==child['job_id']


def test_continuation_rejects_live_or_unconfirmed_source(tmp_path):
    rt=Runtime(tmp_path);j=running(rt)
    with pytest.raises(RuntimeFault,match='cancelled'):continuation.prepare(rt,j['job_id'])
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='stop')))
    with pytest.raises(RuntimeFault):continuation.prepare(rt,j['job_id'])


def test_continuation_fences_checkpoint_change_before_creation(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);source=running(rt);jid=source['job_id']
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=jid,idempotency_key='stop')))
    source=service.finish(rt,jid);old=rt.execution(jid);old['different']=True
    monkeypatch.setattr(continuation,'prepare',lambda *a:(source,None,old,{}))
    with pytest.raises(RuntimeFault,match='checkpoint changed'):
        continuation.restart_candidate_analysis(rt,jid,'continue-n10')


def test_n10_reuses_only_this_traversals_verified_fact(monkeypatch):
    from test_n10_summary import setup_candidate
    from t01_phase1_real.development.workflow import candidate_developability as cd,validation
    rt,b,rows,_,fact=setup_candidate(monkeypatch)
    rows['validation']['fact']=copy.deepcopy(fact)
    calls=[]
    monkeypatch.setattr(validation,'verified_fact',lambda *a:(calls.append(a) or fact))
    baseline=cd.request(rt,b,rows,'c_s1_structure')
    cached={('workflow','validation'):copy.deepcopy(fact)}
    assert cd.request(rt,b,rows,'c_s1_structure',verified_facts=cached)==baseline
    assert len(calls)==1
    cd.request(rt,b,rows,'c_s1_structure',verified_facts={})
    assert len(calls)==2
    rows['validation']['fact']['records'][0]['passed']=False
    with pytest.raises(RuntimeFault,match='changed during traversal'):
        cd.request(rt,b,rows,'c_s1_structure',verified_facts=cached)


def test_candidate_submission_checks_owner_scope_and_standard_scheduler(tmp_path,monkeypatch):
    from test_real_service_api import credentials,principal,Service,ServiceConfig,TOKEN_B
    from t01_phase1_real.service_api.app import Principal,ServiceError
    s=Service(ServiceConfig(runtime_root=tmp_path),credentials());owner=principal(s.credentials)
    try:
        rt=s.runtime(owner);j=run(rt)
        s.store.register_submission(owner,'old','fingerprint',j['job_id'])
        created=rt.submit_workflow(encode(body()),'new-candidate-analysis')
        calls=[]
        monkeypatch.setattr(continuation,'restart_candidate_analysis',lambda rt,jid,key:
            (calls.append((rt.scope,jid,key)) or dict(created,state='running')))
        scheduled=[]
        monkeypatch.setattr(s,'schedule',lambda *args,**kw:scheduled.append((args,kw)))
        with pytest.raises(ServiceError):
            s.submit_candidate_analysis(principal(s.credentials,TOKEN_B),j['job_id'],'key')
        with pytest.raises(ServiceError):
            s.submit_candidate_analysis(Principal(owner.principal_id,frozenset(['query']),'x'),j['job_id'],'key')
        assert calls==scheduled==[]
        value=s.submit_candidate_analysis(owner,j['job_id'],'key')
        assert value['action']=='CANDIDATE_ANALYSIS_SUBMITTED'
        assert calls[0][0]==owner.runtime_scope and scheduled[0][1]=={'recovering':True}
    finally:s.shutdown()


def test_candidate_submission_http_auth_and_exact_fields(tmp_path,monkeypatch):
    import threading
    from test_real_service_api import credentials,Service,ServiceConfig,Phase1RealServiceServer,request,TOKEN_A
    s=Service(ServiceConfig(runtime_root=tmp_path),credentials())
    server=Phase1RealServiceServer(('127.0.0.1',0),s)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    calls=[]
    monkeypatch.setattr(s,'submit_candidate_analysis',lambda p,j,k:(calls.append((p,j,k)) or {'job_id':j}))
    url=f'http://127.0.0.1:{server.server_port}/v1/workflows/t01p1r-job-'+('1'*32)+'/candidate-analysis'
    try:
        assert request(url,'POST',value={'idempotency_key':'x'})[0]==401
        assert request(url,'POST',TOKEN_A,{'idempotency_key':'x','sequence':'AA'})[0]==422
        assert calls==[]
        assert request(url,'POST',TOKEN_A,{'idempotency_key':'x'})[0]==202
        assert calls[0][2]=='x'
    finally:server.shutdown();server.server_close();thread.join();s.shutdown()
