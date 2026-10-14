"""Prepare the immutable r05 same-run and exact GPU environment overlay; dry-run only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from scripts.prepare_esmfold2_backend_r02 import ROOT, encoded, kc


IMAGE = 'harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b'
OLD_CODE = 'antigen-esmfold2-backend-code-r03'
R04_CODE = 'antigen-n12-same-run-code-r04'
R04B_CODE = 'antigen-n12-same-run-code-r04b'
NEW_CODE = 'antigen-n12-same-run-code-r05'
BASE_CODES = (OLD_CODE, R04_CODE, R04B_CODE, NEW_CODE)
# The control-plane image imports the application from /app/src. The older r04
# overlay also left equivalent mounts under /opt/t01/src; those are preserved
# when rebuilding the live mount list, while new imports are overlaid here.
SERVICE_SOURCE_ROOT = '/app/src'
OVERLAY_PATHS = (
    't01_phase1_real/development/runtime.py',
    't01_phase1_real/development/proteinmpnn/source.py',
    't01_phase1_real/development/esm_if1/source.py',
    't01_phase1_real/development/thermompnn/source.py',
    't01_phase1_real/development/foldx/source.py',
    't01_phase1_real/development/supervisor.py',
    't01_phase1_real/development/n12_prediction_evidence.py',
    't01_phase1_real/development/esmfold2/source.py',
    't01_phase1_real/development/esmfold2/standard.py',
)
REQUIRED_PATHS = OVERLAY_PATHS


def _key(path):
    return 'r05-' + path.replace('/', '-').replace('_', '-').replace('.', '-')


def render(deployment, oldcode):
    pod = deployment['spec']['template']['spec']
    containers = {c['name']: i for i, c in enumerate(pod['containers'])}
    service = containers['service']
    service_mounts = copy.deepcopy(pod['containers'][service].get('volumeMounts', []))
    volumes = {v['name']: i for i, v in enumerate(pod['volumes'])}
    volume_index = volumes['esmfold2-code']
    oldvolume = pod['volumes'][volume_index]['configMap']
    if pod['containers'][service]['image'] != IMAGE:
        raise ValueError('Unexpected control image revision')
    base_code = oldvolume['name']
    if base_code not in BASE_CODES:
        raise ValueError('Expected deployed r03, r04, or r05 source ConfigMap')
    if oldcode['metadata']['name'] != base_code or oldcode.get('immutable') is not True:
        raise ValueError('Expected immutable deployed r03/r04/r05 source ConfigMap')

    data = copy.deepcopy(oldcode['data'])
    items = copy.deepcopy(oldvolume['items'])
    by_path = {row['path']: row for row in items}
    for path in OVERLAY_PATHS:
        text = (ROOT / 'src' / path).read_bytes().decode('utf-8')
        row = by_path.get(path)
        if row is None:
            key = _key(path)
            if key in data:
                raise ValueError('Generated ConfigMap key collision: ' + key)
            row = dict(key=key, path=path)
            items.append(row)
            by_path[path] = row
        data[row['key']] = text

    for path in REQUIRED_PATHS:
        row = by_path.get(path)
        if row is None or row['key'] not in data:
            raise ValueError('Required r05 source path is absent: ' + path)
        local = (ROOT / 'src' / path).read_bytes()
        if hashlib.sha256(data[row['key']].encode()).hexdigest() != hashlib.sha256(local).hexdigest():
            raise ValueError('Final ConfigMap source differs from local source: ' + path)

    mount_paths = {row['mountPath'] for row in service_mounts}
    for path in OVERLAY_PATHS:
        target = SERVICE_SOURCE_ROOT + '/' + path
        if target in mount_paths:
            existing = next(row for row in service_mounts if row.get('mountPath') == target)
            if (existing.get('name') != 'esmfold2-code' or existing.get('subPath') != path
                    or existing.get('readOnly') is not True):
                raise ValueError('Service source mount collision: ' + target)
            continue
        service_mounts.append(dict(name='esmfold2-code', mountPath=target,
                                   subPath=path, readOnly=True))
        mount_paths.add(target)

    newvolume = copy.deepcopy(oldvolume)
    newvolume.update(name=NEW_CODE, items=items)
    patch = [
        dict(op='test', path='/metadata/resourceVersion', value=deployment['metadata']['resourceVersion']),
        dict(op='test', path=f'/spec/template/spec/containers/{service}/image', value=IMAGE),
        dict(op='test', path=f'/spec/template/spec/volumes/{volume_index}/configMap', value=oldvolume),
        dict(op='test', path=f'/spec/template/spec/containers/{service}/volumeMounts',
             value=pod['containers'][service].get('volumeMounts', [])),
        dict(op='replace', path=f'/spec/template/spec/volumes/{volume_index}/configMap', value=newvolume),
        dict(op='replace', path=f'/spec/template/spec/containers/{service}/volumeMounts', value=service_mounts),
    ]
    configmap = dict(
        apiVersion='v1',
        kind='ConfigMap',
        metadata=dict(name=NEW_CODE, namespace='him-ws'),
        immutable=True,
        data=data,
    )
    hashes = {p: hashlib.sha256((ROOT / 'src' / p).read_bytes()).hexdigest() for p in REQUIRED_PATHS}
    return configmap, patch, hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError('Use a new output directory')
    deployment = json.loads(kc('get', 'deployment', 'antigen-design', '-o', 'json'))
    if deployment['status'].get('readyReplicas') != 1 or deployment['status'].get('observedGeneration') != deployment['metadata']['generation']:
        raise ValueError('Deployment is not stable')
    volume = next((v for v in deployment['spec']['template']['spec'].get('volumes', [])
                   if v.get('name') == 'esmfold2-code'), None)
    base_code = (volume or {}).get('configMap', {}).get('name')
    if base_code not in BASE_CODES:
        raise ValueError('Expected deployed r03, r04, or r05 source ConfigMap')
    oldcode = json.loads(kc('get', 'configmap', base_code, '-o', 'json'))
    code, patch, hashes = render(deployment, oldcode)
    kc('apply', '--dry-run=server', '-f', '-', data=encoded(code))
    kc('patch', 'deployment', 'antigen-design', '--type=json', '--dry-run=server',
       '-p', json.dumps(patch))
    args.output_dir.mkdir(parents=True)
    for name, value in (
        ('worker-code.json', code),
        ('deployment.patch.json', patch),
        ('deployment.before.json', deployment),
        ('source-hashes.json', hashes),
    ):
        (args.output_dir / name).write_bytes(encoded(value))
    print('N12_SAME_RUN_R05_SERVER_DRY_RUN_PASS', args.output_dir)
    print('No cluster resources were changed.')


if __name__ == '__main__':
    main()
