"""Bounded full-pool transport and immutable continuation; no model execution."""
import copy
import pytest
from t01_phase1_real.common import encode,decode,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.foldx import policy as foldx
from t01_phase1_real.development.workflow import continuation,service,policy,validation
from test_foldx_development import scan_body


def full_request(count=40,length=1000):
    body=scan_body()
    body.update(protein_sequence='A'*length,fixed_positions=[],scan_positions=[],mode='buildmodel',
        variants=[dict(variant_id=str(i)+'x'*250,mutations=[dict(position=p,wt='A',mut='G')
            for p in range(1,length+1)]) for i in range(count)])
    return body


def test_full_pool_roundtrip_and_hash_run_guards(tmp_path):
    rt=Runtime(tmp_path)
    from test_workflow_performance import running
    parent=running(rt);raw=encode(full_request())
    assert 65536<len(raw)<4*1024**2
    ref=rt.stage_request(parent['run_id'],raw,foldx.TOOL)
    with rt._db() as db:
        assert rt._input(db,ref,parent['run_id'])==raw
        with pytest.raises(RuntimeFault):rt._input(db,dict(ref,sha256='0'*64),parent['run_id'])
        other=rt.submit_workflow(encode(__import__('test_local_workflow').body()),'other-run')
        with pytest.raises(RuntimeFault):rt._input(db,ref,other['run_id'])
        row=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
    (rt.root/row['relative_path']).write_bytes(raw[:-1]+b' ')
    with pytest.raises(RuntimeFault):rt._request_bytes(dict(request_artifact=ref,run_id=parent['run_id']))


def test_capacity_is_not_a_global_unbounded_exception(tmp_path):
    rt=Runtime(tmp_path)
    from test_workflow_performance import running
    parent=running(rt)
    for raw,tool in ((b' '* (4*1024**2+1),foldx.TOOL),(encode(full_request()),'t01.real.ingest_structure'),
                     (encode(dict(full_request(),unknown='x')),foldx.TOOL)):
        with pytest.raises(RuntimeFault):rt.stage_request(parent['run_id'],raw,tool)


def checkpoint(monkeypatch):
    from types import SimpleNamespace
    body=dict(protein_sequence='A',configuration={},engineering_design='BACKEND_EVIDENCE_V1')
    fact={'records':[1]};context=dict(workflow_job_id='original',node='validation')
    selected=dict(validation_source=context,selected=[],records_sha256='hash')
    rows=dict(design=dict(job_id='design-child',state='succeeded'),
        validation=dict(state='succeeded',origin='INTERNAL_FACT',fact=fact,
            validation_source=dict(workflow_job_id='source',node='validation')),
        preselection=dict(state='succeeded',origin='INTERNAL_FACT',fact=selected),
        c_s1_structure=dict(job_id='structure-child',state='succeeded'),
        c_s1_developability=dict(job_id='n10-child',state='succeeded'),
        stability=dict(state='blocked',job_id=None,reason_code='INVALID_REQUEST',detail='Request exceeds tool capacity'))
    job=dict(job_id='source',run_id='run',tool_id=policy.TOOL,state='failed',error_code='OUTPUT_INVALID')
    ex=dict(nodes=rows,tree_stopped=True,fatal_error='OUTPUT_INVALID',continuation={'source_job_id':'original'})
    jobs={'source':job,'original':dict(run_id='run')}
    jobs.update({r['job_id']:dict(job_id=r['job_id'],run_id='run',state='succeeded',attempt_id='attempt')
        for r in rows.values() if r.get('job_id')})
    def execution(jid):
        if jid=='source':return ex
        if jid=='original':return dict(nodes={'preselection':{'fact':selected}})
        return dict(tree_stopped=True)
    rt=SimpleNamespace(get=lambda jid:jobs[jid],execution=execution,_request_bytes=lambda j:encode(body),
        _request_limit=Runtime._request_limit,result=lambda jid:{'generation':{'records':[{'sample_number':1,'sequence':'A'}]}})
    monkeypatch.setattr(policy,'request',decode)
    monkeypatch.setattr(policy,'order',lambda b:tuple(rows)+('variant_report',))
    monkeypatch.setattr(service,'configuration',lambda rt:{})
    monkeypatch.setattr(continuation.engineering,'enabled',lambda b:True)
    monkeypatch.setattr(validation,'verified_fact',lambda *a:fact)
    from t01_phase1_real.development.workflow import m1,candidate_developability as cd
    monkeypatch.setattr(m1,'preselection',lambda rt,b,r:dict(selected,validation_source=r['validation']['validation_source']))
    monkeypatch.setattr(service,'verified',lambda rt,b,n,jid,*a:jobs[jid])
    checked=[]
    monkeypatch.setattr(cd,'observations',lambda *a:checked.append(a))
    monkeypatch.setattr(service,'request_for',lambda *a:(full_request(24,214),None))
    return rt,job,ex,checked


def test_n14_reuses_all_n10_and_repairs_only_provenance_in_new_copy(monkeypatch):
    rt,job,ex,checked=checkpoint(monkeypatch);old=copy.deepcopy(ex)
    _,_,_,rows=continuation.prepare_stability(rt,'source')
    assert ex==old and 'stability' not in rows
    assert rows['c_s1_developability']['job_id']=='n10-child' and checked
    assert rows['preselection']['fact']['validation_source']==rows['validation']['validation_source']
    assert rows['preselection']['fact']['selected']==old['nodes']['preselection']['fact']['selected']


@pytest.mark.parametrize('fault',['live','pending','native_started','downstream_started','partial','different_selection','wrong_ancestor'])
def test_n14_rejects_unsafe_or_different_checkpoint(monkeypatch,fault):
    rt,job,ex,_=checkpoint(monkeypatch)
    if fault=='live':job['state']='running'
    elif fault=='pending':ex['pending_confirmation']={'required':True}
    elif fault=='native_started':ex['nodes']['stability']['job_id']='foldx'
    elif fault=='downstream_started':ex['nodes']['variant_report']={'job_id':'report'}
    elif fault=='partial':ex['nodes']['c_s1_developability']['state']='running'
    elif fault=='wrong_ancestor':ex['continuation']['source_job_id']='elsewhere'
    else:
        from t01_phase1_real.development.workflow import m1
        monkeypatch.setattr(m1,'preselection',lambda *a:{'selected':[99]})
    with pytest.raises(RuntimeFault):continuation.prepare_stability(rt,'source')


def test_new_continuation_preserves_producer_context_and_prior_job(tmp_path,monkeypatch):
    from test_workflow_performance import running
    rt=Runtime(tmp_path);source=running(rt)
    source=service.finish(rt,source['job_id'],error='OUTPUT_INVALID')
    old=rt.execution(source['job_id']);body=policy.request(rt._request_bytes(source))
    context=dict(workflow_job_id=source['job_id'],node='validation')
    rows={'validation':dict(state='succeeded',validation_source=context),
          'preselection':dict(fact={'validation_source':context}),
          'c_s1_developability':dict(job_id='n10',state='succeeded')}
    monkeypatch.setattr(continuation,'prepare_stability',lambda *a:(source,body,old,rows))
    new=continuation.restart_candidate_analysis(rt,source['job_id'],'n14-retry')
    fresh=rt.execution(new['job_id'])
    assert new['run_id']==source['run_id'] and rt.execution(source['job_id'])==old
    assert fresh['nodes']['validation']['validation_source']==fresh['nodes']['preselection']['fact']['validation_source']==context
    assert fresh['continuation']['boundary']=='stability' and fresh['continuation']['reused_children']=={'c_s1_developability':'n10'}
    assert continuation.restart_candidate_analysis(rt,source['job_id'],'n14-retry')==new


def test_capacity_failure_stops_before_report_with_original_error(tmp_path,monkeypatch):
    from test_workflow_performance import running
    rt=Runtime(tmp_path);parent=running(rt)
    monkeypatch.setattr(policy,'order',lambda b:('stability','variant_report'))
    monkeypatch.setattr(service,'request_for',lambda *a:({'request':'fixture'},None))
    def fail(*args):raise RuntimeFault('INVALID_REQUEST','Request exceeds tool capacity')
    monkeypatch.setattr(service,'_create_child',fail)
    result=service.dispatch(rt,parent['job_id'])
    assert result['state']=='failed' and result['error_code']=='INVALID_REQUEST'
    ex=rt.execution(parent['job_id'])
    assert ex['fatal_detail']=='Request exceeds tool capacity' and 'variant_report' not in ex['nodes']
