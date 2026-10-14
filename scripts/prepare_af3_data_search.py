"""Render the bounded, zero-GPU AF3 local data-search acceptance Job."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_af3_data_search.py"
OUTPUT = ROOT / "deploy/alphafold3/data-search.r01.rancher.yaml"
NAME = "antigen-af3-data-search-r01"
RUNTIME_CLAIM = "antigen-af3-runtime"
IMAGE = (
    "harbor-core.base.svc.cluster.local/qcyz/antigen-af3@"
    "sha256:35db7c1feb3368a7c72b0d1f60b295ed1473b562b61526db265fc0c446fd4373"
)
SEQUENCE = (
    "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"
)
SEQUENCE_SHA256 = "233b4b0b8c4616095bc3249f9375fc345d32af7deaef07117d0383c51d6f19aa"


def fold_input() -> dict:
    value = {
        "name": "t01-1ubq-af3-data-r01",
        "modelSeeds": [1],
        "sequences": [{"protein": {"id": "A", "sequence": SEQUENCE}}],
        "dialect": "alphafold3",
        "version": 1,
    }
    if hashlib.sha256(SEQUENCE.encode()).hexdigest() != SEQUENCE_SHA256:
        raise ValueError("Pinned 1UBQ sequence identity differs")
    return value


def documents() -> list[dict]:
    config = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "immutable": True,
        "data": {
            "run_af3_data_search.py": RUNNER.read_text(encoding="utf-8"),
            "fold_input.json": json.dumps(fold_input(), indent=2) + "\n",
        },
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
    runtime_claim = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": RUNTIME_CLAIM, "namespace": "him-ws"},
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "resources": {"requests": {"storage": "50Gi"}},
            "storageClassName": "ceph-rbd",
        },
    }
    container = {
        "name": "data-search",
        "image": IMAGE,
        "imagePullPolicy": "IfNotPresent",
        "command": ["/alphafold3_venv/bin/python", "-u", "-B", "/runner/run_af3_data_search.py"],
        "env": [
            {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"},
            {"name": "CUDA_VISIBLE_DEVICES", "value": ""},
            {"name": "JAX_PLATFORMS", "value": "cpu"},
        ],
        "resources": {
            "requests": {"cpu": "8", "memory": "64Gi", "ephemeral-storage": "512Mi"},
            "limits": {"cpu": "16", "memory": "96Gi", "ephemeral-storage": "4Gi"},
        },
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "seccompProfile": {"type": "RuntimeDefault"},
            "capabilities": {"drop": ["ALL"]},
        },
        "volumeMounts": [
            {"name": "runner", "mountPath": "/runner", "readOnly": True},
            {"name": "runner", "mountPath": "/input", "readOnly": True},
            {"name": "databases", "mountPath": "/databases", "readOnly": True},
            {"name": "weights", "mountPath": "/weights", "readOnly": True},
            {"name": "runtime", "mountPath": "/runtime"},
            {"name": "tmp", "mountPath": "/tmp"},
        ],
    }
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 28800,
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
                        {"name": "runner", "configMap": {"name": NAME}},
                        {"name": "databases", "persistentVolumeClaim": {
                            "claimName": "antigen-af3-databases", "readOnly": True}},
                        {"name": "weights", "persistentVolumeClaim": {
                            "claimName": "antigen-af3-models", "readOnly": True}},
                        {"name": "runtime", "persistentVolumeClaim": {"claimName": RUNTIME_CLAIM}},
                        {"name": "tmp", "emptyDir": {"sizeLimit": "4Gi"}},
                    ],
                },
            },
        },
    }
    documents = [config, policy, runtime_claim, job]
    json.loads(json.dumps(documents))
    return documents


def main() -> None:
    OUTPUT.write_text(yaml.safe_dump_all(documents(), sort_keys=False), encoding="utf-8")
    print("AF3_DATA_SEARCH_RENDERED", OUTPUT)


if __name__ == "__main__":
    main()
