from __future__ import annotations

import pytest

from t01_phase1_mock.jsonio import load_json
from t01_phase1_mock.catalog import validate_instance
from t01_phase1_mock.paths import (
    M2_ACCEPTANCE_RESULT_PATH,
    M2_ACCEPTANCE_RESULT_SCHEMA_PATH,
)


GLOBAL_ASSERTION_IDS = tuple(
    f"t01_phase1_mock_v01.acceptance.global.{number:03d}"
    for number in (4, 8, 9, 10, 11, 12, 13, 14, 17)
)
FOCUS_COUNTS = (2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 2, 2, 2, 3)
FOCUS_ASSERTION_IDS = tuple(
    f"t01_phase1_mock_v01.acceptance.case.{case_number:03d}.focus.{focus_number:02d}"
    for case_number, count in enumerate(FOCUS_COUNTS, start=1)
    for focus_number in range(1, count + 1)
)
M2_ASSERTION_IDS = GLOBAL_ASSERTION_IDS + FOCUS_ASSERTION_IDS


def test_m2_report_has_frozen_execution_totals(m2_report) -> None:
    assert m2_report["status"] == "PASS"
    assert m2_report["case_count"] == 21
    assert m2_report["submission_count"] == 23
    assert m2_report["unique_submission_request_id_count"] == 23
    assert m2_report["request_variant_count"] == 22
    assert m2_report["attempt_fixture_count"] == 326
    assert m2_report["null_attempt_fixture_count"] == 8
    assert m2_report["fixture_payload_file_count"] == 350
    assert m2_report["node_terminal_directive_count"] == 378
    assert m2_report["attempt_count"] == 334
    assert m2_report["checkpoint_plan_count"] == 4
    assert m2_report["checkpoint_count"] == 16
    assert m2_report["tool_count"] == 26
    assert m2_report["operator_count"] == 28
    assert m2_report["global_assertion_count"] == 9
    assert m2_report["focus_assertion_count"] == 44
    assert m2_report["blocker_assertion_count"] == 53
    assert m2_report["blocker_failure_count"] == 0
    assert m2_report["coverage_gate_count"] == 10
    assert m2_report["coverage_gate_failure_count"] == 0
    assert all(item["status"] == "PASS" for item in m2_report["coverage_gates"])
    assert len(m2_report["source_sha256"]) == 21


@pytest.mark.parametrize("assertion_id", M2_ASSERTION_IDS)
def test_each_m2_blocker_assertion_passes(assertion_id, m2_report) -> None:
    results = {
        item["assertion_id"]: item
        for item in m2_report["global_assertions"] + m2_report["focus_assertions"]
    }
    assert set(results) == set(M2_ASSERTION_IDS)
    assert results[assertion_id]["severity"] == "BLOCKER"
    assert results[assertion_id]["status"] == "PASS"


def test_all_case_results_pass(m2_report) -> None:
    assert len(m2_report["case_results"]) == 21
    assert all(item["status"] == "PASS" for item in m2_report["case_results"])
    assert sum(item["submission_count"] for item in m2_report["case_results"]) == 23
    assert sum(item["checkpoint_count"] for item in m2_report["case_results"]) == 16


def test_submission_action_totals(m2_report) -> None:
    actions = [
        action
        for item in m2_report["case_results"]
        for action in item["submission_actions"]
    ]
    assert actions.count("CREATE_RUN") == 21
    assert actions.count("RETURN_EXISTING_RUN") == 1
    assert actions.count("REJECT_REQUEST") == 1


def test_committed_m2_result_matches_executable_harness(m2_report) -> None:
    assert load_json(M2_ACCEPTANCE_RESULT_PATH) == m2_report


def test_m2_result_has_and_passes_its_own_schema(m2_report) -> None:
    schema = load_json(M2_ACCEPTANCE_RESULT_SCHEMA_PATH)
    validate_instance(m2_report, schema, "committed M2 result")
