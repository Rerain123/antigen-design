from __future__ import annotations

import json

from t01_phase1_mock.dify.transport import MCPApplication, MCP_PROTOCOL_VERSION
from t01_phase1_mock.engine import MockBackend
from t01_phase1_mock.fixtures import FixtureRepository
from t01_phase1_mock.storage import InMemoryRunStore


def _application(spec_bundle, fixture_repository: FixtureRepository) -> MCPApplication:
    return MCPApplication(
        MockBackend(
            bundle=spec_bundle,
            fixtures=fixture_repository,
            store=InMemoryRunStore(),
        )
    )


def test_mcp_initialize_and_exact_26_tool_catalogue(spec_bundle, fixture_repository):
    app = _application(spec_bundle, fixture_repository)
    status, initialized = app.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        }
    )
    assert status == 200
    assert initialized["result"]["protocolVersion"] == MCP_PROTOCOL_VERSION

    status, listed = app.dispatch(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    )
    assert status == 200
    actual = [item["name"] for item in listed["result"]["tools"]]
    assert actual == list(app.facade.tool_ids)
    assert len(actual) == 26
    assert all("outputSchema" in item for item in listed["result"]["tools"])


def test_mcp_calls_initialize_node_control_and_finalize(
    spec_bundle, fixture_repository
):
    app = _application(spec_bundle, fixture_repository)
    request = fixture_repository.instantiate_submission_request(
        "happy_provided_structure", "submit_1"
    )
    _, initialized = app.dispatch(
        {
            "jsonrpc": "2.0",
            "id": "init",
            "method": "tools/call",
            "params": {
                "name": "t01_phase1_mock_v01.tool.run.initialize",
                "arguments": {"request_json": json.dumps(request)},
            },
        }
    )
    output = initialized["result"]["structuredContent"]
    run_id = output["run_id"]
    assert output["action"] == "CREATE_RUN"

    calls = (
        ("t01_phase1_mock_v01.tool.node.n01", "status", "SUCCEEDED"),
        (
            "t01_phase1_mock_v01.tool.control.design_suitability",
            "decision",
            "DESIGN_SUITABLE",
        ),
        ("t01_phase1_mock_v01.tool.run.finalize", "run_status", "COMPLETED"),
    )
    for index, (name, field, expected) in enumerate(calls, start=3):
        status, response = app.dispatch(
            {
                "jsonrpc": "2.0",
                "id": index,
                "method": "tools/call",
                "params": {"name": name, "arguments": {"run_id": run_id}},
            }
        )
        assert status == 200
        assert response["result"]["isError"] is False
        assert response["result"]["structuredContent"][field] == expected


def test_mcp_fails_closed_for_unknown_tool_and_arguments(spec_bundle, fixture_repository):
    app = _application(spec_bundle, fixture_repository)
    _, unknown = app.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "not.registered", "arguments": {}},
        }
    )
    assert unknown["error"]["code"] == -32602

    _, extra = app.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "t01_phase1_mock_v01.tool.run.initialize",
                "arguments": {"request_json": "{}", "secret": "forbidden"},
            },
        }
    )
    assert extra["error"]["code"] == -32602
