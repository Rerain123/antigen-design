"""W6 FoldX request, assets, command and recorded native-output tests."""
import copy

import pytest

from t01_phase1_real.common import REPO, RuntimeFault, decode, encode
from t01_phase1_real.development.foldx import policy


def artifact():
    return dict(artifact_id="a" * 32, run_id="r" * 32, job_id="j" * 32, attempt_id="t" * 32,
        role="result", media_type="application/json", evidence_kind="G0_REAL_OUTPUT", sha256="a" * 64, size_bytes=100)


def scan_body():
    return dict(protein_sequence="ACDEFGHIK", user_sequence_id="foldx-test", structure_artifact=artifact(), mode="positionscan",
        fixed_positions=[2], scan_positions=[1, 3, 4], variants=[], scope_source=dict(purpose="ENGINEERING_STABILITY_SCOPE", source_id="test"), timeout_seconds=60)


def test_exact_positionscan_request():
    assert policy.request(encode(scan_body()))["mode"] == "positionscan"


def test_buildmodel_request_and_wt_binding():
    request = scan_body(); request.update(mode="buildmodel", scan_positions=[], variants=[dict(variant_id="v1", mutations=[dict(position=3, wt="D", mut="A")])])
    assert policy.request(encode(request))["variants"][0]["variant_id"] == "v1"


@pytest.mark.parametrize("change", [
    {"mode": "buildmodel"}, {"scan_positions": []}, {"fixed_positions": [2, 1]},
    {"variants": [dict(variant_id="v1", mutations=[dict(position=3, wt="X", mut="A")])]},
])
def test_request_guards(change):
    request = scan_body(); request.update(change)
    with pytest.raises(RuntimeFault): policy.request(encode(request))


def test_registered_candidate_assets_are_hash_verified():
    receipt = policy.verify_assets()
    assert receipt["license_basis"] == "USER_ATTESTED_ACADEMIC_VERSION"
    assert receipt["executable"]["sha256"] == "5309d81c3f08b8405d172153aaf9792a244c06f98387c9d57a104302a9cef2cf"
    assert receipt["image_status"] == "BUILT_VERIFIED"


def test_cpu_command_has_no_gpu_and_mounts_candidate_package():
    from t01_phase1_real.development import docker
    job = dict(tool_id=policy.TOOL, run_id="run", job_id="job", attempt_id="attempt", execution_identity="execution")
    command = docker.foldx_command(REPO / "tmp", job, "native-test", 60)
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command and "--gpus" not in command
    assert policy.IMAGE in command and any("target=/app,readonly" in item for item in command)


def test_native_histidine_tautomer_codes_are_normalized():
    from t01_phase1_real.development.foldx.result import NATIVE_MUTATION
    assert NATIVE_MUTATION["e"] == NATIVE_MUTATION["o"] == "H"


def recording(case):
    folder = REPO / "discovery/t01-phase1-real/w6/foldx-integration-20260909/acceptance-r04/cases" / case
    job = decode((folder / "job.json").read_bytes())
    published = decode((folder / "result.json").read_bytes())
    files = {row["path"]: (folder / "artifacts" / row["artifact"]["artifact_id"]).read_bytes() for row in published["raw_artifacts"]}
    return job, decode(files["input.json"]), files, published["execution"]


def test_recorded_real_positionscan_exact_aa20_and_repair():
    from t01_phase1_real.development.foldx.result import result
    value = result(*recording("positionscan-two-positions"))
    assert value["status"] == "positionscan_unreviewed"
    assert value["native_completeness"] == dict(complete_native_output=True, raw_rows=42, unique_rows=40, wt_duplicate_rows=2)
    assert len(value["ddg_results"]) == 40
    assert {(row["position"], row["mut"]) for row in value["ddg_results"]} == {(position, aa) for position in (1, 3) for aa in policy.ALPHABET}


def test_recorded_real_buildmodel_has_five_runs_per_variant():
    from t01_phase1_real.development.foldx.result import result
    value = result(*recording("buildmodel-three-variants-five-runs"))
    assert value["status"] == "buildmodel_unreviewed" and len(value["variant_ddg"]) == 3
    assert all(row["runs"] == 5 and len(row["native_ddg_runs"]) == 5 for row in value["variant_ddg"])


def test_recorded_native_artifact_loss_is_quarantined():
    from t01_phase1_real.development.foldx.result import result
    job, body, files, execution = recording("positionscan-two-positions")
    files = copy.deepcopy(files)
    del files["output/positionscan/HIS1_target_Repair.pdb"]
    value = result(job, body, files, copy.deepcopy(execution))
    assert value["ddg_results"] is None and value["null_reason"] == "OUTPUT_INVALID"
