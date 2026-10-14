"""Independently hash every registered nr file on a read-only PVC mount."""
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import monotonic

ROOT = Path('/data/nr-20250624/raw')
MANIFEST_SHA256 = 'ea46b05b6465cd97557cf0e6304cc0e7766e53d4ece4209b55bf59d64d4841cd'


def check(row):
    path = ROOT / row['path']
    assert path.is_file() and not path.is_symlink(), row['path']
    before = path.stat()
    assert before.st_nlink == 1, row['path']
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    after = path.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (
        after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), row['path']
    assert size == row['bytes'] and digest.hexdigest() == row['sha256'], row['path']
    return size


def main():
    start = monotonic()
    raw = (ROOT / 'manifest.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
    manifest = json.loads(raw)
    assert manifest['database_id'] == 'nr-20250624'
    rows = manifest['files']
    names = {row['path'] for row in rows}
    assert len(names) == len(rows) == 2227
    actual = {str(path.relative_to(ROOT)) for path in ROOT.iterdir() if path.is_file()}
    assert actual == names | {'manifest.json'}
    done = 0
    total = 0
    threshold = 25 * 1024 ** 3
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(check, row) for row in rows]
        for future in as_completed(futures):
            total += future.result()
            done += 1
            if total >= threshold:
                print('PROGRESS', done, '/', len(rows), 'bytes', total,
                      'elapsed_s', round(monotonic() - start, 1), flush=True)
                threshold += 25 * 1024 ** 3
    print(json.dumps(dict(status='VERIFIED_FULL_SHA256',
                          manifest_sha256=MANIFEST_SHA256, files=done,
                          bytes=total, elapsed_seconds=round(monotonic()-start, 1),
                          read_only_mount=True, upstream_checksum_verified=False),
                     sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
