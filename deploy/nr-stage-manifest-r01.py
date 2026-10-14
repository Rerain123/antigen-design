"""Register the completed nr staging bytes without moving or rewriting the database."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/data/nr-20250624')
RAW = ROOT / 'raw'
MIRROR = 'http://ncbichina.iict.ac.cn:8008/blastdb/20250624/2025-06-24-01-05-02/'
CANONICAL = 'gs://blast-db/2025-06-24-01-05-02/'
AUXILIARY = {'pal', 'pdb', 'pos', 'pot', 'ptf', 'pto', 'pxm'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic(path, raw):
    tmp = path.with_name(path.name + '.pending')
    with tmp.open('xb') as stream:
        stream.write(raw)
    tmp.replace(path)


def main():
    metadata_raw = (ROOT / 'nr-prot-metadata.json').read_bytes()
    meta = json.loads(metadata_raw)
    receipt = json.loads((ROOT / 'download-receipt.json').read_bytes())
    assert receipt['status'] == 'STAGED_NOT_N03_ACCEPTED'
    assert receipt['source'] == MIRROR
    assert meta['dbname'] == 'nr' and meta['dbtype'] == 'Protein'
    assert meta['number-of-volumes'] == 123
    rows = receipt['files']
    names = [row['path'] for row in rows]
    assert len(names) == len(set(names)) == 1113
    assert set(names) == {Path(url).name for url in meta['files']} | {'nr.pal'}
    assert all(url.startswith(CANONICAL) for url in meta['files'])
    assert sum(row['bytes'] for row in rows) == receipt['downloaded_bytes']
    core = sum(row['bytes'] for row in rows if row['path'].rsplit('.', 1)[-1] not in AUXILIARY)
    assert core == meta['bytes-total'], (core, meta['bytes-total'])
    checksums = (ROOT / 'SHA256SUMS').read_text().splitlines()
    assert checksums == [row['sha256'] + '  raw/' + row['path'] for row in rows]
    existing = {p.name for p in RAW.iterdir() if p.is_file()}
    expected = set(names) | {name + '.source.json' for name in names}
    assert existing in (expected, expected | {'nr-prot-metadata.json'})
    entries = []
    for row in rows:
        name = row['path']
        assert (RAW / name).stat().st_size == row['bytes']
        entries.append(dict(path=name, role='alias' if name == 'nr.pal' else 'index',
                            bytes=row['bytes'], sha256=row['sha256']))
        sidecar = RAW / (name + '.source.json')
        sidecar_raw = sidecar.read_bytes()
        source = json.loads(sidecar_raw)
        assert source['url'] == MIRROR + name and source['bytes'] == row['bytes']
        assert set(source) == {'url', 'bytes', 'validator'}
        entries.append(dict(path=sidecar.name, role='provenance',
                            bytes=len(sidecar_raw), sha256=digest(sidecar_raw)))
    metadata_copy = RAW / 'nr-prot-metadata.json'
    if metadata_copy.exists():
        assert metadata_copy.read_bytes() == metadata_raw
    else:
        atomic(metadata_copy, metadata_raw)
    entries.append(dict(path=metadata_copy.name, role='metadata',
                        bytes=len(metadata_raw), sha256=digest(metadata_raw)))
    manifest = dict(
        schema_version='0.2.0', database_id='nr-20250624',
        qualification='TARGET_DATABASE_UNREVIEWED',
        purpose='N03 local blastp target for M1 internal testing; mirror ' + MIRROR,
        created_at=datetime.now(timezone.utc).isoformat(),
        source=dict(name='NCBI nr protein database via IICT mirror',
                    version='2025-06-24-01-05-02', release_date='2025-06-22',
                    license='UNREVIEWED: internal M1 engineering use only',
                    reference=CANONICAL),
        blast=dict(db_prefix='nr', dbtype='prot', blastdb_version=5,
                   title=meta['description'], sequence_count=meta['number-of-sequences'],
                   makeblastdb_version='NCBI prebuilt; builder version not supplied',
                   builder_identity='NCBI nr snapshot 2025-06-24-01-05-02'),
        prebuilt=dict(metadata_path=metadata_copy.name, alias_path='nr.pal',
                      volume_prefixes=[f'nr.{i:03d}' for i in range(123)],
                      integrity='LOCAL_SHA256_NO_UPSTREAM_CHECKSUM'),
        files=sorted(entries, key=lambda row: row['path']))
    manifest_raw = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
    assert len(manifest_raw) <= 1024 * 1024
    manifest_path = RAW / 'manifest.json'
    assert not manifest_path.exists()
    atomic(manifest_path, manifest_raw)
    print(json.dumps(dict(status='REGISTERED_NOT_VERIFIED',
                          manifest_sha256=digest(manifest_raw),
                          manifest_bytes=len(manifest_raw), files=len(entries),
                          database_bytes=receipt['downloaded_bytes'],
                          metadata_core_bytes=core,
                          upstream_checksum_verified=False), sort_keys=True))


if __name__ == '__main__':
    main()
