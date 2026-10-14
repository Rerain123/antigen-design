"""Deploy the BLAST result-contract compatibility fix for the direct REAL entrypoint."""
import argparse
import base64
import hashlib
import json
import subprocess

import yaml

import prepare_m1_p1_deploy as common


OUT = common.ROOT / 'deploy/m1-p4/nr-result-fix-r01'
NAME = 'antigen-m1-p4-nr-result-fix-r01'
VOLUME = 'p4-nr-result-fix'
MOUNT = '/app/src/t01_phase1_real/development/blast/result.py'
SOURCE = common.ROOT / 'src/t01_phase1_real/development/blast/result.py'


def patch(live):
    assert live['spec']['replicas'] == 1 and live['spec']['strategy'] == {'type': 'Recreate'}
    spec = live['spec']['template']['spec']
    assert not any(v['name'] == VOLUME for v in spec['volumes'])
    service = [(i, c) for i, c in enumerate(spec['containers']) if c['name'] == 'service']
    assert len(service) == 1
    index, container = service[0]
    assert not any(m['mountPath'] == MOUNT for m in container['volumeMounts'])
    mounts = list(container['volumeMounts'])
    mounts.append(dict(name=VOLUME, mountPath=MOUNT, subPath='result.py', readOnly=True))
    return [
        dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
        dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
        dict(op='replace', path=f'/spec/template/spec/containers/{index}/volumeMounts', value=mounts),
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
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if args.apply:
        preflight = json.loads((OUT / 'preflight.json').read_bytes())
        assert preflight['source_hash'] == source_hash
        assert preflight['deployment_resource_version'] == live['metadata']['resourceVersion']
        subprocess.run(common.K + ['create', '-f', str(OUT / 'configmap.yaml')], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                                   '--patch-file', str(OUT / 'deployment.patch.json')], check=True)
        print('P4_NR_RESULT_FIX_ROLLOUT_SUBMITTED')
        return
    config = dict(apiVersion='v1', kind='ConfigMap',
                  metadata=dict(name=NAME, namespace='him-ws'), immutable=True,
                  binaryData={'result.py': base64.b64encode(SOURCE.read_bytes()).decode()})
    operations = patch(live)
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'configmap.yaml').write_text(yaml.safe_dump(config, sort_keys=False), encoding='utf-8')
    (OUT / 'deployment.patch.json').write_text(json.dumps(operations, indent=2) + '\n', encoding='utf-8')
    (OUT / 'preflight.json').write_text(json.dumps(dict(
        reason='Accept the intentional /blast/bin/blastp.REAL direct entrypoint while preserving fixed arguments and output hashes',
        idle=idle, deployment_uid=live['metadata']['uid'],
        deployment_resource_version=live['metadata']['resourceVersion'],
        deployment_generation=live['metadata']['generation'], source_hash=source_hash,
        mount_path=MOUNT, read_only=True), indent=2) + '\n', encoding='utf-8')
    subprocess.run(common.K + ['create', '--dry-run=server', '-f', str(OUT / 'configmap.yaml')], check=True)
    subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                               '--patch-file', str(OUT / 'deployment.patch.json'),
                               '--dry-run=server', '-o', 'name'], check=True)
    print('P4_NR_RESULT_FIX_PREPARED', OUT)


if __name__ == '__main__':
    main()
