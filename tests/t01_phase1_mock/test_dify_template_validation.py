from __future__ import annotations

from copy import deepcopy

import pytest

from t01_phase1_mock.dify.generator import render_all
from t01_phase1_mock.dify.validator import validate_workflow_document
from t01_phase1_mock.jsonio import ContractError


def test_both_templates_pass_fail_closed_static_validation() -> None:
    for generated in render_all():
        facts = validate_workflow_document(
            generated.document,
            expected_app_name=generated.app_name,
            template=True,
        )
        assert facts["business_node_count"] == 18
        assert facts["semantic_edge_count"] == 27
        assert facts["registered_tool_count"] == 26


@pytest.mark.parametrize("mutation", ["unknown_node", "dangling_edge", "provider", "cycle", "secret"])
def test_template_validator_rejects_structural_and_security_drift(mutation: str) -> None:
    document = deepcopy(render_all()[0].document)
    graph = document["workflow"]["graph"]
    if mutation == "unknown_node":
        graph["nodes"][0]["data"]["type"] = "llm"
    elif mutation == "dangling_edge":
        graph["edges"][0]["target"] = "MISSING"
    elif mutation == "provider":
        next(node for node in graph["nodes"] if node["data"]["type"] == "tool")["data"][
            "provider_id"
        ] = "unexpected-provider"
    elif mutation == "cycle":
        next(node for node in graph["nodes"] if node["id"] == "N12_C3")["data"][
            "t01_design_cycle"
        ] = 4
    else:
        document["workflow"]["environment_variables"] = [{"name": "api_key", "value": "x"}]
    with pytest.raises(ContractError):
        validate_workflow_document(document, template=True)

