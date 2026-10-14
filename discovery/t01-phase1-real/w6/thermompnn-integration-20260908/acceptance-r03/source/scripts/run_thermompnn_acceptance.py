"""W6 ThermoMPNN real offline SSM, source guards and lifecycle acceptance."""
import argparse
import copy
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from t01_phase1_real.common import RuntimeFault, decode, encode, now, sha
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.thermompnn import policy
from t01_phase1_real.winprocess import alive
from run_deeptmhmm_acceptance import until
from structure_integration_cases import SEQUENCE, cif, geometry, metadata


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value if isinstance(value, bytes) else encode(value))


def request(structure_ref, source_id="W6 explicit engineering scan", **changes):
    value = dict(
        protein_sequence=SEQUENCE,
        user_sequence_id=source_id,
        structure_artifact=structure_ref,
        scan_positions=list(range(1, len(SEQUENCE) + 1)),
        excluded_positions=[2, 8],
        scope_source=dict(purpose="ENGINEERING_EXPLICIT_SCAN_SCOPE", source_id=source_id),
        timeout_seconds=300,
    )
    value.update(changes)
    return value


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
    rt = Runtime(root)
    entries, guards = [], []
    profile = policy.registered_profile()
    write(batch / "profile.json", profile)
    write(batch / "rules.json", policy.registered_rules())
    write(batch / "assets.json", policy.verify_assets())
    sources = [
        *policy.HERE.glob("*.py"),
        *policy.HERE.glob("*.json"),
        *[policy.HERE.parent / name for name in ("runtime.py", "registry.py", "contracts.py", "cli.py", "docker.py", "supervisor.py")],
        *list((policy.HERE.parent / "proteinmpnn").glob("*.py")),
        *list((REPO / "src/t01_structure_mapping").glob("*.py")),
        REPO / "requirements/thermompnn.Dockerfile",
        Path(__file__),
        REPO / "scripts/structure_integration_cases.py",
        REPO / "tests/test_thermompnn_development.py",
    ]
    for path in sources:
        write(batch / "source" / path.relative_to(REPO), path.read_bytes())

    def finish(name, job, state="succeeded", error=None, kind="REAL_OFFLINE_THERMOMPNN"):
        final = rt.wait(job["job_id"], 900)
        value = rt.result(final["job_id"]) if final["artifacts"] else None
        write(batch / "cases" / name / "job.json", final)
        write(batch / "cases" / name / "events.json", rt.events(final["job_id"]))
        if final["attempt_id"]:
            write(batch / "cases" / name / "execution.json", rt.execution(final["job_id"]))
        if value:
            write(batch / "cases" / name / "result.json", value)
        for ref in final["artifacts"]:
            raw = rt.artifact_bytes(final["job_id"], ref["artifact_id"])
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
            assert rt.execution(final["job_id"])["tree_stopped"]
        scan = value and value.get("scan")
        row = dict(
            case=name,
            kind=kind,
            job_id=final["job_id"],
            tool_id=final["tool_id"],
            state=state,
            error_code=error,
            native_prediction_count=scan and scan["native_prediction_count"],
            selected_prediction_count=scan and scan["selected_prediction_count"],
            tool_invoked=bool(scan and scan["engine_runtime"]["tool_invoked"]),
            artifacts_verified=len(final["artifacts"]),
        )
        entries.append(row)
        print(encode(row).decode(), flush=True)
        return final, value

    def submit(name, body, fault=None):
        write(batch / "requests" / (name + ".json"), body)
        job = rt.submit_sequence(encode(body), name, policy.TOOL)
        rt._development_fault = fault
        try:
            rt.dispatch(job["job_id"])
        finally:
            rt._development_fault = None
        return rt.get(job["job_id"])

    def run(name, body, **kwargs):
        return finish(name, submit(name, body), **kwargs)

    def structure(name, data, body, provenance):
        write(batch / "inputs" / (name + ".structure"), data)
        write(batch / "inputs" / (name + ".json"), body)
        write(batch / "inputs" / (name + "-provenance.json"), provenance)
        job = rt.submit_structure(encode(body), "structure-" + name, data)
        rt.dispatch(job["job_id"])
        final, _ = finish("structure-" + name, job, kind="REAL_STRUCTURE_PARSER")
        return next(ref for ref in final["artifacts"] if ref["role"] == "result")

    def reject(name, body):
        write(batch / "rejected-requests" / (name + ".json"), body)
        try:
            rt.submit_sequence(encode(body), name, policy.TOOL)
        except RuntimeFault as exc:
            row = dict(case=name, state="PASS", error_code=exc.code, diagnostic=str(exc), rejected_before_admission=True)
            guards.append(row)
            print(encode(row).decode(), flush=True)
        else:
            raise AssertionError("Invalid ThermoMPNN request accepted: " + name)

    structure_path = REPO / "discovery/t01-phase1-real/w5/esm-if1-assets-20260908/reference.pdb"
    structure_data = structure_path.read_bytes()
    structure_body = metadata(fmt="PDB", source="unknown")
    structure_body["source_declaration"]["note"] = "EXISTING_LOCAL_ENGINEERING_STRUCTURE; not a scientific reference"
    structure_ref = structure(
        "existing-local-reference",
        structure_data,
        structure_body,
        dict(kind="EXISTING_LOCAL_ENGINEERING_STRUCTURE", path=str(structure_path), sha256=sha(structure_data)),
    )
    body = request(structure_ref)
    main_job, main_value = run("monomer-full-ssm", body)
    scan = main_value["scan"]
    assert scan["complete_native_output"] and scan["native_prediction_count"] == 20 * len(SEQUENCE)
    assert scan["effective_positions"] == [1, 3, 4, 5, 6, 7, 9]
    assert scan["selected_prediction_count"] == 140 and scan["ranked_nonself_prediction_count"] == 133
    assert scan["native_wt_self_count"] == len(SEQUENCE)
    assert {row["author_address"]["auth_seq_id"] for row in scan["predictions"]} == {"42", "44", "45", "46", "47", "48", "50"}
    assert any(row["ddg_thermompnn"] < 0 for row in scan["predictions"])
    assert any(row["ddg_thermompnn"] > 0 for row in scan["predictions"])
    assert all(row["rank_thermompnn"] is None for row in scan["predictions"] if row["is_wt_self"])
    assert rt.submit_sequence(encode(body), "monomer-full-ssm", policy.TOOL)["job_id"] == main_job["job_id"]
    try:
        rt.submit_sequence(encode(dict(body, user_sequence_id="changed")), "monomer-full-ssm", policy.TOOL)
    except RuntimeFault as exc:
        assert exc.code == "IDEMPOTENCY_CONFLICT"
        guards.append(dict(case="idempotency-conflict", error_code=exc.code))
    else:
        raise AssertionError("Changed duplicate accepted")

    invalid = {
        "missing-structure": dict(body, structure_artifact=None),
        "empty-scan": dict(body, scan_positions=[]),
        "unsorted-scan": dict(body, scan_positions=[2, 1]),
        "duplicate-scan": dict(body, scan_positions=[1, 1]),
        "outside-sequence": dict(body, scan_positions=[10]),
        "bad-sequence": dict(body, protein_sequence="X" + SEQUENCE[1:]),
        "float-timeout": dict(body, timeout_seconds=1.0),
        "caller-model": dict(body, model="other"),
        "missing-scope-source": {key: value for key, value in body.items() if key != "scope_source"},
    }
    forged = copy.deepcopy(body)
    forged["structure_artifact"]["sha256"] = "0" * 64
    invalid["forged-structure-ref"] = forged
    for name, changed in invalid.items():
        reject(name, changed)

    failed, _ = finish("tool-failure", submit("tool-failure", body, "tool_failure"), "failed", "TOOL_FAILED", "CONTROLLED_FAULT")
    retry = rt.control(encode(dict(contract_version="0.1.0", operation="retry", job_id=failed["job_id"], idempotency_key="tool-failure-retry")))
    rt.dispatch(retry["job_id"])
    finish("tool-failure-retry", retry, kind="LIFECYCLE_RETRY_REAL_OFFLINE_THERMOMPNN")
    finish("corrupt-output", submit("corrupt-output", body, "corrupt_output"), "failed", "OUTPUT_INVALID", "CONTROLLED_FAULT")

    queued = rt.submit_sequence(encode(body), "queued-cancel", policy.TOOL)
    rt.control(encode(dict(contract_version="0.1.0", operation="cancel", job_id=queued["job_id"], idempotency_key="queued-cancel")))
    finish("queued-cancel", queued, "cancelled", "CANCELLED", "LIFECYCLE_NO_NATIVE_EXECUTION")
    running = submit("running-cancel", body, "slow_worker")
    until(lambda: (root / rt.attempt_path(running) / "output/runtime_started.json").is_file())
    rt.control(encode(dict(contract_version="0.1.0", operation="cancel", job_id=running["job_id"], idempotency_key="running-cancel")))
    finish("running-cancel", running, "cancelled", "CANCELLED", "CONTROLLED_SLOW_WORKER")
    finish("timeout", submit("timeout", dict(body, timeout_seconds=1), "slow_worker"), "timed_out", "TIMEOUT", "CONTROLLED_SLOW_WORKER")
    for fault in ("crash_after_start", "crash_after_receipt"):
        crashed = submit(fault, body, fault)
        until(lambda: alive(rt.execution(crashed["job_id"]).get("supervisor")) is False)
        rt.recover(crashed["job_id"])
        finish(
            fault,
            crashed,
            "failed" if fault == "crash_after_start" else "succeeded",
            "INTERRUPTED" if fault == "crash_after_start" else None,
            "CONTROLLED_SUPERVISOR_CRASH",
        )

    rows = geometry()
    for row in rows:
        position = int(row["label_seq_id"])
        row.update(
            auth_asym_id="B",
            label_asym_id="LABEL_B",
            auth_seq_id="100" if position <= 2 else str(100 + position * 3),
            pdbx_PDB_ins_code="A" if position == 2 else ".",
        )
    context = [
        dict(
            row,
            auth_asym_id="A",
            label_asym_id="LABEL_A",
            auth_comp_id="ALA",
            label_comp_id="ALA",
            Cartn_y=str(float(row["Cartn_y"]) + 30),
        )
        for row in rows
    ]
    multi_ref = structure(
        "multichain",
        cif(context + rows),
        metadata(source="unknown", context=["A", "B"], selection=dict(model_index=0, chain_selector="B")),
        dict(kind="SYNTHETIC_MULTICHAIN_ENGINEERING_GEOMETRY", target_chain="B"),
    )
    _, multi = run("multichain-r39-skip", request(multi_ref, "R39 multi-chain guard"))
    assert multi["status"] == "skipped_multichain_unreviewed"
    assert multi["scan"]["reason_code"] == "R39_THERMOMPNN_MONOMER_ONLY"
    assert not multi["scan"]["engine_runtime"]["tool_invoked"]

    def cli(name, parameters):
        argv = [sys.executable, "-X", "utf8", str(REPO / "scripts/t01_runtime.py"), "--root", str(root), *parameters]
        process = subprocess.run(argv, capture_output=True, timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch / "cli" / (name + ".json"), dict(argv=argv, exit_code=process.returncode, stdout=process.stdout.decode(), stderr=process.stderr.decode()))
        assert process.returncode == 0
        return decode(process.stdout)

    queried = cli("query", ["result", "--job-id", main_job["job_id"]])
    assert queried["scan"]["comparison_set_sha256"] == scan["comparison_set_sha256"]

    pending = rt.submit_sequence(encode(body), "late-source-tamper", policy.TOOL)
    with rt._db() as database:
        path = root / database.execute("SELECT relative_path FROM artifacts WHERE id=?", (structure_ref["artifact_id"],)).fetchone()[0]
    with path.open("ab") as stream:
        stream.write(b" controlled W6 source tamper")
    rt.dispatch(pending["job_id"])
    finish("late-source-tamper", pending, "failed", "HASH_MISMATCH", "CONTROLLED_SOURCE_TAMPER")
    result_ref = next(ref for ref in main_job["artifacts"] if ref["role"] == "result")
    with rt._db() as database:
        path = root / database.execute("SELECT relative_path FROM artifacts WHERE id=?", (result_ref["artifact_id"],)).fetchone()[0]
    with path.open("ab") as stream:
        stream.write(b" controlled W6 publication tamper")
    try:
        rt.result(main_job["job_id"])
    except RuntimeFault as exc:
        assert exc.code == "HASH_MISMATCH"
        guards.append(dict(case="published-result-tamper", error_code=exc.code))
    else:
        raise AssertionError("Tampered result accepted")

    assert profile == policy.registered_profile() and docker.inspect(root, policy.SLOT) is None
    write(batch / "guards.json", guards)
    inventory = [
        dict(path=path.relative_to(batch).as_posix(), bytes=path.stat().st_size, sha256=sha(path.read_bytes()))
        for path in sorted(batch.rglob("*"))
        if path.is_file()
    ]
    write(
        batch / "index.json",
        dict(
            status="PASS",
            completed_at=now(),
            scope="W6_THERMOMPNN_INDEPENDENT_ENGINEERING",
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
        ),
    )
    print("W6_THERMOMPNN_ENGINEERING_ACCEPTANCE_PASS", flush=True)


if __name__ == "__main__":
    main()
