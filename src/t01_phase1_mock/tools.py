"""Thin 26-tool facade registered by M1-06; no scientific implementation lives here."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .engine import MockBackend
from .jsonio import ContractError


class MockToolFacade:
    """Dispatch the frozen logical tool IDs to one deterministic backend truth."""

    def __init__(self, backend: MockBackend) -> None:
        self.backend = backend
        tools = backend.bundle.asset_registry["tool_namespace"]["tools"]
        self._tool_by_id = {item["tool_id"]: item for item in tools}
        if len(self._tool_by_id) != 26:
            raise ContractError("tool facade requires exactly 26 registered tools")

    @property
    def tool_ids(self) -> tuple[str, ...]:
        return tuple(self._tool_by_id)

    def call(self, tool_id: str, **arguments: Any) -> Any:
        tool = self._tool_by_id.get(tool_id)
        if tool is None:
            raise ContractError(f"unknown Phase 1 Mock tool: {tool_id}")
        role = tool["tool_role"]
        if role == "RUN_INITIALIZER":
            request = arguments.get("request")
            if not isinstance(request, dict):
                raise ContractError("run initializer requires request object")
            return self.backend.submit(request).to_dict()

        run_id = arguments.get("run_id")
        if not isinstance(run_id, str):
            raise ContractError(f"{tool_id} requires run_id")
        run = self.backend.get_run(run_id)
        scenario_ref = arguments.get("scenario_ref")
        if scenario_ref is not None:
            if not isinstance(scenario_ref, str):
                raise ContractError(f"{tool_id} scenario_ref must be a string")
            if scenario_ref != run["scenario_ref"]:
                raise ContractError("tool scenario_ref does not match the bound run")

        if role == "NODE_STUB":
            node_id = tool["node_id"]
            return deepcopy(
                next(item for item in run["node_results"] if item["node_id"] == node_id)
            )
        if role == "CONTROL_LITERAL":
            return self._control_literal(run, tool["control_key"])
        if role == "RUN_FINALIZER":
            return run
        raise ContractError(f"unsupported registered tool role: {role}")

    def _control_literal(self, run: dict[str, Any], control_key: str) -> dict[str, Any]:
        scenario = self.backend.bundle.scenario_for_ref(run["scenario_ref"])
        source = deepcopy(scenario["control_plan"][control_key])
        source["runtime_decisions"] = [
            deepcopy(item)
            for item in run["control_decisions"]
            if (
                (control_key == "design_suitability" and item["control_type"] == "DESIGN_SUITABILITY")
                or (control_key == "n12_validation" and item["control_type"] == "N12_VALIDATION")
                or (
                    control_key == "n15_delivery_recommendation"
                    and item["control_type"] == "N15_DELIVERY_RECOMMENDATION"
                )
                or (control_key == "n16_applicability" and item["control_type"] == "N16_APPLICABILITY")
                or (control_key == "n17_applicability" and item["control_type"] == "N17_APPLICABILITY")
            )
        ]
        source["mock_only"] = True
        source["scientific_compute"] = False
        return source
