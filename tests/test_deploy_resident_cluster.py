import copy
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('deploy_resident_cluster', Path(__file__).resolve().parents[1]/'scripts/deploy_resident_cluster.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


def baseline():
    return {'replicas':1,'strategy':{'type':'Recreate'},'selector':{'matchLabels':{'app':'antigen-design'}},
            'template':{'metadata':{'labels':{'app':'antigen-design'}},'spec':{
                'securityContext':{'fsGroup':10001},
                'volumes':[{'name':'runtime','persistentVolumeClaim':{'claimName':'antigen-design-runtime'}},
                           {'name':'credentials','secret':{'secretName':'existing-credentials'}}],
                'containers':[{'name':'service','image':'control:latest','args':['--port','18083'],
                               'env':[{'name':'T01_REAL_SERVICE_CREDENTIALS_FILE','value':'/run/secrets/t01/credentials.json'}],
                               'volumeMounts':[{'name':'runtime','mountPath':'/var/lib/t01'},
                                               {'name':'credentials','mountPath':'/run/secrets/t01','readOnly':True}]}]}}}


def test_shared_paths_secret_isolation_and_single_gpu_allocation():
    before = baseline()
    original = copy.deepcopy(before)
    images = {g:'registry/'+g+'@sha256:'+'a'*64 for g in deploy.assembly.GROUPS}
    target = deploy.make_target(before, images, 'control@sha256:'+'b'*64)
    assert before == original
    pod = target['template']['spec']
    assert len(pod['containers']) == 10
    assert pod['containers'][0]['args'] == original['template']['spec']['containers'][0]['args']
    assert pod['containers'][0]['env'][0] == original['template']['spec']['containers'][0]['env'][0]
    paths = pod['containers'][0]['volumeMounts']
    assert any(m['mountPath']=='/etc/t01/resident.json' and m['subPath']=='resident.json' for m in paths)
    gpu = [c for c in pod['containers'] if 'nvidia.com/gpu' in c.get('resources',{}).get('limits',{})]
    assert [c['name'] for c in gpu] == ['worker-gpu']
    for worker in pod['containers'][1:]:
        mounts = {m['mountPath']:m for m in worker['volumeMounts']}
        assert mounts['/var/lib/t01']['name']=='runtime'
        assert mounts['/t01/assets']['readOnly']
        assert all(m['name']!='credentials' for m in worker['volumeMounts'])
        assert mounts['/run/t01-slot']['name']=='slot-'+worker['name'].removeprefix('worker-')
    blast=next(c for c in pod['containers'] if c['name']=='worker-blast')
    assert blast['resources']['limits']=={'cpu':'4','memory':'16Gi'}


def test_unverified_image_or_existing_worker_is_rejected():
    with pytest.raises(ValueError, match='unverified'):
        deploy.image_map([{'group':'gpu','status':'UPLOADING'}])
    with pytest.raises(ValueError, match='nine'):
        deploy.image_map([])
    before=baseline()
    before['template']['spec']['containers'].append({'name':'unrelated-sidecar'})
    with pytest.raises(ValueError, match='existing containers'):
        deploy.make_target(before, {}, 'image')


def test_apply_rejects_deployment_drift_before_any_mutation(tmp_path, monkeypatch):
    before=baseline()
    plan={'uid':'stable-uid','before_spec':before,'target_spec':{'changed':True},'rollback_spec':before}
    (tmp_path/'plan.json').write_text(json.dumps(plan))
    live={'metadata':{'uid':'stable-uid'},'spec':copy.deepcopy(before)}
    live['spec']['template']['spec']['containers'][0]['image']='colleague-new-release'
    monkeypatch.setattr(deploy,'OUT',tmp_path)
    monkeypatch.setattr(deploy,'get',lambda *args:live)
    def no_write(*args,**kwargs):
        pytest.fail('No mutation may occur after a drift detection')
    monkeypatch.setattr(deploy,'kubectl',no_write)
    with pytest.raises(ValueError,match='changed since preparation'):
        deploy.apply_plan()


def test_patch_has_atomic_identity_and_version_preconditions():
    request=deploy.patch_for({'metadata':{'uid':'u1','resourceVersion':'v2'}}, {'replicas':1})
    assert request[:2]==[{'op':'test','path':'/metadata/uid','value':'u1'},
                         {'op':'test','path':'/metadata/resourceVersion','value':'v2'}]
    assert request[2]['op']=='replace'
