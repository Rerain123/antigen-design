import copy
import io
import json
from pathlib import Path
from urllib.parse import urlsplit
import zipfile

import pytest
from t01_phase1_real.common import sha
from t01_phase1_real.service_api.user_report import render, from_workflow_package, series_svg
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.app import Credentials, Principal, ServiceError

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'discovery/t01-phase1-real/m1-p4-20260922/himat-first-review-r01'
CANDIDATES=ROOT/'discovery/t01-phase1-real/m1-p3-20260922/r01/delivery/data.json'


def test_real_excluded_candidates_are_not_recommended_and_ddg_is_not_lost():
    data=json.loads(CANDIDATES.read_bytes());before=copy.deepcopy(data)
    html=render(data).decode()
    assert '本轮暂无可推荐候选' in html and '共记录 24 个设计候选' in html
    assert '-2.63' in html  # Actual sample-4 five-run FoldX mean; not an invented score.
    assert '仅有 3 个代表候选' in html
    assert 'CONTROLLED_ENGINEERING_DERIVATIVE' in html
    assert '未评估' in html and data==before


def test_archive_render_preserves_failure_facts_and_original_bytes():
    raw=(ARCHIVE/'workflow.zip').read_bytes();digest=sha(raw)
    html=from_workflow_package(raw).decode()
    assert '本次未生成设计候选' in html
    assert '计算步骤失败或停止' in html and '结构预测' in html
    assert '遮蔽风险未完成判定' in html
    assert sha((ARCHIVE/'workflow.zip').read_bytes())==digest


def test_null_is_not_zero_and_input_text_cannot_execute_or_load_external_assets():
    d=dict(subject=dict(host_species='<img src=https://evil.test onerror=alert(1)>',protein_sequence='ACD'),
        missing_conditions=[dict(code='</pre><script>alert(1)</script>')])
    html=render(d,preview_note='<script>bad()</script>').decode()
    assert '<script' not in html and '<img src=' not in html
    assert '&lt;script&gt;' in html and 'Content-Security-Policy' in html
    assert '0.00' not in html and '暂无完整结果' in html


@pytest.mark.parametrize('state',['failed','cancelled','timed_out','running'])
def test_incomplete_workflow_is_not_reported_as_finished(state):
    html=render({},dict(state=state)).decode()
    assert ('阶段性结果' if state=='running' else '本次分析未完整完成') in html


def test_plot_does_not_join_across_missing_residues():
    svg=series_svg([('raw',[.1,.2,None,.3,.4],'#087f79')],'test')
    assert svg.count('stroke-width="2.2"')==2
    assert 'NaN' not in svg and 'None' not in svg


def test_html_attachment_retains_auth_expiry_and_signed_bytes():
    raw=(ARCHIVE/'workflow.zip').read_bytes()
    snapshot=json.loads((ARCHIVE/'snapshot.json').read_bytes())
    parent=next(r for r in snapshot['records'] if r['job']['tool_id']=='t01.real.local_workflow')
    class Reports:
        credentials=Credentials.from_document({'credentials':[dict(token='k'*48,principal='himat-t01-test',scopes=['query','download'])]})
        def report(self,*args):return dict(content=raw,filename='workflow.zip',sha256=sha(raw),
            report_name='20261011-073807-12345678')
        def status(self,*args):return dict(terminal=True,state='succeeded',error_code=None,nodes=parent['execution']['nodes'])
    adapter=HiMatIntegration(Reports(),'https://example.invalid',b'k'*32)
    user=Principal('himat-t01-test',frozenset({'query','download'}),'test')
    card=adapter.check(user,parent['job']['job_id'])['data']
    assert card['primaryAttachmentId']=='attachment_user_report'
    assert len(card['attachments'])==3
    target=urlsplit(card['attachments'][-1]['fileUrl'])
    value,filename,mime,digest=adapter.download(target.path,target.query)
    assert filename=='20261011-073807-12345678-report.html' and mime.startswith('text/html') and sha(value)==digest
    with pytest.raises(ServiceError):adapter.download(target.path,target.query.replace('himat-t01-test','other'))
    with pytest.raises(ServiceError):adapter.download(target.path,target.query,now=10**12)
    with pytest.raises(ServiceError):adapter.download(target.path.replace('/html','/zip'),target.query)


def test_old_markdown_only_packages_keep_the_existing_attachment():
    inner=io.BytesIO()
    with zipfile.ZipFile(inner,'w') as z:z.writestr('report.md','old')
    outer=io.BytesIO()
    with zipfile.ZipFile(outer,'w') as z:z.writestr('local-delivery.zip',inner.getvalue())
    assert from_workflow_package(outer.getvalue()) is None
