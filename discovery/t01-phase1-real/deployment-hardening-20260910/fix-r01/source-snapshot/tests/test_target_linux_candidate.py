import json
import hashlib

import pytest

from t01_phase1_real.deployment.kubernetes import SCIENTIFIC_SOURCE_IMAGE_IDS, control_plane_documents, job_state, redacted_documents, scientific_job_spec
from scripts.build_target_linux_candidate import RUNTIME_SCRIPT_MAP
from scripts.verify_target_linux_candidate import verify_index


DIGEST = "registry.local/t01/control@sha256:" + "a" * 64
GPU_TOOLS = {"deeptmhmm", "bepipred", "structure", "proteinmpnn", "esm-if1", "thermompnn"}


def test_control_plane_is_single_replica_recreate_persistent_and_restricted():
    docs = control_plane_documents(DIGEST)
    kinds = [row["kind"] for row in docs]
    assert kinds == ["Namespace", "ServiceAccount", "Secret", "ConfigMap", "PersistentVolumeClaim", "Role", "RoleBinding", "Deployment", "Service", "NetworkPolicy"]
    deployment = next(row for row in docs if row["kind"] == "Deployment")
    assert deployment["spec"]["replicas"] == 1
    assert deployment["spec"]["strategy"] == {"type": "Recreate"}
    pod = deployment["spec"]["template"]["spec"]
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert pod["containers"][0]["securityContext"]["readOnlyRootFilesystem"] is True
    assert not any("hostPath" in volume for volume in pod["volumes"])
    assert pod["containers"][0]["resources"] == {"requests": {"cpu": "2", "memory": "8Gi"}, "limits": {"cpu": "4", "memory": "16Gi"}}
    assert "docker.sock" not in json.dumps(docs)
    role = next(row for row in docs if row["kind"] == "Role")
    assert "secrets" not in json.dumps(role)
    pvc = next(row for row in docs if row["kind"] == "PersistentVolumeClaim")
    assert pvc["spec"]["resources"]["requests"]["storage"] == "2Ti"


def test_secret_is_redacted_from_evidence_copy():
    docs = control_plane_documents(DIGEST, credentials_json="sensitive")
    redacted = redacted_documents(docs)
    assert "sensitive" not in json.dumps(redacted)
    assert "sensitive" in json.dumps(docs)


@pytest.mark.parametrize("tool", sorted(SCIENTIFIC_SOURCE_IMAGE_IDS))
def test_scientific_jobs_are_digest_pinned_non_applying_and_isolated(tool):
    kwargs = {"gpu_resource_key": "nvidia.com/gpu"} if tool in GPU_TOOLS else {}
    job = scientific_job_spec(tool, "e123", scientific_image=f"registry.local/t01/{tool}@sha256:" + "b" * 64, control_image=DIGEST, asset_claim=f"t01-{tool}-assets", **kwargs)
    pod = job["spec"]["template"]["spec"]
    assert job["metadata"]["annotations"]["t01.openai/not-submitted"] == "true"
    assert job["metadata"]["annotations"]["t01.openai/source-image-id"] == SCIENTIFIC_SOURCE_IMAGE_IDS[tool]
    assert pod["automountServiceAccountToken"] is False
    assert pod["containers"][0]["securityContext"]["privileged"] is False
    assert pod["containers"][0]["securityContext"]["readOnlyRootFilesystem"] is True
    assert not any("hostPath" in volume for volume in pod["volumes"])
    command = " ".join(pod["containers"][0]["command"])
    assert "/t01/launcher/development/" in command


def test_gpu_and_digest_inputs_fail_closed():
    with pytest.raises(ValueError, match="@sha256"):
        control_plane_documents("registry.local/t01/control:latest")
    with pytest.raises(ValueError, match="GPU"):
        scientific_job_spec("thermompnn", "e1", scientific_image="r/x@sha256:" + "b" * 64, control_image=DIGEST, asset_claim="assets")
    with pytest.raises(ValueError, match="unsupported"):
        scientific_job_spec("unknown", "e1", scientific_image="r/x@sha256:" + "b" * 64, control_image=DIGEST, asset_claim="assets")


def test_job_state_mapping_uses_observed_conditions_only():
    assert job_state({"metadata": {"uid": "u"}, "status": {"active": 1}})["state"] == "running"
    assert job_state({"metadata": {"uid": "u"}, "status": {"conditions": [{"type": "Complete", "status": "True"}]}})["state"] == "succeeded"
    failed = job_state({"metadata": {"uid": "u"}, "status": {"conditions": [{"type": "Failed", "status": "True", "reason": "DeadlineExceeded"}]}})
    assert failed == {"state": "failed", "reason_code": "DeadlineExceeded", "job_uid": "u", "resource_version": None}
    assert job_state({"metadata": {"uid": "u", "deletionTimestamp": "now"}})["state"] == "stop_requested"
    assert job_state({})["state"] == "reconciling"


def test_candidate_index_detects_byte_tamper(tmp_path):
    payload = tmp_path / "payload.txt"
    payload.write_bytes(b"accepted")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    (tmp_path / "index.json").write_text(json.dumps({"indexed_files": 1, "files": [{"path": "payload.txt", "size_bytes": 8, "sha256": digest}]}), encoding="utf-8")
    assert verify_index(tmp_path)["indexed_files"] == 1
    payload.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="byte mismatch"):
        verify_index(tmp_path)


def test_linux_stage_replaces_child_process_entry_points():
    mapping = dict(RUNTIME_SCRIPT_MAP)
    assert mapping["t01_linux_development_supervisor.py"] == "t01_development_supervisor.py"
    assert mapping["t01_linux_w1_supervisor.py"] == "w1_runtime_supervisor.py"
    assert mapping["t01_linux_w1_worker.py"] == "w1_runtime_worker.py"
