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


PREPARE = module("prepare_af3_data_search_inspection", ROOT / "scripts/prepare_af3_data_search_inspection.py")


def test_data_search_inspection_is_read_only_and_zero_gpu():
    config, policy, job = PREPARE.documents()
    documents = [config, policy, job]
    assert list(yaml.safe_load_all(yaml.safe_dump_all(documents, sort_keys=False))) == documents
    assert "egress" not in policy["spec"]
    pod = job["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert "@sha256:35db7c1f" in container["image"]
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert pod["volumes"][1]["persistentVolumeClaim"]["readOnly"] is True
    assert "nvidia.com/gpu" not in json.dumps(job)
