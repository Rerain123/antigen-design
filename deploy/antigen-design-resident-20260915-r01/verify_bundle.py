"""Package pinned resident images/assets, or verify a transferred bundle offline.

Build uses Docker only to inspect and save existing images. No registry push,
image rebuild, database approval, extraction, or cluster mutation is performed.
The verify command needs Python 3.11+ and its standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile


ROOT = Path(__file__).resolve().parents[1]
ASSET_PREFIX = 'var/t01-phase1-real/tool-assets/'


def require(value, message):
    if not value:
        raise ValueError(message)


def safe_name(value):
    require(isinstance(value, str) and value and '\\' not in value and ':' not in value,
            'Invalid archive path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(p not in ('', '.', '..') for p in value.split('/')),
            'Archive path escapes root')
    return value


def stream_hash(stream):
    digest = hashlib.sha256()
    count = 0
    while block := stream.read(8 * 1024**2):
        digest.update(block)
        count += len(block)
    return count, digest.hexdigest()


def file_record(path, root):
    require(not path.is_symlink(), 'File symlink rejected')
    with path.open('rb') as stream:
        size, digest = stream_hash(stream)
    return dict(path=path.relative_to(root).as_posix(), bytes=size, sha256=digest)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def asset_inventory(receipts):
    """Use only files named by the accepted original asset receipts."""
    selected = {}
    for tool, value in receipts.items():
        require(value['status'] == 'PASS', 'Unverified asset receipt')
        receipt = value['receipt']
        for entry in receipt.get('files', []) + receipt.get('original_archives', []):
            source = entry['path']
            if tool == 'deeptmhmm':
                source = ASSET_PREFIX + 'deeptmhmm-academic-1.0-0a7a6c5d009e/' + source
            elif tool == 'netmhc':
                source = ASSET_PREFIX + 'netmhc-pinned/' + source
            safe_name(source)
            if not source.startswith(ASSET_PREFIX):
                continue  # Authority/source files are in the control-plane image.
            name = safe_name(source[len(ASSET_PREFIX):])
            row = dict(path=name, source=source, bytes=entry['bytes'], sha256=entry['sha256'],
                       mode=0o755 if name.endswith(('.sh', '/foldx_20270131')) else 0o644)
            require(name not in selected or selected[name] == row, 'Conflicting asset identity')
            selected[name] = row
    require(selected, 'Empty asset inventory')
    return sorted(selected.values(), key=lambda row: row['path'])


def write_assets(path, rows, source_root):
    require(not path.exists(), 'Refusing to overwrite an asset archive')
    with tarfile.open(path, 'x', format=tarfile.PAX_FORMAT) as archive:
        for row in rows:
            source = source_root / row['source']
            require(source.resolve().is_relative_to(source_root.resolve()), 'Asset escapes repository')
            require(not source.is_symlink(), 'Asset symlink rejected')
            actual = file_record(source, source_root)
            require((actual['bytes'], actual['sha256']) == (row['bytes'], row['sha256']),
                    'Source asset changed: ' + row['path'])
            info = tarfile.TarInfo(row['path'])
            info.size = row['bytes']
            info.mode = row['mode']
            info.uid = info.gid = 10001
            info.mtime = 1789430400
            with source.open('rb') as stream:
                archive.addfile(info, stream)


def verify_assets_archive(path, rows):
    expected = {safe_name(row['path']): row for row in rows}
    require(len(expected) == len(rows), 'Duplicate asset inventory')
    seen = set()
    with tarfile.open(path, 'r|*') as archive:
        for member in archive:
            name = safe_name(member.name)
            require(name not in seen and name in expected and member.isfile(), 'Unexpected asset member')
            row = expected[name]
            require(member.size == row['bytes'] and member.mode == row['mode'], 'Asset size/mode changed')
            with archive.extractfile(member) as stream:
                size, digest = stream_hash(stream)
            require(size == row['bytes'] and digest == row['sha256'], 'Asset hash changed: ' + name)
            seen.add(name)
    require(seen == set(expected), 'Missing asset members')
    return dict(files=len(seen), bytes=sum(row['bytes'] for row in rows))


def verify_images_archive(path, images):
    """Bind exported OCI manifests to platform identities observed in Docker."""
    expected = {row['tag']: row.get('export_manifest_digest', row['image_id']) for row in images.values()}
    require(len(expected) == len(images), 'Duplicate image tags')
    entries = {}
    small = {}
    manifest = None
    with tarfile.open(path, 'r|*') as archive:
        for member in archive:
            name = safe_name(member.name.rstrip('/') if member.isdir() else member.name)
            if member.isdir():
                continue
            require(member.isfile() and name not in entries, 'Unexpected image archive member')
            with archive.extractfile(member) as stream:
                if name == 'manifest.json' or name == 'index.json' or member.size <= 1024**2:
                    require(member.size <= 1024**2, 'Oversized Docker manifest')
                    raw = stream.read()
                    small[name] = raw
                    if name == 'manifest.json':
                        manifest = json.loads(raw)
                    size, digest = len(raw), hashlib.sha256(raw).hexdigest()
                else:
                    size, digest = stream_hash(stream)
            require(size == member.size, 'Truncated image member')
            if name.startswith('blobs/sha256/'):
                require(name == 'blobs/sha256/' + digest, 'Image blob hash mismatch')
            entries[name] = dict(bytes=size, sha256=digest)
    require(isinstance(manifest, list) and len(manifest) == len(images), 'Unexpected image manifest')
    observed = {}
    for row in manifest:
        config = entries[safe_name(row['Config'])]
        require(row['Layers'] and all(safe_name(layer) in entries for layer in row['Layers']),
                'Missing image layer')
        for tag in row['RepoTags']:
            require(tag not in observed, 'Duplicate exported tag')
            observed[tag] = 'sha256:' + config['sha256']
    configurations = observed
    if any('export_manifest_digest' in row for row in images.values()):
        require(all('export_manifest_digest' in row for row in images.values()), 'Mixed image identity records')
        require('index.json' in small, 'OCI index required for platform export')
        index = json.loads(small['index.json'])
        require(index['schemaVersion'] == 2 and len(index['manifests']) == len(images), 'Invalid OCI index')
        def descriptor(value):
            digest = value['digest']
            require(re.fullmatch(r'sha256:[0-9a-f]{64}', digest), 'Invalid OCI digest')
            name = 'blobs/sha256/' + digest[7:]
            require(name in entries and entries[name]['sha256'] == digest[7:]
                    and entries[name]['bytes'] == value['size'], 'OCI descriptor mismatch')
            return name
        observed = {}
        docker_rows = {tag: row for row in manifest for tag in row['RepoTags']}
        for entry in index['manifests']:
            name = descriptor(entry)
            require(entry['platform']['os'] == 'linux' and entry['platform']['architecture'] == 'amd64',
                    'Unexpected image platform')
            tag = entry['annotations']['io.containerd.image.name']
            if tag.startswith('docker.io/library/'):
                tag = tag[len('docker.io/library/'):]
            require(tag in expected and tag not in observed, 'Unexpected OCI image tag')
            native = json.loads(small[name])
            config_name = descriptor(native['config'])
            layers = [descriptor(layer) for layer in native['layers']]
            require(native['schemaVersion'] == 2 and config_name == docker_rows[tag]['Config']
                    and layers == docker_rows[tag]['Layers'], 'Docker and OCI manifest disagree')
            config = json.loads(small[config_name])
            require(config['architecture'] == 'amd64' and config['os'] == 'linux', 'Unexpected config platform')
            observed[tag] = entry['digest']
    require(observed == expected, 'Exported images differ from accepted image IDs/tags')
    return dict(images=len(manifest), members=len(entries), tags=observed, configuration_ids=configurations)


def mount_plan(images, asset_bytes):
    return dict(schema_version='0.1.0', status='PROPOSED_NOT_APPLIED', namespace='him-ws',
        deployment='antigen-design', topology='one control container and nine resident workers in one Pod',
        reason='Existing RWO runtime claim must remain on one node; one GPU worker serializes three tools.',
        runtime=dict(claim='antigen-design-runtime', observed_capacity='20Gi', mount='/var/lib/t01',
                     access='read-write', uid=10001, gid=10001),
        assets=dict(proposed_claim='antigen-design-assets', proposed_capacity='20Gi',
                    proposed_storage_class='ceph-rbd', created=False, bytes=asset_bytes,
                    archive='assets/tool-assets.tar', extract_into='asset PVC root',
                    control_mount='/app/var/t01-phase1-real/tool-assets', worker_mount='/t01/assets',
                    access='read-only', directories_are_archive_roots=True),
        control_configuration=dict(file='configuration/controller.json',
                    container_path='/etc/t01/resident.json',
                    environment={'T01_RESIDENT_CONFIG_FILE':'/etc/t01/resident.json'},
                    newer_control_image_required=True),
        workers={group:dict(image_id=row['image_id'], local_tag=row['tag'],
                    registry_manifest_digest=None, root='/var/lib/t01/resident/'+group,
                    temporary_mount='/run/t01-slot', temporary_mount_scope='one container',
                    config='/opt/t01/worker.json', gpu_count=1 if group=='gpu' else 0,
                    gpu_resource_key=None if group=='gpu' else 'not-applicable')
                    for group,row in images.items()},
        databases={tool:dict(registered=False, mount='/t01/databases/'+tool)
                   for tool in ('blast','homology','domains')},
        pending=['registry upload endpoint and pushed manifest digests',
                 'asset PVC creation and upload', 'GPU resource name and node capacity',
                 'N10 A3D resident business integration', 'updated control image and HiMat integration'],
        exclusions=['AF3', 'ESMFold2', 'unregistered scientific databases', 'secrets', 'runtime jobs'],
        no_kubernetes_job_api=True, apply_ready=False)


def verify(bundle):
    manifest = json.loads((bundle / 'bundle.json').read_bytes())
    require(manifest['schema_version'] == '0.1.0', 'Unsupported bundle')
    seen = set()
    for row in manifest['files']:
        name = safe_name(row['path'])
        require(name not in seen, 'Duplicate bundle entry')
        seen.add(name)
        path = bundle / name
        require(path.resolve().is_relative_to(bundle.resolve()), 'Bundle path escapes root')
        actual = file_record(path, bundle)
        require(actual == row, 'Bundle hash mismatch: ' + name)
    images = json.loads((bundle / 'metadata/images.json').read_bytes())['built']
    assets = json.loads((bundle / 'metadata/assets.json').read_bytes())['files']
    require({'images/workers-linux-amd64.tar', 'assets/tool-assets.tar',
             'metadata/images.json', 'metadata/assets.json'} <= seen, 'Bundle inventory is incomplete')
    return dict(status='PASS', scientific_workflow_verified=False, deployed=False,
                images=verify_images_archive(bundle / 'images/workers-linux-amd64.tar', images),
                assets=verify_assets_archive(bundle / 'assets/tool-assets.tar', assets))


def build(assembly, output, docker, resume=False):
    require(not output.exists() or resume, 'Use a new output directory or explicitly resume an unfinished export')
    require(not (output/'bundle.json').exists(), 'Completed bundles are not overwritten')
    # Read-only validation of the accepted step-1 archive, before exporting anything.
    index = json.loads((assembly / 'index.json').read_bytes())
    for row in index['files']:
        path = assembly / safe_name(row['path'])
        require(file_record(path, assembly) == row, 'Step-1 evidence changed')
    images = json.loads((assembly / 'images.json').read_bytes())
    receipts = json.loads((assembly / 'assets.json').read_bytes())
    rows = asset_inventory(receipts)
    if resume:
        previous = json.loads((output/'metadata/images.json').read_bytes())
        for group, row in images['built'].items():
            require(all(previous['built'][group].get(k) == v for k,v in row.items()), 'Resume image identity changed')
        require(json.loads((output/'configuration/controller.json').read_bytes()) ==
                json.loads((assembly/'controller.json').read_bytes()), 'Resume controller configuration changed')
    for group,row in images['built'].items():
        actual = json.loads(subprocess.check_output([docker,'image','inspect',row['tag']]))[0]
        require(actual['Id'] == row['image_id'] and actual['Os']=='linux' and actual['Architecture']=='amd64',
                'Accepted image changed: ' + group)
        platform = json.loads(subprocess.check_output([docker,'image','inspect','--platform','linux/amd64',row['tag']]))[0]
        require(platform['Descriptor']['mediaType'] == 'application/vnd.oci.image.manifest.v1+json'
                and platform['Descriptor']['digest'] == platform['Id'], 'Expected OCI platform manifest')
        # --platform selects a platform manifest; default inspection can return its parent index.
        row['export_manifest_digest'] = platform['Id']
        require(json.loads(subprocess.check_output([docker,'image','inspect',row['tag']]))[0]['Id'] == row['image_id'],
                'Image tag changed during platform inspection')
    required = sum(row['bytes'] for row in rows) + sum(
        json.loads(subprocess.check_output([docker,'image','inspect',row['tag']]))[0]['Size']
        for row in images['built'].values()) + 5 * 1024**3
    require(shutil.disk_usage(output.parent).free > required, 'Insufficient destination disk space')
    output.mkdir(exist_ok=resume)
    for name in ('images','assets','metadata','configuration'):
        (output/name).mkdir(exist_ok=resume)
    write_json(output/'metadata/images.json', images)
    shutil.copyfile(assembly/'assets.json', output/'metadata/original-asset-receipts.json')
    shutil.copyfile(assembly/'controller.json', output/'configuration/controller.json')
    for path in (assembly/'configuration').glob('*.worker.json'):
        shutil.copyfile(path, output/'configuration'/path.name)
    write_json(output/'metadata/assets.json', dict(files=rows, file_count=len(rows)))
    write_json(output/'configuration/mount-plan.json', mount_plan(images['built'], sum(r['bytes'] for r in rows)))
    shutil.copyfile(Path(__file__), output/'verify_bundle.py')
    print('Exporting nine existing images into one archive on destination drive...', flush=True)
    partial = output/'images/workers-linux-amd64.tar.partial'
    final_image = output/'images/workers-linux-amd64.tar'
    if not partial.exists() and not final_image.exists():
        with (output/'metadata/docker-save.log').open('wb') as log:
            done = subprocess.run([docker,'image','save','--platform','linux/amd64','--output',str(partial),
                                   *[row['tag'] for row in images['built'].values()]], stdout=log,stderr=subprocess.STDOUT)
        require(done.returncode == 0, 'Docker save failed; partial archive retained for diagnosis')
    else:
        require(resume, 'Existing image export requires explicit resume')
        print('Verifying existing image export; no second large export...', flush=True)
    exported = verify_images_archive(final_image if final_image.exists() else partial, images['built'])
    if not final_image.exists():
        partial.rename(final_image)
    write_json(output/'metadata/image-export-verification.json', exported)
    print('Images exported and checked; packing',len(rows),'pinned asset files...', flush=True)
    partial = output/'assets/tool-assets.tar.partial'
    final_assets = output/'assets/tool-assets.tar'
    if not final_assets.exists():
        write_assets(partial, rows, ROOT)
        checked = verify_assets_archive(partial, rows)
        partial.rename(final_assets)
    else:
        checked = verify_assets_archive(final_assets, rows)
    write_json(output/'metadata/asset-export-verification.json', checked)
    files = [file_record(p, output) for p in sorted(output.rglob('*')) if p.is_file()]
    write_json(output/'bundle.json',dict(schema_version='0.1.0', status='PACKAGED_NOT_UPLOADED',
               source_assembly=str(assembly), source_index_sha256=file_record(assembly/'index.json',assembly)['sha256'],
               deployed=False, scientific_gate='CLOSED', files=files))
    (output/'SHA256SUMS').write_text(''.join(f"{r['sha256']}  {r['path']}\n" for r in files)+
        file_record(output/'bundle.json',output)['sha256']+'  bundle.json\n', encoding='utf-8')
    print(json.dumps(dict(status='PACKAGED_NOT_UPLOADED', files=len(files),
                         total_bytes=sum(r['bytes'] for r in files), output=str(output))), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    pack = sub.add_parser('build')
    pack.add_argument('--assembly',type=Path,required=True)
    pack.add_argument('--output',type=Path,required=True)
    pack.add_argument('--docker',default='docker')
    pack.add_argument('--resume',action='store_true',help='Validate and reuse an unfinished export; never overwrite a completed bundle')
    check = sub.add_parser('verify')
    check.add_argument('bundle',type=Path)
    args = parser.parse_args()
    if args.command=='build':
        build(args.assembly.absolute(),args.output.absolute(),args.docker,args.resume)
    else:
        print(json.dumps(verify(args.bundle.absolute()),indent=2))


if __name__=='__main__':
    main()
