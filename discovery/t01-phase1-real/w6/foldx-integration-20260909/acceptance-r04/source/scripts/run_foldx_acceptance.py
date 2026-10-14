"""W6 FoldX real offline RepairPDB, BuildModel, PositionScan and lifecycle acceptance."""
import argparse
import copy
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from t01_phase1_real.common import RuntimeFault, decode, encode, now, sha
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.foldx import policy
from t01_phase1_real.winprocess import alive
from run_deeptmhmm_acceptance import until
from structure_integration_cases import SEQUENCE, metadata


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value if isinstance(value, bytes) else encode(value))


def scan_request(structure_ref, source_id="W6 FoldX explicit PositionScan", **changes):
    value = dict(
        protein_sequence=SEQUENCE,
        user_sequence_id=source_id,
        structure_artifact=structure_ref,
        mode="positionscan",
        fixed_positions=[2],
        scan_positions=[1, 3],
        variants=[],
        scope_source=dict(purpose="ENGINEERING_STABILITY_SCOPE", source_id=source_id),
        timeout_seconds=300,
    )
    value.update(changes)
    return value


def build_request(structure_ref, source_id="W6 FoldX explicit BuildModel", one=False):
    variants = [dict(variant_id="single-A1G", mutations=[dict(position=1, wt=SEQUENCE[0], mut="G")])]
    if not one:
        variants += [
            dict(variant_id="double-D3A-E4G", mutations=[dict(position=3, wt=SEQUENCE[2], mut="A"), dict(position=4, wt=SEQUENCE[3], mut="G")]),
            dict(variant_id="single-K9A", mutations=[dict(position=9, wt=SEQUENCE[8], mut="A")]),
        ]
    return dict(
        protein_sequence=SEQUENCE,
        user_sequence_id=source_id,
        structure_artifact=structure_ref,
        mode="buildmodel",
        fixed_positions=[2],
        scan_positions=[],
        variants=variants,
        scope_source=dict(purpose="ENGINEERING_STABILITY_SCOPE", source_id=source_id),
        timeout_seconds=300,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--batch", required=True)
    args = parser.parse_args()
    root = Path(args.root).absolute()
    batch = Path(args.batch).absolute()
    assert root.is_relative_to(REPO / "var/t01-phase1-real") and not root.exists()
    assert batch.is_relative_to(REPO / "discovery/t01-phase1-real/w6") and not batch.exists()
    batch.mkdir(parents=True)
    runtime = Runtime(root)
    entries, guards = [], []
    profile = policy.registered_profile()
    write(batch / "profile.json", profile)
    write(batch / "rules.json", policy.registered_rules())
    write(batch / "assets.json", policy.verify_assets())
    engine_info = docker.call(root, ["info", "--format", "{{json .}}"], 30)
    image_info = docker.call(root, ["image", "inspect", policy.IMAGE], 30)
    assert engine_info.returncode == 0 and image_info.returncode == 0
    write(batch / "environment.json", dict(
        captured_at=now(),
        docker_info=decode(engine_info.stdout),
        image_inspect=decode(image_info.stdout)[0],
        expected_image_id=policy.IMAGE,
        isolation=dict(network="none", read_only_root=True, cpu_set="0-1", cpus=2, memory_bytes=2 * 1024**3, gpu_requested=False),
    ))
    sources = [
        *policy.HERE.glob("*.py"),
        *[policy.HERE.parent / name for name in ("runtime.py", "registry.py", "contracts.py", "cli.py", "docker.py", "supervisor.py")],
        *list((policy.HERE.parent / "proteinmpnn").glob("*.py")),
        *list((REPO / "src/t01_structure_mapping").glob("*.py")),
        REPO / "requirements/foldx.Dockerfile",
        Path(__file__),
        REPO / "scripts/structure_integration_cases.py",
        REPO / "tests/test_foldx_development.py",
    ]
    for path in sources:
        write(batch / "source" / path.relative_to(REPO), path.read_bytes())

    def finish(name, job, state="succeeded", error=None, kind="REAL_OFFLINE_FOLDX"):
        final = runtime.wait(job["job_id"], 900)
        value = runtime.result(final["job_id"]) if final["artifacts"] else None
        write(batch / "cases" / name / "job.json", final)
        write(batch / "cases" / name / "events.json", runtime.events(final["job_id"]))
        if final["attempt_id"]:
            write(batch / "cases" / name / "execution.json", runtime.execution(final["job_id"]))
        if value:
            write(batch / "cases" / name / "result.json", value)
        for ref in final["artifacts"]:
            raw = runtime.artifact_bytes(final["job_id"], ref["artifact_id"])
            assert len(raw) == ref["size_bytes"] and sha(raw) == ref["sha256"]
            write(batch / "cases" / name / "artifacts" / ref["artifact_id"], raw)
        assert final["state"] == state and final["error_code"] == error, (name, final, value)
        assert not final["usable_for_pipeline"]
        if state == "succeeded":
            assert final["scientific_disposition"] == "review_required"
        if value:
            assert not value["usable_for_pipeline"] and not value["automatic_handoff"]
            assert value["production_status"] == "NOT_DEPLOYED"
            if final["tool_id"] == policy.TOOL:
                assert value["scientific_gate"] == "NOT_EVALUATED"
        if final["attempt_id"]:
            assert runtime.execution(final["job_id"])["tree_stopped"]
        native_runtime_path = root / runtime.attempt_path(final) / "output/runtime.json" if final["attempt_id"] else None
        native_runtime = decode(native_runtime_path.read_bytes()) if native_runtime_path and native_runtime_path.is_file() else None
        row = dict(
            case=name,
            kind=kind,
            job_id=final["job_id"],
            tool_id=final["tool_id"],
            state=state,
            error_code=error,
            mode=value and value.get("mode"),
            native_completeness=value and value.get("native_completeness"),
            repair_completed=bool(value and value.get("repair")),
            tool_invoked=bool(native_runtime and native_runtime.get("tool_invoked")),
            artifacts_verified=len(final["artifacts"]),
        )
        entries.append(row)
        print(encode(row).decode(), flush=True)
        return final, value

    def submit(name, body, fault=None):
        write(batch / "requests" / (name + ".json"), body)
        job = runtime.submit_sequence(encode(body), name, policy.TOOL)
        runtime._development_fault = fault
        try:
            runtime.dispatch(job["job_id"])
        finally:
            runtime._development_fault = None
        return runtime.get(job["job_id"])

    def run(name, body, **kwargs):
        return finish(name, submit(name, body), **kwargs)

    def reject(name, body):
        write(batch / "rejected-requests" / (name + ".json"), body)
        try:
            runtime.submit_sequence(encode(body), name, policy.TOOL)
        except RuntimeFault as exc:
            row = dict(case=name, state="PASS", error_code=exc.code, diagnostic=str(exc), rejected_before_admission=True)
            guards.append(row)
            print(encode(row).decode(), flush=True)
        else:
            raise AssertionError("Invalid FoldX request accepted: " + name)

    structure_path = REPO / "discovery/t01-phase1-real/w5/esm-if1-assets-20260908/reference.pdb"
    structure_data = structure_path.read_bytes()
    structure_body = metadata(fmt="PDB", source="unknown")
    structure_body["source_declaration"]["note"] = "EXISTING_LOCAL_ENGINEERING_STRUCTURE; not a scientific reference"
    write(batch / "inputs/existing-local-reference.structure", structure_data)
    write(batch / "inputs/existing-local-reference.json", structure_body)
    write(batch / "inputs/existing-local-reference-provenance.json", dict(kind="EXISTING_LOCAL_ENGINEERING_STRUCTURE", path=str(structure_path), sha256=sha(structure_data)))
    structure_job = runtime.submit_structure(encode(structure_body), "structure-existing-local-reference", structure_data)
    runtime.dispatch(structure_job["job_id"])
    structure_final, _ = finish("structure-existing-local-reference", structure_job, kind="REAL_STRUCTURE_PARSER")
    structure_ref = next(ref for ref in structure_final["artifacts"] if ref["role"] == "result")

    scan_body = scan_request(structure_ref)
    scan_job, scan_value = run("positionscan-two-positions", scan_body)
    assert scan_value["status"] == "positionscan_unreviewed"
    assert scan_value["native_completeness"] == dict(raw_rows=42, unique_rows=40, wt_duplicate_rows=2, complete_native_output=True)
    assert len(scan_value["ddg_results"]) == 40
    assert {row["position"] for row in scan_value["ddg_results"]} == {1, 3}
    assert all(row["confidence"] is None for row in scan_value["ddg_results"])
    assert runtime.submit_sequence(encode(scan_body), "positionscan-two-positions", policy.TOOL)["job_id"] == scan_job["job_id"]
    changed = dict(scan_body, user_sequence_id="changed")
    try:
        runtime.submit_sequence(encode(changed), "positionscan-two-positions", policy.TOOL)
    except RuntimeFault as exc:
        assert exc.code == "IDEMPOTENCY_CONFLICT"
        guards.append(dict(case="idempotency-conflict", error_code=exc.code))
    else:
        raise AssertionError("Changed duplicate accepted")

    build_body = build_request(structure_ref)
    _, build_value = run("buildmodel-three-variants-five-runs", build_body)
    assert build_value["status"] == "buildmodel_unreviewed"
    assert build_value["native_completeness"] == dict(variants=3, runs_per_variant=5, native_dif_rows=15, complete_native_output=True)
    assert len(build_value["variant_ddg"]) == 3
    assert all(row["runs"] == 5 and len(row["native_ddg_runs"]) == 5 for row in build_value["variant_ddg"])

    invalid = {
        "missing-structure": dict(scan_body, structure_artifact=None),
        "empty-scan": dict(scan_body, scan_positions=[]),
        "unsorted-scan": dict(scan_body, scan_positions=[3, 1]),
        "fixed-scan-overlap": dict(scan_body, fixed_positions=[1, 2]),
        "bad-sequence": dict(scan_body, protein_sequence="X" + SEQUENCE[1:]),
        "float-timeout": dict(scan_body, timeout_seconds=1.0),
        "mixed-mode": dict(scan_body, variants=[dict(variant_id="bad", mutations=[dict(position=3, wt=SEQUENCE[2], mut="A")])]),
        "missing-scope-source": {key: value for key, value in scan_body.items() if key != "scope_source"},
    }
    forged = copy.deepcopy(scan_body)
    forged["structure_artifact"]["sha256"] = "0" * 64
    invalid["forged-structure-ref"] = forged
    for name, body in invalid.items():
        reject(name, body)

    lifecycle_body = build_request(structure_ref, "W6 FoldX lifecycle", one=True)
    failed, _ = finish("tool-failure", submit("tool-failure", lifecycle_body, "tool_failure"), "failed", "TOOL_FAILED", "CONTROLLED_FAULT")
    retry = runtime.control(encode(dict(contract_version="0.1.0", operation="retry", job_id=failed["job_id"], idempotency_key="tool-failure-retry")))
    runtime.dispatch(retry["job_id"])
    finish("tool-failure-retry", retry, kind="LIFECYCLE_RETRY_REAL_OFFLINE_FOLDX")
    finish("corrupt-output", submit("corrupt-output", lifecycle_body, "corrupt_output"), "failed", "OUTPUT_INVALID", "CONTROLLED_FAULT")

    queued = runtime.submit_sequence(encode(lifecycle_body), "queued-cancel", policy.TOOL)
    runtime.control(encode(dict(contract_version="0.1.0", operation="cancel", job_id=queued["job_id"], idempotency_key="queued-cancel")))
    finish("queued-cancel", queued, "cancelled", "CANCELLED", "LIFECYCLE_NO_NATIVE_EXECUTION")
    running = submit("running-cancel", lifecycle_body, "slow_worker")
    until(lambda: (root / runtime.attempt_path(running) / "output/runtime_started.json").is_file())
    runtime.control(encode(dict(contract_version="0.1.0", operation="cancel", job_id=running["job_id"], idempotency_key="running-cancel")))
    finish("running-cancel", running, "cancelled", "CANCELLED", "CONTROLLED_SLOW_WORKER")
    finish("timeout", submit("timeout", dict(lifecycle_body, timeout_seconds=1), "slow_worker"), "timed_out", "TIMEOUT", "CONTROLLED_SLOW_WORKER")
    for fault in ("crash_after_start", "crash_after_receipt"):
        crashed = submit(fault, lifecycle_body, fault)
        until(lambda: alive(runtime.execution(crashed["job_id"]).get("supervisor")) is False)
        runtime.recover(crashed["job_id"])
        finish(
            fault,
            crashed,
            "failed" if fault == "crash_after_start" else "succeeded",
            "INTERRUPTED" if fault == "crash_after_start" else None,
            "CONTROLLED_SUPERVISOR_CRASH",
        )

    def cli(name, parameters):
        argv = [sys.executable, "-X", "utf8", str(REPO / "scripts/t01_runtime.py"), "--root", str(root), *parameters]
        process = subprocess.run(argv, capture_output=True, timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch / "cli" / (name + ".json"), dict(argv=argv, exit_code=process.returncode, stdout=process.stdout.decode(), stderr=process.stderr.decode()))
        assert process.returncode == 0
        return decode(process.stdout)

    queried = cli("query", ["result", "--job-id", scan_job["job_id"]])
    assert queried["native_completeness"] == scan_value["native_completeness"]

    pending = runtime.submit_sequence(encode(scan_body), "late-source-tamper", policy.TOOL)
    with runtime._db() as database:
        path = root / database.execute("SELECT relative_path FROM artifacts WHERE id=?", (structure_ref["artifact_id"],)).fetchone()[0]
    with path.open("ab") as stream:
        stream.write(b" controlled W6 FoldX source tamper")
    runtime.dispatch(pending["job_id"])
    finish("late-source-tamper", pending, "failed", "HASH_MISMATCH", "CONTROLLED_SOURCE_TAMPER")
    result_ref = next(ref for ref in scan_job["artifacts"] if ref["role"] == "result")
    with runtime._db() as database:
        path = root / database.execute("SELECT relative_path FROM artifacts WHERE id=?", (result_ref["artifact_id"],)).fetchone()[0]
    with path.open("ab") as stream:
        stream.write(b" controlled W6 FoldX publication tamper")
    try:
        runtime.result(scan_job["job_id"])
    except RuntimeFault as exc:
        assert exc.code == "HASH_MISMATCH"
        guards.append(dict(case="published-result-tamper", error_code=exc.code))
    else:
        raise AssertionError("Tampered result accepted")

    assert profile == policy.registered_profile() and docker.inspect(root, policy.SLOT) is None
    write(batch / "guards.json", guards)
    inventory = [
        dict(path=path.relative_to(batch).as_posix(), bytes=path.stat().st_size, sha256=sha(path.read_bytes()))
        for path in sorted(batch.rglob("*")) if path.is_file()
    ]
    write(batch / "index.json", dict(
        status="PASS",
        completed_at=now(),
        scope="W6_FOLDX_INDEPENDENT_ENGINEERING",
        runtime_root=str(root),
        profile=profile,
        cases=entries,
        guards=guards,
        files=inventory,
        scientific_signoff=None,
        usable_for_pipeline=False,
        automatic_handoff=False,
        production_status="NOT_DEPLOYED",
        complete_n14=False,
        complete_n17=False,
        scientific_gate="NOT_EVALUATED",
    ))
    print("W6_FOLDX_ENGINEERING_ACCEPTANCE_PASS", flush=True)


if __name__ == "__main__":
    main()
