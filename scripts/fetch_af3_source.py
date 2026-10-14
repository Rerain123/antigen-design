"""Fetch, verify, and safely stage the pinned AlphaFold 3 v3.0.2 source."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request


COMMIT = "f6a5aecf6eea2b5de4f846df86921630c5036b0b"
URL = "https://codeload.github.com/google-deepmind/alphafold3/tar.gz/" + COMMIT
PREFIX = "alphafold3-" + COMMIT
EXPECTED_ARCHIVE_BYTES = 5_909_661
EXPECTED_ARCHIVE_SHA256 = "c9badce145a62ccdfb776d6128fb2774a3ccb0b9f61cfd3d4d0ee83547f6dee6"
EXPECTED_MEMBERS = 220
EXPECTED_DOCKERFILE_SHA256 = "c4ffc1855c65962c1f5a7d434274bd85654a478e297498198ac250e698c1c58b"
EXPECTED_PYPROJECT_SHA256 = "2064b089754d00470fb7d990e8dce9d76b98afa8f5d567265db6710a2fe081e2"
EXPECTED_UV_LOCK_BYTES = 135_267
EXPECTED_UV_LOCK_SHA256 = "86f48ffa1b38b37efc0d1b10bdc1be1f7989bd6521f3f04257e7aeeeb62510ed"
EXPECTED_WHEEL_URLS = 326
EXPECTED_INDEX_URLS = 69
CUDA_IMAGE = "nvidia/cuda@sha256:c87e78933f4c16e3272123bf2f75537306596d0fbaa395a29696a22786e5ee0e"
UV_IMAGE = "ghcr.io/astral-sh/uv@sha256:816fdce3387ed2142e37d2e56e1b1b97ccc1ea87731ba199dc8a25c04e4997c5"
PYPI_WHEEL_SOURCE = "https://files.pythonhosted.org/"
PYPI_WHEEL_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/"
PYPI_INDEX_SOURCE = "https://pypi.org/simple"
PYPI_INDEX_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe_relative(name: str) -> PurePosixPath | None:
    if name == PREFIX:
        return None
    expected = PREFIX + "/"
    if not name.startswith(expected):
        raise ValueError("Archive member is outside the pinned source prefix")
    relative = PurePosixPath(name[len(expected):])
    if (relative.is_absolute() or "\\" in name or ".." in relative.parts
            or any(part in ("", ".") for part in relative.parts)):
        raise ValueError("Unsafe source archive path: " + repr(name))
    return relative


def extract_verified(raw: bytes, output: Path) -> dict:
    if len(raw) != EXPECTED_ARCHIVE_BYTES or sha256(raw) != EXPECTED_ARCHIVE_SHA256:
        raise ValueError("Pinned AF3 source archive identity differs")
    if output.exists():
        raise ValueError("AF3 source output already exists; refusing overwrite")
    output.mkdir(parents=True)
    files = 0
    directories = 0
    seen: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) != EXPECTED_MEMBERS:
            raise ValueError("Pinned AF3 source archive member count differs")
        for member in members:
            relative = safe_relative(member.name)
            if relative is None:
                if not member.isdir():
                    raise ValueError("Pinned source root is not a directory")
                continue
            key = relative.as_posix()
            if key in seen:
                raise ValueError("Duplicate AF3 source archive path: " + key)
            seen.add(key)
            destination = output.joinpath(*relative.parts)
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=False)
                directories += 1
                continue
            if not member.isfile() or member.issym() or member.islnk() or member.isdev():
                raise ValueError("Unsupported AF3 source archive member: " + key)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("AF3 source archive member is unreadable: " + key)
            with destination.open("xb") as stream:
                while chunk := source.read(1024 * 1024):
                    stream.write(chunk)
            destination.chmod(member.mode & 0o777)
            files += 1

    dockerfile = output / "docker" / "Dockerfile"
    pyproject = output / "pyproject.toml"
    uv_lock = output / "uv.lock"
    if sha256(dockerfile.read_bytes()) != EXPECTED_DOCKERFILE_SHA256:
        raise ValueError("Pinned AF3 Dockerfile SHA-256 differs")
    if sha256(pyproject.read_bytes()) != EXPECTED_PYPROJECT_SHA256:
        raise ValueError("Pinned AF3 pyproject SHA-256 differs")
    official_uv_lock = uv_lock.read_bytes()
    if (len(official_uv_lock) != EXPECTED_UV_LOCK_BYTES
            or sha256(official_uv_lock) != EXPECTED_UV_LOCK_SHA256):
        raise ValueError("Pinned AF3 uv.lock identity differs")

    text = dockerfile.read_text(encoding="utf-8")
    cuda_old = "FROM nvidia/cuda:12.6.3-base-ubuntu24.04"
    uv_old = "COPY --from=ghcr.io/astral-sh/uv:0.9.24"
    if text.count(cuda_old) != 1 or text.count(uv_old) != 1:
        raise ValueError("Pinned AF3 Dockerfile base image statements differ")
    text = text.replace(cuda_old, "FROM " + CUDA_IMAGE)
    text = text.replace(uv_old, "COPY --from=" + UV_IMAGE)
    dockerfile.write_text(text, encoding="utf-8", newline="\n")

    lock_text = official_uv_lock.decode("utf-8")
    if lock_text.count(PYPI_WHEEL_SOURCE) != EXPECTED_WHEEL_URLS:
        raise ValueError("Pinned AF3 uv.lock wheel URL count differs")
    if lock_text.count(PYPI_INDEX_SOURCE) != EXPECTED_INDEX_URLS:
        raise ValueError("Pinned AF3 uv.lock index URL count differs")
    lock_text = lock_text.replace(PYPI_WHEEL_SOURCE, PYPI_WHEEL_MIRROR)
    lock_text = lock_text.replace(PYPI_INDEX_SOURCE, PYPI_INDEX_MIRROR)
    uv_lock.write_text(lock_text, encoding="utf-8", newline="\n")

    return {
        "schema": "t01.af3-environment-source/1",
        "status": "AF3_SOURCE_VERIFIED_BASE_IMAGES_PINNED_NOT_BUILT",
        "version": "3.0.2",
        "commit": COMMIT,
        "url": URL,
        "archive_bytes": len(raw),
        "archive_sha256": sha256(raw),
        "archive_members": len(members),
        "source_files": files,
        "source_directories": directories,
        "official_dockerfile_sha256": EXPECTED_DOCKERFILE_SHA256,
        "pinned_dockerfile_sha256": sha256(dockerfile.read_bytes()),
        "pyproject_sha256": EXPECTED_PYPROJECT_SHA256,
        "official_uv_lock_bytes": EXPECTED_UV_LOCK_BYTES,
        "official_uv_lock_sha256": EXPECTED_UV_LOCK_SHA256,
        "mirrored_uv_lock_sha256": sha256(uv_lock.read_bytes()),
        "mirrored_wheel_urls": EXPECTED_WHEEL_URLS,
        "mirrored_index_urls": EXPECTED_INDEX_URLS,
        "pypi_mirror": PYPI_INDEX_MIRROR,
        "cuda_image": CUDA_IMAGE,
        "uv_image": UV_IMAGE,
        "scientific_gate": "CLOSED",
        "usable_for_pipeline": False,
    }


def download(opener=urllib.request.urlopen) -> bytes:
    request = urllib.request.Request(URL, headers={"Accept-Encoding": "identity"})
    with opener(request, timeout=120) as response:
        if response.status != 200:
            raise ValueError("Pinned AF3 source download did not return 200")
        raw = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise ValueError("Pinned AF3 source archive exceeds the download bound")
    return raw


def prepare(workspace: Path, opener=urllib.request.urlopen) -> dict:
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    output = workspace / "source"
    receipt_path = workspace / "source-receipt.json"
    if receipt_path.exists() or output.exists():
        raise ValueError("AF3 build workspace is not empty")
    receipt = extract_verified(download(opener), output)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("AF3_SOURCE_VERIFIED " + json.dumps(receipt, sort_keys=True), flush=True)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    prepare(args.workspace)


if __name__ == "__main__":
    main()
