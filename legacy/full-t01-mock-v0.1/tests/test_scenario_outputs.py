from __future__ import annotations

import pytest

from t01_mock_mcp.contracts import ErrorCategory, StepStatus

from conftest import make_request


def test_epitope_maps_have_all_three_required_keys(engine, configure) -> None:
    run_id = configure("MOCK-HAPPY-PATH")
    result = engine.execute("epitope.synthesize_maps", make_request(run_id))
    evidence = result.data["epitope_evidence"]
    assert {
        "b_cell_epitope_map",
        "t_cell_presentation_map",
        "b_cell_antigenic_hotspot_map",
    } <= set(evidence)
    assert evidence["weight_mapping_status"] == "SOP_PENDING"


@pytest.mark.parametrize(
    "scenario,violation,penalty",
    [
        ("MOCK-EPITOPE-STRUCTURAL-FAIL", True, False),
        ("MOCK-EPITOPE-PREDICTION-FAIL", False, True),
    ],
)
def test_epitope_failure_layers(engine, configure, scenario, violation, penalty) -> None:
    run_id = configure(scenario)
    result = engine.execute("epitope.validate_presentation", make_request(run_id, scope="variant"))
    assert result.data["epitope_violation"] is violation
    assert result.data["soft_penalty"] is penalty


def test_variant_safety_failure_is_hard_exclusion(engine, configure) -> None:
    run_id = configure("MOCK-VARIANT-SAFETY-FAIL")
    result = engine.execute("safety.assess_triple", make_request(run_id, scope="variant"))
    assert result.data["safety_excluded"] is True


def test_score_pool_skip_scenario(engine, configure) -> None:
    run_id = configure("MOCK-19B-SKIPPED")
    result = engine.execute("t01.select_stability_score_pool", make_request(run_id))
    assert result.status == StepStatus.SKIPPED
    assert result.data["score_pool"] == []


def test_sc10_warning_does_not_invent_final_downgrade_rule(engine, configure) -> None:
    run_id = configure("MOCK-SC10-WARNING")
    result = engine.execute("ranking.rank_variants", make_request(run_id))
    assert result.status == StepStatus.DEGRADED
    assert "SC10_DOWNGRADE_RULE_SOP_PENDING" in result.quality_flags


@pytest.mark.parametrize(
    "scenario,category,retryable,exit_code",
    [
        ("MOCK-TOOL-TIMEOUT", ErrorCategory.TIMEOUT, True, None),
        ("MOCK-OUTPUT-MISSING", ErrorCategory.OUTPUT_MISSING, True, 0),
        ("MOCK-OUTPUT-INVALID", ErrorCategory.OUTPUT_INVALID, False, 0),
    ],
)
def test_standard_fault_contract(engine, configure, scenario, category, retryable, exit_code) -> None:
    run_id = configure(scenario)
    result = engine.execute("structure.fetch", make_request(run_id))
    assert result.status == StepStatus.FAILED
    assert result.error.category == category
    assert result.error.retryable is retryable
    assert result.provenance.exit_code == exit_code


def test_candidate_json_has_minimum_reviewed_keys(engine, configure) -> None:
    run_id = configure("MOCK-HAPPY-PATH")
    result = engine.execute("output.assemble_candidate_json", make_request(run_id))
    candidate = result.data["candidate"]
    assert {
        "best_candidate",
        "top20_variants",
        "delta_table",
        "design_permissions",
        "evidence_provenance",
        "quality_flags",
        "warnings",
        "design_skipped",
        "failure_report",
        "artifacts",
    } <= set(candidate)
    assert candidate["execution_mode"] == "mock"


def test_every_scientific_fixture_marks_mock_and_no_compute(engine, configure) -> None:
    run_id = configure("MOCK-HAPPY-PATH")
    result = engine.execute("structure.predict", make_request(run_id))
    assert "MOCK_DATA" in result.quality_flags
    assert result.data["scientific_computation_performed"] is False
    assert result.provenance.compute_profile == "mock-no-scientific-compute"

