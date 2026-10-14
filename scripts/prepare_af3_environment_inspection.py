"""Render a zero-GPU, no-egress inspection Job for the pinned AF3 image."""
from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/inspect_af3_environment.py"
OUTPUT = ROOT / "deploy/alphafold3/environment-inspect.r03.rancher.yaml"
NAME = "antigen-af3-environment-inspect-r03"
IMAGE = (
    "harbor-core.base.svc.cluster.local/qcyz/antigen-af3@"
    "sha256:35db7c1feb3368a7c72b0d1f60b295ed1473b562b61526db265fc0c446fd4373"
)


def documents() -> list[dict]:
    config = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "immutable": True,
        "data": {"inspect_af3_environment.py": SOURCE.read_text(encoding="utf-8")},
    }
    policy = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {
            "podSelector": {"matchLabels": {"app": NAME}},
            "policyTypes": ["Ingress", "Egress"],
        },
    }
    container = {
        "name": "inspect",
        "image": IMAGE,
        "imagePullPolicy": "IfNotPresent",
        "command": ["/alphafold3_venv/bin/python", "-u", "-B", "/inspect/inspect_af3_environment.py"],
        "env": [
            {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"},
            {"name": "HOME", "value": "/tmp"},
            {"name": "TMPDIR", "value": "/tmp"},
            {"name": "CUDA_VISIBLE_DEVICES", "value": ""},
            {"name": "JAX_PLATFORMS", "value": "cpu"},
        ],
        "resources": {
            "requests": {"cpu": "500m", "memory": "1Gi", "ephemeral-storage": "256Mi"},
            "limits": {"cpu": "2", "memory": "4Gi", "ephemeral-storage": "2Gi"},
        },
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "seccompProfile": {"type": "RuntimeDefault"},
            "capabilities": {"drop": ["ALL"]},
        },
        "volumeMounts": [
            {"name": "inspect", "mountPath": "/inspect", "readOnly": True},
            {"name": "tmp", "mountPath": "/tmp"},
        ],
    }
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 600,
            "template": {
                "metadata": {"labels": {"app": NAME}},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "imagePullSecrets": [{"name": "harbor"}],
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 10001,
                        "runAsGroup": 10001,
                        "fsGroup": 10001,
                        "fsGroupChangePolicy": "OnRootMismatch",
                    },
                    "containers": [container],
                    "volumes": [
                        {"name": "inspect", "configMap": {"name": NAME}},
                        {"name": "tmp", "emptyDir": {"sizeLimit": "2Gi"}},
                    ],
                },
            },
        },
    }
    json.loads(json.dumps([config, policy, job]))
    return [config, policy, job]


def main() -> None:
    OUTPUT.write_text(yaml.safe_dump_all(documents(), sort_keys=False), encoding="utf-8")
    print("AF3_ENVIRONMENT_INSPECTION_RENDERED", OUTPUT)


if __name__ == "__main__":
    main()
