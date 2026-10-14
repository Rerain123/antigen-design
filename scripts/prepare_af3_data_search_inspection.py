"""Render a read-only, zero-GPU verifier for AF3 data-search output."""
from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/inspect_af3_data_search.py"
OUTPUT = ROOT / "deploy/alphafold3/data-search-inspect.r01.rancher.yaml"
NAME = "antigen-af3-data-search-inspect-r01"
IMAGE = (
    "harbor-core.base.svc.cluster.local/qcyz/antigen-af3@"
    "sha256:35db7c1feb3368a7c72b0d1f60b295ed1473b562b61526db265fc0c446fd4373"
)


def documents() -> list[dict]:
    config = {
        "apiVersion": "v1", "kind": "ConfigMap",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "immutable": True,
        "data": {"inspect_af3_data_search.py": SOURCE.read_text(encoding="utf-8")},
    }
    policy = {
        "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {"podSelector": {"matchLabels": {"app": NAME}},
                 "policyTypes": ["Ingress", "Egress"]},
    }
    job = {
        "apiVersion": "batch/v1", "kind": "Job",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {
            "backoffLimit": 0, "activeDeadlineSeconds": 1800,
            "template": {"metadata": {"labels": {"app": NAME}}, "spec": {
                "restartPolicy": "Never", "automountServiceAccountToken": False,
                "imagePullSecrets": [{"name": "harbor"}],
                "securityContext": {"runAsNonRoot": True, "runAsUser": 10001,
                                    "runAsGroup": 10001, "fsGroup": 10001,
                                    "fsGroupChangePolicy": "OnRootMismatch"},
                "containers": [{
                    "name": "inspect", "image": IMAGE, "imagePullPolicy": "IfNotPresent",
                    "command": ["/alphafold3_venv/bin/python", "-u", "-B", "/inspect/inspect_af3_data_search.py"],
                    "resources": {"requests": {"cpu": "100m", "memory": "256Mi", "ephemeral-storage": "128Mi"},
                                  "limits": {"cpu": "1", "memory": "1Gi", "ephemeral-storage": "1Gi"}},
                    "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                        "seccompProfile": {"type": "RuntimeDefault"},
                                        "capabilities": {"drop": ["ALL"]}},
                    "volumeMounts": [{"name": "inspect", "mountPath": "/inspect", "readOnly": True},
                                     {"name": "runtime", "mountPath": "/runtime", "readOnly": True},
                                     {"name": "tmp", "mountPath": "/tmp"}],
                }],
                "volumes": [{"name": "inspect", "configMap": {"name": NAME}},
                            {"name": "runtime", "persistentVolumeClaim": {"claimName": "antigen-af3-runtime", "readOnly": True}},
                            {"name": "tmp", "emptyDir": {"sizeLimit": "1Gi"}}],
            }},
        },
    }
    documents = [config, policy, job]
    json.loads(json.dumps(documents))
    return documents


def main() -> None:
    OUTPUT.write_text(yaml.safe_dump_all(documents(), sort_keys=False), encoding="utf-8")
    print("AF3_DATA_SEARCH_INSPECTION_RENDERED", OUTPUT)


if __name__ == "__main__":
    main()
