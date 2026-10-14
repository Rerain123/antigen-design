"""Pydantic contracts shared by every T-01 mock tool."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "0.1.0"
WORKFLOW_VERSION = "T01-v10"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ExecutionMode(str, Enum):
    MOCK = "mock"
    SMOKE = "smoke"
    PRODUCTION = "production"


class StepStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    SKIPPED = "SKIPPED"
    DEGRADED = "DEGRADED"
    WAITING_USER = "WAITING_USER"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_USER = "WAITING_USER"
    SUCCEEDED = "SUCCEEDED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Outcome(str, Enum):
    VARIANT_HANDOFF = "VARIANT_HANDOFF"
    WT_DESIGN_SKIPPED = "WT_DESIGN_SKIPPED"
    WT_FAILURE_REPORT = "WT_FAILURE_REPORT"


class ErrorCategory(str, Enum):
    INPUT_VALIDATION = "INPUT_VALIDATION"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    EXECUTION = "EXECUTION"
    OUTPUT_MISSING = "OUTPUT_MISSING"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    SCIENTIFIC_GATE = "SCIENTIFIC_GATE"
    CANCELLED = "CANCELLED"
    INTERNAL = "INTERNAL"


class ArtifactRef(ContractModel):
    artifact_id: str = Field(min_length=1)
    logical_name: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    producer_step_id: str = Field(min_length=1)
    created_at: datetime
    resource_uri: str | None

    @field_validator("logical_name")
    @classmethod
    def logical_name_must_not_be_a_path(cls, value: str) -> str:
        if "/" in value or "\\" in value or re.match(r"^[A-Za-z]:", value):
            raise ValueError("logical_name must be a business filename, not a server path")
        return value

    @field_validator("resource_uri")
    @classmethod
    def resource_uri_must_not_leak_local_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        lowered = value.lower()
        if lowered.startswith(("file:", "/data/")) or re.match(r"^[A-Za-z]:[\\/]", value):
            raise ValueError("resource_uri must not expose a local server path")
        return value


class WarningItem(ContractModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class ToolError(ContractModel):
    code: str = Field(min_length=1)
    category: ErrorCategory
    retryable: bool
    message: str = Field(min_length=1)
    user_message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class Provenance(ContractModel):
    adapter_name: str
    adapter_version: str
    tool_name: str
    tool_version: str
    model_name: str | None
    model_version: str | None
    parameter_profile: str
    parameters: dict[str, Any]
    random_seed: int | None
    input_hashes: list[str]
    started_at: datetime
    finished_at: datetime
    exit_code: int | None
    compute_profile: str


class ExecutionMetrics(ContractModel):
    duration_ms: int = Field(ge=0)
    resource_summary: dict[str, Any] = Field(default_factory=dict)


class Progress(ContractModel):
    current: int = Field(ge=0)
    total: int = Field(gt=0)
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def current_not_above_total(self) -> "Progress":
        if self.current > self.total:
            raise ValueError("progress.current cannot exceed progress.total")
        return self


class StepRequest(ContractModel):
    schema_version: Literal["0.1.0"]
    workflow_version: Literal["T01-v10"]
    run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    scope: str = Field(min_length=1)
    execution_mode: ExecutionMode
    parameters: dict[str, Any]
    input_artifacts: list[ArtifactRef]
    context: dict[str, Any]
    idempotency_key: str = Field(min_length=1)


class StepResult(ContractModel):
    schema_version: Literal["0.1.0"]
    workflow_version: Literal["T01-v10"]
    run_id: str
    step_id: str
    node_id: str
    attempt: int = Field(ge=1)
    job_id: str | None
    status: StepStatus
    progress: Progress | None
    data: dict[str, Any] | None
    artifacts: list[ArtifactRef]
    quality_flags: list[str]
    warnings: list[WarningItem]
    error: ToolError | None
    provenance: Provenance
    metrics: ExecutionMetrics

    @model_validator(mode="after")
    def validate_state_shape(self) -> "StepResult":
        if self.status in {StepStatus.QUEUED, StepStatus.RUNNING}:
            if self.job_id is None or self.progress is None:
                raise ValueError("QUEUED/RUNNING results require job_id and progress")
        elif self.progress is not None:
            raise ValueError("terminal results must have progress=null")

        if self.status in {StepStatus.FAILED, StepStatus.CANCELLED}:
            if self.error is None:
                raise ValueError("FAILED/CANCELLED results require error")
        elif self.error is not None:
            raise ValueError("non-error results must have error=null")
        return self


class ContextScores(ContractModel):
    injection_confidence: Literal["HIGH", "NON_HIGH"]
    sequence_level: dict[str, ArtifactRef | None]
    structure_level: dict[str, ArtifactRef | None]


class T01Input(ContractModel):
    protein_sequence: str = Field(min_length=1)
    host: str = Field(min_length=1)
    pathogen_type: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    epitope_mode: Literal["both", "bcell_only", "tcell_only"]
    epitope_policy: str | dict[str, Any]
    regions_permissions: list[dict[str, Any]] | None = None
    md_validation: bool
    membrane_design_confirm: bool
    low_conf_design_confirm: bool
    context_scores: ContextScores | None = None
    mhc_alleles: list[str] | None = None
    expression_host: str | None = None
    request_visualization: bool = False
    execution_mode: ExecutionMode
    client_request_id: str = Field(min_length=1)

    @field_validator("protein_sequence")
    @classmethod
    def validate_sequence_text(cls, value: str) -> str:
        if value != value.strip() or not re.fullmatch(r"[A-Za-z]+", value):
            raise ValueError("protein_sequence must contain letters only and no surrounding whitespace")
        return value.upper()


class ConfigureRunRequest(ContractModel):
    run_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    input: T01Input | None = None


class RunRecord(ContractModel):
    run_id: str
    scenario_id: str
    status: RunStatus
    outcome: Outcome | None
    input: T01Input | None
    created_at: datetime
    updated_at: datetime


class JobLookupRequest(ContractModel):
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)


class JobCancelRequest(JobLookupRequest):
    reason: str = Field(min_length=1)
