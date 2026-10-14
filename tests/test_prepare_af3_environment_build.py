import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


FETCH = module("fetch_af3_source", ROOT / "scripts/fetch_af3_source.py")
PREPARE = module("prepare_af3_environment_build", ROOT / "scripts/prepare_af3_environment_build.py")


def archive(rows):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        root = tarfile.TarInfo(FETCH.PREFIX)
        root.type = tarfile.DIRTYPE
        tar.addfile(root)
        for name, raw in rows:
            info = tarfile.TarInfo(FETCH.PREFIX + "/" + name)
            info.size = len(raw)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(raw))
    return output.getvalue()


def test_source_archive_is_verified_and_base_images_are_pinned(tmp_path, monkeypatch):
    dockerfile = (
        b"FROM nvidia/cuda:12.6.3-base-ubuntu24.04\n"
        b"COPY --from=ghcr.io/astral-sh/uv:0.9.24 /uv /bin/uv\n"
    )
    pyproject = b"[project]\nname='alphafold3'\n"
    uv_lock = (
        b'source = { registry = "https://pypi.org/simple" }\n'
        b'url = "https://files.pythonhosted.org/packages/example.whl"\n'
    )
    raw = archive([("docker/Dockerfile", dockerfile), ("pyproject.toml", pyproject),
                   ("uv.lock", uv_lock)])
    monkeypatch.setattr(FETCH, "EXPECTED_ARCHIVE_BYTES", len(raw))
    monkeypatch.setattr(FETCH, "EXPECTED_ARCHIVE_SHA256", hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(FETCH, "EXPECTED_MEMBERS", 4)
    monkeypatch.setattr(FETCH, "EXPECTED_DOCKERFILE_SHA256", hashlib.sha256(dockerfile).hexdigest())
    monkeypatch.setattr(FETCH, "EXPECTED_PYPROJECT_SHA256", hashlib.sha256(pyproject).hexdigest())
    monkeypatch.setattr(FETCH, "EXPECTED_UV_LOCK_BYTES", len(uv_lock))
    monkeypatch.setattr(FETCH, "EXPECTED_UV_LOCK_SHA256", hashlib.sha256(uv_lock).hexdigest())
    monkeypatch.setattr(FETCH, "EXPECTED_WHEEL_URLS", 1)
    monkeypatch.setattr(FETCH, "EXPECTED_INDEX_URLS", 1)
    receipt = FETCH.extract_verified(raw, tmp_path / "source")
    text = (tmp_path / "source/docker/Dockerfile").read_text()
    assert FETCH.CUDA_IMAGE in text
    assert FETCH.UV_IMAGE in text
    lock_text = (tmp_path / "source/uv.lock").read_text()
    assert FETCH.PYPI_WHEEL_MIRROR in lock_text
    assert FETCH.PYPI_INDEX_MIRROR in lock_text
    assert receipt["commit"] == FETCH.COMMIT
    assert receipt["scientific_gate"] == "CLOSED"


def test_source_archive_rejects_path_escape(tmp_path, monkeypatch):
    raw = archive([("../escape", b"x")])
    monkeypatch.setattr(FETCH, "EXPECTED_ARCHIVE_BYTES", len(raw))
    monkeypatch.setattr(FETCH, "EXPECTED_ARCHIVE_SHA256", hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(FETCH, "EXPECTED_MEMBERS", 2)
    with pytest.raises(ValueError, match="Unsafe source archive path"):
        FETCH.extract_verified(raw, tmp_path / "source")


def test_build_job_is_rootless_bounded_and_zero_gpu():
    config, policy, cache_claim, job = PREPARE.documents()
    documents = [config, policy, cache_claim, job]
    assert list(yaml.safe_load_all(yaml.safe_dump_all(documents, sort_keys=False))) == documents
    assert 'mirrors = ["dockerproxy.net"]' in config["data"]["buildkitd.toml"]
    pod = job["spec"]["template"]["spec"]
    builder = pod["containers"][0]
    assert pod["automountServiceAccountToken"] is False
    assert pod["securityContext"]["runAsUser"] == 1000
    assert builder["securityContext"]["appArmorProfile"] == {"type": "Unconfined"}
    assert builder["securityContext"]["allowPrivilegeEscalation"] is True
    assert set(builder["securityContext"]["capabilities"]["add"]) == {"SETUID", "SETGID"}
    assert builder["securityContext"]["capabilities"]["drop"] == ["ALL"]
    assert builder["image"].endswith("995077ff90af1afff56ff23018699d7511d122b2b111041f2011bd12afd5c0fe")
    assert builder["resources"]["limits"]["memory"] == "16Gi"
    assert builder["resources"]["limits"]["ephemeral-storage"] == "50Gi"
    assert "for attempt in 1 2 3" in builder["command"][-1]
    state = next(volume for volume in pod["volumes"] if volume["name"] == "state")
    assert state["persistentVolumeClaim"] == {"claimName": PREPARE.CACHE_CLAIM}
    assert cache_claim["spec"]["storageClassName"] == "ceph-rbd"
    assert cache_claim["spec"]["resources"]["requests"]["storage"] == "30Gi"
    assert "nvidia.com/gpu" not in json.dumps(job)
    assert policy["spec"]["egress"] == [
        {"ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}]},
        {"ports": [{"protocol": "TCP"}]},
    ]
