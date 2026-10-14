"""Inspect the pinned AF3 runtime without mounting models, databases, or GPUs."""
from __future__ import annotations

import hashlib
from importlib import import_module, metadata
import json
import os
from pathlib import Path
import subprocess
import sys


EXPECTED_PACKAGES = {
    "alphafold3": "3.0.2",
    "jax": "0.9.1",
    "jaxlib": "0.9.1",
    "jax-cuda12-plugin": "0.9.1",
    "numpy": "2.4.1",
    "nvidia-cudnn-cu12": "9.17.1.4",
    "rdkit": "2025.9.4",
}
EXPECTED_MODULES = (
    "alphafold3.common.folding_input",
    "alphafold3.data.pipeline",
    "alphafold3.model.model",
)
HMMER_BINARIES = ("hmmalign", "hmmbuild", "hmmsearch", "jackhmmer", "nhmmer")
EXPECTED_HELP_FLAGS = (
    "--model_dir",
    "--db_dir",
    "--[no]run_data_pipeline",
    "--[no]run_inference",
)
DATA_FILES = (
    Path("/app/alphafold/src/alphafold3/constants/converters/ccd.pickle"),
    Path("/app/alphafold/src/alphafold3/constants/converters/chemical_component_sets.pickle"),
)


def file_identity(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}


def command_output(
    command: list[str], timeout: int = 30, accepted_returncodes: tuple[int, ...] = (0,)
) -> str:
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        env={**os.environ, "CUDA_VISIBLE_DEVICES": "", "JAX_PLATFORMS": "cpu"},
    )
    if result.returncode not in accepted_returncodes:
        raise RuntimeError(f"Command failed ({result.returncode}): {command!r}\n{result.stdout[-2000:]}")
    return result.stdout


def inspect() -> dict[str, object]:
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(f"Expected Python 3.12, got {sys.version}")

    packages = {name: metadata.version(name) for name in EXPECTED_PACKAGES}
    if packages != EXPECTED_PACKAGES:
        raise RuntimeError(f"Package identity mismatch: {packages!r}")

    for module_name in EXPECTED_MODULES:
        import_module(module_name)

    hmmer = {}
    for name in HMMER_BINARIES:
        path = Path("/hmmer/bin") / name
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f"Missing HMMER executable: {path}")
        hmmer[name] = str(path)
    jackhmmer_help = command_output([hmmer["jackhmmer"], "-h"])
    if "HMMER 3.4" not in jackhmmer_help:
        raise RuntimeError("jackhmmer does not report HMMER 3.4")

    data_files = []
    for path in DATA_FILES:
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Missing build_data output: {path}")
        data_files.append(file_identity(path))

    entrypoint = Path("/app/alphafold/run_alphafold.py")
    if not entrypoint.is_file():
        raise RuntimeError(f"Missing AF3 entry point: {entrypoint}")
    # Abseil help flags intentionally exit with status 1 after printing help.
    help_text = command_output(
        [sys.executable, str(entrypoint), "--helpshort"],
        timeout=90,
        accepted_returncodes=(0, 1),
    )
    for flag in EXPECTED_HELP_FLAGS:
        if flag not in help_text:
            raise RuntimeError(f"AF3 help is missing {flag}")

    return {
        "schema": "t01.af3-environment-inspection/1",
        "status": "AF3_ENVIRONMENT_VERIFIED_NOT_LOADED",
        "image_loaded": True,
        "weights_loaded": False,
        "databases_mounted": False,
        "gpu_requested": False,
        "python": sys.version.split()[0],
        "packages": packages,
        "modules": list(EXPECTED_MODULES),
        "hmmer": hmmer,
        "build_data": data_files,
        "entrypoint": str(entrypoint),
        "device_nodes": sorted(str(path) for path in Path("/dev").glob("nvidia*")),
        "scientific_gate": "CLOSED",
        "usable_for_pipeline": False,
        "production_status": "NOT_DEPLOYED",
    }


def main() -> None:
    result = inspect()
    print("AF3_ENVIRONMENT_INSPECTION " + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
