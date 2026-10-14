import importlib.util
import json
import socket
import threading
import time
from pathlib import Path

import pytest
from scripts import build_target_linux_candidate as build
from t01_phase1_real.deployment.kubernetes import control_plane_documents,scientific_job_spec
from t01_phase1_real.service_api import Credentials,Service,ServiceConfig,ServiceError,Phase1RealServiceServer
from t01_phase1_real.service_api.transport import RequestHandler

IMAGE='registry.local/t01/control@sha256:'+'a'*64

@pytest.mark.parametrize('target_name',['project','existing','parent'])
def test_stage_never_removes_existing_directory(tmp_path,monkeypatch,target_name):
    repo=tmp_path/'project';repo.mkdir();(repo/'valuable').write_bytes(b'keep')
    monkeypatch.setattr(build,'REPO',repo)
    target={'project':repo,'parent':tmp_path,'existing':repo/'existing'}[target_name]
    target.mkdir(exist_ok=True)
    with pytest.raises(ValueError):build.stage(repo/'deploy',target)
    assert (repo/'valuable').read_bytes()==b'keep'

def test_render_validates_before_writing_and_never_overwrites(tmp_path):
    (tmp_path/'kubernetes').mkdir();old=tmp_path/'kubernetes/old.yaml';old.write_bytes(b'keep')
    for image in ('invalid',IMAGE):
        with pytest.raises(ValueError):build.render(tmp_path,image)
        assert old.read_bytes()==b'keep'

def test_package_cannot_overwrite_or_package_itself(tmp_path):
    (tmp_path/'data').write_bytes(b'keep')
    with pytest.raises(ValueError):build.package(tmp_path,tmp_path/'result.zip')
    with pytest.raises(ValueError):build.package(tmp_path,tmp_path/'data')

def test_scientific_network_deadline_cpu_and_storage():
    docs=control_plane_documents(IMAGE)
    policy=next(d for d in docs if d['kind']=='NetworkPolicy')['spec']
    assert policy['egress']==policy['ingress']==[] and set(policy['policyTypes'])=={'Egress','Ingress'}
    job=scientific_job_spec('bepipred','attempt1',scientific_image=IMAGE,control_image=IMAGE,asset_claim='assets',timeout_seconds=37)
    assert job['spec']['activeDeadlineSeconds']==37
    pod=job['spec']['template']['spec'];worker=pod['containers'][0]
    assert worker['resources']['limits']=={'cpu':'8','memory':'10Gi'}
    assert {'name':'TORCH_HOME','value':'/torch'} in worker['env']
    assert any(m['mountPath']=='/app' and m['readOnly'] for m in worker['volumeMounts'])
    assert pod['affinity']['podAffinity']['requiredDuringSchedulingIgnoredDuringExecution'][0]['topologyKey']=='kubernetes.io/hostname'
    for value in (0,True,7201,'60'):
        with pytest.raises(ValueError):scientific_job_spec('bepipred','attempt1',scientific_image=IMAGE,control_image=IMAGE,asset_claim='assets',timeout_seconds=value)

def credentials():
    return Credentials.from_document({'credentials':[{'token':'x'*48,'principal':'upload-only','scopes':['upload']}]})

def test_mcp_authentication_does_not_require_query(tmp_path):
    creds=credentials();owner=creds.authenticate('Bearer '+'x'*48)
    assert owner.scopes==frozenset({'upload'})
    with pytest.raises(ServiceError):creds.authenticate('Bearer '+'x'*48,'query')
    handler=object.__new__(RequestHandler);handler.headers={'Authorization':'Bearer '+'x'*48}
    service=Service(ServiceConfig(tmp_path/'runtime'),creds)
    handler.server=type('Server',(),{'service':service})()
    try:assert handler._principal('query',any_scope=True)==owner
    finally:service.shutdown()

@pytest.mark.parametrize('media',[[],{},42,True,None])
def test_malformed_upload_is_structured(tmp_path,media):
    creds=credentials();service=Service(ServiceConfig(tmp_path/'runtime'),creds)
    try:
        with pytest.raises(ServiceError) as exc:service.upload(creds.authenticate('Bearer '+'x'*48),{'name':'x.pdb','media_type':media,'content_base64':'YQ=='})
        assert exc.value.status==422 and exc.value.code=='INVALID_REQUEST'
    finally:service.shutdown()

def test_thread_cap_rejects_before_spawning(tmp_path,monkeypatch):
    service=Service(ServiceConfig(tmp_path/'runtime'),credentials())
    server=Phase1RealServiceServer(('127.0.0.1',0),service)
    closed=[]
    monkeypatch.setattr(server,'shutdown_request',lambda request:closed.append(request))
    try:
        for _ in range(32):assert server._connections.acquire(False)
        server.process_request('connection',('127.0.0.1',1));assert closed==['connection']
    finally:
        for _ in range(32):server._connections.release()
        server.server_close();service.shutdown()

def test_socket_timeout_is_set_before_handler(tmp_path):
    service=Service(ServiceConfig(tmp_path/'runtime'),credentials())
    server=Phase1RealServiceServer(('127.0.0.1',0),service)
    client=socket.create_connection(server.server_address)
    try:
        connection,_=server.get_request();assert connection.gettimeout()==10;connection.close()
    finally:client.close();server.server_close();service.shutdown()

def test_task_queue_capacity_is_bounded(tmp_path):
    service=Service(ServiceConfig(tmp_path/'runtime',max_workers=1,max_pending_tasks=1),credentials())
    try:
        service._scheduled.add(('occupied','job'))
        with pytest.raises(ServiceError) as exc:service.submit(credentials().authenticate('Bearer '+'x'*48),{})
        assert exc.value.status==503
        with pytest.raises(ServiceError):service.schedule(credentials().authenticate('Bearer '+'x'*48),'second')
        assert len(service._scheduled)==1
    finally:service.shutdown()

def test_http_mcp_upload_only_and_malformed_rest(tmp_path):
    import urllib.request
    import urllib.error
    service=Service(ServiceConfig(tmp_path/'runtime'),credentials())
    server=Phase1RealServiceServer(('127.0.0.1',0),service)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def call(path,body):
        req=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+path,
            data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+'x'*48,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=5) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as response:return response.code,json.load(response)
    try:
        status,value=call('/v1/uploads',{'name':'x.pdb','media_type':[],'content_base64':'YQ=='})
        assert status==422 and value['error']['code']=='INVALID_REQUEST'
        status,value=call('/mcp',{'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
            'name':'t01_phase1_real_service_v01.tool.structure.upload','arguments':{'name':'x.pdb','media_type':'chemical/x-pdb','content_base64':'YQ=='}}})
        assert status==200 and not value['result'].get('isError')
    finally:server.shutdown();server.server_close();thread.join();service.shutdown()
