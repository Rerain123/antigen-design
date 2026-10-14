"""Download pinned Biohub ESMFold2 standard assets without running model code."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import time
import urllib.error
import urllib.request

MODELS = {
    'ESMFold2': ('biohub/ESMFold2', 'e1e189d0f5fb70c2693da2332eca4443c0ccccd6'),
    'ESMC-6B': ('biohub/ESMC-6B', '7d0f99a8b716749ad1a0328181c1e0339691b0c2'),
}
SOURCES = {
    'esm': ('Biohub/esm', 'b6b0e8815dc3174a9fe9afd36b222aea57d536c5'),
    'transformers': ('Biohub/transformers', 'ef32577f55da19a4989cd7b22e004dc43a4998cb'),
}

def request(url, headers=None):
    return urllib.request.urlopen(urllib.request.Request(url, headers=dict({'User-Agent': 'T01-asset-preparation/1.0'}, **(headers or {}))), timeout=60)

def read_json(url):
    with request(url) as stream:
        return json.load(stream)

def hashes(path):
    sha256 = hashlib.sha256()
    git_blob = hashlib.sha1(('blob ' + str(path.stat().st_size) + '\0').encode())
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            sha256.update(block)
            git_blob.update(block)
    return sha256.hexdigest(), git_blob.hexdigest()

def validate(path, entry):
    if not path.is_file() or path.stat().st_size != entry['size']:
        return None
    sha256, git_blob = hashes(path)
    expected = entry.get('lfs', {}).get('sha256')
    if (expected and sha256 != expected) or (not expected and git_blob != entry['blobId']):
        return None
    return sha256

def download(url, target, entry):
    if target.exists():
        digest = validate(target, entry)
        if not digest:
            raise ValueError('Existing asset differs from pinned upstream: ' + str(target))
        return digest
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.partial')
    for attempt in range(6):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset == entry['size']:
            break
        if offset > entry['size']:
            raise ValueError('Oversized partial asset')
        try:
            # Fresh resolver query avoids reuse of expired signed CDN redirects.
            resolver = url + '?download=true&t01_attempt=' + str(time.time_ns())
            with request(resolver, {'Range': 'bytes=' + str(offset) + '-'} if offset else {}) as response:
                if offset:
                    if response.status != 206 or not response.headers.get('Content-Range', '').startswith('bytes ' + str(offset) + '-'):
                        raise ValueError('Server did not honor resume range')
                elif response.status != 200:
                    raise ValueError('Unexpected initial download response')
                last = time.monotonic()
                with partial.open('ab' if offset else 'wb') as stream:
                    while block := response.read(4 * 1024**2):
                        stream.write(block)
                        offset += len(block)
                        if offset > entry['size']:
                            raise ValueError('Download larger than pinned asset')
                        if time.monotonic() - last > 30:
                            print('DOWNLOAD', target.name, f'{offset / entry["size"]:.1%}', flush=True)
                            last = time.monotonic()
            if offset == entry['size']:
                break
        except (OSError, urllib.error.URLError) as error:
            print('RETRY', target.name, attempt + 1, type(error).__name__, flush=True)
            if attempt == 5:
                raise RuntimeError('Download interrupted; partial retained: ' + target.name) from None
            time.sleep(3)
    digest = validate(partial, entry)
    if not digest:
        raise ValueError('Downloaded asset failed upstream hash/size check: ' + target.name)
    partial.rename(target)
    return digest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for local, (repo, revision) in MODELS.items():
        metadata_path = out / (local + '.upstream.json')
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_bytes())
        else:
            metadata = read_json(f'https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true')
            metadata_path.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        assert metadata['sha'] == revision and metadata['gated'] is False
        for entry in metadata['siblings']:
            relative = PurePosixPath(entry['rfilename'])
            if relative.is_absolute() or '..' in relative.parts or '\\' in str(relative):
                raise ValueError('Unsafe upstream file path')
            target = out / 'models' / local / relative
            print('ASSET', local, str(relative), entry['size'], flush=True)
            digest = download(f'https://huggingface.co/{repo}/resolve/{revision}/{relative}', target, entry)
            records.append(dict(path=target.relative_to(out).as_posix(), bytes=entry['size'], sha256=digest, repo=repo, revision=revision))
            (out / 'download-progress.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
            print('VERIFIED', local, str(relative), flush=True)
    for name, (repo, revision) in SOURCES.items():
        target = out / 'sources' / (name + '-' + revision + '.tar.gz')
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            partial = target.with_suffix('.partial')
            with request(f'https://codeload.github.com/{repo}/tar.gz/{revision}') as source, partial.open('wb') as dest:
                for block in iter(lambda: source.read(1024**2), b''):
                    dest.write(block)
            partial.rename(target)
        records.append(dict(path=target.relative_to(out).as_posix(), bytes=target.stat().st_size, sha256=hashes(target)[0], repo=repo, revision=revision))
    receipt = dict(status='ASSETS_DOWNLOADED_NOT_DEPLOYED', variant='ESMFold2 standard', models=MODELS, sources=SOURCES,
                   files=records, total_bytes=sum(r['bytes'] for r in records), inference_verified=False)
    (out / 'asset-manifest.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print('ASSETS_VERIFIED', len(records), receipt['total_bytes'], flush=True)

if __name__ == '__main__':
    main()
