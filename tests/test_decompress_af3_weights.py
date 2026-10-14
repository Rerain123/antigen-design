import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


DECOMPRESS = module("decompress_af3_weights", ROOT / "scripts/decompress_af3_weights.py")
PREPARE = module("prepare_af3_weights_decompression", ROOT / "scripts/prepare_af3_weights_decompression.py")


def fixture(root, monkeypatch, source=b"compressed"):
    monkeypatch.setattr(DECOMPRESS, "EXPECTED_SOURCE_BYTES", len(source))
    monkeypatch.setattr(DECOMPRESS, "EXPECTED_SOURCE_SHA256", hashlib.sha256(source).hexdigest())
    monkeypatch.setattr(DECOMPRESS, "MAX_OUTPUT_BYTES", 1024)
    monkeypatch.setattr(DECOMPRESS, "RESERVE_BYTES", 0)
    (root / DECOMPRESS.SOURCE_NAME).write_bytes(source)
    (root / DECOMPRESS.DOWNLOAD_RECEIPT).write_text(json.dumps({
        "file": DECOMPRESS.SOURCE_NAME,
        "bytes": len(source),
        "sha256": hashlib.sha256(source).hexdigest(),
        "status": "WEIGHTS_DOWNLOADED_VERIFIED_NOT_DEPLOYED",
        "decompressed": False,
        "scientific_gate": "CLOSED",
    }))


def test_decompress_publishes_atomically_and_is_idempotent(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    decoded = b"official decoded weights"
    result = DECOMPRESS.decompress(tmp_path, lambda _: [decoded[:5], decoded[5:]])
    assert (tmp_path / "af3.bin").read_bytes() == decoded
    assert not (tmp_path / "af3.bin.partial").exists()
    assert result["target_sha256"] == hashlib.sha256(decoded).hexdigest()
    assert result["model_loaded"] is False
    assert DECOMPRESS.decompress(tmp_path, lambda _: pytest.fail("decoder reused")) == result


def test_decompress_retains_partial_on_decoder_failure(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)

    def broken(_):
        yield b"partial"
        raise ValueError("decoder failed")

    with pytest.raises(ValueError, match="decoder failed"):
        DECOMPRESS.decompress(tmp_path, broken)
    assert (tmp_path / "af3.bin.partial").read_bytes() == b"partial"
    assert not (tmp_path / "af3.bin").exists()


def test_weight_job_is_offline_bounded_and_zero_gpu():
    config, policy, job = PREPARE.documents()
    assert list(yaml.safe_load_all(yaml.safe_dump_all([config, policy, job], sort_keys=False))) == [config, policy, job]
    assert config["immutable"] is True
    assert policy["spec"]["policyTypes"] == ["Ingress", "Egress"]
    assert "egress" not in policy["spec"]
    pod = job["spec"]["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert pod["volumes"][0]["persistentVolumeClaim"]["claimName"] == "antigen-af3-models"
    assert "nvidia.com/gpu" not in json.dumps(job)
