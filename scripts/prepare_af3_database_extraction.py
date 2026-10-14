"""Render the offline, read-write AF3 database extraction Job."""
from __future__ import annotations

import json
from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/extract_af3_databases.py"
MANIFEST = ROOT / "deploy/alphafold3/database-manifest.v3.0.json"
OUTPUT = ROOT / "deploy/alphafold3/databases-extract.r03.rancher.yaml"
NAME = "antigen-af3-databases-extract-r03"
IMAGE = "harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:fba5a32c0550e56a5310160e2fc49d647fcd27d76851073a2d82cc935fb4c2fc"


def documents() -> list[dict]:
    config = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": NAME, "namespace": "him-ws"},
              "immutable": True, "data": {"extract_af3_databases.py": SOURCE.read_text(encoding="utf-8"),
                                             "database-manifest.json": MANIFEST.read_text(encoding="utf-8")}}
    policy = {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
              "metadata": {"name": NAME, "namespace": "him-ws"},
              "spec": {"podSelector": {"matchLabels": {"app": NAME}}, "policyTypes": ["Ingress", "Egress"]}}
    container = {"name": "extract", "image": IMAGE,
                 "command": ["python", "-u", "-B", "/extract/extract_af3_databases.py",
                             "/databases/alphafold3-v3.0/archives", "/databases/alphafold3-v3.0/unpacked-r03", "/extract/database-manifest.json", "--run-id", "r03"],
                 "resources": {"requests": {"cpu": "500m", "memory": "512Mi", "ephemeral-storage": "256Mi"},
                               "limits": {"cpu": "2", "memory": "4Gi", "ephemeral-storage": "1Gi"}},
                 "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                     "capabilities": {"drop": ["ALL"]}},
                 "volumeMounts": [{"name": "databases", "mountPath": "/databases"},
                                  {"name": "extract", "mountPath": "/extract", "readOnly": True}]}
    pod = {"restartPolicy": "Never", "automountServiceAccountToken": False,
           "imagePullSecrets": [{"name": "harbor"}],
           "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001,
                               "fsGroup": 10001, "fsGroupChangePolicy": "OnRootMismatch"},
           "containers": [container],
           "volumes": [{"name": "databases", "persistentVolumeClaim": {"claimName": "antigen-af3-databases"}},
                       {"name": "extract", "configMap": {"name": NAME}}]}
    job = {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": NAME, "namespace": "him-ws"},
           "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 172800,
                    "template": {"metadata": {"labels": {"app": NAME}}, "spec": pod}}}
    return [config, policy, job]


def main() -> None:
    OUTPUT.write_text(yaml.safe_dump_all(documents(), sort_keys=False), encoding="utf-8")
    print("AF3_DATABASE_EXTRACTION_RENDERED", OUTPUT)


if __name__ == "__main__":
    main()
