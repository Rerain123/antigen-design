import hashlib
import io
import json
import tarfile

import pytest

from scripts import resident_bundle as bundle


def add(archive, name, raw, mode=0o644):
    member = tarfile.TarInfo(name)
    member.size = len(raw)
    member.mode = mode
    archive.addfile(member, io.BytesIO(raw))


@pytest.mark.parametrize('name', ['../escape', '/tmp/x', 'a/../b', 'a\\b', 'D:/file', 'a//b'])
def test_unsafe_archive_path_is_rejected(name):
    with pytest.raises(ValueError):
        bundle.safe_name(name)


def test_assets_roundtrip_checks_bytes_modes_and_original_identity(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    raw = b'native executable placeholder'
    (source/'foldx').write_bytes(raw)
    row = dict(path='foldx/foldx_20270131',source='foldx',bytes=len(raw),
               sha256=hashlib.sha256(raw).hexdigest(),mode=0o755)
    target = tmp_path/'assets.tar'
    bundle.write_assets(target, [row], source)
    assert bundle.verify_assets_archive(target, [row])['files']==1
    with pytest.raises(ValueError, match='size/mode'):
        bundle.verify_assets_archive(target, [dict(row,mode=0o644)])
    with pytest.raises(ValueError, match='hash changed'):
        bundle.verify_assets_archive(target, [dict(row,sha256='0'*64)])
    (source/'foldx').write_bytes(b'changed')
    with pytest.raises(ValueError, match='Source asset changed'):
        bundle.write_assets(tmp_path/'changed.tar', [row], source)


@pytest.mark.parametrize('kind', ['symlink','duplicate','unlisted'])
def test_asset_archive_rejects_links_duplicates_and_unlisted_files(tmp_path, kind):
    path=tmp_path/'assets.tar'
    row=dict(path='approved',bytes=1,sha256=hashlib.sha256(b'x').hexdigest(),mode=0o644)
    with tarfile.open(path,'w') as archive:
        if kind=='symlink':
            member=tarfile.TarInfo('approved');member.type=tarfile.SYMTYPE;member.linkname='/etc/passwd'
            archive.addfile(member)
        else:
            add(archive,'approved',b'x')
            add(archive,'approved' if kind=='duplicate' else 'other',b'x')
    with pytest.raises(ValueError):
        bundle.verify_assets_archive(path,[row])


@pytest.mark.parametrize('damage', ['none','config','layer','tag','missing'])
def test_docker_export_binds_tags_configs_and_blob_hashes(tmp_path,damage):
    config=b'{"architecture":"amd64","os":"linux"}'
    layer=b'layer content'
    config_hash=hashlib.sha256(config).hexdigest()
    config_name='blobs/sha256/'+config_hash
    layer_name='blobs/sha256/'+hashlib.sha256(layer).hexdigest()
    path=tmp_path/'images.tar'
    expected={'structure':dict(tag='worker:test',image_id='sha256:'+config_hash)}
    with tarfile.open(path,'w') as archive:
        add(archive,config_name,b'changed' if damage=='config' else config)
        if damage!='missing':add(archive,layer_name,b'changed' if damage=='layer' else layer)
        add(archive,'manifest.json',json.dumps([dict(Config=config_name,Layers=[layer_name],
            RepoTags=['other:test' if damage=='tag' else 'worker:test'])]).encode())
    if damage=='none':
        assert bundle.verify_images_archive(path,expected)['images']==1
    else:
        with pytest.raises(ValueError):bundle.verify_images_archive(path,expected)


def test_mount_plan_keeps_gpu_single_and_site_unknowns_explicit():
    plan=bundle.mount_plan({'gpu':dict(tag='gpu:test',image_id='sha256:'+'a'*64)},123)
    assert not plan['apply_ready'] and not plan['assets']['created']
    assert plan['workers']['gpu']['gpu_count']==1
    assert plan['workers']['gpu']['gpu_resource_key'] is None
    assert plan['workers']['gpu']['registry_manifest_digest'] is None
    assert plan['runtime']['claim']=='antigen-design-runtime'
    assert not any(v['registered'] for v in plan['databases'].values())


@pytest.mark.parametrize('damage', ['none','platform','descriptor_size','manifest_digest','config_binding','layer_binding'])
def test_oci_platform_export_is_bound_to_observed_manifest(tmp_path, damage):
    raw_config=b'{"architecture":"amd64","os":"linux"}'
    raw_layer=b'layer'
    def descriptor(raw):
        return dict(digest='sha256:'+hashlib.sha256(raw).hexdigest(),size=len(raw))
    def path(d):return 'blobs/sha256/'+d['digest'][7:]
    config=descriptor(raw_config);layer=descriptor(raw_layer)
    raw_manifest=json.dumps(dict(schemaVersion=2,config=config,layers=[layer])).encode()
    native=descriptor(raw_manifest)
    expected={'group':dict(tag='worker:test',image_id='sha256:'+'a'*64,
                          export_manifest_digest=native['digest'])}
    if damage=='manifest_digest':expected['group']['export_manifest_digest']='sha256:'+'b'*64
    index_entry=dict(native, platform=dict(os='linux',architecture='arm64' if damage=='platform' else 'amd64'),
                     annotations={'io.containerd.image.name':'docker.io/library/worker:test'})
    if damage=='descriptor_size':index_entry['size']+=1
    docker_manifest=[dict(RepoTags=['worker:test'],Config=path(layer) if damage=='config_binding' else path(config),
                          Layers=[path(config)] if damage=='layer_binding' else [path(layer)])]
    target=tmp_path/'oci.tar'
    with tarfile.open(target,'w') as archive:
        add(archive,path(config),raw_config)
        add(archive,path(layer),raw_layer)
        add(archive,path(native),raw_manifest)
        add(archive,'index.json',json.dumps(dict(schemaVersion=2,manifests=[index_entry])).encode())
        add(archive,'manifest.json',json.dumps(docker_manifest).encode())
    if damage=='none':
        observed=bundle.verify_images_archive(target,expected)
        assert observed['tags']['worker:test']==native['digest']
        assert observed['configuration_ids']['worker:test']==config['digest']
    else:
        with pytest.raises(ValueError):bundle.verify_images_archive(target,expected)


def test_completed_bundle_cannot_be_resumed(tmp_path):
    (tmp_path/'bundle.json').write_text('{}')
    with pytest.raises(ValueError,match='Completed bundles'):
        bundle.build(tmp_path,tmp_path,'unused',resume=True)
