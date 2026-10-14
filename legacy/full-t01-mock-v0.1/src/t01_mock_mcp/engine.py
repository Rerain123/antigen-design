"""Deterministic scenario engine for the T-01 Mock MCP server.

This module deliberately performs no scientific computation.  It implements
only contract validation, routing rules explicitly stated in the reviewed v10
documents, deterministic fixtures, idempotency, and mock job transitions.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .catalog import FAULT_SCENARIOS, FAULT_TOOL, SCENARIOS, STEP_TOOLS
from .contracts import (
    ArtifactRef,
    ErrorCategory,
    ExecutionMetrics,
    ExecutionMode,
    Outcome,
    Progress,
    Provenance,
    RunStatus,
    StepRequest,
    StepResult,
    StepStatus,
    T01Input,
    ToolError,
    WarningItem,
)
from .store import IdempotencyConflict, SQLiteStore


@dataclass(slots=True)
class ToolOutcome:
    status: StepStatus = StepStatus.SUCCEEDED
    data: dict[str, Any] | None = None
    artifacts: list[ArtifactRef] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=lambda: ["MOCK_DATA"])
    warnings: list[WarningItem] = field(default_factory=list)
    error: ToolError | None = None
    exit_code: int | None = 0


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _warning(code: str, message: str, **details: Any) -> WarningItem:
    return WarningItem(code=code, message=message, details=details)


def _error(
    code: str,
    category: ErrorCategory,
    *,
    retryable: bool,
    message: str,
    user_message: str,
    **details: Any,
) -> ToolError:
    return ToolError(
        code=code,
        category=category,
        retryable=retryable,
        message=message,
        user_message=user_message,
        details=details,
    )


class MockEngine:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def execute(self, tool_name: str, request: StepRequest) -> StepResult:
        if tool_name not in STEP_TOOLS:
            raise KeyError(f"unknown T-01 tool: {tool_name}")

        request_hash = _sha256(request.model_dump(mode="json"))
        started = _utc_now()
        started_ns = time.perf_counter_ns()

        try:
            cached = self.store.get_idempotent_result(
                request.idempotency_key, tool_name, request_hash
            )
        except IdempotencyConflict:
            return self._result(
                tool_name,
                request,
                ToolOutcome(
                    status=StepStatus.FAILED,
                    quality_flags=["MOCK_DATA"],
                    error=_error(
                        "IDEMPOTENCY_KEY_CONFLICT",
                        ErrorCategory.INPUT_VALIDATION,
                        retryable=False,
                        message="The idempotency key was already used for different work.",
                        user_message="检测到重复请求标识冲突，请生成新的请求标识后重试。",
                        idempotency_key=request.idempotency_key,
                    ),
                    exit_code=None,
                ),
                started,
                started_ns,
            )
        if cached is not None:
            return cached

        run = self.store.ensure_run(request.run_id, "MOCK-HAPPY-PATH")
        scenario_id = run.scenario_id

        if request.execution_mode != ExecutionMode.MOCK:
            outcome = ToolOutcome(
                status=StepStatus.FAILED,
                error=_error(
                    "MOCK_SERVER_MODE_MISMATCH",
                    ErrorCategory.INPUT_VALIDATION,
                    retryable=False,
                    message="This server accepts execution_mode=mock only.",
                    user_message="当前连接的是 Mock 服务，不能用于冒烟或生产计算。",
                    received=request.execution_mode.value,
                ),
                exit_code=None,
            )
        elif scenario_id not in SCENARIOS:
            outcome = ToolOutcome(
                status=StepStatus.FAILED,
                error=_error(
                    "UNKNOWN_MOCK_SCENARIO",
                    ErrorCategory.INPUT_VALIDATION,
                    retryable=False,
                    message=f"Unknown mock scenario: {scenario_id}",
                    user_message="未找到指定的 Mock 场景。",
                    scenario_id=scenario_id,
                ),
                exit_code=None,
            )
        elif scenario_id in FAULT_SCENARIOS and tool_name == FAULT_TOOL:
            outcome = self._fault_outcome(scenario_id)
        else:
            outcome = self._dispatch(tool_name, request, run.input, scenario_id)

        result = self._result(tool_name, request, outcome, started, started_ns)

        if request.parameters.get("_mock_async") is True and result.status in {
            StepStatus.SUCCEEDED,
            StepStatus.DEGRADED,
            StepStatus.SKIPPED,
        }:
            result = self._queue_result(tool_name, request, result)

        self.store.save_idempotent_result(
            idempotency_key=request.idempotency_key,
            run_id=request.run_id,
            tool_name=tool_name,
            request_hash=request_hash,
            result=result,
        )
        self._update_run(tool_name, result)
        return result

    def _dispatch(
        self,
        tool_name: str,
        request: StepRequest,
        run_input: T01Input | None,
        scenario_id: str,
    ) -> ToolOutcome:
        handlers = {
            "t01.validate_request": self._validate_request,
            "t01.evaluate_length_guard": self._length_guard,
            "t01.route_context_scores": self._route_context,
            "t01.inject_context_scores": self._inject_context,
            "t01.prepare_permission_inputs": self._prepare_permission_inputs,
            "t01.evaluate_mutable_length": self._evaluate_mutable_length,
            "t01.build_evidence_bundle": self._build_evidence_bundle,
            "structure.fetch": self._fetch_structure,
            "t01.route_existing_structure": self._route_existing_structure,
            "structure.assess_quality": self._assess_structure_quality,
            "topology.predict": self._predict_topology,
            "t01.route_rsa": self._route_rsa,
            "t01.route_pathogen_type": self._route_pathogen_type,
            "localization.predict_bacteria": self._predict_bacterial_localization,
            "epitope.synthesize_maps": self._synthesize_epitope_maps,
            "safety.assess_triple": self._assess_safety,
            "conservation.collect_homologs": self._collect_homologs,
            "conservation.extract_regions": self._extract_conserved_regions,
            "conservation.analyze_within_type": self._analyze_within_type,
            "domain.identify": self._identify_domains,
            "developability.assess": self._assess_developability,
            "t01.evaluate_design_applicability": self._design_applicability,
            "t01.route_stability_rescue": self._route_stability_rescue,
            "stability.screen_rescue_top3": self._screen_rescue,
            "design.generate_mutations": self._generate_mutations,
            "design.validate": self._validate_designs,
            "t01.evaluate_design_retry": self._route_design_retry,
            "epitope.validate_presentation": self._validate_epitope_presentation,
            "t01.select_stability_score_pool": self._select_score_pool,
            "ranking.rank_variants": self._rank_variants,
            "sequence.optimize_codons": self._optimize_codons,
            "t01.evaluate_md_gate": self._route_md,
            "output.assemble_candidate_json": self._assemble_candidate_json,
            "t01.route_visualization": self._route_visualization,
            "output.prepare_explanation": self._prepare_explanation,
            "t01.route_handoff": self._route_handoff,
            "handoff.deliver_agent_c": self._deliver_handoff,
        }
        handler = handlers.get(tool_name)
        if handler is not None:
            return handler(request, run_input, scenario_id)
        return self._generic_fixture(tool_name, request, scenario_id)

    @staticmethod
    def _parameter(
        request: StepRequest,
        run_input: T01Input | None,
        name: str,
        default: Any = None,
    ) -> Any:
        if name in request.parameters:
            return request.parameters[name]
        if name in request.context:
            return request.context[name]
        if run_input is not None and hasattr(run_input, name):
            return getattr(run_input, name)
        return default

    def _validate_request(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        candidate = run_input
        if candidate is None:
            try:
                payload = {key: value for key, value in request.parameters.items() if not key.startswith("_mock_")}
                candidate = T01Input.model_validate(payload)
            except ValidationError as exc:
                return ToolOutcome(
                    status=StepStatus.FAILED,
                    data={"mock_data": True, "scenario_id": scenario_id, "valid": False},
                    error=_error(
                        "T01_INPUT_INVALID",
                        ErrorCategory.INPUT_VALIDATION,
                        retryable=False,
                        message="T-01 input failed schema validation.",
                        user_message="输入信息不完整或格式不正确，请检查后重试。",
                        validation_errors=exc.errors(include_url=False),
                    ),
                    exit_code=None,
                )

        needs_mhc = candidate.epitope_mode in {"both", "tcell_only"}
        approved_panel = bool(request.context.get("approved_mhc_panel"))
        if needs_mhc and not candidate.mhc_alleles and not approved_panel:
            return ToolOutcome(
                status=StepStatus.WAITING_USER,
                data={
                    "mock_data": True,
                    "scenario_id": scenario_id,
                    "valid": False,
                    "route": "INPUT_REQUIRED",
                    "required_field": "mhc_alleles",
                },
                warnings=[
                    _warning(
                        "MHC_ALLELES_REQUIRED",
                        "T-cell analysis requires mhc_alleles or a server-approved panel.",
                    )
                ],
            )
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "valid": True,
                "sequence_length": len(candidate.protein_sequence),
                "needs_mhc": needs_mhc,
            }
        )

    def _length_guard(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        sequence = self._parameter(request, run_input, "protein_sequence", "")
        epitope_mode = self._parameter(request, run_input, "epitope_mode", "both")
        if scenario_id == "MOCK-SHORT-MHC-HALT":
            sequence, epitope_mode = "ACDEFGHI", "both"
        elif scenario_id == "MOCK-SHORT-WARNING":
            sequence, epitope_mode = "ACDEFGHIKLMNPQRSTVWY", "bcell_only"
        length = len(sequence)
        needs_mhc = epitope_mode in {"both", "tcell_only"}
        base = {
            "mock_data": True,
            "scenario_id": scenario_id,
            "sequence_length": length,
            "needs_mhc": needs_mhc,
        }
        if length < 9 and needs_mhc:
            return ToolOutcome(
                status=StepStatus.FAILED,
                data={**base, "route": "HALT", "branch_taken": "G-LENGTH-HALT"},
                error=_error(
                    "SEQUENCE_TOO_SHORT_FOR_MHC",
                    ErrorCategory.SCIENTIFIC_GATE,
                    retryable=False,
                    message="Sequence length is below 9 aa while T-cell/MHC analysis is required.",
                    user_message="序列长度不足 9 aa，无法执行所需的 MHC 分析，流程已停止。",
                    sequence_length=length,
                    epitope_mode=epitope_mode,
                ),
                exit_code=None,
            )
        if length < 30:
            return ToolOutcome(
                status=StepStatus.DEGRADED,
                data={**base, "route": "WARNING", "branch_taken": "G-LENGTH-WARN"},
                quality_flags=["MOCK_DATA", "SHORT_SEQUENCE_WARNING"],
                warnings=[
                    _warning(
                        "SEQUENCE_SHORTER_THAN_30_AA",
                        "Sequence is shorter than 30 aa; the workflow continues with a warning.",
                        sequence_length=length,
                    )
                ],
            )
        return ToolOutcome(data={**base, "route": "PASS", "branch_taken": "PASS"})

    def _route_context(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        context_scores = self._parameter(request, run_input, "context_scores")
        if scenario_id == "MOCK-CONTEXT-HIGH":
            confidence = "HIGH"
        elif scenario_id == "MOCK-CONTEXT-NONHIGH":
            confidence = "NON_HIGH"
        elif context_scores is None:
            confidence = None
        elif hasattr(context_scores, "injection_confidence"):
            confidence = context_scores.injection_confidence
        else:
            confidence = context_scores.get("injection_confidence")
        route = "NONE" if confidence is None else confidence
        next_target = {"NONE": "S-07", "HIGH": "step15", "NON_HIGH": "step12"}[route]
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "route": route,
                "branch_taken": f"G-CONTEXT-{route}",
                "after_s16_target": next_target,
                "must_run_s16": route != "NONE",
            }
        )

    def _inject_context(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        context_scores = self._parameter(request, run_input, "context_scores")
        confidence = None
        if context_scores is not None:
            confidence = (
                context_scores.injection_confidence
                if hasattr(context_scores, "injection_confidence")
                else context_scores.get("injection_confidence")
            )
        if scenario_id == "MOCK-CONTEXT-HIGH":
            confidence = "HIGH"
        elif scenario_id == "MOCK-CONTEXT-NONHIGH":
            confidence = "NON_HIGH"
        if confidence not in {"HIGH", "NON_HIGH"}:
            return ToolOutcome(
                status=StepStatus.FAILED,
                data={"mock_data": True, "scenario_id": scenario_id, "injected": False},
                error=_error(
                    "CONTEXT_SCORES_MISSING",
                    ErrorCategory.INPUT_VALIDATION,
                    retryable=False,
                    message="Context injection requires injection_confidence HIGH or NON_HIGH.",
                    user_message="缺少可用的上下文注入数据。",
                ),
                exit_code=None,
            )
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "injected": True,
                "injection_confidence": confidence,
                "next_step": "S-16",
                "after_s16_target": "step15" if confidence == "HIGH" else "step12",
                "input_artifact_hashes": [item.sha256 for item in request.input_artifacts],
            }
        )

    def _prepare_permission_inputs(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "fixed_input": request.parameters.get("fixed_input", []),
                "fixed": request.parameters.get("fixed", []),
                "degraded_regions": request.parameters.get("degraded_regions", []),
                "epitope_evidence": request.parameters.get("epitope_evidence"),
            }
        )

    def _evaluate_mutable_length(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "mutable_length": request.parameters.get("mutable_length"),
                "route": request.parameters.get("route", "SOP_PENDING"),
            },
            quality_flags=["MOCK_DATA", "MUTABLE_LENGTH_ROUTING_SOP_PENDING"],
        )

    def _build_evidence_bundle(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        supplied = request.parameters.get("evidence_bundle", {})
        keys = (
            "fixed_input",
            "domains_input",
            "core_map",
            "epitope_evidence",
            "degraded_regions",
            "user_regions",
        )
        bundle = {key: supplied.get(key) for key in keys}
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "evidence_bundle": bundle,
                "bundle_keys_complete": set(bundle) == set(keys),
            }
        )

    def _fetch_structure(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        found = scenario_id != "MOCK-NO-STRUCTURE"
        data = {
            "mock_data": True,
            "scenario_id": scenario_id,
            "structure_found": found,
            "result": "mock_structure" if found else "no_structure",
        }
        artifacts = [self._artifact("structure.fetch", request, "structure.json")] if found else []
        return ToolOutcome(data=data, artifacts=artifacts)

    def _route_existing_structure(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        found = bool(request.parameters.get("structure_found", scenario_id != "MOCK-NO-STRUCTURE"))
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "structure_found": found,
                "route": "S-09" if found else "S-08",
                "branch_taken": "HAS_STRUCTURE" if found else "NO_STRUCTURE",
            }
        )

    def _assess_structure_quality(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        confidence = request.parameters.get("confidence")
        if confidence is None:
            confidence = "low" if scenario_id == "MOCK-LOW-STRUCTURE" else "high"
        return ToolOutcome(
            data={"mock_data": True, "scenario_id": scenario_id, "confidence": confidence}
        )

    def _predict_topology(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        is_membrane = scenario_id in {"MOCK-MEMBRANE-SKIP", "MOCK-MEMBRANE-CONFIRMED"}
        is_membrane = bool(request.parameters.get("is_membrane", is_membrane))
        tm_count = int(request.parameters.get("tm_count", 1 if is_membrane else 0))
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "is_membrane": is_membrane,
                "tm_count": tm_count,
            }
        )

    def _route_rsa(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        confidence = request.parameters.get(
            "confidence", "low" if scenario_id == "MOCK-LOW-STRUCTURE" else "high"
        )
        if confidence == "low":
            return ToolOutcome(
                status=StepStatus.SKIPPED,
                data={
                    "mock_data": True,
                    "scenario_id": scenario_id,
                    "route": "SKIP_S11",
                    "rsa": None,
                    "branch_taken": "G-STRUCTURE-LOW",
                },
                quality_flags=["MOCK_DATA", "RSA_SKIPPED_LOW_STRUCTURE_CONFIDENCE"],
            )
        return ToolOutcome(
            data={"mock_data": True, "scenario_id": scenario_id, "route": "RUN_S11"}
        )

    def _route_pathogen_type(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        pathogen_type = self._parameter(request, run_input, "pathogen_type", "other")
        if scenario_id == "MOCK-BACTERIA":
            pathogen_type = "bacteria"
        run_s06 = pathogen_type == "bacteria"
        return ToolOutcome(
            status=StepStatus.SUCCEEDED if run_s06 else StepStatus.SKIPPED,
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "pathogen_type": pathogen_type,
                "route": "RUN_S06" if run_s06 else "SKIP_S06",
                "branch_taken": "G-BACTERIA" if run_s06 else "NON_BACTERIA",
            },
        )

    def _predict_bacterial_localization(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "psortb_flag": "MOCK_LOCALIZATION_FLAG",
                "scientific_value_available": False,
            }
        )

    def _synthesize_epitope_maps(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        empty_map = {"mock_data": True, "positions": []}
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "epitope_evidence": {
                    "b_cell_epitope_map": empty_map,
                    "t_cell_presentation_map": empty_map,
                    "b_cell_antigenic_hotspot_map": empty_map,
                    "evidence_levels": ["E0", "E1", "E2", "E3", "E4"],
                    "weight_mapping": None,
                    "weight_mapping_status": "SOP_PENDING",
                },
            },
            artifacts=[self._artifact("epitope.synthesize_maps", request, "epitope_maps.json")],
            quality_flags=["MOCK_DATA", "EPITOPE_WEIGHT_MAPPING_SOP_PENDING"],
        )

    def _assess_safety(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        variant_failure = scenario_id == "MOCK-VARIANT-SAFETY-FAIL" and request.scope == "variant"
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "scope": request.scope,
                "assessment": "NON_PASS" if variant_failure else "PASS",
                "safety_excluded": variant_failure,
                "host_similarity_flag": "MOCK_NON_PASS" if variant_failure else "MOCK_PASS",
            },
            quality_flags=["MOCK_DATA"] + (["VARIANT_SAFETY_EXCLUDED"] if variant_failure else []),
        )

    def _collect_homologs(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        confidence = request.parameters.get("conservation_confidence", "HIGH")
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "conservation_confidence": confidence,
                "homologs": [],
            }
        )

    def _extract_conserved_regions(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        mode = request.parameters.get("mode", "standard")
        if mode not in {"standard", "relaxed", "minimal", "failed"}:
            return ToolOutcome(
                status=StepStatus.FAILED,
                error=_error(
                    "INVALID_CONSERVATION_REGION_MODE",
                    ErrorCategory.OUTPUT_INVALID,
                    retryable=False,
                    message="Conservation region mode is outside the documented enum.",
                    user_message="保守区结果格式不符合约定。",
                    received=mode,
                ),
                exit_code=0,
            )
        return ToolOutcome(
            data={"mock_data": True, "scenario_id": scenario_id, "mode": mode, "regions": []}
        )

    def _analyze_within_type(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        confidence = request.parameters.get("conservation_confidence", "HIGH")
        degraded = confidence == "LOW"
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "conservation_confidence": confidence,
                "conserved_confidence_degraded": degraded,
            },
            quality_flags=["MOCK_DATA"] + (["CONSERVED_CONFIDENCE_DEGRADED"] if degraded else []),
        )

    def _identify_domains(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "domains": [],
                "disulfides": [],
                "oligomer_interfaces": [],
                "core_map": {
                    "component_count": 4,
                    "components": None,
                    "component_names_status": "SOP_PENDING",
                },
            },
            quality_flags=["MOCK_DATA", "CORE_MAP_COMPONENT_NAMES_SOP_PENDING"],
        )

    def _assess_developability(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        classification = request.parameters.get("classification")
        if classification is None:
            classification = "poor" if scenario_id.startswith("MOCK-POOR-RESCUE") else "acceptable"
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "classification": classification,
                "scores": None,
                "scientific_values_available": False,
            }
        )

    def _design_applicability(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        is_membrane = bool(request.parameters.get("is_membrane", False))
        confidence = request.parameters.get("confidence", "high")
        membrane_confirm = bool(
            self._parameter(request, run_input, "membrane_design_confirm", False)
        )
        low_confirm = bool(self._parameter(request, run_input, "low_conf_design_confirm", False))
        if scenario_id == "MOCK-MEMBRANE-SKIP":
            is_membrane, membrane_confirm = True, False
        elif scenario_id == "MOCK-MEMBRANE-CONFIRMED":
            is_membrane, membrane_confirm = True, True
        elif scenario_id == "MOCK-LOW-STRUCTURE":
            confidence = "low"

        flags = ["MOCK_DATA"]
        if is_membrane and not membrane_confirm:
            flags.append("MEMBRANE_EXPECTED_POOR")
            return ToolOutcome(
                status=StepStatus.SKIPPED,
                data={
                    "mock_data": True,
                    "scenario_id": scenario_id,
                    "route": "DESIGN_SKIPPED",
                    "reason": "MEMBRANE_CONFIRMATION_REQUIRED",
                    "handoff": "WT",
                    "suggested_workflow": "T-11",
                },
                quality_flags=flags,
            )
        if confidence == "low" and not low_confirm:
            flags.append("SKIPPED_LOW_CONFIDENCE")
            return ToolOutcome(
                status=StepStatus.SKIPPED,
                data={
                    "mock_data": True,
                    "scenario_id": scenario_id,
                    "route": "DESIGN_SKIPPED",
                    "reason": "LOW_CONFIDENCE_CONFIRMATION_REQUIRED",
                    "handoff": "WT",
                },
                quality_flags=flags,
            )
        if is_membrane:
            flags.append("MEMBRANE_DESIGN_EXPLICITLY_CONFIRMED")
        if confidence == "low":
            flags.append("LOW_CONFIDENCE_DESIGN_EXPLICITLY_CONFIRMED")
        return ToolOutcome(
            data={"mock_data": True, "scenario_id": scenario_id, "route": "CONTINUE"},
            quality_flags=flags,
        )

    def _route_stability_rescue(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        classification = request.parameters.get(
            "classification", "poor" if scenario_id.startswith("MOCK-POOR-RESCUE") else "acceptable"
        )
        is_membrane = bool(request.parameters.get("is_membrane", False))
        should_run = classification == "poor" and not is_membrane
        return ToolOutcome(
            status=StepStatus.SUCCEEDED if should_run else StepStatus.SKIPPED,
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "route": "RUN_BRANCH4" if should_run else "SKIP_BRANCH4",
                "branch_taken": "G-BRANCH4" if should_run else "NO_RESCUE",
                "classification": classification,
                "is_membrane": is_membrane,
            },
        )

    def _screen_rescue(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        success = scenario_id != "MOCK-POOR-RESCUE-FAIL"
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "rescue_success": success,
                "continue_to": "EBB",
                "screened_count": 3,
            },
            quality_flags=["MOCK_DATA"] + (["STABILITY_RESCUE_FAILED_CONTINUE_EBB"] if not success else []),
        )

    def _generate_mutations(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        count = int(request.parameters.get("design_count", {1: 32, 2: 48, 3: 64}.get(request.attempt, 32)))
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "generated_count": count,
                "design_permissions_applied": True,
                "variants": [],
                "scientific_sequences_available": False,
            }
        )

    def _validate_designs(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        passed = int(request.parameters.get("passed_count", 8))
        if scenario_id == "MOCK-DESIGN-RETRY-48":
            passed = 0 if request.attempt == 1 else 8
        elif scenario_id == "MOCK-DESIGN-RETRY-64":
            passed = 0 if request.attempt in {1, 2} else 8
        elif scenario_id == "MOCK-DESIGN-ALL-REJECTED":
            passed = 0
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "passed_count": passed,
                "all_rejected": passed == 0,
                "passed_variants": [],
                "mutation_burden": None,
            }
        )

    def _route_design_retry(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        passed_count = int(request.parameters.get("passed_count", 0))
        if passed_count > 0:
            route, next_count = "CONTINUE", None
        elif request.attempt == 1:
            route, next_count = "RETRY", 48
        elif request.attempt == 2:
            route, next_count = "RETRY", 64
        else:
            route, next_count = "EXHAUSTED", None
        flags = ["MOCK_DATA"] + (["DESIGN_ALL_REJECTED"] if route == "EXHAUSTED" else [])
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "route": route,
                "current_attempt": request.attempt,
                "next_design_count": next_count,
                "max_attempts": 3,
                "design_all_rejected": route == "EXHAUSTED",
            },
            quality_flags=flags,
        )

    def _validate_epitope_presentation(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        structural: bool | None = True
        prediction: bool | None = True
        epitope_violation = False
        soft_penalty = False
        if request.parameters.get("structure_available") is False:
            structural = prediction = None
        elif scenario_id == "MOCK-EPITOPE-STRUCTURAL-FAIL":
            structural, epitope_violation = False, True
        elif scenario_id == "MOCK-EPITOPE-PREDICTION-FAIL":
            prediction, soft_penalty = False, True
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "layers": {
                    "L1_identity": True,
                    "L2_L3_structural": structural,
                    "L4_prediction": prediction,
                },
                "epitope_violation": epitope_violation,
                "soft_penalty": soft_penalty,
            },
            quality_flags=["MOCK_DATA"]
            + (["EPITOPE_STRUCTURAL_HARD_EXCLUSION"] if epitope_violation else [])
            + (["EPITOPE_PREDICTION_SOFT_PENALTY"] if soft_penalty else []),
        )

    def _select_score_pool(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        confidence = request.parameters.get("confidence", "high")
        is_membrane = bool(request.parameters.get("is_membrane", False))
        candidates = request.parameters.get("candidates", [{"candidate_id": "MOCK-VAR-001"}])
        if scenario_id == "MOCK-19B-SKIPPED":
            candidates = []
        should_run = confidence != "low" and not is_membrane and bool(candidates)
        selected = candidates[:40] if should_run else []
        return ToolOutcome(
            status=StepStatus.SUCCEEDED if should_run else StepStatus.SKIPPED,
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "route": "RUN_S31_VARIANT" if should_run else "SKIP_S31_VARIANT",
                "score_pool": selected,
                "score_pool_size": len(selected),
                "selection_rule": "preordered_overall_top40",
            },
        )

    def _rank_variants(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        all_rejected = scenario_id == "MOCK-DESIGN-ALL-REJECTED"
        sc10_warning = scenario_id == "MOCK-SC10-WARNING"
        best = None if all_rejected else {
            "candidate_id": "MOCK-VAR-001",
            "overall": 0.25 if sc10_warning else None,
            "mock_data": True,
        }
        warnings: list[WarningItem] = []
        flags = ["MOCK_DATA"]
        if sc10_warning:
            warnings.append(
                _warning(
                    "SC10_OVERALL_BELOW_0_30",
                    "Mock best.overall is below 0.30; final downgrade choice still requires SOP.",
                    overall=0.25,
                )
            )
            flags.extend(["SC10_WARNING", "SC10_DOWNGRADE_RULE_SOP_PENDING"])
        if all_rejected:
            flags.append("DESIGN_ALL_REJECTED")
        return ToolOutcome(
            status=StepStatus.DEGRADED if sc10_warning else StepStatus.SUCCEEDED,
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "best_candidate": best,
                "top20_variants": [] if all_rejected else [best],
                "failure_report": {"reason": "ALL_DESIGNS_REJECTED", "mock_data": True}
                if all_rejected
                else None,
                "ranking_order": [
                    "hard_filter",
                    "pareto_front",
                    "objective_profile",
                    "family_quota_5",
                    "identity_cluster_gt_95_pct",
                    "SC-10",
                ],
            },
            warnings=warnings,
            quality_flags=flags,
        )

    def _optimize_codons(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        expression_host = self._parameter(request, run_input, "expression_host")
        is_membrane_skip = scenario_id == "MOCK-MEMBRANE-SKIP" or bool(
            request.parameters.get("membrane_design_skipped", False)
        )
        should_run = bool(expression_host) and not is_membrane_skip
        return ToolOutcome(
            status=StepStatus.SUCCEEDED if should_run else StepStatus.SKIPPED,
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "route": "RUN_S30" if should_run else "SKIP_S30",
                "expression_host": expression_host,
                "dna": None,
                "scientific_sequence_available": False,
            },
        )

    def _route_md(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        objective = self._parameter(request, run_input, "objective", "other")
        md_validation = bool(self._parameter(request, run_input, "md_validation", False))
        is_membrane = bool(request.parameters.get("is_membrane", False))
        ddg_available = bool(request.parameters.get("ddg_available", False))
        if scenario_id == "MOCK-MD-RUN":
            objective, is_membrane, ddg_available = "thermostability", False, True
        elif scenario_id == "MOCK-MD-SKIP":
            objective, md_validation, is_membrane, ddg_available = "other", False, False, False
        requested = objective == "thermostability" or md_validation
        should_run = requested and not is_membrane and ddg_available
        reasons = {
            "requested": requested,
            "non_membrane": not is_membrane,
            "ddg_available": ddg_available,
        }
        return ToolOutcome(
            status=StepStatus.SUCCEEDED if should_run else StepStatus.SKIPPED,
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "route": "RUN_S32" if should_run else "SKIP_S32",
                "branch_taken": "G-MD" if should_run else "MD_NOT_APPLICABLE",
                "conditions": reasons,
                "candidate_scope": "top3" if should_run else None,
            },
        )

    def _assemble_candidate_json(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        design_skipped = scenario_id in {"MOCK-MEMBRANE-SKIP", "MOCK-LOW-STRUCTURE"}
        all_rejected = scenario_id == "MOCK-DESIGN-ALL-REJECTED"
        best = None if design_skipped or all_rejected else {
            "candidate_id": "MOCK-VAR-001",
            "mock_data": True,
            "scientific_fields_status": "SOP_PENDING",
        }
        candidate = {
            "best_candidate": best,
            "top20_variants": [] if best is None else [best],
            "delta_table": [],
            "design_permissions": request.parameters.get("design_permissions", []),
            "evidence_provenance": {"mock_data": True},
            "quality_flags": ["MOCK_DATA", "CANDIDATE_INTERNAL_SCHEMA_SOP_PENDING"],
            "warnings": [],
            "design_skipped": design_skipped,
            "failure_report": {"reason": "ALL_DESIGNS_REJECTED", "mock_data": True}
            if all_rejected
            else None,
            "artifacts": [],
            "dna": None,
            "execution_mode": "mock",
        }
        return ToolOutcome(
            data={"mock_data": True, "scenario_id": scenario_id, "candidate": candidate},
            artifacts=[self._artifact("output.assemble_candidate_json", request, "candidate.json")],
            quality_flags=["MOCK_DATA", "CANDIDATE_INTERNAL_SCHEMA_SOP_PENDING"],
        )

    def _route_visualization(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        requested = bool(self._parameter(request, run_input, "request_visualization", False))
        return ToolOutcome(
            status=StepStatus.SUCCEEDED if requested else StepStatus.SKIPPED,
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "route": "RUN_C29_C30" if requested else "SKIP_C29_C30",
            },
        )

    def _prepare_explanation(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "fact_summary": {
                    "execution_mode": "mock",
                    "statement": "No scientific computation was performed; values are contract fixtures.",
                    "llm_may_calculate": False,
                },
            }
        )

    def _route_handoff(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        design_skipped = bool(request.parameters.get("design_skipped", False))
        failure_report = request.parameters.get("failure_report")
        best = request.parameters.get("best_candidate")
        if scenario_id in {"MOCK-MEMBRANE-SKIP", "MOCK-LOW-STRUCTURE"}:
            design_skipped = True
        elif scenario_id == "MOCK-DESIGN-ALL-REJECTED":
            failure_report = {"reason": "ALL_DESIGNS_REJECTED", "mock_data": True}
        elif best is None:
            best = {"candidate_id": "MOCK-VAR-001", "mock_data": True}

        if best is not None and not design_skipped and failure_report is None:
            outcome = Outcome.VARIANT_HANDOFF
            route = "BEST"
        elif design_skipped:
            outcome = Outcome.WT_DESIGN_SKIPPED
            route = "DESIGN_SKIPPED"
        else:
            outcome = Outcome.WT_FAILURE_REPORT
            route = "DESIGN_ALL_REJECTED"
        status = StepStatus.SUCCEEDED if outcome == Outcome.VARIANT_HANDOFF else StepStatus.DEGRADED
        flags = ["MOCK_DATA"]
        if outcome != Outcome.VARIANT_HANDOFF:
            flags.append(outcome.value)
        return ToolOutcome(
            status=status,
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "route": route,
                "outcome": outcome.value,
                "handoff_payload": "VARIANT" if outcome == Outcome.VARIANT_HANDOFF else "WT",
            },
            quality_flags=flags,
        )

    def _deliver_handoff(
        self, request: StepRequest, run_input: T01Input | None, scenario_id: str
    ) -> ToolOutcome:
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "delivered": False,
                "delivery_status": "MOCK_TARGET_INTERFACE_UNDEFINED",
            },
            quality_flags=["MOCK_DATA", "AGENT_C_TARGET_INTERFACE_PENDING"],
            warnings=[
                _warning(
                    "AGENT_C_TARGET_INTERFACE_PENDING",
                    "S-44 delivery is mocked because the target interface is not defined.",
                )
            ],
        )

    def _generic_fixture(
        self, tool_name: str, request: StepRequest, scenario_id: str
    ) -> ToolOutcome:
        artifact_tools = {
            "structure.predict": "predicted_structure.json",
            "structure.compute_rsa": "rsa.json",
            "conservation.compute": "conservation.json",
            "design.generate_mutations": "designs.json",
            "design.validate": "validated_designs.json",
            "variant.reassess_developability": "variant_assessment.json",
            "stability.scan_mutations": "stability_scan.json",
            "stability.score_variants": "variant_ddg.json",
            "dynamics.run_md_validation": "md_validation.json",
            "output.render_comparison_report": "comparison_report.json",
            "handoff.assemble_agent_c": "agent_c_handoff.json",
        }
        artifacts = []
        if tool_name in artifact_tools:
            artifacts.append(self._artifact(tool_name, request, artifact_tools[tool_name]))
        return ToolOutcome(
            data={
                "mock_data": True,
                "scenario_id": scenario_id,
                "tool_name": tool_name,
                "scientific_computation_performed": False,
                "fixture": {},
            },
            artifacts=artifacts,
        )

    @staticmethod
    def _fault_outcome(scenario_id: str) -> ToolOutcome:
        if scenario_id == "MOCK-TOOL-TIMEOUT":
            return ToolOutcome(
                status=StepStatus.FAILED,
                data={"mock_data": True, "scenario_id": scenario_id},
                error=_error(
                    "TOOL_TIMEOUT",
                    ErrorCategory.TIMEOUT,
                    retryable=True,
                    message="Mock scientific tool exceeded its execution deadline.",
                    user_message="计算工具超时，可按策略重试。",
                    fault_tool=FAULT_TOOL,
                ),
                exit_code=None,
            )
        if scenario_id == "MOCK-OUTPUT-MISSING":
            return ToolOutcome(
                status=StepStatus.FAILED,
                data={"mock_data": True, "scenario_id": scenario_id},
                error=_error(
                    "EXPECTED_OUTPUT_MISSING",
                    ErrorCategory.OUTPUT_MISSING,
                    retryable=True,
                    message="Mock process returned exit_code=0 but expected output was absent.",
                    user_message="工具未生成预期结果，不能视为计算成功。",
                    fault_tool=FAULT_TOOL,
                ),
                exit_code=0,
            )
        return ToolOutcome(
            status=StepStatus.FAILED,
            data={"mock_data": True, "scenario_id": scenario_id},
            error=_error(
                "OUTPUT_PARSE_FAILED",
                ErrorCategory.OUTPUT_INVALID,
                retryable=False,
                message="Mock output existed but failed contract parsing.",
                user_message="工具结果存在但格式无效，已阻止错误数据进入后续流程。",
                fault_tool=FAULT_TOOL,
            ),
            exit_code=0,
        )

    def _result(
        self,
        tool_name: str,
        request: StepRequest,
        outcome: ToolOutcome,
        started: datetime,
        started_ns: int,
    ) -> StepResult:
        finished = _utc_now()
        duration_ms = max(0, (time.perf_counter_ns() - started_ns) // 1_000_000)
        provenance = Provenance(
            adapter_name="t01_mock_adapter",
            adapter_version="0.1.0",
            tool_name=tool_name,
            tool_version="mock-0.1.0",
            model_name=None,
            model_version=None,
            parameter_profile="deterministic-fixture",
            parameters=request.parameters,
            random_seed=0,
            input_hashes=[artifact.sha256 for artifact in request.input_artifacts],
            started_at=started,
            finished_at=finished,
            exit_code=outcome.exit_code,
            compute_profile="mock-no-scientific-compute",
        )
        return StepResult(
            schema_version=request.schema_version,
            workflow_version=request.workflow_version,
            run_id=request.run_id,
            step_id=request.step_id,
            node_id=request.node_id,
            attempt=request.attempt,
            job_id=None,
            status=outcome.status,
            progress=None,
            data=outcome.data,
            artifacts=outcome.artifacts,
            quality_flags=list(dict.fromkeys(outcome.quality_flags)),
            warnings=outcome.warnings,
            error=outcome.error,
            provenance=provenance,
            metrics=ExecutionMetrics(
                duration_ms=duration_ms,
                resource_summary={"mode": "mock", "scientific_compute": False},
            ),
        )

    def _queue_result(
        self, tool_name: str, request: StepRequest, final_result: StepResult
    ) -> StepResult:
        job_id = f"job-{_sha256([request.run_id, tool_name, request.idempotency_key])[:20]}"
        final_with_job = StepResult.model_validate(
            {
                **final_result.model_dump(mode="json"),
                "job_id": job_id,
            }
        )
        self.store.create_job(job_id, request.run_id, final_with_job)
        return StepResult.model_validate(
            {
                **final_result.model_dump(mode="json"),
                "job_id": job_id,
                "status": StepStatus.QUEUED.value,
                "progress": {"current": 0, "total": 2, "message": "Mock job queued"},
                "data": {
                    "mock_data": True,
                    "job_state": "QUEUED",
                    "original_tool": tool_name,
                },
                "artifacts": [],
                "warnings": [],
                "error": None,
            }
        )

    def _artifact(
        self, tool_name: str, request: StepRequest, logical_name: str
    ) -> ArtifactRef:
        payload = {
            "mock_data": True,
            "run_id": request.run_id,
            "tool_name": tool_name,
            "step_id": request.step_id,
            "attempt": request.attempt,
        }
        digest = _sha256(payload)
        return ArtifactRef(
            artifact_id=f"mock-{digest[:24]}",
            logical_name=logical_name,
            artifact_type=Path(logical_name).suffix.lstrip(".") or "json",
            media_type="application/json",
            sha256=digest,
            size_bytes=len(_stable_json(payload).encode("utf-8")),
            producer_step_id=request.step_id,
            created_at=_utc_now(),
            resource_uri=f"mock-artifact://{digest[:24]}",
        )

    def _update_run(self, tool_name: str, result: StepResult) -> None:
        if result.status == StepStatus.FAILED:
            self.store.set_run_status(result.run_id, RunStatus.FAILED)
            return
        if result.status == StepStatus.CANCELLED:
            self.store.set_run_status(result.run_id, RunStatus.CANCELLED)
            return
        if result.status == StepStatus.WAITING_USER:
            self.store.set_run_status(result.run_id, RunStatus.WAITING_USER)
            return
        if result.status == StepStatus.QUEUED:
            self.store.set_run_status(result.run_id, RunStatus.QUEUED)
            return
        if tool_name == "t01.route_handoff" and result.data:
            outcome = Outcome(result.data["outcome"])
            status = RunStatus.SUCCEEDED if outcome == Outcome.VARIANT_HANDOFF else RunStatus.DEGRADED
            self.store.set_run_status(result.run_id, status, outcome)
            return
        self.store.set_run_status(result.run_id, RunStatus.RUNNING)

    def job_status(self, run_id: str, job_id: str) -> StepResult:
        from .contracts import JobLookupRequest

        lookup = JobLookupRequest(run_id=run_id, job_id=job_id)
        state, polls, final, _ = self.store.advance_job(lookup)
        if state == StepStatus.SUCCEEDED:
            self.store.set_run_status(run_id, RunStatus.RUNNING)
            return final
        return self._active_job_result(final, state, polls)

    def job_result(self, run_id: str, job_id: str) -> StepResult:
        from .contracts import JobLookupRequest

        lookup = JobLookupRequest(run_id=run_id, job_id=job_id)
        state, polls, final, cancel_reason = self.store.read_job(lookup)
        if state == StepStatus.SUCCEEDED:
            return final
        if state == StepStatus.CANCELLED:
            return self._cancelled_job_result(final, cancel_reason or "cancelled")
        return self._active_job_result(final, state, polls)

    def cancel_job(self, run_id: str, job_id: str, reason: str) -> StepResult:
        from .contracts import JobCancelRequest

        lookup = JobCancelRequest(run_id=run_id, job_id=job_id, reason=reason)
        before, _, final, _ = self.store.read_job(lookup)
        if before not in {StepStatus.QUEUED, StepStatus.RUNNING}:
            return StepResult.model_validate(
                {
                    **final.model_dump(mode="json"),
                    "status": StepStatus.FAILED.value,
                    "progress": None,
                    "data": {"mock_data": True, "job_state": before.value},
                    "artifacts": [],
                    "error": _error(
                        "JOB_ALREADY_TERMINAL",
                        ErrorCategory.EXECUTION,
                        retryable=False,
                        message="A terminal job cannot be cancelled again.",
                        user_message="任务已结束，不能重复取消。",
                        job_id=job_id,
                        state=before.value,
                    ).model_dump(mode="json"),
                }
            )
        _, _, final, cancel_reason = self.store.cancel_job(lookup)
        self.store.set_run_status(run_id, RunStatus.CANCELLED)
        return self._cancelled_job_result(final, cancel_reason or reason)

    @staticmethod
    def _active_job_result(final: StepResult, state: StepStatus, polls: int) -> StepResult:
        current = 0 if state == StepStatus.QUEUED else min(1, polls)
        return StepResult.model_validate(
            {
                **final.model_dump(mode="json"),
                "status": state.value,
                "progress": {
                    "current": current,
                    "total": 2,
                    "message": f"Mock job {state.value.lower()}",
                },
                "data": {"mock_data": True, "job_state": state.value},
                "artifacts": [],
                "warnings": [],
                "error": None,
            }
        )

    @staticmethod
    def _cancelled_job_result(final: StepResult, reason: str) -> StepResult:
        return StepResult.model_validate(
            {
                **final.model_dump(mode="json"),
                "status": StepStatus.CANCELLED.value,
                "progress": None,
                "data": {"mock_data": True, "job_state": "CANCELLED"},
                "artifacts": [],
                "error": _error(
                    "JOB_CANCELLED",
                    ErrorCategory.CANCELLED,
                    retryable=False,
                    message="Mock job was cancelled.",
                    user_message="任务已取消。",
                    reason=reason,
                ).model_dump(mode="json"),
            }
        )
