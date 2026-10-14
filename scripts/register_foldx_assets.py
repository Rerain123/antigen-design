"""Register a user-supplied FoldX archive as an immutable local candidate asset."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

REPO = Path(__file__).resolve().parents[1]
TARGET = REPO / "var/t01-phase1-real/tool-assets/foldx-20270131"
PROBE = REPO / "discovery/t01-phase1-real/w6/stability-assets-20260908/foldx-user-package-probe.json"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True)
    args = parser.parse_args()
    archive = Path(args.zip).absolute()
    if not archive.is_file():
        raise SystemExit("archive does not exist: " + str(archive))
    if TARGET.exists():
        raise SystemExit("refusing to overwrite existing candidate asset: " + str(TARGET))
    if not PROBE.is_file():
        raise SystemExit("run probe_foldx_package.py first: " + str(PROBE))
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    archive_raw = archive.read_bytes()
    if sha(archive_raw) != probe["source_archive_sha256"]:
        raise SystemExit("archive hash differs from the recorded probe")
    staging = TARGET.with_name(TARGET.name + ".staging")
    if staging.exists():
        raise SystemExit("refusing to reuse staging directory: " + str(staging))
    staging.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive) as package:
            names = {info.filename for info in package.infolist()}
            if "foldx_20270131" not in names:
                raise SystemExit("FoldX executable is missing")
            for info in package.infolist():
                name = info.filename
                if name.startswith("/") or ".." in Path(name).parts:
                    raise SystemExit("unsafe archive path: " + name)
                destination = staging / name
                if info.is_dir() or name.endswith("/"):
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(package.read(name))
                mode = (info.external_attr >> 16) & 0o777
                if mode:
                    destination.chmod(mode)
        binary = staging / "foldx_20270131"
        if sha(binary.read_bytes()) != probe["executable"]["sha256"]:
            raise SystemExit("executable hash differs from the recorded probe")
        files = []
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                files.append(dict(path=(TARGET / path.relative_to(staging)).relative_to(REPO).as_posix(), bytes=path.stat().st_size, sha256=sha(path.read_bytes())))
        receipt = dict(
            schema_version="0.1.0",
            engine="FoldX",
            required_version="5.0",
            archive_sha256=probe["source_archive_sha256"],
            executable=probe["executable"],
            files=files,
            user_attestation="ACADEMIC_VERSION_SUPPLIED_BY_USER",
            license_basis="USER_ATTESTED_ACADEMIC_VERSION",
            license_receipt_present=False,
            license_entries=[],
            image=None,
            image_status="NOT_BUILT_DOCKER_UNAVAILABLE",
            execution_status="NOT_EXECUTED_DOCKER_AND_WSL_UNAVAILABLE",
            production_status="NOT_DEPLOYED",
            scientific_signoff=None,
        )
        (staging / "assets.json").write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        staging.replace(TARGET)
        print(json.dumps({"target": str(TARGET), "archive_sha256": receipt["archive_sha256"], "files": len(files)}, ensure_ascii=False))
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
