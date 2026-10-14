"""MCP 2.0 server exposing T-01 v10 contract-compatible mock tools."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from .catalog import SCENARIOS, STEP_TOOLS
from .contracts import (
    ArtifactRef,
    ConfigureRunRequest,
    ExecutionMode,
    RunRecord,
    StepRequest,
    StepResult,
    T01Input,
)
from .engine import MockEngine
from .store import SQLiteStore


def default_db_path() -> Path:
    configured = os.environ.get("T01_MOCK_DB_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "var" / "t01-mock.sqlite3"


def _make_step_tool(engine: MockEngine, tool_name: str):
    def execute_step(
        schema_version: Literal["0.1.0"],
        workflow_version: Literal["T01-v10"],
        run_id: str,
        step_id: str,
        node_id: str,
        attempt: int,
        scope: str,
        execution_mode: ExecutionMode,
        parameters: dict[str, Any],
        input_artifacts: list[ArtifactRef],
        context: dict[str, Any],
        idempotency_key: str,
    ) -> StepResult:
        request = StepRequest(
            schema_version=schema_version,
            workflow_version=workflow_version,
            run_id=run_id,
            step_id=step_id,
            node_id=node_id,
            attempt=attempt,
            scope=scope,
            execution_mode=execution_mode,
            parameters=parameters,
            input_artifacts=input_artifacts,
            context=context,
            idempotency_key=idempotency_key,
        )
        return engine.execute(tool_name, request)

    execute_step.__name__ = tool_name.replace(".", "_").replace("-", "_")
    execute_step.__doc__ = STEP_TOOLS[tool_name].description
    return execute_step


def build_server(db_path: Path | None = None) -> MCPServer:
    store = SQLiteStore(db_path or default_db_path())
    engine = MockEngine(store)
    server = MCPServer(
        name="t01-mock-mcp",
        title="T-01 v10 Mock MCP",
        description=(
            "Contract-first deterministic Mock MCP for Dify workflow debugging. "
            "It performs no scientific computation and accepts execution_mode=mock only."
        ),
        instructions=(
            "Call mock.configure_run or mock.configure_run_from_json first to bind a "
            "run_id to one reviewed scenario. "
            "All scientific-looking values are fixtures marked MOCK_DATA."
        ),
        version="0.1.0",
    )

    for tool_name, spec in STEP_TOOLS.items():
        server.add_tool(
            _make_step_tool(engine, tool_name),
            name=tool_name,
            title=f"{spec.step_id} · {tool_name}",
            description=spec.description,
            structured_output=True,
        )

    def configure_run(
        run_id: str,
        scenario_id: str,
        input: T01Input | None = None,
    ) -> RunRecord:
        """Bind a run_id to one of the 25 reviewed mock scenarios."""

        if scenario_id not in SCENARIOS:
            raise ValueError(f"unknown scenario_id: {scenario_id}")
        return store.configure_run(
            ConfigureRunRequest(run_id=run_id, scenario_id=scenario_id, input=input)
        )

    server.add_tool(
        configure_run,
        name="mock.configure_run",
        title="Configure a deterministic mock run",
        structured_output=True,
    )

    def configure_run_from_json(
        run_id: str,
        scenario_id: str,
        t01_input_json: str,
    ) -> RunRecord:
        """Bind a run from a JSON string supplied by a Dify paragraph input.

        The value may be either a raw T01Input object or the reviewed
        configure_run fixture wrapper.  Parsing and schema validation happen in
        the backend; Dify and the LLM only transport the string.
        """

        if scenario_id not in SCENARIOS:
            raise ValueError(f"unknown scenario_id: {scenario_id}")
        try:
            payload = json.loads(t01_input_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"t01_input_json is not valid JSON: line {exc.lineno}, column {exc.colno}"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError("t01_input_json must decode to a JSON object")

        if "input" in payload:
            fixture_run_id = payload.get("run_id")
            fixture_scenario_id = payload.get("scenario_id")
            if fixture_run_id is not None and fixture_run_id != run_id:
                raise ValueError("run_id does not match the JSON fixture wrapper")
            if fixture_scenario_id is not None and fixture_scenario_id != scenario_id:
                raise ValueError("scenario_id does not match the JSON fixture wrapper")
            payload = payload["input"]
            if not isinstance(payload, dict):
                raise ValueError("fixture input must be a JSON object")

        validated_input = T01Input.model_validate(payload)
        return store.configure_run(
            ConfigureRunRequest(
                run_id=run_id,
                scenario_id=scenario_id,
                input=validated_input,
            )
        )

    server.add_tool(
        configure_run_from_json,
        name="mock.configure_run_from_json",
        title="Configure a deterministic mock run from JSON",
        structured_output=True,
    )

    def get_run(run_id: str) -> dict[str, Any]:
        """Return persistent run state and redacted step/job trace for Dify debugging."""

        return store.export_run_debug(run_id)

    server.add_tool(
        get_run,
        name="mock.get_run",
        title="Inspect mock run state",
        structured_output=True,
    )

    def list_scenarios() -> dict[str, Any]:
        """List the exact scenario IDs required by the reviewed mapping document."""

        return {
            "schema_version": "0.1.0",
            "count": len(SCENARIOS),
            "scenarios": [
                {
                    "scenario_id": scenario_id,
                    "description": description,
                    "expected_path": expected_path,
                }
                for scenario_id, (description, expected_path) in SCENARIOS.items()
            ],
        }

    server.add_tool(
        list_scenarios,
        name="mock.list_scenarios",
        title="List reviewed T-01 mock scenarios",
        structured_output=True,
    )

    def get_job_status(run_id: str, job_id: str) -> StepResult:
        """Advance a deterministic mock job and return current StepResult."""

        return engine.job_status(run_id, job_id)

    server.add_tool(
        get_job_status,
        name="jobs.get_status",
        title="Get mock job status",
        structured_output=True,
    )

    def get_job_result(run_id: str, job_id: str) -> StepResult:
        """Return full result only after a mock job reaches a terminal state."""

        return engine.job_result(run_id, job_id)

    server.add_tool(
        get_job_result,
        name="jobs.get_result",
        title="Get mock job result",
        structured_output=True,
    )

    def cancel_job(run_id: str, job_id: str, reason: str) -> StepResult:
        """Cancel a queued/running mock job; terminal jobs cannot be cancelled again."""

        return engine.cancel_job(run_id, job_id, reason)

    server.add_tool(
        cancel_job,
        name="jobs.cancel",
        title="Cancel mock job",
        structured_output=True,
    )

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="streamable-http",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8101)
    parser.add_argument("--path", default="/mcp")
    parser.add_argument("--db-path", type=Path, default=None)
    args = parser.parse_args()

    server = build_server(args.db_path)
    if args.transport == "stdio":
        server.run("stdio")
    elif args.transport == "sse":
        server.run("sse", host=args.host, port=args.port)
    else:
        server.run(
            "streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path=args.path,
            json_response=True,
        )


if __name__ == "__main__":
    main()
