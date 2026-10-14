"""Persisted native-worker wiring; synthetic boundaries never assert science."""
import copy
import json
from pathlib import Path
import pytest
from t01_phase1_real.common import encode,decode,now,sha,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import service,policy,revision_runtime as wiring,revision_controller as rc
from t01_phase1_real.development.workflow import revision_contract as c,revision_sampling as sampling,revision_budget as budget
from test_expert_revision_workflow import revised_body
from test_expert_revision_core import fixture
from test_s28_validation import resident_admission
from test_foldx_development import artifact


def policies():
    common=dict(policy_id='TEST_ONLY_NOT_EXPERT_APPROVED',policy_status='ENGINEERING_UNREVIEWED')
    return dict(s28=dict(common,required_set_id='fixture-s28',required_check_ids=['constraints','esm_if1','structure']),
        model_roles=dict(common,model_roles=dict(af3='mandatory',esmfold2='mandatory'),
                         min_plddt=dict(af3=.5,esmfold2=.5),selection_order=['af3','esmfold2']),
        foldx_pool=dict(common,source_pool_id='revision_formal_pool',required_check_ids=['s28'],
                        selection_rule_version='esm-desc-mutation-count-id-v1',applicability=True),esm_near_zero=.001)


def setup(tmp_path,monkeypatch,*,count=1,change=None):
    b=revised_body();cfg,snap,_,_=fixture(100);cfg['policies'].update(policies())
    if change:change(cfg)
    b.update(protein_sequence=snap['original_wt_seq'],revision_config=cfg)
    snap['wt_structure_id']=artifact()
    scales=json.loads(Path(c.__file__).parents[1].joinpath('design_backend/scales.json').read_bytes())
    data=dict(snapshot=snap,scales=scales,options=dict(timeout_seconds=60,t4_empty_fixed_confirmation=True))
    raw=[dict(sample_number=1,sequence='S'*count+'A'*(100-count))]
    records=sampling.formal(snap,raw,list(range(1,count+1)),cfg,[],dict(scales=scales,generation_ref=artifact()))
    for r in records:
        r['esm_if1']=c.check('PASS',score=-1.);r['ranking_context']={}
        r['acceptance_status']=r['provisional_acceptance_status']='NOT_ASSESSED'
    rt=Runtime(tmp_path/'runtime');job=rt.submit_workflow(encode(b),'fixture');jid=job['job_id']
    with rt._tx() as db:
        j=rt._job(db,jid);rt._store(db,dict(j,state='running',started_at=now()),j,'fixture')
        rt._execution_store(db,jid,dict(nodes={'formal0':dict(job_id='fixture-formal',state='succeeded')},started_at=now()))
    original_source=service.source;original_result=Runtime.result
    original_get=Runtime.get
    monkeypatch.setattr(Runtime,'get',lambda rt,id:dict(job_id=id,state='succeeded',error_code=None)
                        if id=='fixture-formal' else original_get(rt,id))
    monkeypatch.setattr(service,'source',lambda rt,row:dict(artifact=artifact(),job_id='fixture-formal') if row.get('job_id')=='fixture-formal' else original_source(rt,row))
    monkeypatch.setattr(Runtime,'result',lambda rt,id:dict(generation=dict(records=raw)) if id=='fixture-formal' else {})
    from t01_phase1_real.development.af3 import msa
    from t01_phase1_real.development.foldx import source as fs
    from t01_phase1_real.development.workflow import msa_reuse
    monkeypatch.setattr(msa,'sources',lambda *a,**k:({},{}))
    monkeypatch.setattr(msa_reuse,'ready',lambda *a:(dict(job_id=artifact()['job_id'],artifact=artifact()),None))
    monkeypatch.setattr(fs,'sources',lambda *a,**k:({'native/target.pdb':b'WT'},{}))
    for e in ('af3','esmfold2'):
        monkeypatch.setattr(service.prediction_source(e),'verified',lambda *a,**k:dict(
            quality={'structure':{'mean_plddt':.8}},structure_artifact=artifact(),quality_artifact=artifact()))
    # Emulate asynchronous native execution only; real admission, persisted
    # requests, child identity, budget, recovery and cancellation stay active.
    calls=[]
    def dispatch(rt,id):
        with rt._tx() as db:
            j=rt._job(db,id);calls.append((j['tool_id'],id))
            rt._store(db,dict(j,state='running',attempt_id='fixture-'+id,started_at=now()),j,'fixture-native-start')
    def recover(rt,id):
        with rt._tx() as db:
            j=rt._job(db,id);rt._store(db,dict(j,state='succeeded',finished_at=now()),j,'fixture-native-complete')
    monkeypatch.setattr(Runtime,'dispatch',dispatch);monkeypatch.setattr(Runtime,'recover',recover)
    # Only native bytes/parser are substituted. FoldX association, request,
    # WT consistency and five-repeat aggregation are real consumer code.
    from t01_phase1_real.development.esm_if1 import source as registered
    from t01_phase1_real.development.foldx import result as fr
    def reg(rt,db,ref,tool):
        if tool.endswith('proteinmpnn'):return {},b'',{}, {},{'native/target.pdb':b'WT'}
        row=rt.execution(jid)['nodes']['rf0'];request=decode(rt._request_bytes(rt.get(row['job_id'])))
        rows=[dict(variant_id=v['variant_id'],native_ddg_runs=[-1,-2,-3,-4,-5]) for v in request['variants']]
        return {},b'',dict(variant_ddg=rows),request,{'native/target.pdb':b'WT','rows':rows}
    monkeypatch.setattr(registered,'registered',reg)
    monkeypatch.setattr(fr,'parse',lambda req,files:dict(rows=files['rows']))
    return rt,jid,b,data,records,calls


def drain(rt,jid,b,data,records):
    for _ in range(8):
        result=wiring.tick(rt,jid,b,data,records,0)
        if result is not None:return result
        rt=Runtime(rt.root) if hasattr(rt,'root') else rt
    pytest.fail('Wiring never completed')


@pytest.mark.parametrize('count,engines',[(1,1),(6,2)])
def test_actual_admission_recovery_consumption_and_idempotence(tmp_path,monkeypatch,resident_admission,count,engines):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch,count=count)
    assert drain(rt,jid,b,data,records)=='S28_ORIGINAL_PASS'
    assert len(calls)==engines+1 and calls[-1][0]=='t01.real.foldx'
    assert records[0]['validation']['check_status']=='PASS'
    assert records[0]['foldx']['valid_count']==5 and records[0]['foldx']['mean']==-3
    assert records[0]['foldx']['std']==pytest.approx(1.5811388300841898)
    assert records[0]['acceptance_status']=='NOT_ASSESSED'
    ledger=rt.execution(jid)['revision_ledger'];assert len(ledger['reservations'])==engines+1
    summary=budget.summary(ledger,b['revision_config']);assert summary['structure']['unique_objects']==1
    assert summary['structure']['attempts']==engines and summary['foldx']['attempts']==1
    restarted=Runtime(tmp_path/'runtime');assert drain(restarted,jid,b,data,records)=='S28_ORIGINAL_PASS'
    assert len(calls)==engines+1 and restarted.execution(jid)['revision_ledger']==ledger
    child=restarted.get(rt.execution(jid)['nodes']['rf0']['job_id'])
    req=decode(rt._request_bytes(child));assert req['protein_sequence']==b['protein_sequence'] and req['mode']=='buildmodel'
    assert req['variants'][0]['mutations']==records[0]['mutations'] and not req['scan_positions']


def test_missing_foldx_policy_does_not_block_structure(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch,change=lambda cfg:cfg['policies'].update(foldx_pool=None))
    assert drain(rt,jid,b,data,records)=='configuration_incomplete'
    assert [tool for tool,_ in calls]==['t01.real.af3'] and records[0]['validation']['check_status']=='PASS'


def test_dual_budget_is_atomic(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch,count=6,change=lambda cfg:cfg['call_limits'].update(structure=1))
    assert drain(rt,jid,b,data,records)=='incomplete_only'
    assert not calls and rt.execution(jid)['revision_ledger']['reservations']=={}
    assert records[0]['validation']['check_status']=='NOT_ASSESSED'


def test_cancel_stops_children_and_prevents_foldx(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    assert wiring.tick(rt,jid,b,data,records,0) is None
    child_id=calls[0][1]
    with rt._tx() as db:rt._stop(db,rt._job(db,jid),'cancel')
    service.stop_children(rt,jid)
    assert rt.get(child_id)['stop_reason']=='cancel'
    assert wiring.tick(rt,jid,b,data,records,0) is None and len(calls)==1


def test_required_fail_and_advisory_disagreement():
    p=policies();r=dict(sequence='A'*100,mutations=[{}]*6,constraint_check=c.check('PASS'),esm_if1=c.check('PASS'),ranking_context={})
    obs=dict(af3=dict(c.check('FAIL'),structure={}),esmfold2=dict(c.check('PASS'),structure={}))
    wiring.summarize(r,obs,p)
    assert r['validation']['passed'] is False and r['ranking_context']['model_disagreement']
    p['model_roles']['model_roles']['af3']='advisory';wiring.summarize(r,obs,p)
    assert r['validation']['passed'] is True and r['ranking_context']['model_disagreement']
    obs['esmfold2']=dict(c.check('NOT_ASSESSED',execution='ERROR'),structure=None)
    wiring.summarize(r,obs,p);assert r['validation']['passed'] is None
    del obs['esmfold2'];wiring.summarize(r,obs,p);assert r['validation']['passed'] is None


def test_configuration_requires_explicit_scoped_policy():
    cfg=c.suggested_config('fixture');cfg['policies'].update(policies());assert c.config(cfg)==cfg
    cfg['policies']['model_roles']['policy_status']='EXPERT_APPROVED'
    with pytest.raises(RuntimeFault):c.config(cfg)


def test_frozen_request_tamper_rejected(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    assert wiring.tick(rt,jid,b,data,records,0) is None
    with rt._tx() as db:
        ex=rt._execution(db,jid);ex['revision_bindings']['rx0_s1_af3']['candidate_ids']=['foreign']
        rt._execution_store(db,jid,ex)
    with pytest.raises(RuntimeFault,match='binding'):wiring.enrich(rt,jid,b,data,records)


@pytest.mark.parametrize('failed',[False,True])
def test_quality_failure_vs_execution_failure(tmp_path,monkeypatch,resident_admission,failed):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    if failed:
        def recover(rt,id):
            with rt._tx() as db:
                j=rt._job(db,id);rt._store(db,dict(j,state='failed',error_code='TOOL_FAILED',finished_at=now()),j,'fixture-failure')
        monkeypatch.setattr(Runtime,'recover',recover)
    else:
        monkeypatch.setattr(service.prediction_source('af3'),'verified',lambda *a,**k:dict(
            quality={'structure':{'mean_plddt':.2}},structure_artifact=artifact(),quality_artifact=artifact()))
    assert drain(rt,jid,b,data,records)==('incomplete_only' if failed else 'all_rejected')
    assert records[0]['validation']['check_status']==('NOT_ASSESSED' if failed else 'FAIL')
    assert len(calls)==1


def test_stage_time_clips_native_timeout(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch,change=lambda cfg:cfg['time_limits'].update(structure=2))
    assert wiring.tick(rt,jid,b,data,records,0) is None
    assert decode(rt._request_bytes(rt.get(calls[0][1])))['timeout_seconds']==2
    ledger=rt.execution(jid)['revision_ledger']
    assert wiring.stage_remaining(dict(revision_ledger=dict(attempts={'a':dict(stage='structure',execution_seconds=None)})),b,'rx0_s1_af3')==0


def test_foldx_native_output_tamper_quarantined(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    assert drain(rt,jid,b,data,records)=='S28_ORIGINAL_PASS'
    from t01_phase1_real.development.esm_if1 import source
    original=source.registered
    def changed(*args):
        result=list(original(*args))
        if args[-1]=='t01.real.foldx':result[2]=dict(variant_ddg=[])
        return result
    monkeypatch.setattr(source,'registered',changed)
    with pytest.raises(RuntimeFault,match='native repeats'):wiring.enrich(rt,jid,b,data,records)


def test_foldx_zero_budget_keeps_not_run(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch,change=lambda cfg:cfg.update(foldx_variant_max=0))
    assert drain(rt,jid,b,data,records)=='budget_exhausted'
    assert len(calls)==1 and records[0]['foldx']['execution_status']=='NOT_RUN'


def test_main_revision_controller_reaches_native_consumers(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(rc,'inputs',lambda *a:(data,None))
    original_child=rc.child
    def child(rt,jid,body,name,req):
        if name in wiring.CHILDREN:return original_child(rt,jid,body,name,req)
        service._record(rt,jid,name,dict(job_id='fixture-formal' if name=='formal0' else None,
            state='succeeded',origin='ENGINEERING_FIXTURE',reason_code=None))
        return True
    monkeypatch.setattr(rc,'child',child)
    def assembly(rt,jid,b,data,**kwargs):
        wiring.enrich(rt,jid,b,data,records)
        return dict(proposal_summary=dict(nomination_positions=[1],quarantine_receipts=[],valid_count=24),
            formal_records=copy.deepcopy(records),design_outcomes=[])
    monkeypatch.setattr(rc,'assemble',assembly)
    for _ in range(8):
        if rc.tick(rt,jid,b):break
    else:pytest.fail('Main controller did not reach FoldX')
    fact=rt.execution(jid)['revision_state']
    assert fact['formal_records'][0]['foldx']['valid_count']==5
    assert fact['design_outcomes']==['S28_ORIGINAL_PASS']
    assert rt.execution(jid)['revision_round_outcomes']=={'0':'S28_ORIGINAL_PASS'}
    assert len(calls)==2
