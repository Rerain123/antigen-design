"""Independently verify a completed AF3 local data-search run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat


RUN_ROOT = Path("/runtime/data-search-r01")
EXPECTED_STATUS = "AF3_LOCAL_DATA_SEARCH_VERIFIED_NOT_INFERRED"
EXPECTED_SEQUENCE_SHA256 = "233b4b0b8c4616095bc3249f9375fc345d32af7deaef07117d0383c51d6f19aa"
EXPECTED_MODEL_SHA256 = "df8bbf2621f17dd3ee21c2a921e84a50bc2b80cdc0c7971cb915c2826fee1f9b"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or "\\" in value or ".." in path.parts or path.as_posix() != value:
        raise ValueError(f"Unsafe manifest path: {value!r}")
    return path


def inspect() -> dict[str, object]:
    receipt_path = RUN_ROOT / "data-search-receipt.json"
    manifest_path = RUN_ROOT / "files-manifest.json"
    receipt = json.loads(receipt_path.read_bytes())
    for key, expected in {
        "schema": "t01.af3-data-search/1",
        "status": EXPECTED_STATUS,
        "run_id": "data-search-r01",
        "sequence_sha256": EXPECTED_SEQUENCE_SHA256,
        "model_sha256": EXPECTED_MODEL_SHA256,
        "inference_run": False,
        "gpu_requested": False,
        "usable_as_inference_input": True,
        "scientific_gate": "CLOSED",
        "usable_for_pipeline": False,
        "production_status": "NOT_DEPLOYED",
    }.items():
        if receipt.get(key) != expected:
            raise ValueError(f"Receipt mismatch for {key}: {receipt.get(key)!r}")
    command = json.loads((RUN_ROOT / "command.json").read_bytes())
    command_text = " ".join(command.get("command", []))
    if "--run_data_pipeline=true" not in command_text or "--run_inference=false" not in command_text:
        raise ValueError("Command does not separate data search from inference")

    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("schema") != "t01.af3-data-search-files/1":
        raise ValueError("Unexpected data-search manifest schema")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Data-search manifest is empty")
    seen: set[str] = set()
    total = 0
    for row in rows:
        relative = safe_path(row.get("path", ""))
        name = relative.as_posix()
        if name in seen:
            raise ValueError(f"Duplicate data-search path: {name}")
        seen.add(name)
        path = RUN_ROOT.joinpath(*relative.parts)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink():
            raise ValueError(f"Expected regular data-search file: {path}")
        if info.st_size != row.get("bytes") or sha256_file(path) != row.get("sha256"):
            raise ValueError(f"Data-search file identity mismatch: {name}")
        total += info.st_size
    if sha256_file(manifest_path) != receipt.get("files_manifest_sha256"):
        raise ValueError("Data-search manifest receipt hash mismatch")

    processed = RUN_ROOT / "output/t01-1ubq-af3-data-r01/t01-1ubq-af3-data-r01_data.json"
    value = json.loads(processed.read_bytes())
    protein = value["sequences"][0]["protein"]
    if len(protein["sequence"]) != 76 or not protein["unpairedMsa"] or not isinstance(protein["pairedMsa"], str):
        raise ValueError("Processed input is missing the expected protein MSA fields")
    templates = protein.get("templates")
    if not isinstance(templates, list) or len(templates) != receipt["processed_input"]["template_count"]:
        raise ValueError("Processed template count mismatch")
    result = {
        "schema": "t01.af3-data-search-inspection/1",
        "status": "AF3_LOCAL_DATA_SEARCH_INDEPENDENTLY_VERIFIED_NOT_INFERRED",
        "scientific_gate": "CLOSED",
        "usable_as_inference_input": True,
        "usable_for_pipeline": False,
        "production_status": "NOT_DEPLOYED",
        "file_count": len(rows),
        "total_bytes": total,
        "processed_input": receipt["processed_input"],
        "database_filesystem": {
            "total_bytes": shutil.disk_usage(RUN_ROOT).total,
            "free_bytes": shutil.disk_usage(RUN_ROOT).free,
        },
    }
    print("AF3_LOCAL_DATA_SEARCH_INSPECTION_VERIFIED " + json.dumps(result, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    inspect()
