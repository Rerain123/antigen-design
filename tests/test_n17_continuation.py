"""Controlled lifecycle/report failures; archived native records are never new scans."""
import copy
from types import SimpleNamespace
import pytest
from t01_phase1_real.common import REPO,RuntimeFault,encode,decode
from t01_phase1_real.development.workflow import service,engineering
from t01_phase1_real.development.local_delivery import n17,m1,compute
from t01_phase1_real.service_api.user_report import render


@pytest.mark.parametrize('name',['wt_foldx','wt_thermompnn'])
@pytest.mark.parametrize('code',['TOOL_FAILED','TIMEOUT','ASSET_MISSING'])
def test_scan_failure_route_is_only_operational_and_internal(name,code):
    request=dict(engineering_design=engineering.MODE)
    assert service.recoverable_child_failure(request,name,dict(state='timed_out' if code=='TIMEOUT' else 'failed',error_code=code))
    assert not service.recoverable_child_failure({},name,dict(state='failed',error_code=code))
    assert not service.recoverable_child_failure(request,name,dict(state='cancelled',error_code=code))
    for bad in ('HASH_MISMATCH','FORBIDDEN','PROFILE_NOT_APPROVED','OUTPUT_INVALID','CANCELLED'):
        assert not service.recoverable_child_failure(request,name,dict(state='failed',error_code=bad))


def context(monkeypatch,failed='foldx',state='failed',code='TOOL_FAILED'):
    root=REPO/'discovery/t01-phase1-real'
    records={}
    for folder in ('m1-p1-20260921/r01','m1-p2-20260921/r01','m1-p3-20260922/r01'):
        for path in (root/folder).glob('*.json'):
            r=decode(path.read_bytes())
            if isinstance(r,dict) and r.get('job') and r.get('request'):records[r['job']['job_id']]=r
    final=decode((root/'m1-p2-20260921/r01/final-report.json').read_bytes())
    ref=decode((root/'m1-p3-20260922/r01/wt-reference.json').read_bytes())
    request=decode((root/'m1-p1-20260921/r01/batch.json').read_bytes())['request']
    request['engineering_design']=engineering.MODE
    parent=dict(job_id='parent',run_id=final['job']['run_id'],state='running',stop_reason=None)
    rows={'wt_reference':dict(job_id=ref['job']['job_id'],state='succeeded')}
    for name in ('foldx','thermompnn'):
        src=ref['request']['upstream'][name];rows['wt_'+name]=dict(job_id=src['job_id'],state='succeeded')
    values=dict(variant_report=final['result'],wt_reference=ref['result'])
    files={'input/variant_report-request.json':encode(final['request']),
           'input/wt_reference-request.json':encode(ref['request'])}
    stopped={'value':True}
    rt=SimpleNamespace(get=lambda jid:records[jid]['job'],_job=lambda db,jid:records[jid]['job'],
        _request_bytes=lambda j:encode(records[j['job_id']]['request']),result=lambda jid:records[jid]['result'],
        execution=lambda jid:{'tree_stopped':stopped['value']})
    def verified(rt,b,name,jid,run,rows):
        j=rt.get(jid)
        if j['run_id']!=run:raise RuntimeFault('FORBIDDEN','different run')
        return j
    monkeypatch.setattr(service,'verified',verified)
    def expected(rt,b,rows,name):
        row=rows[name]
        if row['job_id'] is None:return None,'R39_MULTICHAIN_THERMOMPNN_SKIPPED'
        return copy.deepcopy(records[row['job_id']]['request']),None
    monkeypatch.setattr(service,'request_for',expected)
    if failed:
        row=rows['wt_'+failed];job=rt.get(row['job_id']);job.update(state=state,error_code=code)
        row['state']=state
        item=values['wt_reference']['reference']['engines'][failed]
        item.update(state='failed',records=[],effective_positions=[],coverage={'complete':False})
    delivery={'upstream':{'variant_report':{'job_id':final['job']['job_id']}}}
    return SimpleNamespace(rt=rt,parent=parent,request=request,rows=rows,files=files,values=values,
                           stopped=stopped,delivery=delivery,ref=ref)


@pytest.mark.parametrize('engine',['foldx','thermompnn'])
@pytest.mark.parametrize('state,code',[('failed','TOOL_FAILED'),('timed_out','TIMEOUT')])
def test_partial_scan_keeps_successful_engine_and_final_report(monkeypatch,engine,state,code):
    c=context(monkeypatch,engine,state,code)
    facts=n17.facts(c.rt,c.parent,c.request,c.rows,c.files,c.values)
    c.files['input/workflow-n17.json']=encode(facts)
    m1.scan_facts(c.rt,None,c.delivery,c.files,c.values)
    actual=decode(c.files['input/m1-p3-scans.json'])['engines']
    assert actual[engine]['actual_calculation']=='FAILED_OR_TIMED_OUT'
    assert actual[engine]['native_prediction_count'] is None and actual[engine]['displayed_positions']==[]
    other='thermompnn' if engine=='foldx' else 'foldx'
    assert actual[other]['displayed_positions']==[3] and actual[other]['displayed_prediction_count']==20
    from test_local_delivery_development import body
    receipts={n:{'state':'available' if n in c.values else 'missing'} for n in ('wt_draft','variant_report','wt_reference')}
    receipts['dna']=[];c.files['input/source-receipts.json']=encode(receipts)
    for name,value in c.values.items():c.files['input/'+name+'-result.json']=encode(value)
    data=compute.evaluate(body(),c.files)
    package=compute.package(body(),c.files,data)
    assert b'FAILED_OR_TIMED_OUT' in package['output/report.md'] and code.encode() in package['output/report.md']
    html=render(data).decode()
    assert ('超时' if state=='timed_out' else '失败') in html
    assert data['agent_c_payload'] is None and not data['automatic_handoff']
    assert not data['usable_for_pipeline'] and not data['variant_report']['ranked_candidates']


def test_multichain_skip_is_verified_not_fabricated_failure(monkeypatch):
    c=context(monkeypatch,None)
    c.rows['wt_thermompnn']=dict(job_id=None,state='skipped',reason_code='R39_MULTICHAIN_THERMOMPNN_SKIPPED')
    req=decode(c.files['input/wt_reference-request.json']);req['upstream']['thermompnn']=None
    c.files['input/wt_reference-request.json']=encode(req)
    item=c.values['wt_reference']['reference']['engines']['thermompnn'];item.update(state='missing',records=[],effective_positions=[])
    facts=n17.facts(c.rt,c.parent,c.request,c.rows,c.files,c.values)
    c.files['input/workflow-n17.json']=encode(facts)
    m1.scan_facts(c.rt,None,c.delivery,c.files,c.values)
    assert facts['engines']['thermompnn']['actual_calculation']=='NOT_EXECUTED'
    c.rows['wt_thermompnn']['reason_code']='INVENTED_REASON'
    with pytest.raises(RuntimeFault):n17.facts(c.rt,c.parent,c.request,c.rows,c.files,c.values)


def test_failed_scans_are_not_misreported_as_never_executed():
    from test_local_delivery_development import body
    receipts={n:{'state':'missing'} for n in ('wt_draft','variant_report','wt_reference')}
    receipts['wt_reference']={'state':'available'};receipts['dna']=[]
    files={'input/source-receipts.json':encode(receipts),'input/wt_reference-result.json':encode({
        'reference':{'engines':{n:{'state':'failed'} for n in ('foldx','thermompnn')}}})}
    data=compute.evaluate(body(),files)
    assert {'source':'N17','code':'NO_USABLE_NATIVE_SCAN_RESULT'} in data['missing_conditions']
    assert {'source':'N17','code':'NO_NATIVE_SCAN_EXECUTED'} not in data['missing_conditions']


@pytest.mark.parametrize('damage',['unconfirmed_stop','cross_run','foreign_source','cancel','integrity','scope','false_results'])
def test_partial_delivery_never_bypasses_identity_or_stop_guards(monkeypatch,damage):
    c=context(monkeypatch);job=c.rt.get(c.rows['wt_foldx']['job_id'])
    if damage=='unconfirmed_stop':c.stopped['value']=False
    elif damage=='cross_run':job['run_id']='foreign'
    elif damage=='foreign_source':
        req=decode(c.files['input/wt_reference-request.json']);req['upstream']['foldx']=None
        c.files['input/wt_reference-request.json']=encode(req)
    elif damage=='cancel':c.parent['stop_reason']='cancel'
    elif damage=='integrity':job['error_code']='HASH_MISMATCH'
    elif damage=='scope':c.rows['wt_foldx']['scan_scope']={'scope_sha256':'invalid'}
    else:c.values['wt_reference']['reference']['engines']['foldx']['records']=[{'unexpected':'prediction'}]
    with pytest.raises(RuntimeFault):n17.facts(c.rt,c.parent,c.request,c.rows,c.files,c.values)


@pytest.mark.parametrize('remaining,submitted,budget',[(120,True,60),(60,False,None),(20,False,None)])
def test_scan_budget_preserves_report_time(monkeypatch,remaining,submitted,budget):
    from contextlib import nullcontext
    from test_m1_service_p4 import RecordedInputs
    from t01_phase1_real.development.workflow import confirmation,m1 as route
    class Controller(RecordedInputs):
        def __init__(self):
            super().__init__();self.ex={'nodes':copy.deepcopy(self.rows)}
            self.ex['nodes']['wt_foldx']={'state':'ready'}
            self.parent=dict(job_id='parent',run_id='run',state='running',stop_reason=None,request_artifact={})
            self.body['engineering_design']=engineering.MODE
            self.options=self.body.pop('m1_test');self.body['reuse_jobs']={}
        def _tx(self):return nullcontext(None)
        def _job(self,*a):return self.parent
        def _execution(self,*a):return self.ex
        def _input(self,*a):return encode(self.body)
        def _request_bytes(self,j):return encode(self.jobs[j['job_id']]['request'])
        def _stage(self,db,run,raw,tool):self.staged=decode(raw);return {}
        def _admit(self,*a):pass
        def _new_job(self,*a):return {'job_id':'child'}
        def _execution_store(self,db,jid,ex):self.ex=ex
        def _store(self,*a):pass
    rt=Controller()
    monkeypatch.setattr(engineering,'effective',lambda rt,b,rows:(dict(b,m1_test=rt.options),None))
    req,_=route.request_for(rt,dict(rt.body,m1_test=rt.options),rt.rows,'wt_foldx')
    monkeypatch.setattr(confirmation,'elapsed',lambda ex:rt.body['timeout_seconds']-remaining)
    result=service._create_child(rt,'parent','wt_foldx',req)
    assert bool(result)==submitted
    if submitted:
        assert rt.staged['timeout_seconds']==budget
        prior=copy.deepcopy(rt.ex['nodes']['wt_foldx'])
        monkeypatch.setattr(confirmation,'elapsed',lambda ex:rt.body['timeout_seconds']-10)
        assert service._create_child(rt,'parent','wt_foldx',req)=='child'
        assert rt.ex['nodes']['wt_foldx']==prior
    else:
        assert rt.ex['nodes']['wt_foldx']['reason_code']=='N17_DOWNSTREAM_TIME_RESERVE'
        assert rt.parent['stop_reason'] is None
