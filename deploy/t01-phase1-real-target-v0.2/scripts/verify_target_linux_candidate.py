"""Verify every byte and safety-critical invariant in the local candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import yaml


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_index(root: Path) -> dict:
    document = json.loads((root / "index.json").read_text(encoding="utf-8"))
    rows = document["files"]
    declared = {row["path"]: row for row in rows}
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.name != "index.json"}
    if len(declared)!=len(rows) or set(declared) != actual or document["indexed_files"] != len(rows):
        raise ValueError("candidate file set differs from index")
    for relative, row in declared.items():
        path = root / relative
        if path.stat().st_size != row["size_bytes"] or sha(path) != row["sha256"]:
            raise ValueError(f"candidate byte mismatch: {relative}")
    return document


def verify(root: Path, archive: Path | None = None) -> dict:
    index = verify_index(root)
    if index["completion_boundary"] != "LOCAL_RELEASE_CANDIDATE_ONLY" or index["production_status"] != "NOT_DEPLOYED":
        raise ValueError("candidate boundary changed")
    image = json.loads((root / "metadata" / "image.json").read_text(encoding="utf-8"))
    image_tar = root / image["archive"]["path"]
    if image_tar.stat().st_size != image["archive"]["size_bytes"] or sha(image_tar) != image["archive"]["sha256"]:
        raise ValueError("image archive receipt differs")
    sbom = json.loads((root / "metadata" / "sbom.spdx.json").read_text(encoding="utf-8"))
    if sbom.get("spdxVersion") != "SPDX-2.3" or len(sbom.get("packages", [])) != image["sbom"]["packages"]:
        raise ValueError("SBOM receipt differs")
    docs = list(yaml.safe_load_all((root / "kubernetes" / "control-plane.yaml").read_text(encoding="utf-8")))
    validate_control_plane(docs,index.get('schema_version'))
    raw = json.dumps(docs, sort_keys=True)
    if "hostPath" in raw or "docker.sock" in raw or '"privileged": true' in raw:
        raise ValueError("forbidden Kubernetes privilege or host path")
    jobs = list((root / "kubernetes" / "scientific-jobs").glob("*.yaml"))
    expected_jobs=10 if index['schema_version']=='0.1.0' else 11
    if len(jobs) != expected_jobs or any(yaml.safe_load(path.read_text(encoding="utf-8"))["metadata"]["annotations"].get("t01.openai/not-submitted") != "true" for path in jobs):
        raise ValueError("scientific Job set differs")
    if archive is not None:
        if not archive.is_file():
            raise ValueError("offline archive is absent")
        with zipfile.ZipFile(archive) as bundle:
            if len(bundle.namelist())!=len(set(bundle.namelist())) or set(bundle.namelist()) != {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}:
                raise ValueError("offline archive file set differs")
            for name in bundle.namelist():
                if hashlib.sha256(bundle.read(name)).hexdigest() != sha(root / name):
                    raise ValueError(f"offline archive byte mismatch: {name}")
    return {"status": "PASS", "indexed_files": index["indexed_files"], "scientific_jobs": len(jobs), "production_status": "NOT_DEPLOYED"}


def validate_control_plane(docs,version):
    if version not in ('0.1.0','0.2.0'):raise ValueError('unsupported candidate schema version')
    kinds=["Namespace", "ServiceAccount", "Secret", "ConfigMap", "PersistentVolumeClaim", "Role", "RoleBinding", "Deployment", "Service"]
    if version=='0.2.0':kinds.append('NetworkPolicy')
    if [item["kind"] for item in docs] != kinds:
        raise ValueError("control-plane resource set differs")
    if version=='0.2.0':
        from t01_phase1_real.deployment.kubernetes import scientific_network_policy
        policy=docs[-1]
        expected=scientific_network_policy(docs[0]['metadata']['name'])
        if policy!=expected:raise ValueError('candidate offline policy differs')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.root.resolve(), args.archive.resolve() if args.archive else None), sort_keys=True))


if __name__ == "__main__":
    main()
