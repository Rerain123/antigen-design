"""Deterministic, non-applying Kubernetes resource generation.

This module deliberately has no Kubernetes client dependency and no submit
operation. It creates reviewable dictionaries/YAML only. Cluster publication
and registry digests remain site-owned deployment inputs.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


DIGEST_IMAGE = re.compile(r"^[a-z0-9][a-z0-9._:/-]*@sha256:[0-9a-f]{64}$")
DNS_LABEL = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")

def scientific_network_policy(namespace="t01-phase1-real"):
    _name(namespace, 'namespace')
    return {"apiVersion":"networking.k8s.io/v1","kind":"NetworkPolicy",
            "metadata":{"name":"t01-scientific-offline","namespace":namespace},
            "spec":{"podSelector":{"matchLabels":{"app.kubernetes.io/component":"scientific-job"}},
                    "policyTypes":["Ingress","Egress"],"ingress":[],"egress":[]}}

# Verified local Docker image IDs from the current scientific-tool profiles.
# These are provenance inputs, not invented registry manifest digests.
SCIENTIFIC_SOURCE_IMAGE_IDS = {
    "deeptmhmm": "sha256:7f85781fadf8c89ddbafced691d05006caf6881b06aa5b9bae4bd531393bcd72",
    "structure": "sha256:bb6c6b5ce1add12dc9bda3538a218568a9e80c048c12525fc130eaa970dbb9e5",
    "bepipred": "sha256:e1aff495e254ca4da513286f4ada0e1e0a071a2ffd9e0bc8ae3d2e6c91384149",
    "netmhc": "sha256:c0a7239d4005484c1248b78de91bf7a76acffe0ed41f52614a54b6c20b3cf094",
    "blast": "sha256:81f118d2e4f7e11494d27fdbb99c9430423105afff50c4ae158db41d58a3fc57",
    "homology": "sha256:3679b2d22c59629380e47db3af59c7b4c3741e6330ab6962aa51ce526c67d32d",
    "proteinmpnn": "sha256:5b6baa8ebc5660bd3de9cf8b6d1694c7de35fadd23fea6cd7a8352a536e3f3af",
    "esm-if1": "sha256:926d4619df9759cd2417dcc9056b7bd648dca1d2adf15631aaad2e84a88d39cc",
    "thermompnn": "sha256:3cbd3c12b792a8b344347e6e9171d03deb7c5a115a6c4b8af27b84847dfdd847",
    "foldx": "sha256:66539e081922ce4c4fb504c9906feb64044ce668033e63fdc9299d020af8c851",
    "aggrescan3d": "sha256:c9e5a38b7d7f22c0b76678c5135ec4bf1af47cf77e8c9547a3bb4b9f7f2e938b",
}


def _name(value: str, label: str) -> str:
    if not isinstance(value, str) or len(value) > 63 or not DNS_LABEL.fullmatch(value):
        raise ValueError(f"{label} must be a Kubernetes DNS label")
    return value


def _digest_image(value: str, label: str) -> str:
    if not isinstance(value, str) or not DIGEST_IMAGE.fullmatch(value):
        raise ValueError(f"{label} must be a registry image pinned with @sha256")
    return value


def _security() -> dict[str, Any]:
    return {
        "allowPrivilegeEscalation": False,
        "capabilities": {"drop": ["ALL"]},
        "privileged": False,
        "readOnlyRootFilesystem": True,
        "runAsNonRoot": True,
        "seccompProfile": {"type": "RuntimeDefault"},
    }


def control_plane_documents(
    image: str,
    *,
    namespace: str = "t01-phase1-real",
    runtime_claim: str = "t01-phase1-real-runtime",
    storage_size: str = "2Ti",
    storage_class: str | None = None,
    credentials_json: str = '{"replace_at_site":true}',
) -> list[dict[str, Any]]:
    """Return the complete single-replica control-plane resource set."""
    _digest_image(image, "control-plane image")
    _name(namespace, "namespace")
    _name(runtime_claim, "runtime claim")
    if not re.fullmatch(r"[1-9][0-9]*(?:Mi|Gi|Ti)", storage_size):
        raise ValueError("storage size must use an explicit Mi/Gi/Ti quantity")
    labels = {"app.kubernetes.io/name": "t01-phase1-real", "app.kubernetes.io/component": "control-plane"}
    pod_security = {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001, "fsGroup": 10001, "seccompProfile": {"type": "RuntimeDefault"}}
    pvc_spec: dict[str, Any] = {"accessModes": ["ReadWriteOnce"], "resources": {"requests": {"storage": storage_size}}}
    if storage_class:
        _name(storage_class, "storage class")
        pvc_spec["storageClassName"] = storage_class
    return [
        {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace, "labels": {"pod-security.kubernetes.io/enforce": "restricted"}}},
        {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "t01-control-plane", "namespace": namespace}, "automountServiceAccountToken": False},
        {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "t01-service-credentials", "namespace": namespace}, "type": "Opaque", "stringData": {"credentials.json": credentials_json}},
        {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "t01-control-plane-config", "namespace": namespace}, "data": {"release.yaml": "completion_boundary: LOCAL_RELEASE_CANDIDATE_ONLY\nproduction_status: NOT_DEPLOYED\nscientific_gate: CLOSED\ngpu_count_estimate: 1\ngpu_memory_gib_estimate: 64\nproject_cpu_estimate: 32\nproject_memory_gib_estimate: 192\n"}},
        {"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": {"name": runtime_claim, "namespace": namespace}, "spec": pvc_spec},
        {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role", "metadata": {"name": "t01-scientific-job-controller", "namespace": namespace}, "rules": [
            {"apiGroups": ["batch"], "resources": ["jobs"], "verbs": ["create", "delete", "get", "list", "watch"]},
            {"apiGroups": [""], "resources": ["pods", "pods/log"], "verbs": ["get", "list", "watch"]},
            {"apiGroups": ["networking.k8s.io"], "resources": ["networkpolicies"], "verbs": ["get"]},
        ]},
        {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding", "metadata": {"name": "t01-control-plane-jobs", "namespace": namespace}, "subjects": [{"kind": "ServiceAccount", "name": "t01-control-plane", "namespace": namespace}], "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "t01-scientific-job-controller"}},
        {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "t01-control-plane", "namespace": namespace, "labels": labels}, "spec": {
            "replicas": 1, "strategy": {"type": "Recreate"}, "selector": {"matchLabels": labels}, "template": {"metadata": {"labels": labels}, "spec": {
                "serviceAccountName": "t01-control-plane", "automountServiceAccountToken": True, "securityContext": pod_security,
                "terminationGracePeriodSeconds": 30,
                "containers": [{"name": "service", "image": image, "imagePullPolicy": "IfNotPresent", "args": ["--host", "0.0.0.0", "--port", "18083", "--runtime-root", "/var/lib/t01/runtime"],
                    "env": [{"name": "T01_REAL_SERVICE_CREDENTIALS_FILE", "value": "/run/secrets/t01/credentials.json"}],
                    "ports": [{"name": "http", "containerPort": 18083, "protocol": "TCP"}],
                    "readinessProbe": {"httpGet": {"path": "/healthz", "port": "http"}, "periodSeconds": 5, "timeoutSeconds": 2},
                    "livenessProbe": {"httpGet": {"path": "/healthz", "port": "http"}, "initialDelaySeconds": 10, "periodSeconds": 10, "timeoutSeconds": 2},
                    "resources": {"requests": {"cpu": "2", "memory": "8Gi"}, "limits": {"cpu": "4", "memory": "16Gi"}}, "securityContext": _security(),
                    "volumeMounts": [{"name": "runtime", "mountPath": "/var/lib/t01"}, {"name": "credentials", "mountPath": "/run/secrets/t01", "readOnly": True}, {"name": "config", "mountPath": "/etc/t01", "readOnly": True}, {"name": "tmp", "mountPath": "/tmp"}]}],
                "volumes": [{"name": "runtime", "persistentVolumeClaim": {"claimName": runtime_claim}}, {"name": "credentials", "secret": {"secretName": "t01-service-credentials", "defaultMode": 0o400}}, {"name": "config", "configMap": {"name": "t01-control-plane-config", "defaultMode": 0o444}}, {"name": "tmp", "emptyDir": {"sizeLimit": "256Mi"}}],
            }}
        }},
        {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "t01-control-plane", "namespace": namespace, "labels": labels}, "spec": {"type": "ClusterIP", "selector": labels, "ports": [{"name": "http", "port": 80, "targetPort": "http", "protocol": "TCP"}]}},
        scientific_network_policy(namespace),
    ]


def scientific_job_spec(
    tool: str,
    execution_id: str,
    *,
    scientific_image: str,
    control_image: str,
    runtime_claim: str = "t01-phase1-real-runtime",
    asset_claim: str,
    namespace: str = "t01-phase1-real",
    gpu_resource_key: str | None = None,
    timeout_seconds: int = 900,
    attempt_path: str | None = None,
    runtime_job_id: str | None = None,
    image_pull_secrets: list[str] | None = None,
    database_subpath: str = 'database',
) -> dict[str, Any]:
    """Create one immutable scientific Job template without applying it."""
    if tool not in SCIENTIFIC_SOURCE_IMAGE_IDS:
        raise ValueError("unsupported scientific tool")
    _name(execution_id, "execution id")
    _name(namespace, "namespace")
    _name(runtime_claim, "runtime claim")
    _name(asset_claim, "asset claim")
    _digest_image(scientific_image, "scientific image")
    _digest_image(control_image, "control image")
    if image_pull_secrets is None:image_pull_secrets=[]
    if not isinstance(image_pull_secrets,list) or len(image_pull_secrets)>8:raise ValueError('Bounded image pull secret list required')
    for secret in image_pull_secrets:_name(secret,'image pull secret')
    if len(set(image_pull_secrets))!=len(image_pull_secrets):raise ValueError('Duplicate image pull secret')
    maximum_timeout = 14400 if tool == 'blast' else 7200
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= maximum_timeout:
        raise ValueError(f'Job timeout must be 1..{maximum_timeout} seconds')
    needs_gpu = tool in {"proteinmpnn", "esm-if1", "thermompnn"}
    resource_profile = {'deeptmhmm':('8','10Gi'),'bepipred':('8','10Gi'),'structure':('2','1Gi'),
                        'netmhc':('4','4Gi'),'blast':('4','16Gi'),'homology':('2','4Gi'),
                        'proteinmpnn':('2','4Gi'),'esm-if1':('2','6Gi'),'thermompnn':('2','6Gi'),'foldx':('2','2Gi'),
                        'aggrescan3d':('2','1Gi')}
    cpu,memory = resource_profile[tool]
    limits: dict[str, str] = {"cpu": cpu, "memory": memory}
    requests: dict[str, str] = dict(limits)
    if needs_gpu:
        if not gpu_resource_key or not re.fullmatch(r"[a-z0-9.-]+/[a-z0-9.-]+", gpu_resource_key):
            raise ValueError("GPU tools require an explicit extended resource key")
        limits[gpu_resource_key] = "1"
        requests[gpu_resource_key] = "1"
    annotations = {"t01.openai/source-image-id": SCIENTIFIC_SOURCE_IMAGE_IDS[tool], "t01.openai/not-submitted": "true", "t01.openai/scientific-gate": "CLOSED"}
    labels = {"app.kubernetes.io/name": "t01-phase1-real", "app.kubernetes.io/component": "scientific-job", "t01.openai/tool": tool}
    name = f"t01-{tool}-{execution_id}"
    if len(name) > 63:
        raise ValueError("derived Job name exceeds 63 characters")
    attempt = attempt_path or f"executions/{execution_id}"
    if not re.fullmatch(r'[A-Za-z0-9_/-]+',attempt) or any(p in ('','..','.') for p in attempt.split('/')):
        raise ValueError('Attempt path must be a bounded relative storage path')
    if len(attempt)>1024:raise ValueError('Attempt path too long')
    worker_relative = "container_probe.py" if tool == "deeptmhmm" else f"{tool.replace('-', '_')}/worker.py"
    python = "python3" if tool in {"blast", "foldx"} else "python"
    if tool=='aggrescan3d':python='/opt/conda/bin/python'
    mounts = [
        {"name": "runtime", "mountPath": "/input.json", "subPath": f"{attempt}/input.json", "readOnly": True},
        {"name": "runtime", "mountPath": "/input.fasta", "subPath": f"{attempt}/input.fasta", "readOnly": True},
        {"name": "runtime", "mountPath": "/native", "subPath": f"{attempt}/native", "readOnly": True},
        {"name": "runtime", "mountPath": "/out", "subPath": f"{attempt}/output"},
        {"name": "assets", "mountPath": "/t01/assets", "readOnly": True},
        {"name": "launcher", "mountPath": "/t01/launcher", "readOnly": True},
        {"name": "tmp", "mountPath": "/tmp"},
    ]
    environment = {'T01_TOOL_ASSET_ROOT':'/t01/assets','PYTHONUNBUFFERED':'1','PYTHONDONTWRITEBYTECODE':'1'}
    if tool in {'deeptmhmm','bepipred','proteinmpnn','esm-if1','thermompnn','foldx'}:
        mounts.append({'name':'assets','mountPath':'/app','subPath':'package','readOnly':True})
    if tool in {'deeptmhmm','bepipred'}:environment['CUDA_VISIBLE_DEVICES']='-1'
    if tool=='bepipred':environment['TORCH_HOME']='/torch'
    if tool=='structure':environment['MPLCONFIGDIR']='/tmp/matplotlib'
    if needs_gpu:environment.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',CUDA_CACHE_PATH='/tmp/cuda')
    if tool in {'foldx','thermompnn'}:environment['HOME']='/tmp'
    if tool=='esm-if1':
        if runtime_job_id is None:runtime_job_id='replace-at-site'
        environment['T01_JOB_ID']=runtime_job_id
    if tool not in {'proteinmpnn','esm-if1','thermompnn','foldx'}:
        mounts=[m for m in mounts if m['mountPath']!='/native']
    if tool in {"bepipred"}:
        mounts.append({"name": "assets", "mountPath": "/torch/hub/checkpoints", "subPath": "models", "readOnly": True})
    if tool in {"blast", "homology"}:
        if not re.fullmatch(r'database(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,127})?',database_subpath):raise ValueError('Invalid database subpath')
        mounts.append({"name": "assets", "mountPath": "/database", "subPath": database_subpath, "readOnly": True})
    if tool == "structure":
        mounts.extend([
            {"name": "runtime", "mountPath": "/input.structure", "subPath": f"{attempt}/input.structure", "readOnly": True},
            {"name": "runtime", "mountPath": "/binding.json", "subPath": f"{attempt}/binding.json", "readOnly": True},
            {"name": "launcher", "mountPath": "/code", "subPath": "code", "readOnly": True},
            {"name": "launcher", "mountPath": "/profile.json", "subPath": "profile.json", "readOnly": True},
            {"name": "launcher", "mountPath": "/worker", "subPath": "development/structure", "readOnly": True},
        ])
    if tool == "thermompnn":
        environment.update(WANDB_MODE='disabled',TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD='1')
        mounts.append({'name':'assets','mountPath':'/upstream','subPath':'package','readOnly':True})
        mounts.append({"name": "runtime", "mountPath": "/app/local.yaml", "subPath": f"{attempt}/native/runtime-local.yaml", "readOnly": True})
    if tool=='aggrescan3d':
        worker_relative='developability/a3d_worker.py'
        mounts=[m for m in mounts if m['mountPath'] not in ('/input.fasta','/out')]
        mounts.extend([
            {'name':'runtime','mountPath':'/input.pdb','subPath':f'{attempt}/input/a3d-structure.pdb','readOnly':True},
            {'name':'runtime','mountPath':'/out','subPath':f'{attempt}/output/a3d-native'},
        ])
        environment['HOME']='/tmp'
    stage = "import shutil; from pathlib import Path; " \
        "shutil.copytree('/app/src/t01_phase1_real/development','/t01/launcher/development',dirs_exist_ok=True); " \
        "shutil.copytree('/app/src/t01_structure_mapping','/t01/launcher/code/t01_structure_mapping',dirs_exist_ok=True); " \
        "shutil.copy2('/app/docs/project/phase1/PHASE1_REAL_W1_FREESASA_PROFILE.json','/t01/launcher/profile.json')"
    return {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": name, "namespace": namespace, "labels": labels, "annotations": annotations}, "spec": {
        "backoffLimit": 0, "activeDeadlineSeconds":timeout_seconds, "ttlSecondsAfterFinished": 86400, "template": {"metadata": {"labels": labels, "annotations": annotations}, "spec": {
            "restartPolicy": "Never", "automountServiceAccountToken": False,
            **({"imagePullSecrets":[{"name":secret} for secret in image_pull_secrets]} if image_pull_secrets else {}),
            "hostNetwork":False,"hostPID":False,"hostIPC":False,
            "terminationGracePeriodSeconds":10,
            "affinity":{"podAffinity":{"requiredDuringSchedulingIgnoredDuringExecution":[{
                "labelSelector":{"matchLabels":{"app.kubernetes.io/name":"t01-phase1-real","app.kubernetes.io/component":"control-plane"}},
                "topologyKey":"kubernetes.io/hostname"}]}},
            "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001, "fsGroup": 10001, "seccompProfile": {"type": "RuntimeDefault"}},
            "initContainers": [{"name": "stage-launcher", "image": control_image, "imagePullPolicy": "IfNotPresent", "command": ["python", "-B", "-c"],
                "args": [stage],
                "securityContext": _security(), "volumeMounts": [{"name": "launcher", "mountPath": "/t01/launcher"}, {"name": "tmp", "mountPath": "/tmp"}]}],
            "containers": [{"name": "worker", "image": scientific_image, "imagePullPolicy": "IfNotPresent", "command": [python, "-B", f"/t01/launcher/development/{worker_relative}"],
                "env": [{"name":key,"value":value} for key,value in environment.items()], "resources": {"requests": requests, "limits": limits}, "securityContext": _security(), "volumeMounts": mounts}],
            "volumes": [{"name": "runtime", "persistentVolumeClaim": {"claimName": runtime_claim}}, {"name": "assets", "persistentVolumeClaim": {"claimName": asset_claim}}, {"name": "launcher", "emptyDir": {"sizeLimit": "4Mi"}}, {"name": "tmp", "emptyDir": {"sizeLimit": "2Gi"}}],
        }}
    }}


def job_state(job: dict[str, Any]) -> dict[str, Any]:
    """Map an observed Kubernetes Job to the existing factual lifecycle."""
    metadata = job.get("metadata") or {}
    status = job.get("status") or {}
    conditions = {row.get("type"): row for row in status.get("conditions", []) if row.get("status") == "True"}
    if metadata.get("deletionTimestamp"):
        state, reason = "stop_requested", "KUBERNETES_JOB_DELETING"
    elif "Complete" in conditions or status.get("succeeded", 0) > 0:
        state, reason = "succeeded", None
    elif "Failed" in conditions or status.get("failed", 0) > 0:
        state, reason = "failed", (conditions.get("Failed") or {}).get("reason") or "KUBERNETES_JOB_FAILED"
    elif status.get("active", 0) > 0:
        state, reason = "running", None
    elif metadata.get("uid"):
        state, reason = "queued", None
    else:
        state, reason = "reconciling", "KUBERNETES_JOB_OBSERVATION_INCOMPLETE"
    return {"state": state, "reason_code": reason, "job_uid": metadata.get("uid"), "resource_version": metadata.get("resourceVersion")}


def redacted_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy safe for evidence bundles."""
    result = deepcopy(documents)
    for item in result:
        if item.get("kind") == "Secret":
            item["stringData"] = {key: "<redacted>" for key in item.get("stringData", {})}
            item.pop("data", None)
    return result
