"""Render the pinned, rootless, zero-GPU AF3 environment build Job."""
from __future__ import annotations

import json
from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/fetch_af3_source.py"
OUTPUT = ROOT / "deploy/alphafold3/environment-build.r06.rancher.yaml"
NAME = "antigen-af3-environment-build-r06"
CACHE_CLAIM = "antigen-af3-build-cache-r06"
SOURCE_IMAGE = "harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:fba5a32c0550e56a5310160e2fc49d647fcd27d76851073a2d82cc935fb4c2fc"
BUILDKIT_IMAGE = "moby/buildkit@sha256:995077ff90af1afff56ff23018699d7511d122b2b111041f2011bd12afd5c0fe"
DESTINATION = "harbor-core.base.svc.cluster.local/qcyz/antigen-af3:v3.0.2-f6a5aec-r06"


BUILD_COMMAND = f"""umask 077
echo AF3_ENVIRONMENT_BUILD_START {DESTINATION}
success=0
for attempt in 1 2 3; do
  echo AF3_ENVIRONMENT_BUILD_ATTEMPT $attempt 3
  rm -f /workspace/build-metadata.json
  if buildctl-daemonless.sh build \\
    --frontend dockerfile.v0 \\
    --local context=/workspace/source \\
    --local dockerfile=/workspace/source/docker \\
    --opt filename=Dockerfile \\
    --opt platform=linux/amd64 \\
    --output type=image,name={DESTINATION},push=true \\
    --metadata-file /workspace/build-metadata.json; then
    success=1
    break
  fi
  echo AF3_ENVIRONMENT_BUILD_RETRY $attempt
  sleep 15
done
test "$success" = 1
echo AF3_ENVIRONMENT_BUILD_PUSHED {DESTINATION}
cat /workspace/source-receipt.json
cat /workspace/build-metadata.json
"""


def documents() -> list[dict]:
    config = {
        "apiVersion": "v1", "kind": "ConfigMap",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "immutable": True,
        "data": {
            "fetch_af3_source.py": SOURCE.read_text(encoding="utf-8"),
            "buildkitd.toml": (
                'debug = false\n'
                '[registry."docker.io"]\n'
                '  mirrors = ["dockerproxy.net"]\n'
                '[registry."harbor-core.base.svc.cluster.local"]\n'
                '  http = true\n'
                '  insecure = true\n'
            ),
        },
    }
    policy = {
        "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {
            "podSelector": {"matchLabels": {"app": NAME}},
            "policyTypes": ["Ingress", "Egress"],
            "egress": [
                {"ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}]},
                # The CNI evaluates ClusterIP traffic after DNAT on this cluster, so
                # restricting this rule to the Harbor service port blocks its backend
                # targetPort.  The build already requires public TCP egress; allow TCP
                # ports while retaining DNS-only UDP and ingress isolation.
                {"ports": [{"protocol": "TCP"}]},
            ],
        },
    }
    cache_claim = {
        "apiVersion": "v1", "kind": "PersistentVolumeClaim",
        "metadata": {"name": CACHE_CLAIM, "namespace": "him-ws"},
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "resources": {"requests": {"storage": "30Gi"}},
            "storageClassName": "ceph-rbd",
        },
    }
    init = {
        "name": "source", "image": SOURCE_IMAGE,
        "command": ["python", "-u", "-B", "/scripts/fetch_af3_source.py", "/workspace"],
        "resources": {
            "requests": {"cpu": "100m", "memory": "128Mi", "ephemeral-storage": "32Mi"},
            "limits": {"cpu": "1", "memory": "512Mi", "ephemeral-storage": "128Mi"},
        },
        "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                            "seccompProfile": {"type": "RuntimeDefault"},
                            "capabilities": {"drop": ["ALL"]}},
        "volumeMounts": [
            {"name": "workspace", "mountPath": "/workspace"},
            {"name": "config", "mountPath": "/scripts", "readOnly": True},
        ],
    }
    builder = {
        "name": "builder", "image": BUILDKIT_IMAGE,
        "command": ["/bin/sh", "-ec", BUILD_COMMAND],
        "env": [{"name": "BUILDKITD_FLAGS", "value": "--oci-worker-no-process-sandbox --config /etc/buildkit/buildkitd.toml"}],
        "resources": {
            "requests": {"cpu": "4", "memory": "8Gi", "ephemeral-storage": "20Gi"},
            "limits": {"cpu": "8", "memory": "16Gi", "ephemeral-storage": "50Gi"},
        },
        "securityContext": {"allowPrivilegeEscalation": True,
                            "seccompProfile": {"type": "Unconfined"},
                            "appArmorProfile": {"type": "Unconfined"},
                            "capabilities": {"drop": ["ALL"], "add": ["SETUID", "SETGID"]}},
        "volumeMounts": [
            {"name": "workspace", "mountPath": "/workspace"},
            {"name": "state", "mountPath": "/home/user/.local/share/buildkit"},
            {"name": "tmp", "mountPath": "/tmp"},
            {"name": "registry-auth", "mountPath": "/home/user/.docker", "readOnly": True},
            {"name": "config", "mountPath": "/etc/buildkit/buildkitd.toml",
             "subPath": "buildkitd.toml", "readOnly": True},
        ],
    }
    pod_spec = {
        "restartPolicy": "Never", "automountServiceAccountToken": False,
        "imagePullSecrets": [{"name": "harbor"}],
        "securityContext": {"runAsNonRoot": True, "runAsUser": 1000, "runAsGroup": 1000,
                            "fsGroup": 1000, "fsGroupChangePolicy": "OnRootMismatch"},
        "initContainers": [init], "containers": [builder],
        "volumes": [
            {"name": "workspace", "emptyDir": {"sizeLimit": "128Mi"}},
            {"name": "state", "persistentVolumeClaim": {"claimName": CACHE_CLAIM}},
            {"name": "tmp", "emptyDir": {"sizeLimit": "4Gi"}},
            {"name": "registry-auth", "secret": {"secretName": "harbor",
                "items": [{"key": ".dockerconfigjson", "path": "config.json"}]}},
            {"name": "config", "configMap": {"name": NAME}},
        ],
    }
    job = {
        "apiVersion": "batch/v1", "kind": "Job",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 21600,
                 "template": {"metadata": {"labels": {"app": NAME}},
                    "spec": pod_spec}},
    }
    json.loads(json.dumps([config, policy, cache_claim, job]))
    return [config, policy, cache_claim, job]


def main() -> None:
    OUTPUT.write_text(yaml.safe_dump_all(documents(), sort_keys=False), encoding="utf-8")
    print("AF3_ENVIRONMENT_BUILD_RENDERED", OUTPUT)


if __name__ == "__main__":
    main()
