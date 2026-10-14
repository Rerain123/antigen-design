"""User-run installation of the verified ESMFold2 environment on its existing PVC."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import time

ENVIRONMENT = '/models/esmfold2-environment-20260916-r01'
MANIFEST_HASH = 'c719aade5db1dacf747cf1f882061a132558ae359bc5a5dd58fc1f5c955bab39'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def relative(value):
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or not p.parts or '\\' in value:
        raise ValueError('Unsafe relative path: ' + value)
    return p


def checked_path(root, value):
    p = relative(value)
    target = root
    for part in p.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError('Symlink in environment path: ' + value)
    return target


def verify_tree(root, rows):
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in installed environment')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != set(rows):
        raise ValueError('Environment file set mismatch')
    last = time.monotonic()
    for count, (name, row) in enumerate(rows.items(), 1):
        path = checked_path(root, name)
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Installed file integrity mismatch: ' + name)
        if time.monotonic() - last >= 30:
            print('ENVIRONMENT_VERIFY_PROGRESS', count, len(rows), flush=True)
            last = time.monotonic()


def unpack(archive, staging, rows):
    seen = set()
    last = time.monotonic()
    with tarfile.open(archive, mode='r|gz') as source:
        for member in source:
            p = relative(member.name)
            if p.parts[0] != 'site-packages':
                raise ValueError('Archive outside site-packages')
            target = checked_path(staging, p.as_posix())
            if member.isdir():
                # The source archive contains empty cache directories excluded
                # from the file manifest. Only create parents of accepted files.
                continue
            name = PurePosixPath(*p.parts[1:]).as_posix()
            if not member.isfile() or name not in rows or name in seen:
                raise ValueError('Unexpected/duplicate/nonregular archive member: ' + member.name)
            row = rows[name]
            if member.size != row['bytes']:
                raise ValueError('Archive member size mismatch: ' + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            pending = target.with_name(target.name + '.install-pending')
            if pending.is_symlink():
                raise ValueError('Symlink in temporary output')
            h = hashlib.sha256()
            stream = source.extractfile(member)
            with pending.open('wb') as output:
                for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
                    output.write(chunk)
                    h.update(chunk)
            if h.hexdigest() != row['sha256']:
                raise ValueError('Archive member SHA-256 mismatch: ' + name)
            pending.chmod(0o755 if member.mode & 0o111 else 0o644)
            pending.replace(target)
            seen.add(name)
            if time.monotonic() - last >= 30:
                print('ENVIRONMENT_UNPACK_PROGRESS', len(seen), len(rows), flush=True)
                last = time.monotonic()
    if seen != set(rows):
        raise ValueError('Archive is missing required files')


def install(root, expected_hash=MANIFEST_HASH):
    if root.is_symlink():
        raise ValueError('Environment root is a symlink')
    manifest_path = checked_path(root, 'environment-pvc-manifest.json')
    if digest(manifest_path) != expected_hash:
        raise ValueError('Environment manifest differs from fixed profile')
    manifest = json.loads(manifest_path.read_bytes())
    if manifest['id'] != 'esmfold2-python312-cu126-pvc-r01' or manifest['scientific_gate'] != 'CLOSED':
        raise ValueError('Unexpected environment identity')
    for row in manifest['files']:
        print('ENVIRONMENT_SOURCE_VERIFY', row['path'], flush=True)
        path = checked_path(root, row['path'])
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Environment source integrity mismatch: ' + row['path'])
    extracted = manifest['extracted']
    if extracted['root'] != 'site-packages' or extracted['manifest'] != 'site-packages-files.json':
        raise ValueError('Unexpected environment tree mapping')
    tree = json.loads((root / 'site-packages-files.json').read_bytes())
    rows = {}
    for row in tree['files']:
        name = relative(row['path']).as_posix()
        if name in rows:
            raise ValueError('Duplicate tree manifest path')
        rows[name] = row
    if len(rows) != extracted['file_count'] or sum(r['bytes'] for r in rows.values()) != extracted['total_bytes']:
        raise ValueError('Environment tree totals mismatch')
    final = checked_path(root, 'site-packages')
    if not final.exists():
        if shutil.disk_usage(root).free < extracted['total_bytes'] + 1024**3:
            raise ValueError('Insufficient PVC space for extraction')
        staging = checked_path(root, '.environment-unpack-r01')
        staging.mkdir(exist_ok=True)
        print('ENVIRONMENT_UNPACK_START', len(rows), extracted['total_bytes'], flush=True)
        unpack(root / 'site-packages.tar.gz', staging, rows)
        verify_tree(staging / 'site-packages', rows)
        (staging / 'site-packages').rename(final)
    else:
        # Never overwrite an already installed tree: revalidate it.
        verify_tree(final, rows)
    receipt = {'status': 'PVC_ENVIRONMENT_EXTRACTED_VERIFIED_NOT_GPU_TESTED',
               'manifest_sha256': expected_hash, 'files': len(rows),
               'bytes': extracted['total_bytes'], 'scientific_gate': 'CLOSED'}
    temporary = root / 'installation-receipt.json.pending'
    temporary.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    temporary.replace(root / 'installation-receipt.json')
    print('ESMFOLD2_ENVIRONMENT_READY', len(rows), extracted['total_bytes'], flush=True)
    return receipt


def main():
    if sys.argv[1:] == ['--remote']:
        import fcntl
        root = Path(ENVIRONMENT)
        with (root / '.install.lock').open('a') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            install(root)
    elif not sys.argv[1:]:
        project = Path(__file__).resolve().parents[1]
        command = ['kubectl', '--kubeconfig', str(project / '.tmp/himat.kubeconfig'),
                   '-n', 'him-ws', 'exec', '-i', 'antigen-esmfold2-assets-upload',
                   '--', 'python', '-u', '-B', '-', '--remote']
        result = subprocess.run(command, input=Path(__file__).read_bytes())
        raise SystemExit(result.returncode)
    else:
        raise SystemExit('Run without arguments from the local project directory')


if __name__ == '__main__':
    main()
