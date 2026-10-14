from __future__ import annotations

from t01_phase1_mock.constants import EDGE_IDS, NODE_IDS
from t01_phase1_mock.dify.generator import render_all
from t01_phase1_mock.dify.validator import validate_main_debug_pair


def test_generator_is_single_source_and_byte_deterministic() -> None:
    first = render_all()
    second = render_all()
    assert [item.role for item in first] == ["PRIMARY", "DEBUG"]
    assert [item.content for item in first] == [item.content for item in second]
    assert all(item.output_path.read_bytes() == item.content for item in first)
    validate_main_debug_pair(first[0].document, first[1].document)


def test_generated_graph_recovers_frozen_business_topology() -> None:
    for generated in render_all():
        graph = generated.document["workflow"]["graph"]
        assert len(graph["nodes"]) == 59
        assert len(graph["edges"]) == 79
        business_nodes = {
            node["data"].get("t01_business_node_id", node["id"])
            for node in graph["nodes"]
            if node["data"]["type"] == "tool"
        }
        semantic_edges = {
            edge["data"].get("semantic_edge_id")
            for edge in graph["edges"]
            if edge["data"].get("semantic_edge_id")
        }
        assert set(NODE_IDS).issubset(business_nodes)
        assert semantic_edges == set(EDGE_IDS)
        assert {node["data"]["type"] for node in graph["nodes"]}.isdisjoint(
            {"code", "llm", "agent"}
        )


def test_generator_uses_bounded_n12_unrolling_and_literal_controls() -> None:
    graph = render_all()[0].document["workflow"]["graph"]
    by_id = {node["id"]: node for node in graph["nodes"]}
    assert {f"N11_C{i}" for i in range(1, 4)}.issubset(by_id)
    assert {f"N12_C{i}" for i in range(1, 4)}.issubset(by_id)
    assert not any(node["data"]["type"] in {"loop", "iteration"} for node in graph["nodes"])
    assert by_id["GATE_IF"]["data"]["cases"][0]["conditions"][0]["variable_selector"] == [
        "CONTROL_GATE",
        "decision",
    ]
    assert by_id["N16_IF"]["data"]["cases"][0]["conditions"][0]["variable_selector"] == [
        "CONTROL_N16",
        "decision",
    ]
    assert by_id["N17_IF"]["data"]["cases"][0]["conditions"][0]["variable_selector"] == [
        "CONTROL_N17",
        "decision",
    ]

