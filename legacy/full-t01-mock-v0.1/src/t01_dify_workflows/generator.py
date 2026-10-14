"""Build Dify 0.7.0 workflow templates for the reviewed T-01 v10 graph.

The generated workflows contain no LLM, Code, HTTP, or scientific arithmetic
nodes.  They only invoke MCP tools, branch on backend-owned enum/boolean
outputs, aggregate mutually exclusive branches, and return backend results.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from t01_mock_mcp.catalog import SCENARIOS, STEP_TOOLS


DSL_VERSION = "0.7.0"
MCP_PROVIDER_TOKEN = "__T01_MCP_PROVIDER_ID__"
MASTER_NAME = "T01_Master_v10"
SYSTEM_RUN_ID_SELECTOR = ("sys", "workflow_run_id")
PHASE_NAMES = (
    "T01_P0_Structure",
    "T01_P1_EpitopeSafety",
    "T01_P2_ConservationDomain",
    "T01_P3_WTDevelopability",
    "T01_P4_Design",
    "T01_P5_VariantEvaluation",
    "T01_P6_CodonStabilityMD",
    "T01_P7_OutputHandoff",
)
DEBUG_PHASE_NAMES = tuple(f"{name}_Debug" for name in PHASE_NAMES)
DEBUG_PHASE0_NAME = DEBUG_PHASE_NAMES[0]

ALLOWED_NODE_TYPES = {"start", "tool", "if-else", "variable-aggregator", "end"}
CONTROL_TOOL_NAMES = {"mock.configure_run", "mock.configure_run_from_json"}


def _token_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()


def workflow_provider_token(name: str) -> str:
    return f"__{_token_name(name)}_PROVIDER_ID__"


def workflow_tool_token(name: str) -> str:
    return f"__{_token_name(name)}_TOOL_NAME__"


def constant(value: Any) -> dict[str, Any]:
    # Dify 1.17 renders MCP object/array parameters with its JSON editor.  The
    # editor expects the persisted constant to be JSON text; passing a native
    # dict/list makes Monaco treat that object as a text-buffer factory and the
    # node panel crashes before the tool can run.  Dify's backend casts these
    # JSON strings back to the declared MCP object/array types at invocation.
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return {"type": "constant", "value": value}


def variable(*selector: str) -> dict[str, Any]:
    return {"type": "variable", "value": list(selector)}


def mixed(value: str) -> dict[str, Any]:
    return {"type": "mixed", "value": value}


def text_input(
    variable_name: str,
    label: str,
    *,
    required: bool = True,
    paragraph: bool = False,
    max_length: int = 4096,
) -> dict[str, Any]:
    return {
        "variable": variable_name,
        "label": label,
        "type": "paragraph" if paragraph else "text-input",
        "required": required,
        "max_length": max_length,
        "options": [],
    }


def select_input(
    variable_name: str,
    label: str,
    options: Sequence[str],
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "variable": variable_name,
        "label": label,
        "type": "select",
        "required": required,
        "max_length": 128,
        "options": list(options),
    }


def common_stage_inputs(*extra: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        text_input("run_id", "运行 ID", max_length=128),
        select_input("execution_mode", "执行模式", ["mock"]),
        *extra,
    ]


@dataclass(slots=True)
class GraphBuilder:
    start_id: str
    nodes: list[dict[str, Any]] = field(init=False, default_factory=list)
    edges: list[dict[str, Any]] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.nodes.clear()
        self.edges.clear()

    def _node(
        self,
        node_id: str,
        node_type: str,
        title: str,
        data: Mapping[str, Any],
        *,
        x: float,
        y: float,
        height: int | None = None,
    ) -> str:
        payload = {
            "desc": "",
            "selected": False,
            "title": title,
            "type": node_type,
            **copy.deepcopy(dict(data)),
        }
        node_height = height or {
            "start": 150,
            "tool": 98,
            "if-else": 150,
            "variable-aggregator": 108,
            "end": 120,
        }[node_type]
        self.nodes.append(
            {
                "data": payload,
                "height": node_height,
                "id": node_id,
                "position": {"x": x, "y": y},
                "positionAbsolute": {"x": x, "y": y},
                "selected": False,
                "sourcePosition": "right",
                "targetPosition": "left",
                "type": "custom",
                "width": 270,
            }
        )
        return node_id

    def start(self, inputs: Sequence[dict[str, Any]], *, x: float = 0, y: float = 220) -> str:
        return self._node(
            self.start_id,
            "start",
            "开始",
            {"variables": list(inputs)},
            x=x,
            y=y,
            height=max(120, 70 + len(inputs) * 42),
        )

    def tool(
        self,
        node_id: str,
        tool_name: str,
        title: str,
        tool_parameters: Mapping[str, Any],
        *,
        x: float,
        y: float,
        provider_type: str = "mcp",
        provider_id: str = MCP_PROVIDER_TOKEN,
    ) -> str:
        description = STEP_TOOLS.get(tool_name)
        desc = description.description if description else "Dify orchestration boundary tool."
        return self._node(
            node_id,
            "tool",
            title,
            {
                "desc": f"{tool_name} · {desc}",
                "provider_id": provider_id,
                "provider_name": provider_id,
                "provider_type": provider_type,
                "tool_configurations": {},
                "tool_label": title,
                "tool_name": tool_name,
                "tool_node_version": "2",
                "tool_parameters": copy.deepcopy(dict(tool_parameters)),
            },
            x=x,
            y=y,
        )

    def step_tool(
        self,
        node_id: str,
        tool_name: str,
        title: str,
        *,
        step_id: str | None = None,
        attempt: int = 1,
        scope: str = "wt",
        parameters: dict[str, Any] | None = None,
        x: float,
        y: float,
    ) -> str:
        spec = STEP_TOOLS[tool_name]
        params = {
            "schema_version": constant("0.1.0"),
            "workflow_version": constant("T01-v10"),
            "run_id": variable(self.start_id, "run_id"),
            "step_id": constant(step_id or spec.step_id),
            "node_id": constant(node_id),
            "attempt": constant(attempt),
            "scope": constant(scope),
            # Dify 1.17 treats enum/select MCP parameters as constants in the
            # editor. A variable binding survives import but is normalized to
            # an empty string at runtime. This debug workflow intentionally
            # supports only mock mode, so pin the backend contract explicitly.
            "execution_mode": constant("mock"),
            "parameters": parameters or constant({}),
            "input_artifacts": constant([]),
            "context": constant({}),
            "idempotency_key": mixed(
                f"{{{{#{self.start_id}.run_id#}}}}:{node_id}:attempt-{attempt}"
            ),
        }
        return self.tool(node_id, tool_name, title, params, x=x, y=y)

    def workflow_tool(
        self,
        node_id: str,
        workflow_name: str,
        title: str,
        tool_parameters: Mapping[str, Any],
        *,
        x: float,
        y: float,
    ) -> str:
        return self.tool(
            node_id,
            workflow_tool_token(workflow_name),
            title,
            tool_parameters,
            x=x,
            y=y,
            provider_type="workflow",
            provider_id=workflow_provider_token(workflow_name),
        )

    def if_else(
        self,
        node_id: str,
        title: str,
        selector: Sequence[str],
        expected: Any,
        *,
        x: float,
        y: float,
        var_type: str = "string",
    ) -> str:
        return self._node(
            node_id,
            "if-else",
            title,
            {
                "_targetBranches": [
                    {"id": "true", "name": "IF"},
                    {"id": "false", "name": "ELSE"},
                ],
                "logical_operator": "and",
                "cases": [
                    {
                        "case_id": "true",
                        "logical_operator": "and",
                        "conditions": [
                            {
                                "id": f"{node_id}_condition",
                                "variable_selector": list(selector),
                                "comparison_operator": "is",
                                "value": expected,
                                "varType": var_type,
                            }
                        ],
                    }
                ],
            },
            x=x,
            y=y,
        )

    def aggregator(
        self,
        node_id: str,
        title: str,
        selectors: Sequence[Sequence[str]],
        *,
        output_type: str,
        x: float,
        y: float,
    ) -> str:
        return self._node(
            node_id,
            "variable-aggregator",
            title,
            {
                "advanced_settings": {"group_enabled": False, "groups": []},
                "output_type": output_type,
                "variables": [list(value) for value in selectors],
            },
            x=x,
            y=y,
        )

    def end(
        self,
        node_id: str,
        outputs: Mapping[str, Sequence[str]],
        *,
        x: float,
        y: float,
    ) -> str:
        return self._node(
            node_id,
            "end",
            "结束",
            {
                "outputs": [
                    {"variable": name, "value_selector": list(selector)}
                    for name, selector in outputs.items()
                ]
            },
            x=x,
            y=y,
            height=max(110, 70 + len(outputs) * 36),
        )

    def edge(self, source: str, target: str, source_handle: str = "source") -> None:
        edge_id = f"edge_{source}_{source_handle}_{target}"
        self.edges.append(
            {
                "data": {
                    "sourceType": self.node_type(source),
                    "targetType": self.node_type(target),
                },
                "id": edge_id,
                "source": source,
                "sourceHandle": source_handle,
                "target": target,
                "targetHandle": "target",
                "type": "custom",
                "zIndex": 0,
            }
        )

    def node_type(self, node_id: str) -> str:
        for node in self.nodes:
            if node["id"] == node_id:
                return str(node["data"]["type"])
        raise KeyError(node_id)

    def graph(self) -> dict[str, Any]:
        return {
            "edges": self.edges,
            "nodes": self.nodes,
            "viewport": {"x": 0, "y": 0, "zoom": 0.55},
        }


def _features() -> dict[str, Any]:
    return {
        "file_upload": {
            "allowed_file_extensions": [],
            "allowed_file_types": [],
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


def _workflow_document(
    name: str,
    description: str,
    graph: GraphBuilder,
    *,
    icon: str,
) -> dict[str, Any]:
    return {
        "app": {
            "description": description,
            "icon": icon,
            "icon_background": "#E8F5E9",
            "mode": "workflow",
            "name": name,
            "use_icon_as_answer_icon": False,
        },
        "dependencies": [],
        "kind": "app",
        "version": DSL_VERSION,
        "workflow": {
            "conversation_variables": [],
            "environment_variables": [],
            "features": _features(),
            "graph": graph.graph(),
            "rag_pipeline_variables": [],
        },
    }


def _stage_params(start_id: str, **extra: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "run_id": variable(start_id, "run_id"),
        # Stage workflow inputs expose execution_mode for a stable interface,
        # but Dify's select-to-select variable binding can become blank. The
        # current T01 debug contract permits mock mode only.
        "execution_mode": constant("mock"),
    }
    for key, value in extra.items():
        params[key] = value if isinstance(value, dict) and "type" in value else constant(value)
    return params


def build_phase0() -> dict[str, Any]:
    g = GraphBuilder("P0_START")
    g.start(common_stage_inputs())
    g.step_tool("P0_S07_FETCH", "structure.fetch", "S-07 结构获取", x=320, y=220)
    g.if_else("P0_G_FETCH_FAILED", "结构获取失败?", ["P0_S07_FETCH", "status"], "FAILED", x=640, y=220)
    g.step_tool(
        "P0_G_EXISTING",
        "t01.route_existing_structure",
        "已有结构路由",
        parameters=variable("P0_S07_FETCH", "data"),
        x=960,
        y=340,
    )
    g.if_else("P0_IF_PREDICT", "需要结构预测?", ["P0_G_EXISTING", "data", "route"], "S-08", x=1280, y=340)
    g.step_tool("P0_S08_PREDICT", "structure.predict", "S-08 结构预测", x=1600, y=180)
    g.step_tool("P0_S09_QUALITY_PRED", "structure.assess_quality", "S-09 预测结构质量", x=1920, y=180)
    g.step_tool("P0_S09_QUALITY_EXIST", "structure.assess_quality", "S-09 已有结构质量", x=1600, y=500)
    g.aggregator(
        "P0_QUALITY_JOIN",
        "结构质量汇合",
        [["P0_S09_QUALITY_PRED", "data"], ["P0_S09_QUALITY_EXIST", "data"]],
        output_type="object",
        x=2240,
        y=340,
    )
    g.step_tool("P0_S04_TOPOLOGY", "topology.predict", "S-04 拓扑预测", x=2560, y=340)
    g.step_tool(
        "P0_G_RSA",
        "t01.route_rsa",
        "结构低置信 RSA 门控",
        # Dify variable-aggregator exposes only its declared `output` variable
        # to downstream selectors. Aggregate S-09 `data` directly instead of
        # trying to address an undeclared nested `output.data` selector.
        parameters=variable("P0_QUALITY_JOIN", "output"),
        x=2880,
        y=340,
    )
    g.if_else("P0_IF_RSA", "执行 S-11?", ["P0_G_RSA", "data", "route"], "RUN_S11", x=3200, y=340)
    g.step_tool("P0_S11_RSA", "structure.compute_rsa", "S-11 RSA", x=3520, y=180)
    g.aggregator(
        "P0_RSA_JOIN",
        "RSA 路径汇合",
        [["P0_S11_RSA", "json"], ["P0_G_RSA", "json"]],
        output_type="object",
        x=3840,
        y=340,
    )
    g.step_tool("P0_G_BACTERIA", "t01.route_pathogen_type", "细菌分支门控", x=4160, y=340)
    g.if_else("P0_IF_BACTERIA", "执行 S-06?", ["P0_G_BACTERIA", "data", "route"], "RUN_S06", x=4480, y=340)
    g.step_tool("P0_S06_LOCALIZE", "localization.predict_bacteria", "S-06 细菌定位", x=4800, y=180)
    g.aggregator(
        "P0_RESULT_JOIN",
        "阶段0结果汇合",
        [["P0_S06_LOCALIZE", "json"], ["P0_G_BACTERIA", "json"], ["P0_S07_FETCH", "json"]],
        output_type="object",
        x=5120,
        y=340,
    )
    g.aggregator(
        "P0_STATUS_JOIN",
        "阶段0状态汇合",
        [["P0_S06_LOCALIZE", "status"], ["P0_G_BACTERIA", "status"], ["P0_S07_FETCH", "status"]],
        output_type="string",
        x=5440,
        y=340,
    )
    g.end(
        "P0_END",
        {
            "run_id": ["P0_START", "run_id"],
            "stage_status": ["P0_STATUS_JOIN", "output"],
            "stage_result": ["P0_RESULT_JOIN", "output"],
            "structure_quality": ["P0_QUALITY_JOIN", "output"],
            "topology": ["P0_S04_TOPOLOGY", "json"],
        },
        x=5760,
        y=340,
    )
    g.edge("P0_START", "P0_S07_FETCH")
    g.edge("P0_S07_FETCH", "P0_G_FETCH_FAILED")
    g.edge("P0_G_FETCH_FAILED", "P0_RESULT_JOIN", "true")
    g.edge("P0_G_FETCH_FAILED", "P0_G_EXISTING", "false")
    g.edge("P0_G_EXISTING", "P0_IF_PREDICT")
    g.edge("P0_IF_PREDICT", "P0_S08_PREDICT", "true")
    g.edge("P0_S08_PREDICT", "P0_S09_QUALITY_PRED")
    g.edge("P0_S09_QUALITY_PRED", "P0_QUALITY_JOIN")
    g.edge("P0_IF_PREDICT", "P0_S09_QUALITY_EXIST", "false")
    g.edge("P0_S09_QUALITY_EXIST", "P0_QUALITY_JOIN")
    g.edge("P0_QUALITY_JOIN", "P0_S04_TOPOLOGY")
    g.edge("P0_S04_TOPOLOGY", "P0_G_RSA")
    g.edge("P0_G_RSA", "P0_IF_RSA")
    g.edge("P0_IF_RSA", "P0_S11_RSA", "true")
    g.edge("P0_S11_RSA", "P0_RSA_JOIN")
    g.edge("P0_IF_RSA", "P0_RSA_JOIN", "false")
    g.edge("P0_RSA_JOIN", "P0_G_BACTERIA")
    g.edge("P0_G_BACTERIA", "P0_IF_BACTERIA")
    g.edge("P0_IF_BACTERIA", "P0_S06_LOCALIZE", "true")
    g.edge("P0_S06_LOCALIZE", "P0_RESULT_JOIN")
    g.edge("P0_IF_BACTERIA", "P0_RESULT_JOIN", "false")
    g.edge("P0_RESULT_JOIN", "P0_STATUS_JOIN")
    g.edge("P0_STATUS_JOIN", "P0_END")
    return _workflow_document(
        PHASE_NAMES[0],
        "T-01 v10 阶段0调试流程：结构获取、预测、质量、拓扑、RSA与细菌定位。仅编排，不做科学计算。",
        g,
        icon="🧬",
    )


def _derive_phase_debug(document: Mapping[str, Any], phase_index: int) -> dict[str, Any]:
    """Wrap one reviewed stage graph in a standalone, one-click Mock harness."""

    debug_document = copy.deepcopy(dict(document))
    start_id = f"P{phase_index}_START"
    configure_id = f"P{phase_index}D_CONFIGURE_RUN"
    debug_document["app"]["name"] = DEBUG_PHASE_NAMES[phase_index]
    debug_document["app"]["icon"] = "🧪"
    debug_document["app"]["description"] = (
        f"T-01 v10 阶段{phase_index}独立一键调试流程。"
        "自动使用Dify workflow_run_id初始化所选Mock场景；无需手工添加初始化节点或粘贴T-01 JSON。"
        "仅用于调试，不作为Master阶段工具。"
    )

    graph = debug_document["workflow"]["graph"]
    nodes = graph["nodes"]
    edges = graph["edges"]
    nodes_by_id = {node["id"]: node for node in nodes}
    start = nodes_by_id[start_id]

    # Keep stage-specific controls such as P2 entry_mode, but replace the
    # manually supplied run_id/execution_mode pair with a single scenario list.
    stage_specific_inputs = [
        item
        for item in start["data"]["variables"]
        if item["variable"] not in {"run_id", "execution_mode", "scenario_id"}
    ]
    start["data"]["title"] = "开始（选择Mock场景）"
    start["data"]["variables"] = [
        select_input("scenario_id", "Mock 场景", list(SCENARIOS)),
        *stage_specific_inputs,
    ]
    start["height"] = max(120, 70 + len(start["data"]["variables"]) * 42)

    source_run_token = "{{#" + start_id + ".run_id#}}"
    for node in nodes:
        if node["id"] == start_id:
            continue
        node["position"]["x"] += 320
        node["positionAbsolute"]["x"] += 320

        data = node["data"]
        if data.get("type") == "tool" and data.get("tool_name") in STEP_TOOLS:
            parameters = data["tool_parameters"]
            parameters["run_id"] = variable(*SYSTEM_RUN_ID_SELECTOR)
            idempotency = parameters.get("idempotency_key")
            if isinstance(idempotency, dict) and isinstance(idempotency.get("value"), str):
                idempotency["value"] = idempotency["value"].replace(
                    source_run_token,
                    "{{#sys.workflow_run_id#}}",
                )
        elif data.get("type") == "end":
            for output in data["outputs"]:
                if output["variable"] == "run_id":
                    output["value_selector"] = list(SYSTEM_RUN_ID_SELECTOR)

    initializer_builder = GraphBuilder("unused")
    initializer_builder.tool(
        configure_id,
        "mock.configure_run",
        "自动初始化Mock运行",
        {
            "run_id": variable(*SYSTEM_RUN_ID_SELECTOR),
            "scenario_id": variable(start_id, "scenario_id"),
        },
        x=320,
        y=start["position"]["y"],
    )
    nodes.insert(1, initializer_builder.nodes[0])

    original_start_edges = [edge for edge in edges if edge["source"] == start_id]
    if not original_start_edges:
        raise ValueError(f"phase debug source has no Start edge: {start_id}")
    for edge in original_start_edges:
        edge["source"] = configure_id
        edge["data"]["sourceType"] = "tool"
        edge["id"] = f"edge_{configure_id}_{edge['sourceHandle']}_{edge['target']}"
    edges.insert(
        0,
        {
            "data": {"sourceType": "start", "targetType": "tool"},
            "id": f"edge_{start_id}_source_{configure_id}",
            "source": start_id,
            "sourceHandle": "source",
            "target": configure_id,
            "targetHandle": "target",
            "type": "custom",
            "zIndex": 0,
        },
    )
    return debug_document


def build_phase0_debug() -> dict[str, Any]:
    """Backward-compatible entry point for the phase-0 standalone harness."""

    return _derive_phase_debug(build_phase0(), 0)


def build_phase1() -> dict[str, Any]:
    g = GraphBuilder("P1_START")
    g.start(common_stage_inputs())
    full_tools = [
        ("P1_S03_IEDB", "epitope.query_iedb_prior", "S-03 IEDB 既有证据"),
        ("P1_S17_BCELL", "epitope.predict_bcell", "S-17 B细胞表位"),
        ("P1_S18_TCELL", "epitope.predict_tcell", "S-18 T细胞表位"),
        ("P1_S19_MAPS", "epitope.synthesize_maps", "S-19 表位三图"),
        ("P1_S12_GLYCO", "glyco.scan", "S-12 糖基化扫描"),
        ("P1_S23_SAFETY", "safety.assess_triple", "S-23 安全三联筛"),
    ]
    x = 320
    previous = "P1_START"
    for node_id, tool_name, title in full_tools:
        g.step_tool(node_id, tool_name, title, x=x, y=260)
        g.edge(previous, node_id)
        previous = node_id
        x += 320
    g.end(
        "P1_END",
        {"run_id": ["P1_START", "run_id"], "stage_result": ["P1_S23_SAFETY", "json"]},
        x=2240,
        y=260,
    )
    g.edge("P1_S23_SAFETY", "P1_END")
    return _workflow_document(
        PHASE_NAMES[1],
        "T-01 v10 阶段1调试流程：既有表位、B/T细胞表位、三图、糖基化与安全三联筛。",
        g,
        icon="🛡️",
    )


def build_phase2() -> dict[str, Any]:
    g = GraphBuilder("P2_START")
    g.start(common_stage_inputs(select_input("entry_mode", "入口模式", ["full", "context_only"])))
    g.if_else("P2_IF_CONTEXT", "仅补跑 S-16?", ["P2_START", "entry_mode"], "context_only", x=320, y=240)
    g.edge("P2_START", "P2_IF_CONTEXT")
    full_tools = [
        ("P2_S13_HOMOLOGS", "conservation.collect_homologs", "S-13 同源收集"),
        ("P2_S14_CONSERVATION", "conservation.compute", "S-14 保守性计算"),
        ("P2_S15_REGIONS", "conservation.extract_regions", "S-15 保守区提取"),
        ("P2_R11_TYPING", "conservation.analyze_within_type", "R-11 分型内分析"),
        ("P2_S16_DOMAINS_FULL", "domain.identify", "S-16 功能域识别"),
    ]
    previous = "P2_IF_CONTEXT"
    x = 640
    for node_id, tool_name, title in full_tools:
        params = variable("P2_S13_HOMOLOGS", "data") if node_id == "P2_R11_TYPING" else None
        g.step_tool(node_id, tool_name, title, parameters=params, x=x, y=420)
        g.edge(previous, node_id, "false" if previous == "P2_IF_CONTEXT" else "source")
        previous = node_id
        x += 320
    g.step_tool("P2_S16_DOMAINS_CONTEXT", "domain.identify", "0b 补跑 S-16", x=960, y=60)
    g.edge("P2_IF_CONTEXT", "P2_S16_DOMAINS_CONTEXT", "true")
    g.aggregator(
        "P2_RESULT_JOIN",
        "阶段2结果汇合",
        [["P2_S16_DOMAINS_FULL", "json"], ["P2_S16_DOMAINS_CONTEXT", "json"]],
        output_type="object",
        x=2240,
        y=240,
    )
    g.edge("P2_S16_DOMAINS_FULL", "P2_RESULT_JOIN")
    g.edge("P2_S16_DOMAINS_CONTEXT", "P2_RESULT_JOIN")
    g.end(
        "P2_END",
        {"run_id": ["P2_START", "run_id"], "stage_result": ["P2_RESULT_JOIN", "output"]},
        x=2560,
        y=240,
    )
    g.edge("P2_RESULT_JOIN", "P2_END")
    return _workflow_document(
        PHASE_NAMES[2],
        "T-01 v10 阶段2调试流程；上下文入口只补跑S-16，完整入口执行S-13至S-16。",
        g,
        icon="🧭",
    )


def build_phase3() -> dict[str, Any]:
    g = GraphBuilder("P3_START")
    g.start(common_stage_inputs())
    tools = [
        ("P3_S36_SOLUBILITY", "developability.predict_solubility", "S-36 溶解度"),
        ("P3_S36A_EXPRESSION", "developability.compute_expressibility", "S-36a 表达量"),
        ("P3_S37_AGGREGATION", "developability.predict_aggregation", "S-37 聚集"),
        ("P3_S38_PH", "developability.predict_ph_stability", "S-38 pH稳定"),
        ("P3_S39_TAG", "developability.assess_tag_exposure", "S-39 标签暴露"),
        ("P3_S40_BASELINE", "developability.assess", "S-40 WT综合评估"),
    ]
    previous = "P3_START"
    x = 320
    for node_id, tool_name, title in tools:
        g.step_tool(node_id, tool_name, title, x=x, y=300)
        g.edge(previous, node_id)
        previous = node_id
        x += 320
    g.step_tool(
        "P3_R57_GATE",
        "t01.evaluate_design_applicability",
        "R-57 设计适用域门控",
        parameters=variable("P3_S40_BASELINE", "data"),
        x=2240,
        y=300,
    )
    g.edge("P3_S40_BASELINE", "P3_R57_GATE")
    g.if_else("P3_IF_CONTINUE", "允许继续设计?", ["P3_R57_GATE", "data", "route"], "CONTINUE", x=2560, y=300)
    g.edge("P3_R57_GATE", "P3_IF_CONTINUE")
    g.step_tool(
        "B4_GATE",
        "t01.route_stability_rescue",
        "分支4触发门控",
        parameters=variable("P3_S40_BASELINE", "data"),
        x=2880,
        y=120,
    )
    g.edge("P3_IF_CONTINUE", "B4_GATE", "true")
    g.if_else("B4_IF_RUN", "执行稳定性补救?", ["B4_GATE", "data", "route"], "RUN_BRANCH4", x=3200, y=120)
    g.edge("B4_GATE", "B4_IF_RUN")
    g.step_tool("B4_S31_SCAN", "stability.scan_mutations", "分支4 S-31 饱和扫描", scope="rescue", x=3520, y=0)
    g.step_tool("B4_TOP3_SCREEN", "stability.screen_rescue_top3", "Top3 序列版粗筛", scope="rescue", x=3840, y=0)
    g.if_else("B4_IF_SUCCESS", "补救成功?", ["B4_TOP3_SCREEN", "data", "rescue_success"], True, var_type="boolean", x=4160, y=0)
    g.step_tool("B4_S08_PREDICT", "structure.predict", "分支4 S-08 结构预测", scope="rescue", x=4480, y=-120)
    g.step_tool("B4_S11_RSA", "structure.compute_rsa", "分支4 S-11 RSA", scope="rescue", x=4800, y=-120)
    g.step_tool("B4_S09_QUALITY", "structure.assess_quality", "分支4 S-09 质量重评", scope="rescue", x=5120, y=-120)
    g.edge("B4_IF_RUN", "B4_S31_SCAN", "true")
    g.edge("B4_S31_SCAN", "B4_TOP3_SCREEN")
    g.edge("B4_TOP3_SCREEN", "B4_IF_SUCCESS")
    g.edge("B4_IF_SUCCESS", "B4_S08_PREDICT", "true")
    g.edge("B4_S08_PREDICT", "B4_S11_RSA")
    g.edge("B4_S11_RSA", "B4_S09_QUALITY")
    g.aggregator(
        "P3_RESULT_JOIN",
        "R-57与分支4结果汇合",
        [
            ["B4_S09_QUALITY", "json"],
            ["B4_TOP3_SCREEN", "json"],
            ["B4_GATE", "json"],
            ["P3_R57_GATE", "json"],
        ],
        output_type="object",
        x=5440,
        y=300,
    )
    g.edge("P3_IF_CONTINUE", "P3_RESULT_JOIN", "false")
    g.edge("B4_IF_RUN", "P3_RESULT_JOIN", "false")
    g.edge("B4_IF_SUCCESS", "P3_RESULT_JOIN", "false")
    g.edge("B4_S09_QUALITY", "P3_RESULT_JOIN")
    g.end(
        "P3_END",
        {
            "run_id": ["P3_START", "run_id"],
            "stage_result": ["P3_R57_GATE", "json"],
            # MCP structured output exposes `json` as an array in Dify 1.17.
            # Export the backend route separately so a parent workflow can
            # branch on a scalar without attempting to traverse that array.
            "stage_route": ["P3_R57_GATE", "data", "route"],
            "branch4_result": ["P3_RESULT_JOIN", "output"],
        },
        x=5760,
        y=300,
    )
    g.edge("P3_RESULT_JOIN", "P3_END")
    return _workflow_document(
        PHASE_NAMES[3],
        "T-01 v10 阶段3、R-57与分支4调试流程。R-57跳过时不进入稳定性补救。",
        g,
        icon="📊",
    )


def build_phase4() -> dict[str, Any]:
    g = GraphBuilder("P4_START")
    g.start(common_stage_inputs())
    y = 300
    g.step_tool("P4_S27_DESIGN_A1", "design.generate_mutations", "S-27 设计 32", attempt=1, parameters=constant({"design_count": 32}), x=320, y=y)
    g.step_tool("P4_S28_VALIDATE_A1", "design.validate", "S-28 验证 第1轮", attempt=1, parameters=variable("P4_S27_DESIGN_A1", "data"), x=640, y=y)
    g.step_tool("P4_RETRY_GATE_A1", "t01.evaluate_design_retry", "重试门控 第1轮", attempt=1, parameters=variable("P4_S28_VALIDATE_A1", "data"), x=960, y=y)
    g.if_else("P4_IF_RETRY_A1", "第1轮需要重试?", ["P4_RETRY_GATE_A1", "data", "route"], "RETRY", x=1280, y=y)
    g.step_tool("P4_S29_CONSERVATIVE_A1", "design.check_conservative_mutations", "S-29 保守检查 第1轮", attempt=1, parameters=variable("P4_S28_VALIDATE_A1", "data"), x=1600, y=80)
    g.step_tool("P4_S27_DESIGN_A2", "design.generate_mutations", "S-27 设计 48", attempt=2, parameters=constant({"design_count": 48}), x=1600, y=520)
    g.step_tool("P4_S28_VALIDATE_A2", "design.validate", "S-28 验证 第2轮", attempt=2, parameters=variable("P4_S27_DESIGN_A2", "data"), x=1920, y=520)
    g.step_tool("P4_RETRY_GATE_A2", "t01.evaluate_design_retry", "重试门控 第2轮", attempt=2, parameters=variable("P4_S28_VALIDATE_A2", "data"), x=2240, y=520)
    g.if_else("P4_IF_RETRY_A2", "第2轮需要重试?", ["P4_RETRY_GATE_A2", "data", "route"], "RETRY", x=2560, y=520)
    g.step_tool("P4_S29_CONSERVATIVE_A2", "design.check_conservative_mutations", "S-29 保守检查 第2轮", attempt=2, parameters=variable("P4_S28_VALIDATE_A2", "data"), x=2880, y=300)
    g.step_tool("P4_S27_DESIGN_A3", "design.generate_mutations", "S-27 设计 64", attempt=3, parameters=constant({"design_count": 64}), x=2880, y=740)
    g.step_tool("P4_S28_VALIDATE_A3", "design.validate", "S-28 验证 第3轮", attempt=3, parameters=variable("P4_S27_DESIGN_A3", "data"), x=3200, y=740)
    g.step_tool("P4_RETRY_GATE_A3", "t01.evaluate_design_retry", "重试门控 第3轮", attempt=3, parameters=variable("P4_S28_VALIDATE_A3", "data"), x=3520, y=740)
    g.if_else("P4_IF_EXHAUSTED", "三轮全部淘汰?", ["P4_RETRY_GATE_A3", "data", "route"], "EXHAUSTED", x=3840, y=740)
    g.step_tool("P4_S29_CONSERVATIVE_A3", "design.check_conservative_mutations", "S-29 保守检查 第3轮", attempt=3, parameters=variable("P4_S28_VALIDATE_A3", "data"), x=4160, y=520)
    g.aggregator(
        "P4_RESULT_JOIN",
        "设计轮次结果汇合",
        [
            ["P4_RETRY_GATE_A3", "json"],
            ["P4_RETRY_GATE_A2", "json"],
            ["P4_RETRY_GATE_A1", "json"],
        ],
        output_type="object",
        x=4480,
        y=360,
    )
    g.aggregator(
        "P4_ROUTE_JOIN",
        "最终设计路由汇合",
        [
            ["P4_RETRY_GATE_A3", "data", "route"],
            ["P4_RETRY_GATE_A2", "data", "route"],
            ["P4_RETRY_GATE_A1", "data", "route"],
        ],
        output_type="string",
        x=4800,
        y=360,
    )
    g.end(
        "P4_END",
        {
            "run_id": ["P4_START", "run_id"],
            "stage_result": ["P4_RESULT_JOIN", "output"],
            "stage_route": ["P4_ROUTE_JOIN", "output"],
        },
        x=5120,
        y=360,
    )
    for source, target in [
        ("P4_START", "P4_S27_DESIGN_A1"),
        ("P4_S27_DESIGN_A1", "P4_S28_VALIDATE_A1"),
        ("P4_S28_VALIDATE_A1", "P4_RETRY_GATE_A1"),
        ("P4_RETRY_GATE_A1", "P4_IF_RETRY_A1"),
        ("P4_S27_DESIGN_A2", "P4_S28_VALIDATE_A2"),
        ("P4_S28_VALIDATE_A2", "P4_RETRY_GATE_A2"),
        ("P4_RETRY_GATE_A2", "P4_IF_RETRY_A2"),
        ("P4_S27_DESIGN_A3", "P4_S28_VALIDATE_A3"),
        ("P4_S28_VALIDATE_A3", "P4_RETRY_GATE_A3"),
        ("P4_RETRY_GATE_A3", "P4_IF_EXHAUSTED"),
    ]:
        g.edge(source, target)
    g.edge("P4_IF_RETRY_A1", "P4_S27_DESIGN_A2", "true")
    g.edge("P4_IF_RETRY_A1", "P4_S29_CONSERVATIVE_A1", "false")
    g.edge("P4_S29_CONSERVATIVE_A1", "P4_RESULT_JOIN")
    g.edge("P4_IF_RETRY_A2", "P4_S27_DESIGN_A3", "true")
    g.edge("P4_IF_RETRY_A2", "P4_S29_CONSERVATIVE_A2", "false")
    g.edge("P4_S29_CONSERVATIVE_A2", "P4_RESULT_JOIN")
    g.edge("P4_IF_EXHAUSTED", "P4_RESULT_JOIN", "true")
    g.edge("P4_IF_EXHAUSTED", "P4_S29_CONSERVATIVE_A3", "false")
    g.edge("P4_S29_CONSERVATIVE_A3", "P4_RESULT_JOIN")
    g.edge("P4_RESULT_JOIN", "P4_ROUTE_JOIN")
    g.edge("P4_ROUTE_JOIN", "P4_END")
    return _workflow_document(
        PHASE_NAMES[4],
        "T-01 v10 阶段4调试流程：32设计首轮，全淘汰后仅重试48与64两轮。",
        g,
        icon="🧪",
    )


def build_phase5() -> dict[str, Any]:
    g = GraphBuilder("P5_START")
    g.start(common_stage_inputs())
    chain = [
        ("P5_VARIANT_REASSESS", "variant.reassess_developability", "step19 变体批量重评", "variant"),
        ("P5_S23_SAFETY", "safety.assess_triple", "S-23 变体安全复评", "variant"),
        ("P5_S12_GLYCO", "glyco.scan", "S-12 变体glyco复扫", "variant"),
        ("P5_EPITOPE_L1_L4", "epitope.validate_presentation", "step19 四层表位验证", "variant"),
        ("P5_S40_COARSE", "developability.assess", "S-40 五维粗评", "variant_coarse"),
        ("P5_SCORE_POOL", "t01.select_stability_score_pool", "step19b score_pool", "variant"),
    ]
    previous = "P5_START"
    x = 320
    for node_id, tool_name, title, scope in chain:
        g.step_tool(node_id, tool_name, title, scope=scope, x=x, y=300)
        g.edge(previous, node_id)
        previous = node_id
        x += 320
    g.if_else("P5_IF_SCORE", "执行变体FoldX?", ["P5_SCORE_POOL", "data", "route"], "RUN_S31_VARIANT", x=2240, y=300)
    g.edge("P5_SCORE_POOL", "P5_IF_SCORE")
    g.step_tool("P5_S31_VARIANT_DDG", "stability.score_variants", "S-31 变体ddG", scope="variant", parameters=variable("P5_SCORE_POOL", "data"), x=2560, y=80)
    g.step_tool("P5_S40_FINAL_DDG", "developability.assess", "S-40 六维终评", scope="variant_final", parameters=variable("P5_S31_VARIANT_DDG", "data"), x=2880, y=80)
    g.step_tool("P5_STEP20_RANK_DDG", "ranking.rank_variants", "step20 排序链", scope="variant", parameters=variable("P5_S40_FINAL_DDG", "data"), x=3200, y=80)
    g.step_tool("P5_S40_FINAL_NO_DDG", "developability.assess", "S-40 无ddG终评", scope="variant_final", parameters=variable("P5_S40_COARSE", "data"), x=2560, y=520)
    g.step_tool("P5_STEP20_RANK_NO_DDG", "ranking.rank_variants", "step20 降级排序链", scope="variant", parameters=variable("P5_S40_FINAL_NO_DDG", "data"), x=2880, y=520)
    g.edge("P5_IF_SCORE", "P5_S31_VARIANT_DDG", "true")
    g.edge("P5_S31_VARIANT_DDG", "P5_S40_FINAL_DDG")
    g.edge("P5_S40_FINAL_DDG", "P5_STEP20_RANK_DDG")
    g.edge("P5_IF_SCORE", "P5_S40_FINAL_NO_DDG", "false")
    g.edge("P5_S40_FINAL_NO_DDG", "P5_STEP20_RANK_NO_DDG")
    g.aggregator(
        "P5_RESULT_JOIN",
        "排序结果汇合",
        [["P5_STEP20_RANK_DDG", "json"], ["P5_STEP20_RANK_NO_DDG", "json"]],
        output_type="object",
        x=3520,
        y=300,
    )
    g.edge("P5_STEP20_RANK_DDG", "P5_RESULT_JOIN")
    g.edge("P5_STEP20_RANK_NO_DDG", "P5_RESULT_JOIN")
    g.end("P5_END", {"run_id": ["P5_START", "run_id"], "stage_result": ["P5_RESULT_JOIN", "output"]}, x=3840, y=300)
    g.edge("P5_RESULT_JOIN", "P5_END")
    return _workflow_document(
        PHASE_NAMES[5],
        "T-01 v10 阶段5调试流程：变体重评、四层表位验证、19b成本门控、Hard Filter/Pareto排序。",
        g,
        icon="🏁",
    )


def build_phase6() -> dict[str, Any]:
    g = GraphBuilder("P6_START")
    g.start(common_stage_inputs())
    g.step_tool("P6_S30_CODON", "sequence.optimize_codons", "S-30 密码子优化", x=320, y=260)
    g.step_tool("P6_S31_WT_SCAN", "stability.scan_mutations", "S-31 WT稳定性扫描", scope="wt_scan", x=640, y=260)
    g.step_tool("P6_MD_GATE", "t01.evaluate_md_gate", "MD门控", x=960, y=260)
    g.if_else("P6_IF_MD", "执行S-32?", ["P6_MD_GATE", "data", "route"], "RUN_S32", x=1280, y=260)
    g.step_tool("P6_S32_MD", "dynamics.run_md_validation", "S-32 top3 MD", scope="top3", x=1600, y=80)
    g.aggregator(
        "P6_RESULT_JOIN",
        "MD路径汇合",
        [["P6_S32_MD", "json"], ["P6_MD_GATE", "json"]],
        output_type="object",
        x=1920,
        y=260,
    )
    for source, target in [
        ("P6_START", "P6_S30_CODON"),
        ("P6_S30_CODON", "P6_S31_WT_SCAN"),
        ("P6_S31_WT_SCAN", "P6_MD_GATE"),
        ("P6_MD_GATE", "P6_IF_MD"),
    ]:
        g.edge(source, target)
    g.edge("P6_IF_MD", "P6_S32_MD", "true")
    g.edge("P6_S32_MD", "P6_RESULT_JOIN")
    g.edge("P6_IF_MD", "P6_RESULT_JOIN", "false")
    g.end("P6_END", {"run_id": ["P6_START", "run_id"], "stage_result": ["P6_RESULT_JOIN", "output"]}, x=2240, y=260)
    g.edge("P6_RESULT_JOIN", "P6_END")
    return _workflow_document(
        PHASE_NAMES[6],
        "T-01 v10 阶段6调试流程：条件密码子优化、WT扫描与严格MD门控。",
        g,
        icon="⏱️",
    )


def build_phase7() -> dict[str, Any]:
    g = GraphBuilder("P7_START")
    g.start(common_stage_inputs())
    g.step_tool("P7_S42_ASSEMBLE", "output.assemble_candidate_json", "S-42 Candidate组装", x=320, y=300)
    g.step_tool("P7_VIS_GATE", "t01.route_visualization", "可视化门控", x=640, y=300)
    g.if_else("P7_IF_VIS", "执行C29/C30?", ["P7_VIS_GATE", "data", "route"], "RUN_C29_C30", x=960, y=300)
    g.step_tool("P7_C29_VISUAL", "output.render_comparison_report", "C29 对比报告", x=1280, y=80)
    g.step_tool("P7_C30_EXPLAIN", "output.prepare_explanation", "C30 后端事实摘要", x=1600, y=80)
    g.aggregator(
        "P7_VIS_JOIN",
        "展示路径汇合",
        [["P7_C30_EXPLAIN", "json"], ["P7_S42_ASSEMBLE", "json"]],
        output_type="object",
        x=1920,
        y=300,
    )
    g.step_tool(
        "P7_STEP26_HANDOFF",
        "t01.route_handoff",
        "step26 三路交接",
        parameters=variable("P7_S42_ASSEMBLE", "data", "candidate"),
        x=2240,
        y=300,
    )
    g.if_else("P7_IF_BEST", "best存在?", ["P7_STEP26_HANDOFF", "data", "route"], "BEST", x=2560, y=300)
    g.if_else("P7_IF_SKIPPED", "设计跳过?", ["P7_STEP26_HANDOFF", "data", "route"], "DESIGN_SKIPPED", x=2880, y=520)
    branches = [
        ("BEST", "P7_S43_BEST", "P7_S44_BEST", 2880, 40, "variant"),
        ("SKIP", "P7_S43_SKIP", "P7_S44_SKIP", 3200, 400, "wt_skipped"),
        ("FAIL", "P7_S43_FAIL", "P7_S44_FAIL", 3200, 700, "wt_failure"),
    ]
    for label, s43, s44, x, y, scope in branches:
        g.step_tool(s43, "handoff.assemble_agent_c", f"S-43 {label}交接组装", scope=scope, x=x, y=y)
        g.step_tool(s44, "handoff.deliver_agent_c", f"S-44 {label}交付", scope=scope, x=x + 320, y=y)
        g.edge(s43, s44)
    g.aggregator(
        "P7_RESULT_JOIN",
        "三路交付结果汇合",
        [["P7_S44_BEST", "json"], ["P7_S44_SKIP", "json"], ["P7_S44_FAIL", "json"]],
        output_type="object",
        x=3840,
        y=300,
    )
    g.edge("P7_START", "P7_S42_ASSEMBLE")
    g.edge("P7_S42_ASSEMBLE", "P7_VIS_GATE")
    g.edge("P7_VIS_GATE", "P7_IF_VIS")
    g.edge("P7_IF_VIS", "P7_C29_VISUAL", "true")
    g.edge("P7_C29_VISUAL", "P7_C30_EXPLAIN")
    g.edge("P7_C30_EXPLAIN", "P7_VIS_JOIN")
    g.edge("P7_IF_VIS", "P7_VIS_JOIN", "false")
    g.edge("P7_VIS_JOIN", "P7_STEP26_HANDOFF")
    g.edge("P7_STEP26_HANDOFF", "P7_IF_BEST")
    g.edge("P7_IF_BEST", "P7_S43_BEST", "true")
    g.edge("P7_IF_BEST", "P7_IF_SKIPPED", "false")
    g.edge("P7_IF_SKIPPED", "P7_S43_SKIP", "true")
    g.edge("P7_IF_SKIPPED", "P7_S43_FAIL", "false")
    for _, _, s44, _, _, _ in branches:
        g.edge(s44, "P7_RESULT_JOIN")
    g.end(
        "P7_END",
        {
            "run_id": ["P7_START", "run_id"],
            "stage_result": ["P7_RESULT_JOIN", "output"],
            "candidate": ["P7_S42_ASSEMBLE", "data", "candidate"],
            "handoff": ["P7_STEP26_HANDOFF", "json"],
        },
        x=4160,
        y=300,
    )
    g.edge("P7_RESULT_JOIN", "P7_END")
    return _workflow_document(
        PHASE_NAMES[7],
        "T-01 v10 阶段7调试流程：Candidate、可选展示、step26三路分叉与Agent C交接。C30仅返回后端事实。",
        g,
        icon="📦",
    )


def build_master() -> dict[str, Any]:
    g = GraphBuilder("T01_START")
    g.start(
        [
            text_input("run_id", "运行 ID", max_length=128),
            select_input("scenario_id", "Mock 场景", list(SCENARIOS)),
            text_input("t01_input_json", "T-01 输入 JSON", paragraph=True, max_length=65535),
            select_input("execution_mode", "执行模式", ["mock"]),
        ],
        y=380,
    )
    g.tool(
        "T01_CONFIGURE_RUN",
        "mock.configure_run_from_json",
        "初始化Mock运行",
        {
            "run_id": variable("T01_START", "run_id"),
            "scenario_id": variable("T01_START", "scenario_id"),
            "t01_input_json": variable("T01_START", "t01_input_json"),
        },
        x=320,
        y=380,
    )
    common_xy = [(640, 380), (960, 380), (1280, 380), (1600, 380), (1920, 380)]
    g.step_tool("T01_VALIDATE_REQUEST", "t01.validate_request", "输入契约校验", x=common_xy[0][0], y=common_xy[0][1])
    g.if_else("T01_IF_INPUT_REQUIRED", "需要补充输入?", ["T01_VALIDATE_REQUEST", "status"], "WAITING_USER", x=common_xy[1][0], y=common_xy[1][1])
    g.step_tool("T01_G00_LENGTH", "t01.evaluate_length_guard", "长度守卫", x=common_xy[2][0], y=common_xy[2][1])
    g.if_else("T01_IF_LENGTH_HALT", "长度门控停止?", ["T01_G00_LENGTH", "data", "route"], "HALT", x=common_xy[3][0], y=common_xy[3][1])
    g.step_tool("T01_G01_CONTEXT", "t01.route_context_scores", "0b上下文路由", x=common_xy[4][0], y=common_xy[4][1])
    g.if_else("T01_IF_CONTEXT_HIGH", "高置信上下文?", ["T01_G01_CONTEXT", "data", "route"], "HIGH", x=2240, y=380)
    g.if_else("T01_IF_CONTEXT_NONHIGH", "非高置信上下文?", ["T01_G01_CONTEXT", "data", "route"], "NON_HIGH", x=2560, y=620)
    g.step_tool("T01_0B_INJECT_HIGH", "t01.inject_context_scores", "0b高置信注入", x=2560, y=80)
    g.workflow_tool("T01_P2_CONTEXT_HIGH", PHASE_NAMES[2], "P2补跑S-16（HIGH）", _stage_params("T01_START", entry_mode="context_only"), x=2880, y=80)
    g.step_tool("T01_0B_INJECT_NONHIGH", "t01.inject_context_scores", "0b非高置信注入", x=2880, y=620)
    g.workflow_tool("T01_P2_CONTEXT_NONHIGH", PHASE_NAMES[2], "P2补跑S-16（NON_HIGH）", _stage_params("T01_START", entry_mode="context_only"), x=3200, y=620)
    g.workflow_tool("T01_P3_CONTEXT", PHASE_NAMES[3], "从step12重算结构依赖维度", _stage_params("T01_START"), x=3520, y=620)
    g.if_else("T01_IF_P3_CONTEXT_SKIP", "上下文路径R-57跳过?", ["T01_P3_CONTEXT", "stage_route"], "DESIGN_SKIPPED", x=3840, y=620)

    g.workflow_tool("T01_P0_FULL", PHASE_NAMES[0], "P0完整结构阶段", _stage_params("T01_START"), x=2880, y=1000)
    g.if_else("T01_IF_P0_FAILED", "P0失败?", ["T01_P0_FULL", "stage_status"], "FAILED", x=3200, y=1000)
    g.workflow_tool("T01_P1_FULL", PHASE_NAMES[1], "P1完整表位安全阶段", _stage_params("T01_START"), x=3520, y=1000)
    g.workflow_tool("T01_P2_FULL", PHASE_NAMES[2], "P2完整保守功能域阶段", _stage_params("T01_START", entry_mode="full"), x=3840, y=1000)
    g.step_tool("T01_T11_PREPARE", "t01.prepare_permission_inputs", "step11权限输入准备", x=4160, y=1000)
    g.workflow_tool("T01_P3_FULL", PHASE_NAMES[3], "P3 WT可开发性与R-57", _stage_params("T01_START"), x=4480, y=1000)
    g.if_else("T01_IF_P3_FULL_SKIP", "完整路径R-57跳过?", ["T01_P3_FULL", "stage_route"], "DESIGN_SKIPPED", x=4800, y=1000)

    g.aggregator(
        "T01_DESIGN_ENTRY_JOIN",
        "step15入口汇合",
        [
            ["T01_P2_CONTEXT_HIGH", "stage_result"],
            ["T01_P3_CONTEXT", "stage_result"],
            ["T01_P3_FULL", "stage_result"],
        ],
        output_type="object",
        x=5120,
        y=520,
    )
    g.step_tool("T01_T15_GUARD", "t01.evaluate_mutable_length", "step15 mutable_length守卫", x=5440, y=520)
    g.step_tool("T01_T16_BUNDLE", "t01.build_evidence_bundle", "step16六键evidence_bundle", x=5760, y=520)
    g.workflow_tool("T01_P4_DESIGN", PHASE_NAMES[4], "P4序列设计与重试", _stage_params("T01_START"), x=6080, y=520)
    g.if_else("T01_IF_DESIGN_EXHAUSTED", "设计三轮全淘汰?", ["T01_P4_DESIGN", "stage_route"], "EXHAUSTED", x=6400, y=520)
    g.workflow_tool("T01_P5_VARIANTS", PHASE_NAMES[5], "P5变体重评与排序", _stage_params("T01_START"), x=6720, y=760)
    g.workflow_tool("T01_P6_FINAL_SCIENCE", PHASE_NAMES[6], "P6密码子/WT扫描/MD", _stage_params("T01_START"), x=7040, y=760)
    g.aggregator(
        "T01_P7_ENTRY_JOIN",
        "阶段7入口汇合",
        [
            ["T01_P6_FINAL_SCIENCE", "stage_result"],
            ["T01_P4_DESIGN", "stage_result"],
            ["T01_P3_CONTEXT", "stage_result"],
            ["T01_P3_FULL", "stage_result"],
        ],
        output_type="object",
        x=7360,
        y=520,
    )
    g.workflow_tool("T01_P7_OUTPUT", PHASE_NAMES[7], "P7输出与交接", _stage_params("T01_START"), x=7680, y=520)
    g.aggregator(
        "T01_TERMINAL_JOIN",
        "终态结果汇合",
        [
            ["T01_P7_OUTPUT", "stage_result"],
            ["T01_P0_FULL", "stage_result"],
            ["T01_VALIDATE_REQUEST", "json"],
            ["T01_G00_LENGTH", "json"],
        ],
        output_type="object",
        x=8000,
        y=520,
    )
    g.end(
        "T01_END",
        {
            "run_id": ["T01_START", "run_id"],
            "execution_mode": ["T01_START", "execution_mode"],
            "result": ["T01_TERMINAL_JOIN", "output"],
        },
        x=8320,
        y=520,
    )

    for source, target in [
        ("T01_START", "T01_CONFIGURE_RUN"),
        ("T01_CONFIGURE_RUN", "T01_VALIDATE_REQUEST"),
        ("T01_VALIDATE_REQUEST", "T01_IF_INPUT_REQUIRED"),
        ("T01_G00_LENGTH", "T01_IF_LENGTH_HALT"),
        ("T01_G01_CONTEXT", "T01_IF_CONTEXT_HIGH"),
        ("T01_0B_INJECT_HIGH", "T01_P2_CONTEXT_HIGH"),
        ("T01_0B_INJECT_NONHIGH", "T01_P2_CONTEXT_NONHIGH"),
        ("T01_P2_CONTEXT_NONHIGH", "T01_P3_CONTEXT"),
        ("T01_P3_CONTEXT", "T01_IF_P3_CONTEXT_SKIP"),
        ("T01_P0_FULL", "T01_IF_P0_FAILED"),
        ("T01_P1_FULL", "T01_P2_FULL"),
        ("T01_P2_FULL", "T01_T11_PREPARE"),
        ("T01_T11_PREPARE", "T01_P3_FULL"),
        ("T01_P3_FULL", "T01_IF_P3_FULL_SKIP"),
        ("T01_DESIGN_ENTRY_JOIN", "T01_T15_GUARD"),
        ("T01_T15_GUARD", "T01_T16_BUNDLE"),
        ("T01_T16_BUNDLE", "T01_P4_DESIGN"),
        ("T01_P4_DESIGN", "T01_IF_DESIGN_EXHAUSTED"),
        ("T01_P5_VARIANTS", "T01_P6_FINAL_SCIENCE"),
        ("T01_P7_ENTRY_JOIN", "T01_P7_OUTPUT"),
        ("T01_P7_OUTPUT", "T01_TERMINAL_JOIN"),
        ("T01_TERMINAL_JOIN", "T01_END"),
    ]:
        g.edge(source, target)
    g.edge("T01_IF_INPUT_REQUIRED", "T01_TERMINAL_JOIN", "true")
    g.edge("T01_IF_INPUT_REQUIRED", "T01_G00_LENGTH", "false")
    g.edge("T01_IF_LENGTH_HALT", "T01_TERMINAL_JOIN", "true")
    g.edge("T01_IF_LENGTH_HALT", "T01_G01_CONTEXT", "false")
    g.edge("T01_IF_CONTEXT_HIGH", "T01_0B_INJECT_HIGH", "true")
    g.edge("T01_IF_CONTEXT_HIGH", "T01_IF_CONTEXT_NONHIGH", "false")
    g.edge("T01_IF_CONTEXT_NONHIGH", "T01_0B_INJECT_NONHIGH", "true")
    g.edge("T01_IF_CONTEXT_NONHIGH", "T01_P0_FULL", "false")
    g.edge("T01_P2_CONTEXT_HIGH", "T01_DESIGN_ENTRY_JOIN")
    g.edge("T01_IF_P3_CONTEXT_SKIP", "T01_P7_ENTRY_JOIN", "true")
    g.edge("T01_IF_P3_CONTEXT_SKIP", "T01_DESIGN_ENTRY_JOIN", "false")
    g.edge("T01_IF_P0_FAILED", "T01_TERMINAL_JOIN", "true")
    g.edge("T01_IF_P0_FAILED", "T01_P1_FULL", "false")
    g.edge("T01_IF_P3_FULL_SKIP", "T01_P7_ENTRY_JOIN", "true")
    g.edge("T01_IF_P3_FULL_SKIP", "T01_DESIGN_ENTRY_JOIN", "false")
    g.edge("T01_IF_DESIGN_EXHAUSTED", "T01_P7_ENTRY_JOIN", "true")
    g.edge("T01_IF_DESIGN_EXHAUSTED", "T01_P5_VARIANTS", "false")
    g.edge("T01_P6_FINAL_SCIENCE", "T01_P7_ENTRY_JOIN")
    return _workflow_document(
        MASTER_NAME,
        "T-01 v10 Dify调试主流程。LLM不参与科学计算；主流程只调用MCP/阶段工作流并按后端枚举路由。当前模板为Mock调试配置。",
        g,
        icon="🧩",
    )


def build_all() -> dict[str, dict[str, Any]]:
    builders = (
        build_phase0,
        build_phase1,
        build_phase2,
        build_phase3,
        build_phase4,
        build_phase5,
        build_phase6,
        build_phase7,
        build_master,
    )
    documents = [builder() for builder in builders]
    return {str(document["app"]["name"]): document for document in documents}


def _filename(index: int, name: str, *, template: bool) -> str:
    suffix = ".template.dify.yml" if template else ".dify.yml"
    return f"{index:02d}_{name}{suffix}"


def generate_templates(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    documents = build_all()
    validate_workflow_set(documents.values(), allow_placeholders=True)
    written: list[Path] = []
    for index, name in enumerate((*PHASE_NAMES, MASTER_NAME)):
        path = output_dir / _filename(index if name != MASTER_NAME else 99, name, template=True)
        path.write_text(
            yaml.safe_dump(documents[name], allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )
        written.append(path)
    return written


def generate_debug_templates(output_dir: Path) -> list[Path]:
    """Generate standalone Mock harnesses without changing the core DSL set."""

    output_dir.mkdir(parents=True, exist_ok=True)
    core_documents = build_all()
    written: list[Path] = []
    for index, phase_name in enumerate(PHASE_NAMES):
        document = _derive_phase_debug(core_documents[phase_name], index)
        validate_workflow(document, allow_placeholders=True)
        path = output_dir / _filename(index, DEBUG_PHASE_NAMES[index], template=True)
        path.write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )
        written.append(path)
    return written


def load_workflows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    return [yaml.safe_load(path.read_text(encoding="utf-8")) for path in paths]


def _replace_and_write(source: Path, destination: Path, replacements: Mapping[str, str]) -> Path:
    text = source.read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    unresolved = sorted(set(re.findall(r"__[A-Z0-9_]+__", text)))
    if unresolved:
        raise ValueError(f"unresolved placeholders in {source.name}: {unresolved}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return destination


def bind_debug_templates(template_dir: Path, output_dir: Path, mcp_provider_id: str) -> list[Path]:
    provider_id = mcp_provider_id.strip()
    if not provider_id or provider_id.startswith("replace-"):
        raise ValueError("mcp_provider_id must be the provider ID created by this Dify instance")
    sources = sorted(template_dir.glob("*_Debug.template.dify.yml"))
    if len(sources) != len(PHASE_NAMES):
        raise ValueError(f"expected {len(PHASE_NAMES)} debug templates, found {len(sources)}")
    written: list[Path] = []
    for source in sources:
        destination = output_dir / source.name.replace(".template.dify.yml", ".dify.yml")
        path = _replace_and_write(source, destination, {MCP_PROVIDER_TOKEN: provider_id})
        validate_workflow(
            yaml.safe_load(path.read_text(encoding="utf-8")),
            allow_placeholders=False,
        )
        written.append(path)
    return written


def bind_stage_templates(template_dir: Path, output_dir: Path, mcp_provider_id: str) -> list[Path]:
    provider_id = mcp_provider_id.strip()
    if not provider_id or provider_id.startswith("replace-"):
        raise ValueError("mcp_provider_id must be the provider ID created by this Dify instance")
    written: list[Path] = []
    for source in sorted(template_dir.glob("0[0-7]_*.template.dify.yml")):
        destination = output_dir / source.name.replace(".template.dify.yml", ".dify.yml")
        written.append(_replace_and_write(source, destination, {MCP_PROVIDER_TOKEN: provider_id}))
    if len(written) != 8:
        raise ValueError(f"expected 8 stage templates, found {len(written)}")
    for document in load_workflows(written):
        validate_workflow(document, allow_placeholders=False)
    return written


def _binding_replacements(bindings: Mapping[str, Any]) -> dict[str, str]:
    mcp_provider_id = str(bindings.get("mcp_provider_id", "")).strip()
    if not mcp_provider_id or mcp_provider_id.startswith("replace-"):
        raise ValueError("bindings.mcp_provider_id must be the provider ID created by this Dify instance")
    workflow_tools = bindings.get("workflow_tools")
    if not isinstance(workflow_tools, Mapping):
        raise ValueError("bindings.workflow_tools must be an object")
    replacements = {MCP_PROVIDER_TOKEN: mcp_provider_id}
    for name in PHASE_NAMES:
        entry = workflow_tools.get(name)
        if not isinstance(entry, Mapping):
            raise ValueError(f"missing workflow_tools binding for {name}")
        provider_id = str(entry.get("provider_id", "")).strip()
        tool_name = str(entry.get("tool_name", "")).strip()
        if not provider_id or not tool_name or provider_id.startswith("replace-") or tool_name.startswith("replace-"):
            raise ValueError(f"incomplete workflow_tools binding for {name}")
        replacements[workflow_provider_token(name)] = provider_id
        replacements[workflow_tool_token(name)] = tool_name
    return replacements


def bind_master_template(template_dir: Path, output_dir: Path, bindings: Mapping[str, Any]) -> Path:
    replacements = _binding_replacements(bindings)
    sources = sorted(template_dir.glob("99_*.template.dify.yml"))
    if len(sources) != 1:
        raise ValueError(f"expected one master template, found {len(sources)}")
    source = sources[0]
    destination = output_dir / source.name.replace(".template.dify.yml", ".dify.yml")
    written = _replace_and_write(source, destination, replacements)
    validate_workflow(yaml.safe_load(written.read_text(encoding="utf-8")), allow_placeholders=False)
    return written


def bind_templates(template_dir: Path, output_dir: Path, bindings: Mapping[str, Any]) -> list[Path]:
    replacements = _binding_replacements(bindings)

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    template_paths = sorted(template_dir.glob("*.template.dify.yml"))
    if len(template_paths) != 9:
        raise ValueError(f"expected 9 Dify templates, found {len(template_paths)}")
    for source in template_paths:
        destination = output_dir / source.name.replace(".template.dify.yml", ".dify.yml")
        written.append(_replace_and_write(source, destination, replacements))
    validate_workflow_set(load_workflows(written), allow_placeholders=False)
    return written


def validate_workflow(document: Mapping[str, Any], *, allow_placeholders: bool) -> None:
    if document.get("version") != DSL_VERSION:
        raise ValueError(f"unsupported Dify DSL version: {document.get('version')}")
    if document.get("kind") != "app" or document.get("app", {}).get("mode") != "workflow":
        raise ValueError("document must be a Dify Workflow app")
    graph = document.get("workflow", {}).get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    ids = [node.get("id") for node in nodes]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate node IDs in {document.get('app', {}).get('name')}")
    node_types = [node.get("data", {}).get("type") for node in nodes]
    unknown = set(node_types) - ALLOWED_NODE_TYPES
    if unknown:
        raise ValueError(f"forbidden/unknown node types: {sorted(unknown)}")
    if node_types.count("start") != 1 or node_types.count("end") != 1:
        raise ValueError("every workflow must have exactly one Start and one End")
    node_ids = set(ids)
    incoming: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    outgoing: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    outgoing_handles: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in edges:
        if edge.get("source") not in node_ids or edge.get("target") not in node_ids:
            raise ValueError(f"edge references an unknown node: {edge.get('id')}")
        source = str(edge["source"])
        target = str(edge["target"])
        outgoing[source].add(target)
        incoming[target].add(source)
        outgoing_handles[source].add(str(edge.get("sourceHandle", "source")))
    start_id = ids[node_types.index("start")]
    end_id = ids[node_types.index("end")]
    if incoming[start_id] or outgoing[end_id]:
        raise ValueError("Start cannot have incoming edges and End cannot have outgoing edges")
    for node_id, node_type in zip(ids, node_types, strict=True):
        if node_id != start_id and not incoming[node_id]:
            raise ValueError(f"node has no incoming edge: {node_id}")
        if node_id != end_id and not outgoing[node_id]:
            raise ValueError(f"node has no outgoing edge: {node_id}")
        if node_type == "if-else" and outgoing_handles[node_id] != {"true", "false"}:
            raise ValueError(f"IF/ELSE node must expose true and false paths: {node_id}")

    reachable = {start_id}
    frontier = [start_id]
    while frontier:
        current = frontier.pop()
        for target in outgoing[current] - reachable:
            reachable.add(target)
            frontier.append(target)
    if reachable != node_ids:
        raise ValueError(f"unreachable nodes: {sorted(node_ids - reachable)}")

    can_reach_end = {end_id}
    frontier = [end_id]
    while frontier:
        current = frontier.pop()
        for source in incoming[current] - can_reach_end:
            can_reach_end.add(source)
            frontier.append(source)
    if can_reach_end != node_ids:
        raise ValueError(f"nodes cannot reach End: {sorted(node_ids - can_reach_end)}")

    indegree = {node_id: len(incoming[node_id]) for node_id in node_ids}
    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for target in outgoing[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(node_ids):
        raise ValueError("workflow graph must be acyclic; retries are explicitly unrolled")
    for node in nodes:
        data = node.get("data", {})
        if data.get("type") != "tool":
            continue
        provider_type = data.get("provider_type")
        if provider_type not in {"mcp", "workflow"}:
            raise ValueError(f"tool node {node['id']} has forbidden provider type {provider_type}")
        if data.get("tool_node_version") != "2":
            raise ValueError(f"tool node {node['id']} is not tool_node_version 2")
        if not allow_placeholders:
            serialized = json.dumps(data, ensure_ascii=False)
            if re.search(r"__[A-Z0-9_]+__", serialized):
                raise ValueError(f"unresolved placeholder in {node['id']}")


def validate_workflow_set(
    documents: Iterable[Mapping[str, Any]],
    *,
    allow_placeholders: bool,
) -> None:
    docs = list(documents)
    names = {str(document.get("app", {}).get("name")) for document in docs}
    expected_names = {MASTER_NAME, *PHASE_NAMES}
    if names != expected_names:
        raise ValueError(f"workflow set mismatch: expected {sorted(expected_names)}, got {sorted(names)}")
    for document in docs:
        validate_workflow(document, allow_placeholders=allow_placeholders)

    observed_mcp_tools: set[str] = set()
    for document in docs:
        for node in document["workflow"]["graph"]["nodes"]:
            data = node["data"]
            if data.get("type") == "tool" and data.get("provider_type") == "mcp":
                observed_mcp_tools.add(str(data.get("tool_name")))
    missing = set(STEP_TOOLS) - observed_mcp_tools
    unknown = observed_mcp_tools - set(STEP_TOOLS) - CONTROL_TOOL_NAMES
    if missing or unknown:
        raise ValueError(
            f"MCP tool coverage mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
