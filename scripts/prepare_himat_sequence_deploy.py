"""Prepare/apply an immutable HiMat sequence-entry overlay after idle checks."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess

import yaml

import prepare_m1_p1_deploy as common


OUT = common.ROOT / "deploy/m1-p4/himat-sequence-r04"
NAME = "antigen-m1-himat-sequence-r04"
VOLUME = "m1-himat-sequence-code-r04"
FILES = (
    "service_api/transport.py",
    "service_api/himat.py",
    "development/workflow/policy.py",
    "development/esmfold2/policy.py",
    "development/esmfold2/profile.json",
)
SERVICE_ROOT = "/app/src/t01_phase1_real/"
GPU_ROOT = "/opt/t01/src/t01_phase1_real/"


def hashes():
    return {name: hashlib.sha256((common.ROOT / "src/t01_phase1_real" / name).read_bytes()).hexdigest()
            for name in FILES}


def patch(live):
    if live["spec"]["replicas"] != 1 or live["spec"]["strategy"] != {"type": "Recreate"}:
        raise RuntimeError("Expected singleton Recreate deployment")
    spec = live["spec"]["template"]["spec"]
    ops = [
        {"op": "test", "path": "/metadata/resourceVersion", "value": live["metadata"]["resourceVersion"]},
        {"op": "test", "path": "/metadata/uid", "value": live["metadata"]["uid"]},
    ]
    old_himat = {"m1-himat-code-r02", "m1-himat-code", "m1-himat-sequence-code-r03"}
    for index, container in enumerate(spec["containers"]):
        if container["name"] == "service":
            targets = {SERVICE_ROOT + name for name in FILES}
            mounts = [m for m in container["volumeMounts"] if m["mountPath"] not in targets
                      and m["name"] not in old_himat]
            mounts += [{"name": VOLUME, "mountPath": SERVICE_ROOT + name,
                        "subPath": "p" + str(i), "readOnly": True}
                       for i, name in enumerate(FILES)]
        elif container["name"] == "worker-unified-gpu":
            names = FILES[-2:]
            targets = {GPU_ROOT + name for name in names}
            mounts = [m for m in container["volumeMounts"] if m["mountPath"] not in targets]
            mounts += [{"name": VOLUME, "mountPath": GPU_ROOT + name,
                        "subPath": "p" + str(FILES.index(name)), "readOnly": True}
                       for name in names]
        else:
            continue
        paths = [m["mountPath"] for m in mounts]
        if len(paths) != len(set(paths)):
            raise RuntimeError("Duplicate container mount path")
        ops.append({"op": "replace", "path": f"/spec/template/spec/containers/{index}/volumeMounts", "value": mounts})
    volumes = [v for v in spec["volumes"] if v["name"] not in old_himat]
    volumes.append({"name": VOLUME, "configMap": {"name": NAME}})
    ops.append({"op": "replace", "path": "/spec/template/spec/volumes", "value": volumes})
    return ops


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    idle = common.idle()
    if idle["active_jobs"] or idle["gpu_state"]["phase"] != "idle":
        raise RuntimeError("Refusing singleton rollout while work is active")
    current = hashes()
    if args.apply:
        preflight = json.loads((OUT / "preflight.json").read_bytes())
        if preflight["source_hashes"] != current:
            raise RuntimeError("Overlay bytes changed since preflight")
        subprocess.run(common.K + ["create", "-f", str(OUT / "configmap.yaml")], check=True)
        subprocess.run(common.K + ["patch", "deployment", "antigen-design", "--type=json",
                                   "--patch-file", str(OUT / "deployment.patch.json")], check=True)
        subprocess.run(common.K + ["rollout", "status", "deployment/antigen-design", "--timeout=300s"], check=True)
        return
    live = json.loads(subprocess.check_output(common.K + ["get", "deployment", "antigen-design", "-o", "json"]))
    configmap = {"apiVersion": "v1", "kind": "ConfigMap", "immutable": True,
                 "metadata": {"name": NAME, "namespace": "him-ws"},
                 "binaryData": {"p" + str(i): base64.b64encode(
                     (common.ROOT / "src/t01_phase1_real" / name).read_bytes()).decode("ascii")
                     for i, name in enumerate(FILES)}}
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / "configmap.yaml").write_text(yaml.safe_dump(configmap, sort_keys=False), encoding="utf-8")
    (OUT / "deployment.patch.json").write_text(json.dumps(patch(live), indent=2) + "\n", encoding="utf-8")
    (OUT / "preflight.json").write_text(json.dumps({
        "task": "PH1-REAL-HIMAT-1", "input_mode": "USER_SEQUENCE",
        "idle": idle, "source_hashes": current,
        "before_generation": live["metadata"]["generation"],
        "before_uid": live["metadata"]["uid"],
        "before_resource_version": live["metadata"]["resourceVersion"],
    }, indent=2) + "\n", encoding="utf-8")
    subprocess.run(common.K + ["create", "--dry-run=server", "-f", str(OUT / "configmap.yaml")], check=True)
    subprocess.run(common.K + ["patch", "deployment", "antigen-design", "--type=json",
                               "--patch-file", str(OUT / "deployment.patch.json"),
                               "--dry-run=server", "-o", "name"], check=True)
    print("HIMAT_SEQUENCE_DEPLOYMENT_PREPARED", OUT)


if __name__ == "__main__":
    main()
