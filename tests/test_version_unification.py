import base64
import copy
import importlib.util
import io
import json
import json
from pathlib import Path
import sys
import tarfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import version_bundle as bundle
import prepare_version_unification as deploy


@pytest.fixture
def source(tmp_path):
    for name in bundle.PACKAGES:
        folder = tmp_path / 'src' / name
        folder.mkdir(parents=True)
        (folder / '__init__.py').write_bytes(b'# exact\r\n')
    (tmp_path / 'src' / bundle.PACKAGES[0] / 'data.csv').write_bytes(b'asset\r\n')
    return tmp_path / 'src'


def test_deterministic_complete_bundle_and_install(source, tmp_path):
    archive, manifest = bundle.build(source)
    assert bundle.build(source) == (archive, manifest)
    assert len(manifest) == 3
    (tmp_path / 'archive').write_bytes(archive)
    (tmp_path / 'manifest').write_bytes(bundle.encode(manifest))
    target = tmp_path / 'installed'
    bundle.install(tmp_path / 'archive', tmp_path / 'manifest', target, bundle.sha(bundle.encode(manifest)))
    assert bundle.sources(target) == bundle.sources(source)
    with pytest.raises(ValueError, match='empty'):
        bundle.install(tmp_path / 'archive', tmp_path / 'manifest', target, bundle.sha(bundle.encode(manifest)))


@pytest.mark.parametrize('kind', ['traversal', 'symlink', 'duplicate', 'missing', 'corrupt', 'manifest'])
def test_installer_rejects_bad_bundle_before_writing(source, tmp_path, kind):
    files = bundle.sources(source)
    manifest = {name: bundle.sha(raw) for name, raw in files.items()}
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tf:
        for i, (name, raw) in enumerate(files.items()):
            if kind == 'missing' and i == 0:
                continue
            info = tarfile.TarInfo('../escape' if kind == 'traversal' and i == 0 else name)
            info.size = len(raw)
            if kind == 'symlink' and i == 0:
                info.type = tarfile.SYMTYPE
                info.linkname = '/etc/passwd'
            tf.addfile(info, io.BytesIO(b'x' * len(raw) if kind == 'corrupt' and i == 0 else raw))
            if kind == 'duplicate' and i == 0:
                tf.addfile(info, io.BytesIO(raw))
    (tmp_path / 'archive').write_bytes(stream.getvalue())
    (tmp_path / 'manifest').write_bytes(bundle.encode(manifest))
    digest = '0' * 64 if kind == 'manifest' else bundle.sha(bundle.encode(manifest))
    with pytest.raises(ValueError):
        bundle.install(tmp_path / 'archive', tmp_path / 'manifest', tmp_path / 'out', digest)
    assert not (tmp_path / 'out').exists()


def live():
    containers = [dict(name=name, image='registry/image@sha256:' + 'a' * 64,
        args=['unchanged'], securityContext=dict(runAsUser=10001, readOnlyRootFilesystem=True),
        resources=dict(requests=dict(memory='96Gi'), limits=dict(memory='128Gi', gpu=1)),
        volumeMounts=[dict(name='old-code', mountPath='/opt/t01/src/t01_phase1_real/resident_worker.py'),
                      dict(name='data', mountPath='/var/lib/t01')]) for name in ('service', 'worker-structure', 'worker-unified-gpu')]
    return dict(metadata=dict(uid='uid', resourceVersion='42'), spec=dict(replicas=1, strategy=dict(type='Recreate'),
        template=dict(metadata=dict(annotations={'nvidia.com/use-gpuuuid': 'fixed'}),
            spec=dict(containers=containers, volumes=[dict(name='old-code', configMap=dict(name='old')),
                                                      dict(name='data', emptyDir={})]))))


def test_rollout_replaces_whole_packages_and_preserves_operational_config(source):
    before = live()
    saved = copy.deepcopy(before)
    cm, patch, rollback, manifest = deploy.render(before, source)
    assert before == saved
    template = patch[-1]['value']
    assert rollback[0]['value'] == template
    assert rollback[1]['value'] == before['spec']['template']
    assert cm['immutable']
    assert json.loads(base64.b64decode(cm['binaryData']['manifest.json'])) == manifest
    assert not any(v['name'] == 'old-code' for v in template['spec']['volumes'])
    for old, new in zip(before['spec']['template']['spec']['containers'], template['spec']['containers']):
        assert {k:v for k,v in old.items() if k != 'volumeMounts'} == {k:v for k,v in new.items() if k != 'volumeMounts'}
        expected = 4 if new['name'] == 'worker-unified-gpu' else 3 if new['name'] == 'worker-structure' else 4
        assert len([m for m in new['volumeMounts'] if m['name'] == deploy.CODE and m['readOnly']]) == expected
        assert new['volumeMounts'][0] == old['volumeMounts'][1]
    assert template['metadata']['annotations']['nvidia.com/use-gpuuuid'] == 'fixed'


def test_extra_native_paths_and_unused_history_are_detached(source):
    before = live()
    spec = before['spec']['template']['spec']
    spec['volumes'].append(dict(name='stale', configMap=dict(name='historical')))
    spec['containers'][-1]['volumeMounts'].append(dict(name='backend', mountPath='/backend', readOnly=True))
    spec['volumes'].append(dict(name='backend', configMap=dict(name='backend')))
    cm, patch, rollback, manifest = deploy.render(before, source)
    after = patch[-1]['value']['spec']
    assert 'stale' not in {v['name'] for v in after['volumes']}
    assert 'backend' in {v['name'] for v in after['volumes']}
    assert any(m['mountPath']=='/backend/t01_phase1_real' and m['name']==deploy.CODE for m in after['containers'][-1]['volumeMounts'])
    assert any(m['mountPath']=='/code/t01_structure_mapping' and m['name']==deploy.CODE for m in after['containers'][1]['volumeMounts'])
    assert rollback[-1]['value'] == before['spec']['template']


@pytest.mark.parametrize('change', ['init', 'ancestor', 'replicas'])
def test_unreviewed_deployment_rejected(source, change):
    before = live()
    if change == 'init':
        before['spec']['template']['spec']['initContainers'] = [{'name':'existing'}]
    elif change == 'ancestor':
        before['spec']['template']['spec']['containers'][0]['volumeMounts'][0]['mountPath'] = '/opt/t01/src'
    else:
        before['spec']['replicas'] = 2
    with pytest.raises(ValueError):
        deploy.render(before, source)


def test_existing_whole_snapshot_upgrade_changes_only_digest_and_bundle(source):
    before=live();first=deploy.render(before,source)
    before['spec']['template']=first[1][-1]['value'];saved=copy.deepcopy(before)
    (source/bundle.PACKAGES[0]/'new.py').write_bytes(b'# new version\n')
    cm,patch,rollback,manifest=deploy.render(before,source)
    after=copy.deepcopy(patch[-1]['value']);old=before['spec']['template']
    assert after['spec']['containers']==old['spec']['containers']
    assert cm['metadata']['name']!=first[0]['metadata']['name']
    after['metadata']['annotations']=old['metadata']['annotations']
    after['spec']['initContainers'][0]['args']=old['spec']['initContainers'][0]['args']
    next(v for v in after['spec']['volumes'] if v['name']==deploy.BUNDLE)['configMap']=next(v for v in old['spec']['volumes'] if v['name']==deploy.BUNDLE)['configMap']
    assert after==old and before==saved and rollback[-1]['value']==old
    before['spec']['template']['spec']['initContainers'][0]['args'][0]='/unexpected'
    with pytest.raises(ValueError):deploy.render(before,source)


def test_upgrade_repairs_legacy_mounts_without_changing_sources_or_native_settings(source):
    before = live()
    cm, patch, _, _ = deploy.render(before, source)
    before['spec']['template'] = patch[-1]['value']
    for container in before['spec']['template']['spec']['containers'][1:]:
        container['volumeMounts'] += [dict(name=deploy.CODE, mountPath='/app/src/'+p,
                                         subPath=p, readOnly=True) for p in bundle.PACKAGES]
    saved = copy.deepcopy(before)
    new_cm, patch, rollback, _ = deploy.render(before, source)
    assert new_cm == cm and before == saved
    assert rollback[-1]['value'] == saved['spec']['template']
    for old, new in zip(saved['spec']['template']['spec']['containers'], patch[-1]['value']['spec']['containers']):
        if new['name'] == 'service':
            assert new == old
        else:
            expected = copy.deepcopy(old)
            expected['volumeMounts'] = [m for m in expected['volumeMounts'] if not m['mountPath'].startswith('/app/')]
            assert new == expected
            assert any(m['mountPath']=='/opt/t01/src/t01_phase1_real' for m in new['volumeMounts'])


def test_upgrade_refuses_unrecognized_native_alias_mount(source):
    before = live()
    before['spec']['template'] = deploy.render(before, source)[1][-1]['value']
    before['spec']['template']['spec']['containers'][1]['volumeMounts'].append(
        dict(name='user-data', mountPath='/app/models'))
    with pytest.raises(ValueError, match='Unrecognized mount'):
        deploy.render(before, source)


def test_gateway_sized_package_preserves_complete_install_and_upgrade(source, tmp_path):
    import random
    folder = source / bundle.PACKAGES[0]
    (folder/'large.bin').write_bytes(random.Random(9).randbytes(750000))
    for i in range(500):
        (folder/('asset-'+str(i)+'.txt')).write_bytes(str(i).encode())
    before = live()
    cm, patch, rollback, manifest = deploy.render(before, source)
    assert cm['kind'] == 'List' and len(cm['items']) == 2
    assert all(item['immutable'] and len(bundle.encode(item)) < 1024**2 for item in cm['items'])
    files = {}
    for item in cm['items']:
        for name, value in item['binaryData'].items():
            assert name not in files
            files[name] = base64.b64decode(value)
            (tmp_path/name).write_bytes(files[name])
    assert set(files) == {'source.tar.gz','manifest.json','install.py'}
    bundle.install(tmp_path/'source.tar.gz',tmp_path/'manifest.json',tmp_path/'installed',
                   bundle.sha(files['manifest.json']))
    assert bundle.sources(tmp_path/'installed') == bundle.sources(source)
    before['spec']['template'] = patch[-1]['value']
    names = [row['configMap']['name'] for row in next(v for v in before['spec']['template']['spec']['volumes']
             if v['name']==deploy.BUNDLE)['projected']['sources']]
    assert names == [item['metadata']['name'] for item in cm['items']]
    saved = copy.deepcopy(before)
    (folder/'new.py').write_bytes(b'# additional complete version\n')
    new_cm, new_patch, new_rollback, _ = deploy.render(before, source)
    assert new_cm['kind']=='List' and before==saved
    assert new_patch[-1]['value']['spec']['containers'] == before['spec']['template']['spec']['containers']
    assert new_rollback[-1]['value'] == before['spec']['template']
    assert rollback[-1]['value'] == live()['spec']['template']


def test_projected_source_upgrade_rejects_unregistered_metadata_map(source):
    before=live();before['spec']['template']=deploy.render(before,source)[1][-1]['value']
    spec=before['spec']['template']['spec'];digest=before['spec']['template']['metadata']['annotations']['antigen-design/source-sha256']
    index=next(i for i,v in enumerate(spec['volumes']) if v['name']==deploy.BUNDLE)
    spec['volumes'][index]=deploy.bundle_volume(digest,True)
    spec['volumes'][index]['projected']['sources'][1]['configMap']['name']='unregistered'
    with pytest.raises(ValueError,match='Unrecognized source installation'):
        deploy.render(before,source)


@pytest.mark.parametrize('damage', [None, 'missing', 'corrupt', 'traversal', 'reordered', 'manifest'])
def test_chunked_source_installs_exact_bytes_and_rejects_tamper(source, tmp_path, damage):
    import random
    (source / bundle.PACKAGES[0] / 'large.bin').write_bytes(random.Random(19).randbytes(1100000))
    before = live()
    package, patch, _, _ = deploy.render(before, source)
    assert len(package['items']) == 4
    for cm in package['items']:
        assert len(bundle.encode(cm)) < deploy.MAX_CONFIGMAP_REQUEST_BYTES
        for name, value in cm['binaryData'].items(): (tmp_path / name).write_bytes(base64.b64decode(value))
    descriptor_path = tmp_path / 'source.tar.gz.parts.json'
    descriptor = json.loads(descriptor_path.read_bytes())
    if damage == 'missing': (tmp_path / descriptor['parts'][0]['name']).unlink()
    elif damage == 'corrupt':
        path = tmp_path / descriptor['parts'][0]['name']; path.write_bytes(b'x' * path.stat().st_size)
    elif damage == 'traversal': descriptor['parts'][0]['name'] = '../escape'; descriptor_path.write_bytes(bundle.encode(descriptor))
    elif damage == 'reordered': descriptor['parts'].reverse(); descriptor_path.write_bytes(bundle.encode(descriptor))
    digest = bundle.sha((tmp_path / 'manifest.json').read_bytes())
    if damage == 'manifest': digest = '0' * 64
    target = tmp_path / 'installed'
    if damage:
        with pytest.raises((ValueError, OSError)):
            bundle.install(tmp_path / 'source.tar.gz', tmp_path / 'manifest.json', target, digest)
        assert not target.exists()
    else:
        bundle.install(tmp_path / 'source.tar.gz', tmp_path / 'manifest.json', target, digest)
        assert bundle.sources(target) == bundle.sources(source)
        before['spec']['template'] = patch[-1]['value']
        new_package, new_patch, _, _ = deploy.render(before, source)
        assert new_package == package and new_patch[-1]['value'] == before['spec']['template']
