"""Nested lifecycle contract fixtures; no scientific/cluster qualification."""
from contextlib import contextmanager
import copy
from pathlib import Path
import pytest
from t01_phase1_real.common import encode,sha
from t01_phase1_real.deployment import a3d
from t01_phase1_real.deployment.kubernetes import scientific_network_policy,SCIENTIFIC_SOURCE_IMAGE_IDS

IMAGE='registry.local/a3d@sha256:'+'a'*64
CONTROL='registry.local/control@sha256:'+'b'*64


class Runtime:
    def __init__(self,root):self.root=root;self.ex={};self.job={'job_id':'job','attempt_id':'attempt-123','execution_identity':'identity','stop_reason':None}
    def attempt_path(self,job):return 'attempt'
    def get(self,job_id):return dict(self.job)
    def execution(self,job_id):return copy.deepcopy(self.ex)
    @contextmanager
    def _tx(self):yield None
    def _execution(self,db,job_id):return copy.deepcopy(self.ex)
    def _execution_store(self,db,job_id,ex):self.ex=copy.deepcopy(ex)


class API:
    def __init__(self):self.job=None;self.deleted=False;self.posts=0;self.stopped=False;self.fail_post=False
    def __call__(self,method,path,body=None):
        if 'networkpolicies' in path:
            p=scientific_network_policy('test');p['metadata']['uid']='policy';return 200,p
        if '/pods?' in path:
            if self.deleted:return 200,{'items':[]}
            pod={'metadata':{'ownerReferences':[{'uid':'owned','kind':'Job'}]},'spec':copy.deepcopy(self.job['spec']['template']['spec']),
                 'status':{'phase':'Succeeded' if self.stopped else 'Running'}}
            pod['spec']['nodeName']='node'
            for field,name,image in [('containerStatuses','worker',IMAGE),('initContainerStatuses','stage-launcher',CONTROL)]:
                pod['status'][field]=[dict(name=name,restartCount=0,imageID=image,state={'terminated':{'exitCode':0}})]
            return 200,{'items':[pod]}
        if method=='POST':
            self.posts+=1;self.job=copy.deepcopy(body);self.job['metadata']['uid']='owned'
            if self.fail_post:raise a3d.ClusterError('KUBERNETES_UNAVAILABLE','lost response')
            return 201,self.job
        if method=='DELETE':self.deleted=True;self.job=None;return 200,{}
        if self.job and self.stopped:self.job['status']={'conditions':[{'type':'Complete','status':'True'}]}
        return (200,self.job) if self.job else (404,{})


@pytest.fixture
def target(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);api=API()
    output=tmp_path/'attempt/output/a3d-native';output.mkdir(parents=True)
    (output/'execution.json').write_bytes(encode(dict(exit_code=0,input_sha256='input',python='2.7.15')))
    for name in ('stdout.txt','stderr.txt'):(output/name).write_bytes(b'fixture')
    config=dict(server='https://cluster',token_file='/token',ca_file='/ca',namespace='test',runtime_claim='runtime',
        runtime_volume_root=str(tmp_path),control_image=CONTROL,tools={'aggrescan3d':dict(image=IMAGE,asset_claim='assets',gpu_resource_key=None)})
    monkeypatch.setattr(a3d,'configuration',lambda:(config,'config'))
    monkeypatch.setattr(a3d,'API',lambda *args:api)
    monkeypatch.setattr(a3d,'qualification',lambda cfg:dict(network_policy_uid='policy',node_names=['node'],
        tools={'aggrescan3d':dict(image=IMAGE,source_image_id=SCIENTIFIC_SOURCE_IMAGE_IDS['aggrescan3d'])}))
    return rt,api


def test_a3d_completed_job_collects_output_with_durable_receipt(target):
    rt,api=target;api.stopped=True;execution={'command':{'input_sha256':'input'}}
    completed=a3d.run(rt,rt.job,{'timeout_seconds':30},execution)
    assert completed.returncode==0 and api.posts==1 and rt.ex['a3d_stop_confirmed']
    assert execution['command']['runtime']=='kubernetes' and execution['target_profile']=='kubernetes-a3d-0.1.0'


def test_lost_submit_response_stays_pending_and_recovery_never_posts_again(target):
    rt,api=target;api.fail_post=True
    with pytest.raises(a3d.Pending):a3d.run(rt,rt.job,{'timeout_seconds':30},{'command':{'input_sha256':'input'}})
    assert not rt.ex.get('a3d_stop_confirmed') and rt.ex['dispatcher'] is None
    assert a3d.cleanup_interrupted(rt,rt.job,rt.ex)
    assert api.posts==1 and api.deleted and rt.ex['a3d_stop_confirmed']


def test_recovery_cannot_delete_foreign_job(target):
    rt,api=target;api.fail_post=True
    with pytest.raises(a3d.Pending):a3d.run(rt,rt.job,{'timeout_seconds':30},{'command':{'input_sha256':'input'}})
    api.job['metadata']['annotations']['t01.openai/owner']='foreign'
    assert not a3d.cleanup_interrupted(rt,rt.job,rt.ex)
    assert not api.deleted and api.posts==1
