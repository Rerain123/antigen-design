from __future__ import annotations

from t01_phase1_mock.jsonio import load_json
from t01_phase1_mock.paths import M3_TARGET_PREFLIGHT_PATH


def test_local_dify_target_and_provider_are_frozen(spec_bundle) -> None:
    evidence = load_json(M3_TARGET_PREFLIGHT_PATH)
    target = evidence["target"]
    provider = evidence["provider"]
    expected_tools = [
        item["tool_id"] for item in spec_bundle.asset_registry["tool_namespace"]["tools"]
    ]
    assert evidence["result"] == "PASS"
    assert target == {
        **target,
        "environment": "LOCAL_DIFY_DOCKER",
        "dify_version": "1.17.0",
        "dsl_version": "0.7.0",
        "deployment": "docker-compose",
        "instance_scope": "localhost-only",
    }
    assert provider["server_identifier"] == "t01-phase1-mock-mcp-v01"
    assert provider["workflow_provider_id"] == provider["server_identifier"]
    assert provider["protocol"] == "MCP_STREAMABLE_HTTP"
    assert provider["protocol_version"] == "2025-06-18"
    assert provider["reachable"] is True
    assert provider["tool_ids"] == expected_tools
    assert provider["tool_count"] == 26


def test_target_evidence_records_same_instance_reference_and_scope_guards() -> None:
    evidence = load_json(M3_TARGET_PREFLIGHT_PATH)
    reference = evidence["same_instance_reference_export"]
    assert reference["app_name"] == "T01_Master_v10"
    assert len(reference["sha256"]) == 64
    assert set(reference["node_types"]) == {
        "start",
        "tool",
        "if-else",
        "variable-aggregator",
        "end",
    }
    assert reference["contains_secret"] is False
    assert evidence["scope_guards"] == {
        "himat_backend_accessed": False,
        "scientific_network_calls": 0,
        "scientific_compute": False,
    }

