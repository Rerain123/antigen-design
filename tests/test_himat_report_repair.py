"""Actual ordinary HiMat results and version-independent, bound export checks."""
import copy
import gzip
import io
import json
import zipfile
from pathlib import Path

import pytest

from t01_phase1_real.common import RuntimeFault, encode, sha
from t01_phase1_real.service_api.native_results import collect, mhc_summary
from t01_phase1_real.service_api.user_report import from_workflow_package, render
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.app import Credentials, Principal

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'reports/himat-report-audit-20261008'


@pytest.fixture(scope='module')
def actual():
    v = json.loads(gzip.decompress((EVIDENCE/'backend-evidence.json.gz').read_bytes()))
    package = (EVIDENCE/'original-workflow-package.zip').read_bytes()
    assert sha(package) == v['package_sha256']
    workflow = json.loads(zipfile.ZipFile(io.BytesIO(package)).read('workflow.json'))
    nodes = copy.deepcopy(workflow['nodes'])
    for name, row in nodes.items():
        row['reason_code'] = row.get('reason_code') or row.get('error_code')
        if row.get('job_id'):
            value = v['results'][row['job_id']]
            row.update(result=value, tool_id=value['tool_id'])
            if 'channels' in value:
                batches = [v['results'][b['artifact']['job_id']] for b in value.get('batch_sources', [])]
                row['mhc_summary'] = mhc_summary(value, batches)
    snapshot = dict(nodes=nodes, job_id=v['parent']['job_id'], run_id=v['parent']['run_id'],
        workflow_package_sha256=sha(package), mhc_batches=[{}]*4, revision_config=None)
    return package, snapshot, workflow


def test_actual_ordinary_report_exposes_existing_values_and_zero_candidate_cause(actual):
    raw, snapshot, _ = actual
    before = sha(encode(snapshot))
    html = from_workflow_package(raw, native_results=snapshot).decode()
    for expected in ('118636', '>776<', '>1861<', '27.896500', '10.673466', '-0.574900',
                     'PROPKA 原始 pH 能量曲线', '1.072734', '1.083347',
                     '位点（1-based）：143', '成熟链', '固定约束来源',
                     '原生候选生成器未调用'):
        assert expected in html
    assert 'S27_VALIDATED_FUNCTIONAL' not in html and 't01p1r-job-' not in html
    assert '16 个 MHC 批次' not in html and '正式生成 0 条记录' not in html
    assert '<strong>0</strong><span>生成候选</span>' in html
    assert '未接通' not in html  # This run has actual WT A3D/PROPKA results.
    assert '尚无经过验证' in html and '10月9日专家已明确' in html and '不追改历史结果' in html
    assert len(html.encode()) < 4*1024**2 and sha(encode(snapshot)) == before


def test_common_details_do_not_replace_legacy_candidate_records():
    data = dict(variant_report=dict(records=[dict(id='existing-candidate',mutations=[])]))
    snapshot = dict(nodes={},job_id='j',run_id='r',workflow_package_sha256='a'*64)
    html = render(data, native_results=snapshot).decode()
    assert 'existing-candidate' in html and '<strong>1</strong><span>候选记录</span>' in html


def bound_runtime():
    original = encode(dict(protein_sequence='ACD'))
    request = encode(dict(protein_sequence='ACD', example='test-only'))
    result = encode(dict(binding=dict(job_id='child',run_id='run',input_sha256=sha(request))))
    ref = dict(job_id='child',run_id='run',artifact_id='result',role='result',size_bytes=len(result),sha256=sha(result))
    parent = dict(job_id='parent',run_id='run',tool_id='t01.real.local_workflow',state='succeeded')
    child = dict(job_id='child',run_id='run',tool_id='t01.real.domains',state='succeeded',artifacts=[ref])
    workflow = dict(parent_at_assembly=parent,sequence_sha256=sha(b'ACD'),expert_revision=None,
                    nodes=dict(domains=dict(node_id='N09',**child)))
    package = io.BytesIO()
    with zipfile.ZipFile(package,'w') as z:z.writestr('workflow.json',encode(workflow))
    class ReadsOnly:
        jobs = {'parent':parent,'child':child}
        def get(self,jid):return self.jobs[jid]
        def _request_bytes(self,job):return original if job['job_id']=='parent' else request
        def artifact_bytes(self,jid,aid):
            assert (jid,aid)==('child','result')
            return result
    report = dict(job_id='parent',content=package.getvalue(),sha256=sha(package.getvalue()))
    return ReadsOnly(), report


def test_collector_exports_non_v2_with_manifest_hashes_and_no_mutations():
    rt, report = bound_runtime()
    before = copy.deepcopy(rt.jobs)
    snapshot, archive = collect(rt,'parent',report,include_raw=True)
    assert snapshot['revision_config'] is None and snapshot['new_model_calls']==0
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        manifest=json.loads(z.read('manifest.json'))
        for row in manifest['files']:
            raw=z.read(row['path'])
            assert len(raw)==row['size_bytes'] and sha(raw)==row['sha256']
        assert z.read('original-workflow-package.zip')==report['content']
    assert rt.jobs==before


def raw_runtime():
    rt, report = bound_runtime()
    payloads = {'first': b'A' * 8192, 'second': b'BC' * 4096}
    refs = [dict(job_id='child', run_id='run', artifact_id=k, role='native',
                 size_bytes=len(raw), sha256=sha(raw)) for k, raw in payloads.items()]
    result = encode(dict(binding=dict(job_id='child', run_id='run',
                        input_sha256=sha(rt._request_bytes(rt.jobs['child']))),
                         raw_artifacts=[dict(path=r['artifact_id']+'.txt', artifact=r) for r in refs]))
    result_ref = dict(job_id='child', run_id='run', artifact_id='result', role='result',
                      size_bytes=len(result), sha256=sha(result))
    rt.jobs['child']['artifacts'] = [result_ref] + refs
    with zipfile.ZipFile(io.BytesIO(report['content'])) as z:
        workflow = json.loads(z.read('workflow.json'))
    workflow['nodes']['domains']['artifacts'] = rt.jobs['child']['artifacts']
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.writestr('workflow.json', encode(workflow))
    report.update(content=out.getvalue(), sha256=sha(out.getvalue()))
    payloads['result'] = result
    rt.artifact_bytes = lambda jid, aid: payloads[aid]
    return rt, report, payloads


def test_native_members_are_compressed_before_the_next_raw_file_is_read(monkeypatch):
    rt, report, payloads = raw_runtime()
    events = []
    write = zipfile.ZipFile.writestr
    def observed_write(self, info, raw, *args, **kwargs):
        events.append(('write', info.filename))
        return write(self, info, raw, *args, **kwargs)
    def observed_read(jid, aid):
        events.append(('read', aid))
        return payloads[aid]
    monkeypatch.setattr(zipfile.ZipFile, 'writestr', observed_write)
    rt.artifact_bytes = observed_read
    first = collect(rt, 'parent', report, include_raw=True)[1]
    assert events.index(('write', 'tools/domains/first.txt')) < events.index(('read', 'second'))
    assert first == collect(rt, 'parent', report, include_raw=True)[1]
    with zipfile.ZipFile(io.BytesIO(first)) as z:
        manifest = json.loads(z.read('manifest.json'))
        for item in manifest['files']:
            assert sha(z.read(item['path'])) == item['sha256']
        assert z.read('tools/domains/first.txt') == payloads['first']


@pytest.mark.parametrize('limit', ['MAX_EXPORT', 'MAX_ARCHIVE'])
def test_native_export_enforces_inclusive_expanded_and_compressed_limits(monkeypatch, limit):
    from t01_phase1_real.service_api import native_results
    rt, report, _ = raw_runtime()
    raw = collect(rt, 'parent', report, include_raw=True)[1]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        size = sum(i.file_size for i in z.infolist()) if limit == 'MAX_EXPORT' else len(raw)
    monkeypatch.setattr(native_results, limit, size)
    assert collect(rt, 'parent', report, include_raw=True)[1] == raw
    monkeypatch.setattr(native_results, limit, size - 1)
    with pytest.raises(RuntimeFault):
        collect(rt, 'parent', report, include_raw=True)


def test_streaming_export_still_rejects_tampered_raw_bytes():
    rt, report, payloads = raw_runtime()
    payloads['second'] = b'tampered'
    with pytest.raises(RuntimeFault, match='Native output bytes differ'):
        collect(rt, 'parent', report, include_raw=True)


@pytest.mark.parametrize('corruption',['run','bytes','binding'])
def test_non_v2_export_still_rejects_unbound_results(corruption):
    rt, report=bound_runtime()
    if corruption=='run':rt.jobs['child']['run_id']='foreign'
    elif corruption=='bytes':rt.artifact_bytes=lambda *args:b'corrupt'
    else:rt._request_bytes=lambda job:encode(dict(protein_sequence='ACD',changed=True))
    with pytest.raises(RuntimeFault):collect(rt,'parent',report)


def test_himat_non_v2_card_keeps_not_executed_and_offers_native_attachment(actual):
    package,snapshot,workflow=actual
    class Reports:
        credentials=Credentials.from_document({'credentials':[dict(token='k'*48,principal='himat-t01-test',scopes=['query','download'])]})
        def report(self,*args):return dict(content=package,filename='workflow.zip',sha256=sha(package),native_results=snapshot,
            report_name='20261011-073807-12345678')
        def native_report(self,*args,**kwargs):return dict(content=b'test',filename='antigen-tool-results.zip',sha256=sha(b'test'))
        def status(self,*args):return dict(terminal=True,state='succeeded',error_code=None,nodes=workflow['nodes'])
    adapter=HiMatIntegration(Reports(),'https://example.invalid',b'k'*32)
    owner=Principal('himat-t01-test',frozenset({'query','download'}),'test')
    card=adapter.check(owner,snapshot['job_id'])['data']
    assert 'DESIGN_NOT_EXECUTED' in card['summaryText'] and 'NO_DESIGNABLE_POSITIONS' in card['summaryText']
    assert len(card['attachments'])==4 and card['attachments'][-1]['attachmentId']=='attachment_native_results'


def test_expert_adoption_does_not_replay_pre_adoption_job(monkeypatch):
    from t01_phase1_real.development.workflow import revision_v2
    configure = revision_v2.config
    captured = []
    class ExistingSubmissions:
        jobs = {}
        def submit(self, principal, body):
            captured.append(copy.deepcopy(body))
            key = body['idempotency_key']
            if key not in self.jobs:
                self.jobs[key] = dict(job_id='captured-job-'+str(len(self.jobs)),state='queued')
            return dict(self.jobs[key])
    service = ExistingSubmissions()
    adapter = HiMatIntegration(service,'https://example.invalid',b'k'*32)
    owner = Principal('himat-t01-test',frozenset({'submit','query'}),'test')
    sequence = 'ACDEFGHIKLMNPQRSTVWY'
    with monkeypatch.context() as old:
        old.setattr(revision_v2,'config',lambda *a,**k:configure('himat-expert-v2-20261010-rsa-positions-v1'))
        legacy = adapter.submit_sequence(owner,sequence,'猪')
    original = copy.deepcopy(captured[0])
    current = adapter.submit_sequence(owner,sequence,'猪')
    replay = adapter.submit_sequence(owner,sequence,'猪')
    assert current['job_id'] != legacy['job_id'] and replay['job_id'] == current['job_id']
    assert current['calculation_config_id'] == 'himat-expert-v2-20261013-same-engine-v2'
    assert captured[0] == original and captured[1] == captured[2]
    from t01_phase1_real.development.workflow.revision_structure import SINGLE_MODEL_POLICY
    assert captured[1]['request']['revision_config'] == configure(current['calculation_config_id'],model_policy=SINGLE_MODEL_POLICY)
    assert captured[1]['request']['prediction']['engine'] == 'af3'
