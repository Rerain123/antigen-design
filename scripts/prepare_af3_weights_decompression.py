"""Render the offline, zero-GPU AF3 weight decompression Job."""
from __future__ import annotations

import json
from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/decompress_af3_weights.py"
OUTPUT = ROOT / "deploy/alphafold3/weights-decompress.r01.rancher.yaml"
NAME = "antigen-af3-weights-decompress-r01"
IMAGE = "harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:fba5a32c0550e56a5310160e2fc49d647fcd27d76851073a2d82cc935fb4c2fc"


def documents() -> list[dict]:
    config = {
        "apiVersion": "v1", "kind": "ConfigMap",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "immutable": True,
        "data": {"decompress_af3_weights.py": SOURCE.read_text(encoding="utf-8")},
    }
    policy = {
        "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {"podSelector": {"matchLabels": {"app": NAME}}, "policyTypes": ["Ingress", "Egress"]},
    }
    container = {
        "name": "decompress", "image": IMAGE,
        "command": ["python", "-u", "-B", "/scripts/decompress_af3_weights.py",
                    "/weights/alphafold3-official-r01"],
        "resources": {
            "requests": {"cpu": "500m", "memory": "256Mi", "ephemeral-storage": "64Mi"},
            "limits": {"cpu": "2", "memory": "1Gi", "ephemeral-storage": "256Mi"},
        },
        "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]}},
        "volumeMounts": [
            {"name": "weights", "mountPath": "/weights"},
            {"name": "scripts", "mountPath": "/scripts", "readOnly": True},
        ],
    }
    pod_spec = {
        "restartPolicy": "Never", "automountServiceAccountToken": False,
        "imagePullSecrets": [{"name": "harbor"}],
        "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001,
                            "fsGroup": 10001, "fsGroupChangePolicy": "OnRootMismatch"},
        "containers": [container],
        "volumes": [
            {"name": "weights", "persistentVolumeClaim": {"claimName": "antigen-af3-models"}},
            {"name": "scripts", "configMap": {"name": NAME}},
        ],
    }
    job = {
        "apiVersion": "batch/v1", "kind": "Job",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 7200,
                 "template": {"metadata": {"labels": {"app": NAME}}, "spec": pod_spec}},
    }
    json.loads(json.dumps([config, policy, job]))
    return [config, policy, job]


def main() -> None:
    OUTPUT.write_text(yaml.safe_dump_all(documents(), sort_keys=False), encoding="utf-8")
    print("AF3_WEIGHT_DECOMPRESSION_RENDERED", OUTPUT)


if __name__ == "__main__":
    main()
