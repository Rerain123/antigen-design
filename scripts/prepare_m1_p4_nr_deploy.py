"""Prepare the immutable N03 nr code and read-only target PVC mounts for P4."""
import argparse
import base64
import hashlib
import json
import subprocess
import yaml
import prepare_m1_p1_deploy as common

OUT = common.ROOT / 'deploy/m1-p4/nr-r01'
NAME = 'antigen-m1-p4-nr-code-r01'
FILES = ('development/blast/policy.py', 'development/blast/prebuilt.py')
VOLUME = 'n03-nr-target'
SUBPATH = 'nr-20250624/raw'
SERVICE_MOUNT = '/var/lib/t01/m1-p1-test-data/blast/nr-20250624'
WORKER_MOUNT = '/t01/databases/blast/nr-20250624'


def patch(live):
    assert live['spec']['replicas'] == 1 and live['spec']['strategy'] == {'type': 'Recreate'}
    spec = live['spec']['template']['spec']
    assert not any(v['name'] == VOLUME for v in spec['volumes'])
    ops = [dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
           dict(op='test', path='/metadata/uid', value=live['metadata']['uid'])]
    for i, container in enumerate(spec['containers']):
        if container['name'] == 'service':
            mounts = [m for m in container['volumeMounts']
                      if m['mountPath'] not in {'/app/src/t01_phase1_real/' + name for name in FILES}]
            mounts += [dict(name=NAME, mountPath='/app/src/t01_phase1_real/' + name,
                            subPath='p' + str(j), readOnly=True) for j, name in enumerate(FILES)]
            mounts.append(dict(name=VOLUME, mountPath=SERVICE_MOUNT,
                               subPath=SUBPATH, readOnly=True))
            ops.append(dict(op='replace', path=f'/spec/template/spec/containers/{i}/volumeMounts', value=mounts))
        elif container['name'] == 'worker-blast':
            mounts = list(container['volumeMounts'])
            mounts.append(dict(name=VOLUME, mountPath=WORKER_MOUNT,
                               subPath=SUBPATH, readOnly=True))
            ops.append(dict(op='replace', path=f'/spec/template/spec/containers/{i}/volumeMounts', value=mounts))
    assert sum(op['path'].endswith('/volumeMounts') for op in ops) == 2
    volumes = list(spec['volumes'])
    volumes.append(dict(name=NAME, configMap=dict(name=NAME)))
    volumes.append(dict(name=VOLUME, persistentVolumeClaim=dict(claimName='antigen-n03-nr', readOnly=True)))
    ops.append(dict(op='replace', path='/spec/template/spec/volumes', value=volumes))
    return ops


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    idle = common.idle()
    assert not idle['active_jobs'] and idle['gpu_state']['phase'] == 'idle'
    sources = {name: common.ROOT / 'src/t01_phase1_real' / name for name in FILES}
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sources.items()}
    if args.apply:
        assert json.loads((OUT / 'preflight.json').read_bytes())['source_hashes'] == hashes
        subprocess.run(common.K + ['create', '-f', str(OUT / 'configmap.yaml')], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                                   '--patch-file', str(OUT / 'deployment.patch.json')], check=True)
        return
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    ops = patch(live)
    cm = dict(apiVersion='v1', kind='ConfigMap',
              metadata=dict(name=NAME, namespace='him-ws'), immutable=True,
              binaryData={'p' + str(j): base64.b64encode(sources[name].read_bytes()).decode()
                          for j, name in enumerate(FILES)})
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'configmap.yaml').write_text(yaml.safe_dump(cm, sort_keys=False), encoding='utf-8')
    (OUT / 'deployment.patch.json').write_text(json.dumps(ops, indent=2) + '\n', encoding='utf-8')
    (OUT / 'preflight.json').write_text(json.dumps(dict(idle=idle, source_hashes=hashes,
                                                       before_generation=live['metadata']['generation']), indent=2) + '\n', encoding='utf-8')
    subprocess.run(common.K + ['create', '--dry-run=server', '-f', str(OUT / 'configmap.yaml')], check=True)
    subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                               '--patch-file', str(OUT / 'deployment.patch.json'),
                               '--dry-run=server', '-o', 'name'], check=True)


if __name__ == '__main__':
    main()
