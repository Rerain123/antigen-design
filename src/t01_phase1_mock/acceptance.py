"""Executable M2 adapter for the frozen M1-07 blocker assertion catalog."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .catalog import SpecificationBundle, validate_instance
from .constants import (
    ASSERTION_OPERATOR_NAMES,
    ENVELOPE_ID_PATTERN,
    LEGACY_IDENTITY_MARKERS,
    M2_RESULT_VERSION,
    MODE_BY_OUTPUT_COMPLETENESS,
    NODE_IDS,
    PROHIBITED_RUNTIME_VALUE_TOKENS,
    REQUEST_ID_PATTERN,
    RUN_ID_PATTERN,
)
from .engine import MockBackend, SubmissionResult
from .fixtures import FixtureRepository
from .jsonio import (
    ContractError,
    canonical_sha256,
    deep_copy,
    load_json,
    pretty_json_bytes,
)
from .paths import M2_ACCEPTANCE_RESULT_PATH, M2_ACCEPTANCE_RESULT_SCHEMA_PATH


class AssertionOperatorRegistry:
    """Closed implementation of all 28 M1-07 assertion operators."""

    NAMES = ASSERTION_OPERATOR_NAMES

    def evaluate(
        self,
        name: str,
        actual: Any,
        expected: Any,
    ) -> bool:
        if name not in self.NAMES:
            raise ContractError(f"unknown assertion operator: {name}")
        if name == "JSON_SCHEMA_VALID":
            if not isinstance(expected, dict):
                raise ContractError("JSON_SCHEMA_VALID expected value must be a schema")
            for index, document in enumerate(_flatten(actual)):
                validate_instance(
                    _external_envelope(document),
                    expected,
                    f"selected envelope {index}",
                )
            return True
        if name == "REFERENCES_RESOLVE":
            return _selected_references_resolve(actual, expected)
        if name == "NO_SCIENTIFIC_VALUES":
            return _selected_values_are_non_scientific(actual, expected)
        if name == "COUNT_EQUALS":
            def count_value(value: Any) -> int:
                if isinstance(value, bool):
                    raise ContractError("COUNT_EQUALS does not accept booleans")
                if isinstance(value, int):
                    return value
                try:
                    return len(value)
                except TypeError as exc:
                    raise ContractError(
                        "COUNT_EQUALS actual value must be an integer or sized value"
                    ) from exc

            if isinstance(expected, list):
                if not isinstance(actual, list) or len(actual) != len(expected):
                    return False
                if any(isinstance(item, bool) or not isinstance(item, int) for item in expected):
                    raise ContractError(
                        "COUNT_EQUALS vector expected value must contain integers"
                    )
                return [count_value(item) for item in actual] == expected
            if not isinstance(expected, int) or isinstance(expected, bool):
                raise ContractError(
                    "COUNT_EQUALS expected value must be an integer or integer vector"
                )
            return count_value(actual) == expected
        if name == "SET_EQUALS":
            def stable_identity(value: Any) -> Any:
                if isinstance(value, dict) and isinstance(value.get("workflow_id"), str):
                    return value["workflow_id"]
                if isinstance(value, dict) and isinstance(value.get("tool_id"), str):
                    return value["tool_id"]
                return value

            left = [stable_identity(item) for item in _flatten(actual)]
            right = [stable_identity(item) for item in _flatten(expected)]
            try:
                return set(left) == set(right)
            except TypeError as exc:
                raise ContractError("SET_EQUALS selected values are not hashable identities") from exc
        if name == "BIJECTION":
            left, right = actual
            return len(left) == len(set(left)) and len(right) == len(set(right)) and set(left) == set(right)
        if name == "EXACT_CATALOG_PROJECTION":
            return _selected_projection_equals(actual, expected)
        if name in {
            "NODE_ATTEMPT_FIELD_SEQUENCE_EQUALS",
            "CONTROL_DECISION_SEQUENCE_EQUALS",
            "SUBMISSION_ACTION_EQUALS",
            "IDENTITY_RELATION_EQUALS",
            "EMISSION_COUNT_EQUALS",
            "NO_STUB_PROMOTION",
        }:
            return actual == expected
        if name == "NORMALIZED_EQUALS":
            if expected is True:
                return (
                    isinstance(actual, list)
                    and len(actual) == 2
                    and actual[0] == actual[1]
                )
            return actual == expected
        if name == "FIELD_EQUALS":
            return _semantic_equals(actual, expected)
        if name == "FIELD_ABSENT":
            return all(field not in actual for field in expected)
        if name == "MATCHES_REGEX":
            if isinstance(expected, dict):
                if not isinstance(actual, list) or len(actual) != 4:
                    raise ContractError("identity selector must resolve four groups")
                request_id, run_id, envelope_id, recovery_ids = actual
                values_and_patterns = [
                    (request_id, expected.get("request_id_pattern")),
                    (run_id, expected.get("run_id_pattern")),
                    (envelope_id, expected.get("envelope_id_pattern")),
                    *[
                        (value, expected.get("run_id_pattern"))
                        for value in recovery_ids
                    ],
                ]
                return all(
                    isinstance(value, str)
                    and isinstance(pattern, str)
                    and re.fullmatch(pattern, value) is not None
                    for value, pattern in values_and_patterns
                )
            values = actual if isinstance(actual, (list, tuple)) else [actual]
            patterns = expected if isinstance(expected, (list, tuple)) else [expected] * len(values)
            if not all(isinstance(value, str) for value in values) or not all(
                isinstance(pattern, str) for pattern in patterns
            ):
                raise ContractError("MATCHES_REGEX accepts strings only")
            return len(values) == len(patterns) and all(
                re.fullmatch(pattern, value) is not None
                for value, pattern in zip(values, patterns, strict=True)
            )
        if name == "CONTAINS_NONE":
            if not isinstance(expected, list):
                raise ContractError("CONTAINS_NONE expected value must be an array")
            ordinary_tokens = [item for item in expected if item != "MOCK-"]
            return _contains_none(actual, ordinary_tokens) and (
                "MOCK-" not in expected
                or all(
                    not item.startswith("MOCK-")
                    for item in _string_values(actual)
                )
            )
        if name == "NODE_STATUS_ALL":
            return all(value == expected for value in actual)
        if name == "NODE_ATTEMPT_COUNT_EQUALS":
            return [len(value) for value in actual] == expected
        if name == "EDGE_PRESENT":
            return all(edge in actual for edge in expected)
        if name == "EDGE_ABSENT":
            return all(edge not in actual for edge in expected)
        if name == "EDGE_ORDERED_SUBSEQUENCE":
            return _ordered_subsequence(actual, expected)
        if name == "NO_CONTROL_AFTER_NODE":
            if not isinstance(actual, (list, tuple)) or len(actual) != 2:
                raise ContractError("NO_CONTROL_AFTER_NODE expects control and node status")
            controls, node_status = actual
            if not isinstance(controls, dict) or not isinstance(expected, dict):
                raise ContractError("NO_CONTROL_AFTER_NODE expects normalized objects")
            return (
                node_status in {"FAILED", "TIMED_OUT", "CANCELLED"}
                and expected.get("control_state") == "NOT_REACHED"
                and all(
                    isinstance(value, dict)
                    and (value.get("state") or value.get("mode")) == "NOT_REACHED"
                    for value in controls.values()
                )
            )
        if name == "JOIN_PRECONDITION":
            if not isinstance(actual, (list, tuple)) or len(actual) != 3:
                raise ContractError("JOIN_PRECONDITION expects two statuses and edge plan")
            left_status, right_status, edges = actual
            if not isinstance(expected, dict):
                raise ContractError("JOIN_PRECONDITION expected value must be an object")
            join_edge = expected.get("join_edge")
            arrivals = expected.get("required_arrival_edges")
            if not isinstance(edges, list) or not isinstance(arrivals, list):
                raise ContractError("JOIN_PRECONDITION edge values must be arrays")
            if join_edge not in edges or any(edge not in edges for edge in arrivals):
                return False
            join_index = edges.index(join_edge)
            return (
                all(edges.index(edge) < join_index for edge in arrivals)
                and left_status not in {"PENDING", "RUNNING"}
                and right_status not in {"PENDING", "RUNNING"}
            )
        if name == "ORIGINAL_RUN_UNCHANGED":
            if expected is not True or not isinstance(actual, (list, tuple)):
                return False
            return len(actual) == 2 and actual[0] is not None and actual[0] == actual[1]
        if name == "PATH_WITHIN":
            try:
                Path(actual).resolve().relative_to(Path(expected).resolve())
            except ValueError:
                return False
            return True
        if name == "HASH_UNCHANGED":
            if isinstance(actual, (list, tuple)) and len(actual) == 2:
                return actual[0] == actual[1]
            return actual == expected
        raise ContractError(f"operator has no evaluator: {name}")


def _flatten(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return [item for nested in value for item in _flatten(nested)]
    return [value]


def _string_values(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _string_values(item)


def _external_envelope(document: Any) -> Any:
    if not (
        isinstance(document, dict)
        and document.get("envelope_type") == "PHASE1_RUN_RESULT"
    ):
        return document
    adapter_only = {
        "node",
        "control",
        "expected_run",
        "handoff_status",
        "result_kind",
        "run_error_codes",
        "errors",
        "artifact_refs",
        "error_refs",
        "attempt_refs",
        "audit_refs",
        "recovery_refs",
        "control_emission_count",
    }
    return {key: value for key, value in document.items() if key not in adapter_only}


def _semantic_equals(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict) and set(expected) <= {"contains", "excludes"}:
        if not isinstance(actual, list):
            return False
        contains = expected.get("contains", [])
        excludes = expected.get("excludes", [])
        return all(item in actual for item in contains) and all(
            item not in actual for item in excludes
        )
    if expected == {"reference_preserved": True}:
        return isinstance(actual, list) and bool(actual) and all(
            isinstance(item, dict)
            and isinstance(item.get("artifact_id"), str)
            and isinstance(item.get("uri"), str)
            and item.get("integrity_status") == "VERIFIED"
            and re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) is not None
            for item in actual
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _semantic_equals(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected, strict=True)
        )
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual == expected
    return type(actual) is type(expected) and actual == expected


def _selected_projection_equals(actual: Any, expected: Any) -> bool:
    if actual == expected:
        return True
    if not (
        isinstance(actual, list)
        and isinstance(expected, list)
        and len(actual) == len(expected) == 5
    ):
        return False
    submissions, controls, nodes, edges, expected_run = actual
    submission_plan, control_plan, node_plan, edge_plan, catalog_run = expected
    if not (
        isinstance(submissions, list)
        and isinstance(submission_plan, list)
        and len(submissions) == len(submission_plan)
    ):
        return False
    for result, directive in zip(submissions, submission_plan, strict=True):
        if result.get("action") != directive.get("expected_action"):
            return False
        if result.get("error_code") != directive.get("expected_error_code"):
            return False

    normalized_nodes: dict[str, dict[str, Any]] = {}
    if not isinstance(nodes, list):
        return False
    for node in nodes:
        output = node.get("output")
        disposition = node.get("disposition")
        normalized_nodes[node.get("node_id")] = {
            "status": node.get("status"),
            "attempts": node.get("attempts"),
            "output_mode": node.get("output_mode"),
            "fact_set_key": None if output is None else output.get("fact_set_key"),
            "disposition_reason_code": (
                None if disposition is None else disposition.get("reason_code")
            ),
            "error_codes": [item.get("code") for item in node.get("issues", [])],
        }
    return (
        controls == control_plan
        and normalized_nodes == node_plan
        and edges == edge_plan
        and expected_run == catalog_run
    )


def _selected_references_resolve(actual: Any, expected: Any) -> bool:
    if not isinstance(expected, dict):
        raise ContractError("REFERENCES_RESOLVE expected value must be an object")
    if set(expected) == {"dangling_reference_count", "duplicate_identity_count"}:
        if expected != {"dangling_reference_count": 0, "duplicate_identity_count": 0}:
            return False
        if not isinstance(actual, list) or len(actual) != 4:
            return False
        artifacts, errors, attempts, audit_events = actual

        def unique_or_equal(items: list[dict[str, Any]], identity_key: str):
            by_id: dict[str, dict[str, Any]] = {}
            for item in items:
                identity = item.get(identity_key)
                if not isinstance(identity, str):
                    return None
                if identity in by_id and by_id[identity] != item:
                    return None
                by_id[identity] = item
            return by_id

        artifact_by_id = unique_or_equal(artifacts, "artifact_id")
        error_by_id = unique_or_equal(errors, "error_id")
        attempt_by_id = unique_or_equal(attempts, "attempt_id")
        event_by_id = unique_or_equal(audit_events, "event_id")
        if any(item is None for item in (artifact_by_id, error_by_id, attempt_by_id, event_by_id)):
            return False
        assert artifact_by_id is not None
        assert error_by_id is not None
        assert attempt_by_id is not None
        for attempt in attempt_by_id.values():
            if any(key not in artifact_by_id for key in attempt["output_artifact_ids"]):
                return False
            predecessor = attempt["recovery_of_attempt_id"]
            if predecessor is not None and predecessor not in attempt_by_id:
                return False
        for artifact in artifact_by_id.values():
            producer = artifact["source_attempt_id"]
            if producer is not None and producer not in attempt_by_id:
                return False
        for issue in error_by_id.values():
            attempt_id = issue["attempt_id"]
            if attempt_id is not None and attempt_id not in attempt_by_id:
                return False
            if any(key not in artifact_by_id for key in issue["artifact_ids"]):
                return False
            cause = issue["caused_by_error_id"]
            if cause is not None and cause not in error_by_id:
                return False
        return True

    selected = [item for item in _flatten(actual) if item is not None]
    return (
        all(isinstance(item, str) for item in selected)
        and len(selected) == len(set(selected))
        and set(selected) == set(expected)
    )


def _selected_values_are_non_scientific(actual: Any, expected: Any) -> bool:
    if expected != {
        "scientific_assertion_count": 0,
        "remote_retrieval_count": 0,
        "scientific_execution_count": 0,
    }:
        return False

    def runtime_projection(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: runtime_projection(item)
                for key, item in value.items()
                if key not in {"$schema", "$id", "title", "description"}
            }
        if isinstance(value, list):
            return [runtime_projection(item) for item in value]
        return value

    return _contains_none(runtime_projection(actual), PROHIBITED_RUNTIME_VALUE_TOKENS)


class SelectorAdapter:
    """Resolve the frozen M1-07 selector grammar against a read-only case view."""

    ROOTS = (
        "catalog",
        "fixture",
        "acceptance",
        "request",
        "submission",
        "run",
        "trace",
        "workflow",
        "original_run",
    )
    _SEGMENT = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*|[*])(?:\[(?P<bracket>[^]]+)\])?$")

    def __init__(self, view: dict[str, Any]) -> None:
        if tuple(view) != self.ROOTS:
            raise ContractError("selector view roots do not match the frozen contract")
        self._view = deep_copy(view)

    def resolve(self, expression: str) -> Any:
        if not isinstance(expression, str) or not expression:
            raise ContractError("selector must be a non-empty string")
        parts = self._split_outside_brackets(expression, "|")
        catalog_prefix = (
            "catalog.current_scenario"
            if parts[0].startswith("catalog.current_scenario.")
            else None
        )
        resolved: list[Any] = []
        for part in parts:
            root_name = part.split(".", 1)[0].split("[", 1)[0]
            if root_name not in self.ROOTS:
                if catalog_prefix is None:
                    raise ContractError(f"selector has no declared root: {part}")
                part = f"{catalog_prefix}.{part}"
            resolved.append(self._resolve_one(part))
        return resolved[0] if len(resolved) == 1 else resolved

    def _resolve_one(self, selector: str) -> Any:
        segments = self._split_outside_brackets(selector, ".")
        root_segment = segments.pop(0)
        match = self._SEGMENT.fullmatch(root_segment)
        if match is None:
            raise ContractError(f"unsupported selector root: {root_segment}")
        root = match.group("name")
        if root not in self.ROOTS:
            raise ContractError(f"unknown selector root: {root}")
        value: Any = self._apply_bracket(self._view[root], match.group("bracket"))
        for raw_segment in segments:
            match = self._SEGMENT.fullmatch(raw_segment)
            if match is None:
                raise ContractError(f"unsupported selector segment: {raw_segment}")
            value = self._step(value, match.group("name"), match.group("bracket"))
        return deep_copy(value)

    @staticmethod
    def _split_outside_brackets(value: str, delimiter: str) -> list[str]:
        parts: list[str] = []
        start = 0
        depth = 0
        for index, character in enumerate(value):
            if character == "[":
                depth += 1
            elif character == "]":
                depth -= 1
                if depth < 0:
                    raise ContractError(f"unbalanced selector brackets: {value}")
            elif character == delimiter and depth == 0:
                parts.append(value[start:index])
                start = index + 1
        if depth != 0:
            raise ContractError(f"unbalanced selector brackets: {value}")
        parts.append(value[start:])
        return parts

    def _step(self, value: Any, name: str, bracket: str | None) -> Any:
        if isinstance(value, list):
            mapped = [self._step(item, name, bracket) for item in value]
            return [nested for item in mapped for nested in item] if all(
                isinstance(item, list) for item in mapped
            ) else mapped
        if name == "*":
            if not isinstance(value, dict):
                raise ContractError("wildcard selector requires an object")
            selected: Any = list(value.values())
        else:
            if not isinstance(value, dict) or name not in value:
                raise ContractError(f"missing selector field: {name}")
            selected = value[name]
        return self._apply_bracket(selected, bracket)

    @staticmethod
    def _apply_bracket(value: Any, bracket: str | None) -> Any:
        if bracket is None:
            return value
        if bracket == "*":
            if isinstance(value, dict):
                return list(value.values())
            if isinstance(value, list):
                return value
            raise ContractError("[*] requires an array or object")
        if ".." in bracket:
            start, end = bracket.split("..", 1)
            if isinstance(value, dict):
                keys = list(value)
                try:
                    return [value[key] for key in keys[keys.index(start) : keys.index(end) + 1]]
                except ValueError as exc:
                    raise ContractError(f"unknown selector range: {bracket}") from exc
            if isinstance(value, list):
                first = int(start) - 1
                last = len(value) if end == "n" else int(end)
                return value[first:last]
            raise ContractError("selector range requires an array or object")
        if "|" in bracket and isinstance(value, dict):
            keys = bracket.split("|")
            if any(key not in value for key in keys):
                raise ContractError(f"selector union contains an unknown key: {bracket}")
            return [value[key] for key in keys]
        if "=" in bracket:
            field, literal = bracket.split("=", 1)
            if not isinstance(value, list):
                raise ContractError("selector filter requires an array")
            expected: Any = int(literal) if literal.isdigit() else literal
            matches = [
                item
                for item in value
                if isinstance(item, dict) and item.get(field) == expected
            ]
            if len(matches) != 1:
                raise ContractError(
                    f"selector filter must resolve exactly once: {bracket}"
                )
            return matches[0]
        if isinstance(value, list) and bracket.isdigit():
            index = int(bracket) - 1
            if index < 0 or index >= len(value):
                raise ContractError(f"selector index is out of range: {bracket}")
            return value[index]
        if isinstance(value, dict) and bracket in value:
            return value[bracket]
        raise ContractError(f"selector key does not resolve: {bracket}")


@dataclass
class CaseExecution:
    scenario: dict[str, Any]
    fixture_case: dict[str, Any]
    acceptance_case: dict[str, Any]
    requests: list[dict[str, Any]]
    submissions: list[dict[str, Any]]
    checkpoints: list[dict[str, Any]]
    final_run: dict[str, Any]
    final_run_id: str
    original_hash_before: str | None = None
    original_hash_after: str | None = None
    control_emission_count: int = 1


def _node_map(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["node_id"]: item for item in run["node_results"]}


def _edge_ids(run: dict[str, Any]) -> list[str]:
    return [item["edge_id"] for item in run["edge_traversals"]]


def _control_decisions(
    run: dict[str, Any], control_type: str
) -> list[dict[str, Any]]:
    return [
        item for item in run["control_decisions"] if item["control_type"] == control_type
    ]


def _text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _contains_none(value: Any, tokens: list[str] | tuple[str, ...]) -> bool:
    serialized = _text(value)
    return all(token not in serialized for token in tokens)


def _ordered_subsequence(values: list[str], expected: list[str]) -> bool:
    position = 0
    for value in values:
        if position < len(expected) and value == expected[position]:
            position += 1
    return position == len(expected)


def _attempt_recovery_numbers(node: dict[str, Any]) -> list[int | None]:
    number_by_id = {
        attempt["attempt_id"]: attempt["attempt_number"]
        for attempt in node["attempts"]
    }
    return [
        (
            None
            if attempt["recovery_of_attempt_id"] is None
            else number_by_id[attempt["recovery_of_attempt_id"]]
        )
        for attempt in node["attempts"]
    ]


def _attempt_output_mode(
    attempt: dict[str, Any], artifact_by_id: dict[str, dict[str, Any]]
) -> str:
    if not attempt["output_artifact_ids"]:
        return "NONE"
    roles = {
        artifact_by_id[artifact_id]["artifact_role"]
        for artifact_id in attempt["output_artifact_ids"]
    }
    return "PARTIAL_STUB" if "PARTIAL_RESULT" in roles else "COMPLETE_STUB"


def normalize_node_plan(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    artifacts = {
        artifact["artifact_id"]: artifact
        for node in run["node_results"]
        if node["output"] is not None
        for artifact in node["output"]["artifacts"]
    }
    normalized: dict[str, dict[str, Any]] = {}
    for node in run["node_results"]:
        output = node["output"]
        normalized[node["node_id"]] = {
            "status": node["status"],
            "attempts": [
                {
                    "attempt_number": attempt["attempt_number"],
                    "attempt_kind": attempt["attempt_kind"],
                    "design_cycle": attempt["design_cycle"],
                    "status": attempt["status"],
                    "recovery_of_attempt_number": _attempt_recovery_numbers(node)[index],
                    "output_mode": _attempt_output_mode(attempt, artifacts),
                    "fixture_result_key": (
                        None
                        if not attempt["output_artifact_ids"]
                        else artifacts[attempt["output_artifact_ids"][0]]["metadata"][
                            "fixture_result_key"
                        ]
                    ),
                    "error_codes": [item["code"] for item in attempt["issues"]],
                    "parameters": deep_copy(attempt["parameters"]),
                }
                for index, attempt in enumerate(node["attempts"])
            ],
            "output_mode": MODE_BY_OUTPUT_COMPLETENESS[node["output_completeness"]],
            "fact_set_key": None if output is None else output["data"]["fact_set_key"],
            "disposition_reason_code": (
                None if node["disposition"] is None else node["disposition"]["reason_code"]
            ),
            "error_codes": [item["code"] for item in node["issues"]],
        }
    return normalized


def normalized_control_view(
    run: dict[str, Any], scenario: dict[str, Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    mapping = {
        "design_suitability": "DESIGN_SUITABILITY",
        "n12_validation": "N12_VALIDATION",
        "n15_delivery_recommendation": "N15_DELIVERY_RECOMMENDATION",
        "n16_applicability": "N16_APPLICABILITY",
        "n17_applicability": "N17_APPLICABILITY",
    }
    for key, control_type in mapping.items():
        decisions = _control_decisions(run, control_type)
        if key == "n12_validation":
            result[key] = {
                "state": "EMIT_SEQUENCE" if decisions else "NOT_REACHED",
                "source": "SCENARIO_LITERAL",
                "decisions": [
                    {
                        "design_cycle": item["source_facts"]["design_cycle"],
                        "source": item["source_facts"]["source"],
                        "decision": item["decision"],
                        "reason_code": item["reason_code"],
                        "fact_set_key": item["source_facts"]["fact_set_key"],
                    }
                    for item in decisions
                ],
                "not_reached_reason_code": (
                    None
                    if decisions
                    else scenario["control_plan"][key]["not_reached_reason_code"]
                ),
            }
        elif decisions:
            item = decisions[0]
            result[key] = {
                "state": "EMIT",
                "source": item["source_facts"]["source"],
                "decision": item["decision"],
                "reason_code": item["reason_code"],
                "fact_set_key": item["source_facts"]["fact_set_key"],
            }
        else:
            result[key] = deep_copy(scenario["control_plan"][key])

    edges = _edge_ids(run)
    expected_entry = scenario["control_plan"]["n18_entry"]
    if "E013" in edges:
        mode = "WT_DIRECT_ENTER"
    elif "E026" in edges:
        mode = "DESIGN_JOIN_ENTER"
    else:
        mode = "NOT_REACHED"
    result["n18_entry"] = {
        "source": "SCENARIO_LITERAL",
        "mode": mode,
        "reason_code": expected_entry["reason_code"],
    }
    return result


def normalized_trace_view(
    run: dict[str, Any], scenario: dict[str, Any]
) -> dict[str, Any]:
    sources = {
        item["source_facts"].get("source") for item in run["control_decisions"]
    }
    sources.add(scenario["control_plan"]["n18_entry"]["source"])
    return {
        "edge_plan": _edge_ids(run),
        "route_decision_sources": sorted(item for item in sources if item is not None),
        "timing_decision_source": "SCENARIO_LITERAL",
    }


def selector_view(
    case: CaseExecution,
    bundle: SpecificationBundle,
) -> dict[str, Any]:
    """Build the nine-root semantic view frozen by the M1-07 selector contract.

    This is deliberately separate from the external envelope: convenient selector
    aliases never add fields to, or mutate, an M1-04 object.
    """

    raw_run = case.final_run
    normalized_nodes = normalize_node_plan(raw_run)
    node_view: dict[str, dict[str, Any]] = {}
    for raw_node in raw_run["node_results"]:
        node_id = raw_node["node_id"]
        item = deep_copy(raw_node)
        item["output_mode"] = normalized_nodes[node_id]["output_mode"]
        item["attempts"] = deep_copy(normalized_nodes[node_id]["attempts"])
        if item["output"] is not None:
            item["output"]["fact_set_key"] = item["output"]["data"]["fact_set_key"]
        node_view[node_id] = item

    artifacts = [
        artifact
        for node in raw_run["node_results"]
        if node["output"] is not None
        for artifact in node["output"]["artifacts"]
    ]
    if raw_run["result"] is not None:
        artifacts.extend(raw_run["result"]["artifacts"])
    attempts = [
        attempt
        for node in raw_run["node_results"]
        for attempt in node["attempts"]
    ]
    errors = [
        issue
        for node in raw_run["node_results"]
        for issue in node["issues"]
    ] + list(raw_run["issues"])

    expected_run = {
        "run_status": raw_run["run_status"],
        "result_kind": raw_run["result"]["result_kind"],
        "handoff_status": raw_run["result"]["handoff"]["status"],
        "run_error_codes": [item["code"] for item in raw_run["issues"]],
        "disclosures": raw_run["result"]["summary"]["disclosures"],
    }
    run_view = deep_copy(raw_run)
    run_view.update(
        {
            "node": node_view,
            "control": normalized_control_view(raw_run, case.scenario),
            "expected_run": expected_run,
            "handoff_status": raw_run["result"]["handoff"]["status"],
            "result_kind": raw_run["result"]["result_kind"],
            "run_error_codes": [item["code"] for item in raw_run["issues"]],
            "errors": errors,
            "artifact_refs": artifacts,
            "error_refs": errors,
            "attempt_refs": attempts,
            "audit_refs": raw_run["audit"]["events"],
            "recovery_refs": [raw_run["recovery_of_run_id"]]
            if raw_run["recovery_of_run_id"] is not None
            else [],
            "control_emission_count": case.control_emission_count,
        }
    )

    catalog_view = deep_copy(case.scenario)
    catalog_view["current_scenario"] = deep_copy(case.scenario)
    catalog_view["scenarios"] = deep_copy(list(bundle.scenarios))
    fixture_view = deep_copy(case.fixture_case)
    fixture_view["attempt_fixture_resolution"] = {
        key: bundle.scenario_catalog["scenario_catalog_version"]
        for key in bundle.declared_attempt_fixture_keys
    }
    registry = deep_copy(bundle.asset_registry)
    registry["identity_namespace"] = {
        "request_id_pattern": REQUEST_ID_PATTERN.pattern,
        "run_id_pattern": RUN_ID_PATTERN.pattern,
        "envelope_id_pattern": ENVELOPE_ID_PATTERN.pattern,
    }
    current_paths_and_identities = {
        "namespace_root": registry["namespace_root"],
        "filesystem_release_root": registry["filesystem_release_root"],
        "directory_layout": registry["directory_layout"],
        "tool_ids": [
            item["tool_id"] for item in registry["tool_namespace"]["tools"]
        ],
        "workflow_ids": [item["workflow_id"] for item in registry["workflows"]],
    }
    return {
        "catalog": catalog_view,
        "fixture": fixture_view,
        "acceptance": deep_copy(case.acceptance_case),
        "request": deep_copy(case.requests[0]),
        "submission": deep_copy(case.submissions),
        "run": run_view,
        "trace": normalized_trace_view(raw_run, case.scenario),
        "workflow": {
            "envelope_examples": deep_copy(list(bundle.envelope_examples)),
            "envelope_schema": deep_copy(bundle.envelope_schema),
            "asset_registry": registry,
            "current_paths_and_identities": current_paths_and_identities,
        },
        "original_run": {
            "hash_before": case.original_hash_before,
            "hash_after": case.original_hash_after,
        },
    }


def _references_close(run: dict[str, Any]) -> bool:
    if [node["node_id"] for node in run["node_results"]] != list(NODE_IDS):
        return False
    if run["current_node_ids"] != [
        node["node_id"] for node in run["node_results"] if node["status"] == "RUNNING"
    ]:
        return False

    attempt_by_id: dict[str, dict[str, Any]] = {}
    artifact_by_id: dict[str, dict[str, Any]] = {}
    error_by_id: dict[str, dict[str, Any]] = {}

    def add_unique_or_equal(target: dict[str, Any], identity: str, value: dict[str, Any]) -> bool:
        if identity in target and target[identity] != value:
            return False
        target[identity] = value
        return True

    for node in run["node_results"]:
        for attempt in node["attempts"]:
            if attempt["attempt_id"] in attempt_by_id:
                return False
            attempt_by_id[attempt["attempt_id"]] = attempt
            for issue in attempt["issues"]:
                if not add_unique_or_equal(error_by_id, issue["error_id"], issue):
                    return False
        for issue in node["issues"]:
            if not add_unique_or_equal(error_by_id, issue["error_id"], issue):
                return False
        if node["output"] is not None:
            output_ids = []
            for artifact in node["output"]["artifacts"]:
                if not add_unique_or_equal(artifact_by_id, artifact["artifact_id"], artifact):
                    return False
                output_ids.append(artifact["artifact_id"])
            if node["output"]["data"]["artifact_ids"] != output_ids:
                return False

    for issue in run["issues"]:
        if not add_unique_or_equal(error_by_id, issue["error_id"], issue):
            return False
    if run["result"] is not None:
        for artifact in run["result"]["artifacts"]:
            if not add_unique_or_equal(artifact_by_id, artifact["artifact_id"], artifact):
                return False

    for attempt in attempt_by_id.values():
        if (
            attempt["recovery_of_attempt_id"] is not None
            and attempt["recovery_of_attempt_id"] not in attempt_by_id
        ):
            return False
        if any(item not in artifact_by_id for item in attempt["output_artifact_ids"]):
            return False
    for artifact in artifact_by_id.values():
        source_attempt_id = artifact["source_attempt_id"]
        if source_attempt_id is not None and source_attempt_id not in attempt_by_id:
            return False
    for issue in error_by_id.values():
        if issue["attempt_id"] is not None and issue["attempt_id"] not in attempt_by_id:
            return False
        if any(item not in artifact_by_id for item in issue["artifact_ids"]):
            return False
        if (
            issue["caused_by_error_id"] is not None
            and issue["caused_by_error_id"] not in error_by_id
        ):
            return False

    decision_ids = [item["decision_id"] for item in run["control_decisions"]]
    if len(decision_ids) != len(set(decision_ids)):
        return False
    decision_set = set(decision_ids)
    traversal_ids = [item["traversal_id"] for item in run["edge_traversals"]]
    if len(traversal_ids) != len(set(traversal_ids)):
        return False
    if [item["sequence"] for item in run["edge_traversals"]] != list(
        range(1, len(run["edge_traversals"]) + 1)
    ):
        return False
    for node in run["node_results"]:
        if any(item not in decision_set for item in node["control_decision_ids"]):
            return False
    for traversal in run["edge_traversals"]:
        if traversal["attempt_id"] is not None and traversal["attempt_id"] not in attempt_by_id:
            return False
        if (
            traversal["control_decision_id"] is not None
            and traversal["control_decision_id"] not in decision_set
        ):
            return False

    event_ids = [item["event_id"] for item in run["audit"]["events"]]
    if len(event_ids) != len(set(event_ids)):
        return False
    if [item["sequence"] for item in run["audit"]["events"]] != list(
        range(1, len(run["audit"]["events"]) + 1)
    ):
        return False
    edge_set = set(_edge_ids(run))
    for event in run["audit"]["events"]:
        if event["attempt_id"] is not None and event["attempt_id"] not in attempt_by_id:
            return False
        if event["edge_id"] is not None and event["edge_id"] not in edge_set:
            return False
        if (
            event["control_decision_id"] is not None
            and event["control_decision_id"] not in decision_set
        ):
            return False
    return True


def _exact_projection(case: CaseExecution) -> bool:
    scenario = case.scenario
    run = case.final_run
    if normalize_node_plan(run) != scenario["node_plan"]:
        return False
    if _edge_ids(run) != scenario["edge_plan"]:
        return False
    if normalized_control_view(run, scenario) != scenario["control_plan"]:
        return False
    expected = scenario["expected_run"]
    actual_expected = {
        "run_status": run["run_status"],
        "result_kind": run["result"]["result_kind"],
        "handoff_status": run["result"]["handoff"]["status"],
        "run_error_codes": [item["code"] for item in run["issues"]],
        "disclosures": run["result"]["summary"]["disclosures"],
    }
    if actual_expected != expected:
        return False
    directives = scenario["submission_plan"]
    if len(case.submissions) != len(directives):
        return False
    for actual, expected_submission in zip(case.submissions, directives, strict=True):
        if actual["action"] != expected_submission["expected_action"]:
            return False
        if actual["error_code"] != expected_submission["expected_error_code"]:
            return False
    return True


class AcceptanceHarness:
    """Execute 21 cases/23 submissions and every M2 blocker assertion definition."""

    def __init__(
        self,
        *,
        bundle: SpecificationBundle | None = None,
        fixtures: FixtureRepository | None = None,
    ) -> None:
        self.bundle = bundle or SpecificationBundle.load()
        self.fixtures = fixtures or FixtureRepository(self.bundle)
        self.operators = AssertionOperatorRegistry()
        declared_operators = tuple(self.bundle.acceptance_catalog["operator_contract"])
        if declared_operators != self.operators.NAMES:
            raise ContractError("assertion operator registry differs from M1-07")

    @staticmethod
    def _expected_value(
        expected_spec: dict[str, Any], adapter: SelectorAdapter
    ) -> Any:
        if set(expected_spec) == {"source_selector"}:
            return adapter.resolve(expected_spec["source_selector"])
        if set(expected_spec) != {"literal"}:
            raise ContractError("assertion expected must contain one frozen source")

        def resolve_relations(value: Any) -> Any:
            if isinstance(value, dict) and set(value) == {"same_as"}:
                reference = value["same_as"]
                if not isinstance(reference, str):
                    raise ContractError("same_as selector must be a string")
                return adapter.resolve(reference)
            if isinstance(value, dict):
                return {key: resolve_relations(item) for key, item in value.items()}
            if isinstance(value, list):
                return [resolve_relations(item) for item in value]
            return deep_copy(value)

        return resolve_relations(expected_spec["literal"])

    def _evaluate_case_assertion(
        self, assertion: dict[str, Any], case: CaseExecution
    ) -> bool:
        adapter = SelectorAdapter(selector_view(case, self.bundle))
        actual = adapter.resolve(assertion["actual_selector"])
        expected = self._expected_value(assertion["expected"], adapter)
        return self.operators.evaluate(assertion["operator"], actual, expected)

    def _execute_case(self, scenario_key: str) -> CaseExecution:
        scenario = self.bundle.scenario_by_key[scenario_key]
        fixture_case = self.bundle.fixture_case_by_scenario[scenario_key]
        acceptance_case = self.bundle.acceptance_case_by_scenario[scenario_key]
        backend = MockBackend(bundle=self.bundle, fixtures=self.fixtures)
        requests: list[dict[str, Any]] = []
        submissions: list[dict[str, Any]] = []
        checkpoints: list[dict[str, Any]] = []
        current_run_id: str | None = None
        original_hash_before: str | None = None
        original_hash_after: str | None = None

        for binding in fixture_case["submission_bindings"]:
            request = self.fixtures.instantiate_submission_request(
                scenario_key, binding["submission_key"]
            )
            requests.append(request)
            if scenario_key == "idempotency_conflict" and current_run_id is not None:
                original_hash_before = backend.run_hash(current_run_id)
            result = backend.submit(request)
            submissions.append(result.to_dict())
            if result.action == "CREATE_RUN":
                current_run_id = result.run_id
                if scenario_key in self.bundle.checkpoint_by_scenario:
                    checkpoints.append(
                        {
                            "sequence": 1,
                            "action": "SUBMIT_CREATE",
                            "checkpoint_fact": "CREATE_RUN_ACCEPTED",
                            "run_id": current_run_id,
                            "run": deep_copy(result.run),
                        }
                    )
            elif result.action == "RETURN_EXISTING_RUN":
                current_run_id = result.run_id
            if scenario_key == "idempotency_conflict" and original_hash_before is not None:
                original_hash_after = backend.run_hash(current_run_id)

        if current_run_id is None:
            raise ContractError(f"case {scenario_key} did not produce a run")

        plan = self.bundle.checkpoint_by_scenario.get(scenario_key)
        if plan is not None:
            for step in plan["steps"][1:]:
                action = step["action"]
                if action in {"POLL_SCENARIO_CHECKPOINT", "POLL_TERMINAL"}:
                    envelope = backend.poll_run(current_run_id)
                elif action == "INJECT_SCENARIO_EVENT":
                    envelope = backend.inject_scenario_event(
                        current_run_id, step["checkpoint_fact"]
                    )
                elif action == "CANCEL_RUN":
                    envelope = backend.cancel_run(current_run_id)
                elif action == "REQUEST_RECOVERY":
                    current_run_id, envelope = backend.recover_run(current_run_id)
                else:
                    raise ContractError(f"unknown checkpoint action: {action}")
                checkpoints.append(
                    {
                        "sequence": step["sequence"],
                        "action": action,
                        "checkpoint_fact": step["checkpoint_fact"],
                        "run_id": current_run_id,
                        "run": deep_copy(envelope),
                    }
                )
                if envelope["run_status"] != step["expected_run_status"]:
                    raise ContractError(f"checkpoint status mismatch in {scenario_key}")

        final_run = backend.get_run(current_run_id)
        metadata = backend.get_run_metadata(current_run_id)
        return CaseExecution(
            scenario=scenario,
            fixture_case=fixture_case,
            acceptance_case=acceptance_case,
            requests=requests,
            submissions=submissions,
            checkpoints=checkpoints,
            final_run=final_run,
            final_run_id=current_run_id,
            original_hash_before=original_hash_before,
            original_hash_after=original_hash_after,
            control_emission_count=metadata["control_emission_count"],
        )

    def execute_cases(self) -> list[CaseExecution]:
        return [self._execute_case(item["scenario_key"]) for item in self.bundle.scenarios]

    def _global_checks(
        self, cases: list[CaseExecution]
    ) -> dict[str, Callable[[], bool]]:
        all_requests = [request for case in cases for request in case.requests]
        materialized_requests = [
            self.fixtures.load_request_variant(key)
            for key in self.bundle.request_variant_by_key
        ]
        all_runs = [case.final_run for case in cases]
        all_runs.extend(
            checkpoint["run"] for case in cases for checkpoint in case.checkpoints
        )

        def schema_valid() -> bool:
            for index, request in enumerate(materialized_requests + all_requests):
                self.bundle.validate_envelope(request, f"M2 request {index}")
            for index, run in enumerate(all_runs):
                self.bundle.validate_envelope(run, f"M2 run {index}")
            return True

        def fixtures_resolve() -> bool:
            counts = self.fixtures.verify()
            return counts == {
                "input_fixture_count": 2,
                "request_variant_count": 22,
                "attempt_fixture_count": 326,
                "payload_file_count": 350,
            }

        def exact_projection() -> bool:
            return all(_exact_projection(case) for case in cases)

        def mock_flags() -> bool:
            return all(
                request["data_classification"] == "MOCK_DATA"
                and request["scientific_compute"] is False
                for request in all_requests
            ) and all(
                run["data_classification"] == "MOCK_DATA"
                and run["scientific_compute"] is False
                and run["result"]["handoff"]["status"] == "NOT_DEPLOYED"
                and run["result"]["handoff"]["delivered"] is False
                for run in (case.final_run for case in cases)
            )

        def literal_sources() -> bool:
            for case in cases:
                sources = normalized_trace_view(case.final_run, case.scenario)[
                    "route_decision_sources"
                ]
                if sources != ["SCENARIO_LITERAL"]:
                    return False
            return True

        def no_scientific_values() -> bool:
            payloads: list[Any] = []
            payloads.extend(self.fixtures.load_input(key) for key in self.bundle.input_fixture_by_key)
            payloads.extend(materialized_requests)
            payloads.extend(all_requests)
            payloads.extend(all_runs)
            for key in self.bundle.declared_attempt_fixture_keys:
                payloads.append(self.fixtures.load_attempt_stub(key))
            return all(_contains_none(item, PROHIBITED_RUNTIME_VALUE_TOKENS) for item in payloads)

        def references_resolve() -> bool:
            return all(_references_close(run) for run in all_runs)

        def ids_match() -> bool:
            if any(REQUEST_ID_PATTERN.fullmatch(item["request_id"]) is None for item in all_requests):
                return False
            for run in all_runs:
                if RUN_ID_PATTERN.fullmatch(run["run_id"]) is None:
                    return False
                if ENVELOPE_ID_PATTERN.fullmatch(run["envelope_id"]) is None:
                    return False
                recovery = run["recovery_of_run_id"]
                if recovery is not None and RUN_ID_PATTERN.fullmatch(recovery) is None:
                    return False
            return True

        def legacy_isolated() -> bool:
            registry = self.bundle.asset_registry
            current_values = {
                registry["namespace_root"],
                registry["filesystem_release_root"],
                registry["directory_layout"]["source_package_root"],
                registry["directory_layout"]["test_root"],
                registry["directory_layout"]["fixture_root"],
                registry["directory_layout"]["runtime_root"],
                registry["tool_namespace"]["mcp_server_name"],
                registry["tool_namespace"]["dify_provider_name"],
                *(item["tool_id"] for item in registry["tool_namespace"]["tools"]),
                *(item["workflow_id"] for item in registry["workflows"]),
                *(request["request_id"] for request in all_requests),
                *(case.final_run_id for case in cases),
            }
            return _contains_none(sorted(current_values), LEGACY_IDENTITY_MARKERS)

        return {
            "t01_phase1_mock_v01.acceptance.global.004": schema_valid,
            "t01_phase1_mock_v01.acceptance.global.008": fixtures_resolve,
            "t01_phase1_mock_v01.acceptance.global.009": exact_projection,
            "t01_phase1_mock_v01.acceptance.global.010": mock_flags,
            "t01_phase1_mock_v01.acceptance.global.011": literal_sources,
            "t01_phase1_mock_v01.acceptance.global.012": no_scientific_values,
            "t01_phase1_mock_v01.acceptance.global.013": references_resolve,
            "t01_phase1_mock_v01.acceptance.global.014": ids_match,
            "t01_phase1_mock_v01.acceptance.global.017": legacy_isolated,
        }

    def run(self, cases: list[CaseExecution] | None = None) -> dict[str, Any]:
        cases = self.execute_cases() if cases is None else cases
        global_specs = [
            item
            for item in self.bundle.acceptance_catalog["global_assertions"]
            if "M2_BACKEND" in item["applies_to"]
        ]
        global_checks = self._global_checks(cases)
        global_results: list[dict[str, Any]] = []
        for assertion in global_specs:
            assertion_id = assertion["assertion_id"]
            check = global_checks.get(assertion_id)
            if check is None:
                raise ContractError(f"unknown M2 global assertion: {assertion_id}")
            try:
                native_results = [
                    self._evaluate_case_assertion(assertion, case)
                    for case in cases
                ]
                aggregate_result = bool(check())
                passed = all(native_results) and aggregate_result
                detail = (
                    None
                    if passed
                    else "catalog operator or aggregate invariant returned false"
                )
            except Exception as exc:  # report a blocker rather than silently skipping it
                passed = False
                detail = f"{type(exc).__name__}: {exc}"
            global_results.append(
                {
                    "assertion_id": assertion_id,
                    "operator": assertion["operator"],
                    "severity": assertion["severity"],
                    "status": "PASS" if passed else "FAIL",
                    "detail": detail,
                }
            )

        focus_results: list[dict[str, Any]] = []
        for case in cases:
            specs = [
                item
                for item in case.acceptance_case["focus_assertions"]
                if "M2_BACKEND" in item["applies_to"]
            ]
            for assertion in specs:
                detail: str | None = None
                try:
                    passed = self._evaluate_case_assertion(assertion, case)
                    if not passed:
                        detail = "predicate returned false"
                except Exception as exc:
                    passed = False
                    detail = f"{type(exc).__name__}: {exc}"
                focus_results.append(
                    {
                        "assertion_id": assertion["assertion_id"],
                        "scenario_key": case.scenario["scenario_key"],
                        "operator": assertion["operator"],
                        "severity": assertion["severity"],
                        "status": "PASS" if passed else "FAIL",
                        "detail": detail,
                    }
                )

        all_results = global_results + focus_results
        blocker_failures = [item for item in all_results if item["status"] != "PASS"]
        submissions = [item for case in cases for item in case.submissions]
        requests = [item for case in cases for item in case.requests]
        checkpoint_count = sum(len(case.checkpoints) for case in cases)
        request_ids = [item["request_id"] for item in requests]
        case_results = [
            {
                "ordinal": case.fixture_case["ordinal"],
                "scenario_key": case.scenario["scenario_key"],
                "submission_count": len(case.submissions),
                "submission_actions": [item["action"] for item in case.submissions],
                "checkpoint_count": len(case.checkpoints),
                "final_run_id": case.final_run_id,
                "recovery_of_run_id": case.final_run["recovery_of_run_id"],
                "run_status": case.final_run["run_status"],
                "result_kind": case.final_run["result"]["result_kind"],
                "focus_assertion_count": len(
                    case.acceptance_case["focus_assertions"]
                ),
                "status": (
                    "PASS"
                    if all(
                        item["status"] == "PASS"
                        for item in focus_results
                        if item["scenario_key"] == case.scenario["scenario_key"]
                    )
                    else "FAIL"
                ),
            }
            for case in cases
        ]
        case_status = {item["scenario_key"]: item["status"] for item in case_results}
        coverage_results: list[dict[str, Any]] = []
        executed_keys = set(case_status)
        for gate in self.bundle.acceptance_catalog["coverage_gates"]:
            required = gate["required_scenario_keys"]
            passed = (
                len(required) >= gate["minimum_case_count"]
                and set(required) <= executed_keys
                and all(case_status[key] == "PASS" for key in required)
            )
            coverage_results.append(
                {
                    "gate_id": gate["gate_id"],
                    "category": gate["category"],
                    "required_scenario_keys": deep_copy(required),
                    "minimum_case_count": gate["minimum_case_count"],
                    "executed_case_count": sum(
                        key in executed_keys for key in required
                    ),
                    "status": "PASS" if passed else "FAIL",
                    "detail": None if passed else "required case is missing or failed",
                }
            )
        coverage_failures = [
            item for item in coverage_results if item["status"] != "PASS"
        ]
        inventory = self.bundle.fixture_manifest["inventory"]
        report = {
            "$schema": M2_ACCEPTANCE_RESULT_SCHEMA_PATH.name,
            "document_type": "T01_PHASE1_MOCK_M2_ACCEPTANCE_RESULT",
            "result_version": M2_RESULT_VERSION,
            "source_acceptance_catalog_version": self.bundle.acceptance_catalog[
                "acceptance_catalog_version"
            ],
            "source_fixture_manifest_version": self.bundle.fixture_manifest[
                "fixture_manifest_version"
            ],
            "source_scenario_catalog_version": self.bundle.scenario_catalog[
                "scenario_catalog_version"
            ],
            "source_sha256": deep_copy(self.bundle.source_sha256),
            "stage": "M2_BACKEND",
            "implementation_state": "M2_BACKEND_EXECUTED",
            "status": (
                "PASS" if not blocker_failures and not coverage_failures else "FAIL"
            ),
            "execution_environment": {
                "python_constraint": ">=3.11,<3.12",
                "transport": "IN_PROCESS_LOCAL",
                "network_mode": "OFFLINE",
                "clock_driven_branching": False,
            },
            "case_count": len(cases),
            "submission_count": len(submissions),
            "unique_submission_request_id_count": len(set(request_ids)),
            "request_variant_count": len(self.bundle.request_variant_by_key),
            "attempt_fixture_count": len(self.bundle.declared_attempt_fixture_keys),
            "null_attempt_fixture_count": self.bundle.null_attempt_fixture_count,
            "fixture_payload_file_count": self.fixtures.materialization["counts"][
                "payload_file_count"
            ],
            "node_terminal_directive_count": inventory[
                "node_terminal_directive_count"
            ],
            "attempt_count": inventory["attempt_count"],
            "checkpoint_plan_count": len(self.bundle.checkpoint_by_scenario),
            "checkpoint_count": checkpoint_count,
            "tool_count": len(
                self.bundle.asset_registry["tool_namespace"]["tools"]
            ),
            "operator_count": len(self.operators.NAMES),
            "global_assertion_count": len(global_results),
            "focus_assertion_count": len(focus_results),
            "blocker_assertion_count": len(all_results),
            "blocker_failure_count": len(blocker_failures),
            "coverage_gate_count": len(coverage_results),
            "coverage_gate_failure_count": len(coverage_failures),
            "scientific_execution_count": 0,
            "network_request_count": 0,
            "legacy_implementation_reuse_count": 0,
            "dify_dsl_count": 0,
            "case_results": case_results,
            "coverage_gates": coverage_results,
            "global_assertions": global_results,
            "focus_assertions": focus_results,
        }
        result_schema = load_json(M2_ACCEPTANCE_RESULT_SCHEMA_PATH)
        validate_instance(report, result_schema, "M2 acceptance result")
        return report

    def run_and_write(self) -> dict[str, Any]:
        report = self.run()
        M2_ACCEPTANCE_RESULT_PATH.write_bytes(pretty_json_bytes(report))
        return report
