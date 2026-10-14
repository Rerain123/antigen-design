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


INSPECT = module("inspect_af3_assets", ROOT / "scripts/inspect_af3_assets.py")
PREPARE = module("prepare_af3_assets_inspection", ROOT / "scripts/prepare_af3_assets_inspection.py")


def valid_tree(tmp_path, monkeypatch):
    databases, weights = tmp_path / "databases", tmp_path / "weights"
    databases.mkdir(); weights.mkdir()
    monkeypatch.setattr(INSPECT, "WEIGHT_BYTES", 6)
    assets = []
    receipts = []
    for name, raw in (("one.zst", b"one"), ("two.zst", b"twotwo")):
        identity = {"url": "https://example.invalid/" + name, "bytes": len(raw), "etag": '"x"',
                    "md5_base64": "x", "crc32c_base64": "x"}
        asset = {"file": name, "generation": "1", "identity": identity}; assets.append(asset)
        (databases / name).write_bytes(raw)
        (databases / f"{name}.source.json").write_text(json.dumps(identity))
        receipt = {**identity, "file": name, "sha256": "a" * 64, "official_md5_verified": True,
                   "decompressed": False, "status": "ARCHIVE_VERIFIED_NOT_DEPLOYED", "scientific_gate": "CLOSED"}
        receipts.append(receipt)
        (databases / f"{name}.receipt.json").write_text(json.dumps(receipt))
    manifest = {"schema": "t01.af3-database-download/1", "archives_only": True,
                "total_bytes": sum(a["identity"]["bytes"] for a in assets), "assets": assets}
    manifest_path = tmp_path / "manifest.json"; manifest_path.write_text(json.dumps(manifest))
    (databases / "database-manifest.json").write_text(json.dumps(manifest))
    (databases / "download-receipt.json").write_text(json.dumps({
        "status": "DATABASE_ARCHIVES_VERIFIED_NOT_DEPLOYED", "scientific_gate": "CLOSED",
        "decompressed": False, "assets": receipts}))
    (weights / INSPECT.WEIGHT_FILE).write_bytes(b"weight")
    (weights / "download-receipt.json").write_text(json.dumps({
        "file": INSPECT.WEIGHT_FILE, "bytes": INSPECT.WEIGHT_BYTES, "sha256": INSPECT.WEIGHT_SHA256,
        "status": "WEIGHTS_DOWNLOADED_VERIFIED_NOT_DEPLOYED", "official_crc32c_verified": True,
        "decompressed": False, "scientific_gate": "CLOSED"}))
    monkeypatch.setattr(INSPECT, "filesystem", lambda path: {"total_bytes": 10**12, "free_bytes": 8*10**11, "used_bytes": 2*10**11})
    return databases, weights, manifest_path


def test_inspection_manifest_and_space(tmp_path, monkeypatch):
    databases, weights, manifest_path = valid_tree(tmp_path, monkeypatch)
    result = INSPECT.inspect(databases, weights, manifest_path)
    assert result["database_archives"]["count"] == 2
    assert result["extraction_space_planning"]["provisionally_sufficient"] is True
    assert result["scientific_gate"] == "CLOSED"


def test_partial_archive_is_rejected(tmp_path, monkeypatch):
    databases, weights, manifest_path = valid_tree(tmp_path, monkeypatch)
    (databases / "one.zst.partial").write_bytes(b"partial")
    with pytest.raises(ValueError, match="Partial archive remains"):
        INSPECT.inspect(databases, weights, manifest_path)


def test_rendered_job_is_read_only_and_offline():
    config, policy, job = PREPARE.documents()
    rendered = yaml.safe_dump_all([config, policy, job], sort_keys=False)
    assert list(yaml.safe_load_all(rendered)) == [config, policy, job]
    assert config["immutable"] is True
    assert config["data"]["inspect_af3_assets.py"] == (ROOT / "scripts/inspect_af3_assets.py").read_text(encoding="utf-8")
    assert policy["spec"]["policyTypes"] == ["Ingress", "Egress"]
    spec = job["spec"]["template"]["spec"]
    assert spec["automountServiceAccountToken"] is False
    assert spec["containers"][0]["command"][5] == "/weights/alphafold3-official-r01"
    assert next(m for m in spec["containers"][0]["volumeMounts"] if m["name"] == "models")["mountPath"] == "/weights"
    assert all(mount["readOnly"] for mount in spec["containers"][0]["volumeMounts"])
    assert all(volume.get("persistentVolumeClaim", {}).get("readOnly", True) for volume in spec["volumes"])
    assert "nvidia.com/gpu" not in json.dumps(job)
