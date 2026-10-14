"""Read-only AF3 archive/receipt and PVC-space inspection.

This deliberately does not decompress or hash the 238 GB database payloads.
The downloader already recorded full-stream MD5/SHA-256 verification; this
step independently remounts both PVCs, checks identities/sizes/receipts and
reports actual filesystem capacity before an extraction job is prepared.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat


WEIGHT_FILE = "af3.bin.zst"
WEIGHT_BYTES = 1_020_545_840
WEIGHT_SHA256 = "74d0258616917cd122f5eab6d076afe4a8930e96823851e65e4f777dfb1f33ff"
OFFICIAL_EXPANDED_ESTIMATE_BYTES = 630_000_000_000
PLANNING_RESERVE_BYTES = 64 * 1024**3


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def regular_file(path: Path, size: int | None = None) -> None:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise ValueError(f"Expected regular file: {path.name}")
    if size is not None and info.st_size != size:
        raise ValueError(f"Unexpected size: {path.name}")


def filesystem(path: Path) -> dict:
    value = os.statvfs(path)
    return {
        "total_bytes": value.f_blocks * value.f_frsize,
        "free_bytes": value.f_bavail * value.f_frsize,
        "used_bytes": (value.f_blocks - value.f_bfree) * value.f_frsize,
    }


def inspect(databases: Path, weights: Path, manifest_path: Path) -> dict:
    databases, weights = databases.resolve(), weights.resolve()
    manifest = read_json(manifest_path)
    if manifest["schema"] != "t01.af3-database-download/1" or manifest["archives_only"] is not True:
        raise ValueError("Unexpected pinned database manifest")
    if read_json(databases / "database-manifest.json") != manifest:
        raise ValueError("PVC database manifest differs from the pinned manifest")
    receipt = read_json(databases / "download-receipt.json")
    if receipt.get("status") != "DATABASE_ARCHIVES_VERIFIED_NOT_DEPLOYED":
        raise ValueError("Database download receipt is not verified")
    if receipt.get("decompressed") is not False or receipt.get("scientific_gate") != "CLOSED":
        raise ValueError("Database receipt release guards differ")
    receipt_assets = {row["file"]: row for row in receipt["assets"]}
    expected_names = {row["file"] for row in manifest["assets"]}
    if set(receipt_assets) != expected_names:
        raise ValueError("Database receipt inventory differs from the pinned manifest")
    rows = []
    for asset in manifest["assets"]:
        name, identity = asset["file"], asset["identity"]
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError("Unsafe archive name")
        archive = databases / name
        regular_file(archive, identity["bytes"])
        if (databases / f"{name}.partial").exists():
            raise ValueError(f"Partial archive remains: {name}")
        if read_json(databases / f"{name}.source.json") != identity:
            raise ValueError(f"Source identity differs: {name}")
        per_file = read_json(databases / f"{name}.receipt.json")
        if per_file != receipt_assets[name]:
            raise ValueError(f"Per-file receipt differs: {name}")
        if any(per_file.get(key) != value for key, value in identity.items()):
            raise ValueError(f"Pinned identity differs in receipt: {name}")
        if (per_file.get("status"), per_file.get("official_md5_verified"),
                per_file.get("decompressed"), per_file.get("scientific_gate")) != (
                "ARCHIVE_VERIFIED_NOT_DEPLOYED", True, False, "CLOSED"):
            raise ValueError(f"Archive verification guard differs: {name}")
        if not re.fullmatch(r"[0-9a-f]{64}", per_file.get("sha256", "")):
            raise ValueError(f"Missing archive SHA-256: {name}")
        rows.append({"file": name, "bytes": archive.stat().st_size, "sha256": per_file["sha256"]})
    if sum(row["bytes"] for row in rows) != manifest["total_bytes"]:
        raise ValueError("Database archive byte total differs")

    weight_receipt = read_json(weights / "download-receipt.json")
    regular_file(weights / WEIGHT_FILE, WEIGHT_BYTES)
    if (weights / f"{WEIGHT_FILE}.partial").exists():
        raise ValueError("Partial weight archive remains")
    if (weight_receipt.get("file"), weight_receipt.get("bytes"), weight_receipt.get("sha256")) != (
            WEIGHT_FILE, WEIGHT_BYTES, WEIGHT_SHA256):
        raise ValueError("Weight receipt identity differs")
    if (weight_receipt.get("status"), weight_receipt.get("official_crc32c_verified"),
            weight_receipt.get("decompressed"), weight_receipt.get("scientific_gate")) != (
            "WEIGHTS_DOWNLOADED_VERIFIED_NOT_DEPLOYED", True, False, "CLOSED"):
        raise ValueError("Weight verification guard differs")

    database_fs = filesystem(databases)
    weights_fs = filesystem(weights)
    planning_need = OFFICIAL_EXPANDED_ESTIMATE_BYTES + PLANNING_RESERVE_BYTES
    return {
        "status": "AF3_ASSETS_MOUNTED_RECEIPTS_AND_SIZES_VERIFIED_NOT_EXTRACTED",
        "database_archives": {"count": len(rows), "bytes": sum(row["bytes"] for row in rows), "files": rows},
        "database_filesystem": database_fs,
        "extraction_space_planning": {
            "official_approximate_expanded_bytes": OFFICIAL_EXPANDED_ESTIMATE_BYTES,
            "reserve_bytes": PLANNING_RESERVE_BYTES,
            "required_planning_free_bytes": planning_need,
            "provisionally_sufficient": database_fs["free_bytes"] >= planning_need,
            "note": "Planning check only; exact expanded size must be measured and bounded by the extraction job.",
        },
        "weights": {"file": WEIGHT_FILE, "bytes": WEIGHT_BYTES, "sha256": WEIGHT_SHA256},
        "weights_filesystem": weights_fs,
        "scientific_gate": "CLOSED",
        "usable_for_pipeline": False,
        "production_status": "NOT_DEPLOYED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("databases", type=Path)
    parser.add_argument("weights", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    result = inspect(args.databases, args.weights, args.manifest)
    print("AF3_ASSET_INSPECTION " + json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
