"""Rule boundaries: explain archived evidence, never silently relax permissions."""
import copy
import json
from pathlib import Path

import pytest

from t01_phase1_real.common import RuntimeFault
from t01_phase1_real.development.bepipred import postprocessing as peaks
from t01_phase1_real.development.design_backend.boundary import describe
from t01_phase1_real.development.developability import camsol, camsol_numerics as numeric
from t01_phase1_real.development.netmhc.host_panel import readiness
from t01_phase1_real.service_api.native_report import build

ROOT = Path(__file__).resolve().parents[1]


def actual():
    return json.loads((ROOT/'reports/himat-report-review-20261009/backend-evidence.json').read_text(encoding='utf8'))


def test_real_chain_boundary_preserves_current_masks_and_separates_overlap():
    data = actual(); before = copy.deepcopy(data)
    perms = data['results']['design_inputs']['audit']['permissions']
    domains = data['results']['domains']['analysis']['functional_domains']
    result = describe(perms, domains)
    assert result['all_positions_fixed'] and result['sequence_length'] == 233
    assert result['mature_chain_fixed_positions'] == list(range(1, 234))
    assert result['also_fixed_by_independent_evidence'] == list(range(1, 48))
    assert result['fixed_only_by_mature_chain'] == list(range(48, 234))
    assert result['alternative_permissions'] is None and not result['permissions_changed']
    assert data == before


def test_user_fixed_and_independent_hard_are_not_removed_with_chain():
    chain = dict(source='domains', source_path='analysis.functional_domains[0]', constraint_state='HARD')
    rows = [dict(position=i, design_permission='FIXED', evidence_source=[chain], user_sources=[]) for i in range(1, 4)]
    rows[0]['user_sources'] = [dict(permission='FIXED')]
    rows[1]['evidence_source'] = [chain, dict(source='epitope_map', constraint_state='HARD')]
    rows[2]['design_permission'] = 'OPEN'
    result = describe(dict(per_residue=rows, fixed_positions=[1, 2]), [dict(type='mature_chain')])
    assert result['also_fixed_by_independent_evidence'] == [1, 2]
    assert result['explicit_override_positions'] == [3] and not result['fixed_only_by_mature_chain']
    assert not result['all_positions_fixed']


def test_actual_v2_no_model_report_preserves_raw_execution_evidence():
    data = actual(); original = copy.deepcopy(data)
    nodes = copy.deepcopy(data['nodes'])
    for name, result in data['results'].items():
        if name in nodes:
            nodes[name]['result'] = result
    # Minimal report-view context from the verified archived results.
    view = dict(wt_draft=dict(assessments={name: dict(observations=result)
                                         for name, result in data['results'].items()}))
    native = dict(nodes=nodes, run_id=data['job']['run_id'], job_id=data['job']['job_id'],
                  workflow_package_sha256='archived-evidence-view', revision_config=data['request']['revision_config'])
    sections = build(view, dict(expert_revision=data['revision_state']), native)
    assert '原生候选生成器未调用' in sections['permissions']
    assert '仅有成熟链 HARD 依据' in sections['permissions'] and '>186<' in sections['permissions']
    assert '完整覆盖：' not in sections['appendix']
    assert '完整计算参数、任务记录和原始文件保留在随附结果包中' in sections['appendix']
    assert data == original


def test_project_strict_threshold_and_native_top20_are_distinct():
    assert peaks.threshold_mask([.15, .1512, .15120001]) == [False, False, True]
    assert peaks.native_top20_mask([.5]*7) == [True]+[False]*6
    assert sum(peaks.native_top20_mask([.5]*8)) == 2


def test_filter_and_bridge_order_is_observably_ambiguous():
    rows = peaks.segments([True]*3+[False]*2+[True]*3)
    assert peaks.minimum_length(peaks.bridge(rows)) == [dict(start=1, end=8)]
    assert peaks.bridge(peaks.minimum_length(rows)) == []
    assert rows == [dict(start=1, end=3), dict(start=6, end=8)]
    assert peaks.bridge([dict(start=1, end=6), dict(start=10, end=15)]) == [dict(start=1, end=6), dict(start=10, end=15)]


@pytest.mark.parametrize('bad', [[], [float('nan')], [float('inf')], [-.1], [1.1], [True]])
def test_postprocessing_rejects_invalid_probability(bad):
    with pytest.raises(RuntimeFault):
        peaks.threshold_mask(bad)


def test_score_diagnostics_never_choose_project_column_or_publish_peaks():
    rows = [dict(sequence_position=i, ensemble_probability=.2, linear_epitope_score=.1) for i in range(1, 11)]
    before = copy.deepcopy(rows); result = peaks.inspect(rows)
    assert len(result['columns']['ensemble_probability']['above_project_threshold_positions']) == 10
    assert result['columns']['linear_epitope_score']['above_project_threshold_positions'] == []
    assert result['linear_peaks'] is result['linear_scores'] is result['selected_project_score'] is None
    assert not result['scientific_consumption'] and rows == before


def test_camsol_defined_correction_matches_independent_hand_calculation():
    params = camsol.parameters()
    # Synthetic kernel fixture: explicit counts supplied, not a pattern policy.
    expected = .96018 + params['correction_coefficients']['a_pat']*2
    assert numeric.corrected_profile('A', params, pattern_counts=[2]) == pytest.approx([expected])
    assert numeric.normalize([1., 3., 5.], mu=3., sigma=2.) == [-1., 0., 1.]
    result = numeric.summarize([-.7, .7, -.8, .8, 2.])
    assert result['eq9_value'] == pytest.approx(.4) and result['classification'] == 'medium'
    assert not result['scientific_consumption']


@pytest.mark.parametrize('value, expected', [(-1.0001, 'low'), (-1., 'medium'), (1., 'medium'), (1.0001, 'high')])
def test_camsol_classification_boundaries(value, expected):
    assert numeric.summarize([value])['classification'] == expected


def test_camsol_regions_and_registered_parameters_remain_unreviewed():
    assert numeric.summarize([-2.]*5+[-1.]+[-2.]*4)['insoluble_regions'] == [dict(start=1, end=5)]
    value = camsol.assess('ACDEFGHIK')
    assert isinstance(value['global_score'],float) and len(value['per_residue'])==9
    assert value['status'] == 'computed_unreviewed' and not value['reliable']
    with pytest.raises(TypeError):
        numeric.corrected_profile('A', camsol.parameters())


@pytest.mark.parametrize('sigma', [None, 0., -1., float('nan'), float('inf'), True])
def test_camsol_rejects_invalid_calibration(sigma):
    with pytest.raises(RuntimeFault):
        numeric.normalize([1.], mu=0., sigma=sigma)


def test_pig_readiness_does_not_substitute_human_panel_or_call_models():
    result = readiness('猪')
    assert result['channels']['mhc_i']['allele_count'] == 76
    ii = result['channels']['mhc_ii']
    assert ii['status'] == 'UNAVAILABLE' and ii['allele_count'] == 0
    assert 'LOCAL_MODEL_AND_PERCENT_RANK_SUPPORT_FOR_EACH_PAIR' in ii['missing_requirements']
    assert not result['model_invoked'] and not result['substitution_applied']
