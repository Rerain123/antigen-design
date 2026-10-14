from __future__ import annotations

import json
from pathlib import Path

from t01_dify_workflows import (
    DEBUG_PHASE_NAMES,
    DEBUG_PHASE0_NAME,
    MASTER_NAME,
    PHASE_NAMES,
    bind_debug_templates,
    bind_master_template,
    bind_stage_templates,
    bind_templates,
    generate_debug_templates,
    generate_templates,
    load_workflows,
    validate_workflow_set,
)


def synthetic_bindings() -> dict[str, object]:
    return {
        "mcp_provider_id": "00000000-0000-4000-8000-000000000001",
        "workflow_tools": {
            name: {
                "provider_id": f"provider-{index:02d}",
                "tool_name": f"tool-{index:02d}",
            }
            for index, name in enumerate(PHASE_NAMES)
        },
    }


def test_generate_nine_dify_templates_with_full_mcp_coverage(tmp_path: Path) -> None:
    paths = generate_templates(tmp_path / "templates")
    assert len(paths) == 9
    documents = load_workflows(paths)
    validate_workflow_set(documents, allow_placeholders=True)
    assert {document["app"]["name"] for document in documents} == {
        MASTER_NAME,
        *PHASE_NAMES,
    }


def test_bind_replaces_every_instance_specific_placeholder(tmp_path: Path) -> None:
    templates = tmp_path / "templates"
    bound = tmp_path / "bound"
    generate_templates(templates)
    paths = bind_templates(templates, bound, synthetic_bindings())
    assert len(paths) == 9
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "__T01_" not in text
    validate_workflow_set(load_workflows(paths), allow_placeholders=False)


def test_two_pass_binding_supports_dify_publish_order(tmp_path: Path) -> None:
    templates = tmp_path / "templates"
    generate_templates(templates)
    stages = bind_stage_templates(templates, tmp_path / "stages", "mcp-provider-test")
    assert len(stages) == 8
    assert all("__T01_" not in path.read_text(encoding="utf-8") for path in stages)
    master = bind_master_template(templates, tmp_path / "master", synthetic_bindings())
    assert master.name.startswith("99_T01_Master_v10")
    assert "__T01_" not in master.read_text(encoding="utf-8")


def test_workflows_have_no_llm_code_or_http_nodes(tmp_path: Path) -> None:
    paths = generate_templates(tmp_path / "templates")
    node_types = {
        node["data"]["type"]
        for document in load_workflows(paths)
        for node in document["workflow"]["graph"]["nodes"]
    }
    assert node_types == {"start", "tool", "if-else", "variable-aggregator", "end"}


def test_mcp_object_and_array_constants_are_json_text_for_dify_editor(tmp_path: Path) -> None:
    paths = generate_templates(tmp_path / "templates")
    documents = load_workflows(paths)
    json_parameter_names = {"parameters", "input_artifacts", "context"}

    for document in documents:
        for node in document["workflow"]["graph"]["nodes"]:
            data = node["data"]
            if data.get("type") != "tool" or data.get("provider_type") != "mcp":
                continue
            for name in json_parameter_names & data["tool_parameters"].keys():
                parameter = data["tool_parameters"][name]
                if parameter["type"] != "constant":
                    continue
                assert isinstance(parameter["value"], str)
                assert isinstance(json.loads(parameter["value"]), (dict, list))


def test_mock_execution_mode_is_pinned_for_tool_invocations(tmp_path: Path) -> None:
    paths = generate_templates(tmp_path / "templates")
    documents = load_workflows(paths)

    checked = 0
    for document in documents:
        for node in document["workflow"]["graph"]["nodes"]:
            data = node["data"]
            if data.get("type") != "tool":
                continue
            parameter = data.get("tool_parameters", {}).get("execution_mode")
            if parameter is None:
                continue
            assert parameter == {"type": "constant", "value": "mock"}
            checked += 1

    assert checked > 0


def test_phase0_quality_join_exposes_data_as_its_output(tmp_path: Path) -> None:
    paths = generate_templates(tmp_path / "templates")
    phase0 = next(
        document
        for document in load_workflows(paths)
        if document["app"]["name"] == PHASE_NAMES[0]
    )
    nodes = {
        node["id"]: node["data"]
        for node in phase0["workflow"]["graph"]["nodes"]
    }

    assert nodes["P0_QUALITY_JOIN"]["variables"] == [
        ["P0_S09_QUALITY_PRED", "data"],
        ["P0_S09_QUALITY_EXIST", "data"],
    ]
    assert nodes["P0_G_RSA"]["tool_parameters"]["parameters"] == {
        "type": "variable",
        "value": ["P0_QUALITY_JOIN", "output"],
    }


def test_stage_routes_are_exported_as_scalars_for_master_branching(tmp_path: Path) -> None:
    documents = {
        document["app"]["name"]: document
        for document in load_workflows(generate_templates(tmp_path / "templates"))
    }

    phase3_nodes = {
        node["id"]: node["data"]
        for node in documents[PHASE_NAMES[3]]["workflow"]["graph"]["nodes"]
    }
    phase3_outputs = {
        item["variable"]: item["value_selector"]
        for item in phase3_nodes["P3_END"]["outputs"]
    }
    assert phase3_outputs["stage_route"] == ["P3_R57_GATE", "data", "route"]

    phase4_nodes = {
        node["id"]: node["data"]
        for node in documents[PHASE_NAMES[4]]["workflow"]["graph"]["nodes"]
    }
    assert phase4_nodes["P4_ROUTE_JOIN"]["output_type"] == "string"
    assert phase4_nodes["P4_ROUTE_JOIN"]["variables"] == [
        ["P4_RETRY_GATE_A3", "data", "route"],
        ["P4_RETRY_GATE_A2", "data", "route"],
        ["P4_RETRY_GATE_A1", "data", "route"],
    ]
    phase4_outputs = {
        item["variable"]: item["value_selector"]
        for item in phase4_nodes["P4_END"]["outputs"]
    }
    assert phase4_outputs["stage_route"] == ["P4_ROUTE_JOIN", "output"]

    master_nodes = {
        node["id"]: node["data"]
        for node in documents[MASTER_NAME]["workflow"]["graph"]["nodes"]
    }
    assert master_nodes["T01_IF_P3_CONTEXT_SKIP"]["cases"][0]["conditions"][0][
        "variable_selector"
    ] == ["T01_P3_CONTEXT", "stage_route"]
    assert master_nodes["T01_IF_P3_FULL_SKIP"]["cases"][0]["conditions"][0][
        "variable_selector"
    ] == ["T01_P3_FULL", "stage_route"]
    assert master_nodes["T01_IF_DESIGN_EXHAUSTED"]["cases"][0]["conditions"][0][
        "variable_selector"
    ] == ["T01_P4_DESIGN", "stage_route"]


def test_phase0_debug_harness_auto_initializes_a_unique_mock_run(tmp_path: Path) -> None:
    paths = generate_debug_templates(tmp_path / "debug-templates")
    assert len(paths) == 8
    assert {document["app"]["name"] for document in load_workflows(paths)} == set(DEBUG_PHASE_NAMES)
    document = load_workflows(paths)[0]
    assert document["app"]["name"] == DEBUG_PHASE0_NAME

    graph = document["workflow"]["graph"]
    nodes = {node["id"]: node["data"] for node in graph["nodes"]}
    assert [item["variable"] for item in nodes["P0_START"]["variables"]] == ["scenario_id"]

    initializer = nodes["P0D_CONFIGURE_RUN"]
    assert initializer["tool_name"] == "mock.configure_run"
    assert initializer["tool_parameters"] == {
        "run_id": {"type": "variable", "value": ["sys", "workflow_run_id"]},
        "scenario_id": {"type": "variable", "value": ["P0_START", "scenario_id"]},
    }

    for data in nodes.values():
        if data.get("type") != "tool" or data.get("tool_name") not in {
            "structure.fetch",
            "t01.route_existing_structure",
            "structure.predict",
            "structure.assess_quality",
            "topology.predict",
            "t01.route_rsa",
            "structure.compute_rsa",
            "t01.route_pathogen_type",
            "localization.predict_bacteria",
        }:
            continue
        assert data["tool_parameters"]["run_id"] == {
            "type": "variable",
            "value": ["sys", "workflow_run_id"],
        }
        assert "{{#sys.workflow_run_id#}}" in data["tool_parameters"]["idempotency_key"]["value"]

    end_outputs = {
        item["variable"]: item["value_selector"]
        for item in nodes["P0_END"]["outputs"]
    }
    assert end_outputs["run_id"] == ["sys", "workflow_run_id"]
    assert "P0_START.run_id" not in paths[0].read_text(encoding="utf-8")

    edges = {(edge["source"], edge["target"]) for edge in graph["edges"]}
    assert ("P0_START", "P0D_CONFIGURE_RUN") in edges
    assert ("P0D_CONFIGURE_RUN", "P0_S07_FETCH") in edges
    assert ("P0_START", "P0_S07_FETCH") not in edges


def test_bind_phase0_debug_harness_replaces_mcp_provider(tmp_path: Path) -> None:
    templates = tmp_path / "debug-templates"
    generate_debug_templates(templates)
    paths = bind_debug_templates(templates, tmp_path / "debug-bound", "t01-mock-mcp")
    assert len(paths) == 8
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "__T01_" not in text
        assert "provider_id: t01-mock-mcp" in text


def test_debug_harnesses_preserve_stage_specific_start_controls(tmp_path: Path) -> None:
    documents = load_workflows(generate_debug_templates(tmp_path / "debug-templates"))
    for index, document in enumerate(documents):
        nodes = {
            node["id"]: node["data"]
            for node in document["workflow"]["graph"]["nodes"]
        }
        start_variables = [
            item["variable"] for item in nodes[f"P{index}_START"]["variables"]
        ]
        expected = ["scenario_id", "entry_mode"] if index == 2 else ["scenario_id"]
        assert start_variables == expected
        assert nodes[f"P{index}D_CONFIGURE_RUN"]["tool_name"] == "mock.configure_run"


def test_example_binding_file_has_every_phase() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "dify"
        / "config"
        / "provider-bindings.example.json"
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    assert set(value["workflow_tools"]) == set(PHASE_NAMES)
