"""Independently audit one immutable W6 FoldX acceptance batch."""
import argparse
import math
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from t01_phase1_real.common import decode, encode, now, sha
from t01_phase1_real.development.foldx import policy


def artifact_bytes(case, result, logical_name):
    row = next(row for row in result["raw_artifacts"] if row["path"] == logical_name)
    path = case / "artifacts" / row["artifact"]["artifact_id"]
    raw = path.read_bytes()
    assert len(raw) == row["artifact"]["size_bytes"] and sha(raw) == row["artifact"]["sha256"]
    return raw


def fxout(raw):
    header, rows = None, []
    for line in raw.decode().splitlines():
        if line.startswith("Pdb\t"):
            header = line.split("\t")
        elif header and line.strip():
            parts = line.split("\t")
            assert len(parts) == len(header)
            rows.append(dict(zip(header, parts)))
    assert header and rows
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    batch = Path(args.batch).absolute()
    output = Path(args.output).absolute()
    assert batch.is_relative_to(REPO / "discovery/t01-phase1-real/w6")
    assert output.is_relative_to(REPO / "discovery/t01-phase1-real/w6") and not output.exists()
    index_raw = (batch / "index.json").read_bytes()
    index = decode(index_raw)
    assert index["status"] == "PASS" and index["scope"] == "W6_FOLDX_INDEPENDENT_ENGINEERING"
    assert index["production_status"] == "NOT_DEPLOYED" and not index["usable_for_pipeline"]
    assert not index["automatic_handoff"] and index["scientific_signoff"] is None
    assert not index["complete_n14"] and not index["complete_n17"] and index["scientific_gate"] == "NOT_EVALUATED"
    assert index["profile"] == policy.registered_profile()
    assert decode((batch / "assets.json").read_bytes()) == policy.verify_assets()
    for row in index["files"]:
        path = batch / row["path"]
        assert path.is_file() and path.stat().st_size == row["bytes"] and sha(path.read_bytes()) == row["sha256"]

    expected = {
        "structure-existing-local-reference": ("succeeded", None),
        "positionscan-two-positions": ("succeeded", None),
        "buildmodel-three-variants-five-runs": ("succeeded", None),
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
    assert {row["case"] for row in index["cases"]} == set(expected)
    published = 0
    for row in index["cases"]:
        assert (row["state"], row["error_code"]) == expected[row["case"]]
        case = batch / "cases" / row["case"]
        job = decode((case / "job.json").read_bytes())
        assert job["state"] == row["state"] and job["error_code"] == row["error_code"]
        assert not job["usable_for_pipeline"]
        for ref in job["artifacts"]:
            raw = (case / "artifacts" / ref["artifact_id"]).read_bytes()
            assert len(raw) == ref["size_bytes"] and sha(raw) == ref["sha256"]
            published += 1
        if (case / "result.json").is_file():
            result = decode((case / "result.json").read_bytes())
            assert not result["usable_for_pipeline"] and not result["automatic_handoff"]
            assert result["production_status"] == "NOT_DEPLOYED"
        if row["tool_id"] == policy.TOOL and job["attempt_id"]:
            execution = decode((case / "execution.json").read_bytes())
            assert execution["tree_stopped"] and execution["container_stopped"]

    scan_case = batch / "cases/positionscan-two-positions"
    scan = decode((scan_case / "result.json").read_bytes())
    assert scan["native_completeness"] == dict(complete_native_output=True, raw_rows=42, unique_rows=40, wt_duplicate_rows=2)
    rows = scan["ddg_results"]
    assert len(rows) == 40 and {(row["position"], row["mut"]) for row in rows} == {(position, aa) for position in (1, 3) for aa in policy.ALPHABET}
    assert all(row["confidence"] is None and math.isfinite(row["ddg_foldx"]) for row in rows)
    native_scan = artifact_bytes(scan_case, scan, "output/positionscan/PS_target_Repair_scanning_output.txt").decode().splitlines()
    assert len(native_scan) == 42 and sum(line.split("\t")[0][-1] in "eo" for line in native_scan) == 2
    assert len([row for row in scan["raw_artifacts"] if re.fullmatch(r"output/positionscan/[A-Z]{3}(1|3)_target_Repair\.pdb", row["path"])]) == 40
    assert artifact_bytes(scan_case, scan, "output/repair/target_Repair.pdb")

    build_case = batch / "cases/buildmodel-three-variants-five-runs"
    build = decode((build_case / "result.json").read_bytes())
    assert build["native_completeness"] == dict(complete_native_output=True, native_dif_rows=15, runs_per_variant=5, variants=3)
    assert len(build["variant_ddg"]) == 3
    dif_path = next(row["path"] for row in build["raw_artifacts"] if re.fullmatch(r"output/buildmodel/Dif_.*\.fxout", row["path"]))
    dif_rows = fxout(artifact_bytes(build_case, build, dif_path))
    assert len(dif_rows) == 15
    for variant_index, result in enumerate(build["variant_ddg"], 1):
        native = [float(row["total energy"]) for row in dif_rows if re.fullmatch(r"target_Repair_" + str(variant_index) + r"_[0-4]\.pdb", row["Pdb"])]
        assert len(native) == 5 and native == result["native_ddg_runs"]
        mean = sum(native) / 5
        std = (sum((value - mean) ** 2 for value in native) / 5) ** 0.5
        assert abs(mean - result["ddg_foldx"]) < 1e-12 and abs(std - result["std"]) < 1e-12
        assert result["runs"] == 5
    assert len([row for row in build["raw_artifacts"] if re.fullmatch(r"output/buildmodel/(WT_)?target_Repair_[1-3]_[0-4]\.pdb", row["path"])]) == 30
    assert artifact_bytes(build_case, build, "output/repair/target_Repair.pdb")

    for case_name in ("positionscan-two-positions", "buildmodel-three-variants-five-runs", "tool-failure-retry", "crash_after_receipt"):
        case = batch / "cases" / case_name
        result = decode((case / "result.json").read_bytes())
        inspect = decode(artifact_bytes(case, result, "container-inspect.json"))
        host = inspect["HostConfig"]
        assert host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
        assert host["Memory"] == host["MemorySwap"] == 2 * 1024**3
        assert host["NanoCpus"] == 2 * 10**9 and host["CpusetCpus"] == "0-1" and not host.get("DeviceRequests")
        assert inspect["Config"]["Image"] == policy.IMAGE and inspect["State"]["ExitCode"] == 0

    guard_names = {row["case"] for row in index["guards"]}
    assert len(index["guards"]) == 11 and {"idempotency-conflict", "published-result-tamper"}.issubset(guard_names)
    report = dict(
        status="PASS",
        audited_at=now(),
        batch=str(batch),
        index_sha256=sha(index_raw),
        indexed_files_verified=len(index["files"]),
        task_cases_verified=len(index["cases"]),
        request_and_integrity_guards_verified=len(index["guards"]),
        published_artifacts_verified=published,
        repairpdb_real_cases_verified=4,
        positionscan_native_rows=42,
        positionscan_unique_aa20_rows=40,
        buildmodel_variants=3,
        buildmodel_native_runs=15,
        lifecycle_cancel_timeout_recovery_verified=True,
        scientific_signoff=None,
        usable_for_pipeline=False,
        production_status="NOT_DEPLOYED",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(encode(report))
    print(encode(report).decode())


if __name__ == "__main__":
    main()
