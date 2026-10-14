"""Items 5–8 source/scope/numerical regressions; synthetic cases, no model runs."""
import copy
import io
from contextlib import nullcontext
import numpy as np
import pytest
from t01_phase1_real.common import RuntimeFault,encode,decode,sha
from t01_phase1_real.development.wt_reference.consensus import classify,evaluate


@pytest.mark.parametrize('a,b,expected',[(.2,.2,'high_consensus'),(.2,.5,'medium_consensus'),
    (.5,.2,'medium_consensus'),(.51,.6,'low_consensus'),(None,.9,'single_engine'),(None,None,'no_consensus'),
    (.3,.4,None),(.1,.8,None),(.5,.7,None)])
def test_r40_defined_thresholds_and_uncovered_cases(a,b,expected):
    assert classify(a,b)==expected


def test_r40_preserves_native_denominators_self_and_energy_separation():
    rows=[dict(position=1,wt='A',mut=a,rank_foldx=i+1,ddg_foldx=i-5.) for i,a in enumerate('ACDEFGHIKLMNPQRSTVWY')]
    thermo=[dict(position=1,wt='A',mut=r['mut'],rank_thermompnn=i+1,ddg_thermompnn=300-i) for i,r in enumerate(rows[1:])]
    engines=dict(foldx={'records':rows},thermompnn={'records':thermo})
    before=copy.deepcopy(engines);r=evaluate(engines)
    assert len(r['records'])==19 and engines==before
    first=r['records'][0]
    assert first['engines']['foldx']['comparison_count']==20
    assert first['engines']['thermompnn']['comparison_count']==19
    assert first['consensus_rank']=='high_consensus' and first['combined_ddg'] is None
    assert first['ddg']==dict(foldx=-4.,thermompnn=300)
    thermo[0]['rank_thermompnn']=None
    assert evaluate(engines)['records'][0]['reason']=='ENGINE_RANK_MISSING'


@pytest.mark.parametrize('size',[24,48,64])
def test_full_n13_pool_survives_past_slot_three_and_keeps_legacy(monkeypatch,size):
    from t01_phase1_real.development.variant_report import m1,source,compute
    from t01_phase1_real.development.workflow import validation,service
    from t01_phase1_real.development.workflow import m1 as workflow
    rows=[dict(id='s'+str(i),sample_number=i,sequence='C'+'A'*19,sequence_sha256=sha(('C'+'A'*19).encode()),
        mutations=[dict(position=1,wt='A',mut='C')],esm_if1={'esm_if1_score':-i},
        disposition='UNDETERMINED',exclusion_reasons=[]) for i in range(1,size+1)]
    monkeypatch.setattr(source,'sources',lambda *a:({}, {},{'design_audit':{'state':'available'}}))
    monkeypatch.setattr(compute,'preselection_rows',lambda *a:copy.deepcopy(rows))
    checks=[dict(sample_number=i,selected='af3',engines={'af3':{'source':{'job_id':'p'+str(i)}}}) for i in range(1,size+1)]
    monkeypatch.setattr(validation,'verified_fact',lambda *a:dict(source_jobs={'design_audit':{}},review_pool=list(range(1,size+1)),records=checks))
    context=dict(workflow_job_id='parent',node='validation')
    fact=m1.verified_preselection(None,None,'A'*20,'test',{},context,'ALL_VALIDATED')
    assert len(fact['selected'])==size and fact['sample_numbers']==list(range(1,size+1))
    active={'preselection':{'state':'succeeded','fact':fact}}
    assert workflow.prediction_engine(active,f'rep{size}_prediction')=='af3'
    assert workflow.sequence(None,{},active,f'rep{size}_prediction')=='C'+'A'*19
    assert service.worker(f'rep{size}_prediction',{},active).TOOL=='t01.real.af3'
    assert len(m1.verified_preselection(None,None,'A'*20,'test',{},context)['selected'])==3
    with pytest.raises(RuntimeFault):m1.verified_preselection(None,None,'A'*20,'test',{},None,'ALL_VALIDATED')


def test_calibration_sampling_is_batch_independent_and_moments_match_numpy():
    from t01_phase1_real.development.developability.calibration import assets,batches,moments,calibrate
    f=assets()['frequencies']
    a=np.concatenate(list(batches(f,count=113,batch_size=7)))
    b=np.concatenate(list(batches(f,count=113,batch_size=64)))
    assert np.array_equal(a,b) and a.shape==(113,200)
    result=moments(np.array_split(a.astype(float),17))
    assert result['mean']==pytest.approx(a.mean(),abs=1e-12)
    assert result['population_std']==pytest.approx(a.std(),abs=1e-12)
    r=calibrate(lambda x:x.astype(float),f,count=113,batch_size=7)
    assert r['diagnostic_moments']==moments(np.array_split(a.astype(float),range(7,113,7)))
    assert r['mu_random'] is None and r['sigma_random'] is None and not r['scientific_consumption']
    with pytest.raises(RuntimeFault):calibrate(lambda x:np.zeros(1),f,count=1)


def test_calibration_assets_keep_public_sign_and_expert_unchanged():
    from t01_phase1_real.development.developability.calibration import assets
    from t01_phase1_real.development.developability.camsol import parameters,ASSET,ASSET_SHA256
    m=assets();assert m['roseman_public_values']['I']>0 and m['roseman_public_values']['R']<0
    assert m['roseman_transform'] is None and m['pattern_count'] is None
    assert sha(ASSET.read_bytes())==ASSET_SHA256
    assert parameters()['random_normalization']['mu_random'] is None


def dna_fixture(monkeypatch):
    from t01_phase1_real.development.codon import policy,lineage
    from t01_phase1_real.development.design_backend import source as registered
    from t01_phase1_real.development.variant_report import source,compute
    from test_codon_development import body
    b=body();b.update(input_kind='VERIFIED_N15_ENGINEERING_CANDIDATE',candidate_source={'source':{'job_id':'report','artifact':None},'candidate_id':'c1'})
    report=dict(records=[dict(id='c1',sequence=b['protein_sequence'],sequence_sha256=sha(b['protein_sequence'].encode()),exclusion_reasons=[])],
        engineering_selection=dict(top20=['c1'],sc10={'overall_pass':True}))
    class RT:
        job=dict(run_id='run',state='succeeded')
        def _job(self,db,jid):return self.job
        def _request_bytes(self,job):return encode(dict(protein_sequence='A'*20))
        def result(self,jid):return dict(report=report)
    monkeypatch.setattr(registered,'sources',lambda *a,**kw:({},dict(report={'report':report}),{}))
    monkeypatch.setattr(source,'sources',lambda *a:({}, {},{}))
    monkeypatch.setattr(compute,'evaluate',lambda *a:copy.deepcopy(report))
    return RT(),b,report


@pytest.mark.parametrize('bad',['foreign_run','sequence','excluded','nonstandard','threshold','not_selected','tampered_report'])
def test_n16_rejects_invalid_lineage(monkeypatch,bad):
    from t01_phase1_real.development.codon.lineage import verify
    from t01_phase1_real.development.variant_report import compute
    rt,b,report=dna_fixture(monkeypatch)
    if bad=='foreign_run':rt.job=dict(run_id='foreign',state='succeeded')
    if bad=='sequence':b['protein_sequence']='A'*20
    if bad=='excluded':report['records'][0]['exclusion_reasons']=['R35']
    if bad=='nonstandard':report['records'][0]['non_standard']=True
    if bad=='threshold':report['engineering_selection']['sc10']['overall_pass']=False
    if bad=='not_selected':report['engineering_selection']['top20']=[]
    if bad=='tampered_report':monkeypatch.setattr(compute,'evaluate',lambda *a:{})
    with pytest.raises(RuntimeFault):verify(rt,None,b,'run')


def test_n16_all_selected_slots_explicit_host_and_lineage(monkeypatch):
    from t01_phase1_real.development.codon.lineage import verify
    from t01_phase1_real.development.workflow import candidate_dna,service
    rt,b,report=dna_fixture(monkeypatch)
    assert decode(verify(rt,None,b,'run')['input/candidate-lineage.json'])['candidate_id']=='c1'
    report['records']=[dict(report['records'][0],id='c'+str(i)) for i in range(1,21)]
    report['engineering_selection']['top20']=[r['id'] for r in report['records']]
    monkeypatch.setattr(service,'source',lambda *a:{'job_id':'report','artifact':None})
    rows={'variant_report':dict(state='succeeded',job_id='report')}
    for name in candidate_dna.ORDER:
        req,reason=candidate_dna.request(rt,b,rows,name)
        assert reason is None and req['candidate_source']['candidate_id'] in report['engineering_selection']['top20']
        assert service.worker(name).TOOL=='t01.real.optimize_codons'
    req,_=candidate_dna.request(rt,b,rows,'codon20');assert req['candidate_source']['candidate_id']=='c20'
    b['expression_host']=None;assert candidate_dna.request(rt,b,rows,'codon')==(None,'EXPRESSION_HOST_NOT_PROVIDED')
    b['expression_host']='CHO';assert candidate_dna.request(rt,b,rows,'codon')[0]['host_profile'] is None


def test_html_discloses_dna_fallback_and_consensus_without_overflow_markup():
    from t01_phase1_real.service_api.user_report import render
    data=dict(dna=[dict(subject='c<1',source_status='optimization_incomplete',reason='UNOPTIMIZED_DNA_FALLBACK',dna={'initial_dna':'ACGT'*500})],
        wt_reference={'consensus_ranking':dict(records=[dict(consensus_rank=None,reason='R40_COMBINATION_UNDEFINED')])})
    html=render(data,{}).decode()
    assert '表达序列' in html and 'c&lt;1' in html and 'ACGT'*500 in html
    assert '原蛋白稳定性扫描共识' in html and '规则未定义或覆盖不足时保持未评估' in html


def test_n16_worker_persists_lineage_and_rechecks_before_publication(tmp_path,monkeypatch):
    from t01_phase1_real.development.codon import lineage,policy
    from t01_phase1_real.development import Runtime
    from test_codon_development import body,run
    rt=Runtime(tmp_path);b=body();b.update(input_kind='VERIFIED_N15_ENGINEERING_CANDIDATE',
        candidate_source=dict(source={'job_id':'fixture','artifact':None},candidate_id='c1'))
    calls=[]
    def verified(rt,db,request,run_id):
        calls.append(run_id)
        return {'input/candidate-lineage.json':encode(dict(synthetic_only=True,sequence_sha256=sha(request['protein_sequence'].encode())))}
    monkeypatch.setattr(lineage,'verify',verified)
    job=run(rt,b);assert job['state']=='succeeded',rt.result(job['job_id'])
    value=rt.result(job['job_id'])
    assert len(calls)==2 and calls==[job['run_id']]*2
    assert value['candidate_source']==b['candidate_source'] and value['dna']['optimized_dna']
    assert not value['usable_for_pipeline']
    monkeypatch.setattr(lineage,'verify',lambda *a: (_ for _ in ()).throw(RuntimeFault('FORBIDDEN','foreign')))
    job=run(rt,b,key='reject');assert job['error_code']=='FORBIDDEN'
    assert rt.result(job['job_id'])['execution']['worker_started'] is False
