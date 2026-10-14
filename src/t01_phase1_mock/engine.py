"""Deterministic scenario engine with checkpoint, cancel, recovery, and idempotency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import SpecificationBundle
from .constants import RUN_ID_PATTERN
from .fixtures import (
    FixtureRepository,
    canonical_request_fingerprint,
)
from .jsonio import ContractError, canonical_sha256, deep_copy, sha256_bytes, stable_uuid4
from .projection import RunProjector, make_error
from .storage import FilesystemRunStore, InMemoryRunStore, RunStore


@dataclass(frozen=True)
class SubmissionResult:
    action: str
    request_id: str | None
    run_id: str | None
    run: dict[str, Any] | None
    error: dict[str, Any] | None

    @property
    def error_code(self) -> str | None:
        return None if self.error is None else self.error["code"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "request_id": self.request_id,
            "run_id": self.run_id,
            "run": deep_copy(self.run),
            "error": deep_copy(self.error),
            "error_code": self.error_code,
        }


class MockBackend:
    """Offline-only backend whose control truth is the frozen scenario catalog."""

    def __init__(
        self,
        *,
        bundle: SpecificationBundle | None = None,
        fixtures: FixtureRepository | None = None,
        store: RunStore | None = None,
    ) -> None:
        self.bundle = bundle or SpecificationBundle.load()
        self.fixtures = fixtures or FixtureRepository(self.bundle)
        self.store = store or InMemoryRunStore()
        self.projector = RunProjector(self.bundle, self.fixtures)

    @classmethod
    def local(
        cls,
        *,
        bundle: SpecificationBundle | None = None,
        fixtures: FixtureRepository | None = None,
        runtime_root: Path | None = None,
    ) -> "MockBackend":
        """Create the offline local entry point with filesystem-backed state."""

        return cls(
            bundle=bundle,
            fixtures=fixtures,
            store=FilesystemRunStore(runtime_root),
        )

    @staticmethod
    def _run_id(seed: str) -> str:
        return f"t01-phase1-mock-v01-run-{stable_uuid4('run:' + seed)}"

    def _request_error(
        self,
        request: dict[str, Any],
        code: str,
    ) -> SubmissionResult:
        scenario_ref = request.get("scenario_ref")
        scenario_key = (
            scenario_ref.rsplit(".", 1)[-1]
            if isinstance(scenario_ref, str) and "." in scenario_ref
            else "request"
        )
        occurred_at = request.get("created_at", "2026-09-04T00:00:00Z")
        issue = make_error(
            run_id="request-validation",
            scenario_key=scenario_key,
            code=code,
            occurred_at=occurred_at,
            node_id=None,
            attempt_id=None,
        )
        return SubmissionResult(
            action="REJECT_REQUEST",
            request_id=request.get("request_id"),
            run_id=None,
            run=None,
            error=issue,
        )

    def _validate_request_integrity(
        self, request: dict[str, Any]
    ) -> dict[str, Any]:
        self.bundle.validate_envelope(request, "submitted request")
        scenario = self.bundle.scenario_for_ref(request["scenario_ref"])
        sequence_hash = sha256_bytes(request["inputs"]["protein_sequence"].encode("ascii"))
        if request["input_fingerprints"]["protein_sequence_sha256"] != sequence_hash:
            raise ContractError("protein sequence fingerprint mismatch")
        structure = request["inputs"]["structure"]
        structure_hash = None if structure is None else structure["artifact"]["sha256"]
        if request["input_fingerprints"]["structure_sha256"] != structure_hash:
            raise ContractError("structure fingerprint mismatch")
        if structure is not None:
            if structure["structure_format"] != structure["artifact"]["format"]:
                raise ContractError("structure format and artifact format disagree")
            if structure["artifact"]["source_node_id"] is not None:
                raise ContractError("request structure cannot claim a node producer")
        return scenario

    @staticmethod
    def _validate_profile(request: dict[str, Any], scenario: dict[str, Any]) -> None:
        profile = scenario["input_profile"]
        structure = request["inputs"]["structure"]
        if profile["structure_case"] == "PROVIDED_LOCAL_PDB":
            if structure is None or structure["structure_format"] != "PDB":
                raise ContractError("scenario requires the provided local PDB fixture")
        elif structure is not None:
            raise ContractError("scenario requires an absent structure input")
        if request["options"]["design_objective"] != profile["design_objective"]:
            raise ContractError("request design objective differs from scenario profile")
        expression_host = request["options"]["expression_host"]
        expression_case = profile["expression_host_case"]
        if expression_case == "OMITTED" and expression_host is not None:
            raise ContractError("scenario requires expression_host=null")
        if expression_case != "OMITTED" and expression_host is None:
            raise ContractError("scenario requires an explicit expression_host fixture")
        if profile["remote_lookup_allowed"] is not False:
            raise ContractError("remote lookup cannot be enabled in M2")

    def _new_record(
        self,
        *,
        request: dict[str, Any],
        scenario: dict[str, Any],
        fingerprint: str,
        run_id: str,
        recovery_of_run_id: str | None = None,
        checkpoint_index: int = 0,
        checkpoint_fact: str = "TERMINAL_PROJECTION_AVAILABLE",
        envelope: dict[str, Any],
        terminal: bool,
    ) -> dict[str, Any]:
        return {
            "document_type": "T01_PHASE1_MOCK_RUN_RECORD",
            "record_namespace": "t01_phase1_mock_v01",
            "record_version": "T01-PHASE1-MOCK-M2-RUN-RECORD-v0.1",
            "run_id": run_id,
            "scenario_key": scenario["scenario_key"],
            "request": deep_copy(request),
            "canonical_request_fingerprint": fingerprint,
            "checkpoint_index": checkpoint_index,
            "checkpoint_fact": checkpoint_fact,
            "recovery_of_run_id": recovery_of_run_id,
            "control_emission_count": 1,
            "terminal": terminal,
            "envelope": deep_copy(envelope),
        }

    def submit(self, request: dict[str, Any]) -> SubmissionResult:
        try:
            scenario = self._validate_request_integrity(request)
        except ContractError:
            return self._request_error(request, "REQUEST_SCHEMA_INVALID")

        fingerprint = canonical_request_fingerprint(request)
        existing = self.store.get_idempotency(request["idempotency_key"])
        if existing is not None:
            if existing["fingerprint"] != fingerprint:
                return self._request_error(request, "REQUEST_IDEMPOTENCY_CONFLICT")
            record = self.store.get_record(existing["run_id"])
            if record is None:
                raise ContractError("idempotency index references a missing run")
            return SubmissionResult(
                action="RETURN_EXISTING_RUN",
                request_id=request["request_id"],
                run_id=record["run_id"],
                run=deep_copy(record["envelope"]),
                error=None,
            )

        try:
            self._validate_profile(request, scenario)
        except ContractError:
            return self._request_error(request, "INTERNAL_CONTRACT_VIOLATION")

        run_id = self._run_id(
            f"{request['idempotency_key']}:{fingerprint}:initial"
        )
        if RUN_ID_PATTERN.fullmatch(run_id) is None:
            raise ContractError("backend generated an invalid run ID")
        plan = self.bundle.checkpoint_by_scenario.get(scenario["scenario_key"])
        if plan is None:
            envelope = self.projector.terminal(
                request=request, scenario=scenario, run_id=run_id
            )
            checkpoint_index = 0
            fact = "TERMINAL_PROJECTION_AVAILABLE"
            terminal = True
        else:
            first = plan["steps"][0]
            if first["action"] != "SUBMIT_CREATE":
                raise ContractError("checkpoint plan does not begin with SUBMIT_CREATE")
            envelope = self.projector.checkpoint(
                request=request,
                scenario=scenario,
                run_id=run_id,
                checkpoint_fact=first["checkpoint_fact"],
            )
            checkpoint_index = 1
            fact = first["checkpoint_fact"]
            terminal = False
        record = self._new_record(
            request=request,
            scenario=scenario,
            fingerprint=fingerprint,
            run_id=run_id,
            checkpoint_index=checkpoint_index,
            checkpoint_fact=fact,
            envelope=envelope,
            terminal=terminal,
        )
        self.store.put_record(record)
        self.store.bind_idempotency(request["idempotency_key"], fingerprint, run_id)
        return SubmissionResult(
            action="CREATE_RUN",
            request_id=request["request_id"],
            run_id=run_id,
            run=deep_copy(envelope),
            error=None,
        )

    def _record(self, run_id: str) -> dict[str, Any]:
        if RUN_ID_PATTERN.fullmatch(run_id) is None:
            raise ContractError(f"invalid run_id: {run_id}")
        record = self.store.get_record(run_id)
        if record is None:
            raise ContractError(f"unknown run_id: {run_id}")
        return record

    def get_run(self, run_id: str) -> dict[str, Any]:
        return deep_copy(self._record(run_id)["envelope"])

    def get_run_metadata(self, run_id: str) -> dict[str, Any]:
        record = self._record(run_id)
        return {
            key: deep_copy(record[key])
            for key in (
                "run_id",
                "scenario_key",
                "checkpoint_index",
                "checkpoint_fact",
                "recovery_of_run_id",
                "control_emission_count",
                "terminal",
            )
        }

    def _next_step(self, record: dict[str, Any]) -> dict[str, Any]:
        if record["terminal"]:
            raise ContractError(f"run is already terminal: {record['run_id']}")
        plan = self.bundle.checkpoint_by_scenario.get(record["scenario_key"])
        if plan is None:
            raise ContractError("run has no checkpoint plan")
        index = record["checkpoint_index"]
        if index >= len(plan["steps"]):
            raise ContractError("checkpoint plan is exhausted")
        return plan["steps"][index]

    def _advance(self, run_id: str, action: str) -> tuple[str, dict[str, Any]]:
        record = self._record(run_id)
        step = self._next_step(record)
        if step["action"] != action:
            raise ContractError(
                f"checkpoint action mismatch: expected {step['action']}, got {action}"
            )
        scenario = self.bundle.scenario_by_key[record["scenario_key"]]

        if action == "REQUEST_RECOVERY":
            original = self.projector.recovery_origin_failure(
                request=record["request"],
                scenario=scenario,
                run_id=run_id,
            )
            record["envelope"] = original
            record["terminal"] = True
            record["checkpoint_fact"] = "RECOVERY_SUPERSEDED_BY_NEW_RUN"
            self.store.put_record(record)

            recovery_run_id = self._run_id(f"{run_id}:recovery:1")
            recovered = self.projector.checkpoint(
                request=record["request"],
                scenario=scenario,
                run_id=recovery_run_id,
                checkpoint_fact=step["checkpoint_fact"],
                recovery_of_run_id=run_id,
            )
            recovery_record = self._new_record(
                request=record["request"],
                scenario=scenario,
                fingerprint=record["canonical_request_fingerprint"],
                run_id=recovery_run_id,
                recovery_of_run_id=run_id,
                checkpoint_index=step["sequence"],
                checkpoint_fact=step["checkpoint_fact"],
                envelope=recovered,
                terminal=False,
            )
            self.store.put_record(recovery_record)
            return recovery_run_id, deep_copy(recovered)

        terminal = action == "POLL_TERMINAL"
        if terminal:
            envelope = self.projector.terminal(
                request=record["request"],
                scenario=scenario,
                run_id=run_id,
                recovery_of_run_id=record["recovery_of_run_id"],
            )
        else:
            envelope = self.projector.checkpoint(
                request=record["request"],
                scenario=scenario,
                run_id=run_id,
                checkpoint_fact=step["checkpoint_fact"],
                recovery_of_run_id=record["recovery_of_run_id"],
            )
        if envelope["run_status"] != step["expected_run_status"]:
            raise ContractError("checkpoint projection has the wrong run status")
        record["checkpoint_index"] = step["sequence"]
        record["checkpoint_fact"] = step["checkpoint_fact"]
        record["terminal"] = terminal
        record["envelope"] = deep_copy(envelope)
        self.store.put_record(record)
        return run_id, deep_copy(envelope)

    def poll_run(self, run_id: str) -> dict[str, Any]:
        record = self._record(run_id)
        if record["terminal"]:
            return deep_copy(record["envelope"])
        action = self._next_step(record)["action"]
        if action not in {"POLL_SCENARIO_CHECKPOINT", "POLL_TERMINAL"}:
            raise ContractError(f"run awaits explicit {action}, not a poll")
        _, envelope = self._advance(run_id, action)
        return envelope

    def inject_scenario_event(self, run_id: str, checkpoint_fact: str) -> dict[str, Any]:
        record = self._record(run_id)
        step = self._next_step(record)
        if step["action"] != "INJECT_SCENARIO_EVENT":
            raise ContractError("run is not awaiting a scenario event")
        if checkpoint_fact != step["checkpoint_fact"]:
            raise ContractError(
                f"scenario event mismatch: expected {step['checkpoint_fact']}"
            )
        _, envelope = self._advance(run_id, "INJECT_SCENARIO_EVENT")
        return envelope

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        _, envelope = self._advance(run_id, "CANCEL_RUN")
        return envelope

    def recover_run(self, run_id: str) -> tuple[str, dict[str, Any]]:
        return self._advance(run_id, "REQUEST_RECOVERY")

    def run_count(self) -> int:
        return len(self.store.run_ids())

    def run_hash(self, run_id: str) -> str:
        return canonical_sha256(self.get_run(run_id))

    def read_artifact(self, run_id: str, artifact_id: str) -> bytes:
        """Resolve a run-scoped artifact URI to its verified fixture bytes."""

        run = self.get_run(run_id)
        artifacts = [
            artifact
            for node in run["node_results"]
            if node["output"] is not None
            for artifact in node["output"]["artifacts"]
        ]
        matches = [item for item in artifacts if item["artifact_id"] == artifact_id]
        if len(matches) != 1:
            raise ContractError(f"unknown or ambiguous artifact_id: {artifact_id}")
        artifact = matches[0]
        required_prefix = f"artifact://t01-phase1-mock-v0.1/{run_id}/"
        if not artifact["uri"].startswith(required_prefix):
            raise ContractError("artifact URI is outside the run namespace")
        fixture_key = artifact["metadata"].get("fixture_result_key")
        if not isinstance(fixture_key, str):
            raise ContractError("artifact has no fixture binding")
        path = self.fixtures.resolve_attempt_fixture_path(fixture_key)
        payload = path.read_bytes()
        if len(payload) != artifact["size_bytes"]:
            raise ContractError("artifact byte size differs from its envelope reference")
        if sha256_bytes(payload) != artifact["sha256"]:
            raise ContractError("artifact SHA-256 differs from its envelope reference")
        return payload
