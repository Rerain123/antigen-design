"""API fixtures plus archived native bytes; these tests are not target qualification."""
import copy
import json
import pytest
from t01_phase1_real.common import REPO,decode,encode,sha
from t01_phase1_real.deployment.kubernetes import scientific_job_spec,SCIENTIFIC_SOURCE_IMAGE_IDS
from t01_phase1_real.deployment.launcher import digest
from t01_phase1_real.development.structure.result import result

IMAGE='registry.local/structure@sha256:'+'a'*64
CONTROL='registry.local/control@sha256:'+'b'*64


@pytest.fixture
def target(tmp_path,monkeypatch):
    folder=REPO/'discovery/t01-phase1-real/w1/structure-integration-20260906/acceptance-r02/cases/normal-cif'
    job=decode((folder/'job.json').read_bytes());old=decode((folder/'result.json').read_bytes())
    files={r['path']:(folder/'artifacts'/r['artifact']['artifact_id']).read_bytes() for r in old['raw_artifacts']}
    body=decode(files['input.json']);runtime=decode(files['output/runtime.json'])
    runtime.update(network_interfaces=[[1,'lo'],[2,'eth0']],cpu_affinity=[4,5,6,7])
    files['output/runtime.json']=encode(runtime)
    evidence=tmp_path/'fixture-evidence.json';evidence.write_bytes(b'{"evidence_kind":"CONTRACT_FIXTURE_ONLY"}')
    approved=dict(schema_version='0.1.0',server='https://cluster.local',namespace='test',control_image=CONTROL,
        network_policy_uid='policy-1',node_names=['fixture-node'],tools={'structure':dict(image=IMAGE,source_image_id=SCIENTIFIC_SOURCE_IMAGE_IDS['structure'])},
        approved_by='test-fixture',approved_at='test-fixture',evidence={name:dict(path=evidence.name,sha256=sha(evidence.read_bytes())) for name in
            ('cni_dns_denied','cni_tcp_denied','effective_network_policies','image_provenance','storage','cancel_recovery')})
    receipt_path=tmp_path/'qualification.json';receipt_path.write_bytes(encode(approved))
    config=dict(server='https://cluster.local',token_file='/token',ca_file='/ca',namespace='test',runtime_claim='runtime',
        runtime_volume_root=str(tmp_path),control_image=CONTROL,tools={'structure':dict(image=IMAGE,asset_claim='assets',gpu_resource_key=None)},
        qualification=dict(path=str(receipt_path),sha256=sha(receipt_path.read_bytes())))
    config_path=tmp_path/'launcher.json';config_path.write_bytes(encode(config));monkeypatch.setenv('T01_KUBERNETES_CONFIG_FILE',str(config_path))
    manifest=scientific_job_spec('structure','one',scientific_image=IMAGE,control_image=CONTROL,asset_claim='assets',namespace='test')
    owner=digest({k:job[k] for k in ('job_id','attempt_id','execution_identity','request_artifact','execution_profile')})
    receipt=dict(uid='job-uid',namespace='test',owner=owner,spec_sha256=digest(manifest),spec=copy.deepcopy(manifest['spec']),network_policy_uid='policy-1')
    manifest['metadata'].update(uid='job-uid');manifest['metadata']['annotations'].update({'t01.openai/owner':owner,'t01.openai/spec-sha256':receipt['spec_sha256']})
    manifest['status']={'conditions':[{'type':'Complete','status':'True'}]}
    state=lambda name,image:dict(name=name,restartCount=0,imageID='docker-pullable://'+image,state={'terminated':{'exitCode':0,'reason':'Completed'}})
    pod=dict(metadata={'ownerReferences':[{'kind':'Job','uid':'job-uid'}]},spec=copy.deepcopy(manifest['spec']['template']['spec']),
        status=dict(phase='Succeeded',containerStatuses=[state('worker',IMAGE)],initContainerStatuses=[state('stage-launcher',CONTROL)]))
    pod['spec']['nodeName']='fixture-node'
    observation=dict(job=manifest,pods=[pod],stopped_confirmed=True)
    execution=dict(backend='kubernetes',exit_code=0,error_code=None,stopped_confirmed=True,kubernetes_receipt=receipt,
        kubernetes_observation=observation,kubernetes_config_sha256=sha(config_path.read_bytes()))
    return job,body,files,execution,config_path,receipt_path,evidence


def test_target_profile_preserves_actual_network_and_cpu_without_docker_claims(target):
    job,body,files,execution,*_=target;original=files['output/runtime.json']
    value=result(job,body,files,execution)
    assert value['analysis']['freesasa']['status']=='executed'
    assert files['output/runtime.json']==original and 'image_id' not in execution
    assert not value['usable_for_pipeline'] and value['scientific_signoff'] is None


@pytest.mark.parametrize('damage',['qualification','evidence','config','owner','policy','node','image','init_image','exit','running','sidecar','raw_output'])
def test_target_result_rejects_unqualified_or_changed_execution(target,damage):
    job,body,files,execution,config_path,receipt_path,evidence=target
    pod=execution['kubernetes_observation']['pods'][0]
    if damage=='qualification':receipt_path.unlink()
    elif damage=='evidence':evidence.write_bytes(b'changed')
    elif damage=='config':config_path.write_bytes(config_path.read_bytes()+b' ')
    elif damage=='owner':execution['kubernetes_receipt']['owner']='foreign'
    elif damage=='policy':execution['kubernetes_receipt']['network_policy_uid']='changed'
    elif damage=='node':pod['spec']['nodeName']='unqualified'
    elif damage=='image':pod['status']['containerStatuses'][0]['imageID']='wrong'
    elif damage=='init_image':pod['status']['initContainerStatuses'][0]['imageID']='wrong'
    elif damage=='exit':pod['status']['containerStatuses'][0]['state']['terminated']['exitCode']=1
    elif damage=='running':pod['status']['phase']='Running'
    elif damage=='sidecar':pod['spec']['containers'].append(copy.deepcopy(pod['spec']['containers'][0]))
    elif damage=='raw_output':files['output/result/raw_areas.json']+=b' '
    value=result(job,body,files,execution)
    assert value['analysis'] is None and value['status']=='unreliable' and not value['usable_for_pipeline']


def test_docker_profile_still_rejects_target_network_observations(target):
    job,body,files,execution,*_=target
    execution.update(backend='docker',image_id=SCIENTIFIC_SOURCE_IMAGE_IDS['structure'])
    assert result(job,body,files,execution)['analysis'] is None
