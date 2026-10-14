"""Materialize and resolve the closed synthetic fixture set declared by M1-07."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .catalog import SpecificationBundle, validate_instance
from .constants import (
    ENVELOPE_CONTRACT_VERSION,
    FIXTURE_MANIFEST_VERSION,
    MATERIALIZATION_VERSION,
    NODE_REGISTRY_VERSION,
    SCENARIO_CATALOG_VERSION,
    TOPOLOGY_VERSION,
    CONTROL_FLOW_VERSION,
)
from .jsonio import (
    ContractError,
    canonical_sha256,
    load_json,
    pretty_json_bytes,
    sha256_bytes,
    stable_uuid4,
)
from .paths import (
    FIXTURE_ROOT,
    MATERIALIZATION_PATH,
    MATERIALIZATION_SCHEMA_PATH,
    PROJECT_ROOT,
    resolve_project_relative,
)


_ATTEMPT_KEY_RE = re.compile(
    r"^(?P<scenario>[a-z][a-z0-9_]*)[.]n(?P<node>0[1-9]|1[0-8])"
    r"[.]attempt_(?P<attempt>[1-9][0-9]*)$"
)

_FIXED_CREATED_AT = "2026-09-04T00:00:00Z"
_SYNTHETIC_SEQUENCE = "MOCKONLYTRANSPORTFIXTURE"
_SYNTHETIC_HOST_SPECIES = "Synthetic non-production host fixture"
_SUPPORTED_EXPRESSION_HOST = "synthetic-supported-expression-host-fixture"
_UNSUPPORTED_EXPRESSION_HOST = "synthetic-unsupported-expression-host-sentinel"
_STRUCTURE_BYTES = (
    b"REMARK 999 SYNTHETIC TRANSPORT FIXTURE; NO SCIENTIFIC COORDINATES\nEND\n"
)


def _actor(actor_type: str, actor_id: str, version: str | None) -> dict[str, Any]:
    return {
        "actor_type": actor_type,
        "actor_id": actor_id,
        "component_version": version,
    }


def _request_timestamp(ordinal: int, submission: int = 0) -> str:
    minute = ordinal * 2 + submission
    hour, minute = divmod(minute, 60)
    return f"2026-09-04T{hour:02d}:{minute:02d}:00Z"


def _request_identity(seed: str) -> str:
    return f"t01-phase1-mock-v01-req-{stable_uuid4('request:' + seed)}"


def _envelope_identity(seed: str) -> str:
    return f"t01-phase1-mock-v01-env-{stable_uuid4('envelope:' + seed)}"


def _structure_artifact() -> dict[str, Any]:
    return {
        "artifact_id": "t01_phase1_mock_v01.fixture.input.synthetic_local_structure",
        "artifact_role": "INPUT_STRUCTURE",
        "uri": "artifact://t01-phase1-mock-v0.1/fixtures/inputs/synthetic-local-structure",
        "media_type": "chemical/x-pdb",
        "format": "PDB",
        "size_bytes": len(_STRUCTURE_BYTES),
        "sha256": sha256_bytes(_STRUCTURE_BYTES),
        "integrity_status": "VERIFIED",
        "created_at": _FIXED_CREATED_AT,
        "producer": _actor(
            "MOCK_SCENARIO",
            "t01_phase1_mock_v01.fixture_materializer",
            MATERIALIZATION_VERSION,
        ),
        "source_node_id": None,
        "source_attempt_id": None,
        "metadata": {
            "mock_only": True,
            "synthetic_transport_fixture": True,
            "scientific_coordinates_present": False,
        },
    }


class FixtureMaterializer:
    """Write the exact synthetic payload set declared by the frozen manifest."""

    def __init__(self, bundle: SpecificationBundle | None = None) -> None:
        self.bundle = bundle or SpecificationBundle.load()

    @staticmethod
    def _write(relative_path: str, payload: bytes) -> dict[str, Any]:
        path = resolve_project_relative(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.is_symlink():
            raise ContractError(f"refusing to replace symlink: {relative_path}")
        path.write_bytes(payload)
        persisted = path.read_bytes()
        if persisted != payload:
            raise ContractError(f"fixture write verification failed: {relative_path}")
        return {
            "path": relative_path,
            "size_bytes": len(payload),
            "sha256": sha256_bytes(payload),
            "data_classification": "MOCK_DATA",
            "scientific_compute": False,
        }

    def _input_payload(self, fixture: dict[str, Any]) -> dict[str, Any]:
        structure = None
        if fixture["fixture_key"] == "input.synthetic.standard":
            structure = {
                "artifact": _structure_artifact(),
                "structure_format": "PDB",
                "chain_selector": "AUTO",
                "preserve_original_format": True,
            }
        return {
            "document_type": "T01_PHASE1_MOCK_INPUT_FIXTURE",
            "materialization_version": MATERIALIZATION_VERSION,
            "fixture_key": fixture["fixture_key"],
            "fixture_id": fixture["fixture_id"],
            "data_classification": "MOCK_DATA",
            "scientific_compute": False,
            "synthetic_input_only": True,
            "protein_sequence": _SYNTHETIC_SEQUENCE,
            "host_species": _SYNTHETIC_HOST_SPECIES,
            "structure": structure,
            "synthetic_structure_payload": (
                None if structure is None else _STRUCTURE_BYTES.decode("ascii")
            ),
            "disclosures": [
                "MOCK_DATA_ONLY",
                "NOT_SCIENTIFIC_EVIDENCE",
                "SYNTHETIC_TRANSPORT_INPUT",
            ],
        }

    def _request_payload(
        self, variant: dict[str, Any], ordinal: int
    ) -> dict[str, Any]:
        scenario = self.bundle.scenario_by_key[variant["scenario_key"]]
        fixture_case = self.bundle.fixture_case_by_scenario[variant["scenario_key"]]
        input_spec = self.bundle.input_fixture_by_key[variant["input_fixture_key"]]
        input_payload = self._input_payload(input_spec)
        profile = scenario["input_profile"]
        expression_case = profile["expression_host_case"]
        if expression_case == "OMITTED":
            expression_host = None
        elif expression_case == "PROVIDED_SUPPORTED_FIXTURE":
            expression_host = _SUPPORTED_EXPRESSION_HOST
        elif expression_case == "PROVIDED_UNSUPPORTED_SENTINEL":
            expression_host = _UNSUPPORTED_EXPRESSION_HOST
        else:
            raise ContractError(f"unknown expression_host_case: {expression_case}")

        timestamp = _request_timestamp(ordinal)
        seed = variant["request_variant_key"]
        structure = deepcopy(input_payload["structure"])
        structure_hash = None if structure is None else structure["artifact"]["sha256"]
        request: dict[str, Any] = {
            "envelope_type": "PHASE1_RUN_REQUEST",
            "contract_version": ENVELOPE_CONTRACT_VERSION,
            "topology_version": TOPOLOGY_VERSION,
            "node_registry_version": NODE_REGISTRY_VERSION,
            "control_flow_version": CONTROL_FLOW_VERSION,
            "envelope_id": _envelope_identity(seed),
            "created_at": timestamp,
            "execution_mode": "MOCK",
            "execution_profile": "PHASE1_FULL",
            "data_classification": "MOCK_DATA",
            "scientific_compute": False,
            "request_id": _request_identity(seed),
            "idempotency_key": fixture_case["idempotency_key_literal"],
            "scenario_ref": variant["scenario_ref"],
            "inputs": {
                "protein_sequence": input_payload["protein_sequence"],
                "host_species": input_payload["host_species"],
                "structure": structure,
            },
            "options": {
                "design_objective": profile["design_objective"],
                "expression_host": expression_host,
            },
            "input_fingerprints": {
                "protein_sequence_sha256": sha256_bytes(
                    input_payload["protein_sequence"].encode("ascii")
                ),
                "structure_sha256": structure_hash,
            },
            "audit": {
                "trace_id": f"t01_phase1_mock_v01.trace.request.{stable_uuid4(seed)}",
                "correlation_id": f"t01_phase1_mock_v01.correlation.{stable_uuid4(seed)}",
                "events": [
                    {
                        "event_id": f"t01_phase1_mock_v01.event.request.{stable_uuid4(seed)}",
                        "sequence": 1,
                        "event_type": "REQUEST_ACCEPTED",
                        "occurred_at": timestamp,
                        "actor": _actor(
                            "BACKEND",
                            "t01_phase1_mock_v01.request_validator",
                            "0.1.0",
                        ),
                        "node_id": None,
                        "attempt_id": None,
                        "edge_id": None,
                        "control_decision_id": None,
                        "details": {
                            "mock_only": True,
                            "remote_lookup_performed": False,
                            "source": "M1_07_FIXTURE_MANIFEST",
                        },
                    }
                ],
                "audit_artifacts": [],
            },
        }

        for mutation in variant["canonical_request_mutations"]:
            if (
                mutation["operation"] != "REPLACE"
                or mutation["json_pointer"] != "/options/design_objective"
            ):
                raise ContractError(f"unsupported frozen request mutation: {mutation}")
            request["options"]["design_objective"] = mutation["value"]
        self.bundle.validate_envelope(request, f"request variant {seed}")
        return request

    def _attempt_stub(
        self,
        scenario: dict[str, Any],
        node_id: str,
        node: dict[str, Any],
        attempt: dict[str, Any],
    ) -> dict[str, Any]:
        responsibility = self.bundle.responsibility_by_node[node_id]
        fixture_key = attempt["fixture_result_key"]
        if fixture_key is None:
            raise ContractError("null attempt fixture cannot be materialized")
        artifact_id = (
            f"t01_phase1_mock_v01.fixture_artifact.{scenario['scenario_key']}."
            f"{node_id.lower()}.attempt_{attempt['attempt_number']}"
        )
        disclosures = ["MOCK_DATA_ONLY", "NOT_SCIENTIFIC_EVIDENCE"]
        disclosures.extend(responsibility["must_disclose"])
        stub = {
            "mock_only": True,
            "scientific_compute": False,
            "scenario_key": scenario["scenario_key"],
            "node_id": node_id,
            "mock_output_key": responsibility["mock_output_key"],
            "fact_set_key": node["fact_set_key"],
            "emitted_fact_kinds": responsibility["emitted_fact_kinds"],
            "entity_refs": [
                "mock://t01_phase1_mock_v01/"
                f"{scenario['scenario_key']}/{node_id.lower()}/"
                f"attempt-{attempt['attempt_number']}"
            ],
            "artifact_ids": [artifact_id],
            "disclosures": list(dict.fromkeys(disclosures)),
            "scientific_claims": [],
        }
        self.bundle.validate_mock_stub(stub, f"attempt fixture {fixture_key}")
        return stub

    def materialize(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []

        for index, fixture in enumerate(self.bundle.fixture_manifest["input_fixtures"]):
            payload = pretty_json_bytes(self._input_payload(fixture))
            written = self._write(fixture["planned_payload_path"], payload)
            files.append(
                {
                    "kind": "INPUT_FIXTURE",
                    "logical_key": fixture["fixture_key"],
                    **written,
                    "source_pointer": f"/input_fixtures/{index}",
                }
            )

        for index, variant in enumerate(self.bundle.fixture_manifest["request_variants"]):
            scenario_ordinal = (
                list(self.bundle.scenario_by_key).index(variant["scenario_key"]) + 1
            )
            request = self._request_payload(variant, scenario_ordinal)
            written = self._write(
                variant["planned_payload_path"], pretty_json_bytes(request)
            )
            files.append(
                {
                    "kind": "REQUEST_VARIANT",
                    "logical_key": variant["request_variant_key"],
                    **written,
                    "source_pointer": f"/request_variants/{index}",
                }
            )

        attempt_index = 0
        for scenario_index, scenario in enumerate(self.bundle.scenarios):
            for node_id, node in scenario["node_plan"].items():
                for attempt_index_in_node, attempt in enumerate(node["attempts"]):
                    fixture_key = attempt["fixture_result_key"]
                    if fixture_key is None:
                        continue
                    match = _ATTEMPT_KEY_RE.fullmatch(fixture_key)
                    if match is None:
                        raise ContractError(f"invalid attempt fixture key: {fixture_key}")
                    relative_path = (
                        "dify/t01-phase1-mock-v0.1/fixtures/node-results/"
                        f"{match.group('scenario')}/n{match.group('node')}/"
                        f"attempt-{match.group('attempt')}.json"
                    )
                    stub = self._attempt_stub(scenario, node_id, node, attempt)
                    written = self._write(relative_path, pretty_json_bytes(stub))
                    files.append(
                        {
                            "kind": "ATTEMPT_RESULT",
                            "logical_key": fixture_key,
                            **written,
                            "source_pointer": (
                                f"/scenarios/{scenario_index}/node_plan/{node_id}/"
                                f"attempts/{attempt_index_in_node}"
                            ),
                        }
                    )
                    attempt_index += 1

        document = {
            "$schema": MATERIALIZATION_SCHEMA_PATH.name,
            "document_type": "T01_PHASE1_MOCK_FIXTURE_MATERIALIZATION",
            "materialization_version": MATERIALIZATION_VERSION,
            "source_fixture_manifest_version": FIXTURE_MANIFEST_VERSION,
            "source_scenario_catalog_version": SCENARIO_CATALOG_VERSION,
            "envelope_contract_version": ENVELOPE_CONTRACT_VERSION,
            "implementation_milestone": "PH1-MOCK-M2",
            "materialization_state": "MATERIALIZED_AND_VERIFIED",
            "data_classification": "MOCK_DATA",
            "scientific_compute": False,
            "network_access_performed": False,
            "legacy_implementation_reused": False,
            "dify_dsl_created": False,
            "source_sha256": deepcopy(self.bundle.source_sha256),
            "counts": {
                "input_fixture_count": 2,
                "request_variant_count": 22,
                "attempt_fixture_count": attempt_index,
                "payload_file_count": len(files),
            },
            "files": files,
        }
        schema = load_json(MATERIALIZATION_SCHEMA_PATH)
        validate_instance(document, schema, "fixture materialization")
        MATERIALIZATION_PATH.write_bytes(pretty_json_bytes(document))
        FixtureRepository(self.bundle).verify()
        return document


class FixtureRepository:
    """Read-only, fail-closed access to the materialized fixture set."""

    def __init__(self, bundle: SpecificationBundle | None = None) -> None:
        self.bundle = bundle or SpecificationBundle.load()
        if not MATERIALIZATION_PATH.exists():
            raise ContractError(
                "fixture payloads are not materialized; run FixtureMaterializer first"
            )
        self.materialization_schema = load_json(MATERIALIZATION_SCHEMA_PATH)
        self.materialization = load_json(MATERIALIZATION_PATH)
        validate_instance(
            self.materialization,
            self.materialization_schema,
            "fixture materialization",
        )
        self._entry_by_key = {
            item["logical_key"]: item for item in self.materialization["files"]
        }
        self._attempt_stub_cache: dict[str, dict[str, Any]] = {}
        if len(self._entry_by_key) != len(self.materialization["files"]):
            raise ContractError("materialization contains duplicate logical keys")

    @classmethod
    def check(cls, bundle: SpecificationBundle | None = None) -> dict[str, int]:
        """Verify an existing materialization without writing any file."""

        return cls(bundle).verify()

    def load_input(self, fixture_key: str) -> dict[str, Any]:
        if fixture_key not in self.bundle.input_fixture_by_key:
            raise ContractError(f"unknown input fixture key: {fixture_key}")
        entry = self._entry_by_key.get(fixture_key)
        if entry is None or entry["kind"] != "INPUT_FIXTURE":
            raise ContractError(f"input fixture is not materialized: {fixture_key}")
        return load_json(resolve_project_relative(entry["path"], must_exist=True))

    def load_request_variant(self, request_variant_key: str) -> dict[str, Any]:
        if request_variant_key not in self.bundle.request_variant_by_key:
            raise ContractError(f"unknown request variant: {request_variant_key}")
        entry = self._entry_by_key.get(request_variant_key)
        if entry is None or entry["kind"] != "REQUEST_VARIANT":
            raise ContractError(f"request variant is not materialized: {request_variant_key}")
        request = load_json(resolve_project_relative(entry["path"], must_exist=True))
        self.bundle.validate_envelope(request, f"request variant {request_variant_key}")
        return request

    def instantiate_submission_request(
        self,
        scenario_key: str,
        submission_key: str,
    ) -> dict[str, Any]:
        case = self.bundle.fixture_case_by_scenario.get(scenario_key)
        if case is None:
            raise ContractError(f"unknown fixture case: {scenario_key}")
        binding = next(
            (
                item
                for item in case["submission_bindings"]
                if item["submission_key"] == submission_key
            ),
            None,
        )
        if binding is None:
            raise ContractError(
                f"unknown submission {submission_key} for scenario {scenario_key}"
            )
        request = deepcopy(self.load_request_variant(binding["request_variant_key"]))
        seed = f"{case['fixture_case_id']}:{submission_key}"
        request["request_id"] = _request_identity(seed)
        request["envelope_id"] = _envelope_identity(seed)
        timestamp = _request_timestamp(case["ordinal"], int(submission_key.rsplit("_", 1)[1]))
        request["created_at"] = timestamp
        request["audit"]["trace_id"] = (
            f"t01_phase1_mock_v01.trace.submission.{stable_uuid4(seed)}"
        )
        request["audit"]["correlation_id"] = (
            f"t01_phase1_mock_v01.correlation.{stable_uuid4(seed)}"
        )
        event = request["audit"]["events"][0]
        event["event_id"] = f"t01_phase1_mock_v01.event.submission.{stable_uuid4(seed)}"
        event["occurred_at"] = timestamp
        self.bundle.validate_envelope(request, f"submission request {seed}")
        return request

    def resolve_attempt_fixture_path(self, fixture_result_key: str) -> Path:
        if fixture_result_key not in set(self.bundle.declared_attempt_fixture_keys):
            raise ContractError(f"undeclared attempt fixture key: {fixture_result_key}")
        entry = self._entry_by_key.get(fixture_result_key)
        if entry is None or entry["kind"] != "ATTEMPT_RESULT":
            raise ContractError(f"attempt fixture is not materialized: {fixture_result_key}")
        return resolve_project_relative(entry["path"], must_exist=True)

    def load_attempt_stub(self, fixture_result_key: str) -> dict[str, Any]:
        cached = self._attempt_stub_cache.get(fixture_result_key)
        if cached is not None:
            return deepcopy(cached)
        path = self.resolve_attempt_fixture_path(fixture_result_key)
        stub = load_json(path)
        self.bundle.validate_mock_stub(stub, f"attempt fixture {fixture_result_key}")
        self._attempt_stub_cache[fixture_result_key] = deepcopy(stub)
        return deepcopy(stub)

    def attempt_file_metadata(self, fixture_result_key: str) -> dict[str, Any]:
        entry = self._entry_by_key.get(fixture_result_key)
        if entry is None:
            raise ContractError(f"attempt fixture is not materialized: {fixture_result_key}")
        return deepcopy(entry)

    def verify(self) -> dict[str, int]:
        validate_instance(
            self.materialization,
            self.materialization_schema,
            "fixture materialization",
        )
        if self.materialization["source_sha256"] != self.bundle.source_sha256:
            raise ContractError("frozen M1 source hash changed after fixture materialization")
        expected_keys = {
            *self.bundle.input_fixture_by_key,
            *self.bundle.request_variant_by_key,
            *self.bundle.declared_attempt_fixture_keys,
        }
        if set(self._entry_by_key) != expected_keys:
            missing = sorted(expected_keys - set(self._entry_by_key))
            extra = sorted(set(self._entry_by_key) - expected_keys)
            raise ContractError(
                f"materialized fixture closed set mismatch; missing={missing}, extra={extra}"
            )
        for entry in self.materialization["files"]:
            if entry["data_classification"] != "MOCK_DATA":
                raise ContractError(f"fixture index entry is not MOCK_DATA: {entry['path']}")
            if entry["scientific_compute"] is not False:
                raise ContractError(
                    f"fixture index entry enables scientific compute: {entry['path']}"
                )
            path = resolve_project_relative(entry["path"], must_exist=True)
            payload = path.read_bytes()
            if len(payload) != entry["size_bytes"]:
                raise ContractError(f"fixture size mismatch: {entry['path']}")
            if sha256_bytes(payload) != entry["sha256"]:
                raise ContractError(f"fixture hash mismatch: {entry['path']}")

        for key in self.bundle.input_fixture_by_key:
            payload = self.load_input(key)
            if payload["data_classification"] != "MOCK_DATA":
                raise ContractError(f"input fixture {key} is not MOCK_DATA")
            if payload["scientific_compute"] is not False:
                raise ContractError(f"input fixture {key} enables scientific compute")
            structure = payload["structure"]
            embedded = payload["synthetic_structure_payload"]
            if structure is None:
                if embedded is not None:
                    raise ContractError(f"input fixture {key} has unexpected structure payload")
            else:
                if embedded.encode("ascii") != _STRUCTURE_BYTES:
                    raise ContractError(f"input fixture {key} structure payload changed")
                if sha256_bytes(embedded.encode("ascii")) != structure["artifact"]["sha256"]:
                    raise ContractError(f"input fixture {key} structure hash mismatch")
        for key in self.bundle.request_variant_by_key:
            request = self.load_request_variant(key)
            expected_sequence_hash = sha256_bytes(
                request["inputs"]["protein_sequence"].encode("ascii")
            )
            if request["input_fingerprints"]["protein_sequence_sha256"] != expected_sequence_hash:
                raise ContractError(f"request sequence fingerprint mismatch: {key}")
            structure = request["inputs"]["structure"]
            expected_structure_hash = (
                None if structure is None else structure["artifact"]["sha256"]
            )
            if request["input_fingerprints"]["structure_sha256"] != expected_structure_hash:
                raise ContractError(f"request structure fingerprint mismatch: {key}")
        for key in self.bundle.declared_attempt_fixture_keys:
            self.load_attempt_stub(key)

        actual_node_files = {
            path.resolve()
            for path in (FIXTURE_ROOT / "node-results").rglob("*.json")
        }
        expected_node_files = {
            resolve_project_relative(self._entry_by_key[key]["path"], must_exist=True)
            for key in self.bundle.declared_attempt_fixture_keys
        }
        if actual_node_files != expected_node_files:
            raise ContractError("node-result directory contains missing or undeclared JSON files")

        expected_payload_paths = {
            resolve_project_relative(item["path"], must_exist=True)
            for item in self.materialization["files"]
        }
        actual_payload_paths = {
            path.resolve()
            for directory in (FIXTURE_ROOT / "inputs", FIXTURE_ROOT / "requests", FIXTURE_ROOT / "node-results")
            if directory.exists()
            for path in directory.rglob("*")
            if path.is_file()
        }
        if actual_payload_paths != expected_payload_paths:
            raise ContractError("fixture payload directories contain missing or undeclared files")
        return deepcopy(self.materialization["counts"])


def canonical_request_fingerprint(request: dict[str, Any]) -> str:
    return canonical_sha256(
        {
            "scenario_ref": request["scenario_ref"],
            "inputs": request["inputs"],
            "options": request["options"],
            "input_fingerprints": request["input_fingerprints"],
        }
    )
