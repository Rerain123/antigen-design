"""Controller/transport regressions; synthetic fixtures do not claim scientific execution."""
import copy
import io
import zipfile
from datetime import datetime,timedelta,timezone
import pytest
from t01_phase1_real.common import RuntimeFault,encode,decode,sha,now
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import service,engineering,confirmation,policy
from t01_phase1_real.service_api.progress import project
from t01_phase1_real.service_api.himat import HiMatIntegration
from test_local_workflow import body
from test_proteinmpnn_development import request as mpnn_request


@pytest.fixture
def pending(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);b=body();b['engineering_design']=engineering.MODE
    job=rt.submit_workflow(encode(b),'pending');jid=job['job_id']
    draft=mpnn_request(b['protein_sequence']);draft['constraints']['fixed_positions']=[]
    draft['constraints']['open_positions'].append(1);draft['t4_empty_fixed_confirmation']=False
    audit={'audit':dict(confirmation_required=True,pending_n11_request_draft=draft,n11_request_draft=None)}
    aj=dict(job_id='audit',state='succeeded',error_code=None,run_id=job['run_id'],artifacts=[dict(role='result',sha256=sha(encode(audit)))])
    # Only scientific producers are replaced; durable Runtime and controller are real.
    original_result=rt.result
    monkeypatch.setattr(rt,'result',lambda id:audit if id=='audit' else original_result(id))
    monkeypatch.setattr(service,'verified',lambda r,b,n,id,*a,**k:aj if id=='audit' else r.get(id))
    with rt._tx() as db:
        old=rt._job(db,jid);j=copy.deepcopy(old);j.update(state='running',started_at=now())
        rt._store(db,j,old,'fixture')
        nodes={n:dict(node_id=policy.NODES[n],job_id=None,state='skipped') for n in policy.order(b)[:12]}
        nodes['design_inputs']=dict(state='succeeded',job_id='audit',node_id='N11')
        rt._execution_store(db,jid,dict(nodes=nodes,started_at=now(),phase='scheduling',dispatcher=None))
    confirmation.pause(rt,jid)
    return rt,jid,b,audit


@pytest.mark.parametrize('decision',[True,False])
def test_durable_confirmation_replay_decline_and_mask_binding(pending,decision):
    rt,jid,b,audit=pending;p=rt.execution(jid)['pending_confirmation']
    assert project(rt.execution(jid)['nodes'])['node_progress']['N11']['state']=='awaiting_confirmation'
    assert engineering.effective(rt,b,rt.execution(jid)['nodes'])[1]==confirmation.CODE
    confirmation.decide(rt,jid,p['confirmation_id'],decision,'owner')
    rows=rt.execution(jid)['nodes'];original=copy.deepcopy(rows)
    effective,reason=engineering.effective(rt,b,rows)
    if decision:
        assert reason is None and effective['m1_test']['t4_empty_fixed_confirmation'] is True
        assert not effective['m1_test']['constraints']['fixed_positions']
    else:assert reason=='T4_DESIGN_DECLINED' and rows['design']['state']=='skipped'
    confirmation.decide(rt,jid,p['confirmation_id'],decision,'owner')
    assert rt.execution(jid)['nodes']==original
    with pytest.raises(RuntimeFault,match='already recorded'):
        confirmation.decide(rt,jid,p['confirmation_id'],not decision,'owner')
    assert rt.get(jid)['run_id']==p['run_id']


@pytest.mark.parametrize('damage',['token','audit','cancel','type'])
def test_stale_tampered_cancelled_confirmation_rejected(pending,damage):
    rt,jid,b,audit=pending;p=rt.execution(jid)['pending_confirmation'];token=p['confirmation_id'];decision=True
    if damage=='token':token+='wrong'
    if damage=='audit':audit['audit']['pending_n11_request_draft']['seed']+=1
    if damage=='cancel':
        with rt._tx() as db:rt._stop(db,rt._job(db,jid),'cancel')
    if damage=='type':decision='true'
    with pytest.raises(RuntimeFault):confirmation.decide(rt,jid,token,decision,'owner')
    assert rt.execution(jid)['pending_confirmation']==p


def test_pending_restart_dispatch_does_not_start_design_and_wait_excluded_from_deadline(pending,monkeypatch):
    rt,jid,b,audit=pending
    with rt._tx() as db:
        ex=rt._execution(db,jid);earlier=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        ex['started_at']=earlier;ex['pending_confirmation']['requested_at']=earlier
        rt._execution_store(db,jid,ex)
    monkeypatch.setattr(rt,'dispatch',lambda id:pytest.fail('No child should start before confirmation'))
    assert service.dispatch(rt,jid)['state']=='running'
    assert confirmation.elapsed(rt.execution(jid))<2
    assert rt.execution(jid)['nodes']['design']['job_id'] is None


def test_confirmation_reaches_native_request_same_run_without_repeating_front_nodes(pending,monkeypatch):
    rt,jid,b,audit=pending;p=rt.execution(jid)['pending_confirmation']
    confirmation.decide(rt,jid,p['confirmation_id'],True,'owner')
    front=copy.deepcopy(rt.execution(jid)['nodes']['design_inputs'])
    monkeypatch.setattr(service,'m1_design_reason',lambda *a:None)
    monkeypatch.setattr(service,'source',lambda *a:dict(artifact=audit['audit']['pending_n11_request_draft']['structure_artifact']))
    monkeypatch.setattr(service,'m1_inputs',lambda *a:{'fixture':True})
    from t01_phase1_real.development.proteinmpnn import source as mpnn_source
    monkeypatch.setattr(mpnn_source,'sources',lambda *a,**k:None)
    calls=[]
    monkeypatch.setattr(rt,'dispatch',lambda id:calls.append(id) or rt.get(id))
    service.dispatch(rt,jid)
    row=rt.execution(jid)['nodes']['design'];child=rt.get(row['job_id'])
    assert child['run_id']==rt.get(jid)['run_id'] and len(calls)==1
    assert decode(rt._request_bytes(child))['t4_empty_fixed_confirmation'] is True
    assert rt.execution(jid)['nodes']['design_inputs']==front
    service.dispatch(rt,jid)
    assert rt.execution(jid)['nodes']['design']['job_id']==child['job_id']


def test_pre_authorized_policy_keeps_audit_bound_warning_without_pause(pending,monkeypatch):
    rt,jid,b,audit=pending
    b=dict(b,interaction_policy='PREAUTHORIZED_T4_CONTINUE_WITH_WARNING_V1')
    policy.request(encode(b))
    monkeypatch.setattr(rt,'_request_bytes',lambda job:encode(b))
    with rt._tx() as db:
        ex=rt._execution(db,jid);ex['pending_confirmation']=None;ex['nodes'].pop('design')
        rt._execution_store(db,jid,ex)
    confirmation.pause(rt,jid)
    ex=rt.execution(jid);consent=ex['nodes']['design']['confirmation']
    assert ex['pending_confirmation'] is None and ex['nodes']['design']['state']=='ready'
    assert consent['decision'] is True and consent['actor']=='configured:'+b['interaction_policy']
    assert consent['warning'] and consent['scientific_release'] is False
    assert consent['draft_sha256']==sha(encode(audit['audit']['pending_n11_request_draft']))
    assert engineering.effective(rt,b,ex['nodes'])[1] is None


def test_report_uses_workflow_execution_not_suitability():
    from t01_phase1_real.development.local_delivery import compute
    from test_local_delivery_development import body as delivery_body
    receipts={n:dict(state='missing') for n in ('wt_draft','variant_report','wt_reference')}
    receipts.update(wt_draft=dict(state='available'),dna=[])
    fact=dict(status='NOT_EXECUTED',reason_code='T4_DESIGN_DECLINED',detail=None)
    files={'input/source-receipts.json':encode(receipts),'input/wt_draft-result.json':encode(dict(draft=dict(gate=dict(status='SUITABLE_FOR_DESIGN')))),
        'input/workflow-design.json':encode(dict(design=fact))}
    d=compute.evaluate(delivery_body(),files);md=compute.readable(d).decode()
    assert d['outcome']=='DESIGN_NOT_EXECUTED'
    assert 'T4_DESIGN_DECLINED' in md and '候选设计未执行' in md
    nested=io.BytesIO()
    with zipfile.ZipFile(nested,'w') as z:z.writestr('report.md','结果：DESIGN_ELIGIBLE_RELEASE_CLOSED')
    outer=io.BytesIO()
    with zipfile.ZipFile(outer,'w') as z:
        z.writestr('local-delivery.zip',nested.getvalue())
        z.writestr('workflow.json',encode(dict(nodes=dict(design=dict(state='skipped',reason_code='N11_MASK_EXPORT_BLOCKED')))))
    md=HiMatIntegration.report_markdown({'content':outer.getvalue()}).decode()
    assert md.index('候选设计未执行')<md.index('DESIGN_ELIGIBLE_RELEASE_CLOSED')


@pytest.mark.parametrize('fixed',[False,True])
@pytest.mark.parametrize('precise_cif',[False,True])
def test_real_audit_mask_conversion_emits_pending_draft_only_when_needed(tmp_path,monkeypatch,fixed,precise_cif):
    from test_proteinmpnn_development import source,SEQUENCE
    from test_design_backend_development import request,receipts,scales,region
    from t01_phase1_real.development.design_backend import compute
    from t01_phase1_real.development.proteinmpnn import policy as native
    if precise_cif:
        from structure_integration_cases import geometry,cif
        atoms=geometry()
        for atom in atoms:atom['Cartn_x']=str(float(atom['Cartn_x'])+0.000423)
        structure,raw,facts=source(tmp_path,'normal-cif',data=cif(atoms))
    else:structure,raw,facts=source(tmp_path)
    b=request(SEQUENCE,t4_handshake=True)
    b['upstream']['structure']=dict(job_id='fixture',artifact=mpnn_request()['structure_artifact'])
    if fixed:b['user_regions']=[region(1,1,'FIXED')]
    values=dict(structure=structure)
    files={'input/source-receipts.json':encode(receipts(values)),'input/scales.json':encode(scales()),
        'input/structure-result.json':encode(structure),'input/structure-original.bin':raw,
        **{'input/'+n+'.json':encode(facts[n]) for n in ('preflight','raw_metadata','raw_addresses')}}
    monkeypatch.setattr(compute,'geometry',lambda *a:dict(status='unavailable',residues=None))
    a=compute.evaluate(b,files)
    assert a['mask_conversion_error'] is None
    if precise_cif:
        projection=a['mask_conversion']['native/conversion.json']['coordinate_projection']
        assert projection['max_absolute_delta_angstrom']==pytest.approx(.000423)
        assert projection['source_coordinates_preserved_in_original']
        legacy=compute.evaluate({k:v for k,v in b.items() if k!='t4_handshake'},files)
        assert legacy['n11_request_draft'] is None and legacy['mask_conversion_error']
    if fixed:
        assert a['n11_request_draft'] and not a.get('confirmation_required')
    else:
        assert a['confirmation_required'] and a['n11_request_draft'] is None
        draft=a['pending_n11_request_draft']
        with pytest.raises(RuntimeFault,match='T4'):native.request(encode(draft))
        native.request(encode(dict(draft,t4_empty_fixed_confirmation=True)))
        assert len(draft['constraints']['restricted_positions'])==len(SEQUENCE)


def test_service_confirmation_owner_and_mcp_contract(pending,tmp_path,monkeypatch):
    from t01_phase1_real.service_api.app import Service,ServiceConfig,Credentials,ServiceError
    from t01_phase1_real.service_api.transport import MCPApplication
    rt,jid,b,audit=pending;p=rt.execution(jid)['pending_confirmation']
    creds=Credentials.from_document({'credentials':[
        dict(token='h'*48,principal='himat-t01-test',scopes=['submit','query']),
        dict(token='b'*48,principal='other',scopes=['submit','query'])]})
    api=Service(ServiceConfig(tmp_path/'service'),creds)
    owner=creds.authenticate('Bearer '+'h'*48);other=creds.authenticate('Bearer '+'b'*48)
    api.store.register_submission(owner,'fixture','fingerprint',jid)
    monkeypatch.setattr(api,'runtime',lambda principal:rt)
    scheduled=[];monkeypatch.setattr(api,'schedule',lambda *a,**k:scheduled.append(a[1]))
    try:
        with pytest.raises(ServiceError):api.confirm_design(other,jid,p['confirmation_id'],True)
        app=MCPApplication(api,HiMatIntegration(api,'https://example.invalid',b'k'*32))
        args=dict(job_id=jid,confirmation_id=p['confirmation_id'],decision=True)
        _,response=app.dispatch(owner,dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name=app.HIMAT_CONFIRM_TOOL,arguments=args)))
        assert not response['result']['isError'] and scheduled==[jid]
        assert response['result']['structuredContent']['run_id']==p['run_id']
    finally:api.shutdown()
