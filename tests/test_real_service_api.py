import base64
import io
import json
import os
import re
import threading
import urllib.error
import urllib.request
from urllib.parse import urlsplit
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
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.transport import HIMAT_MCP_AUTH_HEADER, MCPApplication


TOKEN_A = "a" * 48
TOKEN_B = "b" * 48


def test_service_cli_maps_queue_capacity_and_delay_by_name(tmp_path,monkeypatch):
    from t01_phase1_real.service_api import transport
    captured=[]
    monkeypatch.setattr(transport,'serve',lambda host,port,config,creds:captured.append(config))
    monkeypatch.setattr(transport.Credentials,'from_environment',lambda:credentials())
    assert transport.main(['--runtime-root',str(tmp_path/'cli'),'--max-workers','3',
        '--max-pending-tasks','70','--dispatch-start-delay-seconds','2'])==0
    assert captured[0].max_workers==3 and captured[0].max_pending_tasks==70
    assert captured[0].dispatch_start_delay_seconds==2
    assert transport.main(['--runtime-root',str(tmp_path/'default')])==0
    assert captured[1].max_pending_tasks==64 and captured[1].dispatch_start_delay_seconds==0


def credentials():
    return Credentials.from_document({"credentials": [
        {"token": TOKEN_A, "principal": "tenant-a", "scopes": ["submit", "query", "control", "download", "upload"]},
        {"token": TOKEN_B, "principal": "tenant-b", "scopes": ["submit", "query", "control", "download", "upload"]},
    ]})


def test_rustfs_report_publication_is_owner_authorized_and_retryable(tmp_path, monkeypatch):
    from t01_phase1_real.service_api.object_storage import StorageError
    monkeypatch.delenv('RUSTFS_ENABLED',raising=False)
    creds=credentials()
    service=Service(ServiceConfig(runtime_root=tmp_path/'rustfs'),creds)
    owner=principal(creds)
    other=principal(creds,TOKEN_B)
    calls=[]
    class Publisher:
        fail=False
        def publish_report(self,scope,job_id,raw,markdown,**kwargs):
            calls.append((scope,job_id,sha(raw)))
            assert kwargs['created_at']==service.runtime(owner).get(job_id)['created_at']
            if self.fail:raise StorageError('private upstream error')
            return [{'fileName':'report.zip','fileUrl':'https://storage.example.test/antigen-design/data/test/report.zip',
                     'sizeBytes':len(raw),'sha256':sha(raw),'mediaType':'application/zip'}]
    publisher=Publisher()
    service.report_publisher=publisher
    try:
        job=service.submit(owner,{'request':body(),'idempotency_key':'rustfs-case'})
        wait(service,owner,job['job_id'])
        with pytest.raises(ServiceError):service.report_for_json(other,job['job_id'])
        assert calls==[]
        publisher.fail=True
        with pytest.raises(ServiceError) as error:service.report_for_json(owner,job['job_id'])
        assert error.value.code=='REPORT_PUBLICATION_FAILED'
        assert 'private upstream' not in str(error.value)
        publisher.fail=False
        result=service.report_for_json(owner,job['job_id'])
        assert result['publication_status']=='verified' and result['attachments']
        assert 'content_base64' not in result
        assert calls[-1][0]==owner.runtime_scope
        service.report_publisher=None
        legacy=service.report_for_json(owner,job['job_id'])
        assert base64.b64decode(legacy['content_base64'])==service.report(owner,job['job_id'])['content']
    finally:
        service.shutdown()


def test_himat_card_publishes_four_files_and_keeps_signed_downloads(tmp_path, monkeypatch):
    from t01_phase1_real.service_api.object_storage import RustFSPublisher, report_filenames
    monkeypatch.delenv('RUSTFS_ENABLED',raising=False)
    creds=Credentials.from_document({'credentials':[dict(token=TOKEN_A,principal='himat-t01-test',
        scopes=['submit','query','download'])]})
    service=Service(ServiceConfig(tmp_path/'himat-storage'),creds)
    owner=principal(creds)
    publisher=RustFSPublisher(endpoint='https://storage.example.test',bucket='antigen-design',
        access_key='test-access',secret_key='test-secret')
    objects={};puts=[];fail={'enabled':False}
    def storage_request(method,key,body=b'',extra=None,**kwargs):
        if fail['enabled']:return 503,{},b''
        if method=='HEAD':
            return (200,{'content-length':str(len(objects[key])),'x-amz-meta-sha256':sha(objects[key])},b'') if key in objects else (404,{},b'')
        if method=='PUT':
            assert extra['if-none-match']=='*'
            objects[key]=body;puts.append(key);return 200,{},b''
        if method=='GET':return 200,{},objects[key]
        raise AssertionError(method)
    monkeypatch.setattr(publisher,'_request',storage_request)
    service.report_publisher=publisher
    try:
        submitted=service.submit(owner,{'request':body(),'idempotency_key':'himat-storage'})
        jid=submitted['job_id'];wait(service,owner,jid)
        original_report=service.report
        def with_native(principal,job_id):
            value=original_report(principal,job_id)
            value['native_results']={}
            return value
        monkeypatch.setattr(service,'report',with_native)
        native=b'bounded-native-export';html=b'<html>engineering attachment</html>'
        monkeypatch.setattr(HiMatIntegration,'report_html',staticmethod(lambda _:html))
        monkeypatch.setattr(service,'native_report',lambda *a,**kw:dict(content=native,sha256=sha(native),
            filename=report_filenames(kw['verified_report']['report_name'])['native'],media_type='application/zip'))
        adapter=HiMatIntegration(service,'https://himat.example.test',b'k'*32)
        fail['enabled']=True
        with pytest.raises(ServiceError) as error:adapter.check(owner,jid)
        assert error.value.code=='REPORT_PUBLICATION_FAILED' and puts==[]
        fail['enabled']=False
        card=adapter.check(owner,jid)['data']
        assert card['publicationStatus']=='verified' and len(card['storageAttachments'])==4
        assert len(objects)==4 and len(puts)==4
        assert {a['fileName'] for a in card['attachments']}==set(report_filenames(card['reportName']).values())
        for attachment in card['attachments']:
            url=urlsplit(attachment['fileUrl'])
            raw,name,_,digest=adapter.download(url.path,url.query)
            stored=next(a for a in card['storageAttachments'] if a['fileName']==name)
            assert raw==objects[stored['storageKey']] and digest==stored['sha256']
            with pytest.raises(ServiceError):adapter.download(url.path,url.query.replace('himat-t01-test','other'))
            with pytest.raises(ServiceError):adapter.download(url.path,url.query,now=10**12)
        assert adapter.check(owner,jid)['data']['reportName']==card['reportName'] and len(puts)==4
        import jsonschema
        output=service.report_for_json(owner,jid)
        schema=next(t['outputSchema'] for t in MCPApplication.tools() if t['name'].endswith('.workflow.report'))
        jsonschema.validate(output,schema)
        assert len(output['attachments'])==4 and len(puts)==4
    finally:
        service.shutdown()


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


def test_credentials_support_exact_secret_file_injection(tmp_path, monkeypatch):
    secret = tmp_path / "credentials.json"
    secret.write_text(json.dumps({"credentials": [
        {"token": TOKEN_A, "principal": "tenant-a", "scopes": ["query"]}
    ]}), encoding="utf-8")
    monkeypatch.delenv("T01_REAL_SERVICE_CREDENTIALS_JSON", raising=False)
    monkeypatch.setenv("T01_REAL_SERVICE_CREDENTIALS_FILE", str(secret.resolve()))
    assert Credentials.from_environment().authenticate("Bearer " + TOKEN_A, "query").principal_id == "tenant-a"
    monkeypatch.setenv("T01_REAL_SERVICE_CREDENTIALS_JSON", "{}")
    with pytest.raises(ServiceError) as error:
        Credentials.from_environment()
    assert error.value.code == "CONFIGURATION_INVALID"


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


def request(url, method="GET", token=None, value=None, extra_headers=None):
    headers = {}
    data = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if extra_headers:
        headers.update(extra_headers)
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


def test_himat_sequence_submission_uses_new_sequence_without_sample_structure_or_masks(tmp_path, monkeypatch):
    creds = Credentials.from_document({"credentials": [{
        "token": "h" * 48, "principal": "himat-t01-test", "scopes": ["submit", "query", "download"],
    }]})
    service = Service(ServiceConfig(tmp_path / "runtime"), creds)
    adapter = HiMatIntegration(service, "https://himat.ws.scqcyz.cn", b"k" * 32)
    owner = creds.authenticate("Bearer " + "h" * 48)
    captured = []
    monkeypatch.setattr(service, "upload", lambda *args: pytest.fail("No 1UBQ structure may be uploaded"))
    monkeypatch.setattr(service, "submit", lambda principal, body: captured.append(body) or {"job_id": "t01p1r-job-" + "1" * 32, "state": "queued"})
    sequence = "MRHRPIFRRRPRPRRRRRHRRRYVRRKLFIRRPTAGTYYTKKYSTMNVISVGTPQNNKPWHANHFITRLNEWETAISFEYYKILKMKVTLSPVISPAQQTKTMFGHTAIDLDGAWTTNTWLQDDPYAESSTRKVMTSKKKHSRYFTPKPILAGTTSAHPGQSLFFFSRPTPWLNTYDPTVQWGALLWSIYVPEKTGMTDFYGTKEVWIRYKSVL"
    assert len(sequence) == 214
    try:
        first = adapter.submit_sequence(owner, sequence, "Homo sapiens")
        second = adapter.submit_sequence(owner, sequence, "Homo sapiens")
        assert first["job_id"] == second["job_id"]
        assert captured[0]["idempotency_key"] == captured[1]["idempotency_key"]
        req = captured[0]["request"]
        assert req["protein_sequence"] == sequence and req["host_species"] == "Homo sapiens"
        assert req["structure"] is None and req["prediction"]["engine"] == "af3"
        assert "m1_test" not in req and req["reuse_jobs"] == {}
        assert req["analysis"]["blast"]["database_id"] == "iedb-20261013-6l62-r01"
        assert req["analysis"]["blast"]["thresholds"] == dict(identity_percent_min=70,query_coverage_percent_min=80)
        assert req["analysis"]["blast"]["database_manifest_sha256"] == "000695140d8fedf1cc897faba5356bf184928235a3417486448b3ec09c72992b"
        assert first["input_profile"] == "HIMAT_SEQUENCE_EXPERT_V2"
        assert first['rule_version'] == 'expert-revision-20260929-v2'
        assert req['revision_config']['parameter_status'] == 'SUGGESTED_UNCALIBRATED'
        assert req['revision_config']['structure_eval_max'] == 24
        assert req['revision_config']['foldx_number_of_runs'] == 5
        from t01_phase1_real.development.netmhc.host_panel import options
        assert req["analysis"]["netmhc"] == options(req['host_species'])
        from t01_phase1_real.common import encode
        from t01_phase1_real.development.workflow import policy as workflow_policy
        assert workflow_policy.request(encode(req))["prediction"]["engine"] == "af3"
        adapter.submit_sequence(owner, "A" * 999, "Homo sapiens")
        assert workflow_policy.request(encode(captured[-1]["request"]))["protein_sequence"] == "A" * 999
        for seq, host in (("A" * 1000, "Homo sapiens"), (sequence, ""), ("A" * 8, "Homo sapiens")):
            with pytest.raises(ServiceError):
                adapter.submit_sequence(owner, seq, host)
        with pytest.raises(ServiceError):
            adapter.submit_sequence(owner, sequence, "Homo sapiens", "../wrong-target")
    finally:
        service.shutdown()


def test_himat_mcp_card_is_direct_and_download_capability_is_bounded(tmp_path, monkeypatch):
    token = "h" * 48
    creds = Credentials.from_document({"credentials": [{
        "token": token, "principal": "himat-t01-test", "scopes": ["submit", "query", "download"],
    }]})
    secret = tmp_path / "key"
    secret.write_bytes(b"k" * 32)
    monkeypatch.setenv("T01_HIMAT_DOWNLOAD_KEY_FILE", str(secret))
    monkeypatch.setenv("T01_HIMAT_ATTACHMENT_BASE_URL", "https://himat.ws.scqcyz.cn")
    service = Service(ServiceConfig(tmp_path / "runtime"), creds)
    job_id = "t01p1r-job-" + "1" * 32
    markdown = "# 本地工程交付报告\n\n结果：ALL_EXCLUDED\n\n## 来源与缺项\n\n- N16: NO_QUALIFIED_CANDIDATE\n"
    nested_buffer = io.BytesIO()
    with zipfile.ZipFile(nested_buffer, "w") as nested:
        nested.writestr("report.md", markdown)
    outer_buffer = io.BytesIO()
    with zipfile.ZipFile(outer_buffer, "w") as outer:
        outer.writestr("local-delivery.zip", nested_buffer.getvalue())
    report_raw = outer_buffer.getvalue()
    snapshot = {"job_id": job_id, "run_id": "t01p1r-run-" + "2" * 32,
                "state": "succeeded", "terminal": True, "error_code": None,
                "scientific_gate": "CLOSED", "usable_for_pipeline": False,
                "production_status": "NOT_DEPLOYED", "nodes": {}}
    monkeypatch.setattr(service, "status", lambda principal, job, node=None: snapshot)
    monkeypatch.setattr(service, "report", lambda principal, job: {
        "job_id": job, "filename": job + ".zip", "content": report_raw,
        "report_name": '20261011-073807-11111111',
        "sha256": sha(report_raw), "report_markdown": "# workflow status only\n",
    })
    monkeypatch.setattr(service, "report_for_json", lambda *args: pytest.fail("HiMat called public RustFS publication"))
    server = Phase1RealServiceServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        himat_headers = {HIMAT_MCP_AUTH_HEADER: "Bearer " + token}
        status, _, raw = request(base + "/mcp", "POST", value=payload, extra_headers=himat_headers)
        names = {row["name"] for row in json.loads(raw)["result"]["tools"]}
        assert status == 200 and names == {MCPApplication.HIMAT_SUBMIT_TOOL, MCPApplication.HIMAT_CHECK_TOOL, MCPApplication.HIMAT_CONFIRM_TOOL}
        assert all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", "AntigenDesignT01-" + name) for name in names)
        assert request(base + "/mcp", "POST", value=payload,
                       extra_headers={HIMAT_MCP_AUTH_HEADER: "Bearer " + "x" * 48})[0] == 401
        assert request(base + "/v1/workflows", "POST", value={}, extra_headers=himat_headers)[0] == 401
        snapshot.update(state="running", terminal=False, nodes={
            "prediction": {"node_id": "N01", "state": "succeeded"},
            "blast": {"node_id": "N03", "state": "running"},
        })
        progress_call = {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {
            "name": MCPApplication.HIMAT_CHECK_TOOL, "arguments": {"job_id": job_id}}}
        progress = json.loads(request(base + "/mcp", "POST", value=progress_call,
            extra_headers={**himat_headers, "Authorization": "Bearer " + "x" * 48})[2])["result"]["structuredContent"]
        assert progress["state"] == "running" and progress["completed_nodes"] == 1
        assert progress["current_nodes"] == ["N03"] and progress["terminal"] is False
        assert progress["total_nodes"] == 18 and progress["progress_unit"] == "business_nodes"
        snapshot.update(state="succeeded", terminal=True, nodes={})
        payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "t01_phase1_real_service_v01.tool.workflow.report", "arguments": {"job_id": job_id},
        }}
        assert "error" in json.loads(request(base + "/mcp", "POST", token, payload)[2])
        payload["params"] = {"name": "t01_phase1_real_service_v01.tool.workflow.wait",
                             "arguments": {"job_id": job_id, "timeout_seconds": 20}}
        assert "error" in json.loads(request(base + "/mcp", "POST", token, payload)[2])
        payload["params"]["name"] = MCPApplication.HIMAT_CHECK_TOOL
        payload["params"]["arguments"] = {"job_id": job_id}
        status, _, raw = request(base + "/mcp", "POST", token, payload)
        card = json.loads(raw)["result"]
        assert status == 200 and set(card) == {"data", "type"}
        assert card["type"] == "primer_design_output"
        assert card["data"]["status"] == "COMPLETED"
        assert "ALL_EXCLUDED" in card["data"]["summaryText"]
        assert card["data"]["issues"] == ["N16: NO_QUALIFIED_CANDIDATE"]
        for attachment in card["data"]["attachments"]:
            target = urlsplit(attachment["fileUrl"])
            status, headers, downloaded = request(base + target.path + "?" + target.query)
            assert status == 200
            assert sha(downloaded) == headers["X-Content-SHA256"]
        zip_url = urlsplit(card["data"]["attachments"][1]["fileUrl"])
        assert request(base + zip_url.path + "?" + zip_url.query + "&other=1")[0] == 403
        assert request(base + zip_url.path + "?" + zip_url.query.replace("himat-t01-test", "tenant-b"))[0] == 403
        assert server.himat is not None
        with pytest.raises(ServiceError) as expired:
            server.himat.download(zip_url.path, zip_url.query, now=int(__import__("time").time()) + 3601)
        assert expired.value.status == 403
        assert request(base + "/v1/workflows", "POST", token, {"request": body(), "idempotency_key": "raw"})[0] == 403
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
