"""Independently verify the published AF3 database extraction, read-only.

The extraction Job already checked each compressed source while creating the
output.  This verifier remounts the database PVC read-only and checks the
published receipt, the complete extracted manifest, the AF3 v3.0 directory
layout, filesystem metadata, and (by default) every output SHA-256.  It never
writes to the PVC and never requests a GPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import time


REQUIRED_RECEIPT_STATUS = "AF3_DATABASES_EXTRACTED_VERIFIED_NOT_DEPLOYED"
REQUIRED_MANIFEST_SCHEMA = "t01.af3-database-extraction/1"
EXPECTED_OUTPUT_ROOT = "unpacked-r03"
EXPECTED_FILE_COUNT = 195867
EXPECTED_TOTAL_BYTES = 672435030513
REQUIRED_ROOT_FILES = (
    "pdb_seqres_2022_09_28.fasta",
    "rfam_14_9_clust_seq_id_90_cov_80_rep_seq.fasta",
    "rnacentral_active_seq_id_90_cov_80_linclust.fasta",
    "bfd-first_non_consensus_sequences.fasta",
    "nt_rna_2023_02_23_clust_seq_id_90_cov_80_rep_seq.fasta",
    "uniref90_2022_05.fa",
    "uniprot_all_2021_04.fa",
    "mgy_clusters_2022_05.fa",
)
REQUIRED_PDB_PREFIX = "mmcif_files/"
HASH_CHUNK_BYTES = 8 * 1024 * 1024


def read_json(path: Path) -> dict:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def filesystem(path: Path) -> dict:
    value = shutil.disk_usage(path)
    return {
        "total_bytes": value.total,
        "free_bytes": value.free,
        "used_bytes": value.used,
    }


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or "\\" in value or ".." in path.parts
            or path.as_posix() != value or any(part in ("", ".") for part in path.parts)):
        raise ValueError(f"Unsafe extracted path: {value!r}")
    return path


def regular_file(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise ValueError(f"Expected regular extracted file: {path}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(root: Path, *, full_hash: bool = True, progress_every: int = 10000) -> dict:
    root = root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"Database root is not a real directory: {root}")
    output = root / EXPECTED_OUTPUT_ROOT
    if not output.is_dir() or output.is_symlink():
        raise ValueError(f"Published extraction directory is missing: {output}")
    if (root / f"{EXPECTED_OUTPUT_ROOT}.partial").exists():
        raise ValueError("A partial directory remains beside the published output")

    receipt = read_json(root / "extraction-receipt.json")
    expected_receipt = {
        "status": REQUIRED_RECEIPT_STATUS,
        "scientific_gate": "CLOSED",
        "decompressed": True,
        "source_manifest": "database-manifest.json",
        "output_root": EXPECTED_OUTPUT_ROOT,
        "file_count": EXPECTED_FILE_COUNT,
        "total_bytes": EXPECTED_TOTAL_BYTES,
        "files_manifest": "extracted-manifest.json",
    }
    for key, expected in expected_receipt.items():
        if receipt.get(key) != expected:
            raise ValueError(f"Extraction receipt mismatch for {key}: {receipt.get(key)!r}")

    manifest = read_json(output / "extracted-manifest.json")
    if manifest.get("schema") != REQUIRED_MANIFEST_SCHEMA:
        raise ValueError("Unexpected extracted manifest schema")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != EXPECTED_FILE_COUNT:
        raise ValueError("Extracted manifest file count differs from the pinned receipt")

    paths: set[str] = set()
    actual_total = 0
    root_files: set[str] = set()
    mmcif_files = 0
    hashed_files = 0
    started = time.monotonic()
    for index, row in enumerate(files, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Manifest row {index} is not an object")
        relative = safe_relative(row.get("path", ""))
        name = relative.as_posix()
        if name in paths:
            raise ValueError(f"Duplicate extracted path: {name}")
        paths.add(name)
        target = output.joinpath(*relative.parts)
        regular_file(target)
        expected_size = row.get("size_bytes")
        if not isinstance(expected_size, int) or expected_size < 0:
            raise ValueError(f"Invalid size in extracted manifest: {name}")
        actual_size = target.stat().st_size
        if actual_size != expected_size:
            raise ValueError(f"Extracted size mismatch: {name}")
        expected_hash = row.get("sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise ValueError(f"Missing SHA-256 in extracted manifest: {name}")
        if any(char not in "0123456789abcdef" for char in expected_hash):
            raise ValueError(f"Invalid SHA-256 in extracted manifest: {name}")
        if full_hash and sha256_file(target) != expected_hash:
            raise ValueError(f"Extracted SHA-256 mismatch: {name}")
        actual_total += actual_size
        if "/" not in name:
            root_files.add(name)
        if name.startswith(REQUIRED_PDB_PREFIX):
            mmcif_files += 1
        hashed_files += 1 if full_hash else 0
        if progress_every and index % progress_every == 0:
            print("AF3_EXTRACTION_INSPECTION_PROGRESS", index, len(files), actual_total, flush=True)

    missing = sorted(set(REQUIRED_ROOT_FILES) - root_files)
    if missing:
        raise ValueError("Missing AF3 root database files: " + ", ".join(missing))
    if mmcif_files == 0:
        raise ValueError("No extracted mmcif_files/ members were found")
    if actual_total != EXPECTED_TOTAL_BYTES:
        raise ValueError(f"Extracted byte total differs: {actual_total}")
    if len(paths) != EXPECTED_FILE_COUNT:
        raise ValueError("Extracted path inventory is not unique")

    disk = filesystem(root)
    elapsed = time.monotonic() - started
    result = {
        "status": "AF3_DATABASES_EXTRACTION_INDEPENDENTLY_VERIFIED_NOT_DEPLOYED",
        "scientific_gate": "CLOSED",
        "usable_for_pipeline": False,
        "production_status": "NOT_DEPLOYED",
        "output_root": EXPECTED_OUTPUT_ROOT,
        "file_count": len(files),
        "total_bytes": actual_total,
        "required_root_files": list(REQUIRED_ROOT_FILES),
        "mmcif_file_count": mmcif_files,
        "hash_mode": "full" if full_hash else "metadata_only",
        "hashed_file_count": hashed_files,
        "elapsed_seconds": round(elapsed, 3),
        "database_filesystem": disk,
    }
    print("AF3_EXTRACTION_INSPECTION_VERIFIED " + json.dumps(result, sort_keys=True), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="PVC root containing alphafold3-v3.0")
    parser.add_argument("--metadata-only", action="store_true",
                        help="Skip re-hashing file contents; not used by the acceptance Job")
    parser.add_argument("--progress-every", type=int, default=10000)
    args = parser.parse_args()
    if args.progress_every < 0:
        parser.error("--progress-every must be non-negative")
    inspect(args.root, full_hash=not args.metadata_only, progress_every=args.progress_every)


if __name__ == "__main__":
    main()
