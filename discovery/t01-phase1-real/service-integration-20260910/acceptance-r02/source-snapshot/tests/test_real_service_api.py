import base64
import io
import json
import threading
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime

import pytest
import yaml

from t01_phase1_real.common import TERMINAL, sha
from t01_phase1_real.service_api import Credentials, Phase1RealServiceServer, Service, ServiceConfig, ServiceError
from t01_phase1_real.service_api.dify import (
    APP_NAME, PROVIDER_ID, PROVIDER_TOKEN, bound_bytes, semantic_graph, template_bytes,
)
from t01_phase1_real.service_api import app as service_app


TOKEN_A = "a" * 48
TOKEN_B = "b" * 48


def credentials():
    return Credentials.from_document({"credentials": [
        {"token": TOKEN_A, "principal": "tenant-a", "scopes": ["submit", "query", "control", "download", "upload"]},
        {"token": TOKEN_B, "principal": "tenant-b", "scopes": ["submit", "query", "control", "download", "upload"]},
    ]})


def body():
    from t01_phase1_real.development.workflow import policy
    return {
        "protein_sequence": "ACDEFGHIKLMNPQRSTVWY",
        "user_sequence_id": "service-test",
        "host_species": "Homo sapiens",
        "expression_host": None,
        "organism": None,
        "structure": None,
        "analysis": {name: None for name in policy.OPTIONS},
        "reuse_jobs": {},
        "timeout_seconds": 300,
    }


def principal(creds, token=TOKEN_A, scope="query"):
    return creds.authenticate("Bearer " + token, scope)


def wait(service, owner, job_id):
    value = service.wait(owner, job_id, 30)
    assert value["state"] in TERMINAL
    return value


def test_credentials_are_exact_constant_time_and_scoped():
    creds = credentials()
    assert principal(creds).principal_id == "tenant-a"
    assert creds.inventory()[0]["token_sha256"] == sha(TOKEN_A.encode())
    with pytest.raises(ServiceError) as error:
        creds.authenticate(None, "query")
    assert error.value.status == 401
    limited = Credentials.from_document({"credentials": [
        {"token": "x" * 32, "principal": "reader", "scopes": ["query"]}
    ]})
    with pytest.raises(ServiceError) as error:
        limited.authenticate("Bearer " + "x" * 32, "control")
    assert error.value.status == 403


def test_submit_replay_owner_isolation_report_and_retry(tmp_path):
    creds = credentials()
    service = Service(ServiceConfig(tmp_path / "runtime"), creds)
    owner_a = principal(creds)
    owner_b = principal(creds, TOKEN_B)
    first = service.submit(owner_a, {"idempotency_key": "same", "request": body()})
    assert first["action"] == "CREATED"
    replay = service.submit(owner_a, {"idempotency_key": "same", "request": body()})
    assert replay["action"] == "REPLAYED" and replay["job_id"] == first["job_id"]
    changed = body()
    changed["user_sequence_id"] = "changed"
    with pytest.raises(ServiceError) as error:
        service.submit(owner_a, {"idempotency_key": "same", "request": changed})
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    with pytest.raises(ServiceError) as error:
        service.status(owner_b, first["job_id"])
    assert error.value.status == 403
    assert wait(service, owner_a, first["job_id"])["state"] == "succeeded"
    report = service.report(owner_a, first["job_id"])
    assert sha(report["content"]) == report["sha256"]
    with zipfile.ZipFile(io.BytesIO(report["content"])) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert all(sha(archive.read(row["path"])) == row["sha256"] for row in manifest["files"])
    with pytest.raises(ServiceError) as error:
        service.retry(owner_a, first["job_id"], "retry-success")
    assert error.value.code == "INVALID_STATE"
    service.shutdown()


def test_upload_is_registered_bounded_and_owner_scoped(tmp_path):
    creds = credentials()
    service = Service(ServiceConfig(tmp_path / "runtime"), creds)
    owner_a = principal(creds)
    owner_b = principal(creds, TOKEN_B)
    uploaded = service.upload(owner_a, {
        "name": "input.pdb", "media_type": "chemical/x-pdb",
        "content_base64": base64.b64encode(b"ATOM\n").decode(),
    })
    metadata, raw = service.store.upload_bytes(owner_a, uploaded["upload_id"])
    assert raw == b"ATOM\n" and metadata["sha256"] == sha(raw)
    with pytest.raises(ServiceError) as error:
        service.store.upload_bytes(owner_b, uploaded["upload_id"])
    assert error.value.status == 403
    with pytest.raises(ServiceError):
        service.upload(owner_a, {"name": "../input.pdb", "media_type": "chemical/x-pdb", "content_base64": "QQ=="})
    service.shutdown()


def test_cancel_recover_and_retry_are_idempotent(tmp_path):
    creds = credentials()
    service = Service(ServiceConfig(tmp_path / "runtime", dispatch_start_delay_seconds=1), creds)
    owner = principal(creds)
    submitted = service.submit(owner, {"idempotency_key": "cancelled", "request": body()})
    cancelled = service.cancel(owner, submitted["job_id"], "cancel-key")
    assert cancelled["state"] == "cancelled"
    replay = service.cancel(owner, submitted["job_id"], "cancel-key")
    assert replay["action"] == "CANCEL_REPLAYED"
    recovered = service.recover(owner, submitted["job_id"], "recover-key")
    assert recovered["state"] == "cancelled"
    retried = service.retry(owner, submitted["job_id"], "retry-key")
    assert retried["job_id"] != submitted["job_id"]
    assert retried["action"] == "RETRY_CREATED"
    assert service.retry(owner, submitted["job_id"], "retry-key")["job_id"] == retried["job_id"]
    assert wait(service, owner, retried["job_id"])["state"] == "succeeded"
    service.shutdown()


def test_drive_waits_for_child_supervisor_registration(tmp_path, monkeypatch):
    creds = credentials()
    service = Service(ServiceConfig(tmp_path / "runtime"), creds)
    owner = principal(creds)

    class RuntimeFixture:
        supervisor = None
        recover_calls = 0

        def get(self, job_id):
            if job_id == "workflow":
                return {"state": "running" if self.recover_calls == 0 else "succeeded"}
            return {"state": "running", "started_at": datetime.now(UTC).isoformat()}

        def execution(self, job_id):
            if job_id == "workflow":
                return {"nodes": {"bepipred": {"job_id": "child"}}}
            return {"phase": "spawn_intent", "supervisor": self.supervisor, "container_started": False}

        def recover(self, job_id):
            assert self.supervisor == {"pid": 1, "birth": "fixture"}
            self.recover_calls += 1
            return {"state": "succeeded"}

    runtime = RuntimeFixture()
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        runtime.supervisor = {"pid": 1, "birth": "fixture"}

    monkeypatch.setattr(service, "runtime", lambda _: runtime)
    monkeypatch.setattr(service_app.time, "sleep", sleep)
    service._drive(owner, "workflow", recovering=True)
    assert sleeps == [0.25]
    assert runtime.recover_calls == 1
    service.shutdown()


def request(url, method="GET", token=None, value=None):
    headers = {}
    data = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if value is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(value, separators=(",", ":")).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return response.status, response.headers, raw
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


def test_authenticated_http_and_mcp_surface(tmp_path):
    creds = credentials()
    service = Service(ServiceConfig(tmp_path / "runtime"), creds)
    server = Phase1RealServiceServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, _, raw = request(base + "/healthz")
        assert status == 200 and json.loads(raw)["scientific_gate"] == "CLOSED"
        assert request(base + "/v1/workflows", "POST", value={})[0] == 401
        status, _, raw = request(base + "/v1/workflows", "POST", TOKEN_A, {
            "idempotency_key": "http", "request": body(),
        })
        assert status == 201
        job_id = json.loads(raw)["job_id"]
        status, _, raw = request(base + f"/v1/workflows/{job_id}", token=TOKEN_B)
        assert status == 403 and json.loads(raw)["error"]["code"] == "FORBIDDEN"
        wait(service, principal(creds), job_id)
        status, headers, package = request(base + f"/v1/workflows/{job_id}/report", token=TOKEN_A)
        assert status == 200 and headers["Content-Type"] == "application/zip" and zipfile.is_zipfile(io.BytesIO(package))
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        status, _, raw = request(base + "/mcp", "POST", TOKEN_A, payload)
        tools = json.loads(raw)["result"]["tools"]
        assert status == 200 and len(tools) == 8
        payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "t01_phase1_real_service_v01.tool.workflow.get", "arguments": {"job_id": job_id}
        }}
        status, _, raw = request(base + "/mcp", "POST", TOKEN_A, payload)
        result = json.loads(raw)["result"]
        assert status == 200 and not result["isError"] and result["structuredContent"]["state"] == "succeeded"
    finally:
        server.shutdown()
        server.server_close()
        service.shutdown()
        thread.join(5)


def test_real_dify_is_generated_bound_and_isolated_from_mock():
    template = yaml.safe_load(template_bytes())
    bound = yaml.safe_load(bound_bytes())
    assert template["app"]["name"] == bound["app"]["name"] == APP_NAME
    assert template["version"] == bound["version"] == "0.7.0"
    assert len(template["workflow"]["graph"]["nodes"]) == 9
    assert len(template["workflow"]["graph"]["edges"]) == 9
    tools = [row["data"] for row in template["workflow"]["graph"]["nodes"] if row["data"]["type"] == "tool"]
    bound_tools = [row["data"] for row in bound["workflow"]["graph"]["nodes"] if row["data"]["type"] == "tool"]
    assert {row["provider_id"] for row in tools} == {PROVIDER_TOKEN}
    assert {row["provider_id"] for row in bound_tools} == {PROVIDER_ID}
    assert all("mock" not in row["tool_name"].lower() for row in bound_tools)
    assert {row["tool_name"].rsplit(".", 1)[-1] for row in bound_tools} == {"submit", "wait", "report"}
    normalized_template = semantic_graph(template)
    normalized_bound = semantic_graph(bound)
    for row in normalized_template["nodes"]:
        if row.get("type") == "tool":
            row["provider_id"] = PROVIDER_ID
            row["provider_name"] = PROVIDER_ID
    assert normalized_template == normalized_bound
