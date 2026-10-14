import json
import pytest
from t01_phase1_real.common import encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.bepipred import policy
from t01_phase1_real.deployment import execution
from t01_phase1_real.deployment.kubernetes import scientific_network_policy

class FakeAPI:
    def __init__(self):self.job=None;self.posts=0;self.deleted=False
    def __call__(self,method,path,body=None):
        if 'networkpolicies' in path:return 200,scientific_network_policy()
        if '/pods?' in path:
            return 200,{'items':[] if self.deleted else [{'metadata':{'ownerReferences':[{'uid':'owned','kind':'Job'}]},'status':{'phase':'Succeeded' if self.job.get('status',{}).get('succeeded') else 'Running'}}]}
        if method=='GET':return (200,self.job) if self.job else (404,{})
        if method=='POST':self.job=body;self.job['metadata']['uid']='owned';self.posts+=1;return 201,self.job
        if method=='DELETE':self.job=None;self.deleted=True;return 200,{}

@pytest.fixture
def setup(tmp_path,monkeypatch):
    rt=Runtime(tmp_path/'runtime');api=FakeAPI();image='r/control@sha256:'+'a'*64
    config=tmp_path/'config.json'
    config.write_text(json.dumps(dict(server='https://cluster.local',token_file='/token',ca_file='/ca',namespace='t01-phase1-real',runtime_claim='runtime',runtime_volume_root=str(tmp_path),control_image=image,tools={'bepipred':dict(image=image,asset_claim='assets',gpu_resource_key=None)})))
    monkeypatch.setenv('T01_KUBERNETES_CONFIG_FILE',str(config))
    monkeypatch.setattr(execution,'enabled',lambda:True)
    monkeypatch.setattr(execution,'API',lambda *args:api)
    monkeypatch.setattr(policy,'verify_assets',lambda:None)
    req=encode(dict(protein_sequence='ACDEFGHIKLMNPQRSTVWY',user_sequence_id='k8-contract-only',timeout_seconds=30))
    return rt,api,rt.submit_sequence(req,'k8-test',policy.TOOL)

def test_runtime_routes_to_job_and_reuses_identity(setup):
    rt,api,j=setup
    assert rt.dispatch(j['job_id'])['state']=='running'
    ex=rt.execution(j['job_id']);assert ex['backend']=='kubernetes' and ex['kubernetes_receipt']['uid']=='owned'
    assert rt.recover(j['job_id'])['state']=='reconciling'
    assert api.posts==1
    api.job['status']={'succeeded':1,'conditions':[{'type':'Complete','status':'True'}]}
    end=rt.reconcile(j['job_id'])
    assert end['state']=='failed' and end['error_code']=='PROFILE_NOT_APPROVED'
    result=rt.result(j['job_id'])
    assert result['raw_scores'] is None and not result['usable_for_pipeline']
    assert any(r['path']=='kubernetes-observation.json' for r in result['raw_artifacts'])

def test_runtime_cancellation_waits_for_pod_deletion(setup):
    rt,api,j=setup;rt.dispatch(j['job_id'])
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='cancel')))
    end=rt.reconcile(j['job_id'])
    assert end['state']=='cancelled' and end['stop_confirmed']
    assert api.deleted and api.posts==1
