"""Fail-closed static validation for Phase 1 Mock Dify templates and bound DSL."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from ..catalog import SpecificationBundle
from ..constants import EDGE_IDS, NODE_IDS
from ..jsonio import ContractError
from .generator import DSL_VERSION, normalized_business_document


_TOKEN_PATTERN = re.compile(r"__[A-Z][A-Z0-9_]*__")
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer\s+[a-z0-9._-]+|password|client[_-]?secret|access[_-]?token|refresh[_-]?token|cookie|jwt)"
)
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?i)(?:[a-z]:\\|/(?:home|users|var|etc|opt)/)")
_REMOTE_SCIENCE_PATTERN = re.compile(
    r"(?i)https?://[^\s]*(?:uniprot|ncbi|alphafold|ebi|rcsb|pdb|blast|interpro)"
)
_ALLOWED_NODE_TYPES = {
    "start",
    "tool",
    "if-else",
    "template-transform",
    "variable-aggregator",
    "end",
}


def load_yaml_bytes(content: bytes, label: str = "Dify DSL") -> dict[str, Any]:
    try:
        value = yaml.safe_load(content.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ContractError(f"{label} is not parseable UTF-8 YAML") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be a YAML object")
    return value


def validate_workflow_document(
    document: dict[str, Any],
    *,
    bundle: SpecificationBundle | None = None,
    expected_app_name: str | None = None,
    expected_provider_id: str | None = None,
    template: bool,
) -> dict[str, Any]:
    bundle = bundle or SpecificationBundle.load()
    registry = bundle.asset_registry
    text = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
    if document.get("version") != DSL_VERSION or document.get("kind") != "app":
        raise ContractError(f"DSL must be target version {DSL_VERSION} and kind app")
    app = document.get("app")
    workflow = document.get("workflow")
    if not isinstance(app, dict) or not isinstance(workflow, dict):
        raise ContractError("DSL requires app and workflow objects")
    if app.get("mode") != "workflow":
        raise ContractError("Dify app mode must be workflow")
    if expected_app_name is not None and app.get("name") != expected_app_name:
        raise ContractError(f"unexpected Dify app name: {app.get('name')}")
    graph = workflow.get("graph")
    if not isinstance(graph, dict):
        raise ContractError("workflow graph is missing")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ContractError("workflow graph nodes/edges must be arrays")
    node_ids = [item.get("id") for item in nodes if isinstance(item, dict)]
    if len(node_ids) != len(set(node_ids)) or any(not isinstance(item, str) for item in node_ids):
        raise ContractError("Dify node IDs must be unique strings")
    node_by_id = {item["id"]: item for item in nodes}
    node_types = {item.get("data", {}).get("type") for item in nodes}
    unknown_types = node_types - _ALLOWED_NODE_TYPES
    if unknown_types:
        raise ContractError(f"unsupported or unsafe Dify node types: {sorted(unknown_types)}")
    for edge in edges:
        if not isinstance(edge, dict):
            raise ContractError("graph edge must be an object")
        if edge.get("source") not in node_by_id or edge.get("target") not in node_by_id:
            raise ContractError(f"dangling graph edge: {edge.get('id')}")
    edge_ids = [edge.get("id") for edge in edges]
    if len(edge_ids) != len(set(edge_ids)):
        raise ContractError("Dify edge IDs must be unique")
    semantic_edges = {
        edge.get("data", {}).get("semantic_edge_id")
        for edge in edges
        if edge.get("data", {}).get("semantic_edge_id") is not None
    }
    if semantic_edges != set(EDGE_IDS):
        raise ContractError(
            f"semantic edge set mismatch: missing={sorted(set(EDGE_IDS)-semantic_edges)}, "
            f"extra={sorted(semantic_edges-set(EDGE_IDS))}"
        )

    business_nodes: set[str] = set()
    tool_nodes: list[dict[str, Any]] = []
    for node in nodes:
        data = node["data"]
        if data["type"] != "tool":
            continue
        tool_nodes.append(node)
        marker = data.get("t01_business_node_id", node["id"])
        if marker in NODE_IDS:
            business_nodes.add(marker)
    if business_nodes != set(NODE_IDS):
        raise ContractError("graph must expose exactly the N01-N18 business identities")
    registered_tools = tuple(item["tool_id"] for item in registry["tool_namespace"]["tools"])
    actual_tools = {node["data"].get("tool_name") for node in tool_nodes}
    if actual_tools != set(registered_tools):
        raise ContractError(
            f"tool set mismatch: missing={sorted(set(registered_tools)-actual_tools)}, "
            f"extra={sorted(actual_tools-set(registered_tools))}"
        )
    providers = {
        (node["data"].get("provider_id"), node["data"].get("provider_name"))
        for node in tool_nodes
    }
    token = registry["binding"]["provider_binding_token"]
    expected = token if template else expected_provider_id
    if not isinstance(expected, str) or not expected:
        raise ContractError("expected provider identity is empty")
    if providers != {(expected, expected)}:
        raise ContractError(f"workflow must use only provider {expected}")

    if template:
        tokens = set(_TOKEN_PATTERN.findall(text))
        if tokens != {token}:
            raise ContractError(f"template token set must be exactly {token}: {sorted(tokens)}")
        if expected_provider_id and expected_provider_id in text:
            raise ContractError("unbound template contains bound provider identity")
    elif _TOKEN_PATTERN.search(text):
        raise ContractError("bound DSL contains an unresolved or unknown token")
    if _SECRET_PATTERN.search(text):
        raise ContractError("DSL contains a secret-like field or value")
    if _ABSOLUTE_PATH_PATTERN.search(text):
        raise ContractError("DSL contains a local absolute path")
    if _REMOTE_SCIENCE_PATTERN.search(text):
        raise ContractError("DSL contains a remote scientific endpoint")
    for marker in registry["regression_isolation"]["forbidden_legacy_identity_markers_in_current_runtime_assets"]:
        # The broad historical marker also appears inside the current canonical
        # version labels (T01-PHASE1-MOCK-*); reject it only as a scenario identity.
        if marker == "MOCK-":
            if re.search(r"(?i)(?:scenario_ref|scenario_key).{0,20}MOCK-", text):
                raise ContractError("DSL contains a forbidden legacy MOCK-* scenario identity")
            continue
        if marker in text:
            raise ContractError(f"DSL contains forbidden legacy marker: {marker}")

    controls = {item["control_key"] for item in registry["tool_namespace"]["tools"] if item["tool_role"] == "CONTROL_LITERAL"}
    expected_controls = {
        "design_suitability",
        "n12_validation",
        "n15_delivery_recommendation",
        "n16_applicability",
        "n17_applicability",
        "n18_entry",
    }
    if controls != expected_controls:
        raise ContractError("control literal registry differs from the six frozen controls")
    required_graph_nodes = {
        "GATE_IF",
        "N11_C1",
        "N11_C2",
        "N11_C3",
        "N12_C1",
        "N12_C2",
        "N12_C3",
        "N16_IF",
        "N17_IF",
        "JOIN_N16_N17",
        "RUN_FINALIZE",
        "END",
    }
    if not required_graph_nodes.issubset(node_by_id):
        raise ContractError("graph is missing Gate/recalc/condition/join/finalization nodes")
    if any(item["data"].get("t01_design_cycle", 0) > 3 for item in tool_nodes):
        raise ContractError("N12 design cycle exceeds the frozen maximum of three")
    return {
        "app_name": app["name"],
        "dsl_version": DSL_VERSION,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "business_node_count": len(business_nodes),
        "semantic_edge_count": len(semantic_edges),
        "registered_tool_count": len(actual_tools),
        "provider": expected,
        "template": template,
    }


def validate_main_debug_pair(main: dict[str, Any], debug: dict[str, Any]) -> None:
    left = normalized_business_document(main)
    right = normalized_business_document(debug)
    if left != right:
        raise ContractError("main/debug differ outside the frozen presentation allowlist")


def validate_yaml_file(
    path: Path,
    *,
    bundle: SpecificationBundle | None = None,
    expected_app_name: str | None = None,
    expected_provider_id: str | None = None,
    template: bool,
) -> dict[str, Any]:
    return validate_workflow_document(
        load_yaml_bytes(path.read_bytes(), str(path)),
        bundle=bundle,
        expected_app_name=expected_app_name,
        expected_provider_id=expected_provider_id,
        template=template,
    )


def normalize_target_export(document: dict[str, Any]) -> dict[str, Any]:
    """Drop only target-generated presentation metadata for readback comparison."""

    value = deepcopy(document)
    graph = value.get("workflow", {}).get("graph", {})
    for node in graph.get("nodes", []):
        node.pop("zIndex", None)
    return value
