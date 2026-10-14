from __future__ import annotations

from copy import deepcopy

import pytest

from t01_phase1_mock import AssertionOperatorRegistry, SelectorAdapter
from t01_phase1_mock.acceptance import selector_view
from t01_phase1_mock.jsonio import ContractError


def test_all_28_frozen_operators_have_native_evaluators(tmp_path) -> None:
    registry = AssertionOperatorRegistry()
    inside = tmp_path / "root" / "child"
    samples = {
        "JSON_SCHEMA_VALID": (
            {"value": 1},
            {
                "type": "object",
                "required": ["value"],
                "properties": {"value": {"type": "integer"}},
            },
        ),
        "COUNT_EQUALS": ([1, 2], 2),
        "SET_EQUALS": (["a", "b"], ["b", "a"]),
        "BIJECTION": ((["a", "b"], ["b", "a"]), None),
        "EXACT_CATALOG_PROJECTION": ({"a": 1}, {"a": 1}),
        "FIELD_EQUALS": ([1, "x"], [1, "x"]),
        "FIELD_ABSENT": ({"kept": True}, ["missing"]),
        "MATCHES_REGEX": ("N01", r"^N[0-9]{2}$"),
        "REFERENCES_RESOLVE": (["fixture.one"], {"fixture.one": "v0.1"}),
        "CONTAINS_NONE": ({"safe": "value"}, ["forbidden"]),
        "NODE_STATUS_ALL": (["SUCCEEDED", "SUCCEEDED"], "SUCCEEDED"),
        "NODE_ATTEMPT_COUNT_EQUALS": ([[1], [1, 2]], [1, 2]),
        "NODE_ATTEMPT_FIELD_SEQUENCE_EQUALS": ([24, 48], [24, 48]),
        "CONTROL_DECISION_SEQUENCE_EQUALS": (["A", "B"], ["A", "B"]),
        "EDGE_PRESENT": (["E001", "E002"], ["E002"]),
        "EDGE_ABSENT": (["E001"], ["E002"]),
        "EDGE_ORDERED_SUBSEQUENCE": (["E001", "E099", "E002"], ["E001", "E002"]),
        "SUBMISSION_ACTION_EQUALS": (["CREATE_RUN", "id"], ["CREATE_RUN", "id"]),
        "IDENTITY_RELATION_EQUALS": ({"same": True}, {"same": True}),
        "EMISSION_COUNT_EQUALS": (1, 1),
        "NO_CONTROL_AFTER_NODE": (
            ({"gate": {"state": "NOT_REACHED"}}, "FAILED"),
            {"terminal_node": "N08", "control_state": "NOT_REACHED"},
        ),
        "NO_SCIENTIFIC_VALUES": (
            {"mock_only": True, "scientific_compute": False},
            {
                "scientific_assertion_count": 0,
                "remote_retrieval_count": 0,
                "scientific_execution_count": 0,
            },
        ),
        "JOIN_PRECONDITION": (
            ("SUCCEEDED", "SKIPPED_CONDITION", ["E024", "E025", "E026"]),
            {"join_edge": "E026", "required_arrival_edges": ["E024", "E025"]},
        ),
        "ORIGINAL_RUN_UNCHANGED": (("same", "same"), True),
        "NO_STUB_PROMOTION": (["FAILED", "FAILED"], ["FAILED", "FAILED"]),
        "PATH_WITHIN": (str(inside), str(tmp_path / "root")),
        "HASH_UNCHANGED": (("a" * 64, "a" * 64), True),
        "NORMALIZED_EQUALS": ({"state": "PASS"}, {"state": "PASS"}),
    }
    assert tuple(samples) == registry.NAMES
    assert all(registry.evaluate(name, *values) for name, values in samples.items())


@pytest.mark.parametrize(
    ("operator", "actual", "expected"),
    (
        ("FIELD_EQUALS", "FAILED", "SUCCEEDED"),
        ("EDGE_PRESENT", ["E001"], ["E002"]),
        ("HASH_UNCHANGED", ("before", "after"), True),
        ("IDENTITY_RELATION_EQUALS", "run-a", "run-b"),
        ("CONTROL_DECISION_SEQUENCE_EQUALS", ["RECALC_REQUIRED"], ["PASS"]),
    ),
)
def test_operator_mutations_fail_closed(operator, actual, expected) -> None:
    assert AssertionOperatorRegistry().evaluate(operator, actual, expected) is False


def test_path_escape_mutation_fails_closed(tmp_path) -> None:
    assert (
        AssertionOperatorRegistry().evaluate(
            "PATH_WITHIN", str(tmp_path / "outside"), str(tmp_path / "inside")
        )
        is False
    )


def test_unknown_operator_is_rejected() -> None:
    with pytest.raises(ContractError, match="unknown assertion operator"):
        AssertionOperatorRegistry().evaluate("APPROX_EQUALS", 1, 1)


def test_count_operator_rejects_implicit_type_conversion() -> None:
    with pytest.raises(ContractError, match="must be an integer"):
        AssertionOperatorRegistry().evaluate("COUNT_EQUALS", [1, 2], "2")


def test_every_m2_catalog_selector_resolves(
    case_executions, execution_by_key, spec_bundle
) -> None:
    globals_for_m2 = [
        item
        for item in spec_bundle.acceptance_catalog["global_assertions"]
        if "M2_BACKEND" in item["applies_to"]
    ]
    for case in case_executions:
        adapter = SelectorAdapter(selector_view(case, spec_bundle))
        for assertion in globals_for_m2:
            adapter.resolve(assertion["actual_selector"])
            if "source_selector" in assertion["expected"]:
                adapter.resolve(assertion["expected"]["source_selector"])

    for acceptance_case in spec_bundle.acceptance_catalog["acceptance_cases"]:
        case = execution_by_key[acceptance_case["scenario_key"]]
        adapter = SelectorAdapter(selector_view(case, spec_bundle))
        for assertion in acceptance_case["focus_assertions"]:
            if "M2_BACKEND" not in assertion["applies_to"]:
                continue
            adapter.resolve(assertion["actual_selector"])
            if "source_selector" in assertion["expected"]:
                adapter.resolve(assertion["expected"]["source_selector"])


def test_selector_view_is_closed_and_read_only(execution_by_key, spec_bundle) -> None:
    case = execution_by_key["happy_provided_structure"]
    view = selector_view(case, spec_bundle)
    assert tuple(view) == SelectorAdapter.ROOTS
    adapter = SelectorAdapter(view)
    selected = adapter.resolve("run.node[N01]")
    selected["status"] = "MUTATED"
    assert case.final_run["node_results"][0]["status"] == "SUCCEEDED"
    with pytest.raises(ContractError, match="missing selector field"):
        adapter.resolve("run.not_a_field")


def test_harness_reports_projection_mutation_as_blocker(
    m2_harness, case_executions
) -> None:
    mutated = deepcopy(case_executions)
    mutated[0].final_run["node_results"][0]["status"] = "FAILED"
    report = m2_harness.run(mutated)
    assert report["status"] == "FAIL"
    failures = {
        item["assertion_id"]
        for item in report["global_assertions"]
        if item["status"] == "FAIL"
    }
    assert "t01_phase1_mock_v01.acceptance.global.004" in failures
    assert "t01_phase1_mock_v01.acceptance.global.009" in failures


def test_every_global_catalog_assertion_reaches_its_native_operator(
    monkeypatch, m2_harness, case_executions, spec_bundle
) -> None:
    calls: list[str] = []
    original = m2_harness.operators.evaluate

    def recording_evaluate(name, actual, expected):
        calls.append(name)
        return original(name, actual, expected)

    monkeypatch.setattr(m2_harness.operators, "evaluate", recording_evaluate)
    report = m2_harness.run(case_executions)
    global_specs = [
        item
        for item in spec_bundle.acceptance_catalog["global_assertions"]
        if "M2_BACKEND" in item["applies_to"]
    ]
    expected_global_calls = [
        assertion["operator"]
        for assertion in global_specs
        for _case in case_executions
    ]
    assert report["status"] == "PASS"
    assert calls[: len(expected_global_calls)] == expected_global_calls
    assert len(calls) == len(expected_global_calls) + 44
