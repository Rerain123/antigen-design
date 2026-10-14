from __future__ import annotations

from jsonschema import Draft202012Validator

from t01_phase1_mock.jsonio import load_json
from t01_phase1_mock.paths import (
    M3_ACCEPTANCE_RESULT_PATH,
    M3_ACCEPTANCE_RESULT_SCHEMA_PATH,
    M3_EXECUTION_MANIFEST_PATH,
    PROJECT_ROOT,
)


def test_m3_machine_result_validates_and_all_blockers_pass() -> None:
    schema = load_json(M3_ACCEPTANCE_RESULT_SCHEMA_PATH)
    result = load_json(M3_ACCEPTANCE_RESULT_PATH)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(result)
    assert result["status"] == "PASS"
    assert result["blocker_failure_count"] == 0
    for stage in (result["main"], result["debug"]):
        assert stage["status"] == "PASS"
        assert (
            stage["case_count"],
            stage["submission_count"],
            stage["checkpoint_plan_count"],
            stage["checkpoint_count"],
        ) == (21, 23, 4, 16)
        assert (
            stage["global_assertion_count"],
            stage["focus_assertion_count"],
            stage["coverage_gate_count"],
        ) == (9, 44, 10)
        assert all(item["status"] == "PASS" for item in stage["global_assertions"])
        assert all(item["status"] == "PASS" for item in stage["focus_assertions"])
        assert all(item["status"] == "PASS" for item in stage["coverage_gates"])
        assert len(stage["instance_run_mappings"]) == 27
        assert len({item["dify_workflow_run_id"] for item in stage["instance_run_mappings"]}) == 27
        assert all(item["dify_status"] == "succeeded" for item in stage["instance_run_mappings"])
        assert all(
            item["dify_workflow_run_id"] != item["canonical_run_id"]
            for item in stage["instance_run_mappings"]
        )


def test_target_captures_hold_23_submissions_and_16_checkpoints_per_role() -> None:
    manifest = load_json(M3_EXECUTION_MANIFEST_PATH)
    for role in ("main", "debug"):
        captures = manifest[role]["captures"]
        submissions = load_json(PROJECT_ROOT / captures["submissions_path"])
        driver = load_json(PROJECT_ROOT / captures["driver_path"])
        finalizations = load_json(PROJECT_ROOT / captures["finalizations_path"])
        assert submissions["status"] == "PASS"
        assert submissions["invocation_count"] == 23
        assert len({item["dify_workflow_run_id"] for item in submissions["results"]}) == 23
        assert driver["checkpoint_plan_count"] == 4
        assert driver["checkpoint_count"] == 16
        assert driver["canonical_submission_count_delta"] == 0
        assert finalizations["status"] == "PASS"
        assert finalizations["invocation_count"] == 4


def test_m3_execution_has_no_scientific_or_himat_side_effects() -> None:
    result = load_json(M3_ACCEPTANCE_RESULT_PATH)
    assert result["scientific_execution_count"] == 0
    assert result["scientific_network_request_count"] == 0
    assert result["legacy_implementation_reuse_count"] == 0
    assert result["himat_backend_access_count"] == 0
