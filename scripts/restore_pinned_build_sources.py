"""Restore Git-transformed line endings in image copies using frozen hashes.

Only run in an isolated build tree. Never update manifests or source originals.
"""
import hashlib
import json
from pathlib import Path


def restore(root, profile_manifest=None):
    root = Path(root).resolve()
    if (root / '.git').exists():
        raise ValueError('Refusing to modify a Git working tree')
    manifest = root / 'src/t01_phase1_real/development/structure/sources.json'
    changes = []
    entries = json.loads(manifest.read_bytes())['files']
    if profile_manifest is not None:
        profile_path = root / profile_manifest
        if profile_path.is_symlink() or not profile_path.resolve().is_relative_to(root):
            raise ValueError('Profile manifest escapes build root')
        entries += json.loads(profile_path.read_bytes())['files']
    codon = root / 'src/t01_phase1_real/development/codon/assets/manifest.json'
    if codon.exists():
        entries.append(dict(path=codon.relative_to(root).as_posix(),
                            sha256='b72cafa76edf117e5deb53fe014afe0d4c24bdbc5d9fbb9d47c6b7581789c6ae'))
        table=json.loads(codon.read_bytes())['table']
        entries.append(dict(path=(codon.parent/table['file']).relative_to(root).as_posix(),sha256=table['sha256']))
    # BepiPred also pins package provenance held outside the mounted model PVC.
    # Only repository-owned files belong in the control image; model assets are
    # still verified by the runtime against the original complete manifest.
    bepipred = root / 'src/t01_phase1_real/development/bepipred/assets.json'
    if bepipred.exists():
        entries += [row for row in json.loads(bepipred.read_bytes())['files']
                    if not row['path'].startswith('var/t01-phase1-real/tool-assets/')]
    unique = {}
    for entry in entries:
        prior = unique.get(entry['path'])
        if prior and prior['sha256'] != entry['sha256']:
            raise ValueError('Conflicting frozen source hashes: ' + entry['path'])
        unique[entry['path']] = entry
    entries = list(unique.values())
    for entry in entries:
        path = root / entry['path']
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Pinned path escapes build root')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() == entry['sha256']:
            continue
        if path.suffix not in ('.md', '.json', '.py', '.txt', '.csv', '.Dockerfile'):
            raise ValueError('Unsupported pinned source: ' + entry['path'])
        lf = raw.replace(b'\r\n', b'\n')
        candidates = (lf, lf.replace(b'\n', b'\r\n'))
        matched = next((v for v in candidates if hashlib.sha256(v).hexdigest() == entry['sha256']), None)
        if matched is None:
            raise ValueError('Pinned source content differs: ' + entry['path'])
        changes.append((path, matched))
    # Validate the whole set before writing any derived image copy.
    for path, raw in changes:
        path.write_bytes(raw)
    for entry in entries:
        if hashlib.sha256((root / entry['path']).read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Build source verification failed')
    return dict(verified=len(entries), restored=len(changes))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-root', required=True, type=Path)
    parser.add_argument('--profile-manifest', type=Path)
    args = parser.parse_args()
    print(json.dumps(restore(args.build_root, args.profile_manifest)))
