"""Deploy persistent target-nr receipt reuse across service restarts."""
import argparse
import base64
import hashlib
import json
import subprocess

import yaml

import prepare_m1_p1_deploy as common


OUT = common.ROOT / 'deploy/m1-p4/nr-receipt-fix-r01'
CODE_NAME = 'antigen-m1-p4-nr-fix-r02'
RECEIPT_NAME = 'antigen-m1-p4-nr-receipt-r01'
CODE_VOLUME = 'p4-nr-fixes-r02'
RECEIPT_VOLUME = 'p4-nr-receipt'
CODE_SOURCES = {
    'development/blast/policy.py': common.ROOT / 'src/t01_phase1_real/development/blast/policy.py',
    'development/blast/prebuilt.py': common.ROOT / 'src/t01_phase1_real/development/blast/prebuilt.py',
    'resident_process.py': common.ROOT / 'src/t01_phase1_real/resident_process.py',
    'development/blast/worker.py': common.ROOT / 'src/t01_phase1_real/development/blast/worker.py',
}
SERVICE_MOUNTS = {
    'development/blast/policy.py': '/app/src/t01_phase1_real/development/blast/policy.py',
    'development/blast/prebuilt.py': '/app/src/t01_phase1_real/development/blast/prebuilt.py',
    'resident_process.py': '/app/src/t01_phase1_real/resident_process.py',
}
WORKER_MOUNT = '/opt/t01/src/t01_phase1_real/development/blast/worker.py'
RECEIPT_MOUNT = '/etc/t01/blast-target-receipt.json'
RECEIPT_SOURCE = common.ROOT / 'deploy/m1-p4/nr-receipt-r01/target-receipt.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch(live):
    assert live['spec']['replicas'] == 1 and live['spec']['strategy'] == {'type': 'Recreate'}
    spec = live['spec']['template']['spec']
    assert not any(v['name'] in (CODE_VOLUME, RECEIPT_VOLUME) for v in spec['volumes'])
    service_index, service = next((i, c) for i, c in enumerate(spec['containers']) if c['name'] == 'service')
    worker_index, worker = next((i, c) for i, c in enumerate(spec['containers']) if c['name'] == 'worker-blast')
    service_paths = set(SERVICE_MOUNTS.values()) | {RECEIPT_MOUNT}
    service_mounts = [m for m in service['volumeMounts'] if m['mountPath'] not in service_paths]
    service_mounts += [dict(name=CODE_VOLUME, mountPath=path, subPath='p' + str(index), readOnly=True)
                       for index, path in enumerate(SERVICE_MOUNTS.values())]
    service_mounts.append(dict(name=RECEIPT_VOLUME, mountPath=RECEIPT_MOUNT,
                               subPath='target-receipt.json', readOnly=True))
    worker_mounts = [m for m in worker['volumeMounts'] if m['mountPath'] != WORKER_MOUNT]
    worker_mounts.append(dict(name=CODE_VOLUME, mountPath=WORKER_MOUNT, subPath='p3', readOnly=True))
    return [
        dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
        dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
        dict(op='replace', path=f'/spec/template/spec/containers/{service_index}/volumeMounts', value=service_mounts),
        dict(op='replace', path=f'/spec/template/spec/containers/{worker_index}/volumeMounts', value=worker_mounts),
        dict(op='add', path='/spec/template/spec/volumes/-',
             value=dict(name=CODE_VOLUME, configMap=dict(name=CODE_NAME))),
        dict(op='add', path='/spec/template/spec/volumes/-',
             value=dict(name=RECEIPT_VOLUME, configMap=dict(name=RECEIPT_NAME))),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    idle = common.idle()
    assert not idle['active_jobs'] and idle['gpu_state']['phase'] == 'idle'
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    code_hashes = {name: digest(path) for name, path in CODE_SOURCES.items()}
    receipt_hash = digest(RECEIPT_SOURCE)
    if args.apply:
        preflight = json.loads((OUT / 'preflight.json').read_bytes())
        assert preflight['code_hashes'] == code_hashes and preflight['receipt_hash'] == receipt_hash
        assert preflight['deployment_resource_version'] == live['metadata']['resourceVersion']
        for name in (CODE_NAME, RECEIPT_NAME):
            subprocess.run(common.K + ['create', '-f', str(OUT / (name + '.yaml'))], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                                   '--patch-file', str(OUT / 'deployment.patch.json')], check=True)
        print('P4_NR_PERSISTENT_RECEIPT_ROLLOUT_SUBMITTED')
        return
    code_cm = dict(apiVersion='v1', kind='ConfigMap', metadata=dict(name=CODE_NAME, namespace='him-ws'),
                   immutable=True, binaryData={'p' + str(index): base64.b64encode(path.read_bytes()).decode()
                                               for index, path in enumerate(CODE_SOURCES.values())})
    receipt_cm = dict(apiVersion='v1', kind='ConfigMap', metadata=dict(name=RECEIPT_NAME, namespace='him-ws'),
                      immutable=True, binaryData={'target-receipt.json': base64.b64encode(RECEIPT_SOURCE.read_bytes()).decode()})
    operations = patch(live)
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / (CODE_NAME + '.yaml')).write_text(yaml.safe_dump(code_cm, sort_keys=False), encoding='utf-8')
    (OUT / (RECEIPT_NAME + '.yaml')).write_text(yaml.safe_dump(receipt_cm, sort_keys=False), encoding='utf-8')
    (OUT / 'deployment.patch.json').write_text(json.dumps(operations, indent=2) + '\n', encoding='utf-8')
    (OUT / 'preflight.json').write_text(json.dumps(dict(
        reason='Persist full target-nr receipt across service restarts; startup rechecks manifest and file stat signatures',
        idle=idle, deployment_uid=live['metadata']['uid'],
        deployment_resource_version=live['metadata']['resourceVersion'],
        deployment_generation=live['metadata']['generation'], code_hashes=code_hashes,
        receipt_hash=receipt_hash, receipt_source=RECEIPT_SOURCE.relative_to(common.ROOT).as_posix(),
        receipt_mount=RECEIPT_MOUNT, target_database='nr-20250624',
        target_manifest_sha256='ea46b05b6465cd97557cf0e6304cc0e7766e53d4ece4209b55bf59d64d4841cd'), indent=2) + '\n', encoding='utf-8')
    for name in (CODE_NAME, RECEIPT_NAME):
        subprocess.run(common.K + ['create', '--dry-run=server', '-f', str(OUT / (name + '.yaml'))], check=True)
    subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                               '--patch-file', str(OUT / 'deployment.patch.json'),
                               '--dry-run=server', '-o', 'name'], check=True)
    print('P4_NR_PERSISTENT_RECEIPT_PREPARED', OUT)


if __name__ == '__main__':
    main()
