"""Minimal Streamable HTTP MCP adapter over the frozen 26-tool facade.

This module deliberately contains transport and serialization concerns only.  All
scenario selection, control literals, node results, and run state continue to come
from :class:`t01_phase1_mock.engine.MockBackend`.
"""

from __future__ import annotations

import argparse
import json
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..engine import MockBackend
from ..jsonio import ContractError
from ..tools import MockToolFacade


MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_SERVER_NAME = "t01-phase1-mock-v01"
MCP_SERVER_VERSION = "0.1.0"
MCP_PATH = "/mcp"
HEALTH_PATH = "/healthz"


_GENERIC_OBJECT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
}


def _string_property(description: str) -> dict[str, str]:
    return {"type": "string", "description": description}


@dataclass(frozen=True)
class ToolCatalogue:
    """Generate MCP tool descriptions directly from the frozen asset registry."""

    facade: MockToolFacade

    def tools(self) -> list[dict[str, Any]]:
        registry_tools = self.facade.backend.bundle.asset_registry["tool_namespace"]["tools"]
        return [self._tool_definition(item) for item in registry_tools]

    @staticmethod
    def _tool_definition(item: dict[str, Any]) -> dict[str, Any]:
        tool_id = item["tool_id"]
        role = item["tool_role"]
        if role == "RUN_INITIALIZER":
            input_schema = {
                "type": "object",
                "properties": {
                    "request_json": _string_property(
                        "Canonical T01 Phase 1 Mock request encoded as UTF-8 JSON."
                    )
                },
                "required": ["request_json"],
                "additionalProperties": False,
            }
            output_schema = {
                "type": "object",
                "properties": {
                    "result": _GENERIC_OBJECT_SCHEMA,
                    "action": _string_property("Submission action."),
                    "request_id": {"type": ["string", "null"]},
                    "run_id": {"type": ["string", "null"]},
                    "run": {"type": ["object", "null"], "additionalProperties": True},
                    "error": {"type": ["object", "null"], "additionalProperties": True},
                    "error_code": {"type": ["string", "null"]},
                },
                "required": ["result", "action", "request_id", "run_id", "run", "error", "error_code"],
                "additionalProperties": False,
            }
            description = "Create or replay one deterministic Phase 1 Mock run."
        else:
            input_schema = {
                "type": "object",
                "properties": {
                    "run_id": _string_property("Canonical backend-issued run identifier."),
                    "scenario_ref": _string_property(
                        "Optional scenario reference; must match the run binding."
                    ),
                },
                "required": ["run_id"],
                "additionalProperties": False,
            }
            properties: dict[str, Any] = {
                "result": _GENERIC_OBJECT_SCHEMA,
                "run_id": {"type": ["string", "null"]},
            }
            if role == "NODE_STUB":
                properties.update(
                    {
                        "node_id": _string_property("Frozen business node ID."),
                        "status": _string_property("Scenario-projected node status."),
                    }
                )
                description = f"Return the deterministic {item['node_id']} node envelope."
            elif role == "CONTROL_LITERAL":
                properties.update(
                    {
                        "state": {"type": ["string", "null"]},
                        "decision": {"type": ["string", "null"]},
                        "decision_1": {"type": ["string", "null"]},
                        "decision_2": {"type": ["string", "null"]},
                        "decision_3": {"type": ["string", "null"]},
                        "mode": {"type": ["string", "null"]},
                    }
                )
                description = (
                    f"Return the frozen {item['control_key']} SCENARIO_LITERAL without inference."
                )
            elif role == "RUN_FINALIZER":
                properties.update(
                    {
                        "run_status": _string_property("Canonical terminal run status."),
                    }
                )
                description = "Return the complete canonical run envelope without modification."
            else:  # pragma: no cover - SpecificationBundle rejects unknown roles first.
                raise ContractError(f"unsupported registered tool role: {role}")
            output_schema = {
                "type": "object",
                "properties": properties,
                "required": ["result", "run_id"],
                "additionalProperties": False,
            }
        return {
            "name": tool_id,
            "title": tool_id,
            "description": description,
            "inputSchema": input_schema,
            "outputSchema": output_schema,
            "annotations": {"readOnlyHint": False, "destructiveHint": False},
        }


class MCPApplication:
    """JSON-RPC dispatcher around one shared backend and facade."""

    def __init__(self, backend: MockBackend | None = None) -> None:
        self.backend = backend or MockBackend.local()
        self.facade = MockToolFacade(self.backend)
        self.catalogue = ToolCatalogue(self.facade)
        self._lock = threading.RLock()

    def dispatch(self, payload: Any) -> tuple[int, dict[str, Any] | None]:
        if not isinstance(payload, dict):
            return HTTPStatus.BAD_REQUEST, self._error(None, -32600, "Invalid Request")
        request_id = payload.get("id")
        if payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str):
            return HTTPStatus.BAD_REQUEST, self._error(request_id, -32600, "Invalid Request")
        method = payload["method"]
        params = payload.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return HTTPStatus.OK, self._error(request_id, -32602, "Invalid params")

        if request_id is None:
            # MCP notifications must not receive a JSON-RPC body.
            if method in {"notifications/initialized", "notifications/cancelled"}:
                return HTTPStatus.ACCEPTED, None
            return HTTPStatus.ACCEPTED, None

        if method == "initialize":
            requested = params.get("protocolVersion")
            supported = {"2024-11-05", "2025-03-26", MCP_PROTOCOL_VERSION}
            negotiated = requested if requested in supported else MCP_PROTOCOL_VERSION
            return HTTPStatus.OK, self._result(
                request_id,
                {
                    "protocolVersion": negotiated,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION},
                    "instructions": (
                        "Offline deterministic Phase 1 Mock only; no scientific computation."
                    ),
                },
            )
        if method == "ping":
            return HTTPStatus.OK, self._result(request_id, {})
        if method == "tools/list":
            return HTTPStatus.OK, self._result(
                request_id, {"tools": self.catalogue.tools()}
            )
        if method == "tools/call":
            return self._call_tool(request_id, params)
        return HTTPStatus.OK, self._error(request_id, -32601, "Method not found")

    def _call_tool(
        self, request_id: str | int, params: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return HTTPStatus.OK, self._error(request_id, -32602, "Invalid params")
        try:
            call_arguments = self._normalize_arguments(name, arguments)
            with self._lock:
                raw = self.facade.call(name, **call_arguments)
            structured = self._structured_output(name, raw)
        except (ContractError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return HTTPStatus.OK, self._error(request_id, -32602, str(exc))
        except Exception as exc:  # pragma: no cover - defensive transport boundary.
            return HTTPStatus.OK, self._error(
                request_id, -32603, f"internal transport error: {type(exc).__name__}"
            )
        text = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return HTTPStatus.OK, self._result(
            request_id,
            {
                "content": [{"type": "text", "text": text}],
                "structuredContent": structured,
                "isError": False,
            },
        )

    def _normalize_arguments(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = next(
            (item for item in self.catalogue.tools() if item["name"] == name), None
        )
        if tool is None:
            raise ContractError(f"unknown Phase 1 Mock tool: {name}")
        allowed = set(tool["inputSchema"]["properties"])
        unknown = set(arguments) - allowed
        if unknown:
            raise ContractError(f"unknown arguments for {name}: {sorted(unknown)}")
        missing = set(tool["inputSchema"].get("required", [])) - set(arguments)
        if missing:
            raise ContractError(f"missing arguments for {name}: {sorted(missing)}")
        if name.endswith("run.initialize"):
            request_json = arguments.get("request_json")
            if not isinstance(request_json, str):
                raise ContractError("request_json must be a string")
            request = json.loads(request_json)
            if not isinstance(request, dict):
                raise ContractError("request_json must encode an object")
            return {"request": request}
        run_id = arguments.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ContractError("run_id must be a non-empty string")
        scenario_ref = arguments.get("scenario_ref")
        if scenario_ref is not None and not isinstance(scenario_ref, str):
            raise ContractError("scenario_ref must be a string")
        result = {"run_id": run_id}
        if scenario_ref is not None and scenario_ref:
            result["scenario_ref"] = scenario_ref
        return result

    def _structured_output(self, name: str, raw: dict[str, Any]) -> dict[str, Any]:
        tool = next(item for item in self.backend.bundle.asset_registry["tool_namespace"]["tools"] if item["tool_id"] == name)
        role = tool["tool_role"]
        if role == "RUN_INITIALIZER":
            # ``result`` exposes the complete submission envelope for the
            # rejection terminal while the sibling scalar fields remain
            # available for ordinary routing and context propagation.
            return {"result": raw, **raw}
        if role == "NODE_STUB":
            return {
                "result": raw,
                "run_id": raw.get("run_id"),
                "node_id": raw.get("node_id"),
                "status": raw.get("status"),
            }
        if role == "CONTROL_LITERAL":
            decisions = raw.get("decisions")
            decision_values = (
                [item.get("decision") for item in decisions if isinstance(item, dict)]
                if isinstance(decisions, list)
                else []
            )
            return {
                "result": raw,
                "run_id": self._run_id_from_control(raw),
                "state": raw.get("state"),
                "decision": raw.get("decision"),
                "decision_1": decision_values[0] if len(decision_values) > 0 else None,
                "decision_2": decision_values[1] if len(decision_values) > 1 else None,
                "decision_3": decision_values[2] if len(decision_values) > 2 else None,
                "mode": raw.get("mode"),
            }
        if role == "RUN_FINALIZER":
            return {"result": raw, "run_id": raw.get("run_id"), "run_status": raw.get("run_status")}
        raise ContractError(f"unsupported registered tool role: {role}")

    @staticmethod
    def _run_id_from_control(raw: dict[str, Any]) -> str | None:
        runtime = raw.get("runtime_decisions")
        if not isinstance(runtime, list):
            return None
        for item in runtime:
            if isinstance(item, dict) and isinstance(item.get("run_id"), str):
                return item["run_id"]
        return None

    @staticmethod
    def _result(request_id: str | int, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }


class _RequestHandler(BaseHTTPRequestHandler):
    server_version = "T01Phase1MockMCP/0.1"
    # Dify creates one short-lived MCP client per workflow tool node and sends
    # initialize/initialized/tools-call over that client.  HTTP/1.1 lets those
    # three messages reuse one TCP connection instead of churning three host ↔
    # container proxy connections per node.
    protocol_version = "HTTP/1.1"

    @property
    def application(self) -> MCPApplication:
        return self.server.application  # type: ignore[attr-defined,no-any-return]

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        if self.path.rstrip("/") == HEALTH_PATH:
            self._write_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "server": MCP_SERVER_NAME,
                    "version": MCP_SERVER_VERSION,
                    "protocol_version": MCP_PROTOCOL_VERSION,
                    "tool_count": len(self.application.facade.tool_ids),
                    "mock_only": True,
                    "scientific_compute": False,
                },
            )
            return
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        if self.path.rstrip("/") != MCP_PATH:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 8 * 1024 * 1024:
                raise ValueError("invalid content length")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                MCPApplication._error(None, -32700, "Parse error"),
            )
            return
        status, response = self.application.dispatch(payload)
        if response is None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._write_json(status, response)

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def log_message(self, format: str, *args: Any) -> None:
        # Never log request bodies or headers; only the sanitized HTTP access line.
        super().log_message(format, *args)

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class Phase1MockMCPServer(ThreadingHTTPServer):
    """Threaded local HTTP server with one shared deterministic backend."""

    daemon_threads = True
    # Windows interprets SO_REUSEADDR broadly enough to let multiple listeners
    # claim the same port.  That can route a campaign into another runtime root,
    # so an M4 transport must hold the address exclusively.
    allow_reuse_address = False
    block_on_close = False
    # A complete Dify case can contain more than fifty MCP nodes.  Keep a
    # comfortably sized accept queue so the Docker/SSRF proxy cannot turn a
    # brief connection burst into a synthetic 503.
    request_queue_size = 256

    def __init__(
        self,
        address: tuple[str, int],
        *,
        backend: MockBackend | None = None,
    ) -> None:
        self.application = MCPApplication(backend)
        super().__init__(address, _RequestHandler)


def serve(host: str, port: int, runtime_root: Path | None = None) -> None:
    backend = MockBackend.local(runtime_root=runtime_root)
    server = Phase1MockMCPServer((host, port), backend=backend)
    print(
        f"phase1_mock_mcp=READY host={host} port={port} path={MCP_PATH} "
        f"tools={len(server.application.facade.tool_ids)}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--runtime-root", type=Path)
    args = parser.parse_args(argv)
    serve(args.host, args.port, args.runtime_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
