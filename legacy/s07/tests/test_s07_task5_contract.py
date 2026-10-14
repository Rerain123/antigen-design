"""Regression guards for S-07's offline contract; no API or runtime deployment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_s07_task5_contract_evidence import (  # noqa: E402
    Builder, build_cases, rejection_cases, storage_checks,
)
from s07_task5_contract import S07Result, digest  # noqa: E402


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    builder = Builder(tmp_path_factory.mktemp("s07-task5"))
    build_cases(builder)
    return builder


def test_saved_results_are_structural_and_cross_field_valid(evidence):
    schema = S07Result.model_json_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for row in evidence.case_rows:
        path = evidence.store.root / row["result_path"]
        data = path.read_bytes()
        saved = json.loads(data)
        validator.validate(saved)
        evidence.store.verify(saved)
        assert digest(data) == evidence.store.refs[row["result_artifact_id"]]["sha256"]
        assert row["result_artifact_id"] not in {ref["artifact_id"] for ref in saved["artifacts"]}


def test_partial_nulls_are_distinct_from_real_chain_ambiguity(evidence):
    partial = evidence.cases["R02"]["candidates"][0]
    mapping = partial["coordinate_mapping"]
    stored = json.loads(evidence.store.read(evidence.store.refs[mapping["per_residue_artifact_id"]]))
    assert partial["alignment"]["query_coverage"] == 1.0
    assert len(stored["input_to_coordinate"]) == 76
    assert [index for index, value in enumerate(stored["input_to_coordinate"], 1) if value is None] == list(range(71, 77))
    ambiguous = evidence.cases["R17"]
    assert {item["auth_asym_id"] for item in ambiguous["candidates"]} == {"K", "L", "M", "N"}
    assert {item["coordinate_mapping"]["mapped_count"] for item in ambiguous["candidates"]} == {200}
    assert ambiguous["status"] == "WAITING_USER"
    assert ambiguous["next_step"] is None
    assert ambiguous["reliability"] == "UNRELIABLE"


def test_frozen_afdb_confidence_and_capped_blast_keep_their_real_meaning(evidence):
    direct = evidence.cases["R03"]
    candidate = direct["candidates"][0]
    assert candidate["alignment"]["query_length"] == 133
    assert candidate["method"] is None
    assert candidate["resolution_angstrom"] is None
    assert candidate["quality_assessment"] == "PENDING_S09"
    summary = candidate["raw_confidence_summary"]
    assert summary["metadata_global_metric"] == 89.69
    confidence = json.loads(evidence.store.read(evidence.store.refs[candidate["confidence_artifact_ids"][0]]))
    assert summary["mean_of_saved_residue_scores"] == pytest.approx(sum(confidence["confidenceScore"]) / 133)
    assert summary["pae_shape"] == [133, 133]
    capped = evidence.cases["R16"]
    blast = next(item for item in capped["source_runs"] if item["operation"] == "BLAST_UNIPROT")
    assert (blast["returned_count"], blast["complete"], blast["capped"]) == (100, False, True)
    assert blast["parameters"]["database"] == "uniprotkb_swissprot"
    assert capped["retrieval_outcome"] is None
    assert capped["next_step"] is None


def test_no_hit_metadata_failure_and_cancellation_have_separate_routes(evidence):
    empty = evidence.cases["R05"]
    assert empty["next_step"] == "S-08"
    afdb = next(item for item in empty["source_runs"] if item["operation"] == "AFDB_LOOKUP")
    assert (afdb["status"], afdb["reason_code"], afdb["complete"]) == ("NOT_RUN", "NO_VERIFIED_IDENTIFIER", False)
    fallback = evidence.cases["R11"]
    assert (fallback["status"], fallback["next_step"], fallback["reliability"]) == ("DEGRADED", "S-09", "UNRELIABLE")
    assert fallback["requires_review"]
    assert any(item["status"] == "FAILED" for item in fallback["source_runs"])
    for name in ("R12", "R15", "R19"):
        assert evidence.cases[name]["next_step"] is None
        assert evidence.cases[name]["retrieval_outcome"] is None
    assert evidence.cases["R15"]["error"]["category"] == "CANCELLED"


@pytest.mark.parametrize("number", range(1, 21), ids=lambda n: f"invalid-state-{n:02d}")
def test_invalid_states_do_not_pass_contract_validation(evidence, number):
    bad = next(value for key, value in rejection_cases(evidence).items() if key.startswith(f"N{number:02d}_"))
    with pytest.raises(ValidationError):
        S07Result.model_validate(bad)


def test_real_storage_recovery_guards(evidence):
    checks = storage_checks(evidence)
    assert len(checks) == 7
    assert all(item["passed"] for item in checks)
