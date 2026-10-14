from __future__ import annotations

from copy import deepcopy

import pytest

from t01_phase1_mock import FixtureRepository
from t01_phase1_mock.constants import EDGE_IDS, NODE_IDS
from t01_phase1_mock.catalog import validate_instance
from t01_phase1_mock.jsonio import (
    ContractError,
    DuplicateJsonKeyError,
    load_json,
)
from t01_phase1_mock.paths import MATERIALIZATION_PATH, resolve_project_relative


def test_frozen_specification_counts(spec_bundle) -> None:
    assert len(spec_bundle.scenarios) == 21
    assert tuple(spec_bundle.responsibility_by_node) == NODE_IDS
    assert len(spec_bundle.declared_attempt_fixture_keys) == 326
    assert spec_bundle.null_attempt_fixture_count == 8
    assert len(spec_bundle.fixture_manifest["request_variants"]) == 22
    assert sum(len(item["submission_plan"]) for item in spec_bundle.scenarios) == 23
    assert set(edge for item in spec_bundle.scenarios for edge in item["edge_plan"]) == set(EDGE_IDS)
    assert len(spec_bundle.envelope_examples) == 4
    assert len(spec_bundle.source_sha256) == 21
    assert len(spec_bundle.acceptance_catalog["global_assertions"]) == 18
    assert len(spec_bundle.acceptance_catalog["operator_contract"]) == 28
    assert len(spec_bundle.acceptance_catalog["coverage_gates"]) == 10


def test_unknown_scenario_is_rejected(spec_bundle) -> None:
    with pytest.raises(ContractError, match="unknown scenario_ref"):
        spec_bundle.scenario_for_ref("t01_phase1_mock_v01.scenario.not_declared")


def test_tool_registry_is_exactly_26(spec_bundle) -> None:
    tools = spec_bundle.asset_registry["tool_namespace"]["tools"]
    assert len(tools) == 26
    assert len({item["tool_id"] for item in tools}) == 26
    assert [item["node_id"] for item in tools if item["tool_role"] == "NODE_STUB"] == list(NODE_IDS)
    assert sum(item["tool_role"] == "CONTROL_LITERAL" for item in tools) == 6


def test_materialization_is_separate_from_frozen_m1_manifest(
    spec_bundle, fixture_repository
) -> None:
    assert spec_bundle.fixture_manifest["implementation_state"] == "SPEC_ONLY_PAYLOADS_NOT_MATERIALIZED"
    assert fixture_repository.materialization["materialization_state"] == "MATERIALIZED_AND_VERIFIED"
    assert fixture_repository.materialization["implementation_milestone"] == "PH1-MOCK-M2"
    assert MATERIALIZATION_PATH.is_file()


def test_materialized_closed_set_and_hashes(fixture_repository) -> None:
    assert fixture_repository.verify() == {
        "input_fixture_count": 2,
        "request_variant_count": 22,
        "attempt_fixture_count": 326,
        "payload_file_count": 350,
    }
    assert (
        fixture_repository.materialization["source_sha256"]
        == fixture_repository.bundle.source_sha256
    )
    assert all(
        entry["data_classification"] == "MOCK_DATA"
        and entry["scientific_compute"] is False
        for entry in fixture_repository.materialization["files"]
    )


def test_materialization_unknown_logical_key_fails_closed(spec_bundle) -> None:
    repository = FixtureRepository(spec_bundle)
    repository.materialization = deepcopy(repository.materialization)
    repository.materialization["files"][0]["logical_key"] = "undeclared.fixture"
    repository._entry_by_key = {
        item["logical_key"]: item for item in repository.materialization["files"]
    }
    with pytest.raises(ContractError, match="closed set mismatch"):
        repository.verify()


def test_materialization_hash_drift_fails_closed(spec_bundle) -> None:
    repository = FixtureRepository(spec_bundle)
    repository.materialization = deepcopy(repository.materialization)
    repository.materialization["files"][0]["sha256"] = "0" * 64
    repository._entry_by_key = {
        item["logical_key"]: item for item in repository.materialization["files"]
    }
    with pytest.raises(ContractError, match="fixture hash mismatch"):
        repository.verify()


def test_frozen_source_hash_drift_fails_closed(spec_bundle) -> None:
    repository = FixtureRepository(spec_bundle)
    repository.materialization = deepcopy(repository.materialization)
    first_source = next(iter(repository.materialization["source_sha256"]))
    repository.materialization["source_sha256"][first_source] = "0" * 64
    with pytest.raises(ContractError, match="frozen M1 source hash changed"):
        repository.verify()


def test_synthetic_input_payloads_are_transport_only(fixture_repository) -> None:
    standard = fixture_repository.load_input("input.synthetic.standard")
    no_structure = fixture_repository.load_input("input.synthetic.no_structure")
    assert standard["synthetic_input_only"] is True
    assert standard["scientific_compute"] is False
    assert standard["structure"] is not None
    assert standard["structure"]["artifact"]["metadata"]["scientific_coordinates_present"] is False
    assert "NO SCIENTIFIC COORDINATES" in standard["synthetic_structure_payload"]
    assert no_structure["structure"] is None
    assert no_structure["synthetic_structure_payload"] is None
    assert standard["protein_sequence"] == no_structure["protein_sequence"]


def test_changed_request_variant_has_only_frozen_mutation(fixture_repository) -> None:
    base = fixture_repository.load_request_variant("idempotency_conflict.request.base")
    changed = fixture_repository.load_request_variant("idempotency_conflict.request.changed")
    for key in base:
        if key in {"request_id", "envelope_id", "audit", "options", "created_at"}:
            continue
        assert base[key] == changed[key]
    assert base["options"]["design_objective"] == "general"
    assert changed["options"]["design_objective"] == "solubility"
    assert base["options"]["expression_host"] == changed["options"]["expression_host"]


def test_all_attempt_payloads_obey_node_responsibility(
    spec_bundle, fixture_repository
) -> None:
    for key in spec_bundle.declared_attempt_fixture_keys:
        stub = fixture_repository.load_attempt_stub(key)
        responsibility = spec_bundle.responsibility_by_node[stub["node_id"]]
        assert stub["mock_output_key"] == responsibility["mock_output_key"]
        assert set(stub["emitted_fact_kinds"]) <= set(responsibility["emitted_fact_kinds"])
        assert stub["scientific_claims"] == []
        assert stub["scientific_compute"] is False


def test_matching_but_undeclared_attempt_key_fails_closed(fixture_repository) -> None:
    with pytest.raises(ContractError, match="undeclared attempt fixture key"):
        fixture_repository.resolve_attempt_fixture_path(
            "happy_provided_structure.n01.attempt_99"
        )


def test_strict_json_loader_rejects_duplicate_keys(tmp_path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"key": 1, "key": 2}', encoding="utf-8")
    with pytest.raises(DuplicateJsonKeyError, match="duplicate JSON key"):
        load_json(duplicate)


def test_project_relative_path_rejects_escape_and_legacy() -> None:
    with pytest.raises(ContractError, match="unsafe project-relative path"):
        resolve_project_relative("../outside.json")
    with pytest.raises(ContractError, match="enters legacy"):
        resolve_project_relative("legacy/full-t01-mock-v0.1/README.md")


def test_invalid_envelope_example_fails_schema(spec_bundle) -> None:
    invalid = dict(spec_bundle.envelope_examples[0])
    invalid.pop("contract_version")
    with pytest.raises(ContractError, match="fails JSON Schema"):
        validate_instance(invalid, spec_bundle.envelope_schema, "invalid example")


def test_unknown_scenario_catalog_version_fails_preflight(spec_bundle) -> None:
    invalid = deepcopy(spec_bundle.scenario_catalog)
    invalid["scenario_catalog_version"] = "T01-PHASE1-MOCK-SCENARIO-CATALOG-v9.9"
    with pytest.raises(ContractError, match="fails JSON Schema"):
        validate_instance(invalid, spec_bundle.scenario_schema, "invalid scenario version")
