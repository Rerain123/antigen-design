"""Project frozen scenario literals into M1-04 request/run envelopes."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from .catalog import SpecificationBundle
from .constants import (
    CONTROL_FLOW_VERSION,
    CONTROL_TYPE_BY_KEY,
    EDGE_ENDPOINTS,
    ENVELOPE_CONTRACT_VERSION,
    NODE_IDS,
    NODE_REGISTRY_VERSION,
    OUTPUT_COMPLETENESS_BY_MODE,
    TOPOLOGY_VERSION,
    UPSTREAM_NODE_IDS,
)
from .fixtures import FixtureRepository
from .jsonio import ContractError, stable_uuid4


_BASE_TIME = datetime(2026, 9, 4, tzinfo=timezone.utc)
_COMPONENT_VERSION = "T01-PHASE1-MOCK-M2-v0.1"


def _timestamp(ordinal: int, offset: int) -> str:
    value = _BASE_TIME + timedelta(minutes=ordinal * 10, seconds=offset)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _identity(kind: str, seed: str) -> str:
    return f"t01_phase1_mock_v01.{kind}.{stable_uuid4(kind + ':' + seed)}"


def _envelope_id(seed: str) -> str:
    return f"t01-phase1-mock-v01-env-{stable_uuid4('envelope:' + seed)}"


def _actor(actor_type: str, actor_id: str) -> dict[str, Any]:
    return {
        "actor_type": actor_type,
        "actor_id": actor_id,
        "component_version": _COMPONENT_VERSION,
    }


def _attempt_id(run_id: str, node_id: str, attempt_number: int) -> str:
    return _identity("attempt", f"{run_id}:{node_id}:{attempt_number}")


def _decision_id(run_id: str, control_key: str, index: int = 1) -> str:
    return _identity("decision", f"{run_id}:{control_key}:{index}")


def _artifact_id(run_id: str, fixture_key: str) -> str:
    return _identity("artifact", f"{run_id}:{fixture_key}")


def _error_id(run_id: str, node_id: str | None, attempt_id: str | None, code: str) -> str:
    return _identity("error", f"{run_id}:{node_id}:{attempt_id}:{code}")


def _error_category(code: str) -> str:
    if code == "NODE_TIMED_OUT":
        return "TIMEOUT"
    if code == "NODE_CANCELLED":
        return "CANCELLATION"
    if code in {"RECALC_EXHAUSTED", "CONTROL_DECISION_MISSING", "CONTROL_DECISION_INVALID"}:
        return "CONTROL"
    if code in {
        "REQUEST_SCHEMA_INVALID",
        "REQUEST_IDEMPOTENCY_CONFLICT",
        "PROTEIN_SEQUENCE_MISSING",
        "HOST_SPECIES_MISSING",
        "EXPRESSION_HOST_UNSUPPORTED",
    }:
        return "VALIDATION"
    if code in {"ARTIFACT_INTEGRITY_FAILED", "STRUCTURE_ARTIFACT_INVALID"}:
        return "ARTIFACT"
    if code == "INTERNAL_CONTRACT_VIOLATION":
        return "INTERNAL"
    return "TOOL"


def make_error(
    *,
    run_id: str,
    scenario_key: str,
    code: str,
    occurred_at: str,
    node_id: str | None,
    attempt_id: str | None,
    retryable: bool = False,
) -> dict[str, Any]:
    retryability = "RETRYABLE" if retryable else "NON_RETRYABLE"
    return {
        "error_id": _error_id(run_id, node_id, attempt_id, code),
        "code": code,
        "category": _error_category(code),
        "severity": "ERROR",
        "retryability": retryability,
        "message": f"Deterministic Mock scenario emitted {code}.",
        "occurred_at": occurred_at,
        "source": _actor("MOCK_SCENARIO", "t01_phase1_mock_v01.scenario_engine"),
        "node_id": node_id,
        "attempt_id": attempt_id,
        "artifact_ids": [],
        "rule_refs": [f"t01_phase1_mock_v01.scenario.{scenario_key}"],
        "details": {
            "mock_only": True,
            "scientific_compute": False,
            "control_source": "SCENARIO_LITERAL",
        },
        "caused_by_error_id": None,
        "manual_review_required": False,
        "blocks_auto_handoff": True,
    }


class RunProjector:
    """Pure projector: scenario directives in, M1-04 envelopes out."""

    def __init__(
        self,
        bundle: SpecificationBundle,
        fixtures: FixtureRepository,
    ) -> None:
        self.bundle = bundle
        self.fixtures = fixtures
        self._ordinal_by_scenario = {
            item["scenario_key"]: index
            for index, item in enumerate(bundle.scenarios, start=1)
        }

    def _artifact_for_attempt(
        self,
        *,
        scenario: dict[str, Any],
        run_id: str,
        node_id: str,
        attempt: dict[str, Any],
        attempt_id: str,
        created_at: str,
    ) -> dict[str, Any] | None:
        fixture_key = attempt["fixture_result_key"]
        if fixture_key is None:
            return None
        metadata = self.fixtures.attempt_file_metadata(fixture_key)
        if attempt["output_mode"] == "PARTIAL_STUB":
            role = "PARTIAL_RESULT"
        elif node_id == "N18":
            role = "FINAL_RESULT"
        else:
            role = "NODE_OUTPUT"
        return {
            "artifact_id": _artifact_id(run_id, fixture_key),
            "artifact_role": role,
            "uri": (
                f"artifact://t01-phase1-mock-v0.1/{run_id}/nodes/"
                f"{node_id.lower()}/attempt-{attempt['attempt_number']}"
            ),
            "media_type": "application/json",
            "format": "JSON",
            "size_bytes": metadata["size_bytes"],
            "sha256": metadata["sha256"],
            "integrity_status": "VERIFIED",
            "created_at": created_at,
            "producer": _actor(
                "MOCK_SCENARIO", "t01_phase1_mock_v01.fixture_projector"
            ),
            "source_node_id": node_id,
            "source_attempt_id": attempt_id,
            "metadata": {
                "mock_only": True,
                "scientific_compute": False,
                "fixture_result_key": fixture_key,
                "source_materialization": "MATERIALIZED_AND_VERIFIED",
            },
        }

    def _attempts_for_node(
        self,
        *,
        scenario: dict[str, Any],
        run_id: str,
        node_id: str,
        directive: dict[str, Any],
        ordinal: int,
    ) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any] | None]]:
        attempts: list[dict[str, Any]] = []
        artifacts: dict[int, dict[str, Any] | None] = {}
        for attempt in directive["attempts"]:
            number = attempt["attempt_number"]
            attempt_id = _attempt_id(run_id, node_id, number)
            started_at = _timestamp(ordinal, int(node_id[1:]) * 20 + number * 2)
            finished_at = _timestamp(ordinal, int(node_id[1:]) * 20 + number * 2 + 1)
            artifact = self._artifact_for_attempt(
                scenario=scenario,
                run_id=run_id,
                node_id=node_id,
                attempt=attempt,
                attempt_id=attempt_id,
                created_at=finished_at,
            )
            artifacts[number] = artifact
            issues = [
                make_error(
                    run_id=run_id,
                    scenario_key=scenario["scenario_key"],
                    code=code,
                    occurred_at=finished_at,
                    node_id=node_id,
                    attempt_id=attempt_id,
                    retryable=(
                        scenario["scenario_key"] == "n08_retryable_recovery"
                        and node_id == "N08"
                        and number == 1
                    ),
                )
                for code in attempt["error_codes"]
            ]
            recovery_number = attempt["recovery_of_attempt_number"]
            attempts.append(
                {
                    "attempt_id": attempt_id,
                    "attempt_number": number,
                    "attempt_kind": attempt["attempt_kind"],
                    "status": attempt["status"],
                    "design_cycle": attempt["design_cycle"],
                    "recovery_of_attempt_id": (
                        None
                        if recovery_number is None
                        else _attempt_id(run_id, node_id, recovery_number)
                    ),
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "executor": _actor(
                        "MOCK_SCENARIO", "t01_phase1_mock_v01.scenario_engine"
                    ),
                    "parameters": deepcopy(attempt["parameters"]),
                    "input_artifact_ids": [],
                    "output_artifact_ids": (
                        [] if artifact is None else [artifact["artifact_id"]]
                    ),
                    "issues": issues,
                    "metrics": {"queue_ms": 0, "runtime_ms": 1},
                }
            )
        return attempts, artifacts

    def _all_attempts(
        self, scenario: dict[str, Any], run_id: str
    ) -> tuple[
        dict[str, list[dict[str, Any]]],
        dict[str, dict[int, dict[str, Any] | None]],
    ]:
        ordinal = self._ordinal_by_scenario[scenario["scenario_key"]]
        attempts: dict[str, list[dict[str, Any]]] = {}
        artifacts: dict[str, dict[int, dict[str, Any] | None]] = {}
        for node_id, directive in scenario["node_plan"].items():
            attempts[node_id], artifacts[node_id] = self._attempts_for_node(
                scenario=scenario,
                run_id=run_id,
                node_id=node_id,
                directive=directive,
                ordinal=ordinal,
            )
        return attempts, artifacts

    def _control_decisions(
        self,
        *,
        scenario: dict[str, Any],
        run_id: str,
        edge_ids: list[str],
    ) -> list[dict[str, Any]]:
        ordinal = self._ordinal_by_scenario[scenario["scenario_key"]]
        plan = scenario["control_plan"]
        edge_set = set(edge_ids)
        decisions: list[dict[str, Any]] = []

        def add(
            key: str,
            item: dict[str, Any],
            *,
            index: int = 1,
            node_id: str | None = None,
            attempt_number: int | None = None,
        ) -> None:
            attempt_id = (
                None
                if attempt_number is None or node_id is None
                else _attempt_id(run_id, node_id, attempt_number)
            )
            source_facts = {
                "mock_only": True,
                "scientific_compute": False,
                "source": item["source"],
                "fact_set_key": item.get("fact_set_key"),
            }
            if item.get("design_cycle") is not None:
                source_facts["design_cycle"] = item["design_cycle"]
            decisions.append(
                {
                    "decision_id": _decision_id(run_id, key, index),
                    "control_type": CONTROL_TYPE_BY_KEY[key],
                    "decision": item["decision"],
                    "reason_code": item["reason_code"],
                    "reason": (
                        f"Deterministic scenario literal emitted {item['reason_code']}."
                    ),
                    "node_id": node_id,
                    "attempt_id": attempt_id,
                    "producer": _actor(
                        "BACKEND", "t01_phase1_mock_v01.control_plane"
                    ),
                    "occurred_at": _timestamp(ordinal, 500 + len(decisions)),
                    "source_facts": source_facts,
                }
            )

        if {"E012", "E014"} & edge_set:
            gate = plan["design_suitability"]
            if gate["state"] == "EMIT":
                add("design_suitability", gate)

        n12 = plan["n12_validation"]
        if n12["state"] == "EMIT_SEQUENCE":
            reached_count = edge_ids.count("E016")
            if "E017" in edge_set or "E018" in edge_set:
                reached_count += 1
            for index, decision in enumerate(n12["decisions"][:reached_count], start=1):
                add(
                    "n12_validation",
                    decision,
                    index=index,
                    node_id="N12",
                    attempt_number=decision["design_cycle"],
                )

        for key, edge, node_id in (
            ("n15_delivery_recommendation", "E021", "N15"),
            ("n16_applicability", "E022", "N16"),
            ("n17_applicability", "E023", "N17"),
        ):
            item = plan[key]
            if edge in edge_set and item["state"] == "EMIT":
                add(
                    key,
                    item,
                    node_id=node_id,
                    attempt_number=(1 if key == "n15_delivery_recommendation" else None),
                )
        return decisions

    @staticmethod
    def _control_ids_by_type(
        decisions: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for decision in decisions:
            result.setdefault(decision["control_type"], []).append(decision["decision_id"])
        return result

    def _node_control_ids(
        self,
        node_id: str,
        directive: dict[str, Any],
        by_type: dict[str, list[str]],
    ) -> list[str]:
        gate = by_type.get("DESIGN_SUITABILITY", [])
        if directive["status"] == "SKIPPED_BRANCH" and node_id in NODE_IDS[10:17]:
            return gate
        if node_id == "N10":
            return gate
        mapping = {
            "N12": "N12_VALIDATION",
            "N15": "N15_DELIVERY_RECOMMENDATION",
            "N16": "N16_APPLICABILITY",
            "N17": "N17_APPLICABILITY",
        }
        control_type = mapping.get(node_id)
        return [] if control_type is None else by_type.get(control_type, [])

    def _disposition(
        self,
        *,
        node_id: str,
        status: str,
        reason_code: str | None,
        control_ids: list[str],
        decided_at: str,
    ) -> dict[str, Any] | None:
        if status not in {"SKIPPED_BRANCH", "SKIPPED_CONDITION", "NOT_EXECUTED"}:
            return None
        kind = {
            "SKIPPED_BRANCH": "BRANCH_NOT_SELECTED",
            "SKIPPED_CONDITION": "CONDITION_NOT_MET",
        }.get(status)
        if kind is None:
            if reason_code == "RUN_CANCELLED":
                kind = "RUN_CANCELLED"
            elif reason_code == "NO_CANDIDATE_FOR_N16":
                kind = "LAUNCH_BLOCKED"
            else:
                kind = "UPSTREAM_BLOCKED"
        return {
            "kind": kind,
            "reason_code": reason_code,
            "reason": f"Scenario literal settled {node_id} as {status}: {reason_code}.",
            "decided_at": decided_at,
            "control_decision_id": control_ids[-1] if control_ids else None,
        }

    def _terminal_nodes(
        self,
        *,
        scenario: dict[str, Any],
        run_id: str,
        decisions: list[dict[str, Any]],
        attempts_by_node: dict[str, list[dict[str, Any]]],
        artifacts_by_node: dict[str, dict[int, dict[str, Any] | None]],
    ) -> list[dict[str, Any]]:
        ordinal = self._ordinal_by_scenario[scenario["scenario_key"]]
        by_type = self._control_ids_by_type(decisions)
        results: list[dict[str, Any]] = []
        for node_id, directive in scenario["node_plan"].items():
            attempts = deepcopy(attempts_by_node[node_id])
            control_ids = self._node_control_ids(node_id, directive, by_type)
            status = directive["status"]
            finished_at = _timestamp(ordinal, 900 + int(node_id[1:]))
            if status in {"SKIPPED_BRANCH", "SKIPPED_CONDITION", "NOT_EXECUTED"}:
                started_at = None
            elif attempts:
                started_at = attempts[0]["started_at"]
            else:
                started_at = None

            artifacts = [
                deepcopy(artifact)
                for number, artifact in artifacts_by_node[node_id].items()
                if artifact is not None
            ]
            output = None
            if directive["output_mode"] != "NONE":
                fixture_attempt = next(
                    (
                        attempt
                        for attempt in reversed(directive["attempts"])
                        if attempt["fixture_result_key"] is not None
                    ),
                    None,
                )
                if fixture_attempt is None:
                    raise ContractError(f"{node_id} output has no fixture")
                data = deepcopy(
                    self.fixtures.load_attempt_stub(fixture_attempt["fixture_result_key"])
                )
                data["fact_set_key"] = directive["fact_set_key"]
                data["artifact_ids"] = [item["artifact_id"] for item in artifacts]
                output = {
                    "payload_type": f"T01_PHASE1_{node_id}_MOCK_STUB",
                    "payload_version": "UNFROZEN",
                    "data": data,
                    "artifacts": artifacts,
                }

            attempt_issues_by_code = {
                issue["code"]: issue
                for attempt in attempts
                for issue in attempt["issues"]
            }
            issues: list[dict[str, Any]] = []
            for code in directive["error_codes"]:
                issue = attempt_issues_by_code.get(code)
                if issue is None:
                    attempt_id = attempts[-1]["attempt_id"] if attempts else None
                    issue = make_error(
                        run_id=run_id,
                        scenario_key=scenario["scenario_key"],
                        code=code,
                        occurred_at=finished_at,
                        node_id=node_id,
                        attempt_id=attempt_id,
                    )
                issues.append(deepcopy(issue))

            results.append(
                {
                    "node_id": node_id,
                    "status": status,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "output_completeness": OUTPUT_COMPLETENESS_BY_MODE[
                        directive["output_mode"]
                    ],
                    "output": output,
                    "attempts": attempts,
                    "disposition": self._disposition(
                        node_id=node_id,
                        status=status,
                        reason_code=directive["disposition_reason_code"],
                        control_ids=control_ids,
                        decided_at=finished_at,
                    ),
                    "issues": issues,
                    "upstream_node_ids": deepcopy(UPSTREAM_NODE_IDS[node_id]),
                    "control_decision_ids": control_ids,
                }
            )
        return results

    @staticmethod
    def _attempt_lookup(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {
            attempt["attempt_id"]: attempt
            for node in nodes
            for attempt in node["attempts"]
        }

    def _edge_traversals(
        self,
        *,
        scenario: dict[str, Any],
        run_id: str,
        edge_ids: list[str],
        decisions: list[dict[str, Any]],
        nodes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        ordinal = self._ordinal_by_scenario[scenario["scenario_key"]]
        by_type = self._control_ids_by_type(decisions)
        node_attempts = {
            node["node_id"]: node["attempts"] for node in nodes
        }
        occurrences: dict[str, int] = {}
        traversals: list[dict[str, Any]] = []
        for sequence, edge_id in enumerate(edge_ids, start=1):
            occurrences[edge_id] = occurrences.get(edge_id, 0) + 1
            source, target = EDGE_ENDPOINTS[edge_id]
            attempt_id = None
            control_id = None

            if edge_id in {"E012", "E013", "E014"}:
                control_id = next(
                    iter(by_type.get("DESIGN_SUITABILITY", [])), None
                )
            elif edge_id == "E015":
                index = occurrences[edge_id] - 1
                if index < len(node_attempts["N11"]):
                    attempt_id = node_attempts["N11"][index]["attempt_id"]
            elif edge_id == "E016":
                index = occurrences[edge_id] - 1
                if index < len(node_attempts["N12"]):
                    attempt_id = node_attempts["N12"][index]["attempt_id"]
                ids = by_type.get("N12_VALIDATION", [])
                if index < len(ids):
                    control_id = ids[index]
            elif edge_id in {"E017", "E018"}:
                if node_attempts["N12"]:
                    attempt_id = node_attempts["N12"][-1]["attempt_id"]
                ids = by_type.get("N12_VALIDATION", [])
                if ids:
                    control_id = ids[-1]
            elif edge_id == "E021":
                if node_attempts["N15"]:
                    attempt_id = node_attempts["N15"][-1]["attempt_id"]
                control_id = next(
                    iter(by_type.get("N15_DELIVERY_RECOMMENDATION", [])), None
                )
            elif edge_id == "E022":
                control_id = next(iter(by_type.get("N16_APPLICABILITY", [])), None)
            elif edge_id == "E023":
                control_id = next(iter(by_type.get("N17_APPLICABILITY", [])), None)
            elif edge_id == "E024":
                if node_attempts["N16"]:
                    attempt_id = node_attempts["N16"][-1]["attempt_id"]
                control_id = next(iter(by_type.get("N16_APPLICABILITY", [])), None)
            elif edge_id == "E025":
                if node_attempts["N17"]:
                    attempt_id = node_attempts["N17"][-1]["attempt_id"]
                control_id = next(iter(by_type.get("N17_APPLICABILITY", [])), None)
            elif source is not None and node_attempts[source]:
                attempt_id = node_attempts[source][-1]["attempt_id"]

            traversals.append(
                {
                    "traversal_id": _identity(
                        "traversal", f"{run_id}:{sequence}:{edge_id}"
                    ),
                    "sequence": sequence,
                    "edge_id": edge_id,
                    "occurred_at": _timestamp(ordinal, 600 + sequence),
                    "source_node_id": source,
                    "target_node_id": target,
                    "attempt_id": attempt_id,
                    "control_decision_id": control_id,
                }
            )
        return traversals

    def _audit(
        self,
        *,
        request: dict[str, Any],
        run_id: str,
        run_status: str,
        scenario_key: str,
        nodes: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        traversals: list[dict[str, Any]],
        issues: list[dict[str, Any]],
        ordinal: int,
        recovery_of_run_id: str | None,
        terminal: bool,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def add(
            event_type: str,
            *,
            node_id: str | None = None,
            attempt_id: str | None = None,
            edge_id: str | None = None,
            control_id: str | None = None,
            details: dict[str, Any] | None = None,
        ) -> None:
            sequence = len(events) + 1
            events.append(
                {
                    "event_id": _identity(
                        "event", f"{run_id}:{sequence}:{event_type}"
                    ),
                    "sequence": sequence,
                    "event_type": event_type,
                    "occurred_at": _timestamp(ordinal, 1000 + sequence),
                    "actor": _actor(
                        "MOCK_SCENARIO", "t01_phase1_mock_v01.scenario_engine"
                    ),
                    "node_id": node_id,
                    "attempt_id": attempt_id,
                    "edge_id": edge_id,
                    "control_decision_id": control_id,
                    "details": details or {"mock_only": True},
                }
            )

        add(
            "RUN_CREATED",
            details={
                "mock_only": True,
                "run_id": run_id,
                "scenario_ref": f"t01_phase1_mock_v01.scenario.{scenario_key}",
            },
        )
        if recovery_of_run_id is not None:
            add(
                "RECOVERY_REQUESTED",
                details={
                    "mock_only": True,
                    "recovery_of_run_id": recovery_of_run_id,
                },
            )
        for decision in decisions:
            add(
                "CONTROL_DECISION_RECORDED",
                node_id=decision["node_id"],
                attempt_id=decision["attempt_id"],
                control_id=decision["decision_id"],
                details={
                    "mock_only": True,
                    "source": "SCENARIO_LITERAL",
                    "decision": decision["decision"],
                },
            )
        for traversal in traversals:
            add(
                "EDGE_TRAVERSED",
                attempt_id=traversal["attempt_id"],
                edge_id=traversal["edge_id"],
                control_id=traversal["control_decision_id"],
            )
        for node in nodes:
            if node["status"] != "PENDING":
                attempt_id = (
                    node["attempts"][-1]["attempt_id"] if node["attempts"] else None
                )
                add(
                    "NODE_STATE_CHANGED",
                    node_id=node["node_id"],
                    attempt_id=attempt_id,
                    details={"mock_only": True, "status": node["status"]},
                )
        for issue in issues:
            add(
                "ERROR_RECORDED",
                node_id=issue["node_id"],
                attempt_id=issue["attempt_id"],
                details={
                    "mock_only": True,
                    "error_id": issue["error_id"],
                    "code": issue["code"],
                },
            )
        add(
            "RUN_STATE_CHANGED",
            details={
                "mock_only": True,
                "to": run_status,
                "terminal": terminal,
            },
        )
        if terminal:
            add(
                "HANDOFF_STATE_CHANGED",
                details={"mock_only": True, "status": "NOT_DEPLOYED"},
            )
        return {
            "trace_id": request["audit"]["trace_id"],
            "correlation_id": request["audit"]["correlation_id"],
            "events": events,
            "audit_artifacts": [],
        }

    @staticmethod
    def _run_issue_list(
        expected_codes: list[str], nodes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        available: dict[str, dict[str, Any]] = {}
        for node in nodes:
            for issue in node["issues"]:
                available.setdefault(issue["code"], issue)
            for attempt in node["attempts"]:
                for issue in attempt["issues"]:
                    available.setdefault(issue["code"], issue)
        missing = [code for code in expected_codes if code not in available]
        if missing:
            raise ContractError(f"run error codes lack node/attempt issue: {missing}")
        return [deepcopy(available[code]) for code in expected_codes]

    def _final_result(
        self,
        *,
        scenario: dict[str, Any],
        nodes: list[dict[str, Any]],
        ordinal: int,
    ) -> dict[str, Any]:
        expected = scenario["expected_run"]
        n18 = nodes[-1]
        artifacts = []
        if n18["output"] is not None:
            artifacts = deepcopy(n18["output"]["artifacts"])
        return {
            "result_kind": expected["result_kind"],
            "summary": {
                "payload_type": f"T01_PHASE1_MOCK_{expected['result_kind']}_STUB",
                "payload_version": "UNFROZEN",
                "mock_only": True,
                "scientific_compute": False,
                "scientific_payload_schema_frozen": False,
                "scenario_key": scenario["scenario_key"],
                "branch_states": {
                    "N16": nodes[15]["status"],
                    "N17": nodes[16]["status"],
                },
                "run_error_codes": deepcopy(expected["run_error_codes"]),
                "disclosures": deepcopy(expected["disclosures"]),
            },
            "artifacts": artifacts,
            "handoff": {
                "status": expected["handoff_status"],
                "delivered": False,
                "external_reference": None,
                "occurred_at": _timestamp(ordinal, 1200),
                "issue_id": None,
            },
        }

    def _run_envelope(
        self,
        *,
        request: dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
        run_status: str,
        recovery_of_run_id: str | None,
        nodes: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        traversals: list[dict[str, Any]],
        issues: list[dict[str, Any]],
        result: dict[str, Any] | None,
        snapshot_tag: str,
    ) -> dict[str, Any]:
        ordinal = self._ordinal_by_scenario[scenario["scenario_key"]]
        terminal = result is not None
        current = [node["node_id"] for node in nodes if node["status"] == "RUNNING"]
        envelope = {
            "envelope_type": "PHASE1_RUN_RESULT",
            "contract_version": ENVELOPE_CONTRACT_VERSION,
            "topology_version": TOPOLOGY_VERSION,
            "node_registry_version": NODE_REGISTRY_VERSION,
            "control_flow_version": CONTROL_FLOW_VERSION,
            "envelope_id": _envelope_id(f"{run_id}:{snapshot_tag}"),
            "created_at": _timestamp(ordinal, 1300),
            "execution_mode": "MOCK",
            "execution_profile": "PHASE1_FULL",
            "data_classification": "MOCK_DATA",
            "scientific_compute": False,
            "run_id": run_id,
            "request_id": request["request_id"],
            "idempotency_key": request["idempotency_key"],
            "scenario_ref": request["scenario_ref"],
            "run_status": run_status,
            "recovery_of_run_id": recovery_of_run_id,
            "started_at": _timestamp(ordinal, 1),
            "finished_at": _timestamp(ordinal, 1400) if terminal else None,
            "current_node_ids": current,
            "input_fingerprints": deepcopy(request["input_fingerprints"]),
            "control_decisions": decisions,
            "edge_traversals": traversals,
            "node_results": nodes,
            "result": result,
            "issues": issues,
            "audit": self._audit(
                request=request,
                run_id=run_id,
                run_status=run_status,
                scenario_key=scenario["scenario_key"],
                nodes=nodes,
                decisions=decisions,
                traversals=traversals,
                issues=issues,
                ordinal=ordinal,
                recovery_of_run_id=recovery_of_run_id,
                terminal=terminal,
            ),
        }
        self.bundle.validate_envelope(envelope, f"run snapshot {scenario['scenario_key']}")
        return envelope

    def terminal(
        self,
        *,
        request: dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
        recovery_of_run_id: str | None = None,
    ) -> dict[str, Any]:
        attempts, artifacts = self._all_attempts(scenario, run_id)
        edge_ids = list(scenario["edge_plan"])
        decisions = self._control_decisions(
            scenario=scenario, run_id=run_id, edge_ids=edge_ids
        )
        nodes = self._terminal_nodes(
            scenario=scenario,
            run_id=run_id,
            decisions=decisions,
            attempts_by_node=attempts,
            artifacts_by_node=artifacts,
        )
        traversals = self._edge_traversals(
            scenario=scenario,
            run_id=run_id,
            edge_ids=edge_ids,
            decisions=decisions,
            nodes=nodes,
        )
        issues = self._run_issue_list(
            scenario["expected_run"]["run_error_codes"], nodes
        )
        result = self._final_result(
            scenario=scenario,
            nodes=nodes,
            ordinal=self._ordinal_by_scenario[scenario["scenario_key"]],
        )
        return self._run_envelope(
            request=request,
            scenario=scenario,
            run_id=run_id,
            run_status=scenario["expected_run"]["run_status"],
            recovery_of_run_id=recovery_of_run_id,
            nodes=nodes,
            decisions=decisions,
            traversals=traversals,
            issues=issues,
            result=result,
            snapshot_tag="terminal",
        )

    @staticmethod
    def _pending_node(node_id: str) -> dict[str, Any]:
        return {
            "node_id": node_id,
            "status": "PENDING",
            "started_at": None,
            "finished_at": None,
            "output_completeness": "NONE",
            "output": None,
            "attempts": [],
            "disposition": None,
            "issues": [],
            "upstream_node_ids": deepcopy(UPSTREAM_NODE_IDS[node_id]),
            "control_decision_ids": [],
        }

    @staticmethod
    def _running_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
        active = deepcopy(attempt)
        active["status"] = "RUNNING"
        active["finished_at"] = None
        active["output_artifact_ids"] = []
        active["issues"] = []
        active["metrics"]["runtime_ms"] = None
        return active

    def checkpoint(
        self,
        *,
        request: dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
        checkpoint_fact: str,
        recovery_of_run_id: str | None = None,
    ) -> dict[str, Any]:
        if checkpoint_fact == "TERMINAL_PROJECTION_AVAILABLE":
            return self.terminal(
                request=request,
                scenario=scenario,
                run_id=run_id,
                recovery_of_run_id=recovery_of_run_id,
            )

        attempts_by_node, artifacts_by_node = self._all_attempts(scenario, run_id)
        edge_ids: list[str]
        if checkpoint_fact == "CREATE_RUN_ACCEPTED":
            edge_ids = ["E001"]
        elif checkpoint_fact in {
            "N08_ATTEMPT_ACTIVE",
            "N08_ATTEMPT_1_FAILED_RETRYABLE",
            "N08_RECOVERY_ACCEPTED",
        }:
            edge_ids = list(scenario["edge_plan"][: scenario["edge_plan"].index("E008") + 1])
        elif checkpoint_fact == "N16_ATTEMPT_ACTIVE":
            edge_ids = list(scenario["edge_plan"][: scenario["edge_plan"].index("E022") + 1])
        elif checkpoint_fact == "N16_TIMEOUT":
            edge_ids = list(scenario["edge_plan"][: scenario["edge_plan"].index("E024") + 1])
        elif checkpoint_fact in {"EXPLICIT_CANCEL_ACCEPTED", "N08_TIMEOUT"}:
            edge_ids = list(scenario["edge_plan"])
        else:
            raise ContractError(f"unsupported checkpoint fact: {checkpoint_fact}")

        decisions = self._control_decisions(
            scenario=scenario, run_id=run_id, edge_ids=edge_ids
        )
        terminal_nodes = self._terminal_nodes(
            scenario=scenario,
            run_id=run_id,
            decisions=decisions,
            attempts_by_node=attempts_by_node,
            artifacts_by_node=artifacts_by_node,
        )
        terminal_by_id = {node["node_id"]: node for node in terminal_nodes}

        if checkpoint_fact == "CREATE_RUN_ACCEPTED":
            completed_before = 0
            active_node = "N01"
        elif checkpoint_fact in {
            "N08_ATTEMPT_ACTIVE",
            "N08_ATTEMPT_1_FAILED_RETRYABLE",
            "N08_RECOVERY_ACCEPTED",
        }:
            completed_before = 7
            active_node = "N08"
        elif checkpoint_fact in {"N16_ATTEMPT_ACTIVE", "N16_TIMEOUT"}:
            completed_before = 15
            active_node = "N16"
        else:
            completed_before = 18
            active_node = ""

        nodes: list[dict[str, Any]] = []
        for index, node_id in enumerate(NODE_IDS):
            if index < completed_before:
                nodes.append(deepcopy(terminal_by_id[node_id]))
            else:
                nodes.append(self._pending_node(node_id))

        if active_node:
            target_index = NODE_IDS.index(active_node)
            terminal_node = terminal_by_id[active_node]
            if checkpoint_fact == "N08_ATTEMPT_1_FAILED_RETRYABLE":
                first = deepcopy(terminal_node["attempts"][0])
                nodes[target_index] = {
                    **self._pending_node(active_node),
                    "status": "FAILED",
                    "started_at": first["started_at"],
                    "finished_at": first["finished_at"],
                    "attempts": [first],
                    "issues": deepcopy(first["issues"]),
                }
            elif checkpoint_fact == "N08_RECOVERY_ACCEPTED":
                first = deepcopy(terminal_node["attempts"][0])
                second = self._running_attempt(terminal_node["attempts"][1])
                nodes[target_index] = {
                    **self._pending_node(active_node),
                    "status": "RUNNING",
                    "started_at": first["started_at"],
                    "attempts": [first, second],
                    "issues": deepcopy(first["issues"]),
                }
            elif checkpoint_fact in {"N16_TIMEOUT"}:
                nodes[target_index] = deepcopy(terminal_node)
            else:
                first = self._running_attempt(terminal_node["attempts"][0])
                nodes[target_index] = {
                    **self._pending_node(active_node),
                    "status": "RUNNING",
                    "started_at": first["started_at"],
                    "attempts": [first],
                    "control_decision_ids": deepcopy(
                        terminal_node["control_decision_ids"]
                    ),
                }

        if checkpoint_fact in {"EXPLICIT_CANCEL_ACCEPTED", "N08_TIMEOUT"}:
            nodes = terminal_nodes

        traversals = self._edge_traversals(
            scenario=scenario,
            run_id=run_id,
            edge_ids=edge_ids,
            decisions=decisions,
            nodes=nodes,
        )
        return self._run_envelope(
            request=request,
            scenario=scenario,
            run_id=run_id,
            run_status="RUNNING",
            recovery_of_run_id=recovery_of_run_id,
            nodes=nodes,
            decisions=decisions,
            traversals=traversals,
            issues=[],
            result=None,
            snapshot_tag=checkpoint_fact.lower(),
        )

    def recovery_origin_failure(
        self,
        *,
        request: dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        snapshot = self.checkpoint(
            request=request,
            scenario=scenario,
            run_id=run_id,
            checkpoint_fact="N08_ATTEMPT_1_FAILED_RETRYABLE",
        )
        nodes = deepcopy(snapshot["node_results"])
        ordinal = self._ordinal_by_scenario[scenario["scenario_key"]]
        for node_id in NODE_IDS[8:]:
            index = NODE_IDS.index(node_id)
            nodes[index] = {
                **self._pending_node(node_id),
                "status": "NOT_EXECUTED",
                "finished_at": _timestamp(ordinal, 900 + int(node_id[1:])),
                "disposition": {
                    "kind": "UPSTREAM_BLOCKED",
                    "reason_code": "UPSTREAM_RESULT_UNAVAILABLE",
                    "reason": "Original run ended before explicit recovery created a new run.",
                    "decided_at": _timestamp(ordinal, 900 + int(node_id[1:])),
                    "control_decision_id": None,
                },
            }
        issue = deepcopy(nodes[7]["issues"][0])
        result = {
            "result_kind": "FAILURE",
            "summary": {
                "payload_type": "T01_PHASE1_MOCK_FAILURE_STUB",
                "payload_version": "UNFROZEN",
                "mock_only": True,
                "scientific_compute": False,
                "scientific_payload_schema_frozen": False,
                "scenario_key": scenario["scenario_key"],
                "disclosures": [
                    "MOCK_DATA_ONLY",
                    "NOT_SCIENTIFIC_EVIDENCE",
                    "RECOVERY_CREATED_NEW_RUN",
                ],
            },
            "artifacts": [],
            "handoff": {
                "status": "NOT_DEPLOYED",
                "delivered": False,
                "external_reference": None,
                "occurred_at": _timestamp(ordinal, 1200),
                "issue_id": None,
            },
        }
        return self._run_envelope(
            request=request,
            scenario=scenario,
            run_id=run_id,
            run_status="FAILED",
            recovery_of_run_id=None,
            nodes=nodes,
            decisions=[],
            traversals=deepcopy(snapshot["edge_traversals"]),
            issues=[issue],
            result=result,
            snapshot_tag="recovery-origin-failed",
        )
