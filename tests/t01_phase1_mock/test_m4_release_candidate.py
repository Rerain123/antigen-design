from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from t01_phase1_mock.dify import campaign
from t01_phase1_mock.jsonio import ContractError, canonical_sha256, deep_copy, load_json
from t01_phase1_mock.paths import (
    BOUND_ROOT,
    M4_ACCEPTANCE_RESULT_SCHEMA_PATH,
    M4_FREEZE_MANIFEST_PATH,
    PROJECT_ROOT,
)


CAMPAIGN_ID = "t01p1m-v01-reg-20260904-release-freeze-03"
CAMPAIGN_ROOT = (
    PROJECT_ROOT
    / "dify"
    / "t01-phase1-mock-v0.1"
    / "regression"
    / "runs"
    / CAMPAIGN_ID
)
RESULT_PATH = CAMPAIGN_ROOT / "T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json"


def _capture(role: str, kind: str) -> dict:
    return load_json(CAMPAIGN_ROOT / role / f"{kind}.capture.json")


def _envelopes(capture: dict):
    for item in capture["results"]:
        outputs = item["outputs"]
        envelope = outputs.get("envelope")
        if not isinstance(envelope, dict):
            submission = outputs.get("submission")
            if isinstance(submission, dict):
                envelope = submission.get("run")
        if isinstance(envelope, dict):
            yield envelope


def test_m4_release_candidate_result_is_schema_valid_and_complete() -> None:
    schema = load_json(M4_ACCEPTANCE_RESULT_SCHEMA_PATH)
    result = load_json(RESULT_PATH)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(result)
    campaign._validate_passing_result(result, CAMPAIGN_ID)
    assert [item["assertion_id"] for item in result["global_assertions"]] == [
        "t01_phase1_mock_v01.acceptance.global.004",
        *(f"t01_phase1_mock_v01.acceptance.global.{number:03d}" for number in range(8, 19)),
    ]
    assert all(item["status"] == "PASS" for item in result["global_assertions"])
    assert all(item["status"] == "PASS" for item in result["coverage_gates"])
    assert all(item["status"] == "PASS" for item in result["parity"]["results"])


def test_m4_target_capture_identity_order_and_cardinality_are_closed() -> None:
    plan = load_json(CAMPAIGN_ROOT / "campaign.json")
    imported = {
        item["role"]: item
        for item in load_json(CAMPAIGN_ROOT / "import-readback-evidence.json")[
            "applications"
        ]
    }
    for role, dify_role in (("main", "PRIMARY"), ("debug", "DEBUG")):
        role_plan = plan["roles"][role]
        submissions = _capture(role, "submissions")
        finalizations = _capture(role, "finalizations")
        assert submissions["invocation_count"] == 23
        assert finalizations["invocation_count"] == 4
        assert submissions["app_id"] == finalizations["app_id"] == role_plan["app_id"]
        assert (
            submissions["draft_workflow_id"]
            == finalizations["draft_workflow_id"]
            == imported[dify_role]["draft_workflow_id"]
        )
        assert [item["ordinal"] for item in submissions["results"]] == list(range(1, 24))
        assert [item["ordinal"] for item in finalizations["results"]] == list(range(1, 5))
        dify_ids = [
            item["dify_workflow_run_id"]
            for capture in (submissions, finalizations)
            for item in capture["results"]
        ]
        assert len(dify_ids) == len(set(dify_ids)) == 27
        submitted_ids = [item["submitted_request_id"] for item in submissions["results"]]
        assert len(submitted_ids) == len(set(submitted_ids)) == 23
        assert all(item["submitted_request_id"] is None for item in finalizations["results"])
        canonical_ids = [
            item["outputs"].get("canonical_run_id")
            for capture in (submissions, finalizations)
            for item in capture["results"]
            if item["outputs"].get("canonical_run_id") is not None
        ]
        assert not (set(dify_ids) & set(canonical_ids))


def test_m4_idempotent_replay_preserves_both_submission_and_existing_run_identity() -> None:
    for role in ("main", "debug"):
        rows = [
            item
            for item in _capture(role, "submissions")["results"]
            if item["scenario_key"] == "idempotent_replay"
        ]
        assert len(rows) == 2
        assert rows[0]["submitted_request_id"] != rows[1]["submitted_request_id"]
        assert rows[1]["outputs"]["submission_action"] == "RETURN_EXISTING_RUN"
        assert rows[1]["outputs"]["envelope"]["request_id"] == rows[0]["submitted_request_id"]
        assert rows[1]["outputs"]["canonical_run_id"] == rows[0]["outputs"]["canonical_run_id"]


def test_m4_main_and_debug_runtime_roots_are_distinct_and_not_m3_or_legacy() -> None:
    plan = load_json(CAMPAIGN_ROOT / "campaign.json")
    main = PROJECT_ROOT / plan["roles"]["main"]["runtime_root"]
    debug = PROJECT_ROOT / plan["roles"]["debug"]["runtime_root"]
    assert main.resolve() != debug.resolve()
    assert not main.is_symlink() and not debug.is_symlink()
    assert "m3-execution" not in main.as_posix() + debug.as_posix()
    assert "/legacy/" not in (main.as_posix() + debug.as_posix()).casefold()
    assert len(list((main / "runs").glob("*/record.json"))) == 22
    assert len(list((debug / "runs").glob("*/record.json"))) == 22
    assert not (main / "idempotency-index.json").samefile(
        debug / "idempotency-index.json"
    )


def test_m4_outputs_remain_mock_only_and_n01_has_no_remote_structure_fallback() -> None:
    n01_forbidden = re.compile(
        r"(?i)(https?://|rcsb|alphafold\.ebi|afdb|external_structure_id)"
    )
    observed = 0
    for role in ("main", "debug"):
        for kind in ("submissions", "finalizations"):
            for envelope in _envelopes(_capture(role, kind)):
                observed += 1
                assert envelope["data_classification"] == "MOCK_DATA"
                assert envelope["scientific_compute"] is False
                if envelope["result"] is not None:
                    assert envelope["result"]["handoff"]["status"] == "NOT_DEPLOYED"
                    assert envelope["result"]["handoff"]["delivered"] is False
                n01 = next(item for item in envelope["node_results"] if item["node_id"] == "N01")
                assert n01_forbidden.search(json.dumps(n01, ensure_ascii=False)) is None
    assert observed > 0


def test_m4_evidence_has_no_secret_token_absolute_binding_or_science_url() -> None:
    secret = re.compile(
        r"(?i)(bearer\s+[a-z0-9._-]+|sk-[a-z0-9]{8,}|password\s*[:=]|cookie\s*[:=])"
    )
    science_url = re.compile(
        r"(?i)https?://[^\s\"']*(uniprot|ncbi|alphafold|rcsb|blast|interpro|himat)"
    )
    absolute_windows = re.compile(r"(?i)[a-z]:\\\\")
    paths = list(CAMPAIGN_ROOT.rglob("*.json")) + list(BOUND_ROOT.rglob("*.yml"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "__T01_" not in text, path
        assert secret.search(text) is None, path
        assert science_url.search(text) is None, path
        assert absolute_windows.search(text) is None, path


def test_m4_import_readback_and_result_hash_tampering_are_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, plan = campaign._load_campaign(CAMPAIGN_ID)
    asset_chain = load_json(root / "asset-chain.json")
    import_evidence = load_json(root / "import-readback-evidence.json")
    tampered_import = deep_copy(import_evidence)
    tampered_import["applications"][0]["bound_sha256"] = "0" * 64
    with pytest.raises(ContractError, match="readback drift"):
        campaign._validate_import_evidence(
            tampered_import,
            campaign_id=CAMPAIGN_ID,
            asset_chain=asset_chain,
            plan=plan,
        )

    result_path = root / "T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json"
    tampered_result = deep_copy(load_json(result_path))
    tampered_result["import_readback"]["sha256"] = "0" * 64
    real_load = campaign.load_json

    def load_with_tampered_result(path: Path):
        if Path(path).resolve() == result_path.resolve():
            return deep_copy(tampered_result)
        return real_load(path)

    monkeypatch.setattr(campaign, "M4_FREEZE_MANIFEST_PATH", tmp_path / "freeze.json")
    monkeypatch.setattr(campaign, "load_json", load_with_tampered_result)
    with pytest.raises(ContractError, match="hash references drifted"):
        campaign.create_freeze_manifest(
            CAMPAIGN_ID, frozen_at="2026-09-04T00:00:00Z"
        )


def test_m4_asset_chain_or_bound_drift_is_blocked_before_freeze(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stored = load_json(CAMPAIGN_ROOT / "asset-chain.json")
    drifted = deep_copy(stored)
    drifted["bound"]["PRIMARY"]["sha256"] = "0" * 64
    monkeypatch.setattr(campaign, "M4_FREEZE_MANIFEST_PATH", tmp_path / "freeze.json")
    monkeypatch.setattr(campaign, "build_asset_chain", lambda bundle=None: drifted)
    with pytest.raises(ContractError, match="asset-chain drift"):
        campaign.create_freeze_manifest(
            CAMPAIGN_ID, frozen_at="2026-09-04T00:00:00Z"
        )


def test_m4_freeze_fails_closed_before_prerequisites_or_when_already_frozen() -> None:
    existed_before = M4_FREEZE_MANIFEST_PATH.exists()
    with pytest.raises((ContractError, FileNotFoundError)):
        campaign.create_freeze_manifest(
            CAMPAIGN_ID, frozen_at="2026-09-04T00:00:00Z"
        )
    assert M4_FREEZE_MANIFEST_PATH.exists() is existed_before


def test_m4_scope_counters_are_zero_and_result_hash_is_stable() -> None:
    result = load_json(RESULT_PATH)
    assert {
        key: result[key]
        for key in (
            "scientific_execution_count",
            "scientific_network_request_count",
            "legacy_implementation_reuse_count",
            "himat_backend_access_count",
            "secret_finding_count",
            "blocker_failure_count",
        )
    } == {
        "scientific_execution_count": 0,
        "scientific_network_request_count": 0,
        "legacy_implementation_reuse_count": 0,
        "himat_backend_access_count": 0,
        "secret_finding_count": 0,
        "blocker_failure_count": 0,
    }
    assert canonical_sha256(result) == canonical_sha256(load_json(RESULT_PATH))
