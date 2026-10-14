"""Render stopped dispatcher/slot deployments from reviewed operator snapshots.

No apply. Enabling requires RBAC, CPU-only service mode and no active GPU holder.
AF3 is deliberately not registered until its resident adapter is implemented.
"""
import copy
import json
from pathlib import Path
import subprocess
import yaml

from prepare_single_gpu_cpu_mode import ROOT, K

NAME = 'antigen-gpu-dispatcher'
SLOT = 'antigen-design-gpu-slot'
UUID = 'GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31'
OUTPUT = ROOT / 'deploy/single-gpu/dispatcher.r01.yaml'


def render(original, registry):
    modes = {}
    volumes = original['spec']['template']['spec']['volumes']
    affinity = {'podAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': [{
        'labelSelector': original['spec']['selector'], 'topologyKey': 'kubernetes.io/hostname'}]}}
    for mode in ('gpu', 'esmfold2'):
        c = copy.deepcopy(next(c for c in original['spec']['template']['spec']['containers'] if c['name'] == 'worker-' + mode))
        config_path = '/opt/t01/worker.json' if mode == 'gpu' else '/etc/t01/esmfold2.worker.json'
        interpreter = '/opt/t01/supervisor/bin/python3.11' if mode == 'gpu' else 'python'
        c['command'] = [interpreter, '-u', '-B', '-m', 't01_phase1_real.gpu_once']
        c['args'] = ['--root', '/var/lib/t01/resident/' + mode, '--config', config_path, '--uuid', UUID]
        c['name'] = 'gpu-worker'
        for kind in ('requests', 'limits'):
            c['resources'][kind] = {k:v for k,v in c['resources'][kind].items() if not k.startswith('nvidia.com/')}
            c['resources'][kind].update({'nvidia.com/gpu': '1', 'nvidia.com/gpumem-percentage': '100', 'nvidia.com/gpucores': '100'})
        package = '/opt/t01/src' if mode == 'gpu' else '/backend'
        c['volumeMounts'].append({'name':'gpu-dispatch-code','mountPath':package+'/t01_phase1_real/gpu_once.py',
                                 'subPath':'gpu_once.py','readOnly':True})
        used = {v['name'] for v in c['volumeMounts']}
        pv = [copy.deepcopy(v) for v in volumes if v['name'] in used]
        pv.append({'name':'gpu-dispatch-code','configMap':{'name':NAME+'-code-r01'}})
        template = {'metadata':{'labels':{'app':SLOT},'annotations':{'nvidia.com/use-gputype':'A100-SXM-64GB','nvidia.com/use-gpuuuid':UUID}},
                    'spec':{'automountServiceAccountToken':False,'runtimeClassName':'nvidia','schedulerName':'hami-scheduler',
                            'imagePullSecrets':[{'name':'harbor'}], 'securityContext':{'runAsUser':10001,'runAsGroup':10001,'fsGroup':10001,'runAsNonRoot':True},
                            'affinity':affinity,'containers':[c],'volumes':pv,'terminationGracePeriodSeconds':60}}
        commands = {row['tool']:row for row in registry[mode]['commands']}
        expected = {'esmfold2'} if mode == 'esmfold2' else {'proteinmpnn','esm-if1','thermompnn'}
        if set(commands) != expected:
            raise ValueError('Unexpected operator registry')
        modes[mode] = {'root':'/var/lib/t01/resident/'+mode, 'commands':commands,'template':template}
    config = {'namespace':'him-ws','deployment':SLOT,'modes':modes}
    code = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':NAME+'-code-r01','namespace':'him-ws'},'immutable':True,
            'data':{name:(ROOT/'src/t01_phase1_real'/name).read_text(encoding='utf-8') for name in ('gpu_dispatch.py','gpu_once.py')}}
    settings = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':NAME+'-config-r01','namespace':'him-ws'},'immutable':True,
                'data':{'dispatch.json':json.dumps(config,indent=2)}}
    slot = {'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':SLOT,'namespace':'him-ws'},
            'spec':{'replicas':0,'strategy':{'type':'Recreate'},'selector':{'matchLabels':{'app':SLOT}},'template':modes['esmfold2']['template']}}
    service = next(c for c in original['spec']['template']['spec']['containers'] if c['name']=='service')
    control = {'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':NAME,'namespace':'him-ws'},
               'spec':{'replicas':0,'strategy':{'type':'Recreate'},'selector':{'matchLabels':{'app':NAME}},'template':{
                   'metadata':{'labels':{'app':NAME}},'spec':{'serviceAccountName':NAME,'automountServiceAccountToken':True,
                       'imagePullSecrets':[{'name':'harbor'}],'affinity':affinity,
                       'securityContext':{'runAsUser':10001,'runAsGroup':10001,'fsGroup':10001,'runAsNonRoot':True},
                       'containers':[{'name':'dispatcher','image':service['image'],
                           'command':['python','-u','-B','-m','t01_phase1_real.gpu_dispatch'],
                           'args':['--config','/dispatch/dispatch.json','--state','/var/lib/t01/gpu-dispatch/state.json'],
                           'env':[{'name':'PYTHONPATH','value':'/app/src'},{'name':'NVIDIA_VISIBLE_DEVICES','value':'void'}],
                           'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'1','memory':'512Mi'}},
                           'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
                           'volumeMounts':[{'name':'runtime','mountPath':'/var/lib/t01'},
                               {'name':'config','mountPath':'/dispatch','readOnly':True},
                               {'name':'code','mountPath':'/app/src/t01_phase1_real/gpu_dispatch.py','subPath':'gpu_dispatch.py','readOnly':True}]}],
                       'volumes':[{'name':'runtime','persistentVolumeClaim':{'claimName':'antigen-design-runtime'}},
                                  {'name':'code','configMap':{'name':NAME+'-code-r01'}},
                                  {'name':'config','configMap':{'name':NAME+'-config-r01'}}]}}}}
    return [code,settings,slot,control]


if __name__ == '__main__':
    original=json.loads((ROOT/'.tmp/single-gpu-cpu-r01/before.json').read_bytes())
    volume=next(v for v in original['spec']['template']['spec']['volumes'] if v['name']=='resident-config')
    cm=json.loads(subprocess.check_output(K+['get','configmap',volume['configMap']['name'],'-o','json']))
    registry={m:json.loads(cm['data'][m+'.worker.json']) for m in ('gpu','esmfold2')}
    docs=render(original,registry)
    OUTPUT.write_text(yaml.safe_dump_all(docs,sort_keys=False),encoding='utf-8')
    print('PREPARED_STOPPED_GPU_DISPATCHER',OUTPUT)
