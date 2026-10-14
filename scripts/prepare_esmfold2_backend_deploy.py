"""Read current deployment and render a guarded user-applied ESMFold2 update.

No cluster mutations. A published control-image digest is required; never infer
an uploaded image from a local tag. Existing credentials/env are kept in place
through a JSON Patch instead of exporting the full Deployment.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.development.esmfold2 import policy
from t01_phase1_real.resident_process import Command

NS='him-ws'
NAME='antigen-design'
CONFIG='antigen-resident-config-esmfold2-r01'
CODE='antigen-esmfold2-backend-code-r01'
LOCK='/var/lib/t01/.gpu-execution.lock'
CODE_FILES=['__init__.py','common.py','resident_worker.py','resident_process.py','resident_offline.py',
            'process_control/__init__.py','process_control/posix.py','development/__init__.py']


def encoded(value): return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()


def kc(*args,data=None):
    result=subprocess.run(['kubectl','--kubeconfig',str(ROOT/'.tmp/himat.kubeconfig'),'-n',NS,'--request-timeout=45s',*args],
                          input=data,capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-1500:])
    return result.stdout


def render(deployment, oldconfig, control_image):
    if not re.fullmatch(r'harbor-core\.base\.svc\.cluster\.local/qcyz/antigen-design@sha256:[a-f0-9]{64}',control_image):
        raise ValueError('Published control image digest required')
    spec=deployment['spec'];pod=spec['template']['spec']
    if spec['replicas']!=1 or spec['strategy']['type']!='Recreate':raise ValueError('Expected singleton Recreate deployment')
    containers=pod['containers'];index={c['name']:i for i,c in enumerate(containers)}
    if 'worker-esmfold2' in index or not {'service','worker-gpu'}<=set(index):raise ValueError('Unexpected deployment stage')
    config=copy.deepcopy(oldconfig)
    if config['version']!='0.1.0' or config['runtime_volume_root']!='/var/lib/t01':raise ValueError('Unexpected resident volume root')
    if 'esmfold2' in config['tools']:raise ValueError('Prediction already registered')
    for tool in ('proteinmpnn','esm-if1','thermompnn'):
        config['tools'][tool]['command']['environment']['T01_SHARED_GPU_LOCK']=LOCK
    env=dict(T01_RESIDENT_OFFLINE='1',T01_SOURCE_IMAGE_ID=policy.IMAGE,T01_SHARED_GPU_LOCK=LOCK,
             PYTHONPATH='/backend:/models/esmfold2-environment-20260916-r01/site-packages',
             HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
             OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',TRITON_CACHE_DIR='/tmp/triton',XDG_CACHE_HOME='/tmp/cache')
    command=Command('esmfold2',('/usr/local/bin/python','-B','-m','t01_phase1_real.development.esmfold2.worker',
        '--input-dir','{input}','--output-dir','{output}/native'),tuple(sorted(env.items())),256*1024**3).document()
    config['tools']['esmfold2']=dict(root='/var/lib/t01/resident/esmfold2',source_image_id=policy.IMAGE,command=command)
    data=copy.deepcopy(oldconfig['_configmap_data']) if '_configmap_data' in oldconfig else {}
    config.pop('_configmap_data',None)
    data['resident.json']=json.dumps(config,sort_keys=True)
    # Keep CPU worker configs byte-for-byte; update the three GPU commands as one registry.
    data['gpu.worker.json']=json.dumps(dict(version='0.1.0',commands=[config['tools'][t]['command'] for t in ('proteinmpnn','esm-if1','thermompnn')]))
    data['esmfold2.worker.json']=json.dumps(dict(version='0.1.0',commands=[command]))
    configmap=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=CONFIG,namespace=NS),immutable=True,data=data)
    paths=CODE_FILES+['development/esmfold2/'+p.name for p in sorted(policy.HERE.iterdir()) if p.suffix in ('.py','.json')]
    code={};items=[]
    for i,path in enumerate(paths):
        key='source-'+str(i)
        code[key]=(ROOT/'src/t01_phase1_real'/path).read_text(encoding='utf-8')
        items.append(dict(key=key,path='t01_phase1_real/'+path))
    codemap=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=CODE,namespace=NS),immutable=True,data=code)
    volumes=copy.deepcopy(pod['volumes'])
    resident=next(v for v in volumes if v['name']=='resident-config')
    resident['configMap']['name']=CONFIG
    if any(v['name'] in ('esmfold2-models','esmfold2-code','esmfold2-tmp') for v in volumes):raise ValueError('Volume collision')
    volumes += [dict(name='esmfold2-models',persistentVolumeClaim=dict(claimName='antigen-esmfold2-models',readOnly=True)),
                dict(name='esmfold2-code',configMap=dict(name=CODE,items=items)),
                dict(name='esmfold2-tmp',emptyDir=dict(sizeLimit='8Gi'))]
    gpu=containers[index['worker-gpu']]
    gpu_mounts=copy.deepcopy(gpu['volumeMounts'])+[dict(name='esmfold2-code',
        mountPath='/opt/t01/src/t01_phase1_real/resident_process.py',subPath='t01_phase1_real/resident_process.py',readOnly=True),
        dict(name='resident-config',mountPath='/opt/t01/worker.json',subPath='gpu.worker.json',readOnly=True)]
    worker=dict(name='worker-esmfold2',image='harbor-core.base.svc.cluster.local/qcyz/antigen-esmfold2@'+policy.IMAGE,
        command=['python','-u','-B','-m','t01_phase1_real.resident_worker'],
        args=['--root','/var/lib/t01/resident/esmfold2','--config','/etc/t01/esmfold2.worker.json'],
        env=[dict(name='PYTHONPATH',value=env['PYTHONPATH'])],
        resources=dict(requests={'cpu':'2','memory':'32Gi','ephemeral-storage':'2Gi'},
                       limits={'cpu':'8','memory':'64Gi','ephemeral-storage':'8Gi','nvidia.com/gpu':'1','nvidia.com/gpumem':'32768'}),
        securityContext=dict(allowPrivilegeEscalation=False,readOnlyRootFilesystem=True,capabilities=dict(drop=['ALL'])),
        volumeMounts=[dict(name='runtime',mountPath='/var/lib/t01'),dict(name='resident-config',mountPath='/etc/t01/esmfold2.worker.json',subPath='esmfold2.worker.json',readOnly=True),
                      dict(name='esmfold2-code',mountPath='/backend',readOnly=True),
                      dict(name='esmfold2-models',mountPath='/models',readOnly=True),dict(name='esmfold2-tmp',mountPath='/tmp')])
    patch=[dict(op='test',path='/metadata/resourceVersion',value=deployment['metadata']['resourceVersion']),
           dict(op='test',path='/spec/template/spec/containers/'+str(index['service'])+'/image',value=containers[index['service']]['image']),
           dict(op='replace',path='/spec/template/spec/volumes',value=volumes),
           dict(op='replace',path='/spec/template/spec/containers/'+str(index['service'])+'/image',value=control_image),
           dict(op='replace',path='/spec/template/spec/containers/'+str(index['worker-gpu'])+'/volumeMounts',value=gpu_mounts),
           dict(op='add',path='/spec/template/spec/containers/-',value=worker)]
    return configmap,codemap,patch


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control-image',required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    if args.output_dir.exists():raise ValueError('Use a new output directory')
    deployment=json.loads(kc('get','deployment',NAME,'-o','json'))
    if deployment['status'].get('readyReplicas')!=1 or deployment['status'].get('observedGeneration')!=deployment['metadata']['generation']:
        raise ValueError('Deployment is not stable')
    volume=next(v for v in deployment['spec']['template']['spec']['volumes'] if v['name']=='resident-config')
    cm=json.loads(kc('get','configmap',volume['configMap']['name'],'-o','json'))
    config=json.loads(cm['data']['resident.json']);config['_configmap_data']=cm['data']
    for claim in ('antigen-esmfold2-models','antigen-design-runtime'):
        if json.loads(kc('get','pvc',claim,'-o','json'))['status']['phase']!='Bound':raise ValueError('PVC is not Bound')
    configmap,codemap,patch=render(deployment,config,args.control_image)
    for resource in (configmap,codemap):kc('apply','--dry-run=server','-f','-',data=encoded(resource))
    kc('patch','deployment',NAME,'--type=json','--dry-run=server','-p',json.dumps(patch))
    args.output_dir.mkdir(parents=True)
    for name,value in [('resident-config.json',configmap),('worker-code.json',codemap),('deployment.patch.json',patch)]:
        (args.output_dir/name).write_bytes(encoded(value))
    print('ESMFOLD2_DEPLOY_PREPARED_SERVER_DRY_RUN_PASS',args.output_dir)
    print('No cluster resources were changed. Apply configmaps then guarded Deployment patch explicitly.')


if __name__=='__main__':main()
