"""The HiMat ESMFold2 deployment must update the path native Python imports."""

import copy
import hashlib
import importlib
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def prep(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("prepare_himat_esmfold2_path_fix")


def fixture(prep):
    paths = {"policy.py": "k-policy", "profile.json": "k-profile", "worker.py": "k-worker"}
    volume = {"name": prep.VOLUME, "configMap": {
        "name": prep.BASE_NAME,
        "items": [{"key": key, "path": prep.BASE_PATH + name}
                  for name, key in paths.items()]}}
    deployment = {"metadata": {"uid": "u1", "resourceVersion": "r1"},
                  "spec": {"replicas": 1, "strategy": {"type": "Recreate"},
                           "template": {"spec": {
                               "containers": [{"name": "worker-unified-gpu", "volumeMounts": [
                                   {"name": prep.VOLUME, "mountPath": "/backend", "readOnly": True},
                                   {"name": "m1-himat-sequence-code-r04",
                                    "mountPath": "/opt/t01/src/" + prep.BASE_PATH + "policy.py",
                                    "subPath": "p3", "readOnly": True}]}],
                               "volumes": [volume]}}}}
    old = {"metadata": {"name": prep.BASE_NAME}, "immutable": True,
           "data": {"k-policy": "old policy\n", "k-profile": "old profile\n",
                    "k-worker": "preserve exactly\r\n"}}
    return deployment, old


def test_fixes_real_backend_import_path_without_changing_other_sources(prep):
    deployment, old = fixture(prep)
    before = copy.deepcopy((deployment, old))
    new, patch, previous = prep.render(deployment, old)

    assert (deployment, old) == before
    assert new["immutable"] is True and new["metadata"]["name"] == prep.NEW_NAME
    assert previous == {"policy.py": hashlib.sha256(b"old policy\n").hexdigest(),
                        "profile.json": hashlib.sha256(b"old profile\n").hexdigest()}
    assert new["data"]["k-worker"] == old["data"]["k-worker"]
    encoded = yaml.safe_load(yaml.safe_dump(new, sort_keys=False))
    for name, key in (("policy.py", "k-policy"), ("profile.json", "k-profile")):
        assert hashlib.sha256(encoded["data"][key].encode()).hexdigest() == prep.source_hashes()[name]
    assert [row["op"] for row in patch] == ["test", "test", "test", "replace"]
    assert patch[-1]["path"] == "/spec/template/spec/volumes/0/configMap/name"
    assert patch[-1]["value"] == prep.NEW_NAME


def test_refuses_wrong_import_mount_and_source_revision(prep):
    deployment, old = fixture(prep)
    deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = []
    with pytest.raises(RuntimeError, match="/backend"):
        prep.render(deployment, old)

    deployment, old = fixture(prep)
    deployment["spec"]["template"]["spec"]["volumes"][0]["configMap"]["name"] = "other"
    with pytest.raises(RuntimeError, match="revision"):
        prep.render(deployment, old)
