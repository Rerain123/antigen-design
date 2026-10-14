"""Prepare an immutable N03 target-database policy code refresh."""
import argparse
import base64
import hashlib
import json
import subprocess

import yaml

import prepare_m1_p1_deploy as common


OUT = common.ROOT / 'deploy/m1-p4/nr-r02'
OLD_NAME = 'antigen-m1-p4-nr-code-r01'
NAME = 'antigen-m1-p4-nr-code-r02'
FILES = ('development/blast/policy.py', 'development/blast/prebuilt.py')


def patch(live):
    assert live['spec']['replicas'] == 1 and live['spec']['strategy'] == {'type': 'Recreate'}
    spec = live['spec']['template']['spec']
    matches = [v for v in spec['volumes'] if v['name'] == OLD_NAME]
    assert len(matches) == 1 and matches[0].get('configMap', {}).get('name') == OLD_NAME
    assert not any(v['name'] == NAME for v in spec['volumes'])
    index = next(i for i, v in enumerate(spec['volumes']) if v['name'] == OLD_NAME)
    return [
        dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
        dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
        dict(op='replace', path=f'/spec/template/spec/volumes/{index}/configMap/name', value=NAME),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    idle = common.idle()
    assert not idle['active_jobs'] and idle['gpu_state']['phase'] == 'idle'
    sources = {name: common.ROOT / 'src/t01_phase1_real' / name for name in FILES}
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sources.items()}
    if args.apply:
        preflight = json.loads((OUT / 'preflight.json').read_bytes())
        assert preflight['source_hashes'] == hashes
        subprocess.run(common.K + ['create', '-f', str(OUT / 'configmap.yaml')], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                                   '--patch-file', str(OUT / 'deployment.patch.json')], check=True)
        return
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    operations = patch(live)
    cm = dict(apiVersion='v1', kind='ConfigMap',
              metadata=dict(name=NAME, namespace='him-ws'), immutable=True,
              binaryData={'p' + str(j): base64.b64encode(sources[name].read_bytes()).decode()
                          for j, name in enumerate(FILES)})
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'configmap.yaml').write_text(yaml.safe_dump(cm, sort_keys=False), encoding='utf-8')
    (OUT / 'deployment.patch.json').write_text(json.dumps(operations, indent=2) + '\n', encoding='utf-8')
    (OUT / 'preflight.json').write_text(json.dumps(dict(
        reason='Reuse verified target nr receipt and allow native BLAST up to 7200 seconds',
        idle=idle, source_hashes=hashes, before_generation=live['metadata']['generation'],
        old_configmap=OLD_NAME, new_configmap=NAME), indent=2) + '\n', encoding='utf-8')
    subprocess.run(common.K + ['create', '--dry-run=server', '-f', str(OUT / 'configmap.yaml')], check=True)
    subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                               '--patch-file', str(OUT / 'deployment.patch.json'),
                               '--dry-run=server', '-o', 'name'], check=True)


if __name__ == '__main__':
    main()
