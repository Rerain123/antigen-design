from __future__ import annotations

import pytest

from t01_mock_mcp.contracts import ErrorCategory, Outcome, StepStatus

from conftest import make_request


@pytest.mark.parametrize(
    "scenario,expected_status,expected_route",
    [
        ("MOCK-SHORT-MHC-HALT", StepStatus.FAILED, "HALT"),
        ("MOCK-SHORT-WARNING", StepStatus.DEGRADED, "WARNING"),
        ("MOCK-HAPPY-PATH", StepStatus.SUCCEEDED, "PASS"),
    ],
)
def test_length_guard(engine, configure, scenario, expected_status, expected_route) -> None:
    run_id = configure(scenario)
    result = engine.execute("t01.evaluate_length_guard", make_request(run_id))
    assert result.status == expected_status
    assert result.data["route"] == expected_route
    if expected_route == "HALT":
        assert result.error.category == ErrorCategory.SCIENTIFIC_GATE


@pytest.mark.parametrize(
    "scenario,expected_route,expected_target",
    [
        ("MOCK-HAPPY-PATH", "NONE", "S-07"),
        ("MOCK-CONTEXT-HIGH", "HIGH", "step15"),
        ("MOCK-CONTEXT-NONHIGH", "NON_HIGH", "step12"),
    ],
)
def test_context_route(engine, configure, scenario, expected_route, expected_target) -> None:
    run_id = configure(scenario)
    result = engine.execute("t01.route_context_scores", make_request(run_id))
    assert result.data["route"] == expected_route
    assert result.data["after_s16_target"] == expected_target


def test_no_structure_routes_to_prediction(engine, configure) -> None:
    run_id = configure("MOCK-NO-STRUCTURE")
    fetched = engine.execute("structure.fetch", make_request(run_id))
    routed = engine.execute("t01.route_existing_structure", make_request(run_id))
    assert fetched.data["structure_found"] is False
    assert routed.data["route"] == "S-08"


def test_low_structure_skips_rsa(engine, configure) -> None:
    run_id = configure("MOCK-LOW-STRUCTURE")
    result = engine.execute("t01.route_rsa", make_request(run_id))
    assert result.status == StepStatus.SKIPPED
    assert result.data["rsa"] is None
    assert "RSA_SKIPPED_LOW_STRUCTURE_CONFIDENCE" in result.quality_flags


@pytest.mark.parametrize(
    "scenario,expected_route",
    [
        ("MOCK-MEMBRANE-SKIP", "DESIGN_SKIPPED"),
        ("MOCK-MEMBRANE-CONFIRMED", "CONTINUE"),
    ],
)
def test_membrane_design_gate(engine, configure, scenario, expected_route) -> None:
    run_id = configure(scenario)
    result = engine.execute("t01.evaluate_design_applicability", make_request(run_id))
    assert result.data["route"] == expected_route


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("MOCK-POOR-RESCUE-SUCCESS", True),
        ("MOCK-POOR-RESCUE-FAIL", False),
    ],
)
def test_branch4_rescue_continues_to_ebb(engine, configure, scenario, expected) -> None:
    run_id = configure(scenario)
    gate = engine.execute("t01.route_stability_rescue", make_request(run_id))
    screen = engine.execute("stability.screen_rescue_top3", make_request(run_id))
    assert gate.data["route"] == "RUN_BRANCH4"
    assert screen.data["rescue_success"] is expected
    assert screen.data["continue_to"] == "EBB"


@pytest.mark.parametrize(
    "attempt,passed_count,route,next_count",
    [
        (1, 0, "RETRY", 48),
        (2, 0, "RETRY", 64),
        (3, 0, "EXHAUSTED", None),
        (1, 1, "CONTINUE", None),
    ],
)
def test_design_retry_gate(engine, configure, attempt, passed_count, route, next_count) -> None:
    run_id = configure("MOCK-HAPPY-PATH")
    request = make_request(run_id, attempt=attempt, parameters={"passed_count": passed_count})
    result = engine.execute("t01.evaluate_design_retry", request)
    assert result.data["route"] == route
    assert result.data["next_design_count"] == next_count


@pytest.mark.parametrize(
    "scenario,attempt,expected_passed",
    [
        ("MOCK-DESIGN-RETRY-48", 1, 0),
        ("MOCK-DESIGN-RETRY-48", 2, 8),
        ("MOCK-DESIGN-RETRY-64", 2, 0),
        ("MOCK-DESIGN-RETRY-64", 3, 8),
        ("MOCK-DESIGN-ALL-REJECTED", 3, 0),
    ],
)
def test_design_validation_scenarios(engine, configure, scenario, attempt, expected_passed) -> None:
    run_id = configure(scenario)
    result = engine.execute("design.validate", make_request(run_id, attempt=attempt))
    assert result.data["passed_count"] == expected_passed


@pytest.mark.parametrize(
    "scenario,expected_route",
    [("MOCK-MD-RUN", "RUN_S32"), ("MOCK-MD-SKIP", "SKIP_S32")],
)
def test_md_gate(engine, configure, scenario, expected_route) -> None:
    run_id = configure(scenario)
    result = engine.execute("t01.evaluate_md_gate", make_request(run_id))
    assert result.data["route"] == expected_route


@pytest.mark.parametrize(
    "scenario,expected_outcome",
    [
        ("MOCK-HAPPY-PATH", Outcome.VARIANT_HANDOFF),
        ("MOCK-MEMBRANE-SKIP", Outcome.WT_DESIGN_SKIPPED),
        ("MOCK-DESIGN-ALL-REJECTED", Outcome.WT_FAILURE_REPORT),
    ],
)
def test_handoff_three_routes(engine, store, configure, scenario, expected_outcome) -> None:
    run_id = configure(scenario)
    result = engine.execute("t01.route_handoff", make_request(run_id))
    assert result.data["outcome"] == expected_outcome.value
    assert store.get_run(run_id).outcome == expected_outcome

