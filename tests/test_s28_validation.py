"""S28 control and scientific boundary fixtures; no synthetic science evidence."""
import copy
from contextlib import nullcontext
import pytest
from t01_phase1_real.common import RuntimeFault,encode,now
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import validation as v,service,policy,design_rounds
from test_local_workflow import body


@pytest.fixture
def resident_admission(monkeypatch):
    # No model execution; retain actual database admission and request validation.
    from t01_phase1_real import resident_execution as resident
    monkeypatch.setattr(resident,'enabled',lambda:True)
    monkeypatch.setattr(resident,'configuration',lambda:({'tools':{}},None))
    monkeypatch.setattr(resident,'registered',lambda *a:None)


@pytest.mark.parametrize('length,count,partial,engines',[
    (250,5,False,['af3']),(250,6,False,[]),(100,5,False,[]),
    (100,6,False,['af3','esmfold2']),(100,10,False,['af3','esmfold2']),
    (100,11,False,['esmfold2']),(20,5,False,[]),(20,6,False,['esmfold2']),
    (250,5,True,['esmfold2']),(100,0,False,['af3'])])
def test_only_defined_intersections_route(length,count,partial,engines):
    assert v.route(length,count,partial)['engines']==engines


def outcome(scores,passed=True):
    obs={engine:dict(state='prediction_failed' if q=='failed' else 'not_executed' if q is None else 'succeeded',plddt=q)
         for engine,q in scores.items()}
    return v.decision(dict(passed=passed),obs,dict(engines=list(scores),reason='UNRESOLVED'))


@pytest.mark.parametrize('scores,passed,expected,reason',[
    ({'esmfold2':.5},True,True,'S28_PASSED'),
    ({'esmfold2':.499},True,False,'PLDDT_BELOW_0_50'),
    ({'esmfold2':'failed'},True,True,'S28_PREDICTION_FAILED_RETAIN_R35'),
    ({'esmfold2':None},True,None,'STRUCTURE_VALIDATION_NOT_EXECUTED'),
    ({'af3':.4,'esmfold2':.7},True,True,'S28_PASSED'),
    ({'af3':.4,'esmfold2':.3},True,False,'PLDDT_BELOW_0_50'),
    ({'af3':.4,'esmfold2':'failed'},True,None,'DUAL_ENGINE_INCOMPLETE_LOW_AVAILABLE_PLDDT'),
    ({'af3':None,'esmfold2':.7},True,True,'S28_PASSED'),
    ({'af3':'failed','esmfold2':'failed'},True,True,'S28_PREDICTION_FAILED_RETAIN_R35'),
    ({},False,False,'R35_DETERIORATION_EXCEEDED'),({},None,None,'R35_UNAVAILABLE'),
    ({},True,None,'UNRESOLVED')])
def test_rejection_failure_and_unknown_are_distinct(scores,passed,expected,reason):
    fact=outcome(scores,passed)
    assert fact['passed'] is expected and fact['reason']==reason
    if scores=={'af3':.4,'esmfold2':.7}:assert fact['selected']=='esmfold2'


@pytest.mark.parametrize('q',[50,float('nan'),float('inf'),True,-.1])
def test_confidence_must_be_normalized_and_finite(q):
    with pytest.raises(RuntimeFault):outcome({'esmfold2':q})


def inventory(n,passed=True,partial=True):
    return dict(generation=[dict(sample_number=i,sequence='C'+'A'*99,mutations=[dict(position=1)]) for i in range(1,n+1)],
        scores=[dict(sample_number=i,passed=passed) for i in range(1,n+1)],
        audit=dict(burden_records=[dict(sample_number=i,engineering_thresholds=dict(any_known_exceeded=True)) for i in range(1,n+1)]),
        refs={},partial=partial,low=[dict(start=1,end=5)],baseline=-1.)


@pytest.mark.parametrize('name,count',[('validation',24),('retry1_validation',48),('retry2_validation',64)])
def test_every_generated_candidate_and_burden_included(monkeypatch,name,count):
    data=inventory(count);seen=[]
    monkeypatch.setattr(v,'inputs',lambda *a:data)
    def observe(rt,b,rows,key,run_id):
        seen.append(key)
        return dict(state='succeeded',plddt=.8,structure={'sample':key})
    monkeypatch.setattr(v,'observation',observe)
    fact=v.assemble(None,{}, {},name,'run')
    assert len(seen)==count and len(fact['records'])==count
    assert fact['review_pool']==list(range(1,count+1)) and fact['status']=='REVIEW_POOL'
    assert all(r['burden_exceeded'] and r['baseline_used']==-1 and r['low_confidence_mutations']==[1] for r in fact['records'])
    assert all(r['passed'] and r['validation_confidence']=='degraded' for r in fact['records'])
    assert not fact['usable_for_pipeline']


@pytest.mark.parametrize('passed,status',[(False,'ALL_REJECTED'),(None,'VALIDATION_UNAVAILABLE')])
def test_r35_rejected_or_unknown_never_invokes_prediction(monkeypatch,passed,status):
    monkeypatch.setattr(v,'inputs',lambda *a:inventory(24,passed))
    monkeypatch.setattr(v,'observation',lambda *a:pytest.fail('Unexpected prediction'))
    assert v.assemble(None,{}, {},'validation','run')['status']==status


def test_empty_generation_is_not_all_rejected(monkeypatch):
    monkeypatch.setattr(v,'inputs',lambda *a:inventory(0))
    assert v.assemble(None,{}, {},'validation','run')['status']=='NO_CANDIDATES'


@pytest.mark.parametrize('status',['NO_CANDIDATES','VALIDATION_UNAVAILABLE','REVIEW_POOL'])
def test_retry_requires_complete_all_rejected_validation(monkeypatch,status):
    class Stub:
        def get(self,jid):return dict(job_id=jid,artifacts=[dict(role='result')])
    rt=Stub();src=service.source(rt,dict(job_id='n11'))
    monkeypatch.setattr(v,'verified_fact',lambda *a:dict(status=status,source_jobs=dict(design=src)))
    rows=dict(design=dict(job_id='n11'),design_audit=dict(state='succeeded'),
        validation=dict(state='succeeded',validation_source=dict(workflow_job_id='flow',node='validation')))
    assert design_rounds.request(rt,{},rows,'retry1_design')==(None,status)
    del rows['validation']
    assert design_rounds.request(rt,{},rows,'retry1_design')==(None,'S28_VALIDATION_NOT_COMPLETE')


def controller(tmp_path):
    rt=Runtime(tmp_path/'runtime');b=body();b.update(engineering_design='BACKEND_EVIDENCE_V1')
    j=rt.submit_workflow(encode(b),'s28');jid=j['job_id']
    with rt._tx() as db:
        old=rt._job(db,jid);rt._store(db,dict(old,state='running',started_at=now()),old,'fixture')
        rt._execution_store(db,jid,dict(nodes={},started_at=now(),phase='scheduling',dispatcher=None))
    return rt,jid,b


def test_native_child_restart_idempotence_and_cancel_fence(tmp_path,resident_admission):
    rt,jid,b=controller(tmp_path)
    req=dict(protein_sequence=b['protein_sequence'],user_sequence_id=b['user_sequence_id'],host_species=b['host_species'],seed=1,timeout_seconds=90)
    first=service._create_child(rt,jid,'v0_s24_esmfold2',req)
    assert rt.get(first)['run_id']==rt.get(jid)['run_id']
    restarted=Runtime(tmp_path/'runtime')
    assert service._create_child(restarted,jid,'v0_s24_esmfold2',req)==first
    with rt._tx() as db:rt._stop(db,rt._job(db,jid),'cancel')
    assert service._create_child(restarted,jid,'v1_s48_esmfold2',req) is None
    service.stop_children(restarted,jid)
    assert restarted.get(first)['state']=='cancelled'


@pytest.mark.parametrize('round_name,count,index',[
    ('validation',24,0),('retry1_validation',48,1),('retry2_validation',64,2)])
def test_controller_covers_every_round_resumes_and_does_not_duplicate(monkeypatch,tmp_path,resident_admission,round_name,count,index):
    rt,jid,b=controller(tmp_path);data=inventory(count);seen=[]
    monkeypatch.setattr(v,'inputs',lambda *a:data)
    monkeypatch.setattr(rt,'dispatch',lambda child:seen.append(child))
    monkeypatch.setattr(rt,'recover',lambda child:seen.append(child))
    completed=set()
    def observation(rt,b,rows,key,run):
        if key in completed:return dict(state='succeeded',plddt=.8,structure={'key':key})
        return None
    monkeypatch.setattr(v,'observation',observation)
    for sample in range(1,count+1):
        assert v.tick(rt,jid,b,round_name) is False
        rows=rt.execution(jid)['nodes'];key=f'v{index}_s{sample}_esmfold2';child=rows[key]['job_id']
        assert len([r for r in rows.values() if r.get('job_id')])==sample
        assert v.tick(rt,jid,b,round_name) is False
        assert rt.execution(jid)['nodes'][key]['job_id']==child
        completed.add(key)
    assert v.tick(rt,jid,b,round_name) is True
    fact=rt.execution(jid)['nodes'][round_name]['fact']
    assert fact['review_pool']==list(range(1,count+1)) and len(set(seen))==count
    # Resume a completed fact by recomputing its sources, not by creating jobs.
    assert v.tick(rt,jid,b,round_name) is True
    assert len(set(seen))==count
    with rt._tx() as db:
        ex=rt._execution(db,jid);ex['nodes'][round_name]['fact']['review_pool'].pop();rt._execution_store(db,jid,ex)
    with pytest.raises(RuntimeFault,match='differs'):v.verified_fact(rt,jid,round_name)


def test_unsupported_af3_does_not_start_or_count_as_rejection(monkeypatch,tmp_path):
    rt,jid,b=controller(tmp_path);data=inventory(24,partial=False)
    # Exercise the asset-cap guard independently of today's 999 aa profile.
    monkeypatch.setattr(service.worker('v0_s1_af3'),'MAX_AA',76)
    monkeypatch.setattr(v,'inputs',lambda *a:data)
    monkeypatch.setattr(rt,'dispatch',lambda *a:pytest.fail('Unsupported AF3 launched'))
    assert v.tick(rt,jid,b,'validation')
    fact=rt.execution(jid)['nodes']['validation']['fact']
    assert fact['status']=='VALIDATION_UNAVAILABLE' and fact['unavailable']==list(range(1,25))
    assert not fact['rejected']


def test_quality_reads_native_nested_structure(monkeypatch):
    class Stub:
        def _db(self):return nullcontext(None)
    job=dict(job_id='p',state='succeeded',artifacts=[dict(role='result')])
    monkeypatch.setattr(service,'verified',lambda *a:job)
    monkeypatch.setattr(service,'source',lambda *a:dict(job_id='p'))
    monkeypatch.setattr(v,'child_sequence',lambda *a:'A'*20)
    from t01_phase1_real.development.esmfold2 import source
    monkeypatch.setattr(source,'verified',lambda *a,**k:dict(quality={'structure':{'mean_plddt':.75}},structure_artifact={},quality_artifact={}))
    result=v.observation(Stub(),dict(host_species='pig'),{'v0_s1_esmfold2':{'job_id':'p'}},'v0_s1_esmfold2','run')
    assert result['plddt']==.75


def test_preselection_filters_by_complete_validation_and_keeps_structure(monkeypatch):
    from t01_phase1_real.development.variant_report import m1,source,compute
    from t01_phase1_real.development.workflow import m1 as workflow
    from t01_phase1_real.common import sha
    rows=[dict(id='sample-'+str(i),sample_number=i,sequence='C'+'A'*19,sequence_sha256=sha(('C'+'A'*19).encode()),
        mutations=[dict(position=1,wt='A',mut='C')],esm_if1={'esm_if1_score':-i},
        disposition='UNDETERMINED',exclusion_reasons=[]) for i in range(1,7)]
    monkeypatch.setattr(source,'sources',lambda *a:({}, {},{'design_audit':{'state':'available'}}))
    monkeypatch.setattr(compute,'preselection_rows',lambda *a:copy.deepcopy(rows))
    facts=[dict(sample_number=i,selected='af3',engines={'af3':{'source':{'job_id':'prediction'}}}) for i in (4,5,6)]
    monkeypatch.setattr(v,'verified_fact',lambda *a:dict(source_jobs={'design_audit':{}},review_pool=[4,5,6],records=facts))
    fact=m1.verified_preselection(None,None,'A'*20,'test',{},dict(workflow_job_id='parent',node='validation'))
    assert fact['sample_numbers']==[4,5,6]  # Better-scoring samples 1..3 failed structure validation.
    assert fact['selected'][0]['validation']==facts[0]
    selection={'preselection':{'state':'succeeded','fact':fact}}
    assert workflow.prediction_engine(selection,'rep1_prediction')=='af3'
    assert service.worker('rep1_prediction',{},selection).TOOL=='t01.real.af3'
    with pytest.raises(RuntimeFault,match='audit differs'):
        m1.verified_preselection(None,None,'A'*20,'test',{'job_id':'foreign'},dict(workflow_job_id='parent',node='validation'))


@pytest.mark.parametrize('engine',['af3','esmfold2'])
def test_link_adapter_keeps_native_engine(monkeypatch,engine):
    from t01_phase1_real.development import n12_prediction_evidence as adapter
    class Stub:
        def _job(self,db,jid):return {'tool_id':'t01.real.'+engine}
    calls=[]
    monkeypatch.setattr(service.prediction_source(engine),'verified',lambda *a,**k:calls.append((a,k)) or {'engine':engine})
    assert adapter.verified_prediction(Stub(),None,'pred','AAA','pig','same-run',True)=={'engine':engine}
    assert calls[0][0][2:]==('pred','AAA','pig','same-run') and calls[0][1]['include_quality']


@pytest.mark.parametrize('count,temp,prefix,next_name,next_count,next_temp',[
    (24,.1,'','retry1_design',48,.3),(48,.3,'retry1_','retry2_design',64,.5)])
def test_all_structure_rejections_trigger_retry_even_when_r35_passes(monkeypatch,count,temp,prefix,next_name,next_count,next_temp):
    data=inventory(count)
    monkeypatch.setattr(v,'inputs',lambda *a:data)
    monkeypatch.setattr(v,'observation',lambda *a:dict(state='succeeded',plddt=.49,structure={}))
    fact=v.assemble(None,{}, {},prefix+'validation','run')
    assert fact['status']=='ALL_REJECTED' and all(r['esm_if1']['passed'] for r in fact['records'])
    class Stub:
        def get(self,jid):return dict(job_id=jid,artifacts=[dict(role='result')])
        def _request_bytes(self,j):return encode(dict(n_designs=count,sampling_temperature=temp,constraints={'same':True}))
    rt=Stub();fact['source_jobs']['design']=service.source(rt,{'job_id':'n11'})
    monkeypatch.setattr(v,'verified_fact',lambda *a:fact)
    rows={prefix+'design':{'job_id':'n11'},prefix+'design_audit':{'state':'succeeded'},
        prefix+'validation':dict(state='succeeded',validation_source=dict(workflow_job_id='parent',node=prefix+'validation'))}
    req,reason=design_rounds.request(rt,{},rows,next_name)
    assert reason is None and req==dict(n_designs=next_count,sampling_temperature=next_temp,constraints={'same':True})


def test_report_preserves_structure_rejection_and_unknown(monkeypatch):
    from t01_phase1_real.development.variant_report import compute
    from test_variant_report_development import request
    from t01_phase1_real.common import sha
    rows=[dict(id='sample-'+str(i),sample_number=i,sequence_sha256=sha(b'ACDE'),esm_if1={'passed':True},
        foldx=None,disposition='UNDETERMINED',exclusion_reasons=[],non_standard=False,
        sequence='ACDE',mutations=[],burden=None,
        engineering_hard_filter={'flags':dict(constraint_override=None,burden_exceeded=None)}) for i in (1,2)]
    monkeypatch.setattr(compute,'preselection_rows',lambda *a:copy.deepcopy(rows))
    validation=dict(records=[dict(sample_number=i,sequence_sha256=sha(b'ACDE'),passed=False if i==1 else None,
        degraded=i==2,reason='PLDDT_BELOW_0_50' if i==1 else 'R04_ROUTE_UNRESOLVED') for i in (1,2)])
    files={'input/source-receipts.json':encode({k:{'state':'missing'} for k in ('design_audit','foldx')}),
           'input/s28-validation.json':encode(validation)}
    report=compute.evaluate(request(),files)
    assert report['records'][0]['disposition']=='EXCLUDED'
    assert report['records'][1]['disposition']=='UNDETERMINED'
    assert report['summary']['excluded']==1 and report['n12_validation']==validation


def test_html_reports_per_round_coverage_and_missing_validation():
    from t01_phase1_real.service_api.user_report import render
    data=dict(n12_validation=[dict(records=[{},{}],review_pool=[],rejected=[1],unavailable=[2])],
        variant_report={'records':[dict(id='sample-2',s28_validation=dict(passed=None,degraded=True,reason='R04_ROUTE_UNRESOLVED'))]})
    html=render(data).decode()
    assert '逐轮候选验证' in html and '未完成验证' in html and '尚待明确' in html
