"""Prepare a CAS-protected CPU maintenance patch; never applies or deletes resources."""
import copy
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.tmp/single-gpu-cpu-r01'
K = ['C:/Program Files/Docker/Docker/resources/bin/kubectl.exe', '--kubeconfig',
     str(ROOT / '.tmp/himat.kubeconfig'), '-n', 'him-ws', '--request-timeout=30s']


def cpu_patch(live):
    if live['metadata']['name'] != 'antigen-design' or live['spec']['replicas'] != 1:
        raise ValueError('Unexpected deployment identity/replica count')
    if live['spec']['strategy'] != {'type': 'Recreate'}:
        raise ValueError('Recreate required to release old allocations before replacement')
    template = copy.deepcopy(live['spec']['template'])
    spec = template['spec']
    removed = [c for c in spec['containers'] if c['name'] in ('worker-gpu', 'worker-esmfold2')]
    if len(removed) != 2:
        raise ValueError('Expected both original GPU workers')
    spec['containers'] = [c for c in spec['containers'] if c not in removed]
    for c in spec.get('initContainers', []) + spec['containers']:
        for values in c.get('resources', {}).values():
            if any(k.startswith('nvidia.com/') for k in values):
                raise ValueError('Unexpected remaining GPU resource')
        env = [e for e in c.get('env', []) if e['name'] not in ('NVIDIA_VISIBLE_DEVICES', 'CUDA_VISIBLE_DEVICES')]
        c['env'] = env + [{'name': 'NVIDIA_VISIBLE_DEVICES', 'value': 'void'},
                          {'name': 'CUDA_VISIBLE_DEVICES', 'value': ''}]
    spec.pop('runtimeClassName', None)
    spec['schedulerName'] = 'default-scheduler'
    annotations = template['metadata'].setdefault('annotations', {})
    for key in list(annotations):
        if key.startswith(('nvidia.com/', 'hami.io/')):
            del annotations[key]
    annotations['antigen-design/gpu-mode'] = 'cpu-maintenance'
    return [
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': live['metadata']['resourceVersion']},
        {'op': 'test', 'path': '/metadata/uid', 'value': live['metadata']['uid']},
        {'op': 'test', 'path': '/spec', 'value': live['spec']},
        {'op': 'replace', 'path': '/spec/template', 'value': template},
    ]


def main():
    live = json.loads(subprocess.check_output(K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    patch = cpu_patch(live)
    OUT.mkdir(parents=True, exist_ok=False)
    # Local private snapshot may contain service settings; do not print or publish it.
    (OUT / 'before.json').write_text(json.dumps(live, indent=2), encoding='utf-8')
    target = OUT / 'patch.json'
    target.write_text(json.dumps(patch, indent=2), encoding='utf-8')
    subprocess.run(K + ['patch', 'deployment', 'antigen-design', '--type=json',
                       '--patch-file', str(target), '--dry-run=server', '-o', 'name'], check=True)
    print('CPU_MODE_PREPARED_SERVER_DRY_RUN_PASS', target)


if __name__ == '__main__':
    main()
