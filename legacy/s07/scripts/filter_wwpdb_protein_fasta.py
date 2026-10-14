"""Filter the wwPDB ``pdb_seqres.txt.gz`` snapshot to protein records.

The output is a discovery-only sequence-search database source.  A manifest is
written with input/output hashes and record statistics so the transformation is
reproducible without committing the large FASTA into the repository.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-last-modified", required=True)
    parser.add_argument(
        "--database-role",
        default="S-07 discovery structure-sequence database source",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists() or args.manifest.exists():
        raise SystemExit("refusing to overwrite existing filtered FASTA or manifest")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)

    record_count = 0
    residue_count = 0
    characters: set[str] = set()
    keep = False

    with gzip.open(args.input, "rt", encoding="ascii", newline=None) as source:
        with args.output.open("w", encoding="ascii", newline="\n") as target:
            for raw_line in source:
                line = raw_line.rstrip("\r\n")
                if line.startswith(">"):
                    keep = "mol:protein" in line.lower()
                    if keep:
                        record_count += 1
                        target.write(line + "\n")
                    continue
                if keep:
                    sequence_line = "".join(line.split()).upper()
                    if sequence_line:
                        residue_count += len(sequence_line)
                        characters.update(sequence_line)
                        target.write(sequence_line + "\n")

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = {
        "classification": "discovery_evidence",
        "production_deployment_status": "NOT_DEPLOYED",
        "database_role": args.database_role,
        "generated_at": generated_at,
        "source": {
            "url": args.source_url,
            "last_modified": args.source_last_modified,
            "file_name": args.input.name,
            "size_bytes": args.input.stat().st_size,
            "sha256": sha256_file(args.input),
        },
        "transformation": {
            "rule": "keep FASTA records whose header contains mol:protein (case-insensitive)",
            "script": "scripts/filter_wwpdb_protein_fasta.py",
        },
        "output": {
            "logical_name": args.output.name,
            "size_bytes": args.output.stat().st_size,
            "sha256": sha256_file(args.output),
            "record_count": record_count,
            "residue_count": residue_count,
            "observed_sequence_characters": sorted(characters),
        },
    }
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
