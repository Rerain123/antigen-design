"""W6 ThermoMPNN exact request, fixed assets and native SSM integrity."""
import copy
import csv
import io

import pytest

from t01_phase1_real.common import REPO, RuntimeFault, decode, encode, sha
from t01_phase1_real.development.thermompnn import policy


def artifact():
    return dict(
        artifact_id="t01p1r-artifact-" + "1" * 32,
        run_id="t01p1r-run-" + "1" * 32,
        job_id="t01p1r-job-" + "1" * 32,
        attempt_id="t01p1r-attempt-" + "1" * 32,
        role="result",
        media_type="application/json",
        evidence_kind="G0_REAL_OUTPUT",
        sha256="a" * 64,
        size_bytes=100,
    )


def body(sequence="ACDEFGHIK"):
    return dict(
        protein_sequence=sequence,
        user_sequence_id="engineering scan",
        structure_artifact=artifact(),
        scan_positions=list(range(1, len(sequence) + 1)),
        excluded_positions=[2],
        scope_source=dict(purpose="ENGINEERING_EXPLICIT_SCAN_SCOPE", source_id="test"),
        timeout_seconds=60,
    )


def test_exact_request_and_full_length_scope_not_artificially_capped():
    request = body("A" * 501)
    assert policy.request(encode(request)) == request


@pytest.mark.parametrize(
    "field,value",
    [
        ("structure_artifact", None),
        ("protein_sequence", "AX"),
        ("scan_positions", []),
        ("scan_positions", [2, 1]),
        ("scan_positions", [1, 1]),
        ("scan_positions", [10]),
        ("excluded_positions", [2, 2]),
        ("timeout_seconds", True),
        ("timeout_seconds", 901),
        ("scope_source", {}),
        ("model", "different"),
    ],
)
def test_exact_request_guards(field, value):
    request = body()
    request[field] = value
    with pytest.raises(RuntimeFault):
        policy.request(encode(request))


@pytest.mark.parametrize("damage", ["missing", "hash", "size"])
def test_asset_integrity_verifier_with_private_registry(tmp_path, monkeypatch, damage):
    data = b"isolated ThermoMPNN asset"
    path = tmp_path / "model.pt"
    path.write_bytes(data)
    receipt = dict(commit=policy.COMMIT, image=policy.IMAGE, model=policy.MODEL, files=[dict(path="model.pt", bytes=len(data), sha256=sha(data))])
    (tmp_path / "assets.json").write_bytes(encode(receipt))
    monkeypatch.setattr(policy, "HERE", tmp_path)
    monkeypatch.setattr(policy, "REPO", tmp_path)
    assert policy.verify_assets() == receipt
    if damage == "missing":
        path.unlink()
    elif damage == "size":
        path.write_bytes(data + b"x")
    else:
        path.write_bytes(b"X" + data[1:])
    with pytest.raises(RuntimeFault):
        policy.verify_assets()


def test_offline_gpu_command_and_registry_contract():
    from t01_phase1_real.development import docker
    from t01_phase1_real.development.registry import spec

    job = dict(tool_id=policy.TOOL, run_id="run", job_id="job", attempt_id="attempt", execution_identity="execution")
    command = docker.thermompnn_command(REPO / "tmp", job, "native-test", 60)
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command and command[command.index("--gpus") + 1] == "device=0"
    assert policy.IMAGE in command and spec(policy.TOOL).NODE == "N17"
    assert any("target=/app/local.yaml,readonly" in item for item in command)


@pytest.fixture
def native_recording(monkeypatch):
    folder = REPO / "discovery/t01-phase1-real/w6/thermompnn-integration-20260908/acceptance-r01/cases/monomer-full-ssm"
    job = decode((folder / "job.json").read_bytes())
    published = decode((folder / "result.json").read_bytes())
    files = {row["path"]: (folder / "artifacts" / row["artifact"]["artifact_id"]).read_bytes() for row in published["raw_artifacts"]}
    monkeypatch.setattr(policy, "registered_profile", lambda: job["execution_profile"])
    return job, decode(files["input.json"]), files, published["execution"]


def test_recorded_real_full_ssm_and_engine_internal_ranking(native_recording):
    from t01_phase1_real.development.thermompnn.result import result

    value = result(*native_recording)
    scan = value["scan"]
    assert value["status"] == "predicted_unreviewed" and scan["complete_native_output"]
    assert scan["native_prediction_count"] == 180 and scan["selected_prediction_count"] == 140
    assert scan["effective_positions"] == [1, 3, 4, 5, 6, 7, 9]
    assert not value["usable_for_pipeline"] and not value["automatic_handoff"]


@pytest.mark.parametrize("damage", ["row-missing", "wt-nonzero", "wrong-wt", "network", "source-hash", "native-input", "command"])
def test_native_corruption_is_quarantined(native_recording, damage):
    from t01_phase1_real.development.thermompnn.result import result

    job, request, files, execution = native_recording
    runtime = decode(files["output/runtime.json"])
    csv_path = "output/native/ThermoMPNN_inference_target.csv"
    if damage in {"row-missing", "wt-nonzero", "wrong-wt"}:
        rows = list(csv.DictReader(io.StringIO(files[csv_path].decode())))
        if damage == "row-missing":
            rows.pop()
        elif damage == "wt-nonzero":
            next(row for row in rows if row["wildtype"] == row["mutation"])["ddG_pred"] = "1.0"
        else:
            rows[0]["wildtype"] = "Y"
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["", "Model", "Dataset", "ddG_pred", "position", "wildtype", "mutation", "pdb", "chain"])
        writer.writeheader()
        writer.writerows(rows)
        files[csv_path] = output.getvalue().encode()
        observation = decode(files["output/observation.json"])
        observation["native_csv_sha256"] = sha(files[csv_path])
        files["output/observation.json"] = encode(observation)
    elif damage == "network":
        runtime["network_interfaces"].append([2, "eth0"])
    elif damage == "source-hash":
        runtime["source_sha256"]["analysis/custom_inference.py"] = "0" * 64
    elif damage == "native-input":
        runtime["native_input_sha256"]["target.pdb"] = "0" * 64
    else:
        runtime["commands"]["scan"]["argv"].append("--threshold")
    runtime["native_output_sha256"] = {
        name[7:]: sha(raw)
        for name, raw in files.items()
        if name.startswith("output/") and name != "output/runtime.json"
    }
    files["output/runtime.json"] = encode(runtime)
    value = result(job, request, files, execution)
    assert value["scan"] is None and value["null_reason"] == "OUTPUT_INVALID"
