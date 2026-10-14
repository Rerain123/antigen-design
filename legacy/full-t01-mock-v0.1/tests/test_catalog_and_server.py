from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from t01_mock_mcp.catalog import CONTROL_TOOLS, JOB_TOOLS, SCENARIOS, STEP_TOOLS
from t01_mock_mcp.server import build_server

from conftest import make_input


EXPECTED_SCENARIOS = {
    "MOCK-HAPPY-PATH",
    "MOCK-SHORT-MHC-HALT",
    "MOCK-SHORT-WARNING",
    "MOCK-CONTEXT-HIGH",
    "MOCK-CONTEXT-NONHIGH",
    "MOCK-NO-STRUCTURE",
    "MOCK-LOW-STRUCTURE",
    "MOCK-BACTERIA",
    "MOCK-MEMBRANE-SKIP",
    "MOCK-MEMBRANE-CONFIRMED",
    "MOCK-POOR-RESCUE-SUCCESS",
    "MOCK-POOR-RESCUE-FAIL",
    "MOCK-DESIGN-RETRY-48",
    "MOCK-DESIGN-RETRY-64",
    "MOCK-DESIGN-ALL-REJECTED",
    "MOCK-EPITOPE-STRUCTURAL-FAIL",
    "MOCK-EPITOPE-PREDICTION-FAIL",
    "MOCK-VARIANT-SAFETY-FAIL",
    "MOCK-19B-SKIPPED",
    "MOCK-SC10-WARNING",
    "MOCK-MD-RUN",
    "MOCK-MD-SKIP",
    "MOCK-TOOL-TIMEOUT",
    "MOCK-OUTPUT-MISSING",
    "MOCK-OUTPUT-INVALID",
}


def test_scenario_catalog_matches_reviewed_contract() -> None:
    assert set(SCENARIOS) == EXPECTED_SCENARIOS
    assert len(SCENARIOS) == 25


def test_tool_catalog_matches_section_6_mapping_document() -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "工作流设计"
        / "02-数据契约"
        / "T01_Dify节点-MCP工具映射与数据契约_v0.1.md"
    )
    text = contract_path.read_text(encoding="utf-8")
    section = text.split("## 6. Dify 节点—MCP 工具映射", 1)[1].split(
        "## 7. 关键门控与分支矩阵", 1
    )[0]
    dotted_identifiers = set(
        re.findall(
            r"(?<![A-Za-z0-9_])[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+(?![A-Za-z0-9_])",
            section,
        )
    )
    # This is a documented field reference, not a tool name.
    dotted_identifiers.discard("best.overall")
    assert dotted_identifiers == set(STEP_TOOLS)


def test_mcp_catalog_contains_all_step_job_and_control_tools(tmp_path: Path) -> None:
    server = build_server(tmp_path / "server.sqlite3")
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == set(STEP_TOOLS) | JOB_TOOLS | CONTROL_TOOLS
    assert len(names) == 63


def test_step_tool_has_flat_unified_request_schema(tmp_path: Path) -> None:
    server = build_server(tmp_path / "server.sqlite3")
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    schema = tools["structure.fetch"].input_schema
    assert set(schema["required"]) == {
        "schema_version",
        "workflow_version",
        "run_id",
        "step_id",
        "node_id",
        "attempt",
        "scope",
        "execution_mode",
        "parameters",
        "input_artifacts",
        "context",
        "idempotency_key",
    }
    assert "request" not in schema["properties"]


def test_mcp_call_returns_structured_step_result(tmp_path: Path) -> None:
    server = build_server(tmp_path / "server.sqlite3")
    configured = asyncio.run(
        server.call_tool(
            "mock.configure_run",
            {
                "run_id": "mcp-run",
                "scenario_id": "MOCK-HAPPY-PATH",
                "input": make_input().model_dump(mode="json"),
            },
        )
    )
    assert configured.is_error is False
    result = asyncio.run(
        server.call_tool(
            "t01.evaluate_length_guard",
            {
                "schema_version": "0.1.0",
                "workflow_version": "T01-v10",
                "run_id": "mcp-run",
                "step_id": "G-LENGTH",
                "node_id": "T01_G00_LENGTH",
                "attempt": 1,
                "scope": "wt",
                "execution_mode": "mock",
                "parameters": {},
                "input_artifacts": [],
                "context": {},
                "idempotency_key": "mcp-call-1",
            },
        )
    )
    assert result.is_error is False
    assert result.structured_content["status"] == "SUCCEEDED"
    assert result.structured_content["data"]["route"] == "PASS"
    assert result.structured_content["provenance"]["compute_profile"] == "mock-no-scientific-compute"


def test_dify_json_control_tool_accepts_reviewed_fixture_wrapper(tmp_path: Path) -> None:
    server = build_server(tmp_path / "server.sqlite3")
    payload = {
        "run_id": "dify-json-run",
        "scenario_id": "MOCK-HAPPY-PATH",
        "input": make_input(client_request_id="dify-json-run").model_dump(mode="json"),
    }
    configured = asyncio.run(
        server.call_tool(
            "mock.configure_run_from_json",
            {
                "run_id": "dify-json-run",
                "scenario_id": "MOCK-HAPPY-PATH",
                "t01_input_json": json.dumps(payload),
            },
        )
    )
    assert configured.is_error is False
    assert configured.structured_content["run_id"] == "dify-json-run"
    assert configured.structured_content["input"]["execution_mode"] == "mock"
