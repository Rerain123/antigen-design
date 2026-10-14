"""Offline ESMFold2 standard worker for the t01.structure-worker/0.1 contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - Windows only; worker runs on Linux.
    resource = None


AA20 = frozenset("ACDEFGHIKLMNPQRSTVWY")
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".new")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("contract_version") != "t01.structure-worker/0.1":
        raise ValueError("Unsupported profile contract_version")
    if profile.get("engine") != "esmfold2" or profile.get("variant") != "standard":
        raise ValueError("Profile must select ESMFold2 standard")
    if profile.get("scientific_gate") != "CLOSED":
        raise ValueError("Engineering profile must keep the scientific gate closed")
    if profile.get("network") != "disabled":
        raise ValueError("ESMFold2 profile must require disabled networking")
    if not SHA256.fullmatch(str(profile.get("asset_manifest_sha256", ""))):
        raise ValueError("Invalid asset manifest hash")
    if not SHA256.fullmatch(str(profile.get("environment_manifest_sha256", ""))):
        raise ValueError("Invalid environment manifest hash")


def validate_request(request: dict[str, Any], profile: dict[str, Any]) -> None:
    if request.get("contract_version") != "t01.structure-worker/0.1":
        raise ValueError("Unsupported request contract_version")
    for key in ("request_id",):
        if not SAFE_ID.fullmatch(str(request.get(key, ""))):
            raise ValueError(f"Invalid {key}")
    if request.get("engine") != "esmfold2":
        raise ValueError("Request engine does not match worker")
    if request.get("asset_profile_id") != profile.get("id"):
        raise ValueError("Request asset_profile_id does not match profile")
    inputs = request.get("inputs")
    parameters = request.get("parameters")
    if not isinstance(inputs, dict) or not isinstance(parameters, dict):
        raise ValueError("inputs and parameters must be objects")
    if not SAFE_ID.fullmatch(str(inputs.get("sequence_id", ""))):
        raise ValueError("Invalid sequence_id")
    sequence = inputs.get("sequence")
    if not isinstance(sequence, str) or not sequence or set(sequence) - AA20:
        raise ValueError("sequence must be non-empty uppercase AA20")
    if len(sequence) > int(profile["max_sequence_length"]):
        raise ValueError("sequence exceeds the verified engineering limit")
    if not isinstance(inputs.get("host_species"), str) or not inputs["host_species"].strip():
        raise ValueError("host_species is required")
    if inputs.get("chain_id") != "A":
        raise ValueError("The initial worker supports chain A only")
    if parameters.get("seed") != int(parameters.get("seed", -1)) or int(parameters["seed"]) < 0:
        raise ValueError("seed must be a non-negative integer")
    if parameters.get("num_samples") != 1:
        raise ValueError("ESMFold2 initial worker requires one sample")
    if parameters.get("msa_mode") != "none" or parameters.get("prepared_input") is not None:
        raise ValueError("Initial engineering profile only supports explicit msa_mode=none")
    timeout = parameters.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout <= 0 or timeout > int(profile["max_timeout_seconds"]):
        raise ValueError("timeout_seconds is outside the profile limit")


def verify_assets(profile: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    root = Path(profile["asset_root"])
    manifest_path = root / "asset-manifest.json"
    if sha256_file(manifest_path) != profile["asset_manifest_sha256"]:
        raise ValueError("Asset manifest hash mismatch")
    manifest = read_json(manifest_path)
    if manifest.get("status") != "ASSETS_DOWNLOADED_NOT_DEPLOYED":
        raise ValueError("Unexpected source asset state")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 23:
        raise ValueError("Expected the complete 23-file standard asset set")
    for row in files:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe asset path")
        path = root / relative
        if path.stat().st_size != row["bytes"] or sha256_file(path) != row["sha256"]:
            raise ValueError(f"Asset integrity mismatch: {relative.as_posix()}")
    return root, manifest


def verify_environment(profile: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    root = Path(profile["environment_root"])
    manifest_path = root / "environment-pvc-manifest.json"
    if sha256_file(manifest_path) != profile["environment_manifest_sha256"]:
        raise ValueError("Environment manifest hash mismatch")
    manifest = read_json(manifest_path)
    if manifest.get("id") != "esmfold2-python312-cu126-pvc-r01":
        raise ValueError("Unexpected environment id")
    if manifest.get("scientific_gate") != "CLOSED":
        raise ValueError("Environment manifest must keep the scientific gate closed")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Environment source files are missing")
    for row in files:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe environment source path")
        path = root / relative
        if path.is_symlink() or path.stat().st_size != row["bytes"] or sha256_file(path) != row["sha256"]:
            raise ValueError(f"Environment source integrity mismatch: {relative.as_posix()}")

    extracted = manifest.get("extracted")
    if not isinstance(extracted, dict) or extracted.get("root") != "site-packages":
        raise ValueError("Unexpected extracted environment root")
    tree_manifest = read_json(root / str(extracted.get("manifest")))
    rows = tree_manifest.get("files")
    if not isinstance(rows, list) or len(rows) != extracted.get("file_count"):
        raise ValueError("Environment tree manifest count mismatch")
    site_packages = root / "site-packages"
    expected_paths: set[str] = set()
    total_bytes = 0
    for row in rows:
        relative = Path(row["path"])
        relative_posix = relative.as_posix()
        if relative.is_absolute() or ".." in relative.parts or relative_posix in expected_paths:
            raise ValueError("Unsafe or duplicate environment tree path")
        expected_paths.add(relative_posix)
        path = site_packages / relative
        if path.is_symlink() or path.stat().st_size != row["bytes"] or sha256_file(path) != row["sha256"]:
            raise ValueError(f"Environment tree integrity mismatch: {relative_posix}")
        total_bytes += row["bytes"]
    actual_paths = {
        path.relative_to(site_packages).as_posix()
        for path in site_packages.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths or total_bytes != extracted.get("total_bytes"):
        raise ValueError("Extracted environment file set mismatch")
    return root, manifest


def make_manifest(output: Path) -> dict[str, Any]:
    files = []
    for path in sorted(p for p in output.rglob("*") if p.is_file() and p.name != "manifest.json"):
        files.append(
            {
                "path": path.relative_to(output).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {"schema_version": "1.0", "files": files}


def run(request_path: Path, output: Path, profile_path: Path) -> None:
    if output.exists():
        raise ValueError("output-dir must not already exist")
    request = read_json(request_path)
    profile = read_json(profile_path)
    validate_profile(profile)
    validate_request(request, profile)
    output.mkdir(parents=False)
    started = time.time()
    try:
        asset_root, asset_manifest = verify_assets(profile)
        environment_root, environment_manifest = verify_environment(profile)
        esmfold_path = asset_root / profile["esmfold2_relative_path"]
        esmc_path = asset_root / profile["esmc_relative_path"]
        ccd_path = asset_root / profile["ccd_relative_path"]
        for path in (esmfold_path, esmc_path, ccd_path):
            if not path.exists():
                raise ValueError(f"Missing registered asset: {path.name}")

        os.environ.update(
            {
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "ESMCFOLD_CCD_PATH": str(ccd_path),
            }
        )
        import torch
        from esm.models.esmfold2 import ESMFold2InputBuilder
        from esm.utils.structure.input_builder import ProteinInput, StructurePredictionInput
        from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required")
        torch.cuda.reset_peak_memory_stats()
        from esmc_strict_loader import load_esmc_strict, require_clean_loading
        model, loading_info = ESMFold2Model.from_pretrained(
            str(esmfold_path), load_esmc=False, local_files_only=True,
            output_loading_info=True,
        )
        require_clean_loading(loading_info, "ESMFold2")
        print("ESMFOLD2_PARAMETERS_STRICTLY_LOADED missing=0 unexpected=0", flush=True)
        model = model.to("cuda").eval()
        esmc_loading = load_esmc_strict(model, esmc_path)
        atomic_json(output / "checkpoint-loading.json", {"esmfold2": loading_info, "esmc": esmc_loading})
        print("ESMFOLD2_INFERENCE_START", flush=True)
        sequence = request["inputs"]["sequence"]
        builder = ESMFold2InputBuilder()
        prediction_input = StructurePredictionInput(
            sequences=[ProteinInput(id="A", sequence=sequence, msa=None)]
        )
        result = builder.fold(
            model,
            prediction_input,
            num_loops=int(profile["inference"]["num_loops"]),
            num_sampling_steps=int(profile["inference"]["num_sampling_steps"]),
            num_diffusion_samples=1,
            seed=int(request["parameters"]["seed"]),
            complex_id=request["inputs"]["sequence_id"],
        )
        structure = result.complex.to_mmcif()
        structure_path = output / "structure.cif"
        structure_path.write_text(structure, encoding="utf-8")
        plddt = result.plddt.detach().float().cpu()
        if not torch.isfinite(plddt).all().item():
            raise ValueError("Non-finite predicted confidence")
        metrics = {
            "mean_plddt": float(plddt.mean().item()),
            "min_plddt": float(plddt.min().item()),
            "max_plddt": float(plddt.max().item()),
            "ptm": result.ptm,
            "iptm": result.iptm,
        }
        atomic_json(output / "metrics.json", metrics)
        atomic_json(
            output / "execution.json",
            {
                "engine": "esmfold2",
                "variant": "standard",
                "network": "disabled",
                "python": sys.version.split()[0],
                "torch": torch.__version__,
                "cuda": torch.version.cuda,
                "gpu_name": torch.cuda.get_device_name(0),
                "gpu_allocation_policy": "scheduler-assigned-exclusive-v1",
                "gpu_count": torch.cuda.device_count(),
                "gpu_capability": list(torch.cuda.get_device_capability(0)),
                "peak_gpu_memory_bytes": torch.cuda.max_memory_allocated(),
                "peak_process_rss_kib": (
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None
                ),
                "elapsed_seconds": time.time() - started,
                "asset_manifest_sha256": profile["asset_manifest_sha256"],
                "asset_file_count": len(asset_manifest["files"]),
                "environment_manifest_sha256": profile["environment_manifest_sha256"],
                "environment_file_count": environment_manifest["extracted"]["file_count"],
                "environment_root": str(environment_root),
                "offline_asset_paths": {
                    "esmfold2": profile["esmfold2_relative_path"],
                    "esmc": profile["esmc_relative_path"],
                    "ccd": profile["ccd_relative_path"],
                },
            },
        )
        atomic_json(
            output / "result.json",
            {
                "contract_version": "t01.structure-worker/0.1",
                "request_id": request["request_id"],
                "sequence_id": request["inputs"]["sequence_id"],
                "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
                "engine": "esmfold2",
                "variant": "standard",
                "msa_mode": "none",
                "status": "predicted_engineering_unreviewed",
                "structure": {
                    "path": "structure.cif",
                    "sha256": sha256_file(structure_path),
                    "format": "mmcif",
                    "chain_id": "A",
                },
                "metrics": metrics,
                "scientific_gate": "CLOSED",
                "usable_for_pipeline": False,
            },
        )
        atomic_json(output / "profile.json", profile)
        atomic_json(output / "request.json", request)
        atomic_json(output / "manifest.json", make_manifest(output))
    except Exception as exc:
        atomic_json(
            output / "failure.json",
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "scientific_gate": "CLOSED",
            },
        )
        atomic_json(output / "manifest.json", make_manifest(output))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    args = parser.parse_args()
    run(args.input, args.output_dir, args.profile)


if __name__ == "__main__":
    main()
