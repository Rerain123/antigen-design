from __future__ import annotations

import json
from pathlib import Path


CAMPAIGN_ROOT = (
    Path(__file__).resolve().parents[1]
    / "discovery"
    / "p0"
    / "s07"
    / "p0-s07-discovery-20260901-a"
)
REPORTS = CAMPAIGN_ROOT / "reports"


def load_report(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def test_candidate_manifest_is_discovery_only() -> None:
    manifest = load_report("candidate_structure_manifest.json")

    assert manifest["production_deployment_status"] == "NOT_DEPLOYED"
    assert manifest["policy_status"] == "PROVISIONAL_DISCOVERY_POLICY"
    assert manifest["candidate_count"] == 5
    assert all(not item["selected_for_production"] for item in manifest["candidates"])
    assert {item["classification"] for item in manifest["candidates"]} == {
        "TARGET_MATCH",
        "TARGET_DERIVED",
        "HOMOLOG_TEMPLATE",
    }


def test_sequence_mapping_preserves_alignment_and_coordinate_gaps() -> None:
    report = load_report("sequence_mapping_report.json")
    mappings = {item["candidate_id"]: item for item in report["mappings"]}

    assert mappings["RCSB:1UBQ_1:A"]["coordinate_mapped_target_residue_count"] == 76
    assert mappings["RCSB:6XRE_13:M"]["mapped_but_unobserved_target_ranges"] == [
        {"start": 1, "end": 11},
        {"start": 62, "end": 87},
        {"start": 352, "end": 393},
    ]
    assert mappings["RCSB:5XZC_2:B"]["unaligned_target_ranges"] == [
        {"start": 1, "end": 91},
        {"start": 357, "end": 393},
    ]
    assert mappings["RCSB:6PPV_1:A"]["coordinate_mapped_target_residue_count"] == 69
    assert mappings["AFDB:AF-O15116-F1:v6:A"][
        "coordinate_mapped_target_fraction"
    ] == 1.0


def test_no_exact_target_case_is_not_promoted_to_scientific_no_structure() -> None:
    manifest = load_report("candidate_structure_manifest.json")
    outcomes = {item["case_id"]: item for item in manifest["case_outcomes"]}

    case = outcomes["P0-DISC-005"]
    assert case["outcome"] == "NO_EXACT_TARGET_EVIDENCE_HOMOLOG_USABILITY_UNDECIDED"
    assert case["rcsb_http_status"] == 204
    assert case["afdb_http_status"] == 400
    assert case["blast_top_hit"]["evalue"] == 3.4


def test_blast_discovery_profile_and_result_caps_remain_explicit() -> None:
    report = load_report("blast_dependency_and_results_manifest.json")
    cases = {item["case_id"]: item for item in report["cases"]}

    assert report["profile"]["classification"] == "PROVISIONAL_DISCOVERY_PROFILE"
    assert report["profile"]["production_approved"] is False
    assert report["tool"]["official_md5_matches"] is True
    assert cases["P0-DISC-001"]["result_was_capped"] is True
    assert cases["P0-DISC-002"]["result_was_capped"] is True
    assert cases["P0-DISC-003"]["result_was_capped"] is True
    assert cases["P0-DISC-005"]["result_was_capped"] is False


def test_evidence_inventory_distinguishes_empty_results_and_failures() -> None:
    inventory = load_report("evidence_inventory.json")
    outcomes = inventory["exchange_outcome_counts"]

    assert inventory["exchange_count"] == 57
    assert inventory["file_count"] == 236
    assert outcomes["HTTP_NO_CONTENT"] >= 2
    assert outcomes["HTTP_ERROR_RESPONSE"] >= 1
    assert outcomes["TRANSPORT_FAILURE"] >= 1
    assert outcomes["CLI_FAILURE"] >= 1
    assert outcomes["CLI_SUCCESS"] >= 1
