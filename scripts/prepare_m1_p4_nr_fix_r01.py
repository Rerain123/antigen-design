"""Deploy the complete P4 BLAST fix set without changing the target database."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import subprocess

import yaml

import prepare_m1_p1_deploy as common


OUT = common.ROOT / 'deploy/m1-p4/nr-fix-r01'
NAME = 'antigen-m1-p4-nr-fix-r01'
VOLUME = 'p4-nr-fixes'
SERVICE_MOUNT = {
    'development/blast/policy.py': '/app/src/t01_phase1_real/development/blast/policy.py',
    'development/blast/prebuilt.py': '/app/src/t01_phase1_real/development/blast/prebuilt.py',
    'resident_process.py': '/app/src/t01_phase1_real/resident_process.py',
}
WORKER_MOUNT = 'development/blast/worker.py'
TARGET_MOUNT = '/var/lib/t01/m1-p1-test-data/blast/nr-20250624'
WORKER_TARGET_MOUNT = '/t01/databases/blast/nr-20250624'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {
        'development/blast/policy.py': common.ROOT / 'src/t01_phase1_real/development/blast/policy.py',
        'development/blast/prebuilt.py': common.ROOT / 'src/t01_phase1_real/development/blast/prebuilt.py',
        'resident_process.py': common.ROOT / 'src/t01_phase1_real/resident_process.py',
        'development/blast/worker.py': common.ROOT / 'src/t01_phase1_real/development/blast/worker.py',
    }


def patch(live):
    assert live['spec']['replicas'] == 1 and live['spec']['strategy'] == {'type': 'Recreate'}
    spec = live['spec']['template']['spec']
    assert not any(v['name'] == VOLUME for v in spec['volumes'])
    workers = [(i, c) for i, c in enumerate(spec['containers']) if c['name'] == 'worker-blast']
    services = [(i, c) for i, c in enumerate(spec['containers']) if c['name'] == 'service']
    assert len(workers) == len(services) == 1
    worker_index, worker = workers[0]
    service_index, service = services[0]
    assert worker['resources']['limits'] == {'cpu': '2', 'memory': '8Gi'}
    assert any(m['mountPath'] == TARGET_MOUNT and m['readOnly'] for m in service['volumeMounts'])
    assert any(m['mountPath'] == WORKER_TARGET_MOUNT and m['readOnly'] for m in worker['volumeMounts'])
    assert any(m['mountPath'] == '/blast/bin/blastp' and m['readOnly'] for m in worker['volumeMounts'])
    service_paths = set(SERVICE_MOUNT.values())
    service_mounts = [m for m in service['volumeMounts'] if m['mountPath'] not in service_paths]
    for index, mount_path in enumerate(SERVICE_MOUNT.values()):
        service_mounts.append(dict(name=VOLUME, mountPath=mount_path,
                                   subPath='p' + str(index), readOnly=True))
    worker_mounts = [m for m in worker['volumeMounts']
                     if m['mountPath'] != '/opt/t01/src/t01_phase1_real/development/blast/worker.py']
    worker_mounts.append(dict(name=VOLUME,
                              mountPath='/opt/t01/src/t01_phase1_real/development/blast/worker.py',
                              subPath='p3', readOnly=True))
    resources = copy.deepcopy(worker['resources'])
    resources.setdefault('limits', {})['cpu'] = '4'
    resources['limits']['memory'] = '16Gi'
    return [
        dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
        dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
        dict(op='replace', path=f'/spec/template/spec/containers/{service_index}/volumeMounts', value=service_mounts),
        dict(op='replace', path=f'/spec/template/spec/containers/{worker_index}/volumeMounts', value=worker_mounts),
        dict(op='replace', path=f'/spec/template/spec/containers/{worker_index}/resources', value=resources),
        dict(op='add', path='/spec/template/spec/volumes/-',
             value=dict(name=VOLUME, configMap=dict(name=NAME))),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    idle = common.idle()
    assert not idle['active_jobs'] and idle['gpu_state']['phase'] == 'idle'
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    src = sources()
    hashes = {name: sha(path) for name, path in src.items()}
    if args.apply:
        preflight = json.loads((OUT / 'preflight.json').read_bytes())
        assert preflight['source_hashes'] == hashes
        assert preflight['deployment_resource_version'] == live['metadata']['resourceVersion']
        subprocess.run(common.K + ['create', '-f', str(OUT / 'configmap.yaml')], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                                   '--patch-file', str(OUT / 'deployment.patch.json')], check=True)
        print('P4_NR_FIX_ROLLOUT_SUBMITTED')
        return
    config = dict(apiVersion='v1', kind='ConfigMap',
                  metadata=dict(name=NAME, namespace='him-ws'), immutable=True,
                  binaryData={
                      'p' + str(index): base64.b64encode(path.read_bytes()).decode()
                      for index, path in enumerate(src.values())
                  })
    operations = patch(live)
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'configmap.yaml').write_text(yaml.safe_dump(config, sort_keys=False), encoding='utf-8')
    (OUT / 'deployment.patch.json').write_text(json.dumps(operations, indent=2) + '\n', encoding='utf-8')
    worker_index = next(i for i, c in enumerate(live['spec']['template']['spec']['containers'])
                        if c['name'] == 'worker-blast')
    (OUT / 'preflight.json').write_text(json.dumps(dict(
        reason='Deploy target nr cache de-duplication, native BLAST entrypoint, 1TiB address space, 16Gi/4CPU worker',
        idle=idle,
        deployment_uid=live['metadata']['uid'],
        deployment_resource_version=live['metadata']['resourceVersion'],
        deployment_generation=live['metadata']['generation'],
        source_hashes=hashes,
        old_worker_limits=live['spec']['template']['spec']['containers'][worker_index]['resources']['limits'],
        target_mounts=dict(service=TARGET_MOUNT, worker=WORKER_TARGET_MOUNT, read_only=True),
        direct_blast_binary='/blast/bin/blastp.REAL'), indent=2) + '\n', encoding='utf-8')
    subprocess.run(common.K + ['create', '--dry-run=server', '-f', str(OUT / 'configmap.yaml')], check=True)
    subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                               '--patch-file', str(OUT / 'deployment.patch.json'),
                               '--dry-run=server', '-o', 'name'], check=True)
    print('P4_NR_FIX_PREPARED', OUT)


if __name__ == '__main__':
    main()
