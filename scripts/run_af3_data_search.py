"""Run and verify the pinned AF3 local data pipeline for the 1UBQ acceptance input."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

try:
    import resource
except ImportError:  # Windows test environment; the acceptance container is Linux.
    resource = None


RUN_ID = "data-search-r01"
RUN_ROOT = Path("/runtime") / RUN_ID
INPUT_SOURCE = Path("/input/fold_input.json")
DATABASE_ROOT = Path("/databases/alphafold3-v3.0/unpacked-r03")
MODEL_ROOT = Path("/weights/alphafold3-official-r01")
MODEL_FILE = MODEL_ROOT / "af3.bin"
MODEL_SHA256 = "df8bbf2621f17dd3ee21c2a921e84a50bc2b80cdc0c7971cb915c2826fee1f9b"
SEQUENCE = (
    "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"
)
SEQUENCE_SHA256 = "233b4b0b8c4616095bc3249f9375fc345d32af7deaef07117d0383c51d6f19aa"
REQUIRED_DATABASES = (
    "pdb_seqres_2022_09_28.fasta",
    "rfam_14_9_clust_seq_id_90_cov_80_rep_seq.fasta",
    "rnacentral_active_seq_id_90_cov_80_linclust.fasta",
    "bfd-first_non_consensus_sequences.fasta",
    "nt_rna_2023_02_23_clust_seq_id_90_cov_80_rep_seq.fasta",
    "uniref90_2022_05.fa",
    "uniprot_all_2021_04.fa",
    "mgy_clusters_2022_05.fa",
    "mmcif_files",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def atomic_json(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def cgroup_memory() -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for name in ("memory.current", "memory.peak"):
        path = Path("/sys/fs/cgroup") / name
        try:
            value = path.read_text(encoding="ascii").strip()
            result[name.replace(".", "_") + "_bytes"] = None if value == "max" else int(value)
        except (FileNotFoundError, PermissionError, ValueError):
            result[name.replace(".", "_") + "_bytes"] = None
    return result


def validate_input(value: dict[str, object]) -> None:
    if value.get("dialect") != "alphafold3" or value.get("version") != 1:
        raise ValueError("Expected pinned alphafold3 input dialect version 1")
    if value.get("modelSeeds") != [1]:
        raise ValueError("Expected the pinned model seed [1]")
    sequences = value.get("sequences")
    if not isinstance(sequences, list) or len(sequences) != 1:
        raise ValueError("Expected exactly one protein chain")
    protein = sequences[0].get("protein") if isinstance(sequences[0], dict) else None
    if not isinstance(protein, dict) or protein.get("id") != "A" or protein.get("sequence") != SEQUENCE:
        raise ValueError("Pinned 1UBQ chain differs")
    if "unpairedMsa" in protein or "pairedMsa" in protein:
        raise ValueError("MSA fields must be unset so AF3 builds them locally")
    if hashlib.sha256(SEQUENCE.encode()).hexdigest() != SEQUENCE_SHA256:
        raise ValueError("Pinned sequence hash differs")


def validate_processed_data(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    sequences = value.get("sequences")
    if not isinstance(sequences, list) or len(sequences) != 1:
        raise ValueError(f"Processed AF3 input has unexpected sequence count: {path}")
    protein = sequences[0].get("protein") if isinstance(sequences[0], dict) else None
    if not isinstance(protein, dict) or protein.get("sequence") != SEQUENCE:
        raise ValueError(f"Processed AF3 input sequence differs: {path}")
    unpaired = protein.get("unpairedMsa")
    paired = protein.get("pairedMsa")
    templates = protein.get("templates")
    if not isinstance(unpaired, str) or not unpaired:
        raise ValueError("Local data pipeline did not produce an unpaired MSA")
    if not isinstance(paired, str):
        raise ValueError("Local data pipeline did not materialize paired MSA state")
    if not isinstance(templates, list):
        raise ValueError("Local data pipeline did not materialize template state")
    return {
        "path": path.relative_to(RUN_ROOT).as_posix(),
        "unpaired_msa_bytes": len(unpaired.encode()),
        "paired_msa_bytes": len(paired.encode()),
        "template_count": len(templates),
    }


def run() -> dict[str, object]:
    if RUN_ROOT.exists():
        raise FileExistsError(f"Refusing to reuse AF3 run directory: {RUN_ROOT}")
    input_dir = RUN_ROOT / "input"
    output_dir = RUN_ROOT / "output"
    tmp_dir = RUN_ROOT / "tmp"
    input_dir.mkdir(parents=True)
    output_dir.mkdir()
    tmp_dir.mkdir()

    input_value = json.loads(INPUT_SOURCE.read_bytes())
    validate_input(input_value)
    input_path = input_dir / "fold_input.json"
    input_path.write_bytes(INPUT_SOURCE.read_bytes())

    missing = [name for name in REQUIRED_DATABASES if not (DATABASE_ROOT / name).exists()]
    if missing:
        raise FileNotFoundError("Missing AF3 database paths: " + ", ".join(missing))
    if not MODEL_FILE.is_file() or sha256_file(MODEL_FILE) != MODEL_SHA256:
        raise ValueError("AF3 decompressed weight identity differs")

    command = [
        "/alphafold3_venv/bin/python",
        "/app/alphafold/run_alphafold.py",
        f"--json_path={input_path}",
        f"--model_dir={MODEL_ROOT}",
        f"--db_dir={DATABASE_ROOT}",
        f"--output_dir={output_dir}",
        "--run_data_pipeline=true",
        "--run_inference=false",
        "--jackhmmer_n_cpu=8",
        "--nhmmer_n_cpu=8",
        "--max_template_date=2021-09-30",
    ]
    atomic_json(
        RUN_ROOT / "command.json",
        {
            "command": command,
            "cwd": "/app/alphafold",
            "network": "DENY_ALL",
            "gpu_requested": False,
            "input_sha256": sha256_file(input_path),
            "sequence_sha256": SEQUENCE_SHA256,
            "model_sha256": MODEL_SHA256,
        },
    )

    environment = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": "",
        "JAX_PLATFORMS": "cpu",
        "HOME": str(tmp_dir),
        "TMPDIR": str(tmp_dir),
        "XDG_CACHE_HOME": str(tmp_dir / "cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    started = time.monotonic()
    log_path = RUN_ROOT / "pipeline.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd="/app/alphafold",
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            log.flush()
        returncode = process.wait()
    elapsed = time.monotonic() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN) if resource is not None else None

    if returncode != 0:
        failure = {
            "status": "AF3_LOCAL_DATA_SEARCH_FAILED_PARTIAL_RETAINED",
            "returncode": returncode,
            "elapsed_seconds": round(elapsed, 3),
            "run_root": str(RUN_ROOT),
            "scientific_gate": "CLOSED",
            "usable_for_pipeline": False,
            "production_status": "NOT_DEPLOYED",
            **cgroup_memory(),
        }
        atomic_json(RUN_ROOT / "failure-receipt.json", failure)
        print("AF3_LOCAL_DATA_SEARCH_FAILED " + json.dumps(failure, sort_keys=True), flush=True)
        raise SystemExit(returncode)

    processed_paths = sorted(output_dir.rglob("*_data.json"))
    if len(processed_paths) != 1:
        raise ValueError(f"Expected one processed AF3 data JSON, found {len(processed_paths)}")
    processed = validate_processed_data(processed_paths[0])

    files = sorted(
        path for path in RUN_ROOT.rglob("*")
        if path.is_file() and path.name not in {"files-manifest.json", "data-search-receipt.json"}
    )
    identities = [file_identity(path, RUN_ROOT) for path in files]
    manifest = {"schema": "t01.af3-data-search-files/1", "files": identities}
    atomic_json(RUN_ROOT / "files-manifest.json", manifest)
    receipt = {
        "schema": "t01.af3-data-search/1",
        "status": "AF3_LOCAL_DATA_SEARCH_VERIFIED_NOT_INFERRED",
        "run_id": RUN_ID,
        "run_root": str(RUN_ROOT),
        "elapsed_seconds": round(elapsed, 3),
        "child_user_cpu_seconds": round(usage.ru_utime, 3) if usage is not None else None,
        "child_system_cpu_seconds": round(usage.ru_stime, 3) if usage is not None else None,
        "child_max_rss_kib": int(usage.ru_maxrss) if usage is not None else None,
        "input_sha256": sha256_file(input_path),
        "sequence_sha256": SEQUENCE_SHA256,
        "model_sha256": MODEL_SHA256,
        "database_root": str(DATABASE_ROOT),
        "required_database_paths": list(REQUIRED_DATABASES),
        "processed_input": processed,
        "file_count": len(identities),
        "total_bytes": sum(int(row["bytes"]) for row in identities),
        "files_manifest_sha256": sha256_file(RUN_ROOT / "files-manifest.json"),
        "gpu_requested": False,
        "inference_run": False,
        "usable_as_inference_input": True,
        "scientific_gate": "CLOSED",
        "usable_for_pipeline": False,
        "production_status": "NOT_DEPLOYED",
        **cgroup_memory(),
    }
    atomic_json(RUN_ROOT / "data-search-receipt.json", receipt)
    print("AF3_LOCAL_DATA_SEARCH_VERIFIED " + json.dumps(receipt, sort_keys=True), flush=True)
    return receipt


if __name__ == "__main__":
    run()
