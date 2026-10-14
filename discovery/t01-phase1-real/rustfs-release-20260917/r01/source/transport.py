"""Threaded authenticated REST and MCP Streamable HTTP transport."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from .app import MAX_JSON_BYTES, Credentials, Principal, Service, ServiceConfig, ServiceError


MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "t01-phase1-real-service-v01"
SERVER_VERSION = "0.1.0"
MCP_PATH = "/mcp"
HEALTH_PATH = "/healthz"


def _object_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


class MCPApplication:
    TOOL_PREFIX = "t01_phase1_real_service_v01.tool."

    def __init__(self, service: Service) -> None:
        self.service = service

    @classmethod
    def tools(cls) -> list[dict[str, Any]]:
        string = {"type": "string"}
        nullable_string = {"type": ["string", "null"]}
        common_output = {
            "job_id": string, "run_id": string, "state": string,
            "error_code": nullable_string, "scientific_gate": string,
            "usable_for_pipeline": {"type": "boolean"}, "production_status": string,
        }
        definitions = [
            ("structure.upload", "Register bounded structure bytes without accepting a server path.",
             _object_schema({"name": string, "media_type": string, "content_base64": string}, ["name", "media_type", "content_base64"]),
             {"upload_id": string, "name": string, "media_type": string, "sha256": string, "size_bytes": {"type": "integer"}}),
            ("workflow.submit", "Submit or idempotently replay one real local workflow.",
             _object_schema({"request_json": string, "idempotency_key": string, "structure_upload_id": string}, ["request_json", "idempotency_key"]),
             {**common_output, "action": string, "terminal": {"type": "boolean"}, "report_ready": {"type": "boolean"}}),
            ("workflow.get", "Read one owner-authorized workflow or node status.",
             _object_schema({"job_id": string, "node": string}, ["job_id"]),
             {**common_output, "terminal": {"type": "boolean"}, "report_ready": {"type": "boolean"}}),
            ("workflow.wait", "Wait for a backend-issued terminal state without deriving scientific decisions.",
             _object_schema({"job_id": string, "timeout_seconds": {"type": "integer", "minimum": 0, "maximum": 600}}, ["job_id", "timeout_seconds"]),
             {**common_output, "terminal": {"type": "boolean"}, "report_ready": {"type": "boolean"}, "wait_timed_out": {"type": "boolean"}}),
            ("workflow.cancel", "Request idempotent cancellation of an owner-authorized workflow.",
             _object_schema({"job_id": string, "idempotency_key": string}, ["job_id", "idempotency_key"]), {**common_output, "action": string}),
            ("workflow.recover", "Request idempotent recovery of existing durable workflow state.",
             _object_schema({"job_id": string, "idempotency_key": string}, ["job_id", "idempotency_key"]), {**common_output, "action": string}),
            ("workflow.retry", "Create an idempotent retry only from a confirmed failed/cancelled/timed-out workflow.",
             _object_schema({"job_id": string, "idempotency_key": string}, ["job_id", "idempotency_key"]), {**common_output, "action": string}),
            ("workflow.report", "Return a hash-verified report. When RustFS is enabled, publish report attachments and return verified public download URLs; retry this call if publication fails.",
             _object_schema({"job_id": string}, ["job_id"]),
             {"job_id": string, "filename": string, "media_type": string, "sha256": string,
              "size_bytes": {"type": "integer"}, "content_base64": string, "report_markdown": string,
              "publication_status": string,
              "attachments": {"type": "array", "items": _object_schema({"fileName": string, "fileUrl": string,
                  "mediaType": string, "sizeBytes": {"type": "integer"}, "sha256": string},
                  ["fileName", "fileUrl", "mediaType", "sizeBytes", "sha256"])},
              "scientific_gate": string, "usable_for_pipeline": {"type": "boolean"}, "production_status": string}),
        ]
        return [
            {
                "name": cls.TOOL_PREFIX + suffix,
                "title": cls.TOOL_PREFIX + suffix,
                "description": description,
                "inputSchema": schema,
                "outputSchema": {"type": "object", "properties": output, "required": [], "additionalProperties": True},
                "annotations": {"readOnlyHint": suffix in {"workflow.get", "workflow.wait"}, "destructiveHint": False},
            }
            for suffix, description, schema, output in definitions
        ]

    @classmethod
    def tool_ids(cls) -> list[str]:
        return [item["name"] for item in cls.tools()]

    def dispatch(self, principal: Principal, payload: Any) -> tuple[int, dict[str, Any] | None]:
        if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str):
            return HTTPStatus.BAD_REQUEST, self._error(payload.get("id") if isinstance(payload, dict) else None, -32600, "Invalid Request")
        request_id = payload.get("id")
        method = payload["method"]
        params = payload.get("params") or {}
        if request_id is None:
            return HTTPStatus.ACCEPTED, None
        if not isinstance(params, dict):
            return HTTPStatus.OK, self._error(request_id, -32602, "Invalid params")
        if method == "initialize":
            requested = params.get("protocolVersion")
            negotiated = requested if requested in {"2024-11-05", "2025-03-26", MCP_PROTOCOL_VERSION} else MCP_PROTOCOL_VERSION
            return HTTPStatus.OK, self._result(request_id, {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": "Authenticated engineering workflow service. Scientific Gate remains closed.",
            })
        if method == "ping":
            return HTTPStatus.OK, self._result(request_id, {})
        if method == "tools/list":
            return HTTPStatus.OK, self._result(request_id, {"tools": self.tools()})
        if method == "tools/call":
            return HTTPStatus.OK, self._call(request_id, principal, params)
        return HTTPStatus.OK, self._error(request_id, -32601, "Method not found")

    def _call(self, request_id: Any, principal: Principal, params: dict[str, Any]) -> dict[str, Any]:
        name, arguments = params.get("name"), params.get("arguments", {})
        if name not in self.tool_ids() or not isinstance(arguments, dict):
            return self._error(request_id, -32602, "Invalid params")
        tool = next(item for item in self.tools() if item["name"] == name)
        schema = tool["inputSchema"]
        allowed = set(schema["properties"])
        if set(arguments) - allowed or set(schema["required"]) - set(arguments):
            return self._error(request_id, -32602, "Invalid params")
        suffix = name[len(self.TOOL_PREFIX):]
        required_scope = {
            "structure.upload": "upload", "workflow.submit": "submit", "workflow.get": "query",
            "workflow.wait": "query", "workflow.cancel": "control", "workflow.recover": "control",
            "workflow.retry": "control", "workflow.report": "download",
        }[suffix]
        if required_scope not in principal.scopes:
            return self._tool_error(request_id, ServiceError("FORBIDDEN", "Credential lacks the required scope", 403))
        try:
            if suffix == "structure.upload":
                value = self.service.upload(principal, arguments)
            elif suffix == "workflow.submit":
                try:
                    request = json.loads(arguments["request_json"])
                except (ValueError, TypeError) as exc:
                    raise ServiceError("INVALID_REQUEST", "request_json is malformed", 422) from exc
                body = {"request": request, "idempotency_key": arguments["idempotency_key"]}
                if arguments.get("structure_upload_id"):
                    body["structure_upload_id"] = arguments["structure_upload_id"]
                value = self.service.submit(principal, body)
            elif suffix == "workflow.get":
                value = self.service.status(principal, arguments["job_id"], arguments.get("node") or None)
            elif suffix == "workflow.wait":
                value = self.service.wait(principal, arguments["job_id"], arguments["timeout_seconds"])
            elif suffix == "workflow.cancel":
                value = self.service.cancel(principal, arguments["job_id"], arguments["idempotency_key"])
            elif suffix == "workflow.recover":
                value = self.service.recover(principal, arguments["job_id"], arguments["idempotency_key"])
            elif suffix == "workflow.retry":
                value = self.service.retry(principal, arguments["job_id"], arguments["idempotency_key"])
            else:
                value = self.service.report_for_json(principal, arguments["job_id"])
        except ServiceError as exc:
            return self._tool_error(request_id, exc)
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return self._result(request_id, {"content": [{"type": "text", "text": text}], "structuredContent": value, "isError": False})

    @classmethod
    def _tool_error(cls, request_id: Any, exc: ServiceError) -> dict[str, Any]:
        value = exc.envelope()
        return cls._result(request_id, {
            "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}],
            "structuredContent": value, "isError": True,
        })

    @staticmethod
    def _result(request_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "T01Phase1RealService/0.1"
    protocol_version = "HTTP/1.1"

    def handle_one_request(self):
        import socket
        import threading
        def expire():
            try:self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:pass
        self._read_deadline=threading.Timer(15,expire)
        self._read_deadline.daemon=True;self._read_deadline.start()
        try:return super().handle_one_request()
        finally:self._read_deadline.cancel()

    def _read_complete(self):
        if hasattr(self,'_read_deadline'):self._read_deadline.cancel()

    @property
    def service(self) -> Service:
        return self.server.service  # type: ignore[attr-defined]

    @property
    def mcp(self) -> MCPApplication:
        return self.server.mcp  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        self._read_complete()
        path = unquote(urlsplit(self.path).path).rstrip("/") or "/"
        if path == HEALTH_PATH:
            self._json(HTTPStatus.OK, {
                "status": "ok", "server": SERVER_NAME, "version": SERVER_VERSION,
                "authentication": "bearer", "scientific_gate": "CLOSED",
                "production_status": "NOT_DEPLOYED", "tool_count": len(self.mcp.tool_ids()),
                "profile": self.service.config.public_profile(),
            })
            return
        match = re.fullmatch(r"/v1/workflows/(t01p1r-job-[0-9a-f]{32})(?:/nodes/([a-z_]+))?", path)
        report = re.fullmatch(r"/v1/workflows/(t01p1r-job-[0-9a-f]{32})/report", path)
        try:
            if report:
                principal = self._principal("download")
                value = self.service.report(principal, report.group(1))
                raw = value["content"]
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Content-Disposition", f'attachment; filename="{value["filename"]}"')
                self.send_header("Digest", "sha-256=" + value["sha256"])
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
                return
            if match:
                principal = self._principal("query")
                self._json(HTTPStatus.OK, self.service.status(principal, match.group(1), match.group(2)))
                return
            raise ServiceError("NOT_FOUND", "Endpoint not found", 404)
        except ServiceError as exc:
            self._json(exc.status, exc.envelope(), authenticate=exc.status == 401)

    def do_POST(self) -> None:  # noqa: N802
        path = unquote(urlsplit(self.path).path).rstrip("/") or "/"
        try:
            if path == MCP_PATH:
                principal = self._principal("query", any_scope=True)
                body = self._body()
                status, response = self.mcp.dispatch(principal, body)
                if response is None:
                    self.send_response(status)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                else:
                    self._json(status, response)
                return
            if path == "/v1/uploads":
                principal = self._principal("upload")
                self._json(HTTPStatus.CREATED, self.service.upload(principal, self._body()))
                return
            if path == "/v1/workflows":
                principal = self._principal("submit")
                value = self.service.submit(principal, self._body())
                self._json(HTTPStatus.CREATED if value["action"] == "CREATED" else HTTPStatus.OK, value)
                return
            match = re.fullmatch(r"/v1/workflows/(t01p1r-job-[0-9a-f]{32})/(cancel|recover|retry)", path)
            if match:
                principal = self._principal("control")
                body = self._body()
                if not isinstance(body, dict) or set(body) != {"idempotency_key"}:
                    raise ServiceError("INVALID_REQUEST", "Exact control fields required", 422)
                operation = match.group(2)
                value = getattr(self.service, operation)(principal, match.group(1), body["idempotency_key"])
                self._json(HTTPStatus.ACCEPTED, value)
                return
            raise ServiceError("NOT_FOUND", "Endpoint not found", 404)
        except ServiceError as exc:
            self._json(exc.status, exc.envelope(), authenticate=exc.status == 401)

    def _principal(self, scope: str, any_scope: bool = False) -> Principal:
        authorization = self.headers.get("Authorization")
        if any_scope:
            # MCP tool list/initialization requires a valid service credential;
            # individual calls enforce their operation scope.
            principal = self.service.credentials.authenticate(authorization)
            return principal
        return self.service.credentials.authenticate(authorization, scope)

    def _body(self) -> Any:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ServiceError("INVALID_REQUEST", "Content-Type application/json required", 415)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ServiceError("INVALID_REQUEST", "Invalid content length", 400) from exc
        if not 0 < length <= MAX_JSON_BYTES:
            raise ServiceError("INVALID_REQUEST", "JSON body size is invalid", 413)
        try:
            raw=self.rfile.read(length)
            if len(raw)!=length:raise ServiceError('INVALID_REQUEST','Incomplete request body',400)
            value=json.loads(raw.decode("utf-8"), object_pairs_hook=self._pairs)
            self._read_complete()
            return value
        except ServiceError:
            raise
        except (ValueError, UnicodeError) as exc:
            raise ServiceError("INVALID_REQUEST", "Malformed UTF-8 JSON", 400) from exc

    @staticmethod
    def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ServiceError("INVALID_REQUEST", "Duplicate JSON key", 400)
            result[key] = value
        return result

    def _json(self, status: int, value: Any, authenticate: bool = False) -> None:
        self._read_complete()
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            if authenticate:
                self.send_header("WWW-Authenticate", "Bearer")
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # Submission is durable and its worker is independent of the client socket.
            return

    def log_message(self, format: str, *args: Any) -> None:
        return  # Never log headers, bodies, bearer values or user input.


class Phase1RealServiceServer(ThreadingHTTPServer):
    daemon_threads = True
    # Linux needs SO_REUSEADDR to restart after connections enter TIME_WAIT.
    # Windows keeps exclusive-style admission; never enable SO_REUSEPORT.
    allow_reuse_address = os.name == 'posix'
    block_on_close = False
    request_queue_size = 128

    def __init__(self, address: tuple[str, int], service: Service) -> None:
        import threading
        self._connections = threading.BoundedSemaphore(32)
        self.service = service
        self.mcp = MCPApplication(service)
        super().__init__(address, RequestHandler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        return connection, address

    def process_request(self, request, client_address):
        if not self._connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connections.release()


def serve(host: str, port: int, config: ServiceConfig, credentials: Credentials) -> None:
    service = Service(config, credentials)
    recovered = service.recover_active()
    server = Phase1RealServiceServer((host, port), service)
    print(f"phase1_real_service=READY host={host} port={port} mcp={MCP_PATH} recovered={recovered}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.shutdown(wait=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18083)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--blast-database-root", type=Path)
    parser.add_argument("--homology-database-root", type=Path)
    parser.add_argument("--domains-database-root", type=Path)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--max-pending-tasks", type=int, default=64)
    parser.add_argument("--dispatch-start-delay-seconds", type=float, default=0)
    args = parser.parse_args(argv)
    try:
        config = ServiceConfig(
            runtime_root=args.runtime_root, blast_database_root=args.blast_database_root,
            homology_database_root=args.homology_database_root, domains_database_root=args.domains_database_root,
            max_workers=args.max_workers, max_pending_tasks=args.max_pending_tasks,
            dispatch_start_delay_seconds=args.dispatch_start_delay_seconds,
        )
        serve(args.host, args.port, config, Credentials.from_environment())
        return 0
    except ServiceError as exc:
        print(json.dumps(exc.envelope(), sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
