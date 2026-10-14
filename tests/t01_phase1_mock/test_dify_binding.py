from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from t01_phase1_mock.dify.binding import bind_documents, binding_schema, validate_manifest
from t01_phase1_mock.jsonio import ContractError, load_json, sha256_bytes
from t01_phase1_mock.paths import BINDING_ROOT, M3_BINDING_EVIDENCE_PATH


MANIFEST_PATH = BINDING_ROOT / "provider-bindings.local_dify_1_17.json"
SCHEMA_PATH = BINDING_ROOT / "T01_PHASE1_MOCK_PROVIDER_BINDING_SCHEMA_v0.1.json"


def test_binding_manifest_and_stored_schema_are_valid(spec_bundle) -> None:
    manifest = load_json(MANIFEST_PATH)
    stored_schema = load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(stored_schema)
    Draft202012Validator(stored_schema).validate(manifest)
    Draft202012Validator(binding_schema()).validate(manifest)
    validate_manifest(manifest, spec_bundle)


def test_bound_workflows_are_exact_deterministic_derivatives() -> None:
    manifest = load_json(MANIFEST_PATH)
    items = bind_documents(manifest)
    assert {item.role for item in items} == {"PRIMARY", "DEBUG"}
    for item in items:
        assert item.path.read_bytes() == item.content
        assert item.sha256 == sha256_bytes(item.content)
        text = item.content.decode("utf-8")
        assert "__T01_" not in text
        assert "t01-phase1-mock-mcp-v01" in text


def test_binding_hash_chain_matches_evidence() -> None:
    manifest = load_json(MANIFEST_PATH)
    evidence = load_json(M3_BINDING_EVIDENCE_PATH)
    assert evidence["result"] == "PASS"
    assert evidence["binding_manifest_sha256"] == sha256_bytes(MANIFEST_PATH.read_bytes())
    assert evidence["registry_sha256"] == manifest["registry_sha256"]
    for item in bind_documents(manifest):
        assert evidence["bound_sha256"][item.role] == item.sha256


def test_binding_fails_closed_on_profile_or_hash_drift() -> None:
    manifest = load_json(MANIFEST_PATH)
    bad_profile = deepcopy(manifest)
    bad_profile["binding_profile"] = "legacy"
    with pytest.raises(ContractError):
        validate_manifest(bad_profile)
    bad_hash = deepcopy(manifest)
    bad_hash["template_sha256"]["PRIMARY"] = "0" * 64
    with pytest.raises(ContractError):
        bind_documents(bad_hash)

