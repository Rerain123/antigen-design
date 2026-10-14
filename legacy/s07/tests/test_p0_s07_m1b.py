from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.capture_http_evidence import CURL_WRITE_OUT_FIELDS, parse_curl_metrics
from t01_s07_candidate import (
    build_output_audit,
    build_rcsb_page_request,
    load_and_validate_plan,
    run_campaign,
)


WORKSPACE = Path(__file__).resolve().parents[1]
PLAN_PATH = WORKSPACE / "discovery" / "p0" / "s07" / "p0-s07-m1b-plan-v0.1.json"
FORBIDDEN_DECISION_KEYS = {
    "scientific_classification",
    "eligibility_decision",
    "selected_candidate",
    "production_route",
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def all_dict_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for child in value.values():
            keys.update(all_dict_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(all_dict_keys(child))
    return keys


def http_exchange(status: int = 200) -> dict[str, Any]:
    return {
        "classification": "discovery_evidence",
        "production_deployment_status": "NOT_DEPLOYED",
        "started_at": "2026-09-01T00:00:00Z",
        "finished_at": "2026-09-01T00:00:01Z",
        "request": {"method": "POST", "url": "https://example.invalid"},
        "response": {"body_file": "response.json", "body_sha256": "abc"},
        "curl": {"exit_code": 0, "metrics": {"http_code": status}},
    }


def test_plan_is_bounded_and_non_production() -> None:
    plan = load_and_validate_plan(PLAN_PATH)

    assert plan["classification"] == "NON_PRODUCTION_OUTPUT_AUDIT"
    assert plan["production_deployment_status"] == "NOT_DEPLOYED"
    assert plan["audit_limits"]["rcsb_max_pages_per_query"] == 20
    assert plan["audit_limits"]["note"].endswith("not approved S-07 production limits.")
    assert not (FORBIDDEN_DECISION_KEYS & all_dict_keys(plan))


def test_curl_metrics_use_compact_line_format_safe_for_windows_paths() -> None:
    metrics = parse_curl_metrics(
        "http_code=200\nresponse_code=200\nremote_ip=132.249.213.18\n"
        "size_download=87367\ntime_total=2.329376\ncontent_type=application/json"
    )

    assert metrics["http_code"] == 200
    assert metrics["size_download"] == 87367.0
    assert metrics["time_total"] == 2.329376
    assert metrics["content_type"] == "application/json"
    assert "curl_version" not in CURL_WRITE_OUT_FIELDS


def test_plan_validator_rejects_a_production_marker(tmp_path: Path) -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    plan["production_deployment_status"] = "DEPLOYED"
    path = tmp_path / "bad-plan.json"
    write_json(path, plan)

    with pytest.raises(ValueError, match="NOT_DEPLOYED"):
        load_and_validate_plan(path)


def test_rcsb_page_builder_does_not_mutate_the_frozen_template() -> None:
    template = {
        "request_options": {"paginate": {"start": 0, "rows": 100}},
        "request_info": {"query_id": "frozen"},
        "query": {"type": "terminal"},
    }
    original = copy.deepcopy(template)

    result = build_rcsb_page_request(template, start=200, rows=50, query_id="page-3")

    assert template == original
    assert result["request_options"]["paginate"] == {"start": 200, "rows": 50}
    assert result["request_info"]["query_id"] == "page-3"


def test_output_audit_observes_pages_layers_and_byte_duplicates(tmp_path: Path) -> None:
    campaign_root = tmp_path / "p0-s07-m1b-test"
    write_json(
        campaign_root / "campaign.json",
        {
            "campaign_id": "p0-s07-m1b-test",
            "classification": "NON_PRODUCTION_OUTPUT_AUDIT",
            "production_deployment_status": "NOT_DEPLOYED",
            "execution_status": "COMPLETE",
            "started_at": "2026-09-01T00:00:00Z",
            "finished_at": "2026-09-01T00:00:02Z",
            "capture_count": 2,
            "capture_process_failure_count": 0,
        },
    )
    write_json(
        campaign_root / "plan" / "plan.json",
        {
            "plan_id": "test-plan",
            "classification": "NON_PRODUCTION_OUTPUT_AUDIT",
            "production_deployment_status": "NOT_DEPLOYED",
            "rcsb_materialization_probes": [],
            "afdb_queries": [],
            "blast": {"cases": []},
        },
    )
    case_root = campaign_root / "evidence" / "rcsb-search" / "P0-DISC-001"
    pages = [
        (1, 0, ["1AAA_1", "1AAA_2"]),
        (2, 2, ["2BBB_1"]),
    ]
    for page_number, start, identifiers in pages:
        page = case_root / f"page-{page_number:04d}"
        write_json(
            page / "request.body.json",
            {"request_options": {"paginate": {"start": start, "rows": 2}}},
        )
        write_json(
            page / "response.json",
            {
                "total_count": 3,
                "result_set": [{"identifier": identifier} for identifier in identifiers],
            },
        )
        write_json(page / "exchange.json", http_exchange())
    write_json(
        case_root / "pagination-run.json",
        {
            "page_size": 2,
            "page_guard": 5,
            "reported_total_count": 3,
            "returned_result_count": 3,
            "stop_reason": "REPORTED_RESULT_SET_EXHAUSTED",
        },
    )
    first = campaign_root / "evidence" / "duplicate-a.bin"
    second = campaign_root / "evidence" / "duplicate-b.bin"
    first.write_bytes(b"same-content")
    second.write_bytes(b"same-content")

    audit = build_output_audit(campaign_root)
    rcsb_case = audit["rcsb_pagination"]["cases"][0]

    assert rcsb_case["page_count"] == 2
    assert rcsb_case["returned_result_count"] == 3
    assert rcsb_case["unique_polymer_entity_count"] == 3
    assert rcsb_case["unique_entry_count"] == 2
    assert rcsb_case["polymer_entities_sharing_an_entry_count"] == 1
    assert rcsb_case["all_reported_results_captured"] is True
    assert audit["content_duplicates"]["duplicate_group_count"] >= 1
    assert audit["boundary"]["contains_scientific_decisions"] is False
    assert not (FORBIDDEN_DECISION_KEYS & all_dict_keys(audit))
    assert (campaign_root / "reports" / "artifact_inventory.json").is_file()
    assert (campaign_root / "reports" / "report_build_manifest.json").is_file()
    assert (campaign_root / "reports" / "P0_M1B_OUTPUT_AUDIT.md").is_file()


def test_runner_refuses_to_overwrite_an_existing_campaign(tmp_path: Path) -> None:
    campaign_root = tmp_path / "p0-s07-m1b-existing"
    campaign_root.mkdir()
    (campaign_root / "keep.txt").write_text("user evidence", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_campaign(
            workspace=WORKSPACE,
            plan_path=PLAN_PATH,
            campaign_root=campaign_root,
            campaign_id="p0-s07-m1b-existing",
            blast_bin=None,
            blast_db=None,
            skip_network=True,
            skip_blast=True,
        )

    assert (campaign_root / "keep.txt").read_text(encoding="utf-8") == "user evidence"
