"""S40 formula and candidate-lineage regression; positive data are synthetic."""
import copy
import math
from contextlib import nullcontext
import pytest
from t01_phase1_real.common import RuntimeFault,encode,sha
from t01_phase1_real.development.developability import compute,policy
from t01_phase1_real.development.workflow import candidate_developability as cd,service,validation,engineering
from test_variant_selection import fixture


def components():
    _,c,_,_,_=fixture()
    return c


def summarize(c,weights=None,ddg=None,**kw):
    return compute.summarize({'dimension_weights':weights},*(c[k] for k in cd.FIELDS),stability_ddg=ddg,**kw)


def test_default_equal_weights_reliability_and_real_ddg():
    c=components();r=summarize(c,ddg=-2)
    assert r['overall_score']==pytest.approx((.8+.8+1/(1+math.exp(-1)))/3)
    assert r['dev_dims_available']==3 and r['effective_weights']['stability_ddg']==pytest.approx(1/3)
    assert r['weight_policy']=='S40_EQUAL_INITIAL_PENDING_BACKTEST'
    assert r['effective_weights']['aggregation']==0 and not r['automatic_design_release']
    old=summarize(c,legacy_weights=True)
    assert old['overall_score'] is None and old['dimension_weights'] is None and 'weight_policy' not in old


def test_omitted_weights_and_explicit_override():
    from test_developability_development import request
    body=request();body.pop('dimension_weights')
    assert policy.request(encode(body))['dimension_weights'] is None
    w=dict.fromkeys(policy.DIMENSIONS,0.);w['solubility']=3;w['stability_ddg']=1
    r=summarize(components(),w,0)
    assert r['overall_score']==pytest.approx(.725) and r['weight_policy']=='EXPLICIT'
    assert r['effective_weights']['solubility']==.75
    assert summarize(components(),dict.fromkeys(policy.DIMENSIONS,0.))['overall_score'] is None


@pytest.mark.parametrize('status',['unknown','unavailable','unreliable'])
def test_required_solubility_never_filled_by_other_dimensions(status):
    c=components();c['solubility']['status']=status
    r=summarize(c,ddg=-10)
    assert r['overall_score'] is None and r['dev_dims_available']==2
    assert not any(r['effective_weights'].values())
    assert 'solubility' in r['excluded_dimensions']


@pytest.mark.parametrize('ddg',[None,-10000,0,10000])
def test_missing_ddg_excluded_and_finite_extremes(ddg):
    r=summarize(components(),ddg=ddg)
    d=r['dimensions']['stability_ddg']
    assert d['included_in_overall']==(ddg is not None)
    assert d['normalized_score']==(None if ddg is None else 1 if ddg<0 else .5 if ddg==0 else 0)


def setup_candidate(monkeypatch,count=24):
    seq='ACDEFGHIKLMNPQRSTVWY'
    records=[dict(sample_number=n,sequence=seq,sequence_sha256=sha(seq.encode())) for n in range(1,count+1)]
    rows=dict(design={'job_id':'design'},design_audit={'job_id':'audit'},
        validation={'validation_source':{'workflow_job_id':'workflow','node':'validation'}})
    fact=dict(source_jobs=dict(design={'job_id':'design'},design_audit={'job_id':'audit'}),records=[dict(r,
        passed=True,selected='af3',structure={'artifact_id':'structure-'+str(r['sample_number'])},
        engines={'af3':{'source':{'job_id':'prediction-'+str(r['sample_number'])}}}) for r in records])
    class RT:
        def result(self,jid):return {'generation':{'records':records}}
    monkeypatch.setattr(validation,'verified_fact',lambda *a:fact)
    monkeypatch.setattr(service,'source',lambda rt,row: {'job_id':row['job_id']} if row and row.get('job_id') else None)
    monkeypatch.setattr(service,'typed',lambda rt,rs,n: {'state':'available','artifact':rs[n]['job_id']} if n in rs else
        {'state':'not_provided','artifact':None,'reason_code':None})
    body=dict(protein_sequence='A'*20,user_sequence_id='test',host_species='pig',engineering_design=engineering.MODE,
        analysis={'developability':{'dimension_weights':None,'target_ph':None,'target_ph_range':[4,8],'timeout_seconds':60}})
    return RT(),body,rows,records,fact


@pytest.mark.parametrize('count',[24,48,64])
def test_all_candidates_get_own_validated_structure_and_native_n10(monkeypatch,count):
    rt,b,rows,records,fact=setup_candidate(monkeypatch,count)
    for n in range(1,count+1):
        s,reason=cd.request(rt,b,rows,f'c_s{n}_structure')
        assert reason is None and s['structure_artifact']==fact['records'][n-1]['structure']
        assert s['protein_sequence']==records[n-1]['sequence']!=b['protein_sequence']
        rows[f'c_s{n}_structure']={'job_id':'s-'+str(n)}
        d,reason=cd.request(rt,b,rows,f'c_s{n}_developability')
        assert reason is None and d['structure_input']['artifact']=='s-'+str(n)
    from t01_phase1_real.development.workflow.policy import order
    schedule=order(b)
    assert schedule.index('c_s64_developability')<schedule.index('stability')<schedule.index('variant_report')


@pytest.mark.parametrize('passed',[False,None])
def test_rejected_or_unknown_not_computed(monkeypatch,passed):
    rt,b,rows,_,f=setup_candidate(monkeypatch);f['records'][0]['passed']=passed
    assert cd.request(rt,b,rows,'c_s1_developability')[0] is None


def test_failed_prediction_uses_no_wt_structure(monkeypatch):
    rt,b,rows,_,f=setup_candidate(monkeypatch);f['records'][0]['selected']=None
    assert cd.request(rt,b,rows,'c_s1_structure')[1]=='N10_CANDIDATE_NO_STRUCTURE'
    assert cd.request(rt,b,rows,'c_s1_developability')[0]['structure_input']['state']=='not_provided'


@pytest.mark.parametrize('fault',['hash','round'])
def test_wrong_sequence_or_round_rejected(monkeypatch,fault):
    rt,b,rows,_,f=setup_candidate(monkeypatch)
    if fault=='hash':f['records'][0]['sequence_sha256']='different'
    else:f['source_jobs']['design']['job_id']='another-round'
    with pytest.raises(RuntimeFault):cd.request(rt,b,rows,'c_s1_developability')


def test_latest_retry_is_authoritative(monkeypatch):
    rt,b,rows,_,f=setup_candidate(monkeypatch)
    rows.update(retry1_design={'job_id':'new-design'},retry1_design_audit={'state':'succeeded','job_id':'new-audit'},
        retry1_validation={'validation_source':{'workflow_job_id':'workflow','node':'retry1_validation'}})
    f['source_jobs']=dict(design={'job_id':'new-design'},design_audit={'job_id':'new-audit'})
    assert cd.request(rt,b,rows,'c_s1_structure')[0] is not None


def test_full_inventory_recomputes_exact_candidate_ddg_without_n13_release():
    from t01_phase1_real.development.variant_report.selection import evaluate
    row,c,obs,files,audit=fixture();rows=[];observations=[]
    for n in range(1,25):
        r=copy.deepcopy(row);r.update(id='sample-'+str(n),sample_number=n,foldx={'ddg_foldx':float(n)},n13=None)
        rows.append(r);dev=copy.deepcopy(c);dev['developability']=summarize(dev)
        observations.append(dict(sample_number=n,sequence_sha256=r['sequence_sha256'],
            sources={'developability':{'job_id':'dev-'+str(n)}},results={'developability':dev}))
    files['input/candidate-developability.json']=encode({'records':observations})
    result=evaluate({},files,rows,audit)
    assert result['top20']==[] and len(result['inventory'])==24
    for n,item in enumerate(result['inventory'],1):
        assert item['developability']['stability_ddg']==float(n)
        assert item['developability']['weight_policy']=='S40_EQUAL_INITIAL_PENDING_BACKTEST'
        assert item['developability']['overall_score']==pytest.approx((1.6+1/(1+math.exp(n/2)))/3)
        assert item['recomputation_sources']['developability']['job_id']=='dev-'+str(n)
        assert 'N13_NOT_COMPUTED' in item['missing'] and not item['scientific_eligible']
    observations[3]['sequence_sha256']='wrong'
    files['input/candidate-developability.json']=encode({'records':observations})
    with pytest.raises(RuntimeFault):evaluate({},files,rows,audit)


@pytest.mark.parametrize('error,ok',[('TOOL_FAILED',True),('TIMEOUT',True),('HASH_MISMATCH',False),('FORBIDDEN',False)])
def test_candidate_failures_keep_integrity_boundary(error,ok):
    b={'engineering_design':engineering.MODE}
    assert service.recoverable_child_failure(b,'c_s24_developability',{'state':'failed','error_code':error}) is ok
    assert not service.recoverable_child_failure(b,'c_s24_developability',{'state':'cancelled','error_code':error})


@pytest.mark.parametrize('fault',[None,'configuration','structure','running','cancelled'])
def test_observations_recheck_source_request_and_process_stop(monkeypatch,fault):
    rt,b,rows,records,fact=setup_candidate(monkeypatch,1)
    rows['validation']['fact']=copy.deepcopy(fact)
    rows.update(c_s1_structure={'job_id':'structure'},c_s1_developability={'job_id':'dev','state':'succeeded'})
    sr=cd.request(rt,b,rows,'c_s1_structure')[0];dr=cd.request(rt,b,rows,'c_s1_developability')[0]
    child={'job_id':'dev','state':'succeeded','attempt_id':'attempt','run_id':'run'}
    if fault=='configuration':dr['target_ph']=6
    if fault=='structure':sr['structure_artifact']={'artifact_id':'wrong'}
    if fault=='cancelled':child['state']='cancelled'
    rt._request_bytes=lambda j:encode(dr if j['job_id']=='dev' else sr)
    rt._db=lambda:nullcontext(None)
    rt.execution=lambda jid:{'tree_stopped':fault!='running'}
    monkeypatch.setattr(service,'verified',lambda rt,b,n,jid,*a:child if jid=='dev' else {'job_id':jid})
    monkeypatch.setattr(cd,'verified_value',lambda *a:{'developability':summarize(components())})
    if fault:
        with pytest.raises(RuntimeFault):cd.observations(rt,b,rows,records,'run')
    else:
        result=cd.observations(rt,b,rows,records,'run')
        assert result[0]['sources']['developability']['job_id']=='dev'


@pytest.mark.parametrize('legacy',[False,True])
@pytest.mark.parametrize('fault',[None,'run','component','summary','native'])
def test_native_replay_preserves_archives_and_rejects_tampering(monkeypatch,legacy,fault):
    from t01_phase1_real.development.design_backend import source as registry
    from t01_phase1_real.development.developability import service as dev_service
    c=components();expected=dict(c,developability=summarize(c))
    value=dict(steps=c,developability=summarize(c,legacy_weights=legacy),raw_artifacts=[dict(path='input/structure',artifact={'artifact_id':'native'})])
    if fault=='component':value['steps']=dict(c,expressibility=dict(c['expressibility'],score=.9))
    if fault=='summary':value['developability']['overall_score']=.91
    original=copy.deepcopy(value)
    class RT:
        def _job(self,db,jid):return {'job_id':jid,'state':'succeeded','run_id':'wrong' if fault=='run' else 'run'}
        def artifact_bytes(self,*a):return b'wrong' if fault=='native' else b'native'
    monkeypatch.setattr(registry,'sources',lambda *a,**k:({'input/developability-request.json':encode({'dimension_weights':None})},{'developability':value},{}))
    monkeypatch.setattr(dev_service,'sources',lambda *a:({'input/structure':b'native'},None,{}))
    monkeypatch.setattr(dev_service,'evaluate',lambda *a:expected)
    if fault:
        with pytest.raises(RuntimeFault):cd.verified_value(RT(),None,{'job_id':'dev'},'AAA','run')
    else:assert cd.verified_value(RT(),None,{'job_id':'dev'},'AAA','run')['developability']['overall_score']==.8
    assert value==original


def test_n14_top40_consumes_all_current_n10_scores(monkeypatch):
    from t01_phase1_real.development.workflow import stability_pool as sp
    from t01_phase1_real.development.variant_report import source,compute as report_compute
    from test_n14_pool import inputs
    records,fact=inputs(48);fact.update(source_jobs={'design_audit':{'job_id':'audit'}},run_id='run')
    rows=dict(design_audit={'job_id':'audit'},structure={'state':'succeeded','job_id':'structure'},wt_draft={'state':'succeeded','job_id':'draft'},
        validation={'validation_source':{'workflow_job_id':'wf','node':'validation'}},c_s48_developability={'state':'succeeded'})
    class RT:
        def _db(self):return nullcontext(None)
        def result(self,jid):return {'analysis':{'quality':{'quality':{'confidence':'high'}}}} if jid=='structure' else {'draft':{'gate':{'basis':{'is_membrane':False}}}}
    monkeypatch.setattr(validation,'verified_fact',lambda *a:fact)
    monkeypatch.setattr(service,'source',lambda rt,r:{'job_id':r['job_id']} if r else None)
    monkeypatch.setattr(source,'sources',lambda *a:({},{},{}))
    monkeypatch.setattr(report_compute,'preselection_rows',lambda *a:records)
    observations=[dict(sample_number=n,sources={'developability':{'job_id':'dev'+str(n)}},
        results={'developability':{'developability':dict(overall_status='computed_unreviewed',overall_score=n/48,stability_ddg=None)}}) for n in range(1,49)]
    monkeypatch.setattr(cd,'observations',lambda *a:observations)
    pool,why=sp.pool(RT(),dict(protein_sequence='AAA',user_sequence_id='test'),rows)
    assert why is None and [r['sample_number'] for r in pool['selected']]==list(range(48,8,-1))
    assert len(pool['score_sources'])==48
    observations[4]['results']['developability']['developability']['overall_status']='incomplete_required_solubility'
    pool,why=sp.pool(RT(),dict(protein_sequence='AAA',user_sequence_id='test'),rows)
    assert why=='N14_TOP40_REQUIRES_COMPLETE_RELIABLE_FIVE_DIMENSION_SCORES' and not pool['selected']


@pytest.mark.parametrize('fault',[None,'foreign_run','wrong_sequence','different_configuration'])
def test_representative_reuse_requires_same_candidate_run_and_request(monkeypatch,fault):
    rt,b,rows,records,_=setup_candidate(monkeypatch,1)
    req=cd.request(rt,b,rows,'c_s1_developability')[0];actual=copy.deepcopy(req)
    if fault=='wrong_sequence':actual['protein_sequence']='A'*20
    if fault=='different_configuration':actual['target_ph']=6
    rows.update(preselection={'fact':{'selected':records}},rep1_developability={'job_id':'dev','state':'succeeded'})
    rt.get=lambda jid:dict(job_id=jid,tool_id='t01.real.developability',run_id='foreign' if fault=='foreign_run' else 'run',
        run_mode='g0_probe',usable_for_pipeline=False,artifacts=[])
    rt._request_bytes=lambda job:encode(actual)
    monkeypatch.setattr(service,'source',lambda *a:{'artifact':None})
    if fault in ('foreign_run','wrong_sequence'):
        with pytest.raises(RuntimeFault):cd.reuse(rt,b,rows,'c_s1_developability',req,'run')
    else:assert cd.reuse(rt,b,rows,'c_s1_developability',req,'run')==('dev' if fault is None else None)


def test_old_workflow_without_candidate_nodes_retains_legacy_report_sources():
    class RT:
        def _job(self,*a):return {'job_id':'parent'}
        def _request_bytes(self,*a):return encode({})
        def _execution(self,*a):return {'nodes':{'rep1_developability':{'job_id':'old'}}}
    assert cd.report_sources(RT(),None,{'n14_source':{'workflow_job_id':'parent'}},[]) is None


def test_report_discloses_s40_defaults_and_missing_dimensions():
    from t01_phase1_real.service_api.user_report import render
    c=components();c['solubility'].update(reliable=False,reason_code='MISSING')
    html=render({'variant_report':{'candidate_developability':{'records':[
        {'id':'candidate-1','developability':summarize(c),'missing':[]}]}}}).decode()
    assert '候选六维可开发性汇总' in html and '默认等权（待回测）' in html
    assert '溶解性' in html and '稳定性 ΔΔG' in html and '缺少可靠溶解性时不生成综合分' in html


def test_published_n10_envelope_replays_and_supplies_s40_components(tmp_path):
    from t01_phase1_real.development import Runtime
    from t01_phase1_real.development.variant_report.selection import evaluate
    from test_developability_development import request
    rt=Runtime(tmp_path/'n10');body=request();body.pop('dimension_weights')
    job=rt.submit_sequence(encode(body),'n10-default',policy.TOOL)
    assert rt.dispatch(job['job_id'])['state']=='succeeded'
    src=service.source(rt,{'job_id':job['job_id']});before=rt.result(job['job_id'])
    with rt._db() as db:value=cd.verified_value(rt,db,src,body['protein_sequence'],job['run_id'])
    assert rt.result(job['job_id'])==before
    row,_,obs,files,audit=fixture();obs['representatives'][0]['results']['developability']=value
    files['input/m1-observations.json']=encode(obs)
    derived=evaluate({},files,[row],audit)['inventory'][0]['developability']
    assert derived is not None and derived['dev_dims_available']>=1
    assert derived['overall_score'] is None and 'solubility' in derived['missing_dimensions']
    assert derived['weight_policy']=='S40_EQUAL_INITIAL_PENDING_BACKTEST'
