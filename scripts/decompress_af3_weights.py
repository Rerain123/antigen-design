"""Safely decompress the pinned official AlphaFold 3 weights.

The verified ``af3.bin.zst`` source is retained.  The decoded file is written
to a staging name, bounded in size, hashed while it is written, fsynced, and
then atomically published as ``af3.bin``.  This step does not load the model,
request a GPU, or open the scientific gate.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Callable, Iterable


SOURCE_NAME = "af3.bin.zst"
TARGET_NAME = "af3.bin"
PARTIAL_NAME = "af3.bin.partial"
DOWNLOAD_RECEIPT = "download-receipt.json"
INSTALLATION_RECEIPT = "installation-receipt.json"
EXPECTED_SOURCE_BYTES = 1_020_545_840
EXPECTED_SOURCE_SHA256 = "74d0258616917cd122f5eab6d076afe4a8930e96823851e65e4f777dfb1f33ff"
MAX_OUTPUT_BYTES = 8 * 1024**3
RESERVE_BYTES = 2 * 1024**3
READ_SIZE = 1024 * 1024
CACHE_FLUSH_BYTES = 1024**3


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
    library.ZSTD_decompressStream.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ZSTDOutBuffer), ctypes.POINTER(ZSTDInBuffer)
    ]
    library.ZSTD_decompressStream.restype = ctypes.c_size_t
    library.ZSTD_isError.argtypes = [ctypes.c_size_t]
    library.ZSTD_isError.restype = ctypes.c_uint
    library.ZSTD_getErrorName.argtypes = [ctypes.c_size_t]
    library.ZSTD_getErrorName.restype = ctypes.c_char_p
    return library


class ZstdReader(io.RawIOBase):
    def __init__(self, source):
        self.source = source
        self.library = _load_zstd()
        self.context = self.library.ZSTD_createDStream()
        if not self.context:
            raise RuntimeError("libzstd could not create a decompression stream")
        self._check(self.library.ZSTD_initDStream(self.context))
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
        state = ZSTDOutBuffer(ctypes.cast(output, ctypes.c_void_p), len(target), 0)
        while state.pos == 0 and not self.eof:
            if self.input_state.pos >= self.input_state.size:
                self.input = self.source.read(READ_SIZE)
                if self.input:
                    self.input_buffer = ctypes.create_string_buffer(self.input)
                    self.input_state = ZSTDInBuffer(
                        ctypes.cast(self.input_buffer, ctypes.c_void_p), len(self.input), 0
                    )
                    self.frame_complete = False
                else:
                    if self.frame_complete:
                        self.eof = True
                        break
                    self.input_state = ZSTDInBuffer(None, 0, 0)
            result = self.library.ZSTD_decompressStream(
                self.context, ctypes.byref(state), ctypes.byref(self.input_state)
            )
            self._check(result)
            if result == 0:
                self.frame_complete = True
            elif not self.input and self.input_state.pos >= self.input_state.size and state.pos == 0:
                raise ValueError("zstd stream ended before a complete frame")
        size = int(state.pos)
        if size:
            target[:size] = bytes(output[:size])
        return size

    def close(self) -> None:
        if getattr(self, "context", None):
            self.library.ZSTD_freeDStream(self.context)
            self.context = None
        super().close()


def regular_file(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise ValueError(f"Expected a regular file: {path}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(READ_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def atomic_json(path: Path, value: dict) -> None:
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pending.replace(path)


def zstd_chunks(source: Path) -> Iterable[bytes]:
    buffer = bytearray(READ_SIZE)
    with source.open("rb") as raw, ZstdReader(raw) as decoded:
        while count := decoded.readinto(buffer):
            yield bytes(memoryview(buffer)[:count])


def verify_source(root: Path) -> Path:
    source = root / SOURCE_NAME
    regular_file(source)
    if source.stat().st_size != EXPECTED_SOURCE_BYTES:
        raise ValueError("Pinned AF3 weight archive size differs")
    receipt = read_json(root / DOWNLOAD_RECEIPT)
    expected = {
        "file": SOURCE_NAME,
        "bytes": EXPECTED_SOURCE_BYTES,
        "sha256": EXPECTED_SOURCE_SHA256,
        "status": "WEIGHTS_DOWNLOADED_VERIFIED_NOT_DEPLOYED",
        "decompressed": False,
        "scientific_gate": "CLOSED",
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise ValueError(f"AF3 weight download receipt mismatch for {key}")
    if sha256_file(source) != EXPECTED_SOURCE_SHA256:
        raise ValueError("Pinned AF3 weight archive SHA-256 differs")
    return source


def verify_existing(root: Path, source: Path) -> dict:
    target = root / TARGET_NAME
    regular_file(target)
    receipt = read_json(root / INSTALLATION_RECEIPT)
    expected = {
        "schema": "t01.af3-weight-installation/1",
        "status": "AF3_WEIGHTS_DECOMPRESSED_VERIFIED_NOT_LOADED",
        "source_file": SOURCE_NAME,
        "source_bytes": EXPECTED_SOURCE_BYTES,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "target_file": TARGET_NAME,
        "decompressed": True,
        "model_loaded": False,
        "scientific_gate": "CLOSED",
        "usable_for_pipeline": False,
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise ValueError(f"AF3 weight installation receipt mismatch for {key}")
    if target.stat().st_size != receipt.get("target_bytes"):
        raise ValueError("Installed AF3 weight size differs from its receipt")
    if sha256_file(target) != receipt.get("target_sha256"):
        raise ValueError("Installed AF3 weight SHA-256 differs from its receipt")
    return receipt


def _flush_output(output, written: int, last_flush: int) -> int:
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
            pass
    return written


def decompress(
    root: Path,
    chunk_source: Callable[[Path], Iterable[bytes]] = zstd_chunks,
) -> dict:
    root = root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("AF3 weight root must be an existing real directory")
    source = verify_source(root)
    target = root / TARGET_NAME
    partial = root / PARTIAL_NAME
    if target.exists():
        if partial.exists():
            raise ValueError("Published and partial AF3 weights both exist")
        result = verify_existing(root, source)
        print("AF3_WEIGHTS_ALREADY_DECOMPRESSED_VERIFIED " + json.dumps(result, sort_keys=True), flush=True)
        return result
    if partial.exists():
        raise ValueError("A prior AF3 weight partial is retained; refusing overwrite")
    if shutil.disk_usage(root).free < MAX_OUTPUT_BYTES + RESERVE_BYTES:
        raise ValueError("Insufficient free space for bounded AF3 weight decompression")

    digest = hashlib.sha256()
    written = 0
    last_flush = 0
    print("AF3_WEIGHT_DECOMPRESSION_START", EXPECTED_SOURCE_BYTES, flush=True)
    try:
        with partial.open("xb") as output:
            for chunk in chunk_source(source):
                if not isinstance(chunk, (bytes, bytearray, memoryview)) or not chunk:
                    raise ValueError("Weight decoder yielded an invalid chunk")
                if written + len(chunk) > MAX_OUTPUT_BYTES:
                    raise ValueError("Decoded AF3 weights exceed the fixed safety bound")
                output.write(chunk)
                digest.update(chunk)
                written += len(chunk)
                last_flush = _flush_output(output, written, last_flush)
            output.flush()
            os.fsync(output.fileno())
        if written <= 0:
            raise ValueError("Decoded AF3 weight file is empty")
        partial.replace(target)
        receipt = {
            "schema": "t01.af3-weight-installation/1",
            "status": "AF3_WEIGHTS_DECOMPRESSED_VERIFIED_NOT_LOADED",
            "source_file": SOURCE_NAME,
            "source_bytes": EXPECTED_SOURCE_BYTES,
            "source_sha256": EXPECTED_SOURCE_SHA256,
            "target_file": TARGET_NAME,
            "target_bytes": written,
            "target_sha256": digest.hexdigest(),
            "decompressed": True,
            "model_loaded": False,
            "scientific_gate": "CLOSED",
            "usable_for_pipeline": False,
            "production_status": "NOT_DEPLOYED",
        }
        atomic_json(root / INSTALLATION_RECEIPT, receipt)
        print("AF3_WEIGHTS_DECOMPRESSED_VERIFIED " + json.dumps(receipt, sort_keys=True), flush=True)
        return receipt
    except Exception:
        print("AF3_WEIGHT_DECOMPRESSION_FAILED_PARTIAL_RETAINED", partial, flush=True)
        raise


def main() -> None:
    import fcntl

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    with (args.root / ".installation.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        decompress(args.root)


if __name__ == "__main__":
    main()
