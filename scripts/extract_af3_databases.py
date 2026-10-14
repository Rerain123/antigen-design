"""Safely extract the pinned AF3 v3.0 database archives.

The source archives stay in place.  Extraction is streamed through the system
libzstd (no network and no temporary full archive copy), every compressed source
is hashed again against its verified receipt, and the final directory is
published only after all files have a manifest.  A failed run leaves its
``*.partial`` staging directory for inspection and never retries or overwrites
an existing published directory.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
from typing import BinaryIO


REQUIRED_SOURCE_STATUS = "DATABASE_ARCHIVES_VERIFIED_NOT_DEPLOYED"
REQUIRED_ARCHIVE_STATUS = "ARCHIVE_VERIFIED_NOT_DEPLOYED"
REQUIRED_OUTPUT_STATUS = "AF3_DATABASES_EXTRACTED_VERIFIED_NOT_DEPLOYED"
RESERVE_BYTES = 64 * 1024**3
EXPANDED_ESTIMATE_BYTES = 630_000_000_000
# Keep the Python/libzstd and filesystem working sets bounded.  The first
# cluster extraction used 8 MiB buffers and a 2 GiB cgroup limit; the pod was
# OOM-killed while streaming the third (large) FASTA archive.  The extractor
# does not need a large read size, so use a 1 MiB transfer buffer and a
# smaller tar wrapper buffer.  Periodic writeback below also prevents a large
# network-filesystem page cache from growing without bound.
READ_SIZE = 1 * 1024 * 1024
IO_BUFFER_SIZE = 256 * 1024
CACHE_FLUSH_BYTES = 1 * 1024**3


class ZSTDInBuffer(ctypes.Structure):
    _fields_ = [("src", ctypes.c_void_p), ("size", ctypes.c_size_t), ("pos", ctypes.c_size_t)]


class ZSTDOutBuffer(ctypes.Structure):
    _fields_ = [("dst", ctypes.c_void_p), ("size", ctypes.c_size_t), ("pos", ctypes.c_size_t)]


def _load_zstd():
    name = ctypes.util.find_library("zstd") or "libzstd.so.1"
    library = ctypes.CDLL(name)
    library.ZSTD_createDStream.restype = ctypes.c_void_p
    library.ZSTD_freeDStream.argtypes = [ctypes.c_void_p]
    library.ZSTD_freeDStream.restype = ctypes.c_size_t
    library.ZSTD_initDStream.argtypes = [ctypes.c_void_p]
    library.ZSTD_initDStream.restype = ctypes.c_size_t
    library.ZSTD_decompressStream.argtypes = [ctypes.c_void_p, ctypes.POINTER(ZSTDOutBuffer), ctypes.POINTER(ZSTDInBuffer)]
    library.ZSTD_decompressStream.restype = ctypes.c_size_t
    library.ZSTD_isError.argtypes = [ctypes.c_size_t]
    library.ZSTD_isError.restype = ctypes.c_uint
    library.ZSTD_getErrorName.argtypes = [ctypes.c_size_t]
    library.ZSTD_getErrorName.restype = ctypes.c_char_p
    return library


class HashingFile:
    def __init__(self, path: Path):
        self.path = path
        self.stream = path.open("rb")
        self.digest = hashlib.sha256()
        self.bytes = 0

    def read(self, size: int = -1) -> bytes:
        raw = self.stream.read(size)
        self.digest.update(raw)
        self.bytes += len(raw)
        return raw

    def close(self) -> None:
        self.stream.close()


class ZstdReader(io.RawIOBase):
    def __init__(self, source: HashingFile, library):
        self.source = source
        self.library = library
        self.context = library.ZSTD_createDStream()
        if not self.context:
            raise RuntimeError("libzstd could not create a decompression stream")
        result = library.ZSTD_initDStream(self.context)
        self._check(result)
        self.input = b""
        self.input_buffer = None
        self.input_state = ZSTDInBuffer()
        self.eof = False
        self.frame_complete = False

    def readable(self) -> bool:
        return True

    def _check(self, result: int) -> None:
        if self.library.ZSTD_isError(result):
            message = self.library.ZSTD_getErrorName(result).decode("utf-8", "replace")
            raise ValueError("zstd decompression failed: " + message)

    def readinto(self, target) -> int:
        if self.eof:
            return 0
        output = (ctypes.c_ubyte * len(target))()
        output_state = ZSTDOutBuffer(ctypes.cast(output, ctypes.c_void_p), len(target), 0)
        while output_state.pos == 0 and not self.eof:
            if self.input_state.pos >= self.input_state.size:
                self.input = self.source.read(READ_SIZE)
                if self.input:
                    self.input_buffer = ctypes.create_string_buffer(self.input)
                    self.input_state = ZSTDInBuffer(ctypes.cast(self.input_buffer, ctypes.c_void_p), len(self.input), 0)
                    self.frame_complete = False
                else:
                    if self.frame_complete:
                        self.eof = True
                        break
                    self.input_state = ZSTDInBuffer(None, 0, 0)
            result = self.library.ZSTD_decompressStream(self.context, ctypes.byref(output_state), ctypes.byref(self.input_state))
            self._check(result)
            if result == 0:
                self.frame_complete = True
            elif not self.input and self.input_state.pos >= self.input_state.size and output_state.pos == 0:
                raise ValueError("zstd stream ended before a complete frame")
        size = int(output_state.pos)
        if size:
            target[:size] = bytes(output[:size])
        return size

    def close(self) -> None:
        if getattr(self, "context", None):
            self.library.ZSTD_freeDStream(self.context)
            self.context = None
        super().close()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(READ_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _flush_output(output, written: int, last_flush: int) -> int:
    """Bound dirty-page growth when writing multi-gigabyte PVC files."""
    if written - last_flush < CACHE_FLUSH_BYTES:
        return last_flush
    output.flush()
    os.fsync(output.fileno())
    fadvise = getattr(os, "posix_fadvise", None)
    dontneed = getattr(os, "POSIX_FADV_DONTNEED", None)
    if fadvise is not None and dontneed is not None:
        try:
            fadvise(output.fileno(), 0, written, dontneed)
        except OSError:
            # Some PVC/FUSE implementations do not support fadvise.  The
            # flush/fsync still bounds the userspace and dirty writeback set.
            pass
    return written


def _copy_decoded(decoder: ZstdReader, output, digest: hashlib._Hash) -> int:
    """Copy decoded bytes with one reusable buffer and no read accumulation."""
    buffer = bytearray(READ_SIZE)
    size = 0
    last_flush = 0
    while True:
        count = decoder.readinto(buffer)
        if not count:
            break
        chunk = memoryview(buffer)[:count]
        output.write(chunk)
        digest.update(chunk)
        size += count
        last_flush = _flush_output(output, size, last_flush)
    return size


def safe_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or path.as_posix() != name:
        raise ValueError("Unsafe archive member path: " + repr(name))
    if any(part in ("", ".") for part in path.parts):
        raise ValueError("Non-canonical archive member path: " + repr(name))
    return path


def verify_source_manifest(archives: Path, manifest_path: Path) -> list[dict]:
    manifest = read_json(manifest_path)
    if manifest.get("archives_only") is not True or manifest.get("schema") != "t01.af3-database-download/1":
        raise ValueError("Unexpected AF3 database manifest")
    saved = read_json(archives / "database-manifest.json")
    if saved != manifest:
        raise ValueError("Mounted database manifest differs from pinned manifest")
    total = 0
    verified = []
    for asset in manifest["assets"]:
        name, identity = asset["file"], asset["identity"]
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError("Unsafe source archive name")
        archive = archives / name
        if not archive.is_file() or archive.is_symlink() or archive.stat().st_size != identity["bytes"]:
            raise ValueError("Source archive size/type mismatch: " + name)
        if read_json(archives / f"{name}.source.json") != identity:
            raise ValueError("Source identity mismatch: " + name)
        receipt = read_json(archives / f"{name}.receipt.json")
        if receipt.get("file") != name or receipt.get("status") != REQUIRED_ARCHIVE_STATUS or receipt.get("decompressed") is not False:
            raise ValueError("Archive receipt is not verified: " + name)
        if not isinstance(receipt.get("sha256"), str) or len(receipt["sha256"]) != 64:
            raise ValueError("Archive receipt lacks SHA-256: " + name)
        total += identity["bytes"]
        checked = dict(asset)
        checked["sha256"] = receipt["sha256"]
        verified.append(checked)
    source_receipt = read_json(archives / "download-receipt.json")
    if source_receipt.get("status") != REQUIRED_SOURCE_STATUS or source_receipt.get("decompressed") is not False:
        raise ValueError("Database download receipt is not an archive-only verified receipt")
    if source_receipt.get("scientific_gate") != "CLOSED" or total != manifest["total_bytes"]:
        raise ValueError("Database source release guard or total differs")
    return verified


def begin_source(archive: Path, expected: dict) -> tuple[HashingFile, ZstdReader]:
    source = HashingFile(archive)
    try:
        library = _load_zstd()
        return source, ZstdReader(source, library)
    except Exception:
        source.close()
        raise


def finish_source(source: HashingFile, expected: dict) -> None:
    try:
        if source.bytes != expected["identity"]["bytes"] or source.digest.hexdigest() != expected.get("sha256"):
            raise ValueError("Compressed source SHA-256/size differs: " + expected["file"])
    finally:
        source.close()


def stream_fasta(archive: Path, expected: dict, target: Path) -> dict:
    source, decoder = begin_source(archive, expected)
    digest = hashlib.sha256()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            size = _copy_decoded(decoder, output, digest)
    finally:
        decoder.close()
    finish_source(source, expected)
    return {"path": target.name, "size_bytes": size, "sha256": digest.hexdigest(), "source_archive": archive.name}


def extract_tar(archive: Path, expected: dict, target: Path) -> list[dict]:
    source, decoder = begin_source(archive, expected)
    files: list[dict] = []
    seen: dict[str, str] = {}
    try:
        target.mkdir(parents=True, exist_ok=True)
        with io.BufferedReader(decoder, buffer_size=IO_BUFFER_SIZE) as stream, tarfile.open(fileobj=stream, mode="r|") as tar:
            for member in tar:
                relative = safe_relative(member.name)
                key = relative.as_posix()
                kind = "dir" if member.isdir() else "file" if member.isfile() else "other"
                if key in seen:
                    raise ValueError("Duplicate tar member: " + key)
                if kind == "other" or member.issym() or member.islnk() or member.isdev():
                    raise ValueError("Unsupported tar member type: " + key)
                seen[key] = kind
                destination = target.joinpath(*relative.parts)
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=False)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise ValueError("Tar member has no readable data: " + key)
                with destination.open("xb") as output:
                    size = 0
                    last_flush = 0
                    while chunk := extracted.read(READ_SIZE):
                        output.write(chunk); digest.update(chunk); size += len(chunk)
                        last_flush = _flush_output(output, size, last_flush)
                files.append({"path": key, "size_bytes": size, "sha256": digest.hexdigest(), "source_archive": archive.name})
    finally:
        decoder.close()
    finish_source(source, expected)
    return files


def atomic_json(path: Path, value: dict) -> None:
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pending.replace(path)


def extract(archives: Path, output: Path, manifest_path: Path, run_id: str = "r01") -> dict:
    archives, output, manifest_path = archives.resolve(), output.resolve(), manifest_path.resolve()
    if output.exists() or output.with_name(output.name + ".partial").exists():
        raise ValueError("Output or partial output already exists; refusing overwrite")
    if shutil.disk_usage(archives).free < EXPANDED_ESTIMATE_BYTES + RESERVE_BYTES:
        raise ValueError("Insufficient PVC space for AF3 extraction planning bound")
    assets = verify_source_manifest(archives, manifest_path)
    staging = output.with_name(output.name + ".partial")
    staging.mkdir(parents=False)
    records = []
    try:
        print("AF3_DATABASE_EXTRACTION_START", len(assets), flush=True)
        for index, asset in enumerate(assets, 1):
            name = asset["file"]; archive = archives / name
            print("AF3_DATABASE_EXTRACTION_FILE", index, len(assets), name, flush=True)
            if name == "pdb_2022_09_28_mmcif_files.tar.zst":
                records.extend(extract_tar(archive, asset, staging))
            else:
                target_name = name[:-4]
                records.append(stream_fasta(archive, asset, staging / target_name))
        records.sort(key=lambda row: row["path"])
        atomic_json(staging / "extracted-manifest.json", {"schema": "t01.af3-database-extraction/1", "files": records})
        output.parent.mkdir(parents=True, exist_ok=True)
        staging.rename(output)
        receipt = {"status": REQUIRED_OUTPUT_STATUS, "scientific_gate": "CLOSED", "decompressed": True,
                   "source_manifest": str(manifest_path.name), "output_root": output.name,
                   "file_count": len(records), "total_bytes": sum(row["size_bytes"] for row in records),
                   "files_manifest": "extracted-manifest.json"}
        atomic_json(archives.parent / "extraction-receipt.json", receipt)
        print("AF3_DATABASES_EXTRACTED_VERIFIED", len(records), receipt["total_bytes"], flush=True)
        return receipt
    except Exception:
        print("AF3_DATABASE_EXTRACTION_FAILED_PARTIAL_RETAINED", staging, flush=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--run-id", default="r01")
    args = parser.parse_args()
    result = extract(args.archives, args.output, args.manifest, args.run_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
