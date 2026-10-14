from __future__ import annotations

from t01_phase1_mock.constants import EDGE_IDS
from t01_phase1_mock.jsonio import load_json
from t01_phase1_mock.paths import M3_IMPORT_EVIDENCE_PATH


def test_local_dify_import_and_readback_evidence_is_complete(spec_bundle) -> None:
    evidence = load_json(M3_IMPORT_EVIDENCE_PATH)
    expected_tools = [
        item["tool_id"] for item in spec_bundle.asset_registry["tool_namespace"]["tools"]
    ]
    assert evidence["result"] == "PASS"
    assert evidence["blocker_count"] == evidence["secret_finding_count"] == 0
    assert evidence["provider"]["authed"] is True
    assert evidence["provider"]["tool_ids"] == expected_tools
    assert evidence["provider"]["tool_count"] == 26
    assert len(evidence["applications"]) == 2
    for app in evidence["applications"]:
        assert app["import_status"] == "completed"
        assert app["warning_count"] == 0
        assert app["node_count"] == 59
        assert app["edge_count"] == 79
        assert app["semantic_edge_ids"] == list(EDGE_IDS)
        assert app["source_semantic_graph_sha256"] == app["readback_semantic_graph_sha256"]
        assert app["tool_ids"] == expected_tools


def test_import_evidence_keeps_instance_and_canonical_ids_separate() -> None:
    evidence = load_json(M3_IMPORT_EVIDENCE_PATH)
    by_role = {item["role"]: item for item in evidence["applications"]}
    assert by_role["PRIMARY"]["stable_workflow_id"] == "t01_phase1_mock_v01.workflow.main"
    assert by_role["DEBUG"]["stable_workflow_id"] == "t01_phase1_mock_v01.workflow.debug"
    assert by_role["PRIMARY"]["app_id"] != by_role["DEBUG"]["app_id"]
    assert by_role["PRIMARY"]["draft_workflow_id"] != by_role["DEBUG"]["draft_workflow_id"]

