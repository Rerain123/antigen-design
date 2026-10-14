import copy
import pytest
from t01_phase1_real.deployment.launcher import Launcher,ClusterError
from t01_phase1_real.deployment.kubernetes import scientific_job_spec,scientific_network_policy

IMAGE='registry.local/t01/control@sha256:'+'a'*64

class API:
    def __init__(self):self.job=None;self.created=0;self.deleted=[];self.pods=[];self.policy=scientific_network_policy()
    def __call__(self,method,path,body=None):
        if 'networkpolicies' in path:return 200,self.policy
        if '/pods?' in path:return 200,dict(items=self.pods)
        if method=='GET':return (200,copy.deepcopy(self.job)) if self.job else (404,{})
        if method=='POST':
            self.job=copy.deepcopy(body);self.job['metadata']['uid']='uid-1';self.created+=1;return 201,copy.deepcopy(self.job)
        if method=='DELETE':self.deleted.append(body);return 202,{}

def spec():return scientific_job_spec('bepipred','attempt1',scientific_image=IMAGE,control_image=IMAGE,asset_claim='assets')

def test_submit_recover_idempotence_and_uid_cancel():
    api=API();launcher=Launcher(api,'t01-phase1-real')
    binding=dict(job_id='job',attempt_id='attempt',input_sha256='input')
    receipt=launcher.submit(spec(),binding)
    assert launcher.submit(spec(),binding,receipt)==receipt and api.created==1
    assert Launcher(api,'t01-phase1-real').submit(spec(),binding,receipt)==receipt
    assert launcher.cancel(receipt)['stopped_confirmed'] is False
    assert api.deleted[0]['preconditions']=={'uid':'uid-1'}
    api.job['metadata']['uid']='replacement'
    with pytest.raises(ClusterError):launcher.cancel(receipt)
    assert len(api.deleted)==1

def test_foreign_name_and_lost_receipt_never_recreated():
    api=API();launcher=Launcher(api,'t01-phase1-real');receipt=launcher.submit(spec(),{'owner':'one'})
    with pytest.raises(ClusterError):launcher.submit(spec(),{'owner':'two'})
    api.job=None
    with pytest.raises(ClusterError) as error:launcher.submit(spec(),{'owner':'one'},receipt)
    assert error.value.code=='EXECUTION_LOST' and api.created==1

def test_deadline_failure_requires_pod_stop_confirmation():
    api=API();launcher=Launcher(api,'t01-phase1-real');receipt=launcher.submit(spec(),{})
    api.job['status']={'conditions':[{'type':'Failed','status':'True','reason':'DeadlineExceeded'}]}
    pod=dict(metadata=dict(ownerReferences=[dict(uid='uid-1',kind='Job')]),status=dict(phase='Running'))
    api.pods=[pod]
    value=launcher.observe(receipt)
    assert value['reason_code']=='DeadlineExceeded' and not value['stopped_confirmed']
    pod['status']['phase']='Failed';assert launcher.observe(receipt)['stopped_confirmed']
    pod['metadata']['ownerReferences'][0]['uid']='foreign'
    with pytest.raises(ClusterError):launcher.observe(receipt)

def test_network_policy_drift_blocks_creation():
    api=API();api.policy['spec']['egress']=[{}]
    with pytest.raises(ClusterError) as error:Launcher(api,'t01-phase1-real').submit(spec(),{})
    assert error.value.code=='NETWORK_ISOLATION_UNVERIFIED' and api.created==0

def test_exited_pod_without_terminal_job_does_not_confirm_stop():
    api=API();launcher=Launcher(api,'t01-phase1-real');receipt=launcher.submit(spec(),{})
    api.job['status']={'failed':1}
    api.pods=[dict(metadata=dict(ownerReferences=[dict(uid='uid-1',kind='Job')]),status=dict(phase='Failed'))]
    assert not launcher.observe(receipt)['stopped_confirmed']
    api.job['status']['conditions']=[dict(type='Failed',status='True')]
    assert launcher.observe(receipt)['stopped_confirmed']

def test_deleted_job_is_not_stop_confirmation_until_pods_exit():
    api=API();launcher=Launcher(api,'t01-phase1-real');receipt=launcher.submit(spec(),{})
    api.job=None
    api.pods=[dict(metadata=dict(ownerReferences=[dict(uid='uid-1',kind='Job')]),status=dict(phase='Running'))]
    assert not launcher.observe_stop(receipt)['stopped_confirmed']
    api.pods=[];assert launcher.observe_stop(receipt)['stopped_confirmed']
    assert not launcher.observe(receipt)['stopped_confirmed']
