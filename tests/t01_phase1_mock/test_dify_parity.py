from __future__ import annotations

from t01_phase1_mock.dify.normalization import OBSERVABILITY_ALLOWLIST, first_difference, normalize_result
from t01_phase1_mock.jsonio import load_json
from t01_phase1_mock.paths import M3_ACCEPTANCE_RESULT_PATH


def test_main_debug_have_21_exact_canonical_results() -> None:
    result = load_json(M3_ACCEPTANCE_RESULT_PATH)
    parity = result["parity"]
    assert parity["status"] == "PASS"
    assert parity["global_016_status"] == "PASS"
    assert parity["case_count"] == 21
    assert parity["failure_count"] == 0
    assert all(item["status"] == "PASS" for item in parity["results"])
    assert all(item["first_difference"] is None for item in parity["results"])
    assert all(item["main_sha256"] == item["debug_sha256"] for item in parity["results"])


def test_normalization_drops_only_frozen_observability_envelope() -> None:
    assert OBSERVABILITY_ALLOWLIST == (
        "/dify_observability/app_id",
        "/dify_observability/workflow_id",
        "/dify_observability/workflow_run_id",
        "/dify_observability/role",
    )
    business = {"run_id": "r1", "run_status": "COMPLETED"}
    main = {**business, "dify_observability": {"role": "PRIMARY", "app_id": "a"}}
    debug = {**business, "dify_observability": {"role": "DEBUG", "app_id": "b"}}
    assert normalize_result(main) == normalize_result(debug) == business
    changed = {**debug, "run_status": "FAILED"}
    assert first_difference(normalize_result(main), normalize_result(changed)) == "/run_status"

