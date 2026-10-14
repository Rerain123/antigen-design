"""HTTP client used only inside the isolated local Linux acceptance network."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
import zipfile


TOKEN_A = "local-operator-" + "a" * 40
TOKEN_B = "local-attacker-" + "b" * 40


def call(base, path, token=None, body=None):
    data = json.dumps(body, sort_keys=True, separators=(",", ":")).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(base + path, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=610) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def value(*args, **kwargs):
    status, _, raw = call(*args, **kwargs)
    return status, json.loads(raw)


def workflow(label, bepipred=False):
    options = ("topology", "blast", "bepipred", "netmhc", "homology", "domains", "developability")
    analysis = {name: None for name in options}
    if bepipred:
        analysis["bepipred"] = {"timeout_seconds": 60}
    return {
        "protein_sequence": "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG",
        "user_sequence_id": label, "host_species": "Homo sapiens", "expression_host": None,
        "organism": None, "structure": None, "analysis": analysis, "reuse_jobs": {}, "timeout_seconds": 300,
    }


def wait(base, job_id, seconds=300):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status, current = value(base, f"/v1/workflows/{job_id}", TOKEN_A)
        assert status == 200, current
        if current["terminal"]:
            return current
        time.sleep(0.2)
    raise AssertionError("job did not reach a terminal state")


def validate_report(raw):
    assert zipfile.is_zipfile(io.BytesIO(raw))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert set(archive.namelist()) == {"manifest.json"} | {row["path"] for row in manifest["files"]}
        for row in manifest["files"]:
            content = archive.read(row["path"])
            assert len(content) == row["size_bytes"]
            assert hashlib.sha256(content).hexdigest() == row["sha256"]
        workflow_report = json.loads(archive.read("workflow.json"))
        assert workflow_report["scientific_gate"] == "CLOSED"
        assert workflow_report["production_status"] == "NOT_DEPLOYED"
        assert workflow_report["usable_for_pipeline"] is False
    return hashlib.sha256(raw).hexdigest(), len(manifest["files"]) + 1


def prepare(base):
    status, health = value(base, "/healthz")
    assert status == 200 and health["production_status"] == "NOT_DEPLOYED"
    status, _ = value(base, "/v1/workflows/t01p1r-job-" + "0" * 32)
    assert status == 401
    request = {"idempotency_key": "linux-cancel", "request": workflow("linux-cancel")}
    status, submitted = value(base, "/v1/workflows", TOKEN_A, request)
    assert status == 201
    status, cancelled = value(base, f"/v1/workflows/{submitted['job_id']}/cancel", TOKEN_A, {"idempotency_key": "cancel-once"})
    assert status == 202 and cancelled["action"] == "CANCEL_REQUESTED"
    assert wait(base, submitted["job_id"])["state"] == "cancelled"
    status, queued = value(base, "/v1/workflows", TOKEN_A, {"idempotency_key": "linux-restart", "request": workflow("linux-restart")})
    assert status == 201 and queued["state"] in {"queued", "running"}
    print(json.dumps({"phase": "prepare", "cancelled_job_id": submitted["job_id"], "restart_job_id": queued["job_id"]}, sort_keys=True))


def verify(base):
    structure = base64.b64encode(b"ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n").decode()
    status, upload = value(base, "/v1/uploads", TOKEN_A, {"name": "input.pdb", "media_type": "chemical/x-pdb", "content_base64": structure})
    assert status == 201 and upload["size_bytes"] > 0
    status, invalid_upload = value(base, "/v1/uploads", TOKEN_A, {"name": "../input.pdb", "media_type": "chemical/x-pdb", "content_base64": structure})
    assert status == 422 and invalid_upload["error"]["code"] == "INVALID_REQUEST"
    request = {"idempotency_key": "linux-restart", "request": workflow("linux-restart")}
    status, replay = value(base, "/v1/workflows", TOKEN_A, request)
    assert status == 200 and replay["action"] == "REPLAYED"
    done = wait(base, replay["job_id"])
    assert done["state"] == "succeeded"
    status, _, report = call(base, f"/v1/workflows/{replay['job_id']}/report", TOKEN_A)
    assert status == 200
    report_sha, report_files = validate_report(report)
    changed = {"idempotency_key": "linux-restart", "request": workflow("changed")}
    status, conflict = value(base, "/v1/workflows", TOKEN_A, changed)
    assert status == 409 and conflict["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    status, forbidden = value(base, f"/v1/workflows/{replay['job_id']}", TOKEN_B)
    assert status == 403 and forbidden["error"]["code"] == "FORBIDDEN"
    status, scientific = value(base, "/v1/workflows", TOKEN_A, {"idempotency_key": "linux-missing-bepipred", "request": workflow("missing-bepipred", True)})
    assert status == 201
    scientific_done = wait(base, scientific["job_id"])
    node = scientific_done["nodes"]["bepipred"]
    assert node["state"] == "failed" and node["reason_code"] == "ASSET_MISSING"
    status, cancelled = value(base, "/v1/workflows", TOKEN_A, {"idempotency_key": "linux-cancel", "request": workflow("linux-cancel")})
    assert status == 200 and cancelled["state"] == "cancelled"
    status, recovered_cancelled = value(base, f"/v1/workflows/{cancelled['job_id']}/recover", TOKEN_A, {"idempotency_key": "recover-once"})
    assert status == 202 and recovered_cancelled["state"] == "cancelled"
    status, retried = value(base, f"/v1/workflows/{cancelled['job_id']}/retry", TOKEN_A, {"idempotency_key": "retry-once"})
    assert status == 202 and retried["action"] == "RETRY_CREATED"
    assert wait(base, retried["job_id"])["state"] == "succeeded"
    print(json.dumps({"phase": "verify", "job_id": replay["job_id"], "report_sha256": report_sha, "report_files": report_files,
                      "scientific_failure": node["reason_code"], "retry_job_id": retried["job_id"]}, sort_keys=True))


def snapshot(base):
    status, replay = value(base, "/v1/workflows", TOKEN_A, {"idempotency_key": "linux-restart", "request": workflow("linux-restart")})
    assert status == 200 and replay["state"] == "succeeded"
    status, _, report = call(base, f"/v1/workflows/{replay['job_id']}/report", TOKEN_A)
    assert status == 200
    report_sha, report_files = validate_report(report)
    print(json.dumps({"phase": "snapshot", "job_id": replay["job_id"], "report_sha256": report_sha, "report_files": report_files}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "verify", "snapshot"))
    parser.add_argument("--base", default="http://t01-rc-service:18083")
    args = parser.parse_args()
    globals()[args.phase](args.base)


if __name__ == "__main__":
    main()
