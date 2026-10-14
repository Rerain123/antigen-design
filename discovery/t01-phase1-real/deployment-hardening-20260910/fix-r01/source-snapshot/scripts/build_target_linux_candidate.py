"""Stage and index the deterministic local Linux release candidate.

The script writes files only. It cannot contact or apply to a Kubernetes cluster.
Docker build/save are intentionally explicit operator steps recorded by the
acceptance runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
import tempfile
import os
from pathlib import Path

import yaml

from t01_phase1_real.deployment.kubernetes import SCIENTIFIC_SOURCE_IMAGE_IDS, control_plane_documents, scientific_job_spec


REPO = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("src", "requirements", "工作流设计", "docs")
RUNTIME_SCRIPT_MAP = (
    ("t01_runtime.py", "t01_runtime.py"),
    ("t01_linux_development_supervisor.py", "t01_development_supervisor.py"),
    ("t01_linux_w1_supervisor.py", "w1_runtime_supervisor.py"),
    ("t01_linux_w1_worker.py", "w1_runtime_worker.py"),
)
GPU_TOOLS = {"proteinmpnn", "esm-if1", "thermompnn"}


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))


def stage(deploy: Path, target: Path) -> None:
    target = target.absolute()
    if target.exists() or target.is_symlink():
        raise ValueError("Stage requires a new, dedicated build directory; existing paths are never removed")
    if target.resolve() == REPO or REPO.is_relative_to(target.resolve()):
        raise ValueError("Cannot stage into the project root or its ancestors")
    for parent in target.parents:
        if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
            raise ValueError("Build directory cannot traverse a link")
    for name in ('Dockerfile','requirements.lock','wheelhouse'):
        if not (deploy/name).exists():raise ValueError('Missing release input: '+name)
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.t01-stage-',dir=target.parent))
    try:
        _stage_into(deploy,temporary)
        # rename is non-destructive on Windows; on POSIX fail if an existing
        # destination appeared. No recursive deletion exists in this script.
        if target.exists():raise ValueError('Build target appeared during staging')
        temporary.rename(target)
    except BaseException:
        # Retain incomplete staging for inspection, never delete a supplied path.
        raise


def _stage_into(deploy: Path, target: Path) -> None:
    shutil.copy2(deploy / "Dockerfile", target / "Dockerfile")
    shutil.copy2(deploy / "requirements.lock", target / "requirements.lock")
    copy_tree(deploy / "wheelhouse", target / "wheelhouse")
    app = target / "application"
    app.mkdir()
    shutil.copy2(REPO / "pyproject.toml", app / "pyproject.toml")
    for name in SOURCE_DIRS:
        source = REPO / name
        if source.exists():
            copy_tree(source, app / name)
    (app / "scripts").mkdir()
    for source_name, target_name in RUNTIME_SCRIPT_MAP:
        shutil.copy2(REPO / "scripts" / source_name, app / "scripts" / target_name)


def render(deploy: Path, image: str) -> None:
    output = deploy / "kubernetes"
    documents = control_plane_documents(image)
    if output.exists() or output.is_symlink():
        raise ValueError('Render requires a new candidate directory; previous manifests are preserved')
    jobs = {}
    for tool in sorted(SCIENTIFIC_SOURCE_IMAGE_IDS):
        scientific = f"replace-at-site.invalid/t01/{tool}@sha256:" + "0" * 64
        options = {"gpu_resource_key": "nvidia.com/gpu"} if tool in GPU_TOOLS else {}
        jobs[tool] = scientific_job_spec(tool, "replace1", scientific_image=scientific, control_image=image, asset_claim=f"t01-{tool}-assets", **options)
    (output / "scientific-jobs").mkdir(parents=True)
    (output / "control-plane.yaml").write_text(yaml.safe_dump_all(documents, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")
    for tool in sorted(SCIENTIFIC_SOURCE_IMAGE_IDS):
        scientific = f"replace-at-site.invalid/t01/{tool}@sha256:" + "0" * 64
        options = {"gpu_resource_key": "nvidia.com/gpu"} if tool in GPU_TOOLS else {}
        job = jobs[tool]
        (output / "scientific-jobs" / f"{tool}.yaml").write_text(yaml.safe_dump(job, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")
    (deploy / "metadata").mkdir(exist_ok=True)
    (deploy / "metadata" / "scientific-source-image-ids.json").write_text(json.dumps(SCIENTIFIC_SOURCE_IMAGE_IDS, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    sources = []
    for name in SOURCE_DIRS:
        for path in sorted((REPO / name).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                raw = path.read_bytes()
                sources.append({"path": path.relative_to(REPO).as_posix(), "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    for source_name, _ in RUNTIME_SCRIPT_MAP:
        path = REPO / "scripts" / source_name
        raw = path.read_bytes()
        sources.append({"path": path.relative_to(REPO).as_posix(), "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    sources.sort(key=lambda row: row["path"])
    (deploy / "metadata" / "source-index.json").write_text(json.dumps({"schema_version": "0.1.0", "files": sources}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def index(root: Path) -> dict:
    rows = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file() and path.name != "index.json":
            raw = path.read_bytes()
            rows.append({"path": path.relative_to(root).as_posix(), "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    summary_path = root / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    value = {**summary, "schema_version": "0.1.0", "completion_boundary": "LOCAL_RELEASE_CANDIDATE_ONLY", "production_status": "NOT_DEPLOYED", "scientific_gate": "CLOSED", "indexed_files": len(rows), "files": rows}
    (root / "index.json").write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return value


def package(root: Path, output: Path) -> dict:
    """Create a deterministic expanded-package mirror as one ZIP."""
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(root.resolve()):
        raise ValueError('Package output must be a new file outside the source tree')
    output.parent.mkdir(parents=True, exist_ok=True)
    fixed_time = (2026, 9, 10, 0, 0, 0)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as archive:
        for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda item: item.relative_to(root).as_posix()):
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), fixed_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    raw = output.read_bytes()
    return {"path": str(output), "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("stage", "render", "index", "package"))
    parser.add_argument("--deploy", type=Path, default=REPO / "deploy" / "t01-phase1-real-target-v0.1")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--image")
    args = parser.parse_args()
    if args.operation == "stage":
        if args.target is None:
            parser.error("stage requires --target")
        stage(args.deploy.resolve(), args.target.resolve())
    elif args.operation == "render":
        if not args.image:
            parser.error("render requires --image")
        render(args.deploy.resolve(), args.image)
    elif args.operation == "index":
        print(json.dumps(index(args.deploy.resolve()), ensure_ascii=False, sort_keys=True))
    else:
        if args.target is None:
            parser.error("package requires --target")
        print(json.dumps(package(args.deploy.resolve(), args.target.resolve()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
