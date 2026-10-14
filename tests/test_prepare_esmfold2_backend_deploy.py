import copy
import json
import pytest
from scripts.prepare_esmfold2_backend_deploy import render, LOCK


def inputs():
    deployment=dict(metadata=dict(resourceVersion='123'),spec=dict(replicas=1,strategy=dict(type='Recreate'),
        template=dict(spec=dict(containers=[dict(name='service',image='old-control',env=[dict(name='RUSTFS_SECRET',valueFrom={'secretKeyRef':{'name':'secret','key':'key'}})]),
            dict(name='worker-gpu',volumeMounts=[dict(name='runtime',mountPath='/var/lib/t01')])],
            volumes=[dict(name='runtime',persistentVolumeClaim=dict(claimName='runtime')),
                     dict(name='resident-config',configMap=dict(name='old'))]))))
    config=dict(version='0.1.0',runtime_volume_root='/var/lib/t01',tools={t:dict(command=dict(tool=t,environment={}))
            for t in ('proteinmpnn','esm-if1','thermompnn')})
    config['_configmap_data']={'resident.json':'old','cpu.worker.json':'preserved'}
    return deployment,config,'harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:'+'a'*64


def test_render_preserves_service_env_and_coordinates_gpu_registry():
    args=inputs();before=copy.deepcopy(args)
    config,code,patch=render(*args)
    assert args==before
    assert config['data']['cpu.worker.json']=='preserved'
    resident=json.loads(config['data']['resident.json'])
    gpu=json.loads(config['data']['gpu.worker.json'])
    assert '_configmap_data' not in resident
    assert all(c['environment']['T01_SHARED_GPU_LOCK']==LOCK for c in gpu['commands'])
    assert resident['tools']['esmfold2']['command']['environment']['T01_SHARED_GPU_LOCK']==LOCK
    assert not any('/env' in p['path'] for p in patch)
    mounts=next(p['value'] for p in patch if p['path'].endswith('/volumeMounts'))
    assert any(m['mountPath']=='/opt/t01/worker.json' for m in mounts)
    assert any(m['mountPath'].endswith('/resident_process.py') for m in mounts)
    assert patch[0]==dict(op='test',path='/metadata/resourceVersion',value='123')
    assert code['immutable'] and config['immutable']
    worker=patch[-1]['value']
    assert worker['resources']['limits']['nvidia.com/gpumem']=='32768'
    assert next(m for m in worker['volumeMounts'] if m['mountPath']=='/models')['readOnly']


@pytest.mark.parametrize('damage',['tag','duplicate','strategy'])
def test_unreviewed_states_refused(damage):
    d,c,image=inputs()
    if damage=='tag':image='registry/image:latest'
    elif damage=='duplicate':c['tools']['esmfold2']={}
    else:d['spec']['strategy']['type']='RollingUpdate'
    with pytest.raises(ValueError):render(d,c,image)


def test_worker_config_is_a_single_file_mount_for_symlink_guard():
    worker=render(*inputs())[-1][-1]['value']
    config_path=worker['args'][worker['args'].index('--config')+1]
    mount=next(m for m in worker['volumeMounts'] if m['name']=='resident-config')
    assert mount['mountPath']==config_path
    assert mount['subPath']=='esmfold2.worker.json'
    assert mount['readOnly'] is True
