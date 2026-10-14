"""Deterministic complete project-source bundle; no model or runtime assets."""
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

PACKAGES = ('t01_phase1_real', 't01_structure_mapping')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sources(root):
    result = {}
    for package in PACKAGES:
        for path in sorted((Path(root) / package).rglob('*')):
            if '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            if path.is_symlink():
                raise ValueError('Source symlinks are forbidden')
            if path.is_file():
                result[path.relative_to(root).as_posix()] = path.read_bytes()
    if any(package + '/__init__.py' not in result for package in PACKAGES):
        raise ValueError('Both complete packages are required')
    return result


def build(root):
    files = sources(root)
    manifest = {name: sha(raw) for name, raw in files.items()}
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o444
            archive.addfile(info, io.BytesIO(raw))
    return gzip.compress(stream.getvalue(), mtime=0), manifest


def install(archive_path, manifest_path, target, expected):
    """Validate the whole archive before writing regular files into an empty directory."""
    manifest_raw = Path(manifest_path).read_bytes()
    if sha(manifest_raw) != expected:
        raise ValueError('Manifest digest mismatch')
    manifest = json.loads(manifest_raw)
    target = Path(target)
    if target.is_symlink() or (target.exists() and any(target.iterdir())):
        raise ValueError('An empty non-symlink destination is required')
    files = {}
    with tarfile.open(archive_path, 'r:gz') as archive:
        for member in archive:
            name = member.name
            path = PurePosixPath(name)
            if (not member.isfile() or path.is_absolute() or '..' in path.parts
                    or path.parts[0] not in PACKAGES or str(path) != name
                    or name not in manifest or name in files or member.size > 4 * 1024 ** 2):
                raise ValueError('Unexpected archive entry')
            raw = archive.extractfile(member).read()
            if sha(raw) != manifest[name]:
                raise ValueError('Source digest mismatch')
            files[name] = raw
            if sum(map(len, files.values())) > 16 * 1024 ** 2:
                raise ValueError('Source bundle too large')
    if set(files) != set(manifest):
        raise ValueError('Incomplete source bundle')
    target.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
        path.chmod(0o444)
    print(json.dumps(dict(source_sha256=expected, files=len(files))))


if __name__ == '__main__':
    import sys
    install(*sys.argv[1:])
