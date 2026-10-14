"""Render the read-only AF3 asset/PVC inspection Job for Rancher import."""
from __future__ import annotations

import json
from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/inspect_af3_assets.py"
MANIFEST = ROOT / "deploy/alphafold3/database-manifest.v3.0.json"
OUTPUT = ROOT / "deploy/alphafold3/assets-inspect.r02.rancher.yaml"
NAME = "antigen-af3-assets-inspect-r02"
IMAGE = "harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:fba5a32c0550e56a5310160e2fc49d647fcd27d76851073a2d82cc935fb4c2fc"


def documents() -> list[dict]:
    script = SOURCE.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")
    json.loads(manifest)
    config = {
        "apiVersion": "v1", "kind": "ConfigMap",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "immutable": True,
        "data": {"inspect_af3_assets.py": script, "database-manifest.json": manifest},
    }
    policy = {
        "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {"podSelector": {"matchLabels": {"app": NAME}},
                 "policyTypes": ["Ingress", "Egress"]},
    }
    container = {
        "name": "inspect", "image": IMAGE,
        "command": ["python", "-u", "-B", "/inspect/inspect_af3_assets.py",
                    "/databases/alphafold3-v3.0/archives",
                    "/weights/alphafold3-official-r01",
                    "/inspect/database-manifest.json"],
        "resources": {"requests": {"cpu": "100m", "memory": "128Mi", "ephemeral-storage": "64Mi"},
                      "limits": {"cpu": "1", "memory": "512Mi", "ephemeral-storage": "256Mi"}},
        "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]}},
        "volumeMounts": [
            {"name": "databases", "mountPath": "/databases", "readOnly": True},
            {"name": "models", "mountPath": "/weights", "readOnly": True},
            {"name": "inspect", "mountPath": "/inspect", "readOnly": True},
        ],
    }
    pod_spec = {
        "restartPolicy": "Never", "automountServiceAccountToken": False,
        "imagePullSecrets": [{"name": "harbor"}],
        "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001,
                            "fsGroup": 10001, "fsGroupChangePolicy": "OnRootMismatch"},
        "containers": [container],
        "volumes": [
            {"name": "databases", "persistentVolumeClaim": {"claimName": "antigen-af3-databases", "readOnly": True}},
            {"name": "models", "persistentVolumeClaim": {"claimName": "antigen-af3-models", "readOnly": True}},
            {"name": "inspect", "configMap": {"name": NAME}},
        ],
    }
    job = {
        "apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 1800,
                 "template": {"metadata": {"labels": {"app": NAME}}, "spec": pod_spec}},
    }
    return [config, policy, job]


def main() -> None:
    OUTPUT.write_text(yaml.safe_dump_all(documents(), sort_keys=False), encoding="utf-8")
    print("AF3_ASSET_INSPECTION_RENDERED", OUTPUT)


if __name__ == "__main__":
    main()
