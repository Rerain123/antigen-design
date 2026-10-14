"""Prepare the ESMFold2 import-path fix; deploy only after all jobs finish."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess

import yaml

import prepare_m1_p1_deploy as common


OUT = common.ROOT / "deploy/m1-p4/himat-esmfold2-path-r06"
BASE_NAME = "antigen-m1-p2-esmfold2-r08"
NEW_NAME = "antigen-m1-himat-esmfold2-path-r06"
VOLUME = "esmfold2-code"
ROOT = common.ROOT / "src/t01_phase1_real/development/esmfold2"
FILES = ("policy.py", "profile.json")
BASE_PATH = "t01_phase1_real/development/esmfold2/"


def source_hashes() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in FILES}


def render(deployment: dict, old: dict) -> tuple[dict, list[dict], dict]:
    if deployment["spec"]["replicas"] != 1 or deployment["spec"]["strategy"] != {"type": "Recreate"}:
        raise RuntimeError("Expected singleton Recreate deployment")
    spec = deployment["spec"]["template"]["spec"]
    containers = [c for c in spec["containers"] if c["name"] == "worker-unified-gpu"]
    if len(containers) != 1:
        raise RuntimeError("Expected one unified GPU worker")
    mounts = containers[0]["volumeMounts"]
    if sum(m["name"] == VOLUME and m["mountPath"] == "/backend" for m in mounts) != 1:
        raise RuntimeError("Expected /backend ESMFold2 source mount")
    if not any(m["name"] == "m1-himat-sequence-code-r04" and
               m["mountPath"] == "/opt/t01/src/" + BASE_PATH + "policy.py" for m in mounts):
        raise RuntimeError("Expected existing HiMat sequence overlay")
    indexed = [(i, v) for i, v in enumerate(spec["volumes"]) if v["name"] == VOLUME]
    if len(indexed) != 1:
        raise RuntimeError("Expected one ESMFold2 code volume")
    index, volume = indexed[0]
    config = volume["configMap"]
    if config["name"] != BASE_NAME or old.get("immutable") is not True or \
       old["metadata"]["name"] != BASE_NAME or old.get("binaryData"):
        raise RuntimeError("Unexpected immutable ESMFold2 source revision")
    items = config["items"]
    paths = {item["path"]: item["key"] for item in items}
    if len(paths) != len(items) or set(paths.values()) != set(old["data"]):
        raise RuntimeError("Projected ESMFold2 file map differs")
    keys = {name: paths[BASE_PATH + name] for name in FILES}
    data = copy.deepcopy(old["data"])
    previous = {name: hashlib.sha256(data[keys[name]].encode("utf-8")).hexdigest()
                for name in FILES}
    for name in FILES:
        data[keys[name]] = (ROOT / name).read_bytes().decode("utf-8")
    if previous == source_hashes():
        raise RuntimeError("ESMFold2 import path already has current bytes")
    new = {"apiVersion": "v1", "kind": "ConfigMap", "immutable": True,
           "metadata": {"name": NEW_NAME, "namespace": "him-ws"}, "data": data}
    patch = [
        {"op": "test", "path": "/metadata/resourceVersion",
         "value": deployment["metadata"]["resourceVersion"]},
        {"op": "test", "path": "/metadata/uid", "value": deployment["metadata"]["uid"]},
        {"op": "test", "path": f"/spec/template/spec/volumes/{index}/configMap/name",
         "value": BASE_NAME},
        {"op": "replace", "path": f"/spec/template/spec/volumes/{index}/configMap/name",
         "value": NEW_NAME},
    ]
    return new, patch, previous


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        state = common.idle()
        if state["active_jobs"] or state["gpu_state"]["phase"] != "idle":
            raise RuntimeError("Refusing rollout while backend work is active")
        preflight = json.loads((OUT / "preflight.json").read_bytes())
        if preflight["new_hashes"] != source_hashes():
            raise RuntimeError("Source changed since preparation")
        subprocess.run(common.K + ["create", "-f", str(OUT / "configmap.yaml")], check=True)
        subprocess.run(common.K + ["patch", "deployment", "antigen-design", "--type=json",
                                   "--patch-file", str(OUT / "deployment.patch.json")], check=True)
        subprocess.run(common.K + ["rollout", "status", "deployment/antigen-design",
                                   "--timeout=300s"], check=True)
        return
    state = common.idle()
    deployment = json.loads(subprocess.check_output(common.K + [
        "get", "deployment", "antigen-design", "-o", "json"]))
    volume = next(v for v in deployment["spec"]["template"]["spec"]["volumes"]
                  if v["name"] == VOLUME)
    old = json.loads(subprocess.check_output(common.K + [
        "get", "configmap", volume["configMap"]["name"], "-o", "json"]))
    new, patch, previous = render(deployment, old)
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / "configmap.yaml").write_text(yaml.safe_dump(new, sort_keys=False), encoding="utf-8")
    (OUT / "deployment.patch.json").write_text(json.dumps(patch, indent=2) + "\n", encoding="utf-8")
    (OUT / "preflight.json").write_text(json.dumps({
        "task": "PH1-REAL-HIMAT-1", "purpose": "ESMFOLD2_ACTUAL_BACKEND_IMPORT_PATH",
        "active_jobs_at_preparation": state["active_jobs"],
        "gpu_phase_at_preparation": state["gpu_state"]["phase"],
        "old_hashes": previous, "new_hashes": source_hashes(),
        "before_generation": deployment["metadata"]["generation"],
        "before_uid": deployment["metadata"]["uid"],
        "before_resource_version": deployment["metadata"]["resourceVersion"],
    }, indent=2) + "\n", encoding="utf-8")
    subprocess.run(common.K + ["create", "--dry-run=server", "-f",
                               str(OUT / "configmap.yaml")], check=True)
    subprocess.run(common.K + ["patch", "deployment", "antigen-design", "--type=json",
                               "--patch-file", str(OUT / "deployment.patch.json"),
                               "--dry-run=server", "-o", "name"], check=True)
    print("HIMAT_ESMFOLD2_PATH_FIX_PREPARED", OUT)


if __name__ == "__main__":
    main()
