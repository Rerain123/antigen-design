"""Strict loading and cross-validation of the frozen M1 machine specifications."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .constants import (
    ACCEPTANCE_CATALOG_VERSION,
    ASSERTION_OPERATOR_NAMES,
    ASSET_REGISTRY_VERSION,
    EDGE_IDS,
    ENVELOPE_CONTRACT_VERSION,
    FIXTURE_MANIFEST_VERSION,
    NAMESPACE_ROOT,
    NODE_IDS,
    SCENARIO_CATALOG_VERSION,
)
from .jsonio import ContractError, load_json, sha256_bytes
from .paths import (
    ACCEPTANCE_CATALOG_PATH,
    ACCEPTANCE_SCHEMA_PATH,
    ASSET_REGISTRY_PATH,
    ASSET_REGISTRY_SCHEMA_PATH,
    ENVELOPE_SCHEMA_PATH,
    ENVELOPE_EXAMPLE_PATHS,
    FIXTURE_MANIFEST_PATH,
    FIXTURE_MANIFEST_SCHEMA_PATH,
    SCENARIO_CATALOG_PATH,
    SCENARIO_SCHEMA_PATH,
    M1_SPEC_SOURCE_PATHS,
    PROJECT_ROOT,
    resolve_project_relative,
)


_VALIDATOR_CACHE: dict[int, tuple[dict[str, Any], Draft202012Validator]] = {}
_MOCK_STUB_SCHEMA_CACHE: dict[int, dict[str, Any]] = {}


def validate_instance(instance: Any, schema: dict[str, Any], label: str) -> None:
    cached = _VALIDATOR_CACHE.get(id(schema))
    if cached is None or cached[0] is not schema:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        _VALIDATOR_CACHE[id(schema)] = (schema, validator)
    else:
        validator = cached[1]
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        location = "/" + "/".join(str(part) for part in first.absolute_path)
        raise ContractError(f"{label} fails JSON Schema at {location}: {first.message}")


@dataclass(frozen=True)
class SpecificationBundle:
    envelope_schema: dict[str, Any]
    scenario_schema: dict[str, Any]
    scenario_catalog: dict[str, Any]
    asset_registry_schema: dict[str, Any]
    asset_registry: dict[str, Any]
    fixture_manifest_schema: dict[str, Any]
    fixture_manifest: dict[str, Any]
    acceptance_schema: dict[str, Any]
    acceptance_catalog: dict[str, Any]
    envelope_examples: tuple[dict[str, Any], ...]
    source_sha256: dict[str, str]

    @classmethod
    def load(cls) -> "SpecificationBundle":
        bundle = cls(
            envelope_schema=load_json(ENVELOPE_SCHEMA_PATH),
            scenario_schema=load_json(SCENARIO_SCHEMA_PATH),
            scenario_catalog=load_json(SCENARIO_CATALOG_PATH),
            asset_registry_schema=load_json(ASSET_REGISTRY_SCHEMA_PATH),
            asset_registry=load_json(ASSET_REGISTRY_PATH),
            fixture_manifest_schema=load_json(FIXTURE_MANIFEST_SCHEMA_PATH),
            fixture_manifest=load_json(FIXTURE_MANIFEST_PATH),
            acceptance_schema=load_json(ACCEPTANCE_SCHEMA_PATH),
            acceptance_catalog=load_json(ACCEPTANCE_CATALOG_PATH),
            envelope_examples=tuple(load_json(path) for path in ENVELOPE_EXAMPLE_PATHS),
            source_sha256={
                path.relative_to(PROJECT_ROOT).as_posix(): sha256_bytes(path.read_bytes())
                for path in M1_SPEC_SOURCE_PATHS
            },
        )
        bundle.validate()
        return bundle

    @property
    def scenarios(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.scenario_catalog["scenarios"])

    @property
    def scenario_by_key(self) -> dict[str, dict[str, Any]]:
        return {item["scenario_key"]: item for item in self.scenarios}

    @property
    def scenario_by_ref(self) -> dict[str, dict[str, Any]]:
        return {
            f"{NAMESPACE_ROOT}.scenario.{item['scenario_key']}": item
            for item in self.scenarios
        }

    @property
    def responsibility_by_node(self) -> dict[str, dict[str, Any]]:
        return {
            item["node_id"]: item
            for item in self.scenario_catalog["node_output_responsibilities"]
        }

    @property
    def fixture_case_by_scenario(self) -> dict[str, dict[str, Any]]:
        return {
            item["scenario_key"]: item
            for item in self.fixture_manifest["fixture_cases"]
        }

    @property
    def request_variant_by_key(self) -> dict[str, dict[str, Any]]:
        return {
            item["request_variant_key"]: item
            for item in self.fixture_manifest["request_variants"]
        }

    @property
    def input_fixture_by_key(self) -> dict[str, dict[str, Any]]:
        return {
            item["fixture_key"]: item
            for item in self.fixture_manifest["input_fixtures"]
        }

    @property
    def checkpoint_by_scenario(self) -> dict[str, dict[str, Any]]:
        return {
            item["scenario_key"]: item
            for item in self.fixture_manifest["checkpoint_plans"]
        }

    @property
    def acceptance_case_by_scenario(self) -> dict[str, dict[str, Any]]:
        return {
            item["scenario_key"]: item
            for item in self.acceptance_catalog["acceptance_cases"]
        }

    @property
    def declared_attempt_fixture_keys(self) -> tuple[str, ...]:
        return tuple(
            attempt["fixture_result_key"]
            for scenario in self.scenarios
            for node in scenario["node_plan"].values()
            for attempt in node["attempts"]
            if attempt["fixture_result_key"] is not None
        )

    @property
    def null_attempt_fixture_count(self) -> int:
        return sum(
            attempt["fixture_result_key"] is None
            for scenario in self.scenarios
            for node in scenario["node_plan"].values()
            for attempt in node["attempts"]
        )

    def scenario_for_ref(self, scenario_ref: str) -> dict[str, Any]:
        try:
            return self.scenario_by_ref[scenario_ref]
        except KeyError as exc:
            raise ContractError(f"unknown scenario_ref: {scenario_ref}") from exc

    def validate_envelope(self, envelope: dict[str, Any], label: str = "envelope") -> None:
        validate_instance(envelope, self.envelope_schema, label)

    def validate_mock_stub(self, stub: dict[str, Any], label: str = "mock stub") -> None:
        schema = _MOCK_STUB_SCHEMA_CACHE.get(id(self.scenario_schema))
        if schema is None:
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$ref": "#/$defs/mock_node_output_stub",
                "$defs": self.scenario_schema["$defs"],
            }
            _MOCK_STUB_SCHEMA_CACHE[id(self.scenario_schema)] = schema
        validate_instance(stub, schema, label)

    def validate(self) -> None:
        validate_instance(
            self.scenario_catalog, self.scenario_schema, "scenario catalog"
        )
        validate_instance(
            self.asset_registry, self.asset_registry_schema, "asset registry"
        )
        validate_instance(
            self.fixture_manifest,
            self.fixture_manifest_schema,
            "fixture manifest",
        )
        validate_instance(
            self.acceptance_catalog,
            self.acceptance_schema,
            "acceptance catalog",
        )
        if len(self.envelope_examples) != 4:
            raise ContractError("exactly four M1-04 envelope examples are required")
        for index, example in enumerate(self.envelope_examples, start=1):
            self.validate_envelope(example, f"M1-04 envelope example {index}")
        if len(self.source_sha256) != len(M1_SPEC_SOURCE_PATHS):
            raise ContractError("M1 source hash lock contains duplicate paths")
        if any(len(value) != 64 for value in self.source_sha256.values()):
            raise ContractError("M1 source hash lock contains an invalid SHA-256")

        expected_versions = {
            self.scenario_catalog["scenario_catalog_version"]: SCENARIO_CATALOG_VERSION,
            self.asset_registry["registry_version"]: ASSET_REGISTRY_VERSION,
            self.fixture_manifest["fixture_manifest_version"]: FIXTURE_MANIFEST_VERSION,
            self.acceptance_catalog["acceptance_catalog_version"]: ACCEPTANCE_CATALOG_VERSION,
            self.scenario_catalog["envelope_contract_version"]: ENVELOPE_CONTRACT_VERSION,
        }
        for actual, expected in expected_versions.items():
            if actual != expected:
                raise ContractError(f"version mismatch: expected {expected}, got {actual}")

        scenarios = self.scenarios
        scenario_keys = [item["scenario_key"] for item in scenarios]
        if len(scenarios) != 21 or len(set(scenario_keys)) != 21:
            raise ContractError("scenario catalog must contain 21 unique scenarios")
        if tuple(self.responsibility_by_node) != NODE_IDS:
            raise ContractError("node responsibility order must be exactly N01-N18")

        manifest_cases = self.fixture_manifest["fixture_cases"]
        acceptance_cases = self.acceptance_catalog["acceptance_cases"]
        if [item["scenario_key"] for item in manifest_cases] != scenario_keys:
            raise ContractError("fixture cases must be an ordered bijection with scenarios")
        if [item["scenario_key"] for item in acceptance_cases] != scenario_keys:
            raise ContractError("acceptance cases must be an ordered bijection with scenarios")

        for index, scenario in enumerate(scenarios):
            if tuple(scenario["node_plan"]) != NODE_IDS:
                raise ContractError(
                    f"{scenario['scenario_key']} node plan is not ordered N01-N18"
                )
            if any(edge not in EDGE_IDS for edge in scenario["edge_plan"]):
                raise ContractError(f"{scenario['scenario_key']} contains unknown edge")
            if scenario["scientific_assertions"]:
                raise ContractError(
                    f"{scenario['scenario_key']} contains scientific assertions"
                )
            manifest_case = manifest_cases[index]
            acceptance_case = acceptance_cases[index]
            if manifest_case["catalog_scenario_pointer"] != f"/scenarios/{index}":
                raise ContractError("fixture case scenario pointer mismatch")
            if acceptance_case["catalog_scenario_pointer"] != f"/scenarios/{index}":
                raise ContractError("acceptance case scenario pointer mismatch")
            if [item["source_text"] for item in acceptance_case["focus_assertions"]] != scenario[
                "scenario_specific_assertions"
            ]:
                raise ContractError("focus assertion source text mismatch")

        attempt_keys = self.declared_attempt_fixture_keys
        if len(attempt_keys) != 326 or len(set(attempt_keys)) != 326:
            raise ContractError("attempt fixture key closed set must contain 326 unique keys")
        if self.null_attempt_fixture_count != 8:
            raise ContractError("exactly eight attempts must have null fixture keys")

        inventory = self.fixture_manifest["inventory"]
        recomputed = {
            "fixture_case_count": len(scenarios),
            "input_fixture_count": len(self.fixture_manifest["input_fixtures"]),
            "request_variant_count": len(self.fixture_manifest["request_variants"]),
            "submission_count": sum(len(item["submission_plan"]) for item in scenarios),
            "node_terminal_directive_count": len(scenarios) * len(NODE_IDS),
            "attempt_count": sum(
                len(node["attempts"])
                for scenario in scenarios
                for node in scenario["node_plan"].values()
            ),
            "attempt_fixture_key_count": len(attempt_keys),
            "null_attempt_fixture_key_count": self.null_attempt_fixture_count,
            "checkpoint_plan_count": len(self.fixture_manifest["checkpoint_plans"]),
            "checkpoint_count": sum(
                len(item["steps"])
                for item in self.fixture_manifest["checkpoint_plans"]
            ),
        }
        if inventory != recomputed:
            raise ContractError(f"fixture inventory mismatch: {inventory} != {recomputed}")

        for item in self.fixture_manifest["input_fixtures"]:
            resolve_project_relative(item["planned_payload_path"])
        for item in self.fixture_manifest["request_variants"]:
            resolve_project_relative(item["planned_payload_path"])

        tools = self.asset_registry["tool_namespace"]["tools"]
        if len(tools) != 26 or len({item["tool_id"] for item in tools}) != 26:
            raise ContractError("asset registry must contain 26 unique tools")
        node_tools = [item["node_id"] for item in tools if item["tool_role"] == "NODE_STUB"]
        if tuple(node_tools) != NODE_IDS:
            raise ContractError("node tools must map exactly to N01-N18")
        if any(
            not item["tool_id"].endswith(item["node_id"].lower())
            for item in tools
            if item["tool_role"] == "NODE_STUB"
        ):
            raise ContractError("node tool identity and node suffix disagree")
        control_keys = [
            item["control_key"]
            for item in tools
            if item["tool_role"] == "CONTROL_LITERAL"
        ]
        if control_keys != list(self.scenarios[0]["control_plan"]):
            raise ContractError("control tools must map exactly to the six control literals")
        if len(self.asset_registry["workflows"]) != 2:
            raise ContractError("asset registry must contain exactly two workflow identities")
        scenario_refs = self.asset_registry["scenario_namespace"]["mappings"]
        if len(scenario_refs) != 21 or {
            item["scenario_ref"] for item in scenario_refs
        } != set(self.scenario_by_ref):
            raise ContractError("asset registry must map exactly 21 scenario refs")

        if tuple(self.acceptance_catalog["operator_contract"]) != ASSERTION_OPERATOR_NAMES:
            raise ContractError("acceptance operator contract must contain the exact 28 operators")
        if len(self.acceptance_catalog["global_assertions"]) != 18:
            raise ContractError("acceptance catalog must contain exactly 18 global assertions")
        if len(self.acceptance_catalog["coverage_gates"]) != 10:
            raise ContractError("acceptance catalog must contain exactly 10 coverage gates")

        m2_globals = [
            item
            for item in self.acceptance_catalog["global_assertions"]
            if "M2_BACKEND" in item["applies_to"]
        ]
        focus = [
            item
            for case in acceptance_cases
            for item in case["focus_assertions"]
            if "M2_BACKEND" in item["applies_to"]
        ]
        if len(m2_globals) != 9 or len(focus) != 44:
            raise ContractError("M2 must have exactly 9 global and 44 focus assertions")


def default_bundle() -> SpecificationBundle:
    return SpecificationBundle.load()
