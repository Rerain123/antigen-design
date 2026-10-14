"""Asynchronous controller regressions; synthetic results, no native models."""
import copy
from pathlib import Path
import json
import pytest
from t01_phase1_real.common import RuntimeFault, encode
from t01_phase1_real.development.workflow import revision_controller as rc, service
from test_expert_revision_workflow import parent
from test_expert_revision_core import fixture


def setup_child(rt, jid, monkeypatch, name, state='succeeded', error=None):
    job=dict(job_id='synthetic-'+name,run_id=rt.get(jid)['run_id'],state=state,error_code=error)
    original_get=rt.get
    monkeypatch.setattr(rt,'get',lambda key:copy.deepcopy(job) if key==job['job_id'] else original_get(key))
    service._record(rt,jid,name,dict(job_id=job['job_id'],state='running',reason_code=None,
                                   origin='ENGINEERING_FIXTURE',custom_binding='retained'))
    monkeypatch.setattr(service,'verified',lambda *a:rt.get(a[3]))
    monkeypatch.setattr(rc,'account',lambda *a:None)
    monkeypatch.setattr(rt,'dispatch',lambda *a:pytest.fail('Already collected job was dispatched'))
    monkeypatch.setattr(rt,'recover',lambda *a:pytest.fail('Already collected job was recovered'))
    return job


@pytest.mark.parametrize('name',['proposal0','proposal1','formal0','cheap0','rx0_s1_af3','z0_s1_bepipred'])
@pytest.mark.parametrize('state,error',[('succeeded',None),('failed','TOOL_FAILED'),('timed_out','TIMEOUT'),('failed','ASSET_MISSING')])
def test_independent_collection_updates_parent_without_resubmitting(tmp_path,monkeypatch,name,state,error):
    rt,jid,body=parent(tmp_path)
    setup_child(rt,jid,monkeypatch,name,state,error)
    assert rc.child(rt,jid,body,name,{})
    saved=rt.execution(jid)['nodes'][name]
    assert (saved['state'],saved['reason_code'])==(state,error)
    assert saved['custom_binding']=='retained'
    rc.terminal_children(rt,jid)
    assert rc.child(rt,jid,body,name,{})
    assert rt.execution(jid)['nodes'][name]==saved  # No repeated state event.


@pytest.mark.parametrize('initial',['queued','running'])
def test_collection_during_poll_still_syncs(tmp_path,monkeypatch,initial):
    rt,jid,body=parent(tmp_path)
    job=setup_child(rt,jid,monkeypatch,'proposal0',initial)
    calls=[]
    def complete(key):
        calls.append(key);job['state']='succeeded'
    monkeypatch.setattr(rt,'dispatch' if initial=='queued' else 'recover',complete)
    assert rc.child(rt,jid,body,'proposal0',{})
    assert calls==[job['job_id']]
    assert rt.execution(jid)['nodes']['proposal0']['state']=='succeeded'


def test_integrity_failure_is_not_a_scientific_rejection(tmp_path,monkeypatch):
    rt,jid,body=parent(tmp_path)
    setup_child(rt,jid,monkeypatch,'proposal0','failed','HASH_MISMATCH')
    with pytest.raises(RuntimeFault,match='integrity failure'):rc.child(rt,jid,body,'proposal0',{})


@pytest.mark.parametrize('state',['cancelled','succeeded'])
def test_terminal_parent_is_not_mutated(tmp_path,monkeypatch,state):
    rt,jid,body=parent(tmp_path)
    setup_child(rt,jid,monkeypatch,'proposal0')
    before=rt.execution(jid)
    get=rt.get
    monkeypatch.setattr(rt,'get',lambda key:dict(get(key),state=state) if key==jid else get(key))
    assert not rc.child(rt,jid,body,'proposal0',{})
    assert rt.execution(jid)==before


@pytest.mark.parametrize('real,cached,error',[('succeeded','running',None),('running','running',None),
    ('failed','succeeded','TOOL_FAILED'),('failed','failed','TIMEOUT')])
def test_finish_rejects_unsynchronized_or_active_children(tmp_path,monkeypatch,real,cached,error):
    rt,jid,body=parent(tmp_path)
    setup_child(rt,jid,monkeypatch,'proposal0',real,error)
    row=rt.execution(jid)['nodes']['proposal0']
    service._record(rt,jid,'proposal0',dict(row,state=cached,reason_code=None))
    cfg,snap,_,_=fixture(19);cfg['structure_eval_max']=0;body['revision_config']=cfg
    monkeypatch.setattr(rc,'inputs',lambda *a:(dict(snapshot=snap),None))
    monkeypatch.setattr(rc,'assemble',lambda *a:pytest.fail('Inconsistent revision was assembled'))
    with pytest.raises(RuntimeFault,match='not synchronized'):rc.tick(rt,jid,body)
    assert rc.STAGE not in rt.execution(jid)['nodes']
    assert 'revision_state' not in rt.execution(jid)


def test_two_completed_batches_reach_formal_scheduling(tmp_path,monkeypatch):
    rt,jid,body=parent(tmp_path);cfg,snap,_,_=fixture(19)
    body.update(protein_sequence=snap['original_wt_seq'],revision_config=cfg)
    data=dict(snapshot=snap,options=dict(timeout_seconds=60,t4_empty_fixed_confirmation=True),
              scales=json.loads(Path(rc.__file__).parents[1].joinpath('design_backend/scales.json').read_bytes()))
    monkeypatch.setattr(rc,'inputs',lambda *a:(data,None))
    for name in ('proposal0','proposal1'):setup_child(rt,jid,monkeypatch,name)
    requests={name:rc._native_request(body,data,'proposal_only',i,snap['eligible_positions'])
              for i,name in enumerate(('proposal0','proposal1'))}
    monkeypatch.setattr(rt,'_request_bytes',lambda job:encode(requests[job['job_id'].removeprefix('synthetic-')]))
    def generated(rt,body,rows,name,run_id):
        job=rt.get(rows[name]['job_id']);job['execution_identity']=name
        assert job['state']=='succeeded'
        return dict(records=[dict(sample_number=i+1,sequence='S'+'A'*18) for i in range(12)]),dict(artifact_id=name),job
    monkeypatch.setattr(rc,'generation',generated)
    scheduled=[]
    def create(rt,jid,name,req):
        scheduled.append(name)
        # Stop at the next scheduling boundary; never call a scientific tool.
        assert name=='formal0'
        raise StopIteration('formal scheduling reached')
    monkeypatch.setattr(service,'_create_child',create)
    with pytest.raises(StopIteration,match='formal scheduling reached'):rc.tick(rt,jid,body)
    assert scheduled==['formal0']
    fact=rc.assemble(rt,jid,body,data)
    assert fact['proposal_summary']['valid_count']==24
    assert fact['proposal_summary']['nomination_positions']
    assert rc.STAGE not in rt.execution(jid)['nodes']


def test_reverification_refuses_historical_stale_completion(tmp_path,monkeypatch):
    rt,jid,body=parent(tmp_path)
    setup_child(rt,jid,monkeypatch,'proposal0')
    rc._store(rt,jid,dict(design_outcomes=['no_valid_presampling']))
    with pytest.raises(RuntimeFault,match='not synchronized'):rc.verified_fact(rt,jid,body)
