"""Regression against the actual completed v2 run and owner-scoped exports."""
import copy
import io
import json
from pathlib import Path
from urllib.parse import urlsplit
import zipfile

import pytest

from t01_phase1_real.common import RuntimeFault, sha
from t01_phase1_real.service_api.app import Credentials, Principal, ServiceError
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.native_results import mhc_summary, safe_path
from t01_phase1_real.service_api.user_report import from_workflow_package

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT/'reports/expert-revision-v2-native-20260930/r01/final'
NATIVE = ROOT/'reports/expert-revision-v2-results-20260930/r01'


def test_actual_backend_numbers_are_visible_with_qualification_retained():
    raw=(OLD/'workflow-package.zip').read_bytes();digest=sha(raw)
    snapshot=json.loads((NATIVE/'tool-results.json').read_bytes());before=copy.deepcopy(snapshot)
    html=from_workflow_package(raw,native_results=snapshot).decode()
    assert '唯一候选' in html and '<strong>5</strong>' in html and '<strong>无记录</strong>' not in html
    assert '-1.758342' in html and '0.787493' in html and '0.813358' in html
    assert '108528' in html and '>559<' in html and '>576<' in html and '0.007' in html
    assert '25.479090' in html and '10.844694' in html and '-0.625000' in html
    assert 'PROPKA 原始 pH 能量曲线' in html and '溶剂可及表面积与相对暴露度' in html
    assert html.count('个残基的两列原始预测均已取得')==3
    assert 'WT 与候选的预测器版本指纹不同' in html
    assert '未接通 AGGRESCAN3D 输入' in html and '未接通 PROPKA 输入' in html
    assert '没有跨组总排名' in html and '完整覆盖：' not in html
    assert "{'high_consensus':" not in html and '正式生成 24 条记录，去重后 5 条' in html
    assert len(html.encode())<4*1024**2 and snapshot==before and sha(raw)==digest


def test_batch_backed_mhc_is_counted_from_native_labels_and_missing_is_not_zero():
    hits=[dict(classification=c,allele='SLA-1:0101',percent_rank=.1,start=1,end=9,peptide_seq='ACDEFGHIK') for c in ('SB','WB','NB')]
    parent=dict(channels=dict(mhc_i=dict(status='parsed_unreviewed',hits=None,observed_rows=3,skipped_inverted_rows=0)))
    batches=[dict(channels=dict(mhc_i=dict(status='parsed_unreviewed',hits=hits)))]
    assert mhc_summary(parent,batches)['mhc_i']['counts']==dict(SB=1,WB=1,NB=1)
    assert mhc_summary(parent,[])['mhc_i']['counts']==dict(SB=None,WB=None,NB=None)
    parent['channels']['mhc_i']['observed_rows']=4
    with pytest.raises(RuntimeFault,match='coverage differs'):mhc_summary(parent,batches)


@pytest.mark.parametrize('path',['../secret','/absolute','C:/secret','a\\b','a/../b','a//b',''])
def test_native_export_rejects_path_escape(path):
    with pytest.raises(RuntimeFault):safe_path(path)


def test_real_raw_export_contains_all_mhc_batches_and_hash_bound_files():
    with zipfile.ZipFile(NATIVE/'antigen-tool-results.zip') as z:
        manifest=json.loads(z.read('manifest.json'))
        assert manifest['source_package_sha256']==sha((OLD/'workflow-package.zip').read_bytes())
        assert len(manifest['files'])==1039 and manifest['new_model_calls']==0
        result_paths=[r['path'] for r in manifest['files'] if '_batch' in r['path'] and r['path'].endswith('/result.json')]
        assert len(result_paths)==16
        for item in manifest['files']:
            raw=z.read(item['path'])
            assert len(raw)==item['size_bytes'] and sha(raw)==item['sha256']


def test_native_attachment_retains_owner_expiry_and_signed_bytes():
    snapshot=json.loads((NATIVE/'tool-results.json').read_bytes())
    package=(OLD/'workflow-package.zip').read_bytes();archive=(NATIVE/'antigen-tool-results.zip').read_bytes()
    jid=snapshot['job_id']
    class Reports:
        credentials=Credentials.from_document({'credentials':[dict(token='k'*48,principal='himat-t01-test',scopes=['query','download'])]})
        def report(self,*args):return dict(content=package,filename='workflow.zip',sha256=sha(package),native_results=snapshot,
            report_name='20261011-073807-12345678')
        def native_report(self,*args,**kwargs):return dict(content=archive,filename='antigen-tool-results.zip',media_type='application/zip',sha256=sha(archive))
        def status(self,*args):return dict(terminal=True,state='succeeded',error_code=None,nodes={})
    adapter=HiMatIntegration(Reports(),'https://example.invalid',b'k'*32)
    user=Principal('himat-t01-test',frozenset({'query','download'}),'test')
    card=adapter.check(user,jid)['data'];assert len(card['attachments'])==4
    attachment=next(a for a in card['attachments'] if a['attachmentId']=='attachment_native_results')
    url=urlsplit(attachment['fileUrl']);value,filename,mime,digest=adapter.download(url.path,url.query)
    assert value==archive and filename=='antigen-tool-results.zip' and mime=='application/zip' and sha(value)==digest
    with pytest.raises(ServiceError):adapter.download(url.path,url.query.replace('himat-t01-test','other'))
    with pytest.raises(ServiceError):adapter.download(url.path,url.query,now=10**12)
    with pytest.raises(ServiceError):adapter.download(url.path.replace('/native','/html'),url.query)
