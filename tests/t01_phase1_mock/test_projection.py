from __future__ import annotations

import pytest

from t01_phase1_mock.acceptance import (
    normalize_node_plan,
    normalized_control_view,
)
from t01_phase1_mock.constants import NODE_IDS


SCENARIO_KEYS = (
    "happy_provided_structure",
    "happy_no_structure_local_af3",
    "happy_no_structure_local_esmfold2",
    "gate_wt_direct",
    "n12_pass_cycle_2",
    "n12_pass_cycle_3",
    "n12_recalc_exhausted",
    "n15_wt_fallback",
    "n16_missing_expression_host",
    "n17_not_applicable",
    "n16_unsupported_expression_host",
    "n17_branch_failed",
    "n16_branch_timeout_partial",
    "n08_upstream_tool_failed",
    "n01_local_prediction_failed_no_remote_fallback",
    "run_cancelled_before_join",
    "n08_retryable_recovery",
    "idempotent_replay",
    "idempotency_conflict",
    "n18_assembly_failed",
    "n08_upstream_timed_out",
)


@pytest.mark.parametrize("scenario_key", SCENARIO_KEYS)
def test_terminal_run_is_exact_catalog_projection(
    scenario_key, execution_by_key, spec_bundle
) -> None:
    execution = execution_by_key[scenario_key]
    run = execution.final_run
    scenario = execution.scenario
    spec_bundle.validate_envelope(run, scenario_key)
    assert [item["node_id"] for item in run["node_results"]] == list(NODE_IDS)
    assert normalize_node_plan(run) == scenario["node_plan"]
    assert normalized_control_view(run, scenario) == scenario["control_plan"]
    assert [item["edge_id"] for item in run["edge_traversals"]] == scenario["edge_plan"]
    assert run["run_status"] == scenario["expected_run"]["run_status"]
    assert run["result"]["result_kind"] == scenario["expected_run"]["result_kind"]
    assert run["result"]["handoff"]["status"] == "NOT_DEPLOYED"


@pytest.mark.parametrize(
    "scenario_key",
    (
        "n16_branch_timeout_partial",
        "run_cancelled_before_join",
        "n08_retryable_recovery",
        "n08_upstream_timed_out",
    ),
)
def test_all_four_checkpoint_steps_are_explicit_and_schema_valid(
    scenario_key, execution_by_key, spec_bundle
) -> None:
    execution = execution_by_key[scenario_key]
    plan = spec_bundle.checkpoint_by_scenario[scenario_key]
    assert len(execution.checkpoints) == 4
    for actual, expected in zip(execution.checkpoints, plan["steps"], strict=True):
        assert actual["sequence"] == expected["sequence"]
        assert actual["action"] == expected["action"]
        assert actual["checkpoint_fact"] == expected["checkpoint_fact"]
        assert actual["run"]["run_status"] == expected["expected_run_status"]
        assert len(actual["run"]["node_results"]) == 18
        spec_bundle.validate_envelope(actual["run"], f"{scenario_key} checkpoint")


def test_recovery_uses_new_run_and_preserves_attempt_history(execution_by_key) -> None:
    execution = execution_by_key["n08_retryable_recovery"]
    original_run_id = execution.checkpoints[0]["run_id"]
    recovered_run_id = execution.final_run_id
    assert recovered_run_id != original_run_id
    assert execution.final_run["recovery_of_run_id"] == original_run_id
    n08 = next(item for item in execution.final_run["node_results"] if item["node_id"] == "N08")
    assert [item["status"] for item in n08["attempts"]] == ["FAILED", "SUCCEEDED"]
    assert n08["attempts"][1]["recovery_of_attempt_id"] == n08["attempts"][0]["attempt_id"]


def test_each_submission_has_a_new_request_id(case_executions) -> None:
    request_ids = [request["request_id"] for case in case_executions for request in case.requests]
    assert len(request_ids) == 23
    assert len(set(request_ids)) == 23
