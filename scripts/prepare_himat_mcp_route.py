"""Prepare/apply an immutable HiMat MCP authentication and tool-name overlay."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess

import yaml

import prepare_m1_p1_deploy as common


OUT = common.ROOT / "deploy/m1-p4/himat-mcp-route-r05"
NAME = "antigen-m1-himat-mcp-route-r05"
VOLUME = "m1-himat-mcp-route-code-r05"
SOURCE = common.ROOT / "src/t01_phase1_real/service_api/transport.py"
TARGET = "/app/src/t01_phase1_real/service_api/transport.py"


def source_hash() -> str:
    return hashlib.sha256(SOURCE.read_bytes()).hexdigest()


def patch(live: dict) -> list[dict]:
    if live["spec"]["replicas"] != 1 or live["spec"]["strategy"] != {"type": "Recreate"}:
        raise RuntimeError("Expected singleton Recreate deployment")
    spec = live["spec"]["template"]["spec"]
    ops = [
        {"op": "test", "path": "/metadata/resourceVersion", "value": live["metadata"]["resourceVersion"]},
        {"op": "test", "path": "/metadata/uid", "value": live["metadata"]["uid"]},
    ]
    service = next((i, c) for i, c in enumerate(spec["containers"]) if c["name"] == "service")
    index, container = service
    old = container["volumeMounts"]
    if sum(m["mountPath"] == TARGET for m in old) != 1:
        raise RuntimeError("Expected one existing MCP transport mount")
    mounts = [m for m in old if m["mountPath"] != TARGET]
    mounts.append({"name": VOLUME, "mountPath": TARGET, "subPath": "code", "readOnly": True})
    ops.append({"op": "replace", "path": f"/spec/template/spec/containers/{index}/volumeMounts",
                "value": mounts})
    if any(v["name"] == VOLUME for v in spec["volumes"]):
        raise RuntimeError("Overlay volume already exists")
    volumes = [*spec["volumes"], {"name": VOLUME, "configMap": {"name": NAME}}]
    ops.append({"op": "replace", "path": "/spec/template/spec/volumes", "value": volumes})
    return ops


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    idle = common.idle()
    if idle["active_jobs"] or idle["gpu_state"]["phase"] != "idle":
        raise RuntimeError("Refusing singleton rollout while backend work is active")
    digest = source_hash()
    if args.apply:
        preflight = json.loads((OUT / "preflight.json").read_bytes())
        if preflight["source_sha256"] != digest:
            raise RuntimeError("Transport changed since preflight")
        subprocess.run(common.K + ["create", "-f", str(OUT / "configmap.yaml")], check=True)
        subprocess.run(common.K + ["patch", "deployment", "antigen-design", "--type=json",
                                   "--patch-file", str(OUT / "deployment.patch.json")], check=True)
        subprocess.run(common.K + ["rollout", "status", "deployment/antigen-design", "--timeout=300s"],
                       check=True)
        return
    live = json.loads(subprocess.check_output(common.K + ["get", "deployment", "antigen-design", "-o", "json"]))
    operations = patch(live)
    configmap = {"apiVersion": "v1", "kind": "ConfigMap", "immutable": True,
                 "metadata": {"name": NAME, "namespace": "him-ws"},
                 "binaryData": {"code": base64.b64encode(SOURCE.read_bytes()).decode("ascii")}}
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / "configmap.yaml").write_text(yaml.safe_dump(configmap, sort_keys=False), encoding="utf-8")
    (OUT / "deployment.patch.json").write_text(json.dumps(operations, indent=2) + "\n", encoding="utf-8")
    (OUT / "preflight.json").write_text(json.dumps({
        "task": "PH1-REAL-HIMAT-1", "purpose": "HIMAT_MCP_AUTH_AND_TOOL_NAMES",
        "idle": idle, "source_sha256": digest,
        "before_generation": live["metadata"]["generation"],
        "before_uid": live["metadata"]["uid"],
        "before_resource_version": live["metadata"]["resourceVersion"],
    }, indent=2) + "\n", encoding="utf-8")
    subprocess.run(common.K + ["create", "--dry-run=server", "-f", str(OUT / "configmap.yaml")], check=True)
    subprocess.run(common.K + ["patch", "deployment", "antigen-design", "--type=json",
                               "--patch-file", str(OUT / "deployment.patch.json"),
                               "--dry-run=server", "-o", "name"], check=True)
    print("HIMAT_MCP_ROUTE_PREPARED", OUT)


if __name__ == "__main__":
    main()
