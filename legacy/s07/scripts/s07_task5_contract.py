"""Offline S-07 review contract and evidence checks; never a runtime adapter."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from t01_mock_mcp.contracts import ArtifactRef, ToolError, WarningItem


OPERATIONS = (
    "PDB_SEARCH", "PDB_METADATA", "PDB_STRUCTURE", "BLAST_UNIPROT",
    "UNIPROT_RECORD", "AFDB_LOOKUP", "AFDB_STRUCTURE",
)
RULE_IDS = [f"S07-EQ-{number:02d}" for number in range(1, 6)]
SUCCESS = {"SUCCEEDED_WITH_RESULTS", "SUCCEEDED_EMPTY"}
CONTRACT_VERSION = "s07.task5.v1-review"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class InputBinding(ReviewModel):
    input_artifact_id: str
    sequence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sequence_length: int = Field(gt=0)
    organism_name: str | None
    accession_hint: str | None


class Profile(ReviewModel):
    profile_id: Literal["s07-api-review-20260903"]
    profile_artifact_id: str
    intended_access_mode: Literal["API"]
    uniprot_search_scope: Literal["uniprotkb_swissprot"]
    rule_status: Literal["PROVISIONAL_USER_APPROVED_EXPERT_PENDING"]
    expert_confirmation_ids: list[str]

    @model_validator(mode="after")
    def keep_all_pending_rules(self) -> "Profile":
        if self.expert_confirmation_ids != RULE_IDS:
            raise ValueError("The five pending rules must remain explicitly attached")
        return self


class SourceRun(ReviewModel):
    operation: Literal[
        "PDB_SEARCH", "PDB_METADATA", "PDB_STRUCTURE", "BLAST_UNIPROT",
        "UNIPROT_RECORD", "AFDB_LOOKUP", "AFDB_STRUCTURE",
    ]
    status: Literal[
        "SUCCEEDED_WITH_RESULTS", "SUCCEEDED_EMPTY", "FAILED", "CANCELLED", "NOT_RUN"
    ]
    reason_code: str = Field(min_length=1)
    bound_sequence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    returned_count: int = Field(ge=0)
    complete: bool
    capped: bool
    failures: list[ToolError] = Field(default_factory=list)
    evidence_kind: Literal["FROZEN_REPLAY", "CONTROLLED", "NOT_RUN"]
    original_access_mode: Literal["API", "LOCAL", "OFFLINE"] | None
    endpoint_or_release: str | None
    tool_name: str | None
    tool_version: str | None
    data_version: str | None
    version_note: str
    original_time: dict[str, str | None]
    evaluated_at: datetime
    parameters: dict[str, Any]
    artifact_ids: list[str]

    @model_validator(mode="after")
    def no_false_execution_or_completeness(self) -> "SourceRun":
        if self.status == "NOT_RUN":
            if any((self.returned_count, self.complete, self.capped, self.failures,
                    self.artifact_ids, self.original_time, self.endpoint_or_release,
                    self.tool_name, self.tool_version, self.data_version,
                    self.original_access_mode, self.parameters)):
                raise ValueError("NOT_RUN cannot claim a query, output, time, or completeness")
            if self.evidence_kind != "NOT_RUN":
                raise ValueError("NOT_RUN requires NOT_RUN provenance")
            return self
        if self.evidence_kind == "NOT_RUN" or not self.artifact_ids:
            raise ValueError("Executed/replayed/controlled states need saved evidence")
        if self.status == "SUCCEEDED_EMPTY" and self.returned_count != 0:
            raise ValueError("Empty means zero returned records")
        if self.status == "SUCCEEDED_WITH_RESULTS" and self.returned_count == 0:
            raise ValueError("Results require at least one returned record")
        if self.status in {"FAILED", "CANCELLED"}:
            if not self.failures or self.complete or self.returned_count:
                raise ValueError("Failure needs errors and cannot claim complete/usable results")
        if self.status == "CANCELLED" and any(
            item.category.value != "CANCELLED" for item in self.failures
        ):
            raise ValueError("Cancellation must retain its own error category")
        if (self.capped or self.failures) and self.complete:
            raise ValueError("Capped or partly failed results cannot be called complete")
        if self.status == "SUCCEEDED_EMPTY" and self.failures:
            raise ValueError("Normal empty cannot hide a failure")
        if self.evidence_kind == "CONTROLLED":
            if self.original_access_mode != "OFFLINE" or self.original_time:
                raise ValueError("Controlled cases must not invent remote invocation facts")
        return self


def method_summary(sources: list[SourceRun], timestamp: str) -> dict[str, Any]:
    """Project captured facts into the expert's MethodSummary shape."""
    entries = []
    for source in sources:
        if source.status == "NOT_RUN":
            continue
        runtime = None
        start, end = source.original_time.get("started_at"), source.original_time.get("finished_at")
        if start and end:
            runtime = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
            if runtime < 0:
                raise ValueError("Recorded source finish precedes start")
        entries.append({
            "step": "fetch_structure",
            "tool": f"{source.operation}: {source.tool_name or 'CONTROLLED_FIXTURE'}",
            "version": source.tool_version or "UNREPORTED" if source.evidence_kind != "CONTROLLED" else "CONTROLLED_FIXTURE",
            "parameters": {
                "source_operation": source.operation, "source_status": source.status,
                "evidence_kind": source.evidence_kind, "data_version": source.data_version,
                "candidate_collection_complete": source.complete, "capped": source.capped,
                "recorded_parameters": source.parameters,
            },
            "runtime_seconds": runtime,
        })
    return {"entries": entries, "pipeline_version": CONTRACT_VERSION, "timestamp": timestamp}


class Alignment(ReviewModel):
    query_length: int = Field(gt=0)
    reference_length: int = Field(gt=0)
    query_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_pct: float | None = Field(default=None, ge=0, le=100)
    query_coverage: float | None = Field(default=None, ge=0, le=1)
    target_coverage: float | None = Field(default=None, ge=0, le=1)
    exact_full_length: bool
    evidence_artifact_id: str

    @model_validator(mode="after")
    def exact_means_exact(self) -> "Alignment":
        equal = self.query_sha256 == self.reference_sha256 and self.query_length == self.reference_length
        if self.exact_full_length != equal:
            raise ValueError("Exact sequence status disagrees with sequence hashes/lengths")
        if equal and (self.identity_pct, self.query_coverage, self.target_coverage) != (100.0, 1.0, 1.0):
            raise ValueError("Exact full-length alignment requires full identity and both coverages")
        return self


class CoordinateMapping(ReviewModel):
    status: Literal["FULL", "PARTIAL"]
    target_length: int = Field(gt=0)
    mapped_count: int = Field(gt=0)
    missing_ranges: list[tuple[int, int]]
    per_residue_artifact_id: str

    @model_validator(mode="after")
    def coverage_is_not_alignment_coverage(self) -> "CoordinateMapping":
        previous, missing = 0, 0
        for start, end in self.missing_ranges:
            if not previous < start <= end <= self.target_length:
                raise ValueError("Missing ranges must be sorted, disjoint and within the input")
            previous = end
            missing += end - start + 1
        if self.mapped_count + missing != self.target_length:
            raise ValueError("Mapped and missing residue counts must cover the input exactly")
        if (self.status == "FULL") != (missing == 0):
            raise ValueError("FULL/PARTIAL disagrees with the missing positions")
        return self


class Candidate(ReviewModel):
    candidate_id: str
    source: Literal["experimental", "alphafolddb"]
    source_object_id: str
    entry_id: str | None
    entity_id: str | None
    label_asym_id: str | None
    auth_asym_id: str | None
    model_number: int | None = Field(default=None, gt=0)
    assembly_id: str | None
    accession: str | None
    model_version: str | None
    organism_name: str | None
    method: str | None
    resolution_angstrom: float | None = Field(default=None, gt=0)
    alignment: Alignment
    coordinate_mapping: CoordinateMapping | None
    eligibility: Literal["ELIGIBLE_PROVISIONAL", "INELIGIBLE", "REVIEW_REQUIRED"]
    reason_codes: list[str] = Field(min_length=1)
    structure_artifact_id: str | None
    confidence_artifact_ids: list[str]
    raw_confidence_summary: dict[str, Any]
    quality_assessment: Literal["PENDING_S09"]

    @model_validator(mode="after")
    def respect_source_and_quality_ownership(self) -> "Candidate":
        if self.source == "alphafolddb":
            if self.method is not None or self.resolution_angstrom is not None:
                raise ValueError("Prediction method/resolution fields must be null")
        elif self.confidence_artifact_ids or self.raw_confidence_summary:
            raise ValueError("Experimental B factors must not become pLDDT")
        if self.coordinate_mapping and not self.structure_artifact_id:
            raise ValueError("Coordinate mapping must refer to a saved structure")
        if self.eligibility == "ELIGIBLE_PROVISIONAL":
            if not all((self.structure_artifact_id, self.coordinate_mapping,
                        self.entity_id, self.label_asym_id, self.auth_asym_id, self.model_number)):
                raise ValueError("Selected-ready candidates require unique chain/model and coordinates")
            if self.source == "alphafolddb" and not self.alignment.exact_full_length:
                raise ValueError("EQ-03 forbids automatic non-exact AFDB selection")
            if self.source == "experimental" and not (
                self.alignment.identity_pct is not None and self.alignment.identity_pct > 95
                and self.alignment.query_coverage is not None and self.alignment.query_coverage > .90
            ):
                raise ValueError("PDB candidates must strictly exceed the expert thresholds")
        return self


class S07Result(ReviewModel):
    contract_version: Literal["s07.task5.v1-review"]
    record_kind: Literal["S07_INTERNAL_RESULT"]
    execution_kind: Literal["OFFLINE_CONTRACT_CHECK"]
    deployment_status: Literal["NOT_DEPLOYED"]
    scientific_acceptance: Literal["NOT_RUN"]
    case_scope: Literal["CONTROLLED_COMPOSITION", "COMPONENT_PROBE"]
    run_id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    step_id: Literal["S-07"]
    attempt: int = Field(ge=1)
    generated_at: datetime
    status: Literal["SUCCEEDED", "DEGRADED", "WAITING_USER", "FAILED", "CANCELLED"]
    input: InputBinding
    profile: Profile
    retrieval_outcome: Literal[
        "EXISTING_STRUCTURE_SELECTED", "NO_ELIGIBLE_EXISTING_STRUCTURE"
    ] | None
    selected_candidate_id: str | None
    selection_reason_codes: list[str]
    next_step: Literal["S-08", "S-09"] | None
    reliability: Literal["RELIABLE", "UNRELIABLE"]
    requires_review: bool
    review_reasons: list[str]
    source_runs: list[SourceRun]
    candidates: list[Candidate]
    candidate_total: int = Field(ge=0)
    candidate_summary_complete: bool
    candidate_manifest_artifact_id: str
    source_manifest_artifact_id: str
    method_summary_artifact_id: str
    prior_attempt_result_artifact_id: str | None
    artifacts: list[ArtifactRef]
    warnings: list[WarningItem]
    error: ToolError | None

    @model_validator(mode="after")
    def validate_routes_and_references(self) -> "S07Result":
        sources = {item.operation: item for item in self.source_runs}
        if len(sources) != len(self.source_runs) or set(sources) != set(OPERATIONS):
            raise ValueError("Every planned operation needs exactly one state, including NOT_RUN")
        artifacts = {item.artifact_id: item for item in self.artifacts}
        candidates = {item.candidate_id: item for item in self.candidates}
        if len(artifacts) != len(self.artifacts) or len(candidates) != len(self.candidates):
            raise ValueError("Artifact IDs and candidate IDs must be unique")
        if self.candidate_total < len(candidates) or (
            self.candidate_summary_complete and self.candidate_total != len(candidates)
        ):
            raise ValueError("Candidate summary totals are inconsistent")
        refs = {
            self.input.input_artifact_id, self.profile.profile_artifact_id,
            self.candidate_manifest_artifact_id, self.source_manifest_artifact_id,
            self.method_summary_artifact_id,
        }
        if self.prior_attempt_result_artifact_id:
            refs.add(self.prior_attempt_result_artifact_id)
        if (self.attempt == 1) != (self.prior_attempt_result_artifact_id is None):
            raise ValueError("Retries must reference a saved prior result; first attempts must not")
        for item in self.source_runs:
            if item.bound_sequence_sha256 != self.input.sequence_sha256:
                raise ValueError("Sources must use the unique bound input sequence")
            refs.update(item.artifact_ids)
        for item in self.candidates:
            if (item.alignment.query_sha256, item.alignment.query_length) != (
                self.input.sequence_sha256, self.input.sequence_length
            ):
                raise ValueError("Candidate alignment belongs to a different input")
            refs.add(item.alignment.evidence_artifact_id)
            refs.update(item.confidence_artifact_ids)
            if item.structure_artifact_id:
                refs.add(item.structure_artifact_id)
            if item.coordinate_mapping:
                if item.coordinate_mapping.target_length != self.input.sequence_length:
                    raise ValueError("Coordinate map must be indexed by the input sequence")
                refs.add(item.coordinate_mapping.per_residue_artifact_id)
        if refs - artifacts.keys():
            raise ValueError(f"Unresolved artifact references: {sorted(refs - artifacts.keys())}")
        if any(item.resource_uri != f"artifact://{item.artifact_id}" for item in self.artifacts):
            raise ValueError("This review profile only exposes opaque artifact identifiers")

        warning_codes = {item.code for item in self.warnings}
        abnormal = [s for s in self.source_runs if s.failures]
        if abnormal and self.reliability != "UNRELIABLE":
            raise ValueError("Failed/partial source calls must retain unreliable status")
        if abnormal and "SOURCE_FAILURE" not in warning_codes:
            raise ValueError("R-48 requires a visible failure warning")
        if "R58_CHAIN_AMBIGUITY" in warning_codes:
            if self.reliability != "UNRELIABLE" or self.status != "WAITING_USER":
                raise ValueError("R-58 chain ambiguity must block automatic handoff and require review")
        if self.status in {"FAILED", "CANCELLED", "WAITING_USER"}:
            if any((self.retrieval_outcome, self.selected_candidate_id, self.next_step)):
                raise ValueError("Failure/cancellation/review cannot masquerade as a scientific outcome")
            if self.status == "WAITING_USER":
                if not self.requires_review or not self.review_reasons or self.error:
                    raise ValueError("Review state needs reasons, not a fabricated service error")
            elif self.error is None:
                raise ValueError("Failed/cancelled results need a ToolError")
            if self.status == "CANCELLED" and self.error.category.value != "CANCELLED":
                raise ValueError("Cancellation must not become another failure category")
            return self
        if self.error is not None or self.retrieval_outcome is None:
            raise ValueError("Successful results require an outcome and no top-level ToolError")

        def done(operation: str, empty: bool = False) -> bool:
            item = sources[operation]
            return (
                item.status == ("SUCCEEDED_EMPTY" if empty else "SUCCEEDED_WITH_RESULTS")
                and item.complete and not item.failures and not item.capped
            )

        def skipped(operation: str, reason: str) -> bool:
            item = sources[operation]
            return item.status == "NOT_RUN" and item.reason_code == reason

        pdb_empty = done("PDB_SEARCH", empty=True)
        metadata_fallback = (
            done("PDB_SEARCH") and sources["PDB_METADATA"].status == "FAILED"
            and sources["PDB_METADATA"].reason_code == "ALL_CANDIDATE_METADATA_FAILED"
        )
        if pdb_empty and not all(skipped(op, "NO_PDB_CANDIDATES") for op in (
            "PDB_METADATA", "PDB_STRUCTURE"
        )):
            raise ValueError("Empty PDB search must not claim metadata/structure calls")
        if metadata_fallback and not skipped("PDB_STRUCTURE", "METADATA_UNAVAILABLE"):
            raise ValueError("No candidate file can be selected after all metadata failed")
        accession_ready = done("UNIPROT_RECORD") and sources["UNIPROT_RECORD"].parameters.get("sequence_exact") is True and (
            (self.input.accession_hint is not None and skipped("BLAST_UNIPROT", "ACCESSION_HINT"))
            or (self.input.accession_hint is None and done("BLAST_UNIPROT"))
        )

        if self.retrieval_outcome == "EXISTING_STRUCTURE_SELECTED":
            selected = candidates.get(self.selected_candidate_id or "")
            if not selected or selected.eligibility != "ELIGIBLE_PROVISIONAL":
                raise ValueError("Selected outcome requires an eligible saved candidate")
            if not self.selection_reason_codes or self.next_step != "S-09":
                raise ValueError("Selection must explain why and route to S-09")
            if self.requires_review and not metadata_fallback:
                raise ValueError("An unresolved selection review must not select a structure")
            if selected.source == "experimental":
                if not all(done(op) for op in ("PDB_SEARCH", "PDB_METADATA", "PDB_STRUCTURE")):
                    raise ValueError("Experimental selection needs complete PDB retrieval")
                if not all(skipped(op, "PDB_SELECTED") for op in OPERATIONS[3:]):
                    raise ValueError("PDB selection must keep fallback operations unexecuted")
            elif not (
                (pdb_empty or metadata_fallback) and accession_ready
                and done("AFDB_LOOKUP") and done("AFDB_STRUCTURE")
            ):
                raise ValueError("AFDB selection needs a justified fallback and completed accession/model checks")
            if abnormal:
                if not (
                    selected.source == "alphafolddb" and metadata_fallback
                    and len(abnormal) == 1 and self.status == "DEGRADED" and self.requires_review
                ):
                    raise ValueError("Only documented all-metadata-failed fallback may continue with a failure")
            if selected.coordinate_mapping.status == "PARTIAL":
                if self.status != "DEGRADED" or "PARTIAL_STRUCTURE" not in warning_codes:
                    raise ValueError("Partial structure must retain degradation and warning")
        else:
            if self.selected_candidate_id or self.next_step != "S-08" or abnormal:
                raise ValueError("Normal none must be unselected and error-free before S-08")
            if not self.candidate_summary_complete or any(
                item.eligibility != "INELIGIBLE" for item in self.candidates
            ):
                raise ValueError("Unexamined or undecided candidates cannot become normal none")
            no_accession = (
                self.input.accession_hint is None and done("BLAST_UNIPROT", empty=True)
                and all(skipped(op, "NO_VERIFIED_IDENTIFIER") for op in OPERATIONS[4:])
            )
            no_model = (
                accession_ready and done("AFDB_LOOKUP", empty=True)
                and skipped("AFDB_STRUCTURE", "NO_AFDB_MODEL")
            )
            if not pdb_empty or not (no_accession or no_model):
                raise ValueError("Normal none requires complete PDB and profile-specific AFDB fallback closure")
            if self.requires_review:
                raise ValueError("Pending review must not be treated as normal none")
        return self


def immutable_write(path: Path, data: bytes) -> None:
    """Never overwrite earlier evidence, including during a rerun."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError(f"Immutable evidence already exists with different bytes: {path}")


class EvidenceStore:
    """A small local fixture store, not the future production artifact service."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.refs: dict[str, dict[str, Any]] = {}
        self.origins: dict[str, list[str]] = {}

    def put(self, name: str, data: bytes, kind: str, media: str = "application/json",
            origin: str | None = None) -> dict[str, Any]:
        sha = digest(data)
        artifact_id = f"sha256-{sha}"
        immutable_write(self.root / "objects" / sha, data)
        if artifact_id not in self.refs:
            self.refs[artifact_id] = ArtifactRef(
                artifact_id=artifact_id, logical_name=name, artifact_type=kind,
                media_type=media, sha256=sha, size_bytes=len(data),
                producer_step_id="S-07", created_at=utc_now(),
                resource_uri=f"artifact://{artifact_id}",
            ).model_dump(mode="json")
        if origin and origin not in self.origins.setdefault(artifact_id, []):
            self.origins[artifact_id].append(origin)
        return self.refs[artifact_id]

    def put_json(self, name: str, value: Any, kind: str) -> str:
        return self.put(name, json_bytes(value), kind)["artifact_id"]

    def read(self, ref: ArtifactRef | dict[str, Any]) -> bytes:
        ref = ArtifactRef.model_validate(ref)
        path = self.root / "objects" / ref.sha256
        data = path.read_bytes()
        if len(data) != ref.size_bytes or digest(data) != ref.sha256:
            raise ValueError(f"Artifact integrity mismatch: {ref.artifact_id}")
        return data

    def verify(self, raw: dict[str, Any]) -> S07Result:
        result = S07Result.model_validate(raw)
        content = {ref.artifact_id: self.read(ref) for ref in result.artifacts}
        snapshot = json.loads(content[result.input.input_artifact_id])
        sequence = snapshot["protein_sequence"]
        if digest(sequence.encode("ascii")) != result.input.sequence_sha256 or len(sequence) != result.input.sequence_length:
            raise ValueError("The immutable input snapshot does not match the result")
        if (snapshot["organism_name"], snapshot["accession_hint"]) != (
            result.input.organism_name, result.input.accession_hint
        ):
            raise ValueError("Organism/accession must also come from the same input snapshot")
        profile = json.loads(content[result.profile.profile_artifact_id])
        if profile != result.profile.model_dump(exclude={"profile_artifact_id"}):
            raise ValueError("The saved execution profile differs from the result")
        source_manifest = json.loads(content[result.source_manifest_artifact_id])
        if source_manifest != [item.model_dump(mode="json") for item in result.source_runs]:
            raise ValueError("Source summary differs from its saved manifest")
        summary = json.loads(content[result.method_summary_artifact_id])
        if summary != method_summary(result.source_runs, result.generated_at.isoformat()):
            raise ValueError("MethodSummary must describe the captured source facts without invented versions/times")
        manifest = json.loads(content[result.candidate_manifest_artifact_id])
        full = {item["candidate_id"]: item for item in manifest["items"]}
        if len(full) != len(manifest["items"]) or len(full) != result.candidate_total:
            raise ValueError("Full candidate manifest count/identity is inconsistent")
        for candidate in result.candidates:
            if full.get(candidate.candidate_id) != candidate.model_dump(mode="json"):
                raise ValueError("Candidate summary differs from the full saved record")
            if not candidate.coordinate_mapping:
                continue
            mapping = candidate.coordinate_mapping
            rows = json.loads(content[mapping.per_residue_artifact_id])["input_to_coordinate"]
            if len(rows) != mapping.target_length:
                raise ValueError("Per-residue mapping length must equal input length")
            missing = {i for a, b in mapping.missing_ranges for i in range(a, b + 1)}
            if {i for i, row in enumerate(rows, 1) if row is None} != missing:
                raise ValueError("Missing coordinates must be real null entries at the recorded positions")
            for row in (row for row in rows if row is not None):
                if (row["entity_id"], row["label_asym_id"], row["auth_asym_id"], row["model_number"]) != (
                    candidate.entity_id, candidate.label_asym_id, candidate.auth_asym_id, candidate.model_number
                ):
                    raise ValueError("Per-residue map references a different chain/model")
                if not {"auth_seq_id", "label_seq_id", "insertion_code"} <= row.keys():
                    raise ValueError("Residue identity must include author numbering and insertion code")
            keys = [
                (row["model_number"], row["auth_asym_id"], row["auth_seq_id"], row["insertion_code"])
                for row in rows if row is not None
            ]
            if len(keys) != len(set(keys)):
                raise ValueError("Two input positions must not claim the same coordinate residue")
        if result.prior_attempt_result_artifact_id:
            prior = S07Result.model_validate_json(content[result.prior_attempt_result_artifact_id])
            if (prior.run_id, prior.attempt + 1, prior.input, prior.profile) != (
                result.run_id, result.attempt, result.input, result.profile
            ):
                raise ValueError("A retry must keep its run/input/profile and follow its prior attempt")
        return result

    def save_result(self, raw: dict[str, Any]) -> dict[str, Any]:
        result = self.verify(raw)
        binding = {
            "run_id": result.run_id,
            "input": result.input.model_dump(mode="json"),
            "profile": result.profile.model_dump(mode="json"),
        }
        immutable_write(self.root / "bindings" / f"{result.run_id}.json", json_bytes(binding))
        data = json_bytes(result.model_dump(mode="json"))
        path = self.root / "results" / result.run_id / f"attempt-{result.attempt:03d}.json"
        immutable_write(path, data)
        return self.put(f"{result.run_id}-attempt-{result.attempt:03d}.json", data, "s07_result")

    def write_index(self) -> None:
        immutable_write(self.root / "artifact_index.json", json_bytes({
            "artifacts": [
                {"ref": ref, "object_path": f"objects/{ref['sha256']}",
                 "origins": self.origins.get(key, [])}
                for key, ref in sorted(self.refs.items())
            ],
            "result_hash_rule": "Result hashes live here, never inside the result being hashed.",
        }))
