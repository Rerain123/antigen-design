"""Prepare immutable N03 policy fix for the persisted nr receipt mount path."""
import argparse
import base64
import hashlib
import json
import subprocess

import yaml

import prepare_m1_p1_deploy as common


OUT = common.ROOT / 'deploy/m1-p4/nr-policy-r03'
NAME = 'antigen-m1-p4-nr-policy-r03'
VOLUME = 'p4-nr-policy-r03'
SOURCE = common.ROOT / 'src/t01_phase1_real/development/blast/policy.py'
MOUNT = '/app/src/t01_phase1_real/development/blast/policy.py'


def patch(live):
    assert live['spec']['replicas'] == 1 and live['spec']['strategy'] == {'type': 'Recreate'}
    spec = live['spec']['template']['spec']
    assert not any(v['name'] == VOLUME for v in spec['volumes'])
    assert any(v['name'] == 'p4-nr-receipt' for v in spec['volumes'])
    service_index, service = next((i, c) for i, c in enumerate(spec['containers']) if c['name'] == 'service')
    worker = next(c for c in spec['containers'] if c['name'] == 'worker-blast')
    assert worker['resources']['limits']['memory'] == '16Gi'
    mounts = list(service['volumeMounts'])
    matches = [(i, m) for i, m in enumerate(mounts) if m['mountPath'] == MOUNT]
    assert len(matches) == 1 and matches[0][1]['name'] == 'p4-nr-fixes-r02'
    assert any(m['mountPath'] == '/etc/t01/blast-target-receipt.json' and m['readOnly'] for m in mounts)
    mount_index = matches[0][0]
    return [
        dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
        dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
        dict(op='replace', path=f'/spec/template/spec/containers/{service_index}/volumeMounts/{mount_index}',
             value=dict(name=VOLUME, mountPath=MOUNT, subPath='policy.py', readOnly=True)),
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
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if args.apply:
        preflight = json.loads((OUT / 'preflight.json').read_bytes())
        assert preflight['source_sha256'] == digest
        assert preflight['deployment_resource_version'] == live['metadata']['resourceVersion']
        subprocess.run(common.K + ['create', '-f', str(OUT / 'configmap.yaml')], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                                   '--patch-file', str(OUT / 'deployment.patch.json')], check=True)
        print('P4_NR_POLICY_R03_ROLLOUT_SUBMITTED')
        return
    operations = patch(live)
    config = dict(apiVersion='v1', kind='ConfigMap',
                  metadata=dict(name=NAME, namespace='him-ws'), immutable=True,
                  binaryData={'policy.py': base64.b64encode(SOURCE.read_bytes()).decode()})
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'configmap.yaml').write_text(yaml.safe_dump(config, sort_keys=False), encoding='utf-8')
    (OUT / 'deployment.patch.json').write_text(json.dumps(operations, indent=2) + '\n', encoding='utf-8')
    (OUT / 'preflight.json').write_text(json.dumps(dict(
        reason='Restore mount_path from the bound persisted target database receipt', idle=idle,
        source_sha256=digest, deployment_uid=live['metadata']['uid'],
        deployment_resource_version=live['metadata']['resourceVersion'],
        deployment_generation=live['metadata']['generation'], mount_path=MOUNT), indent=2) + '\n', encoding='utf-8')
    subprocess.run(common.K + ['create', '--dry-run=server', '-f', str(OUT / 'configmap.yaml')], check=True)
    subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                               '--patch-file', str(OUT / 'deployment.patch.json'),
                               '--dry-run=server', '-o', 'name'], check=True)
    print('P4_NR_POLICY_R03_PREPARED', OUT)


if __name__ == '__main__':
    main()
