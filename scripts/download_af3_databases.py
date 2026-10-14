"""Download pinned official AF3 v3.0 archives to a dedicated persistent volume.

Archives only: unpacking and data-pipeline acceptance are separate steps.
Uses official MD5 (present on every pinned object) plus local SHA-256.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import urllib.request

if __package__:
    from .download_af3_weights import atomic_json, source_identity
else:
    from download_af3_weights import atomic_json, source_identity

BASE = 'https://storage.googleapis.com/alphafold-databases/v3.0/'


def download_one(root, asset, opener=urllib.request.urlopen):
    name = asset['file']
    if Path(name).name != name or '/' in name or '\\' in name or not name.endswith('.zst'):
        raise ValueError('Invalid archive filename')
    url = BASE + name
    with opener(urllib.request.Request(url, method='HEAD'), timeout=60) as reply:
        identity = source_identity(reply.headers)
        identity['url'] = url
        if reply.status != 200 or identity != asset['identity']:
            raise ValueError('Official object differs from pinned manifest: ' + name)
    root.mkdir(parents=True, exist_ok=True)
    target, partial = root / name, root / (name + '.partial')
    source = root / (name + '.source.json')
    if source.exists():
        if json.loads(source.read_text()) != identity:
            raise ValueError('Partial source identity changed: ' + name)
    elif target.exists() or partial.exists():
        raise ValueError('Existing bytes have no source identity: ' + name)
    else:
        atomic_json(source, identity)
    size = identity['bytes']
    if not target.exists():
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > size:
            raise ValueError('Partial exceeds official size: ' + name)
        if shutil.disk_usage(root).free < size - offset + 1024**3:
            raise ValueError('Insufficient PVC space: ' + name)
        if offset < size:
            headers = {'If-Match': identity['etag'], 'Accept-Encoding': 'identity'}
            if offset:
                headers['Range'] = f'bytes={offset}-'
            with opener(urllib.request.Request(url, headers=headers), timeout=120) as reply:
                if reply.status != (206 if offset else 200):
                    raise ValueError('Server did not honor range: ' + name)
                if offset and reply.headers.get('Content-Range') != f'bytes {offset}-{size-1}/{size}':
                    raise ValueError('Incorrect resume range: ' + name)
                if int(reply.headers['Content-Length']) != size-offset or reply.headers.get('ETag') != identity['etag']:
                    raise ValueError('GET identity differs from HEAD: ' + name)
                print('DATABASE_DOWNLOAD_START', name, offset, size, flush=True)
                last = time.monotonic()
                with partial.open('ab' if partial.exists() else 'xb') as output:
                    while chunk := reply.read(4*1024**2):
                        if offset + len(chunk) > size:
                            raise ValueError('Response exceeds pinned size: ' + name)
                        output.write(chunk)
                        offset += len(chunk)
                        if time.monotonic()-last >= 30:
                            print('DATABASE_DOWNLOAD_PROGRESS', name, offset, size, round(offset*100/size, 1), flush=True)
                            last = time.monotonic()
        checked = partial
    else:
        checked = target
    if checked.stat().st_size != size:
        raise ValueError('Incomplete archive; partial retained: ' + name)
    print('DATABASE_VERIFY_START', name, size, flush=True)
    md5, sha = hashlib.md5(), hashlib.sha256()
    last, count = time.monotonic(), 0
    with checked.open('rb') as stream:
        while chunk := stream.read(4*1024**2):
            md5.update(chunk)
            sha.update(chunk)
            count += len(chunk)
            if time.monotonic()-last >= 30:
                print('DATABASE_VERIFY_PROGRESS', name, count, size, flush=True)
                last = time.monotonic()
    if base64.b64encode(md5.digest()).decode() != identity['md5_base64']:
        raise ValueError('Official MD5 mismatch; archive not accepted: ' + name)
    if checked == partial:
        partial.rename(target)
    receipt = {**identity, 'file': name, 'sha256': sha.hexdigest(),
               'official_md5_verified': True, 'decompressed': False,
               'status': 'ARCHIVE_VERIFIED_NOT_DEPLOYED', 'scientific_gate': 'CLOSED'}
    atomic_json(root / (name + '.receipt.json'), receipt)
    print('AF3_DATABASE_ARCHIVE_VERIFIED', name, size, receipt['sha256'], flush=True)
    return receipt


def main():
    import fcntl
    root, manifest_path = Path(sys.argv[1]), Path(sys.argv[2])
    manifest = json.loads(manifest_path.read_text())
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.download.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        saved = root / 'database-manifest.json'
        if saved.exists() and json.loads(saved.read_text()) != manifest:
            raise ValueError('Database manifest changed; use a separate directory')
        atomic_json(saved, manifest)
        assets = manifest['assets']
        remaining = sum(max(0, a['identity']['bytes'] - max(
            [(root / (a['file'] + suffix)).stat().st_size
             for suffix in ('', '.partial') if (root / (a['file'] + suffix)).exists()] or [0])) for a in assets)
        if shutil.disk_usage(root).free < remaining + 1024**3:
            raise ValueError('Insufficient PVC space for remaining archive set')
        receipts = []
        for asset in assets:
            receipts.append(download_one(root, asset))
        atomic_json(root / 'download-receipt.json', {
            'status': 'DATABASE_ARCHIVES_VERIFIED_NOT_DEPLOYED', 'scientific_gate': 'CLOSED',
            'decompressed': False, 'assets': receipts})
        print('AF3_DATABASES_ARCHIVES_VERIFIED', len(receipts), sum(a['bytes'] for a in receipts), flush=True)


if __name__ == '__main__':
    main()
