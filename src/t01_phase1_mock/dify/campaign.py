"""Independent M4 regression campaign and Phase 1 Mock v0.1 freeze support."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from ..acceptance import (
    AcceptanceHarness,
    AssertionOperatorRegistry,
    CaseExecution,
    SelectorAdapter,
    selector_view,
)
from ..catalog import SpecificationBundle, validate_instance
from ..constants import (
    EDGE_IDS,
    M4_CAMPAIGN_ID_PATTERN,
    M4_FREEZE_MANIFEST_VERSION,
    M4_RESULT_VERSION,
    REQUEST_ID_PATTERN,
    RUN_ID_PATTERN,
)
from ..fixtures import FixtureRepository
from ..jsonio import (
    ContractError,
    canonical_sha256,
    deep_copy,
    load_json,
    pretty_json_bytes,
    sha256_bytes,
)
from ..paths import (
    ACCEPTANCE_CATALOG_PATH,
    ASSET_REGISTRY_PATH,
    BINDING_ROOT,
    FIXTURE_ROOT,
    M2_ACCEPTANCE_RESULT_PATH,
    M3_ACCEPTANCE_RESULT_PATH,
    M3_BINDING_EVIDENCE_PATH,
    M3_IMPORT_EVIDENCE_PATH,
    M3_LOCAL_PROFILE_ROOT,
    M4_ACCEPTANCE_RESULT_SCHEMA_PATH,
    M4_FREEZE_MANIFEST_PATH,
    M4_FREEZE_MANIFEST_SCHEMA_PATH,
    M4_RUNS_ROOT,
    M1_SPEC_SOURCE_PATHS,
    PHASE1_RELEASE_ROOT,
    PROJECT_ROOT,
    REGRESSION_ROOT,
    resolve_project_relative,
)
from .binding import bind_documents, validate_manifest
from .generator import render_all
from .normalization import first_difference, normalize_result
from .runner import (
    _case_executions,
    _instance_run_mappings,
    build_submission_batch,
    drive_checkpoints,
)
from .validator import validate_main_debug_pair, validate_workflow_document


M4_STAGE = "M4_REGRESSION_FREEZE"
M4_CAMPAIGN_VERSION = "T01-PHASE1-MOCK-M4-CAMPAIGN-v0.1"
M4_ASSET_CHAIN_VERSION = "T01-PHASE1-MOCK-M4-ASSET-CHAIN-v0.1"
M4_PARTITION_RESULT_VERSION = "T01-PHASE1-MOCK-M4-PARTITION-RESULT-v0.1"
_PROFILE = "local_dify_1_17"
_ROLE_FACTS = {
    "main": ("PRIMARY", "T01_Phase1_Mock_v0.1"),
    "debug": ("DEBUG", "T01_Phase1_Mock_v0.1_Debug"),
}
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _project_relative(path: Path) -> str:
    lexical = path.absolute()
    try:
        relative = lexical.relative_to(PROJECT_ROOT.absolute()).as_posix()
    except ValueError as exc:
        raise ContractError(f"M4 path leaves the project root: {path}") from exc
    checked = resolve_project_relative(relative, must_exist=path.exists())
    if checked != path.resolve():
        raise ContractError(f"M4 path resolution drift: {path}")
    return relative


def validate_campaign_id(campaign_id: str) -> None:
    if M4_CAMPAIGN_ID_PATTERN.fullmatch(campaign_id) is None:
        raise ContractError(
            "campaign_id must match t01p1m-v01-reg-YYYYMMDD-{lowercase-slug}"
        )
    date_value = campaign_id.removeprefix("t01p1m-v01-reg-").split("-", 1)[0]
    try:
        datetime.strptime(date_value, "%Y%m%d")
    except ValueError as exc:
        raise ContractError("campaign_id contains an invalid calendar date") from exc


def campaign_root(campaign_id: str) -> Path:
    validate_campaign_id(campaign_id)
    try:
        runs_relative = M4_RUNS_ROOT.relative_to(PROJECT_ROOT).as_posix()
    except ValueError as exc:
        raise ContractError("M4 runs root leaves the project root") from exc
    runs_root = resolve_project_relative(
        runs_relative, must_exist=M4_RUNS_ROOT.exists()
    )
    root = resolve_project_relative(
        f"{runs_relative}/{campaign_id}",
        must_exist=(runs_root / campaign_id).exists(),
    )
    try:
        root.relative_to(M4_RUNS_ROOT.resolve())
    except ValueError as exc:
        raise ContractError("M4 campaign root escaped the frozen runs root") from exc
    if root.exists() and root.is_symlink():
        raise ContractError("M4 campaign root cannot be a symlink")
    return root


def campaign_runtime_root(campaign_id: str, role: str) -> Path:
    validate_campaign_id(campaign_id)
    if role not in _ROLE_FACTS:
        raise ContractError(f"unknown M4 role: {role}")
    lexical = (
        PROJECT_ROOT
        / "var"
        / "t01-phase1-mock-v0.1"
        / "m4-campaigns"
        / campaign_id
        / role
        / "runtime"
    )
    relative = lexical.relative_to(PROJECT_ROOT).as_posix()
    return resolve_project_relative(relative, must_exist=lexical.exists())


def _hash_record(path: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {
        "path": _project_relative(path),
        "bytes": len(content),
        "sha256": sha256_bytes(content),
    }


def _validate_transport_health(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "status": "ok",
        "server": "t01-phase1-mock-v01",
        "tool_count": 26,
        "mock_only": True,
        "scientific_compute": False,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ContractError("M4 Mock transport health facts differ from the frozen toolset")
    return {
        "endpoint_scope": "LOCALHOST_ONLY",
        "status": payload["status"],
        "server": payload["server"],
        "tool_count": payload["tool_count"],
        "mock_only": payload["mock_only"],
        "scientific_compute": payload["scientific_compute"],
    }


def build_asset_chain(
    bundle: SpecificationBundle | None = None,
) -> dict[str, Any]:
    """Recompute generator→template→binding→bound and frozen-input facts."""

    bundle = bundle or SpecificationBundle.load()
    fixtures = FixtureRepository(bundle)
    fixture_counts = fixtures.verify()
    if fixture_counts != {
        "input_fixture_count": 2,
        "request_variant_count": 22,
        "attempt_fixture_count": 326,
        "payload_file_count": 350,
    }:
        raise ContractError("M4 fixture closed-set cardinality drift")
    if len(bundle.source_sha256) != 21:
        raise ContractError("M4 requires exactly 21 frozen M1 source hashes")
    m2_result = load_json(M2_ACCEPTANCE_RESULT_PATH)
    m3_result = load_json(M3_ACCEPTANCE_RESULT_PATH)
    m3_binding = load_json(M3_BINDING_EVIDENCE_PATH)
    if m2_result.get("status") != "PASS" or m2_result.get("blocker_failure_count") != 0:
        raise ContractError("M4 requires the independent M2 result to remain PASS")
    if m2_result.get("source_sha256") != bundle.source_sha256:
        raise ContractError("M1 source hash drift relative to the M2 acceptance result")
    if m3_result.get("status") != "PASS" or m3_result.get("blocker_failure_count") != 0:
        raise ContractError("M4 requires the independent M3 result to remain PASS")
    if (
        m3_binding.get("result") != "PASS"
        or m3_binding.get("binding_profile") != _PROFILE
        or m3_binding.get("tool_count") != 26
        or m3_binding.get("unresolved_token_count") != 0
        or m3_binding.get("secret_finding_count") != 0
        or m3_binding.get("scientific_compute") is not False
    ):
        raise ContractError("M4 requires the frozen M3 binding evidence to remain PASS")

    generated = render_all(bundle)
    generated_documents: list[dict[str, Any]] = []
    template_records: dict[str, dict[str, Any]] = {}
    for item in generated:
        validate_workflow_document(
            item.document,
            bundle=bundle,
            expected_app_name=item.app_name,
            template=True,
        )
        if not item.output_path.is_file() or item.output_path.read_bytes() != item.content:
            raise ContractError(f"M4 detected generated template drift: {item.output_path}")
        generated_documents.append(item.document)
        template_records[item.role] = _hash_record(item.output_path)
    validate_main_debug_pair(generated_documents[0], generated_documents[1])

    binding_path = BINDING_ROOT / "provider-bindings.local_dify_1_17.json"
    binding = load_json(binding_path)
    validate_manifest(binding, bundle)
    bound = bind_documents(binding, bundle=bundle)
    bound_records: dict[str, dict[str, Any]] = {}
    for item in bound:
        if not item.path.is_file() or item.path.read_bytes() != item.content:
            raise ContractError(f"M4 detected bound workflow drift: {item.path}")
        bound_records[item.role] = _hash_record(item.path)
    recomputed_hashes = {
        "registry_sha256": _hash_record(ASSET_REGISTRY_PATH)["sha256"],
        "template_sha256": {
            "PRIMARY": template_records["PRIMARY"]["sha256"],
            "DEBUG": template_records["DEBUG"]["sha256"],
        },
        "binding_manifest_sha256": _hash_record(binding_path)["sha256"],
        "bound_sha256": {
            "PRIMARY": bound_records["PRIMARY"]["sha256"],
            "DEBUG": bound_records["DEBUG"]["sha256"],
        },
    }
    if any(
        recomputed_hashes[key] != m3_binding.get(key)
        for key in recomputed_hashes
    ):
        raise ContractError("M4 generator/template/binding/bound hash chain drift")

    return {
        "document_type": "T01_PHASE1_MOCK_M4_ASSET_CHAIN",
        "chain_version": M4_ASSET_CHAIN_VERSION,
        "binding_profile": _PROFILE,
        "status": "PASS",
        "source_baseline": {
            "baseline_id": "T01-PHASE1-MOCK-M1-BASELINE-v0.1",
            "source_count": len(bundle.source_sha256),
            "source_sha256": deep_copy(bundle.source_sha256),
        },
        "fixture_counts": fixture_counts,
        "m2_result": _hash_record(M2_ACCEPTANCE_RESULT_PATH),
        "m3_result": _hash_record(M3_ACCEPTANCE_RESULT_PATH),
        "m3_binding_evidence": _hash_record(M3_BINDING_EVIDENCE_PATH),
        "acceptance_catalog": _hash_record(ACCEPTANCE_CATALOG_PATH),
        "asset_registry": _hash_record(ASSET_REGISTRY_PATH),
        "templates": template_records,
        "binding_manifest": _hash_record(binding_path),
        "bound": bound_records,
        "workflow_facts": {
            "registered_workflow_ids": [
                item["workflow_id"] for item in bundle.asset_registry["workflows"]
            ],
            "provider_id": bundle.asset_registry["tool_namespace"]["dify_provider_name"],
            "tool_ids": [
                item["tool_id"]
                for item in bundle.asset_registry["tool_namespace"]["tools"]
            ],
            "workflow_count": 2,
            "tool_count": 26,
            "node_count_per_canvas": 59,
            "edge_count_per_canvas": 79,
            "semantic_edge_ids": list(EDGE_IDS),
        },
        "unresolved_token_count": 0,
        "generator_check": "PASS",
        "binder_check": "PASS",
        "main_debug_normalized_business_graph": "EQUAL",
        "secret_finding_count": 0,
        "scientific_execution_count": 0,
        "scientific_network_request_count": 0,
        "legacy_implementation_reuse_count": 0,
        "blocker_failure_count": 0,
    }


def _convert_batch_to_m4(
    batch: dict[str, Any],
    campaign_id: str,
    application: dict[str, Any],
) -> dict[str, Any]:
    value = deep_copy(batch)
    value["document_type"] = "T01_PHASE1_MOCK_M4_DIFY_BATCH"
    value["batch_version"] = "T01-PHASE1-MOCK-M4-DIFY-BATCH-v0.1"
    value["campaign_id"] = campaign_id
    value["expected_app_id"] = application["app_id"]
    value["stable_workflow_id"] = application["stable_workflow_id"]
    return value


def prepare_campaign(
    campaign_id: str,
    *,
    transport_health: dict[str, Any],
    prepared_at: str,
    bundle: SpecificationBundle | None = None,
) -> dict[str, Any]:
    """Create a new evidence root and two fresh 23-submission Dify batches."""

    bundle = bundle or SpecificationBundle.load()
    root = campaign_root(campaign_id)
    if root.exists():
        raise ContractError(f"M4 campaign already exists and is immutable: {campaign_id}")
    runtime_roots = {
        role: campaign_runtime_root(campaign_id, role) for role in _ROLE_FACTS
    }
    if any(path.exists() for path in runtime_roots.values()):
        raise ContractError(
            "M4 campaign runtime already exists; choose a new campaign identity"
        )
    asset_chain = build_asset_chain(bundle)
    health = _validate_transport_health(transport_health)
    try:
        prepared_time = datetime.fromisoformat(prepared_at.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ContractError("M4 prepared_at must be an ISO-8601 timestamp") from exc
    if prepared_time.tzinfo is None:
        raise ContractError("M4 prepared_at must include a timezone")
    m3_import = load_json(M3_IMPORT_EVIDENCE_PATH)
    if (
        m3_import.get("result") != "PASS"
        or m3_import.get("target", {}).get("environment") != "LOCAL_DIFY_DOCKER"
        or m3_import.get("target", {}).get("dify_version") != "1.17.0"
        or m3_import.get("target", {}).get("dsl_version") != "0.7.0"
        or len(m3_import.get("applications", [])) != 2
    ):
        raise ContractError("M4 cannot resolve the two exact M3 target application identities")
    applications = {
        item.get("role"): item for item in m3_import["applications"]
    }
    if set(applications) != {"PRIMARY", "DEBUG"}:
        raise ContractError("M4 requires exactly one PRIMARY and one DEBUG application")
    if len({item.get("app_id") for item in applications.values()}) != 2:
        raise ContractError("M4 target application IDs must be distinct")

    root.mkdir(parents=True, exist_ok=False)
    (root / "main").mkdir()
    (root / "debug").mkdir()
    (root / "asset-chain.json").write_bytes(pretty_json_bytes(asset_chain))
    roles: dict[str, Any] = {}
    for role, (dify_role, app_name) in _ROLE_FACTS.items():
        application = applications[dify_role]
        if application.get("app_name") != app_name:
            raise ContractError(f"M4 target application name drift for {role}")
        batch_path = root / role / "submissions.batch.json"
        raw = build_submission_batch(
            app_name=app_name,
            role=dify_role,
            output_path=batch_path,
            bundle=bundle,
        )
        batch = _convert_batch_to_m4(raw, campaign_id, application)
        batch_path.write_bytes(pretty_json_bytes(batch))
        roles[role] = {
            "role": dify_role,
            "app_name": app_name,
            "app_id": application["app_id"],
            "draft_workflow_id": application["draft_workflow_id"],
            "stable_workflow_id": application["stable_workflow_id"],
            "runtime_root": _project_relative(runtime_roots[role]),
            "submission_batch": _project_relative(batch_path),
            "submission_capture": _project_relative(root / role / "submissions.capture.json"),
            "lifecycle_capture": _project_relative(root / role / "lifecycle.capture.json"),
            "finalization_batch": _project_relative(root / role / "finalizations.batch.json"),
            "finalization_capture": _project_relative(root / role / "finalizations.capture.json"),
            "submission_batch_evidence": _hash_record(batch_path),
        }

    plan = {
        "document_type": "T01_PHASE1_MOCK_M4_CAMPAIGN",
        "campaign_version": M4_CAMPAIGN_VERSION,
        "campaign_id": campaign_id,
        "state": "PREPARED",
        "prepared_at": prepared_at,
        "binding_profile": _PROFILE,
        "target": {
            "environment": "LOCAL_DIFY_DOCKER",
            "dify_version": "1.17.0",
            "dsl_version": "0.7.0",
            "transport_health": health,
        },
        "source_evidence": {
            "asset_chain": _hash_record(root / "asset-chain.json"),
            "m3_import": _hash_record(M3_IMPORT_EVIDENCE_PATH),
        },
        "expected_applications": [
            {
                "role": item["role"],
                "stable_workflow_id": item["stable_workflow_id"],
                "app_name": item["app_name"],
                "app_id": item["app_id"],
                "draft_workflow_id": item["draft_workflow_id"],
            }
            for item in (applications["PRIMARY"], applications["DEBUG"])
        ],
        "roles": roles,
        "evidence_policy": {
            "reuse_m3_execution_root": False,
            "canonical_submission_count_per_role": 23,
            "checkpoint_plan_count_per_role": 4,
            "checkpoint_count_per_role": 16,
            "scientific_compute": False,
            "production_state": "NOT_DEPLOYED",
        },
    }
    (root / "campaign.json").write_bytes(pretty_json_bytes(plan))
    return plan


def _load_campaign(campaign_id: str) -> tuple[Path, dict[str, Any]]:
    root = campaign_root(campaign_id)
    plan_path = root / "campaign.json"
    if not plan_path.is_file():
        raise ContractError(f"M4 campaign does not exist: {campaign_id}")
    _project_relative(plan_path)
    plan = load_json(plan_path)
    if (
        plan.get("document_type") != "T01_PHASE1_MOCK_M4_CAMPAIGN"
        or plan.get("campaign_version") != M4_CAMPAIGN_VERSION
        or plan.get("campaign_id") != campaign_id
        or plan.get("state") != "PREPARED"
        or plan.get("binding_profile") != _PROFILE
        or plan.get("target", {}).get("environment") != "LOCAL_DIFY_DOCKER"
        or plan.get("target", {}).get("dify_version") != "1.17.0"
        or plan.get("target", {}).get("dsl_version") != "0.7.0"
    ):
        raise ContractError("M4 campaign plan identity mismatch")
    try:
        prepared_time = datetime.fromisoformat(
            str(plan.get("prepared_at", "")).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ContractError("M4 campaign prepared_at is invalid") from exc
    if prepared_time.tzinfo is None:
        raise ContractError("M4 campaign prepared_at must include a timezone")
    policy = plan.get("evidence_policy", {})
    expected_policy = {
        "reuse_m3_execution_root": False,
        "canonical_submission_count_per_role": 23,
        "checkpoint_plan_count_per_role": 4,
        "checkpoint_count_per_role": 16,
        "scientific_compute": False,
        "production_state": "NOT_DEPLOYED",
    }
    if policy != expected_policy:
        raise ContractError("M4 campaign evidence policy drift")
    if set(plan.get("roles", {})) != set(_ROLE_FACTS):
        raise ContractError("M4 campaign role set mismatch")
    expected_apps = {
        item.get("role"): item for item in plan.get("expected_applications", [])
    }
    if set(expected_apps) != {"PRIMARY", "DEBUG"}:
        raise ContractError("M4 campaign application identity set mismatch")
    m3_apps = {
        item.get("role"): item
        for item in load_json(M3_IMPORT_EVIDENCE_PATH).get("applications", [])
    }
    identity_keys = (
        "role",
        "stable_workflow_id",
        "app_name",
        "app_id",
        "draft_workflow_id",
    )
    if set(m3_apps) != set(expected_apps) or any(
        {key: expected_apps[role].get(key) for key in identity_keys}
        != {key: m3_apps[role].get(key) for key in identity_keys}
        for role in expected_apps
    ):
        raise ContractError("M4 campaign application identity differs from M3 evidence")
    for role, (dify_role, app_name) in _ROLE_FACTS.items():
        role_plan = plan["roles"][role]
        app = expected_apps[dify_role]
        if (
            role_plan.get("role") != dify_role
            or role_plan.get("app_name") != app_name
            or role_plan.get("app_id") != app.get("app_id")
            or role_plan.get("draft_workflow_id") != app.get("draft_workflow_id")
            or role_plan.get("stable_workflow_id") != app.get("stable_workflow_id")
        ):
            raise ContractError(f"M4 campaign application identity drift for {role}")
        role_paths = _role_paths(root, plan, role)
        if role_plan.get("submission_batch_evidence") != _hash_record(
            role_paths["submission_batch"]
        ):
            raise ContractError(f"M4 immutable submission batch drift for {role}")
    for key, path in (
        ("asset_chain", root / "asset-chain.json"),
        ("m3_import", M3_IMPORT_EVIDENCE_PATH),
    ):
        record = plan.get("source_evidence", {}).get(key)
        if not isinstance(record, dict) or record != _hash_record(path):
            raise ContractError(f"M4 campaign source evidence drift: {key}")
    return root, plan


def _require_exact_path(
    value: Any,
    expected: Path,
    *,
    must_exist: bool = False,
) -> Path:
    if not isinstance(value, str):
        raise ContractError("M4 campaign path must be project-relative text")
    actual = resolve_project_relative(value, must_exist=must_exist)
    if actual != expected.resolve():
        raise ContractError(f"M4 campaign path drift: {value}")
    return actual


def _role_paths(
    root: Path,
    plan: dict[str, Any],
    role: str,
) -> dict[str, Path]:
    if role not in _ROLE_FACTS:
        raise ContractError(f"unknown M4 role: {role}")
    value = plan["roles"][role]
    expected = {
        "runtime_root": campaign_runtime_root(plan["campaign_id"], role),
        "submission_batch": root / role / "submissions.batch.json",
        "submission_capture": root / role / "submissions.capture.json",
        "lifecycle_capture": root / role / "lifecycle.capture.json",
        "finalization_batch": root / role / "finalizations.batch.json",
        "finalization_capture": root / role / "finalizations.capture.json",
    }
    paths = {
        key: _require_exact_path(
            value.get(key),
            path,
            must_exist=key == "submission_batch",
        )
        for key, path in expected.items()
    }
    if role == "debug" and paths["runtime_root"] == campaign_runtime_root(
        plan["campaign_id"], "main"
    ):
        raise ContractError("M4 main/debug runtime roots must be distinct")
    return paths


def _validate_batch(
    path: Path,
    *,
    campaign_id: str,
    role: str,
    plan: dict[str, Any],
    expected_count: int,
) -> dict[str, Any]:
    batch = load_json(path)
    role_plan = plan["roles"][role]
    if (
        batch.get("document_type") != "T01_PHASE1_MOCK_M4_DIFY_BATCH"
        or batch.get("batch_version") != "T01-PHASE1-MOCK-M4-DIFY-BATCH-v0.1"
        or batch.get("campaign_id") != campaign_id
        or batch.get("role") != role_plan["role"]
        or batch.get("app_name") != role_plan["app_name"]
        or batch.get("expected_app_id") != role_plan["app_id"]
        or batch.get("stable_workflow_id") != role_plan["stable_workflow_id"]
        or batch.get("invocation_count") != expected_count
    ):
        raise ContractError(f"invalid {role} M4 Dify batch: {path}")
    invocations = batch.get("invocations")
    if not isinstance(invocations, list) or len(invocations) != expected_count:
        raise ContractError(f"{role} M4 Dify batch invocation count mismatch")
    expected_operation = "SUBMIT" if expected_count == 23 else "FINALIZE_EXISTING"
    if any(item.get("operation") != expected_operation for item in invocations):
        raise ContractError(f"{role} M4 Dify batch operation mismatch")
    if expected_operation == "SUBMIT":
        for item in invocations:
            try:
                request = json.loads(item.get("request_json", ""))
            except json.JSONDecodeError as exc:
                raise ContractError(f"{role} M4 submission request is not JSON") from exc
            if REQUEST_ID_PATTERN.fullmatch(str(request.get("request_id", ""))) is None:
                raise ContractError(f"{role} M4 submission request_id is invalid")
            if item.get("run_id_override") != "":
                raise ContractError(f"{role} M4 submission run override is forbidden")
    else:
        for item in invocations:
            if (
                item.get("request_json") != ""
                or RUN_ID_PATTERN.fullmatch(str(item.get("run_id_override", ""))) is None
            ):
                raise ContractError(f"{role} M4 finalization identity is invalid")
    return batch


def _validate_capture(
    path: Path,
    *,
    campaign_id: str,
    role: str,
    plan: dict[str, Any],
    batch_path: Path,
    expected_draft_workflow_id: str | None = None,
    expected_count: int,
) -> dict[str, Any]:
    capture = load_json(path)
    dify_role, app_name = _ROLE_FACTS[role]
    role_plan = plan["roles"][role]
    if (
        capture.get("document_type") != "T01_PHASE1_MOCK_M4_DIFY_CAPTURE"
        or capture.get("capture_version") != "T01-PHASE1-MOCK-M4-DIFY-CAPTURE-v0.1"
        or capture.get("campaign_id") != campaign_id
        or capture.get("role") != dify_role
        or capture.get("app_name") != app_name
        or capture.get("app_id") != role_plan["app_id"]
        or capture.get("stable_workflow_id") != role_plan["stable_workflow_id"]
        or capture.get("status") != "PASS"
        or capture.get("invocation_count") != expected_count
        or capture.get("failure_count") != 0
    ):
        raise ContractError(f"invalid {role} M4 Dify capture: {path}")
    draft_id = capture.get("draft_workflow_id")
    if _UUID_PATTERN.fullmatch(str(draft_id or "")) is None or (
        expected_draft_workflow_id is not None
        and draft_id != expected_draft_workflow_id
    ):
        raise ContractError(f"{role} M4 Dify capture draft identity mismatch")
    results = capture.get("results")
    if not isinstance(results, list) or len(results) != expected_count:
        raise ContractError(f"{role} M4 Dify capture result count mismatch")
    batch = _validate_batch(
        batch_path,
        campaign_id=campaign_id,
        role=role,
        plan=plan,
        expected_count=expected_count,
    )
    workflow_run_ids = [item.get("dify_workflow_run_id") for item in results]
    if (
        any(item.get("dify_status") != "succeeded" for item in results)
        or any(
            not isinstance(value, str) or _UUID_PATTERN.fullmatch(value) is None
            for value in workflow_run_ids
        )
        or len(workflow_run_ids) != len(set(workflow_run_ids))
    ):
        raise ContractError(f"{role} M4 Dify capture contains failed or duplicate runs")
    for ordinal, (item, invocation) in enumerate(
        zip(results, batch["invocations"], strict=True), start=1
    ):
        if (
            item.get("ordinal") != ordinal
            or item.get("scenario_key") != invocation.get("scenario_key")
            or item.get("submission_key") != invocation.get("submission_key")
            or item.get("operation") != invocation.get("operation")
            or item.get("dify_error") is not None
            or not isinstance(item.get("total_steps"), int)
            or item.get("total_steps", 0) <= 0
        ):
            raise ContractError(f"{role} M4 Dify capture ordering/identity mismatch")
        outputs = item.get("outputs")
        if not isinstance(outputs, dict):
            raise ContractError(f"{role} M4 Dify capture has invalid outputs")
        canonical = outputs.get("submission")
        if not isinstance(canonical, dict):
            canonical = outputs.get("envelope")
        if not isinstance(canonical, dict):
            raise ContractError(f"{role} M4 Dify capture lacks a canonical output")
        request_id = canonical.get("request_id")
        if REQUEST_ID_PATTERN.fullmatch(str(request_id or "")) is None:
            raise ContractError(f"{role} M4 canonical request identity is invalid")
        canonical_run_id = outputs.get("canonical_run_id") or canonical.get("run_id")
        if canonical_run_id is not None:
            if RUN_ID_PATTERN.fullmatch(str(canonical_run_id)) is None:
                raise ContractError(f"{role} M4 canonical run identity is invalid")
            if canonical_run_id == item["dify_workflow_run_id"]:
                raise ContractError("Dify and canonical run identities must remain separate")
        if invocation["operation"] == "SUBMIT":
            request = json.loads(invocation["request_json"])
            submitted_request_id = request["request_id"]
            if item.get("submitted_request_id") != submitted_request_id:
                raise ContractError(f"{role} M4 submitted request mapping drift")
            submission_action = outputs.get("submission_action") or canonical.get(
                "action"
            )
            if submission_action not in {
                "CREATE_RUN",
                "RETURN_EXISTING_RUN",
                "REJECT_REQUEST",
            }:
                raise ContractError(f"{role} M4 submission action is invalid")
            if (
                submission_action != "RETURN_EXISTING_RUN"
                and request_id != submitted_request_id
            ):
                raise ContractError(f"{role} M4 canonical request mapping drift")
        elif (
            item.get("submitted_request_id") is not None
            or canonical_run_id != invocation["run_id_override"]
        ):
            raise ContractError(f"{role} M4 finalization run mapping drift")
    return capture


def drive_campaign_role(campaign_id: str, role: str) -> dict[str, Any]:
    """Apply the frozen four lifecycle plans after one role's target submissions."""

    root, plan = _load_campaign(campaign_id)
    if role not in _ROLE_FACTS:
        raise ContractError(f"unknown M4 role: {role}")
    role_plan = plan["roles"][role]
    paths = _role_paths(root, plan, role)
    submissions_path = paths["submission_capture"]
    _validate_capture(
        submissions_path,
        campaign_id=campaign_id,
        role=role,
        plan=plan,
        batch_path=paths["submission_batch"],
        expected_count=23,
    )
    final_batch_path = paths["finalization_batch"]
    driver_path = paths["lifecycle_capture"]
    if final_batch_path.exists() or driver_path.exists():
        raise ContractError(
            f"M4 {role} lifecycle evidence already exists and cannot be overwritten"
        )
    raw_driver = drive_checkpoints(
        runtime_root=paths["runtime_root"],
        submission_capture_path=submissions_path,
        finalize_batch_path=final_batch_path,
        driver_capture_path=driver_path,
        app_name=role_plan["app_name"],
        role=role_plan["role"],
    )
    driver = deep_copy(raw_driver)
    driver["document_type"] = "T01_PHASE1_MOCK_M4_LIFECYCLE_DRIVER_CAPTURE"
    driver["driver_version"] = "T01-PHASE1-MOCK-M4-LIFECYCLE-DRIVER-v0.1"
    driver["campaign_id"] = campaign_id
    driver_path.write_bytes(pretty_json_bytes(driver))
    final_batch = _convert_batch_to_m4(
        load_json(final_batch_path), campaign_id, role_plan
    )
    final_batch_path.write_bytes(pretty_json_bytes(final_batch))
    return driver


def _validate_driver(
    path: Path,
    campaign_id: str,
    role: str,
    *,
    bundle: SpecificationBundle,
) -> dict[str, Any]:
    value = load_json(path)
    if (
        value.get("document_type")
        != "T01_PHASE1_MOCK_M4_LIFECYCLE_DRIVER_CAPTURE"
        or value.get("driver_version")
        != "T01-PHASE1-MOCK-M4-LIFECYCLE-DRIVER-v0.1"
        or value.get("campaign_id") != campaign_id
        or value.get("role") != _ROLE_FACTS[role][0]
        or value.get("checkpoint_plan_count") != 4
        or value.get("checkpoint_count") != 16
        or value.get("canonical_submission_count_delta") != 0
    ):
        raise ContractError(f"invalid {role} M4 lifecycle capture")
    checkpoints = value.get("checkpoints")
    if not isinstance(checkpoints, dict) or set(checkpoints) != set(
        bundle.checkpoint_by_scenario
    ):
        raise ContractError(f"invalid {role} M4 checkpoint scenario set")
    for scenario_key, expected_plan in bundle.checkpoint_by_scenario.items():
        records = checkpoints[scenario_key]
        if len(records) != len(expected_plan["steps"]):
            raise ContractError(f"invalid {role} M4 checkpoint count for {scenario_key}")
        for record, expected in zip(records, expected_plan["steps"], strict=True):
            if (
                record.get("sequence") != expected["sequence"]
                or record.get("action") != expected["action"]
                or record.get("checkpoint_fact") != expected["checkpoint_fact"]
                or record.get("run", {}).get("run_status")
                != expected["expected_run_status"]
                or record.get("run_id") != record.get("run", {}).get("run_id")
            ):
                raise ContractError(
                    f"invalid {role} M4 checkpoint ordering for {scenario_key}"
                )
    return value


def _validate_import_evidence(
    evidence: dict[str, Any],
    *,
    campaign_id: str,
    asset_chain: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    if (
        evidence.get("document_type") != "T01_PHASE1_MOCK_M4_IMPORT_EVIDENCE"
        or evidence.get("evidence_version")
        != "T01-PHASE1-MOCK-M4-IMPORT-EVIDENCE-v0.1"
        or evidence.get("campaign_id") != campaign_id
        or evidence.get("binding_profile") != _PROFILE
        or evidence.get("result") != "PASS"
        or evidence.get("blocker_count") != 0
        or evidence.get("secret_finding_count") != 0
        or evidence.get("scientific_compute") is not False
        or evidence.get("scientific_network_request_count") != 0
        or evidence.get("legacy_implementation_reuse_count") != 0
        or evidence.get("himat_backend_access_count") != 0
        or evidence.get("collision_policy") != "EXACT_EXPECTED_APP_ID_UPDATE_ONLY"
        or evidence.get("target", {}).get("environment") != "LOCAL_DIFY_DOCKER"
        or evidence.get("target", {}).get("dify_version") != "1.17.0"
        or evidence.get("target", {}).get("dsl_version") != "0.7.0"
    ):
        raise ContractError("M4 import/readback evidence guard failed")
    provider = evidence.get("provider", {})
    expected_tools = asset_chain["workflow_facts"]["tool_ids"]
    if (
        provider.get("server_identifier") != "t01-phase1-mock-mcp-v01"
        or provider.get("authed") is not True
        or provider.get("tool_count") != 26
        or provider.get("tool_ids") != expected_tools
    ):
        raise ContractError("M4 import/readback provider facts mismatch")
    expected_apps = {item["role"]: item for item in plan["expected_applications"]}
    applications = evidence.get("applications")
    if not isinstance(applications, list) or len(applications) != 2:
        raise ContractError("M4 import/readback must contain exactly two applications")
    if {item.get("role") for item in applications} != {"PRIMARY", "DEBUG"}:
        raise ContractError("M4 import/readback role set mismatch")
    if len({item.get("app_id") for item in applications}) != 2:
        raise ContractError("M4 import/readback application IDs are not unique")
    if len({item.get("draft_workflow_id") for item in applications}) != 2:
        raise ContractError("M4 import/readback draft workflow IDs are not unique")
    for app in applications:
        role = app.get("role")
        expected = expected_apps.get(role)
        if expected is None:
            raise ContractError("M4 import/readback contains an unknown workflow role")
        if (
            app.get("stable_workflow_id") != expected["stable_workflow_id"]
            or app.get("app_name") != expected["app_name"]
            or app.get("app_id") != expected["app_id"]
            or _UUID_PATTERN.fullmatch(str(app.get("draft_workflow_id", ""))) is None
            or app.get("provider_id") != "t01-phase1-mock-mcp-v01"
            or app.get("node_count") != 59
            or app.get("edge_count") != 79
            or app.get("semantic_edge_ids") != list(EDGE_IDS)
            or app.get("tool_ids") != expected_tools
            or app.get("warning_count") != 0
            or app.get("import_status") != "completed"
            or re.fullmatch(r"[0-9a-f]{64}", str(app.get("readback_export_sha256", "")))
            is None
            or app.get("source_semantic_graph_sha256")
            != app.get("readback_semantic_graph_sha256")
            or app.get("bound_sha256")
            != asset_chain["bound"][role]["sha256"]
        ):
            raise ContractError(f"M4 import/readback drift for {role}")


def _focus_stage(
    cases: list[CaseExecution],
    *,
    role: str,
    paths: dict[str, Path],
    bundle: SpecificationBundle,
) -> dict[str, Any]:
    harness = AcceptanceHarness(bundle=bundle)
    focus: list[dict[str, Any]] = []
    for case in cases:
        assertions = [
            item
            for item in case.acceptance_case["focus_assertions"]
            if M4_STAGE in item["applies_to"]
        ]
        for assertion in assertions:
            detail: str | None = None
            try:
                passed = harness._evaluate_case_assertion(assertion, case)
                if not passed:
                    detail = "catalog selector/operator predicate returned false"
            except Exception as exc:
                passed = False
                detail = f"{type(exc).__name__}: {exc}"
            focus.append(
                {
                    "assertion_id": assertion["assertion_id"],
                    "scenario_key": case.scenario["scenario_key"],
                    "operator": assertion["operator"],
                    "severity": assertion["severity"],
                    "status": "PASS" if passed else "FAIL",
                    "detail": detail,
                }
            )
    failures = [item for item in focus if item["status"] != "PASS"]
    capture_hashes, mappings = _instance_run_mappings(paths)
    envelope_by_dify_run: dict[str, str | None] = {}
    submitted_request_by_dify_run: dict[str, str | None] = {}
    for capture_key in ("submissions_path", "finalizations_path"):
        for item in load_json(paths[capture_key])["results"]:
            outputs = item.get("outputs") or {}
            envelope = outputs.get("envelope")
            submission = outputs.get("submission")
            if not isinstance(envelope, dict) and isinstance(submission, dict):
                envelope = submission.get("run")
            envelope_by_dify_run[item["dify_workflow_run_id"]] = (
                envelope.get("envelope_id") if isinstance(envelope, dict) else None
            )
            submitted_request_by_dify_run[item["dify_workflow_run_id"]] = item.get(
                "submitted_request_id"
            )
    for mapping in mappings:
        mapping["canonical_envelope_id"] = envelope_by_dify_run[
            mapping["dify_workflow_run_id"]
        ]
        mapping["submitted_request_id"] = submitted_request_by_dify_run[
            mapping["dify_workflow_run_id"]
        ]
    dify_run_ids = [item["dify_workflow_run_id"] for item in mappings]
    if len(mappings) != 27 or len(dify_run_ids) != len(set(dify_run_ids)):
        raise ContractError(f"{role} M4 Dify run mappings are not a 27-run bijection")
    submission_mappings = [
        item for item in mappings if item["capture_kind"] == "SUBMISSION"
    ]
    finalization_mappings = [
        item for item in mappings if item["capture_kind"] == "FINALIZATION"
    ]
    request_variant_count = len(bundle.request_variant_by_key)
    submitted_request_id_count = len(
        {item["submitted_request_id"] for item in submission_mappings}
    )
    if (
        len(submission_mappings) != 23
        or len(finalization_mappings) != 4
        or request_variant_count != 22
        or submitted_request_id_count != 23
        or any(item["submitted_request_id"] is not None for item in finalization_mappings)
    ):
        raise ContractError(f"{role} M4 request/finalization cardinality mismatch")
    case_results = []
    for case in cases:
        key = case.scenario["scenario_key"]
        status = "PASS" if all(
            item["status"] == "PASS" for item in focus if item["scenario_key"] == key
        ) else "FAIL"
        case_results.append(
            {
                "ordinal": case.fixture_case["ordinal"],
                "scenario_key": key,
                "submission_actions": [item["action"] for item in case.submissions],
                "final_run_id": case.final_run_id,
                "recovery_of_run_id": case.final_run["recovery_of_run_id"],
                "run_status": case.final_run["run_status"],
                "canonical_envelope_sha256": canonical_sha256(case.final_run),
                "status": status,
            }
        )
    return {
        "role": _ROLE_FACTS[role][0],
        "app_name": _ROLE_FACTS[role][1],
        "status": "PASS" if not failures else "FAIL",
        "case_count": len(cases),
        "submission_count": sum(len(case.submissions) for case in cases),
        "request_variant_count": request_variant_count,
        "submitted_request_id_count": submitted_request_id_count,
        "dify_submission_run_count": len(submission_mappings),
        "dify_finalization_run_count": len(finalization_mappings),
        "dify_run_count": len(mappings),
        "checkpoint_plan_count": sum(bool(case.checkpoints) for case in cases),
        "checkpoint_count": sum(len(case.checkpoints) for case in cases),
        "focus_assertion_count": len(focus),
        "focus_failure_count": len(failures),
        "capture_sha256": capture_hashes,
        "instance_run_mappings": mappings,
        "focus_assertions": focus,
        "case_results": case_results,
    }


def _aggregate_selector_view(
    main_cases: list[CaseExecution],
    debug_cases: list[CaseExecution],
    *,
    bundle: SpecificationBundle,
    workflow_facts: dict[str, Any],
    blocker_failures: int,
) -> dict[str, Any]:
    view = selector_view(main_cases[0], bundle)
    view["acceptance"].update(
        {
            "executed_cases": len(main_cases),
            "executed_submissions": sum(len(case.submissions) for case in main_cases),
            "blocker_failures": blocker_failures,
        }
    )
    view["workflow"].update(
        {
            "workflow_ids": workflow_facts["registered_workflow_ids"],
            "provider_id": workflow_facts["provider_id"],
            "tool_ids": workflow_facts["tool_ids"],
            "main": {
                "normalized_result": [
                    normalize_result(case.final_run) for case in main_cases
                ]
            },
            "debug": {
                "normalized_result": [
                    normalize_result(case.final_run) for case in debug_cases
                ]
            },
        }
    )
    return view


def _global_assertions(
    main_cases: list[CaseExecution],
    debug_cases: list[CaseExecution],
    *,
    bundle: SpecificationBundle,
    workflow_facts: dict[str, Any],
    preexisting_failure_count: int,
) -> list[dict[str, Any]]:
    harness = AcceptanceHarness(bundle=bundle)
    operators = AssertionOperatorRegistry()
    specs = [
        item
        for item in bundle.acceptance_catalog["global_assertions"]
        if M4_STAGE in item["applies_to"]
    ]
    expected_ids = [
        "t01_phase1_mock_v01.acceptance.global.004",
        *(
            f"t01_phase1_mock_v01.acceptance.global.{number:03d}"
            for number in range(8, 19)
        ),
    ]
    if [item.get("assertion_id") for item in specs] != expected_ids:
        raise ContractError("M4 must consume exactly 12 frozen global assertions")
    aggregate_ids = {
        "t01_phase1_mock_v01.acceptance.global.015",
        "t01_phase1_mock_v01.acceptance.global.016",
        "t01_phase1_mock_v01.acceptance.global.018",
    }
    results: list[dict[str, Any]] = []
    running_failures = preexisting_failure_count
    for assertion in specs:
        assertion_id = assertion["assertion_id"]
        detail: str | None = None
        try:
            if assertion_id in aggregate_ids:
                view = _aggregate_selector_view(
                    main_cases,
                    debug_cases,
                    bundle=bundle,
                    workflow_facts=workflow_facts,
                    blocker_failures=running_failures,
                )
                adapter = SelectorAdapter(view)
                actual = adapter.resolve(assertion["actual_selector"])
                expected = harness._expected_value(assertion["expected"], adapter)
                passed = operators.evaluate(assertion["operator"], actual, expected)
            else:
                passed = True
                for cases in (main_cases, debug_cases):
                    aggregate = harness._global_checks(cases).get(assertion_id)
                    if aggregate is None:
                        raise ContractError(
                            f"M4 has no aggregate implementation for {assertion_id}"
                        )
                    passed = passed and bool(aggregate()) and all(
                        harness._evaluate_case_assertion(assertion, case)
                        for case in cases
                    )
            if not passed:
                detail = "catalog selector/operator or aggregate invariant returned false"
        except Exception as exc:
            passed = False
            detail = f"{type(exc).__name__}: {exc}"
        if not passed:
            running_failures += 1
        results.append(
            {
                "assertion_id": assertion_id,
                "operator": assertion["operator"],
                "severity": assertion["severity"],
                "status": "PASS" if passed else "FAIL",
                "detail": detail,
            }
        )
    return results


def _parity(
    main_cases: list[CaseExecution], debug_cases: list[CaseExecution]
) -> dict[str, Any]:
    rows = []
    for main, debug in zip(main_cases, debug_cases, strict=True):
        difference = first_difference(
            normalize_result(main.final_run), normalize_result(debug.final_run)
        )
        rows.append(
            {
                "scenario_key": main.scenario["scenario_key"],
                "status": "PASS" if difference is None else "FAIL",
                "first_difference": difference,
                "main_sha256": canonical_sha256(normalize_result(main.final_run)),
                "debug_sha256": canonical_sha256(normalize_result(debug.final_run)),
            }
        )
    failures = [item for item in rows if item["status"] != "PASS"]
    return {
        "stage": "M4_MAIN_DEBUG_PARITY",
        "status": "PASS" if not failures else "FAIL",
        "case_count": len(rows),
        "global_016_status": "PASS" if not failures else "FAIL",
        "failure_count": len(failures),
        "results": rows,
    }


def _coverage(
    main_stage: dict[str, Any],
    debug_stage: dict[str, Any],
    *,
    bundle: SpecificationBundle,
) -> list[dict[str, Any]]:
    main = {item["scenario_key"]: item["status"] for item in main_stage["case_results"]}
    debug = {item["scenario_key"]: item["status"] for item in debug_stage["case_results"]}
    results = []
    for gate in bundle.acceptance_catalog["coverage_gates"]:
        required = gate["required_scenario_keys"]
        passed = (
            len(required) >= gate["minimum_case_count"]
            and all(main.get(key) == "PASS" for key in required)
            and all(debug.get(key) == "PASS" for key in required)
        )
        results.append(
            {
                "gate_id": gate["gate_id"],
                "category": gate["category"],
                "required_scenario_keys": deep_copy(required),
                "minimum_case_count": gate["minimum_case_count"],
                "status": "PASS" if passed else "FAIL",
                "detail": None if passed else "required main/debug case is missing or failed",
            }
        )
    return results


def assemble_campaign_result(
    campaign_id: str,
    *,
    bundle: SpecificationBundle | None = None,
) -> dict[str, Any]:
    """Evaluate new M4 target captures against the frozen M4 catalog stage."""

    bundle = bundle or SpecificationBundle.load()
    root, plan = _load_campaign(campaign_id)
    asset_chain_path = root / "asset-chain.json"
    asset_chain = load_json(asset_chain_path)
    current_chain = build_asset_chain(bundle)
    if canonical_sha256(asset_chain) != canonical_sha256(current_chain):
        raise ContractError("M4 asset chain changed after campaign preparation")

    import_path = root / "import-readback-evidence.json"
    import_evidence = load_json(import_path)
    _validate_import_evidence(
        import_evidence,
        campaign_id=campaign_id,
        asset_chain=asset_chain,
        plan=plan,
    )
    applications_by_role = {
        item["role"]: item for item in import_evidence["applications"]
    }
    target_workflow_facts = {
        "registered_workflow_ids": [
            applications_by_role["PRIMARY"]["stable_workflow_id"],
            applications_by_role["DEBUG"]["stable_workflow_id"],
        ],
        "provider_id": import_evidence["provider"]["server_identifier"],
        "tool_ids": import_evidence["provider"]["tool_ids"],
    }

    cases_by_role: dict[str, list[CaseExecution]] = {}
    stages: dict[str, dict[str, Any]] = {}
    for role in _ROLE_FACTS:
        role_plan = plan["roles"][role]
        role_paths = _role_paths(root, plan, role)
        paths = {
            "submissions_path": role_paths["submission_capture"],
            "finalizations_path": role_paths["finalization_capture"],
            "driver_path": role_paths["lifecycle_capture"],
        }
        _validate_capture(
            paths["submissions_path"],
            campaign_id=campaign_id,
            role=role,
            plan=plan,
            batch_path=role_paths["submission_batch"],
            expected_draft_workflow_id=applications_by_role[role_plan["role"]][
                "draft_workflow_id"
            ],
            expected_count=23,
        )
        _validate_capture(
            paths["finalizations_path"],
            campaign_id=campaign_id,
            role=role,
            plan=plan,
            batch_path=role_paths["finalization_batch"],
            expected_draft_workflow_id=applications_by_role[role_plan["role"]][
                "draft_workflow_id"
            ],
            expected_count=4,
        )
        _validate_driver(
            paths["driver_path"], campaign_id, role, bundle=bundle
        )
        cases = _case_executions(
            runtime_root=role_paths["runtime_root"],
            submissions_path=paths["submissions_path"],
            finalizations_path=paths["finalizations_path"],
            driver_path=paths["driver_path"],
            bundle=bundle,
        )
        cases_by_role[role] = cases
        stages[role] = _focus_stage(
            cases,
            role=role,
            paths=paths,
            bundle=bundle,
        )

    parity = _parity(cases_by_role["main"], cases_by_role["debug"])
    coverage = _coverage(stages["main"], stages["debug"], bundle=bundle)
    preexisting_failures = (
        stages["main"]["focus_failure_count"]
        + stages["debug"]["focus_failure_count"]
        + sum(item["status"] != "PASS" for item in coverage)
        + parity["failure_count"]
    )
    globals_ = _global_assertions(
        cases_by_role["main"],
        cases_by_role["debug"],
        bundle=bundle,
        workflow_facts=target_workflow_facts,
        preexisting_failure_count=preexisting_failures,
    )
    blocker_failures = (
        stages["main"]["focus_failure_count"]
        + stages["debug"]["focus_failure_count"]
        + sum(item["status"] != "PASS" for item in coverage)
        + sum(item["status"] != "PASS" for item in globals_)
    )
    result = {
        "$schema": M4_ACCEPTANCE_RESULT_SCHEMA_PATH.name,
        "document_type": "T01_PHASE1_MOCK_M4_REGRESSION_RESULT",
        "result_version": M4_RESULT_VERSION,
        "campaign_id": campaign_id,
        "binding_profile": _PROFILE,
        "status": "PASS" if blocker_failures == 0 else "FAIL",
        "implementation_state": "M4_REGRESSION_EXECUTED",
        "source_acceptance_catalog_version": bundle.acceptance_catalog[
            "acceptance_catalog_version"
        ],
        "execution_environment": {
            "target": "LOCAL_DIFY_DOCKER",
            "dify_version": "1.17.0",
            "dsl_version": "0.7.0",
            "transport": "MCP_STREAMABLE_HTTP_LOCALHOST",
            "clock_driven_branching": False,
        },
        "asset_chain": {
            **_hash_record(asset_chain_path),
            "status": asset_chain["status"],
        },
        "import_readback": {
            **_hash_record(import_path),
            "status": import_evidence["result"],
            "application_count": len(import_evidence["applications"]),
            "warning_count": sum(
                item["warning_count"] for item in import_evidence["applications"]
            ),
        },
        "main": stages["main"],
        "debug": stages["debug"],
        "global_assertion_count": len(globals_),
        "global_assertions": globals_,
        "coverage_gate_count": len(coverage),
        "coverage_gate_failure_count": sum(
            item["status"] != "PASS" for item in coverage
        ),
        "coverage_gates": coverage,
        "parity": parity,
        "scientific_execution_count": 0,
        "scientific_network_request_count": 0,
        "legacy_implementation_reuse_count": 0,
        "himat_backend_access_count": 0,
        "secret_finding_count": 0,
        "blocker_failure_count": blocker_failures,
    }
    schema = load_json(M4_ACCEPTANCE_RESULT_SCHEMA_PATH)
    validate_instance(result, schema, "M4 regression result")
    output = root / "T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json"
    if output.exists():
        raise ContractError("M4 campaign result already exists and cannot be overwritten")
    output.write_bytes(pretty_json_bytes(result))
    return result


def _iter_frozen_assets(campaign_id: str) -> Iterable[Path]:
    roots_and_patterns = (
        (PROJECT_ROOT / "src" / "t01_phase1_mock", "*.py"),
        (PROJECT_ROOT / "scripts" / "t01_phase1_mock", "*.py"),
        (PROJECT_ROOT / "tests" / "t01_phase1_mock", "*.py"),
        (PROJECT_ROOT / "工作流设计" / "02-数据契约", "T01_PHASE1_MOCK*"),
        (PROJECT_ROOT / "工作流设计" / "03-Dify实现", "T01_PHASE1_MOCK*"),
        (FIXTURE_ROOT, "*"),
        (PHASE1_RELEASE_ROOT / "templates", "*"),
        (PHASE1_RELEASE_ROOT / "config", "*"),
        (PHASE1_RELEASE_ROOT / "bound", "*"),
        (M3_LOCAL_PROFILE_ROOT, "*"),
    )
    seen: set[Path] = set()
    for root, pattern in roots_and_patterns:
        for path in root.rglob(pattern):
            if path.is_file() and "__pycache__" not in path.parts:
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield resolved
    for path in sorted(REGRESSION_ROOT.glob("*.json")):
        if path.resolve() != M4_FREEZE_MANIFEST_PATH.resolve():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved
    for path in campaign_root(campaign_id).rglob("*"):
        if path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved
    for path in (PROJECT_ROOT / "pyproject.toml", *M1_SPEC_SOURCE_PATHS):
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            yield resolved


def _required_frozen_paths(campaign_id: str) -> set[str]:
    root = campaign_root(campaign_id)
    paths = {
        PROJECT_ROOT / "pyproject.toml",
        PROJECT_ROOT / "src" / "t01_phase1_mock" / "dify" / "campaign.py",
        PROJECT_ROOT / "scripts" / "t01_phase1_mock" / "run_m4_campaign.py",
        PROJECT_ROOT / "scripts" / "t01_phase1_mock" / "dify_target_executor.py",
        PROJECT_ROOT / "scripts" / "t01_phase1_mock" / "import_dify_workflows.py",
        ASSET_REGISTRY_PATH,
        ACCEPTANCE_CATALOG_PATH,
        M2_ACCEPTANCE_RESULT_PATH,
        M3_ACCEPTANCE_RESULT_PATH,
        M3_BINDING_EVIDENCE_PATH,
        M3_IMPORT_EVIDENCE_PATH,
        M4_ACCEPTANCE_RESULT_SCHEMA_PATH,
        M4_FREEZE_MANIFEST_SCHEMA_PATH,
        BINDING_ROOT / "provider-bindings.local_dify_1_17.json",
        root / "campaign.json",
        root / "asset-chain.json",
        root / "import-readback-evidence.json",
        root / "regression-partitions.json",
        root / "T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json",
        *M1_SPEC_SOURCE_PATHS,
    }
    for role in _ROLE_FACTS:
        paths.update(
            {
                root / role / "submissions.batch.json",
                root / role / "submissions.capture.json",
                root / role / "lifecycle.capture.json",
                root / role / "finalizations.batch.json",
                root / role / "finalizations.capture.json",
            }
        )
    return {_project_relative(path) for path in paths}


def _validate_passing_result(result: dict[str, Any], campaign_id: str) -> None:
    if (
        result.get("campaign_id") != campaign_id
        or result.get("status") != "PASS"
        or result.get("blocker_failure_count") != 0
        or result.get("global_assertion_count") != 12
        or any(item.get("status") != "PASS" for item in result.get("global_assertions", []))
        or result.get("coverage_gate_count") != 10
        or result.get("coverage_gate_failure_count") != 0
        or any(item.get("status") != "PASS" for item in result.get("coverage_gates", []))
        or result.get("parity", {}).get("status") != "PASS"
        or result.get("parity", {}).get("failure_count") != 0
        or result.get("parity", {}).get("case_count") != 21
        or result.get("scientific_execution_count") != 0
        or result.get("scientific_network_request_count") != 0
        or result.get("legacy_implementation_reuse_count") != 0
        or result.get("himat_backend_access_count") != 0
        or result.get("secret_finding_count") != 0
    ):
        raise ContractError("cannot freeze an incomplete, failed, or out-of-scope M4 result")
    for role in _ROLE_FACTS:
        stage = result.get(role, {})
        if (
            stage.get("status") != "PASS"
            or stage.get("case_count") != 21
            or stage.get("submission_count") != 23
            or stage.get("request_variant_count") != 22
            or stage.get("submitted_request_id_count") != 23
            or stage.get("dify_submission_run_count") != 23
            or stage.get("dify_finalization_run_count") != 4
            or stage.get("dify_run_count") != 27
            or stage.get("checkpoint_plan_count") != 4
            or stage.get("checkpoint_count") != 16
            or stage.get("focus_assertion_count") != 44
            or stage.get("focus_failure_count") != 0
        ):
            raise ContractError(f"cannot freeze incomplete M4 {role} evidence")


def create_freeze_manifest(campaign_id: str, *, frozen_at: str) -> dict[str, Any]:
    """Freeze Mock v0.1 only after M4 and all four regression partitions pass."""

    try:
        frozen_time = datetime.fromisoformat(frozen_at.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ContractError("M4 frozen_at must be an ISO-8601 timestamp") from exc
    if frozen_time.tzinfo is None:
        raise ContractError("M4 frozen_at must include a timezone")
    if M4_FREEZE_MANIFEST_PATH.exists():
        raise ContractError("Phase 1 Mock v0.1 freeze manifest already exists")
    root, plan = _load_campaign(campaign_id)
    result_path = root / "T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json"
    partition_path = root / "regression-partitions.json"
    result = load_json(result_path)
    validate_instance(
        result,
        load_json(M4_ACCEPTANCE_RESULT_SCHEMA_PATH),
        "M4 regression result",
    )
    _validate_passing_result(result, campaign_id)
    asset_chain = load_json(root / "asset-chain.json")
    if canonical_sha256(asset_chain) != canonical_sha256(build_asset_chain()):
        raise ContractError("cannot freeze a campaign with asset-chain drift")
    import_evidence = load_json(root / "import-readback-evidence.json")
    _validate_import_evidence(
        import_evidence,
        campaign_id=campaign_id,
        asset_chain=asset_chain,
        plan=plan,
    )
    if result.get("asset_chain") != {
        **_hash_record(root / "asset-chain.json"),
        "status": "PASS",
    } or result.get("import_readback") != {
        **_hash_record(root / "import-readback-evidence.json"),
        "status": "PASS",
        "application_count": 2,
        "warning_count": 0,
    }:
        raise ContractError("M4 result evidence hash references drifted")
    partitions = load_json(partition_path)
    if (
        partitions.get("document_type") != "T01_PHASE1_MOCK_M4_PARTITION_RESULT"
        or partitions.get("result_version") != M4_PARTITION_RESULT_VERSION
        or partitions.get("campaign_id") != campaign_id
        or partitions.get("status") != "PASS"
    ):
        raise ContractError("cannot freeze without a passing four-partition result")
    required = {"documentation", "current_phase1", "legacy_full_mock", "legacy_s07"}
    records = partitions.get("partitions", [])
    if {item.get("partition_id") for item in records} != required or any(
        item.get("status") != "PASS" or item.get("exit_code") != 0 for item in records
    ):
        raise ContractError("freeze partition evidence is incomplete or failed")
    records_by_id = {item["partition_id"]: item for item in records}
    for partition_id in required:
        record = records_by_id[partition_id]
        expected_log = root / "checks" / f"{partition_id}.log"
        log_record = record.get("output_log", {})
        if (
            log_record.get("path") != _project_relative(expected_log)
            or log_record.get("sha256") != _hash_record(expected_log)["sha256"]
        ):
            raise ContractError(f"M4 partition log hash drift: {partition_id}")
    counts = {item["partition_id"]: item.get("passed_count") for item in records}
    if counts["legacy_full_mock"] != 74 or counts["legacy_s07"] != 41:
        raise ContractError("legacy or S07 frozen regression count changed")

    assets = sorted(
        (_hash_record(path) for path in _iter_frozen_assets(campaign_id)),
        key=lambda item: item["path"],
    )
    asset_paths = [item["path"] for item in assets]
    if len(asset_paths) != len(set(asset_paths)):
        raise ContractError("M4 frozen asset paths are not unique")
    missing_required = _required_frozen_paths(campaign_id) - set(asset_paths)
    if missing_required:
        raise ContractError(f"M4 frozen asset set is incomplete: {min(missing_required)}")
    manifest = {
        "$schema": M4_FREEZE_MANIFEST_SCHEMA_PATH.name,
        "document_type": "T01_PHASE1_MOCK_FREEZE_MANIFEST",
        "manifest_version": M4_FREEZE_MANIFEST_VERSION,
        "release_id": "T01-PHASE1-MOCK-v0.1",
        "release_state": "FROZEN",
        "frozen_at": frozen_at,
        "campaign_id": campaign_id,
        "binding_profile": _PROFILE,
        "m4_result": _hash_record(result_path),
        "regression_partitions": {
            "path": _project_relative(partition_path),
            "status": "PASS",
            "documentation_markdown_count": counts["documentation"],
            "current_phase1_test_count": counts["current_phase1"],
            "legacy_full_mock_test_count": counts["legacy_full_mock"],
            "legacy_s07_test_count": counts["legacy_s07"],
        },
        "frozen_asset_count": len(assets),
        "frozen_assets": assets,
        "acceptance": {
            "case_count_per_role": 21,
            "submission_count_per_role": 23,
            "request_variant_count_per_role": 22,
            "finalization_count_per_role": 4,
            "dify_run_count_per_role": 27,
            "checkpoint_plan_count_per_role": 4,
            "checkpoint_count_per_role": 16,
            "global_assertion_count": 12,
            "focus_assertion_count_per_role": 44,
            "coverage_gate_count": 10,
            "parity_case_count": 21,
            "blocker_failure_count": 0,
        },
        "scope_guards": {
            "data_classification": "MOCK_DATA",
            "scientific_compute": False,
            "scientific_execution_count": 0,
            "scientific_network_request_count": 0,
            "legacy_implementation_reuse_count": 0,
            "himat_backend_access_count": 0,
            "secret_finding_count": 0,
            "production_state": "NOT_DEPLOYED",
        },
        "next_release_gate": "PH1-REAL-W1_READY",
    }
    validate_instance(
        manifest,
        load_json(M4_FREEZE_MANIFEST_SCHEMA_PATH),
        "Phase 1 Mock freeze manifest",
    )
    M4_FREEZE_MANIFEST_PATH.write_bytes(pretty_json_bytes(manifest))
    return manifest


def verify_freeze_manifest() -> dict[str, Any]:
    manifest = load_json(M4_FREEZE_MANIFEST_PATH)
    validate_instance(
        manifest,
        load_json(M4_FREEZE_MANIFEST_SCHEMA_PATH),
        "Phase 1 Mock freeze manifest",
    )
    campaign_id = manifest["campaign_id"]
    root, _ = _load_campaign(campaign_id)
    records = manifest["frozen_assets"]
    record_paths = [item["path"] for item in records]
    if (
        manifest["frozen_asset_count"] != len(records)
        or record_paths != sorted(record_paths)
        or len(record_paths) != len(set(record_paths))
    ):
        raise ContractError("frozen Mock v0.1 asset index is inconsistent")
    forbidden_prefixes = ("legacy/", "var/")
    if any(
        path.startswith(forbidden_prefixes)
        or path == _project_relative(M4_FREEZE_MANIFEST_PATH)
        for path in record_paths
    ):
        raise ContractError("freeze manifest contains a forbidden mutable/legacy asset")
    missing_required = _required_frozen_paths(campaign_id) - set(record_paths)
    if missing_required:
        raise ContractError(f"freeze manifest misses required asset: {min(missing_required)}")
    failures = []
    for record in records:
        path = resolve_project_relative(record["path"], must_exist=False)
        if not path.is_file():
            failures.append(f"missing:{record['path']}")
            continue
        current = _hash_record(path)
        if current["bytes"] != record["bytes"] or current["sha256"] != record["sha256"]:
            failures.append(f"drift:{record['path']}")
    if failures:
        raise ContractError(f"frozen Mock v0.1 asset verification failed: {failures[0]}")
    result_path = root / "T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json"
    if manifest["m4_result"] != _hash_record(result_path):
        raise ContractError("freeze manifest M4 result reference drift")
    result = load_json(result_path)
    validate_instance(
        result,
        load_json(M4_ACCEPTANCE_RESULT_SCHEMA_PATH),
        "M4 regression result",
    )
    _validate_passing_result(result, campaign_id)
    partition_path = root / "regression-partitions.json"
    if manifest["regression_partitions"]["path"] != _project_relative(
        partition_path
    ):
        raise ContractError("freeze manifest partition reference drift")
    partitions = load_json(partition_path)
    partition_counts = {
        item["partition_id"]: item["passed_count"]
        for item in partitions.get("partitions", [])
    }
    expected_counts = {
        "documentation": manifest["regression_partitions"][
            "documentation_markdown_count"
        ],
        "current_phase1": manifest["regression_partitions"][
            "current_phase1_test_count"
        ],
        "legacy_full_mock": 74,
        "legacy_s07": 41,
    }
    if (
        partitions.get("status") != "PASS"
        or partitions.get("campaign_id") != campaign_id
        or partition_counts != expected_counts
    ):
        raise ContractError("freeze manifest partition counts drift")
    return {
        "status": "PASS",
        "release_state": manifest["release_state"],
        "campaign_id": campaign_id,
        "frozen_asset_count": manifest["frozen_asset_count"],
    }
