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


INSPECT = module("inspect_af3_extraction", ROOT / "scripts/inspect_af3_extraction.py")
PREPARE = module("prepare_af3_extraction_inspection", ROOT / "scripts/prepare_af3_extraction_inspection.py")


def valid_tree(tmp_path):
    root = tmp_path / "alphafold3-v3.0"
    output = root / "unpacked-r03"
    output.mkdir(parents=True)
    rows = []
    for name in INSPECT.REQUIRED_ROOT_FILES:
        target = output / name
        target.write_bytes(name.encode())
        rows.append({"path": name, "size_bytes": target.stat().st_size,
                     "sha256": INSPECT.sha256_file(target), "source_archive": name + ".zst"})
    mmcif = output / "mmcif_files" / "1abc.cif"
    mmcif.parent.mkdir()
    mmcif.write_bytes(b"data_1ABC\n")
    rows.append({"path": "mmcif_files/1abc.cif", "size_bytes": mmcif.stat().st_size,
                 "sha256": INSPECT.sha256_file(mmcif), "source_archive": "pdb.tar.zst"})
    # Use the verifier's pinned totals for the fixture without creating 195k files.
    monkey = {"file_count": len(rows), "total_bytes": sum(row["size_bytes"] for row in rows)}
    receipt = {
        "status": INSPECT.REQUIRED_RECEIPT_STATUS, "scientific_gate": "CLOSED", "decompressed": True,
        "source_manifest": "database-manifest.json", "output_root": "unpacked-r03",
        "file_count": monkey["file_count"], "total_bytes": monkey["total_bytes"],
        "files_manifest": "extracted-manifest.json",
    }
    (root / "extraction-receipt.json").write_text(json.dumps(receipt))
    (output / "extracted-manifest.json").write_text(json.dumps({"schema": INSPECT.REQUIRED_MANIFEST_SCHEMA, "files": rows}))
    return root, receipt


def test_extraction_verification_checks_layout_and_hashes(tmp_path, monkeypatch):
    root, receipt = valid_tree(tmp_path)
    monkeypatch.setattr(INSPECT, "EXPECTED_FILE_COUNT", receipt["file_count"])
    monkeypatch.setattr(INSPECT, "EXPECTED_TOTAL_BYTES", receipt["total_bytes"])
    result = INSPECT.inspect(root, full_hash=True, progress_every=0)
    assert result["status"] == "AF3_DATABASES_EXTRACTION_INDEPENDENTLY_VERIFIED_NOT_DEPLOYED"
    assert result["mmcif_file_count"] == 1
    assert result["hashed_file_count"] == receipt["file_count"]


def test_extraction_verification_rejects_tampered_file(tmp_path, monkeypatch):
    root, receipt = valid_tree(tmp_path)
    monkeypatch.setattr(INSPECT, "EXPECTED_FILE_COUNT", receipt["file_count"])
    monkeypatch.setattr(INSPECT, "EXPECTED_TOTAL_BYTES", receipt["total_bytes"])
    target = root / "unpacked-r03" / INSPECT.REQUIRED_ROOT_FILES[0]
    target.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Extracted size mismatch|Extracted SHA-256 mismatch"):
        INSPECT.inspect(root, full_hash=True, progress_every=0)


def test_rendered_job_is_read_only_offline_and_no_gpu():
    config, policy, job = PREPARE.documents()
    rendered = list(yaml.safe_load_all(yaml.safe_dump_all([config, policy, job], sort_keys=False)))
    assert rendered == [config, policy, job]
    assert config["immutable"] is True
    assert policy["spec"]["policyTypes"] == ["Ingress", "Egress"]
    pod = job["spec"]["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert all(mount["readOnly"] for mount in pod["containers"][0]["volumeMounts"])
    assert all(volume.get("persistentVolumeClaim", {}).get("readOnly", True) for volume in pod["volumes"])
    assert "nvidia.com/gpu" not in json.dumps(job)
