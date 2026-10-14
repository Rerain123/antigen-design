"""Mount a direct BLAST executable to bypass the image's vmtouch prefetch wrapper."""
import argparse
import base64
import hashlib
import json
import subprocess

import yaml

import prepare_m1_p1_deploy as common


OUT = common.ROOT / 'deploy/m1-p4/nr-blast-exec-r01'
NAME = 'antigen-m1-p4-blast-exec-r01'
VOLUME = 'blast-exec-fix'
MOUNT = '/blast/bin/blastp'
WRAPPER = '#!/bin/sh\nexec /blast/bin/blastp.REAL "$@"\n'


def patch(live):
    assert live['spec']['replicas'] == 1 and live['spec']['strategy'] == {'type': 'Recreate'}
    spec = live['spec']['template']['spec']
    assert not any(v['name'] == VOLUME for v in spec['volumes'])
    worker = [(i, c) for i, c in enumerate(spec['containers']) if c['name'] == 'worker-blast']
    assert len(worker) == 1
    i, container = worker[0]
    assert container['resources']['limits']['memory'] == '8Gi'
    assert not any(m['mountPath'] == MOUNT for m in container['volumeMounts'])
    return [
        dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
        dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
        dict(op='add', path=f'/spec/template/spec/containers/{i}/volumeMounts/-',
             value=dict(name=VOLUME, mountPath=MOUNT, subPath='blastp', readOnly=True)),
        dict(op='add', path='/spec/template/spec/volumes/-',
             value=dict(name=VOLUME, configMap=dict(name=NAME, defaultMode=493))),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    idle = common.idle()
    assert not idle['active_jobs'] and idle['gpu_state']['phase'] == 'idle'
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    operations = patch(live)
    wrapper_sha = hashlib.sha256(WRAPPER.encode()).hexdigest()
    cm = dict(apiVersion='v1', kind='ConfigMap',
              metadata=dict(name=NAME, namespace='him-ws'), immutable=True,
              data={'blastp': WRAPPER})
    if args.apply:
        preflight = json.loads((OUT / 'preflight.json').read_bytes())
        assert preflight['wrapper_sha256'] == wrapper_sha
        subprocess.run(common.K + ['create', '-f', str(OUT / 'configmap.yaml')], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                                   '--patch-file', str(OUT / 'deployment.patch.json')], check=True)
        return
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'configmap.yaml').write_text(yaml.safe_dump(cm, sort_keys=False), encoding='utf-8')
    (OUT / 'deployment.patch.json').write_text(json.dumps(operations, indent=2) + '\n', encoding='utf-8')
    (OUT / 'preflight.json').write_text(json.dumps(dict(
        reason='Bypass /blast/bin/blastp vmtouch/parallel prefetch wrapper', idle=idle,
        wrapper_sha256=wrapper_sha, deployment_uid=live['metadata']['uid'],
        deployment_resource_version=live['metadata']['resourceVersion'],
        deployment_generation=live['metadata']['generation'], worker_pod_physical_memory_limit='8Gi',
        mount_path=MOUNT, real_binary='/blast/bin/blastp.REAL'), indent=2) + '\n', encoding='utf-8')
    subprocess.run(common.K + ['create', '--dry-run=server', '-f', str(OUT / 'configmap.yaml')], check=True)
    subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                               '--patch-file', str(OUT / 'deployment.patch.json'),
                               '--dry-run=server', '-o', 'name'], check=True)


if __name__ == '__main__':
    main()
