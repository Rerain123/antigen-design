from __future__ import annotations

import pytest

from t01_mock_mcp.contracts import ConfigureRunRequest, ErrorCategory, StepStatus
from t01_mock_mcp.store import RunConfigurationConflict

from conftest import make_input, make_request


def test_idempotent_replay_returns_exact_prior_result(engine, configure) -> None:
    run_id = configure("MOCK-HAPPY-PATH")
    request = make_request(run_id, idempotency_key="same-key")
    first = engine.execute("structure.fetch", request)
    second = engine.execute("structure.fetch", request)
    assert first == second


def test_idempotency_key_conflict_is_stable_error(engine, configure) -> None:
    run_id = configure("MOCK-HAPPY-PATH")
    first = make_request(run_id, idempotency_key="conflict-key", parameters={"a": 1})
    second = make_request(run_id, idempotency_key="conflict-key", parameters={"a": 2})
    assert engine.execute("structure.fetch", first).status == StepStatus.SUCCEEDED
    conflict = engine.execute("structure.fetch", second)
    assert conflict.status == StepStatus.FAILED
    assert conflict.error.code == "IDEMPOTENCY_KEY_CONFLICT"


def test_executed_run_cannot_be_rebound_to_another_scenario(engine, store, configure) -> None:
    run_id = configure("MOCK-HAPPY-PATH", run_id="immutable-run")
    engine.execute("structure.fetch", make_request(run_id))
    with pytest.raises(RunConfigurationConflict):
        store.configure_run(
            ConfigureRunRequest(
                run_id=run_id,
                scenario_id="MOCK-NO-STRUCTURE",
                input=make_input(),
            )
        )


def test_mock_async_job_lifecycle(engine, configure) -> None:
    run_id = configure("MOCK-HAPPY-PATH")
    queued = engine.execute(
        "structure.predict",
        make_request(run_id, parameters={"_mock_async": True}),
    )
    assert queued.status == StepStatus.QUEUED
    assert queued.job_id
    assert queued.artifacts == []

    running = engine.job_status(run_id, queued.job_id)
    assert running.status == StepStatus.RUNNING
    assert running.artifacts == []

    not_ready = engine.job_result(run_id, queued.job_id)
    assert not_ready.status == StepStatus.RUNNING
    assert not_ready.artifacts == []

    complete = engine.job_status(run_id, queued.job_id)
    assert complete.status == StepStatus.SUCCEEDED
    assert complete.artifacts
    full = engine.job_result(run_id, queued.job_id)
    assert full == complete


def test_cancel_active_job_and_reject_repeat_cancel(engine, configure) -> None:
    run_id = configure("MOCK-HAPPY-PATH")
    queued = engine.execute(
        "structure.predict",
        make_request(run_id, parameters={"_mock_async": True}),
    )
    cancelled = engine.cancel_job(run_id, queued.job_id, "test cancellation")
    assert cancelled.status == StepStatus.CANCELLED
    assert cancelled.error.category == ErrorCategory.CANCELLED

    repeated = engine.cancel_job(run_id, queued.job_id, "again")
    assert repeated.status == StepStatus.FAILED
    assert repeated.error.code == "JOB_ALREADY_TERMINAL"
