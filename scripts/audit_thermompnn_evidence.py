"""Independent read-only audit of a completed W6 ThermoMPNN evidence batch."""
import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from t01_phase1_real.common import decode, encode, now, sha
from t01_phase1_real.development.thermompnn import policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    batch = Path(args.batch).absolute()
    output = Path(args.output).absolute()
    assert batch.is_relative_to(REPO / "discovery/t01-phase1-real/w6")
    assert output.is_relative_to(REPO / "discovery/t01-phase1-real/w6") and not output.exists()
    index = decode((batch / "index.json").read_bytes())
    failures = []
    for item in index["files"]:
        path = batch / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha(path.read_bytes()) != item["sha256"]:
            failures.append("indexed-file:" + item["path"])
    artifact_count = 0
    source_count = 0
    for case in index["cases"]:
        folder = batch / "cases" / case["case"]
        job = decode((folder / "job.json").read_bytes())
        for ref in job["artifacts"]:
            artifact_count += 1
            path = folder / "artifacts" / ref["artifact_id"]
            if not path.is_file() or path.stat().st_size != ref["size_bytes"] or sha(path.read_bytes()) != ref["sha256"]:
                failures.append("published-artifact:" + case["case"] + ":" + ref["artifact_id"])
    for path in sorted((batch / "source").rglob("*")):
        if path.is_file():
            source_count += 1
            current = REPO / path.relative_to(batch / "source")
            if not current.is_file() or current.read_bytes() != path.read_bytes():
                failures.append("source-snapshot:" + path.relative_to(batch).as_posix())
    if decode((batch / "profile.json").read_bytes()) != policy.registered_profile():
        failures.append("execution-profile")
    if decode((batch / "rules.json").read_bytes()) != policy.registered_rules():
        failures.append("rule-profile")
    if decode((batch / "assets.json").read_bytes()) != policy.verify_assets():
        failures.append("asset-registry")
    main_result = decode((batch / "cases/monomer-full-ssm/result.json").read_bytes())
    scan = main_result["scan"]
    if not (
        scan["complete_native_output"]
        and scan["native_prediction_count"] == 180
        and scan["expected_native_prediction_count"] == 180
        and scan["selected_prediction_count"] == 140
        and scan["ranked_nonself_prediction_count"] == 133
        and scan["effective_positions"] == [1, 3, 4, 5, 6, 7, 9]
        and scan["raw_ddg_sign_preserved"]
        and not main_result["usable_for_pipeline"]
        and not main_result["automatic_handoff"]
    ):
        failures.append("monomer-full-ssm-semantics")
    multi = decode((batch / "cases/multichain-r39-skip/result.json").read_bytes())
    if not (
        multi["status"] == "skipped_multichain_unreviewed"
        and multi["scan"]["reason_code"] == "R39_THERMOMPNN_MONOMER_ONLY"
        and multi["scan"]["engine_runtime"]["tool_invoked"] is False
    ):
        failures.append("r39-multichain-skip")
    expected_states = {
        "tool-failure": ("failed", "TOOL_FAILED"),
        "tool-failure-retry": ("succeeded", None),
        "corrupt-output": ("failed", "OUTPUT_INVALID"),
        "queued-cancel": ("cancelled", "CANCELLED"),
        "running-cancel": ("cancelled", "CANCELLED"),
        "timeout": ("timed_out", "TIMEOUT"),
        "crash_after_start": ("failed", "INTERRUPTED"),
        "crash_after_receipt": ("succeeded", None),
        "late-source-tamper": ("failed", "HASH_MISMATCH"),
    }
    cases = {item["case"]: item for item in index["cases"]}
    for name, expected in expected_states.items():
        actual = cases.get(name)
        if actual is None or (actual["state"], actual["error_code"]) != expected:
            failures.append("lifecycle:" + name)
    result = dict(
        status="PASS" if not failures else "FAIL",
        audited_at=now(),
        batch=str(batch),
        index_sha256=sha((batch / "index.json").read_bytes()),
        indexed_files_verified=len(index["files"]),
        published_artifacts_verified=artifact_count,
        source_snapshots_verified=source_count,
        task_cases_verified=len(index["cases"]),
        request_guards_verified=len(index["guards"]),
        native_full_ssm_rows=scan["native_prediction_count"],
        selected_rows=scan["selected_prediction_count"],
        ranked_nonself_rows=scan["ranked_nonself_prediction_count"],
        r39_multichain_invoked=False,
        scientific_signoff=None,
        usable_for_pipeline=False,
        production_status="NOT_DEPLOYED",
        failures=failures,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(encode(result))
    print(encode(result).decode())
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
