"""Download one official IEDB SQL snapshot; verify without importing or deploying."""
import argparse
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request

URL = 'https://www.iedb.org/downloader.php?file_name=doc/iedb_public.sql.gz'
LISTING = 'https://www.iedb.org/export_data_v3.php'
MAX_BYTES = 2 * 1024**3
RESERVE = 2 * 1024**3


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def download(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    # A snapshot is immutable. A failed attempt uses a new directory.
    with (root / 'started.json').open('x', encoding='utf-8') as stream:
        json.dump({'started_at': now(), 'pid': os.getpid(), 'url': URL}, stream)
    start = time.monotonic()
    status = dict(state='starting', url=URL, started_at=now(), bytes_received=0)

    def publish(**values):
        status.update(values, updated_at=now(), elapsed_seconds=round(time.monotonic()-start, 2))
        temp = root / 'status.pending'
        temp.write_text(json.dumps(status, indent=2), encoding='utf-8')
        os.replace(temp, root / 'status.json')

    try:
        if shutil.disk_usage(root).free < MAX_BYTES + RESERVE:
            raise RuntimeError('Insufficient free space for bounded download plus reserve')
        with urllib.request.urlopen(LISTING, timeout=45) as response:
            listing = response.read(1024**2 + 1)
        if len(listing) > 1024**2:
            raise RuntimeError('Export listing exceeded expected bound')
        json.loads(listing)
        (root / 'official-export-listing.json').write_bytes(listing)
        publish(state='downloading')
        digest = hashlib.sha256()
        part = root / 'iedb_public.sql.gz.part'
        count = 0
        last = 0
        with urllib.request.urlopen(URL, timeout=60) as response, part.open('xb') as output:
            expected = response.headers.get('Content-Length')
            publish(final_url=response.url, content_length=expected,
                    response_headers={k:v for k,v in response.headers.items()
                                      if k.lower() in ('content-type','etag','last-modified','content-length')})
            if response.status != 200:
                raise RuntimeError('Full download requires HTTP 200')
            while True:
                chunk = response.read(1024**2)
                if not chunk:
                    break
                if count == 0 and chunk[:2] != b'\x1f\x8b':
                    raise RuntimeError('Official response is not a gzip file')
                count += len(chunk)
                if count > MAX_BYTES or shutil.disk_usage(root).free < RESERVE:
                    raise RuntimeError('Download exceeded storage bounds')
                output.write(chunk)
                digest.update(chunk)
                if time.monotonic() - last >= 3:
                    output.flush()
                    publish(bytes_received=count)
                    last = time.monotonic()
            output.flush()
            os.fsync(output.fileno())
        if not count or (expected is not None and count != int(expected)):
            raise RuntimeError('Empty or incomplete HTTP response')
        publish(state='verifying_gzip', bytes_received=count, sha256=digest.hexdigest())
        expanded = 0
        with gzip.open(part, 'rb') as stream:
            while True:
                chunk = stream.read(4*1024**2)
                if not chunk:
                    break
                expanded += len(chunk)
                if expanded > 100 * 1024**3:
                    raise RuntimeError('Expanded stream exceeded verification bound')
                if time.monotonic() - last >= 3:
                    publish(uncompressed_bytes_verified=expanded)
                    last = time.monotonic()
        # gzip EOF checks CRC and length; do not save the expanded SQL yet.
        final = root / 'iedb_public.sql.gz'
        if final.exists():
            raise RuntimeError('Refusing to replace an existing snapshot')
        os.rename(part, final)
        (root / 'SHA256SUMS').write_text(digest.hexdigest()+'  iedb_public.sql.gz\n', encoding='ascii')
        publish(state='downloaded_verified', finished_at=now(), gzip_integrity=True,
                uncompressed_bytes_verified=expanded, file=str(final),
                imported=False, blast_index_built=False, deployed=False,
                upstream_checksum_verified=False)
    except BaseException as exc:
        publish(state='failed', error_type=type(exc).__name__, error=str(exc))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    download(parser.parse_args().destination)
