"""Deterministic Dify 0.7.0 workflow generator for Phase 1 Mock.

The generated canvas only observes facts exposed by the frozen M2 tool facade.
It never derives scientific values or control decisions.  N12 is bounded by a
three-cycle unrolling because a graph cycle is not portable across Dify builds.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..catalog import SpecificationBundle
from ..constants import EDGE_IDS, NODE_IDS
from ..jsonio import ContractError
from ..paths import PROJECT_ROOT


DSL_VERSION = "0.7.0"
GENERATOR_VERSION = "T01-PHASE1-MOCK-M3-GENERATOR-v0.1"
ALLOWED_ROLES = {"PRIMARY", "DEBUG"}


class _StableDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:  # noqa: ANN401 - PyYAML API.
        return True


def dump_yaml(document: dict[str, Any]) -> bytes:
    text = yaml.dump(
        document,
        Dumper=_StableDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )
    return text.replace("\r\n", "\n").encode("utf-8")


@dataclass(frozen=True)
class GeneratedWorkflow:
    workflow_id: str
    template_id: str
    role: str
    app_name: str
    output_path: Path
    document: dict[str, Any]

    @property
    def content(self) -> bytes:
        return dump_yaml(self.document)


class WorkflowGenerator:
    """Build both templates from one M1/M2 specification bundle."""

    def __init__(self, bundle: SpecificationBundle | None = None) -> None:
        self.bundle = bundle or SpecificationBundle.load()
        self.registry = self.bundle.asset_registry
        self.tools = self.registry["tool_namespace"]["tools"]
        self.provider_token = self.registry["binding"]["provider_binding_token"]
        self._tool_by_node = {
            item["node_id"]: item["tool_id"]
            for item in self.tools
            if item["tool_role"] == "NODE_STUB"
        }
        self._tool_by_control = {
            item["control_key"]: item["tool_id"]
            for item in self.tools
            if item["tool_role"] == "CONTROL_LITERAL"
        }
        self.initializer = self._one_tool("RUN_INITIALIZER")
        self.finalizer = self._one_tool("RUN_FINALIZER")

    def _one_tool(self, role: str) -> str:
        matches = [item["tool_id"] for item in self.tools if item["tool_role"] == role]
        if len(matches) != 1:
            raise ContractError(f"registry must contain one {role} tool")
        return matches[0]

    def generate_all(self) -> tuple[GeneratedWorkflow, GeneratedWorkflow]:
        outputs: list[GeneratedWorkflow] = []
        for registered in self.registry["workflows"]:
            role = registered["workflow_role"]
            if role not in ALLOWED_ROLES:
                raise ContractError(f"unsupported workflow role: {role}")
            document = self._document(registered)
            outputs.append(
                GeneratedWorkflow(
                    workflow_id=registered["workflow_id"],
                    template_id=registered["template_id"],
                    role=role,
                    app_name=registered["dify_app_name"],
                    output_path=PROJECT_ROOT.joinpath(*registered["template_path"].split("/")),
                    document=document,
                )
            )
        if len(outputs) != 2:
            raise ContractError("registry must define exactly main and debug workflows")
        return tuple(outputs)  # type: ignore[return-value]

    def _document(self, registered: dict[str, Any]) -> dict[str, Any]:
        role = registered["workflow_role"]
        description = (
            f"{GENERATOR_VERSION}; workflow_id={registered['workflow_id']}; "
            f"template_id={registered['template_id']}; role={role}; "
            "offline MOCK_DATA only; scientific_compute=false; "
            f"semantic_edges={','.join(EDGE_IDS)}"
        )
        nodes, edges = self._graph()
        return {
            "app": {
                "description": description,
                "icon": "🧪",
                "icon_background": "#E4FBCC" if role == "PRIMARY" else "#E5E7EB",
                "mode": "workflow",
                "name": registered["dify_app_name"],
                "use_icon_as_answer_icon": False,
            },
            "dependencies": [],
            "kind": "app",
            "version": DSL_VERSION,
            "workflow": {
                "conversation_variables": [],
                "environment_variables": [],
                "features": self._features(),
                "graph": {
                    "edges": edges,
                    "nodes": nodes,
                    "viewport": {"x": -50, "y": 60, "zoom": 0.38},
                },
            },
        }

    @staticmethod
    def _features() -> dict[str, Any]:
        return {
            "file_upload": {
                "allowed_file_extensions": [".JPG", ".JPEG", ".PNG", ".GIF", ".WEBP", ".SVG"],
                "allowed_file_types": ["image"],
                "allowed_file_upload_methods": ["local_file", "remote_url"],
                "enabled": False,
                "fileUploadConfig": {
                    "audio_file_size_limit": 50,
                    "batch_count_limit": 5,
                    "file_size_limit": 15,
                    "image_file_size_limit": 10,
                    "video_file_size_limit": 100,
                    "workflow_file_upload_limit": 10,
                },
                "image": {
                    "enabled": False,
                    "number_limits": 3,
                    "transfer_methods": ["local_file", "remote_url"],
                },
                "number_limits": 3,
            },
            "opening_statement": "",
            "retriever_resource": {"enabled": False},
            "sensitive_word_avoidance": {"enabled": False},
            "speech_to_text": {"enabled": False},
            "suggested_questions": [],
            "suggested_questions_after_answer": {"enabled": False},
            "text_to_speech": {"enabled": False, "language": "", "voice": ""},
        }

    def _graph(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        positions: dict[str, tuple[int, int]] = {}

        def place(node_id: str, column: int, row: int = 0) -> tuple[int, int]:
            value = (80 + column * 330, 200 + row * 180)
            positions[node_id] = value
            return value

        def add_node(node_id: str, node_type: str, title: str, column: int, row: int, data: dict[str, Any], height: int = 90) -> None:
            x, y = place(node_id, column, row)
            payload = {"desc": "", "selected": False, "title": title, "type": node_type, **data}
            nodes.append(
                {
                    "data": payload,
                    "height": height,
                    "id": node_id,
                    "position": {"x": x, "y": y},
                    "positionAbsolute": {"x": x, "y": y},
                    "selected": False,
                    "sourcePosition": "right",
                    "targetPosition": "left",
                    "type": "custom",
                    "width": 244,
                }
            )

        def add_edge(source: str, target: str, *, handle: str = "source", semantic: str | None = None, suffix: str = "") -> None:
            source_type = next(n["data"]["type"] for n in nodes if n["id"] == source)
            target_type = next(n["data"]["type"] for n in nodes if n["id"] == target)
            edge_id = semantic if semantic and not suffix else f"{source}-{handle}-{target}-target{suffix}"
            data: dict[str, Any] = {
                "isInIteration": False,
                "isInLoop": False,
                "sourceType": source_type,
                "targetType": target_type,
            }
            if semantic:
                data["semantic_edge_id"] = semantic
            edges.append(
                {
                    "data": data,
                    "id": edge_id,
                    "source": source,
                    "sourceHandle": handle,
                    "target": target,
                    "targetHandle": "target",
                    "type": "custom",
                    "zIndex": 0,
                }
            )

        add_node(
            "START", "start", "Canonical Request", 0, 0,
            {
                "variables": [
                    {"label": "operation", "max_length": 48, "options": ["SUBMIT", "FINALIZE_EXISTING"], "required": True, "type": "select", "variable": "operation"},
                    {"label": "request_json", "max_length": 200000, "options": [], "required": False, "type": "paragraph", "variable": "request_json"},
                    {"label": "run_id_override", "max_length": 96, "options": [], "required": False, "type": "text-input", "variable": "run_id_override"},
                ]
            },
            height=142,
        )
        add_node("MODE_IF", "if-else", "Existing run?", 1, 0, self._if_data("START", "operation", "FINALIZE_EXISTING"), 126)
        add_node("RUN_INITIALIZE", "tool", "Create / Replay Run", 2, 1, self._tool_data(self.initializer, {"request_json": self._var("START", "request_json")}), 116)
        add_node("INIT_REJECT_IF", "if-else", "Submission rejected?", 3, 1, self._if_data("RUN_INITIALIZE", "action", "REJECT_REQUEST"), 126)
        add_node("CONTEXT_AGG", "variable-aggregator", "Canonical run context", 4, 0, self._context_aggregator_data(), 180)
        add_node(
            "REJECT_END", "end", "Rejected submission", 4, 2,
            {"outputs": [
                {"value_selector": ["RUN_INITIALIZE", "result"], "value_type": "object", "variable": "submission"},
                {"value_selector": ["RUN_INITIALIZE", "action"], "value_type": "string", "variable": "submission_action"},
                {"value_selector": ["RUN_INITIALIZE", "error_code"], "value_type": "string", "variable": "error_code"},
            ]},
            height=116,
        )
        add_edge("START", "MODE_IF")
        add_edge("MODE_IF", "CONTEXT_AGG", handle="true")
        add_edge("MODE_IF", "RUN_INITIALIZE", handle="false")
        add_edge("RUN_INITIALIZE", "INIT_REJECT_IF")
        add_edge("INIT_REJECT_IF", "REJECT_END", handle="true")
        add_edge("INIT_REJECT_IF", "CONTEXT_AGG", handle="false")

        run_selector = ["CONTEXT_AGG", "run_id", "output"]
        prior = "CONTEXT_AGG"
        for index, node_id in enumerate(NODE_IDS[:10], start=1):
            column = 4 + index * 2
            add_node(node_id, "tool", f"{node_id} Mock fact", column, 0, self._tool_data(self._tool_by_node[node_id], {"run_id": self._selector(run_selector)}), 116)
            check_id = f"CHECK_{node_id}"
            add_node(check_id, "if-else", f"{node_id} succeeded?", column + 1, 0, self._if_data(node_id, "status", "SUCCEEDED"), 126)
            semantic = EDGE_IDS[index - 1]
            add_edge(
                prior,
                node_id,
                handle="true" if prior.startswith("CHECK_") else "source",
                semantic=semantic,
            )
            add_edge(node_id, check_id)
            prior = check_id

        add_node("CONTROL_GATE", "tool", "Design suitability literal", 25, 0, self._tool_data(self._tool_by_control["design_suitability"], {"run_id": self._selector(run_selector)}), 116)
        add_node("GATE_IF", "if-else", "WT direct?", 26, 0, self._if_data("CONTROL_GATE", "decision", "DESIGN_NOT_SUITABLE"), 126)
        add_edge(prior, "CONTROL_GATE", handle="true", semantic="E011")
        add_edge("CONTROL_GATE", "GATE_IF")

        # N11/N12 bounded unrolling. Repeated physical nodes keep the registered N11/N12 identities in data.
        for cycle, row in ((1, 1), (2, 2), (3, 3)):
            add_node(f"N11_C{cycle}", "tool", f"N11 cycle {cycle}", 27 + (cycle - 1) * 4, row, self._tool_data(self._tool_by_node["N11"], {"run_id": self._selector(run_selector)}, business_node_id="N11", cycle=cycle), 116)
            add_node(f"N12_C{cycle}", "tool", f"N12 cycle {cycle}", 28 + (cycle - 1) * 4, row, self._tool_data(self._tool_by_node["N12"], {"run_id": self._selector(run_selector)}, business_node_id="N12", cycle=cycle), 116)
            if cycle < 3:
                add_node(f"RECALC_IF_C{cycle}", "if-else", f"Recalculate after cycle {cycle}?", 30 + (cycle - 1) * 4, row, self._if_data("CONTROL_N12", f"decision_{cycle}", "RECALC_REQUIRED"), 126)
        add_node("CONTROL_N12", "tool", "N12 validation literals", 29, 2, self._tool_data(self._tool_by_control["n12_validation"], {"run_id": self._selector(run_selector)}), 116)
        add_node("EXHAUSTED_IF", "if-else", "N12 exhausted?", 38, 3, self._if_data("CONTROL_N12", "decision_3", "RECALC_EXHAUSTED"), 126)

        add_edge("GATE_IF", "N11_C1", handle="false", semantic="E014")
        add_edge("N11_C1", "N12_C1", semantic="E015")
        add_edge("N12_C1", "CONTROL_N12")
        add_edge("CONTROL_N12", "RECALC_IF_C1")
        add_edge("RECALC_IF_C1", "N11_C2", handle="true", semantic="E016", suffix="-c2")
        add_edge("N11_C2", "N12_C2", semantic="E015", suffix="-c2")
        add_edge("N12_C2", "RECALC_IF_C2")
        add_edge("RECALC_IF_C2", "N11_C3", handle="true", semantic="E016", suffix="-c3")
        add_edge("N11_C3", "N12_C3", semantic="E015", suffix="-c3")
        add_edge("N12_C3", "EXHAUSTED_IF")

        # Downstream design chain.
        for offset, node_id in enumerate(NODE_IDS[12:15]):
            column = 40 + offset * 2
            add_node(node_id, "tool", f"{node_id} Mock fact", column, 0, self._tool_data(self._tool_by_node[node_id], {"run_id": self._selector(run_selector)}), 116)
            check_id = f"CHECK_{node_id}"
            add_node(check_id, "if-else", f"{node_id} succeeded?", column + 1, 0, self._if_data(node_id, "status", "SUCCEEDED"), 126)
            add_edge(node_id, check_id)
        add_edge("RECALC_IF_C1", "N13", handle="false", semantic="E017", suffix="-c1")
        add_edge("RECALC_IF_C2", "N13", handle="false", semantic="E017", suffix="-c2")
        add_edge("EXHAUSTED_IF", "N13", handle="false", semantic="E017", suffix="-c3")
        add_edge("CHECK_N13", "N14", handle="true", semantic="E019")
        add_edge("CHECK_N14", "N15", handle="true", semantic="E020")

        add_node("CONTROL_N15", "tool", "N15 recommendation literal", 47, 0, self._tool_data(self._tool_by_control["n15_delivery_recommendation"], {"run_id": self._selector(run_selector)}), 116)
        add_node("CONTROL_N16", "tool", "N16 applicability literal", 48, -1, self._tool_data(self._tool_by_control["n16_applicability"], {"run_id": self._selector(run_selector)}), 116)
        add_node("CONTROL_N17", "tool", "N17 applicability literal", 48, 1, self._tool_data(self._tool_by_control["n17_applicability"], {"run_id": self._selector(run_selector)}), 116)
        add_node("N16_IF", "if-else", "Execute N16?", 49, -1, self._if_data("CONTROL_N16", "decision", "EXECUTE"), 126)
        add_node("N17_IF", "if-else", "Execute N17?", 49, 1, self._if_data("CONTROL_N17", "decision", "EXECUTE"), 126)
        add_node("N16", "tool", "N16 Mock fact", 50, -2, self._tool_data(self._tool_by_node["N16"], {"run_id": self._selector(run_selector)}), 116)
        add_node("N17", "tool", "N17 Mock fact", 50, 2, self._tool_data(self._tool_by_node["N17"], {"run_id": self._selector(run_selector)}), 116)
        add_node("SKIP_N16", "template-transform", "N16 settled without execution", 50, 0, {"template": "NOT_EXECUTED", "variables": []}, 54)
        add_node("SKIP_N17", "template-transform", "N17 settled without execution", 50, 1, {"template": "NOT_EXECUTED", "variables": []}, 54)
        add_node("JOIN_N16_N17", "variable-aggregator", "N16/N17 settled join", 51, 0, self._join_aggregator_data(), 218)
        add_node("CONTROL_N18", "tool", "N18 entry literal", 52, 0, self._tool_data(self._tool_by_control["n18_entry"], {"run_id": self._selector(run_selector)}), 116)
        add_node("N18", "tool", "N18 Mock fact", 53, 0, self._tool_data(self._tool_by_node["N18"], {"run_id": self._selector(run_selector)}), 116)

        add_edge("CHECK_N15", "CONTROL_N15", handle="true", semantic="E021")
        add_edge("CONTROL_N15", "CONTROL_N16", semantic="E022")
        add_edge("CONTROL_N15", "CONTROL_N17", semantic="E023")
        add_edge("CONTROL_N16", "N16_IF")
        add_edge("CONTROL_N17", "N17_IF")
        add_edge("N16_IF", "N16", handle="true")
        add_edge("N16_IF", "SKIP_N16", handle="false")
        add_edge("N17_IF", "N17", handle="true")
        add_edge("N17_IF", "SKIP_N17", handle="false")
        add_edge("N16", "JOIN_N16_N17", semantic="E024", suffix="-exec")
        add_edge("SKIP_N16", "JOIN_N16_N17", semantic="E024", suffix="-skip")
        add_edge("N17", "JOIN_N16_N17", semantic="E025", suffix="-exec")
        add_edge("SKIP_N17", "JOIN_N16_N17", semantic="E025", suffix="-skip")
        add_edge("JOIN_N16_N17", "CONTROL_N18", semantic="E026")

        # WT direct enters the same N18 control point.
        add_node("WT_SETTLED", "template-transform", "WT direct branch", 47, -3, {"template": "WT_DIRECT", "variables": []}, 54)
        add_edge("GATE_IF", "WT_SETTLED", handle="true", semantic="E012")
        add_edge("WT_SETTLED", "CONTROL_N18", semantic="E013")
        add_edge("CONTROL_N18", "N18")

        add_node("RUN_FINALIZE", "tool", "Canonical envelope", 55, 0, self._tool_data(self.finalizer, {"run_id": self._selector(run_selector)}), 116)
        add_node(
            "END", "end", "Return canonical envelope", 56, 0,
            {"outputs": [
                {"value_selector": ["RUN_FINALIZE", "result"], "value_type": "object", "variable": "envelope"},
                {"value_selector": ["CONTEXT_AGG", "submission_action", "output"], "value_type": "string", "variable": "submission_action"},
                {"value_selector": ["RUN_FINALIZE", "run_id"], "value_type": "string", "variable": "canonical_run_id"},
            ]},
            height=116,
        )
        add_edge("N18", "RUN_FINALIZE", semantic="E027")
        add_edge("RUN_FINALIZE", "END")

        # All fail-closed routes converge on the finalizer; no scientific inference occurs here.
        for node_id in [*(f"CHECK_N{i:02d}" for i in range(1, 11)), "CHECK_N13", "CHECK_N14", "CHECK_N15"]:
            add_edge(node_id, "RUN_FINALIZE", handle="false")
        add_edge("EXHAUSTED_IF", "RUN_FINALIZE", handle="true", semantic="E018")

        # Exact base N01-N18 identity must remain visibly recoverable.
        business_ids = {
            n["data"].get("t01_business_node_id", n["id"])
            for n in nodes
            if n["data"]["type"] == "tool"
        }
        if not set(NODE_IDS).issubset(business_ids):
            raise ContractError("generated graph lost one or more N01-N18 identities")
        return nodes, edges

    def _tool_data(
        self,
        tool_id: str,
        parameters: dict[str, dict[str, Any]],
        *,
        business_node_id: str | None = None,
        cycle: int | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "tool_node_version": "2",
            "tool_parameters": parameters,
            "tool_configurations": {},
            "provider_type": "mcp",
            "provider_id": self.provider_token,
            "provider_name": self.provider_token,
            "tool_label": tool_id,
            "tool_name": tool_id,
        }
        if business_node_id:
            data["t01_business_node_id"] = business_node_id
        if cycle is not None:
            data["t01_design_cycle"] = cycle
        return data

    @staticmethod
    def _var(node_id: str, output: str) -> dict[str, Any]:
        return {"value": [node_id, output], "type": "variable"}

    @staticmethod
    def _selector(selector: list[str]) -> dict[str, Any]:
        return {"value": selector, "type": "variable"}

    @staticmethod
    def _if_data(node_id: str, variable: str, expected: str) -> dict[str, Any]:
        return {
            "cases": [
                {
                    "case_id": "true",
                    "conditions": [
                        {
                            "comparison_operator": "is",
                            "id": f"cond-{node_id.lower()}-{variable.lower()}",
                            "value": expected,
                            "varType": "string",
                            "variable_selector": [node_id, variable],
                        }
                    ],
                    "id": "true",
                    "logical_operator": "and",
                }
            ]
        }

    @staticmethod
    def _context_aggregator_data() -> dict[str, Any]:
        return {
            "advanced_settings": {
                "group_enabled": True,
                "groups": [
                    {
                        "groupId": "group-run-id",
                        "group_name": "run_id",
                        "output_type": "string",
                        "variables": [["RUN_INITIALIZE", "run_id"], ["START", "run_id_override"]],
                    },
                    {
                        "groupId": "group-submission-action",
                        "group_name": "submission_action",
                        "output_type": "string",
                        "variables": [["RUN_INITIALIZE", "action"], ["START", "operation"]],
                    },
                ],
            },
            "output_type": "string",
            "variables": [["RUN_INITIALIZE", "run_id"], ["START", "run_id_override"]],
        }

    @staticmethod
    def _join_aggregator_data() -> dict[str, Any]:
        return {
            "advanced_settings": {
                "group_enabled": True,
                "groups": [
                    {
                        "groupId": "group-n16",
                        "group_name": "n16_settled",
                        "output_type": "string",
                        "variables": [["N16", "status"], ["SKIP_N16", "output"]],
                    },
                    {
                        "groupId": "group-n17",
                        "group_name": "n17_settled",
                        "output_type": "string",
                        "variables": [["N17", "status"], ["SKIP_N17", "output"]],
                    },
                ],
            },
            "output_type": "string",
            "variables": [["N16", "status"], ["SKIP_N16", "output"]],
        }


def render_all(bundle: SpecificationBundle | None = None) -> tuple[GeneratedWorkflow, GeneratedWorkflow]:
    return WorkflowGenerator(bundle).generate_all()


def normalized_business_document(document: dict[str, Any]) -> dict[str, Any]:
    """Remove only the frozen main/debug presentation allowlist."""

    value = deepcopy(document)
    value["app"]["name"] = "<ROLE_APP_NAME>"
    value["app"]["icon_background"] = "<ROLE_ICON_BACKGROUND>"
    description = value["app"]["description"]
    value["app"]["description"] = description.replace("role=PRIMARY", "role=<ROLE>").replace("role=DEBUG", "role=<ROLE>")
    value["app"]["description"] = value["app"]["description"].replace(
        "workflow_id=t01_phase1_mock_v01.workflow.main", "workflow_id=<WORKFLOW_ID>"
    ).replace("workflow_id=t01_phase1_mock_v01.workflow.debug", "workflow_id=<WORKFLOW_ID>")
    value["app"]["description"] = value["app"]["description"].replace(
        "template_id=t01_phase1_mock_v01.template.main", "template_id=<TEMPLATE_ID>"
    ).replace("template_id=t01_phase1_mock_v01.template.debug", "template_id=<TEMPLATE_ID>")
    return value
