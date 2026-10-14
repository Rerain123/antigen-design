"""Raise only BLAST's resident virtual address limit for the prebuilt nr LMDB."""
import argparse
import hashlib
import json
import subprocess

import yaml

import prepare_m1_p1_deploy as common


OLD_CONFIG = 'antigen-unified-gpu-config-r11'
NEW_CONFIG = 'antigen-unified-gpu-config-r12'
OUT = common.ROOT / 'deploy/m1-p4/nr-lmdb-r02'
OLD_ADDRESS_LIMIT = 8 * 1024**3
NEW_ADDRESS_LIMIT = 1024**4


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def changed_config(live):
    assert live.get('immutable') is True and set(live['data']) == {
        'af3.worker.json', 'esmfold2.worker.json', 'gpu.worker.json',
        'resident.json', 'unified-gpu.json'}
    before = json.loads(live['data']['resident.json'])
    assert before['tools']['blast']['command']['memory_bytes'] == OLD_ADDRESS_LIMIT
    assert before['tools']['blast']['command']['environment']['T01_DATABASE_ROOT'] == '/t01/databases/blast'
    after = json.loads(live['data']['resident.json'])
    after['tools']['blast']['command']['memory_bytes'] = NEW_ADDRESS_LIMIT
    data = dict(live['data'])
    data['resident.json'] = json.dumps(after, sort_keys=True, separators=(',', ':'))
    assert all(data[k] == live['data'][k] for k in data if k != 'resident.json')
    return data


def patch(live):
    assert live['spec']['replicas'] == 1 and live['spec']['strategy'] == {'type': 'Recreate'}
    spec = live['spec']['template']['spec']
    worker = next(c for c in spec['containers'] if c['name'] == 'worker-blast')
    assert worker['resources']['limits']['memory'] == '8Gi'
    matches = [(i, v) for i, v in enumerate(spec['volumes']) if v['name'] == 'resident-config']
    assert len(matches) == 1 and matches[0][1]['configMap']['name'] == OLD_CONFIG
    i = matches[0][0]
    return [
        dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
        dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
        dict(op='test', path=f'/spec/template/spec/volumes/{i}/configMap/name', value=OLD_CONFIG),
        dict(op='replace', path=f'/spec/template/spec/volumes/{i}/configMap/name', value=NEW_CONFIG),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    idle = common.idle()
    assert not idle['active_jobs'] and idle['gpu_state']['phase'] == 'idle'
    if args.apply:
        preflight = json.loads((OUT / 'preflight.json').read_bytes())
        live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
        assert live['metadata']['resourceVersion'] == preflight['deployment_resource_version']
        assert live['metadata']['uid'] == preflight['deployment_uid']
        original = json.loads(subprocess.check_output(common.K + ['get', 'configmap', OLD_CONFIG, '-o', 'json']))
        assert digest(original['data']['resident.json']) == preflight['old_resident_sha256']
        assert digest(yaml.safe_load((OUT / 'configmap.yaml').read_text(encoding='utf-8'))['data']['resident.json']) == preflight['new_resident_sha256']
        subprocess.run(common.K + ['create', '-f', str(OUT / 'configmap.yaml')], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                                   '--patch-file', str(OUT / 'deployment.patch.json')], check=True)
        return
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    original = json.loads(subprocess.check_output(common.K + ['get', 'configmap', OLD_CONFIG, '-o', 'json']))
    data = changed_config(original)
    ops = patch(live)
    cm = dict(apiVersion='v1', kind='ConfigMap',
              metadata=dict(name=NEW_CONFIG, namespace='him-ws'), immutable=True, data=data)
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'configmap.yaml').write_text(yaml.safe_dump(cm, sort_keys=False), encoding='utf-8')
    (OUT / 'deployment.patch.json').write_text(json.dumps(ops, indent=2) + '\n', encoding='utf-8')
    (OUT / 'preflight.json').write_text(json.dumps(dict(
        cause='nr BLAST v5 LMDB mdb_env_open Cannot allocate memory under resident RLIMIT_AS',
        old_virtual_address_limit_bytes=OLD_ADDRESS_LIMIT,
        new_virtual_address_limit_bytes=NEW_ADDRESS_LIMIT,
        worker_pod_physical_memory_limit='8Gi',
        old_resident_sha256=digest(original['data']['resident.json']),
        new_resident_sha256=digest(data['resident.json']),
        deployment_uid=live['metadata']['uid'],
        deployment_resource_version=live['metadata']['resourceVersion'],
        deployment_generation=live['metadata']['generation'],
    ), indent=2) + '\n', encoding='utf-8')
    subprocess.run(common.K + ['create', '--dry-run=server', '-f', str(OUT / 'configmap.yaml')], check=True)
    subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                               '--patch-file', str(OUT / 'deployment.patch.json'),
                               '--dry-run=server', '-o', 'name'], check=True)


if __name__ == '__main__':
    main()
