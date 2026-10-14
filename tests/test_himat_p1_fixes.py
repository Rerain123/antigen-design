"""P1 regressions, including the unchanged first HiMat run's native output."""
import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest
from t01_phase1_real.common import RuntimeFault, encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.blast.result import parse_hsps
from t01_phase1_real.development.workflow import service as workflow
from t01_phase1_real.service_api.app import Principal, ServiceError
from t01_phase1_real.service_api.himat import HiMatIntegration
from test_local_workflow import body, run
from test_m1_workflow import GateRuntime, ROWS, m1_body

EVIDENCE = Path(__file__).resolve().parents[1] / 'discovery/t01-phase1-real/m1-p4-20260922/himat-first-review-r01'


def test_original_233aa_blast_output_is_accepted_without_changing_thresholds():
    snapshot = json.loads((EVIDENCE / 'snapshot.json').read_bytes())
    record = next(r for r in snapshot['records'] if r['job']['tool_id'] == 't01.real.blast')
    with zipfile.ZipFile(EVIDENCE / 'native-evidence.zip') as archive:
        ref = next(r for r in record['job']['artifacts'] if r['sha256'] ==
                   '3953118b245c2fd7c78ba4944eaa4d94baf3ac6378a58ecce01a5cc95b702f1f')
        raw = archive.read('artifacts/' + ref['artifact_id'])
    assert hashlib.sha256(raw).hexdigest() == ref['sha256']
    hsps = parse_hsps(raw, record['request'])
    assert len(hsps) == 500
    assert all(h['passes_registered_thresholds'] for h in hsps)
    assert hsps[3]['native_query_coverage_percent'] == 99
    assert hsps[3]['query_coverage_percent'] == pytest.approx(232 * 100 / 233)
    changed = copy.deepcopy(record['request'])
    changed['thresholds']['query_coverage_percent_min'] = 99.8
    assert parse_hsps(raw, changed)[3]['passes_registered_thresholds'] is False


@pytest.mark.parametrize('length,covered,native', [(200,197,99),(200,198,99),(233,232,99),(233,233,100)])
def test_native_coverage_integer_boundary_and_false_full_coverage(length,covered,native):
    from t01_phase1_real.development.blast.policy import sequence_id
    seq = 'A' * length
    b = {'protein_sequence':seq,'thresholds':{'identity_percent_min':80,'query_coverage_percent_min':80}}
    fields = [sequence_id(seq),'target','100',str(covered),'0','0','1',str(covered),
              '1',str(covered),'1e-20','100',str(length),str(length),str(native),'A'*covered,'A'*covered,'test']
    assert parse_hsps(('\t'.join(fields)+'\n').encode(),b)
    fields[14] = str(100 if native == 99 else 99)
    with pytest.raises(RuntimeFault, match='integer formatting'):
        parse_hsps(('\t'.join(fields)+'\n').encode(),b)


@pytest.mark.parametrize('crash',[False,True])
def test_generic_child_failure_stops_and_survives_controller_resume(tmp_path,monkeypatch,crash):
    rt=Runtime(tmp_path);job=rt.submit_workflow(encode(body()),'failure');original=rt.dispatch
    def dispatch(jid):
        if rt.get(jid)['tool_id']=='t01.real.glycosylation':
            rt._development_fault='compute_failure'
            try:result=original(jid)
            finally:rt._development_fault=None
            if crash:raise KeyboardInterrupt()
            return result
        return original(jid)
    monkeypatch.setattr(rt,'dispatch',dispatch)
    if crash:
        with pytest.raises(KeyboardInterrupt):rt.dispatch(job['job_id'])
        monkeypatch.undo()
        final=rt.recover(job['job_id'])
    else:final=rt.dispatch(job['job_id'])
    assert final['state']=='failed'
    nodes=rt.workflow(job['job_id'])['nodes']
    assert nodes['epitope_map']['state']=='skipped'
    assert nodes['glycosylation']['state']=='failed'
    assert nodes['local_delivery']['job_id'] is None
    assert not any(r['path']=='output/package.zip' for r in rt.result(job['job_id'])['raw_artifacts'])


def test_missing_predictors_are_skipped_before_execution_and_n17_is_disclosed(tmp_path):
    rt=Runtime(tmp_path);final=run(rt)
    assert final['state']=='succeeded'
    nodes=rt.workflow(final['job_id'])['nodes']
    assert nodes['epitope_map']['job_id'] is None
    delivery=rt.result(nodes['local_delivery']['job_id'])
    ref=next(r['artifact'] for r in delivery['raw_artifacts'] if r['path']=='output/report.md')
    assert b'NO_NATIVE_SCAN_EXECUTED' in rt.artifact_bytes(nodes['local_delivery']['job_id'],ref['artifact_id'])


def test_original_card_exposes_failures_and_primary_markdown_includes_workflow():
    snapshot=json.loads((EVIDENCE/'snapshot.json').read_bytes())
    parent=next(r for r in snapshot['records'] if r['job']['tool_id']=='t01.real.local_workflow')
    raw=(EVIDENCE/'workflow.zip').read_bytes()
    status={'terminal':True,'state':'succeeded','error_code':None,'nodes':parent['execution']['nodes']}
    class ExistingReport:
        def status(self,*args):return status
        def report(self,*args):return {'content':raw,'filename':'workflow.zip','sha256':hashlib.sha256(raw).hexdigest(),
            'report_name':'20261011-073807-12345678'}
    adapter=HiMatIntegration(ExistingReport(),'https://example.invalid',b'k'*32)
    principal=Principal('himat-t01-test',frozenset({'query','download'}),'test')
    card=adapter.check(principal,parent['job']['job_id'])
    assert any('N01' in s and 'TOOL_FAILED' in s for s in card['data']['issues'])
    assert any('N03' in s and 'OUTPUT_INVALID' in s for s in card['data']['issues'])
    assert '2 项失败' in card['data']['summaryText']
    markdown=adapter.report_markdown(ExistingReport().report())
    assert b'TOOL_FAILED' in markdown and b'OUTPUT_INVALID' in markdown
    status.update(state='failed',error_code='TOOL_FAILED')
    failed=adapter.check(principal,parent['job']['job_id'])
    assert failed['data']['status']=='FAILED' and failed['data']['attachments']==[]
    assert any('N01' in s for s in failed['data']['issues'])



def test_sequence_only_himat_uses_backend_evidence_and_stable_new_identity():
    from t01_phase1_real.development.workflow import policy, engineering
    b=body();captured=[]
    class Submission:
        def submit(self,principal,value):
            captured.append(value)
            return {'job_id':'t01p1r-job-'+'a'*32,'state':'queued'}
    adapter=HiMatIntegration(Submission(),'https://example.invalid',b'k'*32)
    principal=Principal('himat-t01-test',frozenset({'submit'}),'test')
    response=adapter.submit_sequence(principal,b['protein_sequence'],b['host_species'])
    request=captured[-1]['request'];key=captured[-1]['idempotency_key']
    assert response['design_input_status']=='PENDING_BACKEND_EVIDENCE'
    assert request['engineering_design']==engineering.MODE
    assert 'm1_test' not in request and request['expression_host'] is None
    assert request['analysis']['domains']['organism_name'] is None
    assert request['analysis']['domains']['database_id']=='swissprot-2026_03-r01'
    accepted=policy.request(encode(request))
    assert policy.order(accepted).index('design_inputs')<policy.order(accepted).index('revision_design')
    assert 'revision_design' in policy.order(accepted)
    assert accepted['revision_config']['rule_version']=='expert-revision-20260929-v2'
    adapter.submit_sequence(principal,b['protein_sequence'],b['host_species'])
    assert captured[-1]['idempotency_key']==key
    old=json.dumps([b['protein_sequence'],b['host_species'],'first'],ensure_ascii=False,separators=(',',':')).encode()
    assert key!='himat-sequence-'+hashlib.sha256(old).hexdigest()[:48]
    accepted['m1_test']=m1_body()['m1_test']
    with pytest.raises(RuntimeFault):policy.request(encode(accepted))



@pytest.mark.parametrize('exported',[False,True])
def test_audited_inputs_control_design_without_user_masks(exported):
    from t01_phase1_real.development.workflow.engineering import MODE
    b=body();b['engineering_design']=MODE
    draft=dict(protein_sequence=b['protein_sequence'],**m1_body()['m1_test'])
    class Audited(GateRuntime):
        def _request_bytes(self,job):return encode(draft)
        def result(self,jid):
            if jid=='audit':return {'audit':{'n11_request_draft':draft if exported else None,
                                           'mask_conversion_error':{'reason':'Empty FIXED mask requires confirmation'}}}
            return super().result(jid)
    rt=Audited();rows=copy.deepcopy(ROWS)
    req,reason=workflow.request_for(rt,b,rows,'design_inputs')
    assert reason is None and req['user_regions']==[] and req['sample_numbers']==[]
    assert req['upstream']['n11'] is None and req['upstream']['esm_if1'] is None
    rows['design_inputs']={'state':'succeeded','job_id':'audit'}
    req,reason=workflow.request_for(rt,b,rows,'design')
    if exported:
        assert reason is None and req['constraints']==draft['constraints']
        rows['design']={'state':'succeeded','job_id':'design'}
        req,reason=workflow.request_for(rt,b,rows,'design_audit')
        assert reason is None and req['user_regions']==[]
    else:
        assert req is None and reason=='N11_MASK_EXPORT_BLOCKED'
        for name in ('wt_foldx','wt_thermompnn'):
            assert workflow.request_for(rt,b,rows,name)==(None,'N11_MASK_EXPORT_BLOCKED')
    assert 'm1_test' not in b


def test_backend_evidence_missing_inputs_produce_gap_delivery(tmp_path):
    from t01_phase1_real.development.workflow.engineering import MODE
    b=body();b['engineering_design']=MODE
    rt=Runtime(tmp_path);j=run(rt,b);snap=rt.workflow(j['job_id'])
    assert j['state']=='succeeded'
    assert snap['nodes']['design_inputs']['state']=='skipped'
    assert snap['nodes']['design']['reason_code']=='DESIGN_APPLICABILITY_INPUT_INSUFFICIENT'
    assert snap['nodes']['local_delivery']['state']=='succeeded'
    assert not snap['internal_test']['eligible_for_n11']
    child=snap['nodes']['glycosylation']['job_id']
    with pytest.raises(RuntimeFault,match='another run'):
        workflow.verified(rt,b,'glycosylation',child,'t01p1r-run-'+'f'*32)


@pytest.mark.parametrize('native_available',[False,True])
def test_scan_gap_uses_engine_receipts_not_assembly_invocation_count(native_available):
    from test_local_delivery_development import body as delivery_body
    from t01_phase1_real.development.local_delivery.compute import evaluate
    receipts={n:{'state':'missing'} for n in ('wt_draft','variant_report','wt_reference')}
    receipts['wt_reference']={'state':'available'};receipts['dna']=[]
    reference={'scan_invocations':0,'engines':{'foldx':{'state':'available' if native_available else 'missing'}}}
    result=evaluate(delivery_body(),{'input/source-receipts.json':encode(receipts),
        'input/wt_reference-result.json':encode({'reference':reference})})
    assert ({'source':'N17','code':'NO_NATIVE_SCAN_EXECUTED'} in result['missing_conditions']) is (not native_available)


def test_no_open_sites_records_zero_scans_and_missing_applicable_scan_is_rejected():
    from types import SimpleNamespace
    from t01_phase1_real.common import decode
    from t01_phase1_real.development.local_delivery.m1 import scan_facts
    constraints={'fixed_positions':[1],'restricted_positions':[{'position':2,'allowed_residues':'A'}],'open_positions':[]}
    requests={'audit':{'upstream':{'n11':{'job_id':'n11'}}},'n11':{'constraints':constraints}}
    rt=SimpleNamespace(_job=lambda db,jid:{'job_id':jid},_request_bytes=lambda job:encode(requests[job['job_id']]))
    files={'input/variant_report-request.json':encode({'upstream':{'design_audit':{'job_id':'audit'}}}),
           'input/wt_reference-request.json':encode({'upstream':{'foldx':None,'thermompnn':None}})}
    values={'variant_report':{'report':{'m1_test':{'records':[]}}},'wt_reference':{'reference':{'engines':{}}}}
    body={'upstream':{'variant_report':{'job_id':'final'}}}
    scan_facts(rt,None,body,files,values)
    facts=decode(files['input/m1-p3-scans.json'])
    assert facts['verified_scan_jobs']==0
    assert all(r['actual_calculation']=='NOT_EXECUTED' and r['source'] is None for r in facts['engines'].values())
    constraints['open_positions']=[3]
    with pytest.raises(RuntimeFault,match='both applicable'):
        scan_facts(rt,None,body,files,values)
