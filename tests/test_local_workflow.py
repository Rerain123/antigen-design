import copy
import io
import zipfile
import pytest
from t01_phase1_real.common import RuntimeFault,decode,encode,sha,TERMINAL
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import policy,service

def body():
    return dict(protein_sequence='ACDEFGHIKLMNPQRSTVWY',user_sequence_id='local-integration',
                host_species='Homo sapiens',expression_host=None,organism=None,structure=None,
                analysis={n:None for n in policy.OPTIONS},reuse_jobs={},timeout_seconds=300)


@pytest.mark.parametrize('tool,maximum',[('bepipred',1022),('topology',1023)])
def test_workflow_rejects_enabled_tool_length_before_creating_jobs(tmp_path,tool,maximum):
    rt=Runtime(tmp_path);b=body();b['protein_sequence']='A'*(maximum+1);b['analysis'][tool]={}
    with pytest.raises(RuntimeFault,match='support cap'):rt.submit_workflow(encode(b),'too-long')
    with rt._db() as db:assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==0
    b['analysis'][tool]=None
    assert policy.request(encode(b))['protein_sequence']==b['protein_sequence']

def run(rt,b=None,key='test'):
    j=rt.submit_workflow(encode(b or body()),key)
    for _ in range(50):
        j=rt.dispatch(j['job_id'])
        if j['state'] in TERMINAL:return j
    raise AssertionError('workflow did not finish')

def test_real_local_chain(tmp_path):
    rt=Runtime(tmp_path);j=run(rt)
    assert j['state']=='succeeded',rt.result(j['job_id'])
    data=rt.workflow(j['job_id']);nodes=data['nodes']
    assert nodes['glycosylation']['state']=='succeeded'
    assert nodes['local_delivery']['state']=='succeeded'
    assert nodes['structure']['reason_code']=='PREDICTION_SERVICE_NOT_DEPLOYED'
    assert nodes['netmhc']['reason_code']=='ALLELE_PANEL_NOT_PROVIDED'
    assert nodes['design']['reason_code']=='DESIGN_APPLICABILITY_INPUT_INSUFFICIENT'
    assert data['design_applicability_gate']['status']=='INPUT_INSUFFICIENT_OR_NOT_EVALUATED'
    assert data['scientific_release_gate']=='CLOSED'
    assert nodes['codon']['reason_code']=='EXPRESSION_HOST_NOT_PROVIDED'
    assert not data['usable_for_pipeline'] and data['md']=='EXCLUDED'
    ids=[r['job_id'] for r in nodes.values() if r.get('job_id')]
    assert len(ids)==len(set(ids))==5
    assert all(rt.get(i)['run_id']==j['run_id'] for i in ids)
    result=rt.result(j['job_id']);ref=next(r['artifact'] for r in result['raw_artifacts'] if r['path']=='output/package.zip')
    with zipfile.ZipFile(io.BytesIO(rt.artifact_bytes(j['job_id'],ref['artifact_id']))) as z:
        assert 'local-delivery.zip' in z.namelist()
        for row in decode(z.read('manifest.json'))['files']:
            assert sha(z.read(row['path']))==row['sha256']
    assert rt.submit_workflow(encode(body()),'test')['job_id']==j['job_id']
    assert rt.recover(j['job_id'])==j

def test_cancel_before_dispatch(tmp_path):
    rt=Runtime(tmp_path);j=rt.submit_workflow(encode(body()),'cancel')
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='c')))
    assert rt.dispatch(j['job_id'])['state']=='cancelled'
    assert not any(r.get('job_id') for r in rt.workflow(j['job_id'])['nodes'].values())

def test_missing_parameters_recorded_and_continue(tmp_path):
    rt=Runtime(tmp_path);b=body();b['analysis']['netmhc']={};b['analysis']['blast']={}
    j=run(rt,b);nodes=rt.workflow(j['job_id'])['nodes']
    assert nodes['netmhc']['state']=='blocked' and nodes['netmhc']['reason_code']=='INVALID_REQUEST'
    assert nodes['blast']['state']=='blocked'
    assert nodes['local_delivery']['state']=='succeeded'

def test_cancel_during_child_fences_remaining(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);j=rt.submit_workflow(encode(body()),'test');original=rt.dispatch
    def dispatch(jid):
        if rt.get(jid)['tool_id']=='t01.real.glycosylation':
            rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='cancel')))
        return original(jid)
    monkeypatch.setattr(rt,'dispatch',dispatch)
    end=rt.dispatch(j['job_id']);assert end['state']=='cancelled'
    data=rt.workflow(j['job_id']);assert data['nodes']['glycosylation']['state']=='cancelled'
    assert data['nodes']['wt_draft']['job_id'] is None
    assert not any(r['path']=='output/package.zip' for r in rt.result(j['job_id'])['raw_artifacts'])

def test_controller_resume_no_duplicate_children(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);j=rt.submit_workflow(encode(body()),'test');original=rt.dispatch;calls=[]
    def crash(jid):
        if rt.get(jid)['tool_id']=='t01.real.glycosylation' and not calls:
            calls.append(jid);raise KeyboardInterrupt()
        return original(jid)
    monkeypatch.setattr(rt,'dispatch',crash)
    with pytest.raises(KeyboardInterrupt):rt.dispatch(j['job_id'])
    child=rt.execution(j['job_id'])['nodes']['glycosylation']['job_id']
    monkeypatch.undo();end=Runtime(tmp_path).recover(j['job_id'])
    assert end['state']=='succeeded'
    assert rt.workflow(j['job_id'])['nodes']['glycosylation']['job_id']==child

def test_source_tamper_prevents_consumption(tmp_path):
    rt=Runtime(tmp_path);j=run(rt)
    child=rt.workflow(j['job_id'])['nodes']['glycosylation']['job_id']
    ref=rt.get(child)['artifacts'][0]
    with rt._db() as db:path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    (rt.root/path).write_bytes(b'changed')
    with pytest.raises(RuntimeFault):rt.workflow(j['job_id'])

def test_input_and_configuration_fences(tmp_path):
    rt=Runtime(tmp_path);b=body();j=rt.submit_workflow(encode(b),'test')
    changed=copy.deepcopy(b);changed['protein_sequence']='A'*20
    with pytest.raises(RuntimeFault):rt.submit_workflow(encode(changed),'test')
    rt.blast_database_root=tmp_path/'different'
    end=rt.dispatch(j['job_id']);assert end['state']=='failed' and end['error_code']=='PROFILE_NOT_APPROVED'

def test_deadline_does_not_reset_on_recover(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);b=body();b['timeout_seconds']=1
    original=service.current_identity
    def identity():
        import time
        time.sleep(1.1)
        return original()
    monkeypatch.setattr(service,'current_identity',identity)
    j=run(rt,b);assert j['state']=='timed_out'

def test_resume_completed_child_after_controller_crash(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);j=rt.submit_workflow(encode(body()),'test');original=rt.dispatch;completed=[]
    def crash(jid):
        result=original(jid)
        if rt.get(jid)['tool_id']=='t01.real.glycosylation' and not completed:
            completed.append(result);raise KeyboardInterrupt()
        return result
    monkeypatch.setattr(rt,'dispatch',crash)
    with pytest.raises(KeyboardInterrupt):rt.dispatch(j['job_id'])
    assert completed[0]['state']=='succeeded'
    monkeypatch.undo();assert rt.recover(j['job_id'])['state']=='succeeded'
    assert rt.get(completed[0]['job_id'])==completed[0]
    assert rt.workflow(j['job_id'])['nodes']['glycosylation']['job_id']==completed[0]['job_id']

def test_live_controller_fences_second_dispatcher(tmp_path,monkeypatch):
    import threading
    rt=Runtime(tmp_path);j=rt.submit_workflow(encode(body()),'test');original=service.request_for
    entered=threading.Event();release=threading.Event();errors=[]
    def pause(*args):
        if args[-1]=='glycosylation':
            entered.set();assert release.wait(20)
        return original(*args)
    monkeypatch.setattr(service,'request_for',pause)
    def schedule():
        try:rt.dispatch(j['job_id'])
        except BaseException as exc:errors.append(exc)
    thread=threading.Thread(target=schedule);thread.start()
    try:
        assert entered.wait(20)
        other=Runtime(tmp_path)
        assert other.dispatch(j['job_id'])['state']=='running'
        assert 'glycosylation' not in other.execution(j['job_id'])['nodes']
    finally:release.set();thread.join(30)
    assert not thread.is_alive() and not errors
    assert rt.get(j['job_id'])['state']=='succeeded'

def test_retry_is_new_attempt_and_gate_stays_closed(tmp_path):
    rt=Runtime(tmp_path);j=rt.submit_workflow(encode(body()),'test')
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='stop')))
    request=encode(dict(contract_version='0.1.0',operation='retry',job_id=j['job_id'],idempotency_key='retry'))
    retry=rt.control(request);assert retry['retry_of_job_id']==j['job_id'] and retry['job_id']!=j['job_id']
    assert rt.dispatch(retry['job_id'])['state']=='succeeded'
    assert rt.control(request)['job_id']==retry['job_id']
    assert rt.workflow(retry['job_id'])['nodes']['rescore']['reason_code']=='DESIGN_APPLICABILITY_INPUT_INSUFFICIENT'

@pytest.mark.parametrize('status,skip,reason',[
    ('INPUT_INSUFFICIENT_OR_NOT_EVALUATED',None,'DESIGN_APPLICABILITY_INPUT_INSUFFICIENT'),
    ('NOT_SUITABLE_FOR_DESIGN','membrane_expected_poor','R57_MEMBRANE_DESIGN_SKIPPED'),
    ('NOT_SUITABLE_FOR_DESIGN','skipped_low_confidence','R57_LOW_CONFIDENCE_DESIGN_SKIPPED'),
    ('SUITABLE_FOR_DESIGN',None,'SCIENTIFIC_CONSUMPTION_NOT_RELEASED')])
def test_design_route_separates_r57_business_gate_from_scientific_release(status,skip,reason):
    class GateRuntime:
        def result(self,jid):
            assert jid=='wt-job'
            return dict(draft=dict(gate=dict(status=status,design_skip_reason=skip)))
    rows=dict(wt_draft=dict(state='succeeded',job_id='wt-job'))
    assert service.design_route_reason(GateRuntime(),rows)==reason

def test_workflow_forwards_exact_r57_context_to_wt_draft():
    b=body();b['design_context']=dict(pathogen_type='virus_enveloped',
        membrane_design_confirm=True,low_conf_design_confirm=False)
    parsed=policy.request(encode(b));request,reason=service.request_for(None,parsed,{},'wt_draft')
    assert reason is None and request['design_context']==b['design_context']

def test_wrong_sequence_history_rejected(tmp_path):
    rt=Runtime(tmp_path);first=run(rt)
    history=rt.workflow(first['job_id'])['nodes']['variant_report']['job_id']
    b=body();b['protein_sequence']='A'*20;b['reuse_jobs']['variant_report']=history
    j=run(rt,b,key='other')
    assert j['state']=='failed' and j['error_code']=='OUTPUT_INVALID'
    assert rt.workflow(j['job_id'])['nodes']['local_delivery']['job_id'] is None

def test_cli_submit_query_node_and_export(tmp_path,capsys):
    from t01_phase1_real.development.cli import main
    request=tmp_path/'request.json';request.write_bytes(encode(body()));root=tmp_path/'runtime'
    prefix=['--root',str(root)]
    assert main(prefix+['workflow-submit','--input',str(request),'--key','cli','--run'])==0
    j=decode(capsys.readouterr().out.encode());assert j['state']=='succeeded'
    assert main(prefix+['workflow-get','--job-id',j['job_id'],'--node','glycosylation'])==0
    assert decode(capsys.readouterr().out.encode())['state']=='succeeded'
    target=tmp_path/'workflow.zip'
    assert main(prefix+['workflow-export','--job-id',j['job_id'],'--output',str(target)])==0
    capsys.readouterr();assert zipfile.is_zipfile(target)
    assert main(prefix+['workflow-export','--job-id',j['job_id'],'--output',str(target)])==21

def test_cancel_at_terminal_publication_cannot_export(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);original=rt._finish_development
    def finish(jid,ex,files,result):
        if rt.get(jid)['tool_id']==policy.TOOL:
            assert 'output/package.zip' in files
            rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=jid,idempotency_key='at-publication')))
        return original(jid,ex,files,result)
    monkeypatch.setattr(rt,'_finish_development',finish)
    j=run(rt);assert j['state']=='cancelled'
    assert rt.result(j['job_id'])['workflow'] is None
    assert not any(r['path']=='output/package.zip' for r in rt.result(j['job_id'])['raw_artifacts'])
