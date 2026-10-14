import importlib.util
import hashlib
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/esmfold2-standard"
SPEC = importlib.util.spec_from_file_location("esmfold2_worker", DEPLOY / "run_structure.py")
worker = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(worker)


def documents():
    return (
        json.loads((DEPLOY / "profile.server.json").read_text(encoding="utf-8")),
        json.loads((DEPLOY / "request.engineering.json").read_text(encoding="utf-8")),
    )


def test_server_profile_and_engineering_request_are_closed_and_valid():
    profile, request = documents()
    worker.validate_profile(profile)
    worker.validate_request(request, profile)
    assert profile["variant"] == "standard"
    assert profile["network"] == "disabled"
    assert profile["scientific_gate"] == "CLOSED"
    assert request["parameters"]["msa_mode"] == "none"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("engine",), "alphafold3"),
        (("inputs", "sequence"), "ACDX"),
        (("inputs", "chain_id"), "B"),
        (("parameters", "num_samples"), 2),
        (("parameters", "msa_mode"), "local_pipeline"),
    ],
)
def test_request_rejects_unregistered_execution_changes(path, value):
    profile, request = documents()
    target = request
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        worker.validate_request(request, profile)


def test_worker_has_only_explicit_local_model_loading():
    source = (DEPLOY / "run_structure.py").read_text(encoding="utf-8")
    assert "load_esmc(str(esmc_path)" in source
    assert "local_files_only=True" in source
    assert '"HF_HUB_OFFLINE": "1"' in source
    assert '"ESMCFOLD_CCD_PATH": str(ccd_path)' in source
    assert "trust_remote_code" not in source


def test_validation_job_mounts_pvc_root_for_registered_asset_and_environment_paths():
    job = yaml.safe_load((DEPLOY / "validation.job.yaml").read_text(encoding="utf-8"))
    container = job["spec"]["template"]["spec"]["containers"][0]
    mounts = {row["name"]: row for row in container["volumeMounts"]}
    assert mounts["models"] == {"name": "models", "mountPath": "/models", "readOnly": True}
    assert container["resources"]["requests"]["ephemeral-storage"] == "2Gi"


def test_pvc_environment_worker_keeps_fixed_offline_site_packages_path():
    dockerfile = (DEPLOY / "Dockerfile.worker-pvc").read_text(encoding="utf-8")
    assert "python:3.12-slim-bookworm@sha256:" in dockerfile
    assert "PYTHONPATH=/models/esmfold2-environment-20260916-r01/site-packages" in dockerfile
    assert "gcc libc6-dev" in dockerfile
    assert "HF_HUB_OFFLINE=1" in dockerfile
    assert "USER 10001:10001" in dockerfile


def test_environment_verification_rejects_extracted_file_tampering(tmp_path: Path):
    root = tmp_path / "environment"
    site_packages = root / "site-packages"
    site_packages.mkdir(parents=True)
    module = site_packages / "module.py"
    module.write_bytes(b"VALUE = 1\n")
    requirements = root / "requirements.resolved.txt"
    requirements.write_bytes(b"example==1\n")
    archive = root / "site-packages.tar.gz"
    archive.write_bytes(b"fixed archive identity")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    tree = {
        "schema_version": "1.0",
        "root": "site-packages",
        "file_count": 1,
        "total_bytes": module.stat().st_size,
        "files": [{"path": "module.py", "bytes": module.stat().st_size, "sha256": digest(module)}],
    }
    tree_path = root / "site-packages-files.json"
    tree_path.write_text(json.dumps(tree), encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "id": "esmfold2-python312-cu126-pvc-r01",
        "scientific_gate": "CLOSED",
        "extracted": {
            "root": "site-packages",
            "manifest": "site-packages-files.json",
            "file_count": 1,
            "total_bytes": module.stat().st_size,
        },
        "files": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": digest(path)}
            for path in (archive, tree_path, requirements)
        ],
    }
    manifest_path = root / "environment-pvc-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    profile, _ = documents()
    profile["environment_root"] = str(root)
    profile["environment_manifest_sha256"] = digest(manifest_path)
    worker.verify_environment(profile)
    module.write_bytes(b"VALUE = 2\n")
    with pytest.raises(ValueError, match="Environment tree integrity mismatch"):
        worker.verify_environment(profile)
