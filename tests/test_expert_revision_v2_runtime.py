"""Real admission/store/recovery; native scientific boundaries are fixtures."""
import copy
import json
from pathlib import Path
import pytest
from t01_phase1_real.common import encode,decode,now,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import service,revision_controller as rc,revision_runtime as wiring
from t01_phase1_real.development.workflow import revision_v2 as v,revision_v2_runtime as vr,revision_sampling as sampling
from test_expert_revision_core import fixture
from test_expert_revision_workflow import revised_body
from test_s28_validation import resident_admission
from test_foldx_development import artifact
from test_expert_revision_v2 import side


def setup(tmp_path,monkeypatch,*,l4=True,flat=False,empty_targets=False,length=100,count=1,model_policy=v.LEGACY_MODEL_POLICY,mutation_budget=None):
    b=revised_body();cfg=v.config('fixture',model_policy=model_policy);_,snap,_,_=fixture(length)
    if mutation_budget is not None:
        cfg['max_mutation_fraction']=mutation_budget
        snap['mutation_budget']['B']=int(length*mutation_budget)
    b.update(protein_sequence='A'*length,revision_config=cfg)
    b['analysis']['developability']=dict(target_ph=None,target_ph_range=[5.,8.],timeout_seconds=60)
    if l4:
        b['analysis']['bepipred']=dict(timeout_seconds=60)
        b['analysis']['netmhc']=dict(mhc_i_alleles=['HLA-A02:01'],mhc_ii_alleles=['DRB1_0101'],timeout_seconds=60)
    scales=json.loads(Path(v.__file__).parents[1].joinpath('design_backend/scales.json').read_bytes())
    w=side();snap['wt_structure_id']=artifact()
    if empty_targets:w['hotspots']=[]
    data=dict(snapshot=snap,scales=scales,options=dict(timeout_seconds=60,t4_empty_fixed_confirmation=True),
        audit=dict(geometry={'residues':w['geometry']},domain_intervals=[],epitope_hotspot_intervals=w['hotspots']))
    raw=[dict(sample_number=1,sequence='S'*count+'A'*(length-count))]
    records=sampling.formal(snap,raw,list(range(1,count+1)),cfg,[],dict(scales=scales,generation_ref=artifact()))
    for r in records:r.update(esm_if1=v.esm(-1,-1),ranking_context={})
    rt=Runtime(tmp_path/'runtime');jid=rt.submit_workflow(encode(b),'fixture')['job_id']
    dims={'expressibility':dict(reliable=True,normalized_score=.6,source='fixture',value={})}
    frozen=dict(wt_side=w,frozen=v.freeze(dims,None),wt_refs={})
    if model_policy==v.SINGLE_MODEL_POLICY:w['prediction_engine']='af3'
    with rt._tx() as db:
        j=rt._job(db,jid);rt._store(db,dict(j,state='running',started_at=now()),j,'fixture')
        rt._execution_store(db,jid,dict(nodes={'formal0':dict(job_id='fixture-formal',state='succeeded')},revision_v2_frozen=frozen,started_at=now()))
    original_source=service.source
    original_get=Runtime.get
    monkeypatch.setattr(Runtime,'get',lambda rt,id:dict(job_id=id,state='succeeded',error_code=None)
                        if id=='fixture-formal' else original_get(rt,id))
    monkeypatch.setattr(service,'source',lambda rt,row:dict(artifact=artifact(),job_id='fixture-formal') if (row or {}).get('job_id')=='fixture-formal' else original_source(rt,row))
    monkeypatch.setattr(Runtime,'result',lambda rt,id:dict(generation=dict(records=raw)) if id=='fixture-formal' else {})
    monkeypatch.setattr(vr,'wt_inputs',lambda *a:copy.deepcopy(frozen))
    if model_policy==v.SINGLE_MODEL_POLICY:
        from t01_phase1_real.development.workflow.revision_structure import route
        monkeypatch.setattr(vr,'structure_engine',lambda rt,ref:route(length,count,cfg)[0] if ref else None)
    def paired(rt,run,seq,refs):
        value=copy.deepcopy(w);value['hotspot_map_state']={'fixture':True}
        row=refs.get('structure');value['quality_condition']=bool(row and rt.get(row['job_id'])['state']=='succeeded')
        return value
    monkeypatch.setattr(vr,'side',paired)
    monkeypatch.setattr(vr,'bp',lambda *a:([.1]*length if flat else [0.,.1]+[.05]*(length-2),{'fixture':True}))
    from t01_phase1_real.development.workflow import candidate_developability,msa_reuse
    monkeypatch.setattr(candidate_developability,'verified_value',lambda *a:dict(developability=dict(dimensions=dims)))
    monkeypatch.setattr(msa_reuse,'ready',lambda *a:(dict(job_id=artifact()['job_id'],artifact=artifact()),None))
    from t01_phase1_real.development.af3 import msa
    from t01_phase1_real.development.foldx import source as fs,result as fr
    from t01_phase1_real.development.developability import service as ds
    from t01_phase1_real.development.esm_if1 import source as registered
    monkeypatch.setattr(msa,'sources',lambda *a:({},{}))
    monkeypatch.setattr(fs,'sources',lambda *a,**k:({'native/target.pdb':b'WT'},{}))
    monkeypatch.setattr(ds,'sources',lambda *a,**k:({},{}))
    monkeypatch.setattr(Runtime,'_structure_bytes',lambda *a:b'fixture-native-structure')
    monkeypatch.setattr(Runtime,'_epitope_sources',lambda *a:({},{}))
    for engine in ('af3','esmfold2'):
        monkeypatch.setattr(service.prediction_source(engine),'verified',lambda *a,**k:dict(quality={'structure':{'mean_plddt':.8}},structure_artifact=dict(artifact(),role='raw'),quality_artifact=artifact()))
    def reg(rt,db,ref,tool):
        if tool.endswith('proteinmpnn'):return {},b'',{}, {},{'native/target.pdb':b'WT'}
        row=rt.execution(jid)['nodes']['z0_s1_foldx'];req=decode(rt._request_bytes(rt.get(row['job_id'])))
        rr=[dict(variant_id=r['variant_id'],native_ddg_runs=[-1,-2,-3,-4,-5]) for r in req['variants']]
        return {},b'',dict(variant_ddg=rr),req,{'native/target.pdb':b'WT','rows':rr}
    monkeypatch.setattr(registered,'registered',reg);monkeypatch.setattr(fr,'parse',lambda req,files:dict(rows=files['rows']))
    calls=[]
    def dispatch(rt,id):
        with rt._tx() as db:
            j=rt._job(db,id);calls.append(j['tool_id'])
            if j['tool_id']=='t01.real.af3':
                from t01_phase1_real.development.workflow.revision_sequence import ready
                assert all(ready(r) for r in records)
            rt._store(db,dict(j,state='running',attempt_id='fixture-'+id,started_at=now()),j,'fixture-start')
    def recover(rt,id):
        with rt._tx() as db:
            j=rt._job(db,id);rt._store(db,dict(j,state='succeeded',finished_at=now()),j,'fixture-complete')
    monkeypatch.setattr(Runtime,'dispatch',dispatch);monkeypatch.setattr(Runtime,'recover',recover)
    return rt,jid,b,data,records,calls


def drain(rt,jid,b,data,records):
    for _ in range(18):
        outcome=vr.tick(rt,jid,b,data,records,0)
        if outcome is not None:return outcome
    pytest.fail('v2 chain did not complete')


@pytest.mark.parametrize('l4,flat,foldx',[(True,False,True),(False,False,False),(True,True,False)])
def test_actual_v2_native_admission_recovery_and_policy_gates(tmp_path,monkeypatch,resident_admission,l4,flat,foldx):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch,l4=l4,flat=flat)
    assert drain(rt,jid,b,data,records)=='S28_ORIGINAL_PASS'
    assert ('t01.real.foldx' in calls) is foldx
    assert calls[:3]==['t01.real.af3','t01.real.ingest_structure','t01.real.developability']
    r=records[0];assert r['protection']['l1_identity_pass'] is False and r['protection']['passed'] is True
    if foldx:
        assert calls[3:]==['t01.real.bepipred','t01.real.netmhc','t01.real.epitope_map','t01.real.foldx']
        assert r['foldx']['valid_count']==5 and r['foldx']['mean']==-3
        assert r['provisional_acceptance_status']=='PASS' and r['acceptance_status']=='NOT_ASSESSED'
        row=rt.execution(jid)['nodes']['z0_s1_foldx'];req=decode(rt._request_bytes(rt.get(row['job_id'])))
        assert len(req['variants'])==1 and req['protein_sequence']=='A'*100
    else:assert r['l4']['prediction_preservation'] is None and r['provisional_acceptance_status']=='NOT_ASSESSED'
    before=copy.deepcopy(rt.execution(jid));count=len(calls)
    assert drain(Runtime(tmp_path/'runtime'),jid,b,data,records)=='S28_ORIGINAL_PASS'
    assert len(calls)==count and rt.execution(jid)==before


def test_confirmed_empty_targets_survive_incomplete_predictors_and_recovery(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch,l4=False,empty_targets=True)
    assert drain(rt,jid,b,data,records)=='S28_ORIGINAL_PASS'
    r=records[0]
    assert 't01.real.foldx' in calls and r['foldx']['valid_count']==5
    assert r['l4']['check_status']=='NOT_APPLICABLE' and not r['l4']['execution_complete']
    assert r['l4']['prediction_preservation'] is None and r['evidence_group']=='C'
    assert r['acceptance_score'] is None and not r['final_evidence_complete']
    from t01_phase1_real.service_api.native_report import build
    html=build({},dict(expert_revision=dict(formal_records=records)))['candidates']
    assert '不适用' in html and '此候选保留参考身份' in html
    assert '保护轴和完整验收不补分' in html
    summary=next(s for s in r['protection']['check_summaries'] if s['check_id']=='l4')
    assert summary['reason_codes']==['CONFIRMED_EMPTY_TARGETS']
    assert summary['applicability_evidence']==r['protection']['applicability_evidence']
    before=copy.deepcopy(rt.execution(jid));count=len(calls)
    assert drain(Runtime(tmp_path/'runtime'),jid,b,data,records)=='S28_ORIGINAL_PASS'
    assert rt.execution(jid)==before and len(calls)==count


def test_cancellation_and_identity_tamper_stop_downstream(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    assert vr.tick(rt,jid,b,data,records,0) is None
    with rt._tx() as db:rt._stop(db,rt._job(db,jid),'cancel')
    service.stop_children(rt,jid)
    assert vr.tick(rt,jid,b,data,records,0) is None and calls==['t01.real.af3']


def test_v2_child_bound_identity_replayed(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    drain(rt,jid,b,data,records)
    with rt._tx() as db:
        ex=rt._execution(db,jid);ex['revision_bindings']['z0_s1_bepipred']['content_hashes']=['foreign'];rt._execution_store(db,jid,ex)
    with pytest.raises(RuntimeFault,match='identity'):vr.enrich(rt,jid,b,data,records)


def test_main_controller_freeze_and_dispatches_v2(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(rc,'inputs',lambda *a:(data,None))
    original_child=rc.child
    def child(rt,jid,body,name,req):
        if name in wiring.CHILDREN:return original_child(rt,jid,body,name,req)
        service._record(rt,jid,name,dict(job_id='fixture-formal' if name=='formal0' else None,state='succeeded',origin='ENGINEERING_FIXTURE',reason_code=None))
        return True
    monkeypatch.setattr(rc,'child',child)
    def assembly(rt,jid,b,data,**kwargs):
        from t01_phase1_real.development.workflow.revision_sequence import attach
        attach(records)
        wiring.enrich(rt,jid,b,data,records)
        return dict(proposal_summary=dict(nomination_positions=[1],quarantine_receipts=[],valid_count=24),formal_records=copy.deepcopy(records),design_outcomes=[])
    monkeypatch.setattr(rc,'assemble',assembly)
    for _ in range(18):
        if rc.tick(rt,jid,b):break
    else:pytest.fail('v2 main controller did not finish')
    ex=rt.execution(jid)
    assert ex['revision_round_outcomes']=={'0':'S28_ORIGINAL_PASS'}
    assert ex['revision_state']['formal_records'][0]['foldx']['valid_count']==5
    assert ex['revision_v2_frozen']['frozen']['frozen_before_generation']
    assert len(calls)==7


def test_freeze_requires_pre_generation_and_detects_changed_inputs(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    expected=vr.verified_freeze(rt,jid,b)
    with rt._tx() as db:
        ex=rt._execution(db,jid);ex.pop('revision_v2_frozen');rt._execution_store(db,jid,ex)
    with pytest.raises(RuntimeFault,match='before generation'):vr.freeze(rt,jid,b)
    with rt._tx() as db:
        ex=rt._execution(db,jid);ex['nodes']={};rt._execution_store(db,jid,ex)
    assert vr.freeze(rt,jid,b)==expected
    monkeypatch.setattr(vr,'wt_inputs',lambda *a:dict(expected,frozen={}))
    with pytest.raises(RuntimeFault,match='changed'):vr.verified_freeze(rt,jid,b)


def test_pool_replay_and_cumulative_budget(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    drain(rt,jid,b,data,records);vr.verify_allocations(rt,jid,b,records)
    with rt._tx() as db:
        ex=rt._execution(db,jid);ex['revision_v2_allocations']['foldx0']['selected_candidate_ids']=[];rt._execution_store(db,jid,ex)
    with pytest.raises(RuntimeFault,match='allocation changed'):vr.verify_allocations(rt,jid,b,records)


def test_real_assembly_schema_and_html_replay(tmp_path,monkeypatch,resident_admission):
    rt,jid,b,data,records,calls=setup(tmp_path,monkeypatch)
    drain(rt,jid,b,data,records)
    requests={};raw=[dict(sample_number=1,sequence=records[0]['sequence'])]
    original_bytes=Runtime._request_bytes;original_source=service.source
    for name in ('proposal0','proposal1','cheap0'):
        with rt._tx() as db:
            ex=rt._execution(db,jid);ex['nodes'][name]=dict(job_id='fixture-'+name,state='succeeded');rt._execution_store(db,jid,ex)
    def src(rt,row):
        if row and str(row.get('job_id')).startswith('fixture-'):
            return dict(job_id=row['job_id'],artifact=artifact())
        return original_source(rt,row)
    monkeypatch.setattr(service,'source',src)
    def generation(rt,body,rows,name,run):
        stage='proposal_only' if name.startswith('proposal') else 'formal';index=int(name[-1])
        req=rc._native_request(body,data,stage,index,data['snapshot']['eligible_positions'] if stage=='proposal_only' else [1])
        job=dict(job_id=rows[name]['job_id'],execution_identity=name)
        requests[job['job_id']]=req
        return dict(records=raw),artifact(),job
    monkeypatch.setattr(rc,'generation',generation)
    monkeypatch.setattr(Runtime,'_request_bytes',lambda rt,j:encode(requests[j['job_id']]) if j['job_id'] in requests else original_bytes(rt,j))
    from t01_phase1_real.development.esm_if1 import source as es,result as er
    prior=es.registered;observation=dict(baseline=dict(score=-1.),records=[dict(sample_number=1,score=-1.)])
    def reg(rt,db,ref,tool):
        if tool!='t01.real.esm_if1':return prior(rt,db,ref,tool)
        request=dict(sample_numbers=[1],n11_artifact=artifact(),shared_contract_version=rc.contract.VERSION,calculation_config_id='fixture')
        return {},b'',dict(scoring=observation,shared_contract_version=rc.contract.VERSION,calculation_config_id='fixture'),request,{}
    monkeypatch.setattr(es,'registered',reg);monkeypatch.setattr(es,'sources',lambda *a,**k:({},{}))
    monkeypatch.setattr(er,'validate_observation',lambda *a:observation)
    fact=rc.assemble(rt,jid,b,data)
    assert fact['formal_records'][0]['foldx']['valid_count']==5
    assert fact['formal_records'][0]['comparison_score'] is not None
    assert fact['provisional_acceptance_status']=='PASS' and fact['acceptance_status']=='NOT_ASSESSED'
    assert fact['coverage_complete'] is False  # Fixture emits one of 24 requested; never claim full coverage.
    from t01_phase1_real.service_api.user_report import render
    html=render({},dict(state='succeeded',expert_revision=fact)).decode()
    assert '暂定验收' in html and '没有跨组总排名' in html and '完整覆盖：未完成' in html
    assert '结构预测前的序列型可开发性' in html and '分子量（kDa）' in html
    assert rc.assemble(rt,jid,b,data)==fact
