from __future__ import annotations

import csv
import json
from pathlib import Path

from t01_dify_workflows.regression import (
    MASTER_NAME,
    build_editor_result_records,
    build_manifest,
    evaluate_campaign,
    load_expectations,
    prepare_campaign,
)
from t01_mock_mcp.catalog import SCENARIOS


ROOT = Path(__file__).resolve().parents[1]
EXPECTATIONS = ROOT / "dify" / "regression" / "master_expected_25.json"
BASE_INPUT = ROOT / "dify" / "fixtures" / "master_input.example.json"


def test_master_expectations_cover_all_scenarios_in_canonical_order() -> None:
    document = load_expectations(EXPECTATIONS)
    assert document["workflow_name"] == MASTER_NAME
    assert [case["scenario_id"] for case in document["cases"]] == list(SCENARIOS)
    assert len(document["cases"]) == 25
    assert all(case["expected_behavior"] for case in document["cases"])
    assert all(case["expected_workflow_status"] == "succeeded" for case in document["cases"])


def test_prepare_campaign_generates_unique_four_column_inputs(tmp_path: Path) -> None:
    manifest_path, csv_path = prepare_campaign(
        expectations_path=EXPECTATIONS,
        base_input_path=BASE_INPUT,
        campaign="master-reg-test-a",
        output_dir=tmp_path,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["case_count"] == 25
    assert len({case["run_id"] for case in manifest["cases"]}) == 25
    assert manifest["cases"][0]["run_id"] == "master-reg-test-a-01"
    assert manifest["cases"][-1]["scenario_id"] == "MOCK-OUTPUT-INVALID"

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 25
    assert list(rows[0]) == [
        "run_id",
        "scenario_id",
        "t01_input_json",
        "execution_mode",
    ]
    assert json.loads(rows[0]["t01_input_json"])["execution_mode"] == "mock"


def test_evaluator_checks_trace_node_and_nested_value() -> None:
    manifest = {
        "workflow_name": MASTER_NAME,
        "campaign": "unit",
        "cases": [
            {
                "index": 1,
                "run_id": "unit-01",
                "scenario_id": "MOCK-HAPPY-PATH",
                "expected": {
                    "expected_workflow_status": "succeeded",
                    "expected_behavior": "unit",
                    "required_nodes": [f"{MASTER_NAME}::NODE"],
                    "forbidden_nodes": [f"{MASTER_NAME}::FORBIDDEN"],
                    "assertions": [
                        {
                            "node": f"{MASTER_NAME}::NODE",
                            "path": "outputs.json.0.data.route",
                            "equals": "BEST",
                        }
                    ],
                },
            }
        ],
    }
    results = [
        {
            "run_id": "unit-01",
            "response": {"data": {"status": "succeeded"}},
        }
    ]
    traces = {
        "records": [
            {
                "kind": "node_execution",
                "logical_run_id": "unit-01",
                "app_name": MASTER_NAME,
                "node_id": "NODE",
                "outputs": {"json": [{"data": {"route": "BEST"}}]},
            }
        ]
    }
    report = evaluate_campaign(
        manifest=manifest,
        result_records=results,
        trace_document=traces,
    )
    assert report["summary"] == {"total": 1, "passed": 1, "failed": 0}
    assert report["cases"][0]["verdict"] == "PASS"


def test_build_manifest_rejects_noncanonical_campaign() -> None:
    expectations = load_expectations(EXPECTATIONS)
    base_input = json.loads(BASE_INPUT.read_text(encoding="utf-8"))
    try:
        build_manifest(expectations, base_input, "contains space")
    except ValueError as exc:
        assert "campaign" in str(exc)
    else:
        raise AssertionError("invalid campaign should be rejected")


def test_editor_results_use_completed_master_trace_only() -> None:
    manifest = {
        "cases": [
            {"run_id": "ui-01", "scenario_id": "MOCK-HAPPY-PATH"},
            {"run_id": "ui-02", "scenario_id": "MOCK-SHORT-MHC-HALT"},
        ]
    }
    traces = [
        {
            "kind": "workflow_run",
            "logical_run_id": "ui-01",
            "workflow_run_id": "child",
            "app_name": "T01_P0_Structure",
            "status": "succeeded",
            "finished_at": "2026-09-01T00:00:01Z",
        },
        {
            "kind": "workflow_run",
            "logical_run_id": "ui-01",
            "workflow_run_id": "master",
            "app_name": MASTER_NAME,
            "status": "succeeded",
            "created_at": "2026-09-01T00:00:00Z",
            "finished_at": "2026-09-01T00:00:02Z",
            "outputs": {"run_id": "ui-01"},
            "error": None,
        },
        {
            "kind": "workflow_run",
            "logical_run_id": "ui-02",
            "workflow_run_id": "unfinished",
            "app_name": MASTER_NAME,
            "status": "running",
            "created_at": "2026-09-01T00:00:03Z",
            "finished_at": None,
        },
    ]
    results = build_editor_result_records(manifest, traces)
    assert len(results) == 1
    assert results[0]["run_id"] == "ui-01"
    assert results[0]["source"] == "dify_editor_database"
    assert results[0]["response"]["data"]["status"] == "succeeded"
    assert results[0]["response"]["data"]["workflow_run_id"] == "master"
