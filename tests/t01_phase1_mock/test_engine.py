from __future__ import annotations

import pytest

from t01_phase1_mock import MockBackend, MockToolFacade
from t01_phase1_mock.jsonio import ContractError
from t01_phase1_mock.storage import FilesystemRunStore


def test_idempotent_replay_reuses_run_without_reemission(
    spec_bundle, fixture_repository
) -> None:
    backend = MockBackend(bundle=spec_bundle, fixtures=fixture_repository)
    first_request = fixture_repository.instantiate_submission_request(
        "idempotent_replay", "submit_1"
    )
    second_request = fixture_repository.instantiate_submission_request(
        "idempotent_replay", "submit_2"
    )
    first = backend.submit(first_request)
    before = backend.run_hash(first.run_id)
    second = backend.submit(second_request)
    assert first.action == "CREATE_RUN"
    assert second.action == "RETURN_EXISTING_RUN"
    assert second.run_id == first.run_id
    assert first_request["request_id"] != second_request["request_id"]
    assert backend.run_hash(first.run_id) == before
    assert backend.get_run_metadata(first.run_id)["control_emission_count"] == 1
    assert backend.run_count() == 1


def test_idempotency_conflict_is_rejected_before_new_run(
    spec_bundle, fixture_repository
) -> None:
    backend = MockBackend(bundle=spec_bundle, fixtures=fixture_repository)
    first = backend.submit(
        fixture_repository.instantiate_submission_request(
            "idempotency_conflict", "submit_1"
        )
    )
    before = backend.run_hash(first.run_id)
    second = backend.submit(
        fixture_repository.instantiate_submission_request(
            "idempotency_conflict", "submit_2"
        )
    )
    assert second.action == "REJECT_REQUEST"
    assert second.error_code == "REQUEST_IDEMPOTENCY_CONFLICT"
    assert second.run_id is None
    assert backend.run_count() == 1
    assert backend.run_hash(first.run_id) == before


def test_unknown_scenario_never_falls_back_to_happy_path(
    spec_bundle, fixture_repository
) -> None:
    backend = MockBackend(bundle=spec_bundle, fixtures=fixture_repository)
    request = fixture_repository.instantiate_submission_request(
        "happy_provided_structure", "submit_1"
    )
    request["scenario_ref"] = "t01_phase1_mock_v01.scenario.not_declared"
    result = backend.submit(request)
    assert result.action == "REJECT_REQUEST"
    assert result.error_code == "REQUEST_SCHEMA_INVALID"
    assert backend.run_count() == 0


def test_fingerprint_mismatch_is_rejected(spec_bundle, fixture_repository) -> None:
    backend = MockBackend(bundle=spec_bundle, fixtures=fixture_repository)
    request = fixture_repository.instantiate_submission_request(
        "happy_provided_structure", "submit_1"
    )
    request["input_fingerprints"]["protein_sequence_sha256"] = "0" * 64
    result = backend.submit(request)
    assert result.action == "REJECT_REQUEST"
    assert result.error_code == "REQUEST_SCHEMA_INVALID"
    assert backend.run_count() == 0


def test_checkpoint_cannot_advance_with_wrong_action(
    spec_bundle, fixture_repository
) -> None:
    backend = MockBackend(bundle=spec_bundle, fixtures=fixture_repository)
    result = backend.submit(
        fixture_repository.instantiate_submission_request(
            "n16_branch_timeout_partial", "submit_1"
        )
    )
    with pytest.raises(ContractError, match="not awaiting a scenario event"):
        backend.inject_scenario_event(result.run_id, "N16_TIMEOUT")
    assert backend.get_run_metadata(result.run_id)["checkpoint_index"] == 1


def test_cancel_is_acknowledged_then_reaches_terminal_on_explicit_poll(
    spec_bundle, fixture_repository
) -> None:
    backend = MockBackend(bundle=spec_bundle, fixtures=fixture_repository)
    created = backend.submit(
        fixture_repository.instantiate_submission_request(
            "run_cancelled_before_join", "submit_1"
        )
    )
    backend.poll_run(created.run_id)
    acknowledged = backend.cancel_run(created.run_id)
    assert acknowledged["run_status"] == "RUNNING"
    assert backend.get_run_metadata(created.run_id)["terminal"] is False
    with pytest.raises(ContractError, match="checkpoint action mismatch"):
        backend.cancel_run(created.run_id)
    cancelled = backend.poll_run(created.run_id)
    assert cancelled["run_status"] == "CANCELLED"
    assert backend.get_run_metadata(created.run_id)["terminal"] is True
    assert backend.poll_run(created.run_id) == cancelled


def test_timeout_requires_literal_injection(spec_bundle, fixture_repository) -> None:
    backend = MockBackend(bundle=spec_bundle, fixtures=fixture_repository)
    result = backend.submit(
        fixture_repository.instantiate_submission_request(
            "n08_upstream_timed_out", "submit_1"
        )
    )
    active = backend.poll_run(result.run_id)
    assert next(item for item in active["node_results"] if item["node_id"] == "N08")["status"] == "RUNNING"
    with pytest.raises(ContractError, match="scenario event mismatch"):
        backend.inject_scenario_event(result.run_id, "SOME_OTHER_TIMEOUT")
    injected = backend.inject_scenario_event(result.run_id, "N08_TIMEOUT")
    assert injected["run_status"] == "RUNNING"
    injected_hash = backend.run_hash(result.run_id)
    injected_index = backend.get_run_metadata(result.run_id)["checkpoint_index"]
    with pytest.raises(ContractError, match="not awaiting a scenario event"):
        backend.inject_scenario_event(result.run_id, "N08_TIMEOUT")
    assert backend.run_hash(result.run_id) == injected_hash
    assert backend.get_run_metadata(result.run_id)["checkpoint_index"] == injected_index
    terminal = backend.poll_run(result.run_id)
    assert terminal["run_status"] == "TIMED_OUT"


def test_local_backend_entry_point_uses_filesystem_state(
    tmp_path, spec_bundle, fixture_repository
) -> None:
    runtime = tmp_path / "local-entry-point"
    backend = MockBackend.local(
        bundle=spec_bundle,
        fixtures=fixture_repository,
        runtime_root=runtime,
    )
    created = backend.submit(
        fixture_repository.instantiate_submission_request(
            "happy_provided_structure", "submit_1"
        )
    )
    assert (runtime / "runs" / created.run_id / "record.json").is_file()
    restarted = MockBackend.local(
        bundle=spec_bundle,
        fixtures=fixture_repository,
        runtime_root=runtime,
    )
    assert restarted.get_run(created.run_id) == created.run


def test_filesystem_store_resumes_checkpoint_after_restart(
    tmp_path, spec_bundle, fixture_repository
) -> None:
    runtime = tmp_path / "t01-phase1-mock-v0.1"
    first_backend = MockBackend(
        bundle=spec_bundle,
        fixtures=fixture_repository,
        store=FilesystemRunStore(runtime),
    )
    submitted = first_backend.submit(
        fixture_repository.instantiate_submission_request(
            "n08_upstream_timed_out", "submit_1"
        )
    )
    second_backend = MockBackend(
        bundle=spec_bundle,
        fixtures=fixture_repository,
        store=FilesystemRunStore(runtime),
    )
    second_backend.poll_run(submitted.run_id)
    second_backend.inject_scenario_event(submitted.run_id, "N08_TIMEOUT")
    third_backend = MockBackend(
        bundle=spec_bundle,
        fixtures=fixture_repository,
        store=FilesystemRunStore(runtime),
    )
    terminal = third_backend.poll_run(submitted.run_id)
    assert terminal["run_status"] == "TIMED_OUT"
    assert third_backend.get_run_metadata(submitted.run_id)["terminal"] is True


def test_filesystem_store_preserves_idempotency_after_restart(
    tmp_path, spec_bundle, fixture_repository
) -> None:
    runtime = tmp_path / "persistent-idempotency"
    backend = MockBackend(
        bundle=spec_bundle,
        fixtures=fixture_repository,
        store=FilesystemRunStore(runtime),
    )
    first = backend.submit(
        fixture_repository.instantiate_submission_request(
            "idempotent_replay", "submit_1"
        )
    )
    restarted = MockBackend(
        bundle=spec_bundle,
        fixtures=fixture_repository,
        store=FilesystemRunStore(runtime),
    )
    second = restarted.submit(
        fixture_repository.instantiate_submission_request(
            "idempotent_replay", "submit_2"
        )
    )
    assert second.action == "RETURN_EXISTING_RUN"
    assert second.run_id == first.run_id
    assert restarted.run_count() == 1


def test_all_26_tool_facade_entries_dispatch(spec_bundle, fixture_repository) -> None:
    backend = MockBackend(bundle=spec_bundle, fixtures=fixture_repository)
    facade = MockToolFacade(backend)
    request = fixture_repository.instantiate_submission_request(
        "happy_provided_structure", "submit_1"
    )
    initialized = facade.call(
        "t01_phase1_mock_v01.tool.run.initialize", request=request
    )
    run_id = initialized["run_id"]
    for tool in spec_bundle.asset_registry["tool_namespace"]["tools"]:
        if tool["tool_role"] == "RUN_INITIALIZER":
            continue
        value = facade.call(tool["tool_id"], run_id=run_id)
        assert value is not None
    assert facade.call("t01_phase1_mock_v01.tool.run.finalize", run_id=run_id)["run_id"] == run_id


def test_backend_resolves_run_artifact_to_verified_fixture_bytes(
    spec_bundle, fixture_repository
) -> None:
    backend = MockBackend(bundle=spec_bundle, fixtures=fixture_repository)
    result = backend.submit(
        fixture_repository.instantiate_submission_request(
            "happy_provided_structure", "submit_1"
        )
    )
    artifact = result.run["node_results"][0]["output"]["artifacts"][0]
    payload = backend.read_artifact(result.run_id, artifact["artifact_id"])
    assert len(payload) == artifact["size_bytes"]
    with pytest.raises(ContractError, match="unknown or ambiguous"):
        backend.read_artifact(result.run_id, "t01_phase1_mock_v01.artifact.unknown")


def test_unknown_tool_fails_closed(spec_bundle, fixture_repository) -> None:
    facade = MockToolFacade(MockBackend(bundle=spec_bundle, fixtures=fixture_repository))
    with pytest.raises(ContractError, match="unknown Phase 1 Mock tool"):
        facade.call("t01_phase1_mock_v01.tool.node.n99", run_id="unused")


def test_tool_call_rejects_cross_scenario_binding(spec_bundle, fixture_repository) -> None:
    backend = MockBackend(bundle=spec_bundle, fixtures=fixture_repository)
    facade = MockToolFacade(backend)
    created = backend.submit(
        fixture_repository.instantiate_submission_request(
            "happy_provided_structure", "submit_1"
        )
    )
    with pytest.raises(ContractError, match="does not match the bound run"):
        facade.call(
            "t01_phase1_mock_v01.tool.node.n01",
            run_id=created.run_id,
            scenario_ref="t01_phase1_mock_v01.scenario.gate_wt_direct",
        )


def test_corrupt_filesystem_run_record_is_rejected(
    tmp_path, spec_bundle, fixture_repository
) -> None:
    runtime = tmp_path / "corrupt-record"
    backend = MockBackend(
        bundle=spec_bundle,
        fixtures=fixture_repository,
        store=FilesystemRunStore(runtime),
    )
    created = backend.submit(
        fixture_repository.instantiate_submission_request(
            "happy_provided_structure", "submit_1"
        )
    )
    record_path = runtime / "runs" / created.run_id / "record.json"
    record_path.write_text('{"record_namespace": "wrong"}', encoding="utf-8")
    with pytest.raises(ContractError, match="namespace mismatch"):
        FilesystemRunStore(runtime).get_record(created.run_id)


def test_corrupt_idempotency_index_is_rejected(tmp_path) -> None:
    runtime = tmp_path / "corrupt-index"
    store = FilesystemRunStore(runtime)
    store.index_path.write_text('{"document_type": "wrong"}', encoding="utf-8")
    with pytest.raises(ContractError, match="invalid idempotency index"):
        store.get_idempotency("any-key")
