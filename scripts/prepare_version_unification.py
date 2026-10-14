"""Unify complete project packages, preserving native environments and resources."""
import argparse
import base64
import copy
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import prepare_m1_p1_deploy as common
from version_bundle import PACKAGES, build, encode, sha

OUT = common.ROOT / 'deploy/version-unification/r01'
EVIDENCE = common.ROOT / 'reports/version-unification-20260927'
BUNDLE = 'project-source-bundle'
CODE = 'project-source'
MAX_CONFIGMAP_REQUEST_BYTES = 1024 ** 2


def bundle_volume(digest, split=False):
    name = 'antigen-source-' + digest[:16]
    if split:
        names = [name] + ([name + '-part' + str(i) for i in range(1, split)] if type(split) is int else []) + [name + '-meta']
        return dict(name=BUNDLE, projected=dict(defaultMode=292,
            sources=[dict(configMap=dict(name=n)) for n in names]))
    return dict(name=BUNDLE, configMap=dict(name=name, defaultMode=292))


def request_package(cm):
    """Keep each API request below the gateway limit without omitting assets."""
    if len(encode(cm)) < MAX_CONFIGMAP_REQUEST_BYTES:
        return cm, False
    archive = copy.deepcopy(cm)
    metadata = copy.deepcopy(cm)
    archive['binaryData'] = {'source.tar.gz': cm['binaryData']['source.tar.gz']}
    metadata['metadata']['name'] += '-meta'
    metadata['binaryData'] = {key:value for key,value in cm['binaryData'].items() if key != 'source.tar.gz'}
    if len(encode(metadata)) >= MAX_CONFIGMAP_REQUEST_BYTES:
        raise ValueError('Source metadata exceeds a single gateway request')
    if len(encode(archive)) < MAX_CONFIGMAP_REQUEST_BYTES:
        return dict(apiVersion='v1', kind='List', items=[archive, metadata]), True
    raw = base64.b64decode(cm['binaryData']['source.tar.gz'], validate=True)
    chunks = [raw[i:i + 512 * 1024] for i in range(0, len(raw), 512 * 1024)]
    if not 2 <= len(chunks) <= 32:
        raise ValueError('Source archive chunk count exceeds bound')
    items, records = [], []
    for i, chunk in enumerate(chunks):
        item = copy.deepcopy(archive)
        if i: item['metadata']['name'] += '-part' + str(i)
        key = 'source.tar.gz.part' + str(i)
        item['binaryData'] = {key: base64.b64encode(chunk).decode()}
        items.append(item)
        records.append(dict(name=key, size_bytes=len(chunk), sha256=sha(chunk)))
    descriptor = encode(dict(version=1, sha256=sha(raw), parts=records))
    metadata['binaryData']['source.tar.gz.parts.json'] = base64.b64encode(descriptor).decode()
    items.append(metadata)
    if any(len(encode(item)) >= MAX_CONFIGMAP_REQUEST_BYTES for item in items):
        raise ValueError('Chunked source request exceeds gateway limit')
    return dict(apiVersion='v1', kind='List', items=items), len(chunks)


def detach_native_alias_mounts(spec):
    """/app is a per-execution model alias in resident images, never source storage."""
    for container in spec['containers']:
        if container['name'] == 'service':
            continue
        if not container['name'].startswith('worker-'):
            raise ValueError('Unknown container source layout')
        kept = []
        for mount in container.get('volumeMounts', []):
            path = mount['mountPath']
            if path == '/app' or path.startswith('/app/'):
                if not (path in ['/app/src/' + p for p in PACKAGES]
                        and mount == dict(name=CODE, mountPath=path,
                                          subPath=path.rsplit('/', 1)[1], readOnly=True)):
                    raise ValueError('Unrecognized mount beneath native /app alias')
            else:
                kept.append(mount)
        container['volumeMounts'] = kept


def render(live, source_root=common.ROOT / 'src'):
    if live['spec']['replicas'] != 1 or live['spec']['strategy'] != {'type': 'Recreate'}:
        raise ValueError('Expected singleton Recreate')
    archive, manifest = build(source_root)
    digest = sha(encode(manifest))
    name = 'antigen-source-' + digest[:16]
    installer = Path(__file__).with_name('version_bundle.py').read_bytes()
    cm = dict(apiVersion='v1', kind='ConfigMap', metadata=dict(name=name, namespace='him-ws'),
              immutable=True, binaryData={k: base64.b64encode(v).decode() for k, v in
                {'source.tar.gz': archive, 'manifest.json': encode(manifest), 'install.py': installer}.items()})
    cm, split = request_package(cm)
    original = live['spec']['template']
    template = copy.deepcopy(original)
    spec = template['spec']
    if spec.get('initContainers'):
        initializers = spec['initContainers']
        old_digest = original.get('metadata', {}).get('annotations', {}).get('antigen-design/source-sha256', '')
        volumes = {v['name']:v for v in spec['volumes']}
        if (len(initializers) != 1 or initializers[0].get('name') != 'install-project-source'
                or initializers[0].get('command') != ['python', '-B', '/bundle/install.py']
                or len(old_digest) != 64 or any(c not in '0123456789abcdef' for c in old_digest)
                or initializers[0].get('args') != ['/bundle/source.tar.gz', '/bundle/manifest.json', '/source', old_digest]
                or volumes.get(CODE) != dict(name=CODE, emptyDir=dict(sizeLimit='16Mi'))
                or volumes.get(BUNDLE) not in ([bundle_volume(old_digest), bundle_volume(old_digest, True)]
                    + [bundle_volume(old_digest, count) for count in range(2, 33)])):
            raise ValueError('Unrecognized source installation; review before upgrading')
        initializers[0]['args'][-1] = digest
        volume_index = next(i for i,v in enumerate(spec['volumes']) if v['name'] == BUNDLE)
        spec['volumes'][volume_index] = bundle_volume(digest, split)
        template['metadata']['annotations']['antigen-design/source-sha256'] = digest
        detach_native_alias_mounts(spec)
        patch = [dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
                 dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
                 dict(op='replace', path='/spec/template', value=template)]
        rollback = [dict(op='test', path='/spec/template', value=template),
                    dict(op='replace', path='/spec/template', value=original)]
        return cm, patch, rollback, manifest
    roots = [root + '/' + package for root in ('/app/src', '/opt/t01/src') for package in PACKAGES]
    removed = set()
    for container in spec['containers']:
        container_roots = roots + (['/backend/' + package for package in PACKAGES]
                                   if container['name'] == 'worker-unified-gpu' else [])
        if container['name'] == 'worker-structure':
            container_roots += ['/code/t01_structure_mapping']
        mounts = []
        for mount in container.get('volumeMounts', []):
            path = mount['mountPath']
            if any(path == root or path.startswith(root + '/') for root in container_roots):
                removed.add(mount['name'])
            elif any(root.startswith(path.rstrip('/') + '/') for root in roots):
                raise ValueError('Ancestor mount requires explicit compatibility review')
            else:
                mounts.append(mount)
        mounts += [dict(name=CODE, mountPath=root, subPath=root.rsplit('/', 1)[1], readOnly=True)
                   for root in container_roots]
        container['volumeMounts'] = mounts
    detach_native_alias_mounts(spec)
    used = {m['name'] for c in spec['containers'] for m in c['volumeMounts']}
    used.update(m['name'] for c in spec['containers'] for m in c.get('volumeDevices', []))
    # Detach unused historical references; original ConfigMaps/PVCs are retained for rollback.
    spec['volumes'] = [v for v in spec['volumes'] if v['name'] in used]
    if any(v['name'] in (CODE, BUNDLE) for v in spec['volumes']):
        raise ValueError('Source bundle already installed; prepare a fresh upgrade path')
    spec['volumes'] += [dict(name=CODE, emptyDir=dict(sizeLimit='16Mi')),
                        bundle_volume(digest, split)]
    service = next(c for c in spec['containers'] if c['name'] == 'service')
    spec['initContainers'] = [dict(name='install-project-source', image=service['image'],
        imagePullPolicy=service.get('imagePullPolicy', 'IfNotPresent'),
        terminationMessagePath='/dev/termination-log', terminationMessagePolicy='File',
        command=['python', '-B', '/bundle/install.py'],
        args=['/bundle/source.tar.gz', '/bundle/manifest.json', '/source', digest],
        securityContext=copy.deepcopy(service['securityContext']),
        resources=dict(requests=dict(cpu='100m', memory='64Mi'), limits=dict(cpu='500m', memory='128Mi')),
        volumeMounts=[dict(name=BUNDLE, mountPath='/bundle', readOnly=True),
                      dict(name=CODE, mountPath='/source')])]
    template.setdefault('metadata', {}).setdefault('annotations', {})['antigen-design/source-sha256'] = digest
    patch = [dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
             dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
             dict(op='replace', path='/spec/template', value=template)]
    rollback = [dict(op='test', path='/spec/template', value=template),
                dict(op='replace', path='/spec/template', value=original)]
    return cm, patch, rollback, manifest


def idle():
    state = common.idle()
    if state['active_jobs'] or not state['gpu_state'] or state['gpu_state']['phase'] != 'idle':
        raise RuntimeError('Deployment requires idle service and GPU')
    return state


def regression():
    latest = {}
    receipts = ('full.junit.xml', 'order-recheck.junit.xml')
    for name in receipts:
        for case in ET.parse(EVIDENCE / name).iter('testcase'):
            latest[(case.get('classname'), case.get('name'))] = case
    cases = list(latest.values())
    if len(cases) < 2500 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Complete current-root regression must pass')
    linux = list(ET.parse(EVIDENCE / 'linux-executors-final.junit.xml').iter('testcase'))
    if len(linux) < 43 or any(any(c.find(s) is not None for s in ('failure','error','skipped')) for c in linux):
        raise RuntimeError('Real Linux executor regression must pass')
    return dict(total=len(cases), skipped=sum(c.find('skipped') is not None for c in cases),
                linux_passed=len(linux), method='full run plus exact-order isolation fix recheck',
                receipts={n:sha((EVIDENCE/n).read_bytes()) for n in (*receipts,'linux-executors-final.junit.xml')})


def compatibility(manifest):
    rows = json.loads((EVIDENCE / 'predeploy-imports.json').read_bytes())
    digest = sha(encode(manifest))
    if len(rows) != 10 or any(r['status'] != 'PASS' or r['source_sha256'] != digest for r in rows):
        raise RuntimeError('All ten container compatibility checks must match the source bundle')
    frozen = json.loads((EVIDENCE / 'frozen.json').read_bytes())
    if frozen['status'] != 'PASS':
        raise RuntimeError('Frozen assets must verify')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    state = idle()
    if args.apply:
        pre = json.loads((OUT / 'preflight.json').read_bytes())
        if build(common.ROOT / 'src')[1] != pre['source_hashes']:
            raise RuntimeError('Local sources changed since preparation')
        compatibility(pre['source_hashes'])
        for name, digest in pre['artifacts'].items():
            if sha((OUT / name).read_bytes()) != digest:
                raise RuntimeError('Prepared artifacts changed')
        checks = regression()
        if checks != pre['regression']:
            raise RuntimeError('Regression receipt changed')
        subprocess.run(common.K + ['create', '-f', str(OUT / 'configmap.json')], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
                       '--patch-file', str(OUT / 'deployment.patch.json')], check=True)
        print('VERSION_UNIFICATION_SUBMITTED')
        return
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    cm, patch, rollback, manifest = render(live)
    compatibility(manifest)
    OUT.mkdir(parents=True, exist_ok=False)
    artifacts = {'configmap.json': cm, 'deployment.patch.json': patch, 'rollback.patch.json': rollback}
    for name, value in artifacts.items():
        (OUT / name).write_bytes(encode(value) + b'\n')
    checks = regression()
    for command in (['create', '-f', str(OUT / 'configmap.json')],
                    ['patch', 'deployment', 'antigen-design', '--type=json', '--patch-file', str(OUT / 'deployment.patch.json')]):
        subprocess.run(common.K + command + ['--dry-run=server', '-o', 'name'], check=True)
    pre = dict(status='PREPARED', before_generation=live['metadata']['generation'], idle=state,
               source_hashes=manifest, source_sha256=sha(encode(manifest)), regression=checks,
               artifacts={name: sha((OUT / name).read_bytes()) for name in artifacts})
    (OUT / 'preflight.json').write_bytes(encode(pre) + b'\n')
    print(json.dumps(dict(status='PREPARED', source_sha256=pre['source_sha256'], files=len(manifest))))


if __name__ == '__main__':
    main()
