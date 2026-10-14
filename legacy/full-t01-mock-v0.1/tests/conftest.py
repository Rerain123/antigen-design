from __future__ import annotations

from itertools import count
from pathlib import Path
from typing import Any

import pytest

from t01_mock_mcp.contracts import (
    ConfigureRunRequest,
    StepRequest,
    T01Input,
)
from t01_mock_mcp.engine import MockEngine
from t01_mock_mcp.store import SQLiteStore


_keys = count(1)


def make_input(**overrides: Any) -> T01Input:
    payload: dict[str, Any] = {
        "protein_sequence": "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY",
        "host": "human",
        "pathogen_type": "other",
        "objective": "solubility",
        "epitope_mode": "both",
        "epitope_policy": "reviewed-policy-placeholder",
        "regions_permissions": None,
        "md_validation": False,
        "membrane_design_confirm": False,
        "low_conf_design_confirm": False,
        "context_scores": None,
        "mhc_alleles": ["HLA-A*02:01"],
        "expression_host": None,
        "request_visualization": False,
        "execution_mode": "mock",
        "client_request_id": "test-client-request",
    }
    payload.update(overrides)
    return T01Input.model_validate(payload)


def make_request(
    run_id: str,
    *,
    step_id: str = "TEST",
    node_id: str = "TEST_NODE",
    attempt: int = 1,
    scope: str = "wt",
    execution_mode: str = "mock",
    parameters: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> StepRequest:
    return StepRequest(
        schema_version="0.1.0",
        workflow_version="T01-v10",
        run_id=run_id,
        step_id=step_id,
        node_id=node_id,
        attempt=attempt,
        scope=scope,
        execution_mode=execution_mode,
        parameters=parameters or {},
        input_artifacts=[],
        context=context or {},
        idempotency_key=idempotency_key or f"test-key-{next(_keys)}",
    )


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path / "mock.sqlite3")


@pytest.fixture
def engine(store: SQLiteStore) -> MockEngine:
    return MockEngine(store)


@pytest.fixture
def configure(store: SQLiteStore):
    def _configure(
        scenario_id: str,
        *,
        run_id: str | None = None,
        input_value: T01Input | None = None,
    ) -> str:
        selected_run_id = run_id or f"run-{next(_keys)}"
        store.configure_run(
            ConfigureRunRequest(
                run_id=selected_run_id,
                scenario_id=scenario_id,
                input=input_value or make_input(),
            )
        )
        return selected_run_id

    return _configure

