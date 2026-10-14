from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from t01_mock_mcp.contracts import (
    ArtifactRef,
    ExecutionMetrics,
    Progress,
    Provenance,
    StepResult,
)

from conftest import make_input


def test_t01_input_normalizes_sequence_case() -> None:
    value = make_input(protein_sequence="acdefghik")
    assert value.protein_sequence == "ACDEFGHIK"


@pytest.mark.parametrize("sequence", ["ACD E", " CDEF", "ACD1"])
def test_t01_input_rejects_non_letter_sequence(sequence: str) -> None:
    with pytest.raises(ValidationError):
        make_input(protein_sequence=sequence)


@pytest.mark.parametrize(
    "logical_name,resource_uri",
    [
        ("C:\\data\\result.json", None),
        ("result.json", "file:///data/result.json"),
        ("result.json", "/data/result.json"),
    ],
)
def test_artifact_ref_rejects_server_path_leaks(
    logical_name: str, resource_uri: str | None
) -> None:
    with pytest.raises(ValidationError):
        ArtifactRef(
            artifact_id="a1",
            logical_name=logical_name,
            artifact_type="json",
            media_type="application/json",
            sha256="a" * 64,
            size_bytes=1,
            producer_step_id="S-01",
            created_at=datetime.now(UTC),
            resource_uri=resource_uri,
        )


def _base_step_result() -> dict:
    now = datetime.now(UTC)
    return {
        "schema_version": "0.1.0",
        "workflow_version": "T01-v10",
        "run_id": "r1",
        "step_id": "S-01",
        "node_id": "N1",
        "attempt": 1,
        "job_id": None,
        "status": "SUCCEEDED",
        "progress": None,
        "data": {},
        "artifacts": [],
        "quality_flags": [],
        "warnings": [],
        "error": None,
        "provenance": Provenance(
            adapter_name="mock",
            adapter_version="0.1.0",
            tool_name="x",
            tool_version="mock",
            model_name=None,
            model_version=None,
            parameter_profile="test",
            parameters={},
            random_seed=0,
            input_hashes=[],
            started_at=now,
            finished_at=now,
            exit_code=0,
            compute_profile="test",
        ),
        "metrics": ExecutionMetrics(duration_ms=0, resource_summary={}),
    }


def test_queued_result_requires_job_and_progress() -> None:
    value = _base_step_result()
    value["status"] = "QUEUED"
    with pytest.raises(ValidationError):
        StepResult.model_validate(value)


def test_terminal_result_rejects_progress() -> None:
    value = _base_step_result()
    value["progress"] = Progress(current=1, total=2, message="still running")
    with pytest.raises(ValidationError):
        StepResult.model_validate(value)

