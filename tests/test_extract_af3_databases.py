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


EXTRACT = module("extract_af3_databases", ROOT / "scripts/extract_af3_databases.py")
PREPARE = module("prepare_af3_database_extraction", ROOT / "scripts/prepare_af3_database_extraction.py")


@pytest.mark.parametrize("name", ["/absolute", "../escape", "a/../b", "a\\b", "a//b", "a/./b"])
def test_safe_relative_rejects_unsafe_paths(name):
    with pytest.raises(ValueError):
        EXTRACT.safe_relative(name)


def test_safe_relative_accepts_canonical_paths():
    assert EXTRACT.safe_relative("pdb/1abc.cif").as_posix() == "pdb/1abc.cif"


def test_rendered_extraction_job_is_offline_and_write_scoped():
    config, policy, job = PREPARE.documents()
    assert config["immutable"] is True
    assert policy["spec"]["policyTypes"] == ["Ingress", "Egress"]
    spec = job["spec"]["template"]["spec"]
    container = spec["containers"][0]
    assert spec["automountServiceAccountToken"] is False
    assert container["command"][0:3] == ["python", "-u", "-B"]
    assert container["command"][-3:] == ["/extract/database-manifest.json", "--run-id", "r03"]
    assert all(m["readOnly"] for m in container["volumeMounts"] if m["name"] == "extract")
    assert all("nvidia.com/gpu" not in json.dumps(doc) for doc in (config, policy, job))
    assert job["spec"]["backoffLimit"] == 0
    assert job["spec"]["activeDeadlineSeconds"] == 172800
    assert container["resources"]["limits"]["memory"] == "4Gi"


def test_archive_receipt_guard_rejects_unverified(tmp_path):
    archives = tmp_path / "archives"; archives.mkdir()
    (archives / "database-manifest.json").write_text(json.dumps({"schema": "bad"}))
    with pytest.raises(ValueError):
        EXTRACT.verify_source_manifest(archives, archives / "database-manifest.json")
