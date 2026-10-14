from __future__ import annotations

import uuid
from pathlib import Path, PurePosixPath

import pytest
from jsonschema import Draft202012Validator

from t01_phase1_mock.dify import campaign
from t01_phase1_mock.dify.transport import Phase1MockMCPServer
from t01_phase1_mock.jsonio import ContractError, deep_copy, load_json, pretty_json_bytes
from t01_phase1_mock.paths import (
    M4_ACCEPTANCE_RESULT_SCHEMA_PATH,
    M4_FREEZE_MANIFEST_SCHEMA_PATH,
)


def test_m4_schemas_are_valid_draft_2020_12() -> None:
    for path in (
        M4_ACCEPTANCE_RESULT_SCHEMA_PATH,
        M4_FREEZE_MANIFEST_SCHEMA_PATH,
    ):
        Draft202012Validator.check_schema(load_json(path))


def test_m4_transport_forbids_same_port_listener_reuse() -> None:
    assert Phase1MockMCPServer.allow_reuse_address is False


@pytest.mark.parametrize(
    "value",
    (
        "master-reg-20260904-a",
        "t01p1m-v01-reg-20260904-UPPER",
        "t01p1m-v01-reg-20260904-bad_slug",
        "t01p1m-v01-reg-20260230-invalid-date",
        "t01p1m-v01-reg-20260904-../escape",
        "T01P1M-v01-reg-20260904-case",
    ),
)
def test_m4_campaign_identity_rejects_old_invalid_and_escaping_values(value: str) -> None:
    with pytest.raises(ContractError):
        campaign.validate_campaign_id(value)


def test_m4_asset_chain_recomputes_the_m3_takeover_hashes(spec_bundle) -> None:
    chain = campaign.build_asset_chain(spec_bundle)
    assert chain["status"] == "PASS"
    assert chain["source_baseline"]["source_count"] == 21
    assert chain["fixture_counts"] == {
        "input_fixture_count": 2,
        "request_variant_count": 22,
        "attempt_fixture_count": 326,
        "payload_file_count": 350,
    }
    assert chain["asset_registry"]["sha256"] == (
        "ea851f97cacb304a2927d45ef85363d7c44b49f792b10172bfe7792f960672a2"
    )
    assert chain["templates"]["PRIMARY"]["sha256"] == (
        "d14037d202b8cb715560ed9fd1302867796ab7db2d54e3d2d673f8d9626a7e61"
    )
    assert chain["templates"]["DEBUG"]["sha256"] == (
        "09162ff71fad27340ce08e1b73dd4a2caa3b0cdba8a013830c541e6d2a6332f3"
    )
    assert chain["binding_manifest"]["sha256"] == (
        "025d5859b01befbc77540a4d32a0ef01479c34484af481a615cf8b126395855a"
    )
    assert chain["bound"]["PRIMARY"]["sha256"] == (
        "c1bcbb1f2a156d79ac3fcd592c08e5415ca5b671c2e47c339672c11567b48fa6"
    )
    assert chain["bound"]["DEBUG"]["sha256"] == (
        "d7883fbc19ff6aa66a875e7fb60f88be2ce46945c4b919c4057332f71752ad1b"
    )
    assert chain["generator_check"] == chain["binder_check"] == "PASS"
    assert chain["main_debug_normalized_business_graph"] == "EQUAL"


def test_m4_prepare_is_once_only_and_rejects_cross_role_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spec_bundle,
) -> None:
    project = tmp_path / "project"
    runs = project / "dify" / "release" / "regression" / "runs"
    m3_import = project / "m3" / "import-evidence.json"
    m3_import.parent.mkdir(parents=True)
    source = load_json(campaign.M3_IMPORT_EVIDENCE_PATH)
    m3_import.write_bytes(pretty_json_bytes(source))

    def resolve(relative_path: str, *, must_exist: bool = False) -> Path:
        posix = PurePosixPath(relative_path)
        if posix.is_absolute() or ".." in posix.parts or not posix.parts:
            raise ContractError("unsafe test path")
        value = project.joinpath(*posix.parts)
        if must_exist and not value.exists():
            raise FileNotFoundError(value)
        for parent in (project, *value.parents):
            if parent == project.parent:
                break
            if parent.exists() and parent.is_symlink():
                raise ContractError("test symlink rejected")
        return value.resolve()

    monkeypatch.setattr(campaign, "PROJECT_ROOT", project)
    monkeypatch.setattr(campaign, "M4_RUNS_ROOT", runs)
    monkeypatch.setattr(campaign, "M3_IMPORT_EVIDENCE_PATH", m3_import)
    monkeypatch.setattr(campaign, "resolve_project_relative", resolve)
    monkeypatch.setattr(campaign, "build_asset_chain", lambda bundle=None: {"status": "PASS"})
    transport_health = {
        "status": "ok",
        "server": "t01-phase1-mock-v01",
        "tool_count": 26,
        "mock_only": True,
        "scientific_compute": False,
    }
    campaign_id = "t01p1m-v01-reg-20990101-protocol-test"
    plan = campaign.prepare_campaign(
        campaign_id,
        transport_health=transport_health,
        prepared_at="2099-01-01T00:00:00Z",
        bundle=spec_bundle,
    )
    assert plan["state"] == "PREPARED"
    assert plan["roles"]["main"]["runtime_root"] != plan["roles"]["debug"]["runtime_root"]
    with pytest.raises(ContractError, match="already exists"):
        campaign.prepare_campaign(
            campaign_id,
            transport_health=transport_health,
            prepared_at="2099-01-01T00:00:00Z",
            bundle=spec_bundle,
        )

    plan_path = runs / campaign_id / "campaign.json"
    original = load_json(plan_path)
    forbidden_runtime_values = (
        original["roles"]["main"]["runtime_root"],
        "var/t01-phase1-mock-v0.1/m3-execution/main/runtime",
        "legacy/s07/runtime",
    )
    for forbidden in forbidden_runtime_values:
        tampered = deep_copy(original)
        tampered["roles"]["debug"]["runtime_root"] = forbidden
        plan_path.write_bytes(pretty_json_bytes(tampered))
        with pytest.raises(ContractError, match="path drift|distinct|legacy"):
            campaign._load_campaign(campaign_id)


def test_m4_capture_validator_rejects_duplicate_dify_run_ids(
    tmp_path: Path,
    case_executions,
) -> None:
    campaign_id = "t01p1m-v01-reg-20260904-capture-test"
    app_id = "a5fa1d0e-45a9-469e-aef9-4c55639f9eba"
    draft_id = "181b59ac-a9f6-427a-a261-8a690c9c6409"
    stable_id = "t01_phase1_mock_v01.workflow.main"
    plan = {
        "roles": {
            "main": {
                "role": "PRIMARY",
                "app_name": "T01_Phase1_Mock_v0.1",
                "app_id": app_id,
                "stable_workflow_id": stable_id,
            }
        }
    }
    invocations = []
    results = []
    for ordinal, case in enumerate(case_executions[:2], start=1):
        run = deep_copy(case.final_run)
        invocations.append(
            {
                "scenario_key": case.scenario["scenario_key"],
                "submission_key": "checkpoint_finalize_observation",
                "operation": "FINALIZE_EXISTING",
                "request_json": "",
                "run_id_override": run["run_id"],
            }
        )
        results.append(
            {
                "ordinal": ordinal,
                "scenario_key": case.scenario["scenario_key"],
                "submission_key": "checkpoint_finalize_observation",
                "operation": "FINALIZE_EXISTING",
                "submitted_request_id": None,
                "dify_workflow_run_id": str(uuid.uuid4()),
                "dify_status": "succeeded",
                "dify_error": None,
                "total_steps": 3,
                "outputs": {
                    "envelope": run,
                    "canonical_run_id": run["run_id"],
                    "submission_action": "FINALIZE_EXISTING",
                },
            }
        )
    batch_path = tmp_path / "batch.json"
    capture_path = tmp_path / "capture.json"
    batch_path.write_bytes(
        pretty_json_bytes(
            {
                "document_type": "T01_PHASE1_MOCK_M4_DIFY_BATCH",
                "batch_version": "T01-PHASE1-MOCK-M4-DIFY-BATCH-v0.1",
                "campaign_id": campaign_id,
                "app_name": "T01_Phase1_Mock_v0.1",
                "role": "PRIMARY",
                "expected_app_id": app_id,
                "stable_workflow_id": stable_id,
                "invocation_count": 2,
                "invocations": invocations,
            }
        )
    )
    capture = {
        "document_type": "T01_PHASE1_MOCK_M4_DIFY_CAPTURE",
        "capture_version": "T01-PHASE1-MOCK-M4-DIFY-CAPTURE-v0.1",
        "campaign_id": campaign_id,
        "app_name": "T01_Phase1_Mock_v0.1",
        "role": "PRIMARY",
        "app_id": app_id,
        "draft_workflow_id": draft_id,
        "stable_workflow_id": stable_id,
        "status": "PASS",
        "invocation_count": 2,
        "failure_count": 0,
        "results": results,
    }
    capture_path.write_bytes(pretty_json_bytes(capture))
    campaign._validate_capture(
        capture_path,
        campaign_id=campaign_id,
        role="main",
        plan=plan,
        batch_path=batch_path,
        expected_draft_workflow_id=draft_id,
        expected_count=2,
    )
    baseline = deep_copy(capture)
    capture["results"][1]["dify_workflow_run_id"] = capture["results"][0][
        "dify_workflow_run_id"
    ]
    capture_path.write_bytes(pretty_json_bytes(capture))
    with pytest.raises(ContractError, match="duplicate"):
        campaign._validate_capture(
            capture_path,
            campaign_id=campaign_id,
            role="main",
            plan=plan,
            batch_path=batch_path,
            expected_draft_workflow_id=draft_id,
            expected_count=2,
        )
    tamper_cases = []
    for label in (
        "campaign",
        "role",
        "app",
        "count",
        "order",
        "failed",
        "scenario",
    ):
        changed = deep_copy(baseline)
        if label == "campaign":
            changed["campaign_id"] = "t01p1m-v01-reg-20260904-other"
        elif label == "role":
            changed["role"] = "DEBUG"
        elif label == "app":
            changed["app_id"] = "52dd71b0-9b76-4c85-b50c-e5aead4b293b"
        elif label == "count":
            changed["invocation_count"] = 1
        elif label == "order":
            changed["results"].reverse()
        elif label == "failed":
            changed["results"][0]["dify_status"] = "failed"
        else:
            changed["results"][0]["scenario_key"] = "tampered"
        tamper_cases.append(changed)
    for changed in tamper_cases:
        capture_path.write_bytes(pretty_json_bytes(changed))
        with pytest.raises(ContractError):
            campaign._validate_capture(
                capture_path,
                campaign_id=campaign_id,
                role="main",
                plan=plan,
                batch_path=batch_path,
                expected_draft_workflow_id=draft_id,
                expected_count=2,
            )
