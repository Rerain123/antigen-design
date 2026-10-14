"""Scientific presentation keeps observed values and separates failure from absence."""
import copy
import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from t01_phase1_real.common import sha
from t01_phase1_real.service_api.user_report import from_workflow_package, render

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'reports/scientific-report-20261011'


@pytest.fixture(scope='module')
def actual():
    package=(EVIDENCE/'20261011-073807-7ff412a6-results.zip').read_bytes()
    with zipfile.ZipFile(EVIDENCE/'20261011-073807-7ff412a6-tool-results.zip') as archive:
        native=json.loads(archive.read('tool-results.json'))
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        workflow=json.loads(archive.read('workflow.json'))
    return package,native,workflow


def test_current_run_retains_every_candidate_and_the_scientific_failure(actual):
    package,native,workflow=actual
    before=copy.deepcopy(native);digest=sha(package)
    html=from_workflow_package(package,native_results=native).decode()
    assert '候选科学结果汇总' in html
    records=[r for r in workflow['expert_revision']['formal_records'] if r['disposition']!='DUPLICATE']
    assert len(records)==10 and html.count('class="candidate-card"')==10
    for r in records:
        assert f'id="candidate-{r["sample_number"]}"' in html
        assert f'{r["esm_if1"]["score"]:.6f}' in html
        for engine in ('af3','esmfold2'):
            assert f'{r["structure_observations"][engine]["plddt"]:.6f}' in html
        for group in ('l3','auxiliary_geometry_status'):
            for item in r['protection'][group].get('objects',[]):
                assert f'{item["observation"]["rmsd"]:.6f}' in html
    assert '结构保护：未通过；预测表位保留：未评估' in html
    assert native==before and sha(package)==digest


def test_report_contains_scientific_results_without_process_payloads(actual):
    package,native,_=actual
    html=from_workflow_package(package,native_results=native).decode()
    for internal in ('t01p1r-job-','t01p1r-run-','candidate-680de','execution_profile',
                     'resident-process','S27_VALIDATED_FUNCTIONAL','NOT_ASSESSED',
                     'L4_REQUIRED_EXECUTIONS_INCOMPLETE','<pre>','&quot;job_id&quot;'):
        assert internal not in html
    assert not re.search(r'\b[0-9a-f]{64}\b',html)
    assert '1.070296' in html and '1.003466' in html  # This run's out-of-domain RSA.
    assert '末端所需位置的暴露度数据不完整' in html
    assert 'CamSol' in html and '不纳入综合评分' in html
    assert 'IEDB 表位编号' in html and 'PubMed 编号' in html
    assert 'MHC-II：一期未评估' in html


@pytest.mark.parametrize('state,label',[('FAIL','未通过'),('NOT_ASSESSED','未评估'),('PASS','通过')])
def test_acceptance_label_never_invents_approval(state,label):
    revision=dict(formal_records=[],acceptance_status=state)
    html=render({},dict(expert_revision=revision)).decode()
    assert all(term not in html for term in ('完整验收', '暂定验收', '完整评估'))
    assert state not in html


def test_scientific_text_cannot_inject_html_or_external_assets():
    data=dict(subject=dict(protein_sequence='ACD',host_species='<script>steal()</script>'))
    html=render(data).decode()
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'Content-Security-Policy' in html and 'default-src' in html
