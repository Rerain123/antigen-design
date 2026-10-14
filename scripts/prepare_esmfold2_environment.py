"""Create a bounded ESMFold2 image context from the verified local source assets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSETS = ROOT / "var/t01-phase1-real/structure-models/esmfold2-standard-20260916-r01"
DEPLOY = ROOT / "deploy/esmfold2-standard"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(assets: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Output context already exists")
    manifest_path = assets / "asset-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("status") != "ASSETS_DOWNLOADED_NOT_DEPLOYED":
        raise ValueError("Unexpected asset state")
    source_rows = [row for row in manifest["files"] if row["path"].startswith("sources/")]
    if len(source_rows) != 2:
        raise ValueError("Expected exactly two pinned source archives")
    output.mkdir(parents=True)
    extracted = []
    for row in source_rows:
        archive = assets / row["path"]
        if archive.stat().st_size != row["bytes"] or sha256_file(archive) != row["sha256"]:
            raise ValueError("Source archive integrity mismatch: " + row["path"])
        with tarfile.open(archive) as source:
            source.extractall(output, filter="data")
        extracted.append(row)
    esm = next(output.glob("esm-*"))
    transformers = next(output.glob("transformers-*"))
    dockerfile = (DEPLOY / "Dockerfile.environment").read_text(encoding="utf-8")
    dockerfile = dockerfile.replace("TRANSFORMERS_SOURCE", transformers.name).replace(
        "ESM_SOURCE", esm.name
    )
    (output / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    shutil.copyfile(DEPLOY / "requirements.resolved.txt", output / "requirements.resolved.txt")
    receipt = {
        "variant": "standard",
        "asset_manifest_sha256": sha256_file(manifest_path),
        "sources": extracted,
        "dockerfile_sha256": hashlib.sha256(dockerfile.encode()).hexdigest(),
        "requirements_sha256": sha256_file(output / "requirements.resolved.txt"),
        "scientific_gate": "CLOSED",
    }
    (output / "source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.assets.resolve(), args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
