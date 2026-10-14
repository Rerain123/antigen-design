"""Real store/controller checks, with model boundaries replaced by explicit fixtures."""
import copy
import json
from contextlib import nullcontext
import pytest
from t01_phase1_real.common import encode,decode,now,RuntimeFault,sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import policy,service,revision_controller as rc,revision_contract as c,revision_sampling as s
from test_local_workflow import body,run
from test_expert_revision_core import fixture
from test_s28_validation import resident_admission
from test_proteinmpnn_development import request as native_request


def revised_body():
    b=body();b.update(engineering_design='BACKEND_EVIDENCE_V1',revision_config=c.suggested_config('fixture'))
    return b


def parent(tmp_path):
    rt=Runtime(tmp_path/'runtime');b=revised_body();job=rt.submit_workflow(encode(b),'revised');jid=job['job_id']
    with rt._tx() as db:
        old=rt._job(db,jid);rt._store(db,dict(old,state='running',started_at=now()),old,'fixture')
        rt._execution_store(db,jid,dict(nodes={},started_at=now(),phase='scheduling',dispatcher=None))
    return rt,jid,b


def test_opt_in_and_legacy_order_separate():
    legacy=body();legacy['engineering_design']='BACKEND_EVIDENCE_V1'
    assert 'validation' in policy.order(legacy) and rc.STAGE not in policy.order(legacy)
    assert rc.STAGE in policy.order(revised_body()) and 'validation' not in policy.order(revised_body())
    value=revised_body();value['revision_config']['policies']['s28']={'guess':'pass'}
    with pytest.raises(RuntimeFault):policy.request(encode(value))


def test_missing_input_delivers_real_report_without_native_jobs(tmp_path):
    rt=Runtime(tmp_path/'runtime');job=run(rt,revised_body())
    assert job['state']=='succeeded'
    snapshot=rt.workflow(job['job_id'])
    assert snapshot['nodes'][rc.STAGE]['state']=='skipped'
    assert snapshot['nodes']['local_delivery']['state']=='succeeded'
    assert not any(k in snapshot['nodes'] for k in rc.CHILDREN)
    assert not snapshot['usable_for_pipeline']


def test_native_admission_budget_resume_cancel(tmp_path,resident_admission,monkeypatch):
    from t01_phase1_real.development.proteinmpnn import source
    monkeypatch.setattr(source,'sources',lambda *a,**k:({},{}))
    rt,jid,body=parent(tmp_path)
    req=native_request(sequence=body['protein_sequence'],n_designs=12)
    context=dict(shared_contract_version=c.VERSION,stage='proposal_only',calculation_config_id='fixture',rule_version=c.RULE,
        permission_snapshot_id='permissions',reference_id=sha(body['protein_sequence'].encode()),sampling_constraints_sha256=sha(encode(req['constraints'])))
    req['revision_context']=context
    first=service._create_child(rt,jid,'proposal0',req)
    assert rt.execution(jid)['revision_ledger']['reservations']['proposal0']['requested']==12
    restarted=Runtime(tmp_path/'runtime')
    assert service._create_child(restarted,jid,'proposal0',req)==first
    assert len(rt.execution(jid)['revision_ledger']['reservations'])==1
    with rt._tx() as db:rt._stop(db,rt._job(db,jid),'cancel')
    assert service._create_child(restarted,jid,'proposal1',req) is None
    service.stop_children(restarted,jid);assert rt.get(first)['state']=='cancelled'


def test_proposal_cannot_enter_esm_source(monkeypatch):
    from t01_phase1_real.development.esm_if1 import source
    monkeypatch.setattr(source,'registered',lambda *a:({},b'',{},dict(revision_context={'stage':'proposal_only'}),{}))
    with pytest.raises(RuntimeFault,match='Proposal-only'):
        source.sources(None,None,dict(n11_artifact={}))


def test_formal_shared_version_handshake_required(monkeypatch):
    from t01_phase1_real.development.esm_if1 import source
    context=dict(stage='formal',shared_contract_version=c.VERSION,calculation_config_id='fixture')
    monkeypatch.setattr(source,'registered',lambda *a:({},b'',{},dict(revision_context=context),{}))
    with pytest.raises(RuntimeFault,match='contract_incompatible'):
        source.sources(None,None,dict(n11_artifact={}))


def test_sampling_controller_restart_and_policy_stop(monkeypatch,tmp_path):
    rt,jid,body=parent(tmp_path);cfg,snap,_,_=fixture(19)
    # The fixture uses the same frozen WT identity as the controller request.
    body['protein_sequence']=snap['original_wt_seq'];body['revision_config']=cfg
    from pathlib import Path
    scales=json.loads(Path(c.__file__).parents[1].joinpath('design_backend/scales.json').read_bytes())
    data=dict(snapshot=snap,options=dict(timeout_seconds=60,t4_empty_fixed_confirmation=True),scales=scales,audit={})
    monkeypatch.setattr(rc,'inputs',lambda *a:(data,None))
    requests={};executions={};pending=set()
    def child(rt,jid,body,name,req):
        if name not in requests:
            requests[name]=copy.deepcopy(req);pending.add(name)
            service._record(rt,jid,name,dict(job_id=None,state='running',origin='ENGINEERING_FIXTURE',reason_code=None))
            return False
        if name in pending:
            pending.remove(name)
            service._record(rt,jid,name,dict(job_id=None,state='succeeded',origin='ENGINEERING_FIXTURE',reason_code=None))
        return True
    monkeypatch.setattr(rc,'child',child)
    # Exercise selection orchestration; native byte parsing remains covered by
    # source-specific tests and is not presented as native evidence here.
    def assemble(rt,jid,body,data,**kwargs):
        rows=rt.execution(jid)['nodes'];formal=[]
        for i in range(3):
            if rows.get(f'formal{i}',{}).get('state')=='succeeded':
                formal=s.formal(snap,[dict(sample_number=1,sequence='S'+'A'*18)], [1],cfg,[],
                    dict(scales=scales,generation_ref={'id':'formal0'}))
        return dict(proposal_summary=dict(nomination_positions=[1],quarantine_receipts=[],valid_count=24),
                    formal_records=formal,design_outcomes=[])
    monkeypatch.setattr(rc,'assemble',assemble)
    monkeypatch.setattr(service,'source',lambda *a:dict(artifact={'id':'formal0'}))
    for _ in range(10):
        if rc.tick(rt,jid,body):break
    else:pytest.fail('Revision controller did not complete')
    assert set(requests)=={'proposal0','proposal1','formal0','cheap0'}
    assert requests['proposal0']['n_designs']==requests['proposal1']['n_designs']==12
    assert requests['proposal0']['seed']!=requests['proposal1']['seed']
    assert len(requests['formal0']['constraints']['fixed_positions'])==18
    assert requests['cheap0']['sample_numbers']==[1]
    assert rt.execution(jid)['revision_state']['design_outcomes']==['configuration_incomplete']
    assert rc.tick(rt,jid,body)
    assert len(requests)==4


def test_zero_structure_budget_stops_before_proposals(monkeypatch,tmp_path):
    rt,jid,body=parent(tmp_path);cfg,snap,_,_=fixture(19);cfg['structure_eval_max']=0;body['revision_config']=cfg
    monkeypatch.setattr(rc,'inputs',lambda *a:(dict(snapshot=snap),None))
    monkeypatch.setattr(rc,'assemble',lambda *a:dict(design_outcomes=[]))
    monkeypatch.setattr(rc,'child',lambda *a:pytest.fail('Budget stop bypassed'))
    assert rc.tick(rt,jid,body)
    assert rt.execution(jid)['revision_state']['design_outcomes']==['budget_exhausted']


def test_actual_assembly_keeps_full_inventory_schema_and_report(monkeypatch):
    from pathlib import Path
    from t01_phase1_real.service_api.user_report import render
    cfg,snap,_,_=fixture(19)
    body=revised_body();body.update(protein_sequence=snap['original_wt_seq'],revision_config=cfg)
    data=dict(snapshot=snap,options=dict(timeout_seconds=60,t4_empty_fixed_confirmation=True),
        scales=json.loads(Path(c.__file__).parents[1].joinpath('design_backend/scales.json').read_bytes()))
    rows={name:dict(state='succeeded',job_id=name) for name in ('proposal0','proposal1','formal0')}
    requests={name:rc._native_request(body,data,'formal' if name=='formal0' else 'proposal_only',
        1 if name=='proposal1' else 0,[1] if name=='formal0' else snap['eligible_positions']) for name in rows}
    class Fixture:
        def get(self,jid):return dict(run_id='run',job_id=jid,execution_identity=jid)
        def execution(self,jid):return dict(nodes=rows)
        def _request_bytes(self,job):return encode(requests[job['job_id']])
    def generation(rt,body,rows,name,run):
        n=24 if name=='formal0' else 12
        records=[dict(sample_number=i+1,sequence='S'+'A'*18) for i in range(n)]
        return dict(records=records,native_wt=dict(sequence='A'*19)),dict(artifact_id=name),rt.get(name)
    monkeypatch.setattr(rc,'generation',generation)
    result=rc.assemble(Fixture(),'task',body,data)
    assert result['proposal_summary']['valid_count']==24 and len(result['formal_records'])==24
    early=rc.assemble(Fixture(),'task',body,data,sampling_only=True)
    assert early['proposal_summary']==result['proposal_summary']
    assert [(r['sample_number'],r['sequence'],r['disposition']) for r in early['formal_records']]==[
        (r['sample_number'],r['sequence'],r['disposition']) for r in result['formal_records']]
    assert [r['disposition'] for r in result['formal_records']].count('DUPLICATE')==23
    assert result['foldx_pool']['results']==[] and result['acceptance_status']=='NOT_ASSESSED'
    assert all(r['validation']['passed'] is None for r in result['formal_records'])
    html=render({},dict(expert_revision=result,nodes=dict(revision_design=dict(state='succeeded'),formal0=rows['formal0']))).decode()
    assert '正式生成 24 条记录' in html and '本次未生成设计候选' not in html
    assert '未评估' in html and result['formal_records'][0]['sequence'] in html
    requests['formal0']['seed']=999
    with pytest.raises(RuntimeFault,match='Formal request context differs'):rc.assemble(Fixture(),'task',body,data)
    with pytest.raises(RuntimeFault,match='Formal request context differs'):rc.assemble(Fixture(),'task',body,data,sampling_only=True)
