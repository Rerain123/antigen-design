"""Controller optimizations must preserve strict source validation and routing."""
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from t01_phase1_real.common import decode, RuntimeFault
from t01_phase1_real.service_api import replay_cache as cache


def test_exact_inputs_fresh_objects_and_scope_cleanup():
    calls=[]
    def f(raw):
        calls.append(raw)
        return decode(raw)
    with cache.scope() as state:
        first=cache.pure(f,b'{"a":[1]}');first['a'].append(2)
        assert cache.pure(f,b'{"a":[1]}')=={'a':[1]}
        assert cache.pure(f,b'{"a":[2]}')=={'a':[2]}
        for _ in range(2):
            with pytest.raises(RuntimeFault):cache.pure(f,b'{"a":1,"a":2}')
        assert state.hits==1 and len(calls)==4
        with cache.scope() as nested:assert nested is state
    assert not state.entries and state.size==0 and cache.current() is None
    with cache.scope() as other:
        cache.pure(f,b'{"a":[1]}')
        assert other.hits==0


def test_bounds_and_thread_isolation():
    state=cache.Cache(max_bytes=2048,max_entries=1)
    def f(x):return x
    state.call(f,1);state.call(f,2)
    assert len(state.entries)==1 and state.size<=2048
    state.call(f,'x'*10000)
    assert len(state.entries)==1
    with cache.scope():
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(cache.current).result() is None


def test_traversal_exception_clears_cache():
    @cache.traversal
    def fail():
        cache.pure(decode,b'{}')
        raise ValueError('stop')
    with pytest.raises(ValueError):fail()
    assert cache.current() is None


def test_only_exact_maintenance_predictor_pair_is_compatible():
    from t01_phase1_real.service_api.controller_maintenance import same_predictor, AUTHORIZATION
    job = dict(job_id='parent',run_id='run',request_artifact={'sha256':'request'})
    left = dict(execution={'sha256':'old'},rule=None,parameters={'mode':'raw'})
    right = dict(left,execution={'sha256':'new'})
    receipt = dict(authorization=AUTHORIZATION,job_id='parent',run_id='run',request_sha256='request',
                   maintenance=dict(predictor_profiles=[left['execution'],right['execution']],scientific_sources_unchanged=True))
    ex = dict(controller_upgrade=receipt)
    assert same_predictor(job,{},left,left)
    assert same_predictor(job,ex,left,right)
    assert not same_predictor(job,{},left,right)
    assert not same_predictor(job,ex,None,right)
    assert not same_predictor(job,ex,left,dict(right,execution={'sha256':'unknown'}))
    assert not same_predictor(job,ex,left,dict(right,parameters={'mode':'other'}))
    assert not same_predictor(dict(job,run_id='foreign'),ex,left,right)
    receipt['maintenance']['scientific_sources_unchanged']=False
    assert not same_predictor(job,ex,left,right)


def test_maintenance_wait_does_not_reset_active_time(monkeypatch):
    from t01_phase1_real.development.workflow import confirmation
    from t01_phase1_real.service_api.controller_maintenance import AUTHORIZATION
    monkeypatch.setattr(confirmation,'seconds',lambda start:1000)
    ex=dict(started_at='original',confirmation_wait_seconds=30,
            controller_upgrade=dict(authorization=AUTHORIZATION,maintenance={'excluded_seconds':200}))
    assert confirmation.elapsed(ex)==770
    ex['controller_upgrade']['authorization']='unapproved'
    assert confirmation.elapsed(ex)==970


@pytest.mark.parametrize('damage',[None,'science_source','checkpoint','time','predictor'])
def test_operator_maintenance_preserves_original_run(tmp_path,monkeypatch,damage):
    from t01_phase1_real.common import encode,sha
    from t01_phase1_real.development import Runtime
    from t01_phase1_real.service_api import controller_maintenance as maintenance
    from t01_phase1_real.service_api.controller_recovery import accepted
    from t01_phase1_real.development.workflow import policy
    from t01_phase1_real.development.bepipred import policy as bp
    from test_local_workflow import body
    rt=Runtime(tmp_path/'runtime');original=rt.submit_workflow(encode(body()),'maintenance')
    jid=original['job_id'];old_profile=dict(id='predictor',version='1',sha256='a'*64)
    new_profile=dict(old_profile,sha256='b'*64)
    old=tmp_path/'source'/'src'/'t01_phase1_real'/'development'/'workflow'/'service.py'
    old.parent.mkdir(parents=True);old.write_bytes(b'new')
    manifest={'t01_phase1_real/development/workflow/service.py':sha(b'old')}
    if damage=='science_source':
        other=old.parent.parent/'scientific.py';other.write_bytes(b'changed')
        manifest['t01_phase1_real/development/scientific.py']=sha(b'old')
    monkeypatch.setattr(maintenance,'REPO',tmp_path/'source')
    monkeypatch.setattr(maintenance,'now',lambda:'2026-10-10T09:00:00Z')
    monkeypatch.setattr(bp,'registered_profile',lambda:new_profile)
    with rt._tx() as db:
        job=rt._job(db,jid);rt._store(db,dict(job,state='running'),job,'fixture')
        child=dict(job,job_id='t01p1r-job-predictor',state='succeeded',tool_id='t01.real.bepipred',node_id='N04',execution_profile=old_profile)
        rt._store(db,child,None,'fixture')
        ex=dict(nodes={'bepipred':{'job_id':child['job_id']}},started_at='2026-10-10T04:00:00Z',
                revision_ledger={'spent':17},revision_v2_frozen={'original':True})
        rt._execution_store(db,jid,ex)
    checkpoint=sha(encode(ex)) if damage!='checkpoint' else '0'*64
    paused='2026-10-10T08:00:00Z' if damage!='time' else '2026-10-10T10:00:00Z'
    predictor=old_profile if damage!='predictor' else new_profile
    if damage:
        with pytest.raises(RuntimeFault):maintenance.authorize(rt,jid,checkpoint,paused,manifest,predictor)
        assert rt.execution(jid)==ex
    else:
        receipt=maintenance.authorize(rt,jid,checkpoint,paused,manifest,predictor)
        after=rt.execution(jid)
        assert {k:v for k,v in after.items() if k!='controller_upgrade'}==ex
        assert receipt['maintenance']['excluded_seconds']==3600
        assert rt.get(jid)['request_artifact']==original['request_artifact']
        assert accepted(rt.get(jid),after,policy.registered_profile())
        with pytest.raises(RuntimeFault):maintenance.authorize(rt,jid,sha(encode(after)),paused,manifest,predictor)
