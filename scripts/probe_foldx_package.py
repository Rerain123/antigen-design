"""Read-only inventory of a user-supplied FoldX academic package."""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile
import sys

REPO = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    archive = Path(args.zip).absolute()
    output = Path(args.output).absolute()
    assert archive.is_file()
    assert output.is_relative_to(REPO / "discovery/t01-phase1-real/w6") and not output.exists()
    archive_raw = archive.read_bytes()
    with zipfile.ZipFile(archive) as package:
        entries = []
        for info in package.infolist():
            name = info.filename
            if name.startswith("/") or ".." in Path(name).parts:
                raise SystemExit("unsafe archive path: " + name)
            raw = package.read(info)
            entries.append(
                dict(
                    name=name,
                    bytes=len(raw),
                    sha256=digest(raw),
                    is_directory=name.endswith("/"),
                    mode=oct((info.external_attr >> 16) & 0xFFFF),
                    elf64_linux=raw[:4] == b"\x7fELF" and raw[4:5] == b"\x02",
                )
            )
        binary = package.read("foldx_20270131")
    strings = [s.decode("ascii", "replace") for s in re.findall(rb"[ -~]{4,}", binary)]
    markers = sorted(
        marker
        for marker in (
            "FoldX 5.0",
            "RepairPDB",
            "BuildModel",
            "PositionScan",
            "license is corrupted",
            "license is expired",
            "no license file found",
        )
        if any(marker.lower() in value.lower() for value in strings)
    )
    names = [item["name"].lower() for item in entries]
    license_entries = [item["name"] for item in entries if any(token in item["name"].lower() for token in ("license", "licence", "\.foldx"))]
    value = dict(
        schema_version="0.1.0",
        checked_at="2026-09-08",
        engine="FoldX",
        required_version="5.0",
        source_archive=str(archive),
        source_archive_bytes=len(archive_raw),
        source_archive_sha256=digest(archive_raw),
        user_attestation="ACADEMIC_VERSION_SUPPLIED_BY_USER",
        license_basis="USER_ATTESTED_ACADEMIC_VERSION",
        license_receipt_present=bool(license_entries),
        license_entries=license_entries,
        package_entries=entries,
        executable=dict(name="foldx_20270131", sha256=digest(binary), bytes=len(binary), elf64_linux=binary[:4] == b"\x7fELF"),
        static_markers=markers,
        package_has_foldx5_markers="FoldX 5.0" in markers,
        package_has_required_commands=all(marker in markers for marker in ("RepairPDB", "BuildModel", "PositionScan")),
        execution_status="NOT_EXECUTED_DOCKER_AND_WSL_UNAVAILABLE",
        production_status="NOT_DEPLOYED",
        scientific_signoff=None,
        note="User attests this is an academic version; the archive contains no separate license receipt, so runtime license behavior remains an execution-time check.",
        official_license_information="https://foldxsuite.crg.eu/node/737",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(__import__("json").dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8", newline="\n")
    print(__import__("json").dumps({"output": str(output), "archive_sha256": value["source_archive_sha256"], "license_entries": license_entries}, ensure_ascii=False))


if __name__ == "__main__":
    main()
