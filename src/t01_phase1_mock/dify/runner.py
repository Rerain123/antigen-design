"""Build and evaluate real-target M3 execution captures.

Target invocation itself is performed inside the local Dify API container by
``scripts/t01_phase1_mock/dify_target_executor.py``.  This module owns only the
canonical request batches, explicit M2 lifecycle driver, acceptance assertions,
and evidence assembly.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..acceptance import AcceptanceHarness, CaseExecution
from ..catalog import SpecificationBundle
from ..engine import MockBackend
from ..fixtures import FixtureRepository
from ..jsonio import (
    ContractError,
    canonical_sha256,
    deep_copy,
    load_json,
    pretty_json_bytes,
    sha256_bytes,
)
from .normalization import first_difference


M3_RESULT_VERSION = "T01-PHASE1-MOCK-M3-ACCEPTANCE-RESULT-v0.1"
STAGES = ("M3_DIFY_MAIN", "M3_DIFY_DEBUG")


def build_submission_batch(
    *,
    app_name: str,
    role: str,
    output_path: Path,
    bundle: SpecificationBundle | None = None,
) -> dict[str, Any]:
    bundle = bundle or SpecificationBundle.load()
    fixtures = FixtureRepository(bundle)
    invocations: list[dict[str, Any]] = []
    for case in bundle.fixture_manifest["fixture_cases"]:
        for binding in case["submission_bindings"]:
            request = fixtures.instantiate_submission_request(
                case["scenario_key"], binding["submission_key"]
            )
            invocations.append(
                {
                    "scenario_key": case["scenario_key"],
                    "submission_key": binding["submission_key"],
                    "operation": "SUBMIT",
                    "request_json": json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    "run_id_override": "",
                }
            )
    if len(invocations) != 23:
        raise ContractError("M3 submission batch must contain exactly 23 canonical submissions")
    batch = {
        "document_type": "T01_PHASE1_MOCK_M3_DIFY_BATCH",
        "batch_version": "T01-PHASE1-MOCK-M3-DIFY-BATCH-v0.1",
        "app_name": app_name,
        "role": role,
        "invocation_count": len(invocations),
        "invocations": invocations,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pretty_json_bytes(batch))
    return batch


def drive_checkpoints(
    *,
    runtime_root: Path,
    submission_capture_path: Path,
    finalize_batch_path: Path,
    driver_capture_path: Path,
    app_name: str,
    role: str,
    bundle: SpecificationBundle | None = None,
) -> dict[str, Any]:
    bundle = bundle or SpecificationBundle.load()
    capture = load_json(submission_capture_path)
    first_by_scenario: dict[str, dict[str, Any]] = {}
    for item in capture["results"]:
        first_by_scenario.setdefault(item["scenario_key"], item)
    backend = MockBackend.local(bundle=bundle, runtime_root=runtime_root)
    checkpoint_records: dict[str, list[dict[str, Any]]] = {}
    final_invocations: list[dict[str, Any]] = []
    for scenario_key, plan in bundle.checkpoint_by_scenario.items():
        initial = first_by_scenario[scenario_key]
        outputs = initial.get("outputs") or {}
        envelope = outputs.get("envelope")
        if not isinstance(envelope, dict):
            raise ContractError(f"{scenario_key} Dify submission did not expose checkpoint envelope")
        current_run_id = envelope["run_id"]
        records = [
            {
                "sequence": 1,
                "action": "SUBMIT_CREATE",
                "checkpoint_fact": plan["steps"][0]["checkpoint_fact"],
                "run_id": current_run_id,
                "run": deep_copy(envelope),
            }
        ]
        for step in plan["steps"][1:]:
            action = step["action"]
            if action in {"POLL_SCENARIO_CHECKPOINT", "POLL_TERMINAL"}:
                next_envelope = backend.poll_run(current_run_id)
            elif action == "INJECT_SCENARIO_EVENT":
                next_envelope = backend.inject_scenario_event(current_run_id, step["checkpoint_fact"])
            elif action == "CANCEL_RUN":
                next_envelope = backend.cancel_run(current_run_id)
            elif action == "REQUEST_RECOVERY":
                current_run_id, next_envelope = backend.recover_run(current_run_id)
            else:
                raise ContractError(f"unsupported checkpoint action: {action}")
            if next_envelope["run_status"] != step["expected_run_status"]:
                raise ContractError(f"{scenario_key} checkpoint status mismatch at {step['sequence']}")
            records.append(
                {
                    "sequence": step["sequence"],
                    "action": action,
                    "checkpoint_fact": step["checkpoint_fact"],
                    "run_id": current_run_id,
                    "run": deep_copy(next_envelope),
                }
            )
        checkpoint_records[scenario_key] = records
        final_invocations.append(
            {
                "scenario_key": scenario_key,
                "submission_key": "checkpoint_finalize_observation",
                "operation": "FINALIZE_EXISTING",
                "request_json": "",
                "run_id_override": current_run_id,
            }
        )
    if len(checkpoint_records) != 4 or sum(map(len, checkpoint_records.values())) != 16:
        raise ContractError("checkpoint driver must materialize 4 plans and 16 checkpoints")
    final_batch = {
        "document_type": "T01_PHASE1_MOCK_M3_DIFY_BATCH",
        "batch_version": "T01-PHASE1-MOCK-M3-DIFY-BATCH-v0.1",
        "app_name": app_name,
        "role": role,
        "invocation_count": len(final_invocations),
        "invocations": final_invocations,
    }
    driver = {
        "document_type": "T01_PHASE1_MOCK_M3_LIFECYCLE_DRIVER_CAPTURE",
        "driver_version": "T01-PHASE1-MOCK-M3-LIFECYCLE-DRIVER-v0.1",
        "role": role,
        "checkpoint_plan_count": 4,
        "checkpoint_count": 16,
        "canonical_submission_count_delta": 0,
        "checkpoints": checkpoint_records,
    }
    finalize_batch_path.parent.mkdir(parents=True, exist_ok=True)
    finalize_batch_path.write_bytes(pretty_json_bytes(final_batch))
    driver_capture_path.parent.mkdir(parents=True, exist_ok=True)
    driver_capture_path.write_bytes(pretty_json_bytes(driver))
    return driver


def _capture_results(path: Path) -> list[dict[str, Any]]:
    capture = load_json(path)
    if capture.get("status") != "PASS":
        raise ContractError(f"Dify capture is not PASS: {path}")
    return capture["results"]


def _instance_run_mappings(paths: dict[str, Path]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Preserve Dify system-run ↔ canonical identity separation in final evidence."""

    hashes = {key: sha256_bytes(path.read_bytes()) for key, path in paths.items()}
    mappings: list[dict[str, Any]] = []
    for capture_kind, key in (("SUBMISSION", "submissions_path"), ("FINALIZATION", "finalizations_path")):
        for item in _capture_results(paths[key]):
            outputs = item.get("outputs") or {}
            submission = outputs.get("submission")
            envelope = outputs.get("envelope")
            canonical: dict[str, Any] = {}
            if isinstance(submission, dict):
                canonical = submission
            elif isinstance(envelope, dict):
                canonical = envelope
            mappings.append(
                {
                    "capture_kind": capture_kind,
                    "ordinal": item["ordinal"],
                    "scenario_key": item["scenario_key"],
                    "submission_key": item["submission_key"],
                    "operation": item["operation"],
                    "dify_workflow_run_id": item["dify_workflow_run_id"],
                    "canonical_request_id": canonical.get("request_id"),
                    "canonical_run_id": outputs.get("canonical_run_id") or canonical.get("run_id"),
                    "submission_action": outputs.get("submission_action"),
                    "dify_status": item["dify_status"],
                }
            )
    return hashes, mappings


def merge_captures(primary_path: Path, retry_paths: list[Path], output_path: Path) -> dict[str, Any]:
    """Replace failed transport attempts with successful idempotent retries."""

    primary = load_json(primary_path)
    by_ordinal = {item["ordinal"]: item for item in primary["results"]}
    retry_count = 0
    for retry_path in retry_paths:
        retry = load_json(retry_path)
        for item in retry["results"]:
            existing = by_ordinal.get(item["ordinal"])
            if existing is None:
                raise ContractError(f"retry ordinal was not in primary capture: {item['ordinal']}")
            if item["scenario_key"] != existing["scenario_key"] or item["submission_key"] != existing["submission_key"]:
                raise ContractError("retry identity differs from its canonical submission")
            if item["dify_status"] != "succeeded":
                raise ContractError("retry capture is not successful")
            by_ordinal[item["ordinal"]] = item
            retry_count += 1
    results = [by_ordinal[index] for index in sorted(by_ordinal)]
    failed = [item for item in results if item["dify_status"] != "succeeded"]
    merged = {
        **{key: value for key, value in primary.items() if key != "results"},
        "status": "PASS" if not failed else "FAIL",
        "invocation_count": len(results),
        "failure_count": len(failed),
        "transport_retry_count": retry_count,
        "canonical_submission_count_delta": 0,
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pretty_json_bytes(merged))
    return merged


def combine_captures(paths: list[Path], output_path: Path) -> dict[str, Any]:
    """Combine disjoint target-executor chunks while preserving canonical order."""

    if not paths:
        raise ContractError("at least one Dify capture chunk is required")
    captures = [load_json(path) for path in paths]
    identity = {(item["app_name"], item["role"]) for item in captures}
    if len(identity) != 1:
        raise ContractError("capture chunks belong to different apps or roles")
    results: list[dict[str, Any]] = []
    for capture in captures:
        results.extend(capture["results"])
    ordinals = [item["ordinal"] for item in results]
    if len(ordinals) != len(set(ordinals)):
        raise ContractError("capture chunks contain duplicate ordinals")
    results.sort(key=lambda item: item["ordinal"])
    failed = [item for item in results if item["dify_status"] != "succeeded"]
    app_name, role = next(iter(identity))
    combined = {
        "document_type": "T01_PHASE1_MOCK_M3_DIFY_CAPTURE",
        "capture_version": "T01-PHASE1-MOCK-M3-DIFY-CAPTURE-v0.1",
        "app_name": app_name,
        "role": role,
        "status": "PASS" if not failed else "FAIL",
        "invocation_count": len(results),
        "failure_count": len(failed),
        "chunk_count": len(paths),
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pretty_json_bytes(combined))
    return combined


def _case_executions(
    *,
    runtime_root: Path,
    submissions_path: Path,
    finalizations_path: Path,
    driver_path: Path,
    bundle: SpecificationBundle,
) -> list[CaseExecution]:
    fixtures = FixtureRepository(bundle)
    backend = MockBackend.local(bundle=bundle, fixtures=fixtures, runtime_root=runtime_root)
    raw_submissions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in _capture_results(submissions_path):
        raw_submissions[item["scenario_key"]].append(item)
    raw_finalizations = {
        item["scenario_key"]: item for item in _capture_results(finalizations_path)
    }
    driver = load_json(driver_path)
    cases: list[CaseExecution] = []
    for scenario in bundle.scenarios:
        scenario_key = scenario["scenario_key"]
        fixture_case = bundle.fixture_case_by_scenario[scenario_key]
        requests: list[dict[str, Any]] = []
        submissions: list[dict[str, Any]] = []
        for binding, captured in zip(
            fixture_case["submission_bindings"],
            raw_submissions[scenario_key],
            strict=True,
        ):
            request = fixtures.instantiate_submission_request(scenario_key, binding["submission_key"])
            requests.append(request)
            outputs = captured.get("outputs") or {}
            if outputs.get("submission") is not None:
                submission = outputs["submission"]
            else:
                envelope = outputs.get("envelope")
                if not isinstance(envelope, dict):
                    raise ContractError(f"{scenario_key} submission has no canonical envelope")
                submission = {
                    "action": outputs.get("submission_action"),
                    "request_id": request["request_id"],
                    "run_id": outputs.get("canonical_run_id"),
                    "run": envelope,
                    "error": None,
                    "error_code": None,
                }
            submissions.append(deep_copy(submission))
        checkpoints = deep_copy(driver["checkpoints"].get(scenario_key, []))
        if checkpoints:
            final_item = raw_finalizations[scenario_key]
            final_run = deep_copy(final_item["outputs"]["envelope"])
        else:
            envelope_items = [
                item.get("outputs", {}).get("envelope")
                for item in raw_submissions[scenario_key]
                if isinstance(item.get("outputs", {}).get("envelope"), dict)
            ]
            if not envelope_items:
                raise ContractError(f"{scenario_key} has no terminal envelope")
            final_run = deep_copy(envelope_items[-1])
        final_run_id = final_run["run_id"]
        metadata = backend.get_run_metadata(final_run_id)
        same_hash = canonical_sha256(final_run) if scenario_key == "idempotency_conflict" else None
        cases.append(
            CaseExecution(
                scenario=scenario,
                fixture_case=fixture_case,
                acceptance_case=bundle.acceptance_case_by_scenario[scenario_key],
                requests=requests,
                submissions=submissions,
                checkpoints=checkpoints,
                final_run=final_run,
                final_run_id=final_run_id,
                original_hash_before=same_hash,
                original_hash_after=same_hash,
                control_emission_count=metadata["control_emission_count"],
            )
        )
    return cases


def _evaluate_stage(
    *,
    stage: str,
    cases: list[CaseExecution],
    workflow_facts: dict[str, Any],
    bundle: SpecificationBundle,
) -> dict[str, Any]:
    if stage not in STAGES:
        raise ContractError(f"unsupported M3 stage: {stage}")
    harness = AcceptanceHarness(bundle=bundle)
    aggregate_checks = harness._global_checks(cases)  # shared frozen M1 operators/invariants
    global_results: list[dict[str, Any]] = []
    for assertion in bundle.acceptance_catalog["global_assertions"]:
        if stage not in assertion["applies_to"]:
            continue
        assertion_id = assertion["assertion_id"]
        detail: str | None = None
        try:
            if assertion_id.endswith(".015"):
                expected_workflows = {item["workflow_id"] for item in bundle.asset_registry["workflows"]}
                expected_tools = {item["tool_id"] for item in bundle.asset_registry["tool_namespace"]["tools"]}
                passed = (
                    set(workflow_facts["registered_workflow_ids"]) == expected_workflows
                    and workflow_facts["provider_id"] == bundle.asset_registry["tool_namespace"]["dify_provider_name"]
                    and set(workflow_facts["tool_ids"]) == expected_tools
                )
            else:
                check = aggregate_checks.get(assertion_id)
                if check is None:
                    raise ContractError(f"no aggregate implementation for {assertion_id}")
                passed = all(harness._evaluate_case_assertion(assertion, case) for case in cases) and bool(check())
            if not passed:
                detail = "catalog operator or aggregate invariant returned false"
        except Exception as exc:
            passed = False
            detail = f"{type(exc).__name__}: {exc}"
        global_results.append({"assertion_id": assertion_id, "status": "PASS" if passed else "FAIL", "detail": detail})

    focus_results: list[dict[str, Any]] = []
    for case in cases:
        for assertion in case.acceptance_case["focus_assertions"]:
            if stage not in assertion["applies_to"]:
                continue
            try:
                passed = harness._evaluate_case_assertion(assertion, case)
                detail = None if passed else "predicate returned false"
            except Exception as exc:
                passed = False
                detail = f"{type(exc).__name__}: {exc}"
            focus_results.append(
                {
                    "assertion_id": assertion["assertion_id"],
                    "scenario_key": case.scenario["scenario_key"],
                    "status": "PASS" if passed else "FAIL",
                    "detail": detail,
                }
            )
    case_status = {
        case.scenario["scenario_key"]: all(
            item["status"] == "PASS"
            for item in focus_results
            if item["scenario_key"] == case.scenario["scenario_key"]
        )
        for case in cases
    }
    coverage = []
    for gate in bundle.acceptance_catalog["coverage_gates"]:
        required = gate["required_scenario_keys"]
        passed = len(required) >= gate["minimum_case_count"] and all(case_status.get(key) for key in required)
        coverage.append({"gate_id": gate["gate_id"], "status": "PASS" if passed else "FAIL", "required_scenario_keys": required})
    failures = [item for item in global_results + focus_results + coverage if item["status"] != "PASS"]
    return {
        "stage": stage,
        "status": "PASS" if not failures else "FAIL",
        "case_count": len(cases),
        "submission_count": sum(len(case.submissions) for case in cases),
        "checkpoint_plan_count": sum(bool(case.checkpoints) for case in cases),
        "checkpoint_count": sum(len(case.checkpoints) for case in cases),
        "global_assertion_count": len(global_results),
        "focus_assertion_count": len(focus_results),
        "coverage_gate_count": len(coverage),
        "blocker_failure_count": len(failures),
        "global_assertions": global_results,
        "focus_assertions": focus_results,
        "coverage_gates": coverage,
        "case_results": [
            {
                "ordinal": case.fixture_case["ordinal"],
                "scenario_key": case.scenario["scenario_key"],
                "submission_actions": [item["action"] for item in case.submissions],
                "final_run_id": case.final_run_id,
                "recovery_of_run_id": case.final_run["recovery_of_run_id"],
                "run_status": case.final_run["run_status"],
                "canonical_envelope_sha256": canonical_sha256(case.final_run),
                "status": "PASS" if case_status[case.scenario["scenario_key"]] else "FAIL",
            }
            for case in cases
        ],
    }


def assemble_m3_result(
    *,
    main_paths: dict[str, Path],
    debug_paths: dict[str, Path],
    main_runtime_root: Path,
    debug_runtime_root: Path,
    workflow_facts: dict[str, Any],
    instance_mappings: dict[str, Any],
    bundle: SpecificationBundle | None = None,
) -> dict[str, Any]:
    bundle = bundle or SpecificationBundle.load()
    main_cases = _case_executions(runtime_root=main_runtime_root, bundle=bundle, **main_paths)
    debug_cases = _case_executions(runtime_root=debug_runtime_root, bundle=bundle, **debug_paths)
    main = _evaluate_stage(stage="M3_DIFY_MAIN", cases=main_cases, workflow_facts=workflow_facts, bundle=bundle)
    debug = _evaluate_stage(stage="M3_DIFY_DEBUG", cases=debug_cases, workflow_facts=workflow_facts, bundle=bundle)
    main["capture_sha256"], main["instance_run_mappings"] = _instance_run_mappings(main_paths)
    debug["capture_sha256"], debug["instance_run_mappings"] = _instance_run_mappings(debug_paths)
    parity_results: list[dict[str, Any]] = []
    for main_case, debug_case in zip(main_cases, debug_cases, strict=True):
        difference = first_difference(main_case.final_run, debug_case.final_run)
        parity_results.append(
            {
                "scenario_key": main_case.scenario["scenario_key"],
                "status": "PASS" if difference is None else "FAIL",
                "first_difference": difference,
                "main_sha256": canonical_sha256(main_case.final_run),
                "debug_sha256": canonical_sha256(debug_case.final_run),
            }
        )
    parity_failures = [item for item in parity_results if item["status"] != "PASS"]
    result = {
        "$schema": "T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT_SCHEMA_v0.1.json",
        "document_type": "T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT",
        "result_version": M3_RESULT_VERSION,
        "binding_profile": "local_dify_1_17",
        "status": "PASS" if main["status"] == debug["status"] == "PASS" and not parity_failures else "FAIL",
        "implementation_state": "M3_DIFY_EXECUTED",
        "instance_mappings": instance_mappings,
        "workflow_facts": workflow_facts,
        "main": main,
        "debug": debug,
        "parity": {
            "stage": "M3_MAIN_DEBUG_PARITY",
            "status": "PASS" if not parity_failures else "FAIL",
            "case_count": len(parity_results),
            "global_016_status": "PASS" if not parity_failures else "FAIL",
            "failure_count": len(parity_failures),
            "results": parity_results,
        },
        "scientific_execution_count": 0,
        "scientific_network_request_count": 0,
        "legacy_implementation_reuse_count": 0,
        "himat_backend_access_count": 0,
        "blocker_failure_count": main["blocker_failure_count"] + debug["blocker_failure_count"] + len(parity_failures),
    }
    return result
