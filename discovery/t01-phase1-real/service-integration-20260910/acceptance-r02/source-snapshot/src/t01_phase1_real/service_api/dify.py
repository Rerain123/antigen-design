"""Single-source generator for the independent real-service Dify workflow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml

from .transport import MCPApplication


DSL_VERSION = "0.7.0"
GENERATOR_VERSION = "T01-PHASE1-REAL-SERVICE-DIFY-v0.1"
APP_NAME = "T01_Phase1_Real_Service_v0.1"
WORKFLOW_ID = "t01_phase1_real_service_v01.workflow.main"
PROVIDER_TOKEN = "{{#T01_PHASE1_REAL_SERVICE_PROVIDER#}}"
PROVIDER_ID = "t01-phase1-real-service-v01"


class StableDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


def dump(document: dict[str, Any]) -> bytes:
    return yaml.dump(
        document, Dumper=StableDumper, allow_unicode=True, sort_keys=False,
        default_flow_style=False, width=120,
    ).replace("\r\n", "\n").encode("utf-8")


def _features() -> dict[str, Any]:
    return {
        "file_upload": {"enabled": False},
        "opening_statement": "",
        "retriever_resource": {"enabled": False},
        "sensitive_word_avoidance": {"enabled": False},
        "speech_to_text": {"enabled": False},
        "suggested_questions": [],
        "suggested_questions_after_answer": {"enabled": False},
        "text_to_speech": {"enabled": False, "language": "", "voice": ""},
    }


def _variable(node: str, output: str) -> dict[str, Any]:
    return {"type": "variable", "value": [node, output]}


def _selector(node: str, output: str) -> dict[str, Any]:
    return {"type": "variable", "value": [node, output, "output"]}


def _tool(suffix: str, parameters: dict[str, Any]) -> dict[str, Any]:
    tool_id = MCPApplication.TOOL_PREFIX + suffix
    return {
        "tool_node_version": "2",
        "tool_parameters": parameters,
        "tool_configurations": {},
        "provider_type": "mcp",
        "provider_id": PROVIDER_TOKEN,
        "provider_name": PROVIDER_TOKEN,
        "tool_label": tool_id,
        "tool_name": tool_id,
    }


def _if(node: str, variable: str, expected: str) -> dict[str, Any]:
    return {
        "cases": [{
            "case_id": "true",
            "conditions": [{
                "comparison_operator": "is", "id": f"cond-{node.lower()}-{variable}",
                "value": expected, "varType": "string", "variable_selector": [node, variable],
            }],
            "id": "true", "logical_operator": "and",
        }]
    }


def document(provider: str = PROVIDER_TOKEN) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(node_id: str, node_type: str, title: str, col: int, row: int, data: dict[str, Any], height: int = 100) -> None:
        x, y = 80 + col * 330, 200 + row * 190
        nodes.append({
            "data": {"desc": "", "selected": False, "title": title, "type": node_type, **data},
            "height": height, "id": node_id, "position": {"x": x, "y": y},
            "positionAbsolute": {"x": x, "y": y}, "selected": False,
            "sourcePosition": "right", "targetPosition": "left", "type": "custom", "width": 244,
        })

    def add_edge(source: str, target: str, handle: str = "source", edge_id: str | None = None) -> None:
        source_type = next(node["data"]["type"] for node in nodes if node["id"] == source)
        target_type = next(node["data"]["type"] for node in nodes if node["id"] == target)
        edges.append({
            "data": {"isInIteration": False, "isInLoop": False, "sourceType": source_type, "targetType": target_type},
            "id": edge_id or f"{source}-{handle}-{target}-target", "source": source,
            "sourceHandle": handle, "target": target, "targetHandle": "target", "type": "custom", "zIndex": 0,
        })

    add_node("START", "start", "Real workflow request", 0, 0, {"variables": [
        {"label": "operation", "max_length": 32, "options": ["SUBMIT", "GET_EXISTING"], "required": True, "type": "select", "variable": "operation"},
        {"label": "request_json", "max_length": 200000, "options": [], "required": False, "type": "paragraph", "variable": "request_json"},
        {"label": "idempotency_key", "max_length": 128, "options": [], "required": False, "type": "text-input", "variable": "idempotency_key"},
        {"label": "job_id", "max_length": 96, "options": [], "required": False, "type": "text-input", "variable": "job_id"},
        {"label": "wait_timeout_seconds", "max_length": 600, "options": [], "required": True, "type": "number", "variable": "wait_timeout_seconds"},
    ]}, 198)
    add_node("MODE_IF", "if-else", "Existing task?", 1, 0, _if("START", "operation", "GET_EXISTING"), 126)
    add_node("SUBMIT", "tool", "Submit authenticated workflow", 2, 1, _tool("workflow.submit", {
        "request_json": _variable("START", "request_json"),
        "idempotency_key": _variable("START", "idempotency_key"),
    }), 116)
    add_node("JOB_AGG", "variable-aggregator", "Canonical job identity", 3, 0, {
        "advanced_settings": {"group_enabled": True, "groups": [{
            "groupId": "group-job-id", "group_name": "job_id", "output_type": "string",
            "variables": [["SUBMIT", "job_id"], ["START", "job_id"]],
        }]},
        "output_type": "string", "variables": [["SUBMIT", "job_id"], ["START", "job_id"]],
    }, 154)
    add_node("WAIT", "tool", "Wait on backend state", 4, 0, _tool("workflow.wait", {
        "job_id": _selector("JOB_AGG", "job_id"),
        "timeout_seconds": _variable("START", "wait_timeout_seconds"),
    }), 116)
    add_node("SUCCESS_IF", "if-else", "Backend succeeded?", 5, 0, _if("WAIT", "state", "succeeded"), 126)
    add_node("REPORT", "tool", "Get verified report", 6, -1, _tool("workflow.report", {
        "job_id": _selector("JOB_AGG", "job_id"),
    }), 116)
    add_node("SUCCESS_END", "end", "Verified report", 7, -1, {"outputs": [
        {"value_selector": ["REPORT", "job_id"], "value_type": "string", "variable": "job_id"},
        {"value_selector": ["WAIT", "state"], "value_type": "string", "variable": "state"},
        {"value_selector": ["REPORT", "sha256"], "value_type": "string", "variable": "report_sha256"},
        {"value_selector": ["REPORT", "size_bytes"], "value_type": "number", "variable": "report_size_bytes"},
        {"value_selector": ["REPORT", "report_markdown"], "value_type": "string", "variable": "report_markdown"},
        {"value_selector": ["REPORT", "content_base64"], "value_type": "string", "variable": "report_base64"},
        {"value_selector": ["REPORT", "scientific_gate"], "value_type": "string", "variable": "scientific_gate"},
        {"value_selector": ["REPORT", "usable_for_pipeline"], "value_type": "boolean", "variable": "usable_for_pipeline"},
        {"value_selector": ["REPORT", "production_status"], "value_type": "string", "variable": "production_status"},
    ]}, 238)
    add_node("FAILURE_END", "end", "Backend did not succeed", 6, 1, {"outputs": [
        {"value_selector": ["WAIT", "job_id"], "value_type": "string", "variable": "job_id"},
        {"value_selector": ["WAIT", "state"], "value_type": "string", "variable": "state"},
        {"value_selector": ["WAIT", "error_code"], "value_type": "string", "variable": "error_code"},
        {"value_selector": ["WAIT", "wait_timed_out"], "value_type": "boolean", "variable": "wait_timed_out"},
        {"value_selector": ["WAIT", "scientific_gate"], "value_type": "string", "variable": "scientific_gate"},
        {"value_selector": ["WAIT", "usable_for_pipeline"], "value_type": "boolean", "variable": "usable_for_pipeline"},
        {"value_selector": ["WAIT", "production_status"], "value_type": "string", "variable": "production_status"},
    ]}, 198)

    add_edge("START", "MODE_IF")
    add_edge("MODE_IF", "JOB_AGG", "true")
    add_edge("MODE_IF", "SUBMIT", "false")
    add_edge("SUBMIT", "JOB_AGG")
    add_edge("JOB_AGG", "WAIT")
    add_edge("WAIT", "SUCCESS_IF")
    add_edge("SUCCESS_IF", "REPORT", "true")
    add_edge("SUCCESS_IF", "FAILURE_END", "false")
    add_edge("REPORT", "SUCCESS_END")

    value = {
        "app": {
            "description": f"{GENERATOR_VERSION}; workflow_id={WORKFLOW_ID}; authenticated real service; scientific_gate=CLOSED",
            "icon": "🔐", "icon_background": "#E4FBCC", "mode": "workflow",
            "name": APP_NAME, "use_icon_as_answer_icon": False,
        },
        "dependencies": [], "kind": "app", "version": DSL_VERSION,
        "workflow": {"conversation_variables": [], "environment_variables": [], "features": _features(),
                     "graph": {"edges": edges, "nodes": nodes, "viewport": {"x": 0, "y": 80, "zoom": 0.62}}},
    }
    if provider != PROVIDER_TOKEN:
        for node in nodes:
            data = node["data"]
            if data["type"] == "tool":
                data["provider_id"] = provider
                data["provider_name"] = provider
    return value


def template_bytes() -> bytes:
    return dump(document())


def bound_bytes(provider: str = PROVIDER_ID) -> bytes:
    return dump(document(provider))


def semantic_graph(value: dict[str, Any]) -> dict[str, Any]:
    graph = value["workflow"]["graph"]
    nodes = []
    for node in graph["nodes"]:
        data = node["data"]
        nodes.append({key: deepcopy(data.get(key)) for key in (
            "type", "variables", "outputs", "cases", "advanced_settings", "output_type",
            "tool_parameters", "provider_type", "provider_id", "provider_name", "tool_name",
        ) if key in data} | {"id": node["id"]})
    edges = [{key: edge.get(key) for key in ("id", "source", "sourceHandle", "target", "targetHandle")} for edge in graph["edges"]]
    return {"nodes": sorted(nodes, key=lambda row: row["id"]), "edges": sorted(edges, key=lambda row: row["id"])}
