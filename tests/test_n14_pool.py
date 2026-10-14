"""N14 complete-pool engineering tests. Synthetic values are never scientific evidence."""
import copy
from contextlib import nullcontext
import pytest
from t01_phase1_real.common import RuntimeFault,encode,sha
from t01_phase1_real.development.workflow import stability_pool as sp,m1,engineering


def inputs(count):
    records=[dict(id='sample-'+str(n),sample_number=n,sequence_sha256=sha(str(n).encode()),
        mutations=[dict(position=n,wt='A',mut='G')],permissions={'violations':[]}) for n in range(1,count+1)]
    validation=dict(records=[dict(sample_number=r['sample_number'],sequence_sha256=r['sequence_sha256'],passed=True) for r in records])
    return records,validation


@pytest.mark.parametrize('count',[1,24,40])
def test_every_validated_mutant_scored_without_developability_cap(count):
    records,validation=inputs(count);f=sp.choose(records,validation,{})
    assert len(f['selected'])==count and f['reason_code'] is None and not f['scientific_eligible']


@pytest.mark.parametrize('count',[41,48,64])
def test_large_pool_never_arbitrarily_truncated(count):
    records,validation=inputs(count);f=sp.choose(records,validation,{1:.9,2:.8,3:.7})
    assert f['selected']==[] and f['eligible_count']==count
    assert f['missing_five_dimension_scores']==list(range(4,count+1))
    assert f['reason_code']=='N14_TOP40_REQUIRES_COMPLETE_RELIABLE_FIVE_DIMENSION_SCORES'
    scores={n:n/count for n in range(1,count+1)};f=sp.choose(records,validation,scores)
    assert [r['sample_number'] for r in f['selected']]==list(range(count,count-40,-1))
    assert len(f['deferred'])==count-40


def test_top40_ties_keep_disclosed_source_order():
    records,validation=inputs(48);f=sp.choose(records,validation,{n:.5 for n in range(1,49)})
    assert [r['sample_number'] for r in f['selected']]==list(range(1,41))
    assert f['tie_policy']=='STABLE_ORIGINAL_N11_ORDER_FIRST_VERSION'


@pytest.mark.parametrize('score',[float('nan'),float('inf'),-1,1.1,True])
def test_invalid_ranking_input_rejected(score):
    records,validation=inputs(41);scores={n:.5 for n in range(1,42)};scores[4]=score
    with pytest.raises(RuntimeFault):sp.choose(records,validation,scores)


def test_failure_unknown_permissions_and_wt_are_not_scored():
    records,validation=inputs(5)
    validation['records'][0]['passed']=False;validation['records'][1]['passed']=None
    records[2]['permissions']['violations']=['fixed'];records[3]['mutations']=[]
    f=sp.choose(records,validation,{})
    assert [r['sample_number'] for r in f['selected']]==[5] and len(f['excluded'])==4
    records.pop();validation['records'].pop()
    assert sp.choose(records,validation,{})['reason_code']=='NO_VALIDATED_MUTANT_FOR_N14'


@pytest.mark.parametrize('change',['hash','duplicate','missing'])
def test_mismatched_inventory_rejected(change):
    records,validation=inputs(24)
    if change=='hash':validation['records'][3]['sequence_sha256']='changed'
    elif change=='duplicate':records.append(records[0])
    else:validation['records'].pop()
    with pytest.raises(RuntimeFault):sp.choose(records,validation,{})


def test_request_and_report_bind_all24_independently_of_three_n13_representatives(monkeypatch):
    from test_m1_service_p4 import RecordedInputs
    from t01_phase1_real.development.foldx import policy
    rt=RecordedInputs();b=dict(rt.body,engineering_design=engineering.MODE)
    records,validation=inputs(24)
    # Actual input has protected positions 1/2/76; synthetic mutations stay in open positions.
    for n,r in enumerate(records,3):r['mutations']=[dict(position=n,wt=b['protein_sequence'][n-1],mut='G' if b['protein_sequence'][n-1]!='G' else 'A')]
    f=sp.choose(records,validation,{});f['pool_sha256']=sha(encode(f))
    monkeypatch.setattr(sp,'pool',lambda *args:(f,None))
    req,reason=m1.request_for(rt,b,rt.rows,'stability')
    assert reason is None and len(req['variants'])==24 and policy.request(encode(req))==req
    assert req['fixed_positions']==b['m1_test']['constraints']['fixed_positions']
    assert req['structure_artifact']['job_id']==rt.rows['structure']['job_id']
    report,reason=m1.request_for(rt,b,rt.rows,'variant_report')
    assert len(report['foldx_bindings'])==24 and len(report['m1_test']['representatives'])<=3


@pytest.mark.parametrize('membrane,quality,expected',[(False,'high',None),(True,'high','N14_MEMBRANE_WT_SKIPPED'),
    (None,'high','N14_MEMBRANE_STATUS_UNAVAILABLE'),(False,'low','N14_LOW_CONFIDENCE_WT_SKIPPED')])
def test_pool_checks_real_nested_gate_and_hash(monkeypatch,membrane,quality,expected):
    from t01_phase1_real.development.workflow import validation,service
    from t01_phase1_real.development.variant_report import source,compute
    records,fact=inputs(24);fact.update(source_jobs={'design_audit':{'job_id':'audit'}},run_id='run')
    class RT:
        def _db(self):return nullcontext(None)
        def result(self,jid):return {'analysis':{'quality':{'quality':{'confidence':quality}}}} if jid=='structure' else {'draft':{'gate':{'basis':{'is_membrane':membrane}}}}
    monkeypatch.setattr(validation,'verified_fact',lambda *a:fact)
    monkeypatch.setattr(service,'source',lambda rt,row:{'job_id':row['job_id']} if row else None)
    monkeypatch.setattr(source,'sources',lambda *a:({}, {}, {}))
    monkeypatch.setattr(compute,'preselection_rows',lambda *a:records)
    rows={n:dict(state='succeeded',job_id=n) for n in ['structure','wt_draft']}
    rows.update(design_audit={'job_id':'audit'},validation={'validation_source':{'workflow_job_id':'workflow','node':'validation'}})
    result,reason=sp.pool(RT(),dict(protein_sequence='A'*24,user_sequence_id='test'),rows)
    assert reason==expected and len(result['selected'])==24
    assert result['pool_sha256']==sha(encode({k:v for k,v in result.items() if k!='pool_sha256'}))


def test_html_discloses_blocked_large_pool():
    from t01_phase1_real.service_api.user_report import render
    records,validation=inputs(48);f=sp.choose(records,validation,{})
    html=render({'variant_report':{'n14_execution':dict(pool=f,state='skipped',reason_code=f['reason_code'],coverage={'requested':0,'returned':0})}}).decode()
    assert '未任意截取' in html and '5' in html


@pytest.mark.parametrize('change',[None,'omitted_binding','wrong_wt','wrong_fixed','wrong_pool','foreign_child','wrong_round','foreign_sequence','cancelled_parent','cancelled_child','integrity_failure','still_running'])
def test_report_requires_exact_workflow_pool_and_all_bindings(monkeypatch,change):
    from t01_phase1_real.development.workflow import service,design_rounds
    records,validation=inputs(24);fact=sp.choose(records,validation,{})
    fact.update(structure={'artifact':{'id':'wt'}},pool_sha256='pool-hash')
    parent=dict(job_id='parent',tool_id='t01.real.local_workflow',run_id='run',state='running')
    child=dict(job_id='foldx',state='succeeded')
    b=dict(protein_sequence='A'*24,engineering_design=engineering.MODE)
    req=dict(mode='buildmodel',structure_artifact={'id':'wt'},fixed_positions=[1],
        variants=[dict(variant_id=r['id'],mutations=r['mutations']) for r in records],
        scope_source={'source_id':'N14 complete pool sha256=pool-hash'})
    rows=dict(design={'job_id':'design'},design_audit={'job_id':'audit'},stability=dict(job_id='foldx',state='succeeded'))
    report=dict(protein_sequence=b['protein_sequence'],n14_source={'workflow_job_id':'parent'},
        upstream=dict(design_audit={'job_id':'audit'},foldx={'job_id':'foldx'}),
        foldx_bindings=[dict(sample_number=r['sample_number'],variant_id=r['id']) for r in records])
    class RT:
        def _job(self,db,jid):return parent if jid=='parent' else {'job_id':jid}
        def _request_bytes(self,job):return encode(b if job['job_id']=='parent' else req if job['job_id']=='foldx' else {'constraints':{'fixed_positions':[1]}})
        def _execution(self,*a):return {'nodes':rows}
        def execution(self,*a):return {'tree_stopped':False}
    monkeypatch.setattr(sp,'pool',lambda *a:(fact,None))
    monkeypatch.setattr(service,'verified',lambda *a:child)
    monkeypatch.setattr(service,'source',lambda rt,row:{'job_id':row['job_id']} if row else None)
    monkeypatch.setattr(design_rounds,'active',lambda r:r)
    if change=='omitted_binding':report['foldx_bindings'].pop()
    elif change=='wrong_wt':req['structure_artifact']={'id':'other'}
    elif change=='wrong_fixed':req['fixed_positions']=[]
    elif change=='wrong_pool':req['variants'].pop()
    elif change=='foreign_child':report['upstream']['foldx']={'job_id':'other'}
    elif change=='wrong_round':report['upstream']['design_audit']={'job_id':'other'}
    elif change=='foreign_sequence':report['protein_sequence']='G'*24
    elif change=='cancelled_parent':parent['stop_reason']='cancel'
    elif change=='cancelled_child':child['state']='cancelled'
    elif change=='integrity_failure':child.update(state='failed',error_code='OUTPUT_INVALID')
    elif change=='still_running':child['attempt_id']='attempt'
    if change:
        with pytest.raises(RuntimeFault):sp.verify_report(RT(),None,report)
    else:assert sp.verify_report(RT(),None,report)['state']=='succeeded'
