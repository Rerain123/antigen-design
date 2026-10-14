import importlib.util
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


INSPECT = module("inspect_af3_environment", ROOT / "scripts/inspect_af3_environment.py")
PREPARE = module(
    "prepare_af3_environment_inspection",
    ROOT / "scripts/prepare_af3_environment_inspection.py",
)


def test_inspection_contract_keeps_fixed_runtime_identity():
    assert INSPECT.EXPECTED_PACKAGES["alphafold3"] == "3.0.2"
    assert INSPECT.EXPECTED_PACKAGES["jax"] == "0.9.1"
    assert INSPECT.DATA_FILES[0].name == "ccd.pickle"
    assert "--[no]run_data_pipeline" in INSPECT.EXPECTED_HELP_FLAGS
    assert "--[no]run_inference" in INSPECT.EXPECTED_HELP_FLAGS
    compile((ROOT / "scripts/inspect_af3_environment.py").read_text(encoding="utf-8"),
            "inspect_af3_environment.py", "exec")


def test_command_output_accepts_absl_help_exit_code(monkeypatch):
    class Result:
        returncode = 1
        stdout = "valid help"

    monkeypatch.setattr(INSPECT.subprocess, "run", lambda *args, **kwargs: Result())
    assert INSPECT.command_output(["python", "--helpshort"], accepted_returncodes=(0, 1)) == "valid help"


def test_inspection_job_is_digest_pinned_no_egress_and_zero_gpu():
    config, policy, job = PREPARE.documents()
    documents = [config, policy, job]
    assert list(yaml.safe_load_all(yaml.safe_dump_all(documents, sort_keys=False))) == documents
    assert policy["spec"]["policyTypes"] == ["Ingress", "Egress"]
    assert "egress" not in policy["spec"]
    pod = job["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert "@sha256:" in container["image"]
    assert container["image"].endswith(PREPARE.IMAGE.split("@sha256:", 1)[1])
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert pod["automountServiceAccountToken"] is False
    assert pod["securityContext"]["runAsUser"] == 10001
    assert "nvidia.com/gpu" not in json.dumps(job)
    assert all("persistentVolumeClaim" not in volume for volume in pod["volumes"])
