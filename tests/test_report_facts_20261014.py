"""Real historical reports: rendering cannot turn absence into failure or create candidates."""
import copy
import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from t01_phase1_real.service_api.native_report import unique_candidates, geometry_status
from t01_phase1_real.service_api.user_report import from_workflow_package

EVIDENCE = Path(__file__).resolve().parents[1] / 'reports/report-fix-20261014'
# Real scientific payloads stay local; ordinary CI uses the synthetic report tests.
pytestmark = pytest.mark.skipif(
    not all((EVIDENCE / (label + suffix)).is_file()
            for label in ('old', 'new') for suffix in ('-results.zip', '-native.json')),
    reason='Optional local historical report fixtures are not distributed with source',
)


def actual(label):
    raw = (EVIDENCE / (label + '-results.zip')).read_bytes()
    native = json.loads((EVIDENCE / (label + '-native.json')).read_bytes())
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        workflow = json.loads(archive.read('workflow.json'))
    return raw, native, workflow


@pytest.mark.parametrize('label,count,identity', [
    ('old', 32, '20261013-150602-c4081362'),
    ('new', 6, '20261013-170229-d6498f2f'),
])
def test_real_reports_keep_sequence_count_identity_and_unique_links(label, count, identity):
    raw, native, workflow = actual(label)
    before = copy.deepcopy(native)
    html = from_workflow_package(raw, native_results=native).decode()
    assert f'去重后 {count} 条' in html
    assert html.count('class="candidate-card"') == count
    assert identity in html and '下载时间不代表重新计算' in html
    ids = re.findall(r'id="(candidate-[^"]+)"', html)
    assert len(ids) == len(set(ids)) == count
    assert set(re.findall(r'href="#(candidate-[^"]+)"', html)) == set(ids)
    assert native == before


def test_old_report_does_not_call_missing_contacts_a_geometric_failure():
    raw, native, workflow = actual('old')
    html = from_workflow_package(raw, native_results=native).decode()
    assert '局部几何检查：0 条通过，0 条未通过，32 条未评估' in html
    records = unique_candidates(workflow['expert_revision']['formal_records'])
    selected = next(r for r in records if r['disposition'] == 'FORMAL_POOL')
    assert selected['checks']['chk_geometry'] == 'FAIL'  # legacy compatibility aggregate
    assert geometry_status(selected) == 'NOT_ASSESSED'
    assert '0.097452' in html  # existing geometric result stays visible
    assert '第 2 轮 · 候选 14' in html
    assert '233 个残基的两列原始预测均已取得' in html  # round-2 producer, not round-1
    assert sum(r['acceptance_status'] == 'FAIL' for r in records) == 31


def test_new_report_keeps_six_foldx_means_and_provisional_only_acceptance():
    raw, native, workflow = actual('new')
    html = from_workflow_package(raw, native_results=native).decode()
    records = unique_candidates(workflow['expert_revision']['formal_records'])
    assert '局部几何检查：6 条通过，0 条未通过，0 条未评估' in html
    assert html.count('FoldX 稳定性计算：已执行') == 6
    assert '本次评价条件尚不完整' not in html
    for r in records:
        assert r['acceptance_status'] == 'NOT_ASSESSED'
        assert r['provisional_acceptance_status'] == 'PASS'
        assert f'{r["foldx"]["mean"]:.6f}' in html
    assert all(term not in html for term in ('完整验收', '暂定验收', '完整评估', '待科学复核', '完整验收规则仍待校准'))


def test_dedup_selects_whole_evaluated_record_without_mutating_or_combining():
    rows = [dict(sequence='AAA', disposition='REJECTED', sample_number=1),
            dict(sequence='AAA', disposition='FORMAL_POOL', sample_number=2),
            dict(sequence='BBB', disposition='REJECTED', sample_number=1),
            dict(sequence='AAA', disposition='DUPLICATE', sample_number=3)]
    before = copy.deepcopy(rows)
    assert unique_candidates(rows) == [rows[1], rows[2]]
    assert unique_candidates(rows)[0] is rows[1]
    assert rows == before


def test_incomplete_evidence_and_actual_geometry_failure_are_not_softened():
    assert geometry_status({'protection': {'l3': {'check_status': 'FAIL'}}}) == 'FAIL'
    assert geometry_status({'checks': {'chk_geometry': 'FAIL'}}) == 'NOT_ASSESSED'


def test_himat_card_uses_the_same_real_sequence_count_as_html():
    from t01_phase1_real.common import sha
    from t01_phase1_real.service_api.himat import HiMatIntegration
    from t01_phase1_real.service_api.app import Principal
    raw, native, workflow = actual('old')
    class Reports:
        def report(self, *args):
            return dict(content=raw, sha256=sha(raw), filename='old-results.zip',
                        native_results=native, report_name='20261013-150602-c4081362')
        def native_report(self, *args, **kwargs):
            return dict(filename='old-tool-results.zip', sha256=sha(b'fixture'))
    adapter = HiMatIntegration(Reports(), 'https://example.invalid', b'k'*32)
    owner = Principal('himat-t01-test', frozenset({'query', 'download'}), 'test')
    card = adapter.card(owner, workflow['parent_at_assembly']['job_id'],
                        dict(terminal=True, state='succeeded', error_code=None, nodes=workflow['nodes']))['data']
    assert '正式生成 72 条，去重后 32 条' in card['summaryText']
