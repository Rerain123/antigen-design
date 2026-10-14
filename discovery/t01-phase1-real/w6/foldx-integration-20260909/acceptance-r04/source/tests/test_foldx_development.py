"""W6 FoldX candidate request, asset and command contract tests."""
import pytest

from t01_phase1_real.common import REPO, RuntimeFault, encode
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
