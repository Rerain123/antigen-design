"""Build S-07 task 3 discovery reports from frozen local evidence.

This is an evidence builder, not a production structure-selection adapter.  It
uses the proposed query-coverage interpretation only to expose its measured
effect and never invents cross-method or chain tie breakers.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CAMPAIGN_ID = "p0-s07-task3-mmseqs-20260902-a"
IDENTITY_THRESHOLD = 0.95
COVERAGE_THRESHOLD = 0.90
MMSEQS_TAG = "18-8cc5c"
MMSEQS_COMMIT = "8cc5ce367b5638c4306c2d7cfc652dd099a4643f"
MMSEQS_ARCHIVE_SHA256 = (
    "9752087ca4e25e93b830775832a75044dc94ae348d66d4681f9ff0355eecfcbf"
)
PDB_SEQUENCE_SHA256 = (
    "3ce3bf140288f133e0fbf1185186ca50a24cd9bd58f9116b032347101760eeb0"
)
PDB_ENTRIES_SHA256 = (
    "9f9709b11302bc1414ea19b5be6b5e92104804c19fcbcec013010ce0a772fc86"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_ref(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def read_fasta(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    identifier: str | None = None
    chunks: list[str] = []
    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith(">"):
            if identifier is not None:
                records[identifier] = "".join(chunks)
            identifier = line[1:].split()[0]
            chunks = []
        else:
            chunks.append("".join(line.split()).upper())
    if identifier is not None:
        records[identifier] = "".join(chunks)
    return records


def read_mmseqs(path: Path) -> list[dict[str, Any]]:
    typed: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle, delimiter="\t"):
            row: dict[str, Any] = dict(raw)
            for key in ("pident", "fident", "evalue", "bits", "qcov", "tcov"):
                row[key] = float(row[key])
            for key in (
                "nident",
                "alnlen",
                "mismatch",
                "gapopen",
                "qstart",
                "qend",
                "tstart",
                "tend",
                "qlen",
                "tlen",
            ):
                row[key] = int(row[key])
            typed.append(row)
    return typed


def strict_query_coverage_pass(row: dict[str, Any]) -> bool:
    return row["fident"] > IDENTITY_THRESHOLD and row["qcov"] > COVERAGE_THRESHOLD


def target_parts(target: str) -> tuple[str, str]:
    entry, chain = target.split("_", 1)
    return entry.upper(), chain


def read_entries_index(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="latin-1", errors="replace") as handle:
        next(handle)
        next(handle)
        for line in handle:
            columns = line.rstrip("\r\n").split("\t")
            if len(columns) < 8:
                continue
            resolution: float | None
            try:
                value = float(columns[6])
                resolution = value if value > 0 else None
            except ValueError:
                resolution = None
            records[columns[0].upper()] = {
                "entry_id": columns[0].upper(),
                "header": columns[1],
                "accession_date": columns[2],
                "compound": columns[3],
                "source": columns[4],
                "resolution_angstrom": resolution,
                "resolution_raw": columns[6],
                "method": columns[7],
                "method_group": method_group(columns[7]),
            }
    return records


def method_group(method: str) -> str:
    upper = method.upper()
    if "X-RAY" in upper:
        return "X_RAY"
    if "ELECTRON MICROSCOPY" in upper:
        return "CRYO_EM"
    if "NMR" in upper:
        return "NMR"
    return "OTHER"


def ranges_from_positions(positions: set[int]) -> list[dict[str, int]]:
    if not positions:
        return []
    ordered = sorted(positions)
    ranges: list[dict[str, int]] = []
    start = previous = ordered[0]
    for position in ordered[1:]:
        if position != previous + 1:
            ranges.append({"start": start, "end": previous})
            start = position
        previous = position
    ranges.append({"start": start, "end": previous})
    return ranges


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def parse_mmcif(path: Path) -> dict[str, Any]:
    try:
        from Bio.PDB.MMCIF2Dict import MMCIF2Dict
    except ImportError as exc:  # pragma: no cover - explicit discovery dependency
        raise SystemExit("Biopython 1.88 is required for this evidence builder") from exc

    doc = MMCIF2Dict(str(path))
    entity_sequences: dict[str, str] = {}
    for entity_id, sequence in zip(
        as_list(doc.get("_entity_poly.entity_id")),
        as_list(doc.get("_entity_poly.pdbx_seq_one_letter_code_can")),
        strict=True,
    ):
        entity_sequences[str(entity_id)] = re.sub(r"\s+", "", str(sequence))

    chain_atoms: dict[str, dict[str, Any]] = {}
    columns = zip(
        as_list(doc.get("_atom_site.auth_asym_id")),
        as_list(doc.get("_atom_site.label_asym_id")),
        as_list(doc.get("_atom_site.label_entity_id")),
        as_list(doc.get("_atom_site.label_seq_id")),
        as_list(doc.get("_atom_site.group_PDB")),
        as_list(doc.get("_atom_site.pdbx_PDB_model_num")),
        strict=True,
    )
    for auth_chain, label_chain, entity_id, label_seq, group, model in columns:
        if str(model) != "1" or str(group) != "ATOM" or str(label_seq) in {".", "?"}:
            continue
        record = chain_atoms.setdefault(
            str(auth_chain),
            {"label_asym_ids": set(), "entity_ids": set(), "label_seq_ids": set()},
        )
        record["label_asym_ids"].add(str(label_chain))
        record["entity_ids"].add(str(entity_id))
        record["label_seq_ids"].add(int(label_seq))

    methods = [str(item) for item in as_list(doc.get("_exptl.method"))]
    resolution_values = as_list(doc.get("_refine.ls_d_res_high")) or as_list(
        doc.get("_em_3d_reconstruction.resolution")
    )
    resolution = None
    for raw in resolution_values:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            resolution = value
            break

    return {
        "entity_sequences": entity_sequences,
        "chain_atoms": chain_atoms,
        "methods": methods,
        "resolution_angstrom": resolution,
        "deposited_date": (
            as_list(doc.get("_pdbx_database_status.recvd_initial_deposition_date"))
            or [None]
        )[0],
    }


def map_ungapped_alignment_to_coordinates(
    row: dict[str, Any], coordinate_target_positions: set[int]
) -> set[int]:
    match = re.fullmatch(r"(\d+)M", row["cigar"])
    if match is None or int(match.group(1)) != row["alnlen"]:
        raise ValueError(
            f"Evidence mapper supports the observed ungapped selected hit only: {row['target']}"
        )
    mapped: set[int] = set()
    for offset in range(row["alnlen"]):
        query_position = row["qstart"] + offset
        target_position = row["tstart"] + offset
        if target_position in coordinate_target_positions:
            mapped.add(query_position)
    return mapped


def evaluate_controlled_cases(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    strict_results: list[dict[str, Any]] = []
    for case in doc["strict_filter"]["cases"]:
        passed = (
            case["identity"] > IDENTITY_THRESHOLD
            and case["query_coverage"] > COVERAGE_THRESHOLD
        )
        if passed:
            reason = "PASS"
        elif case["identity"] <= IDENTITY_THRESHOLD:
            reason = "IDENTITY_NOT_STRICTLY_GREATER_THAN_095"
        else:
            reason = "COVERAGE_NOT_STRICTLY_GREATER_THAN_090"
        strict_results.append(
            {
                "case_id": case["case_id"],
                "actual_pass": passed,
                "actual_reason": reason,
                "expected_match": (
                    passed == case["expected_pass"] and reason == case["expected_reason"]
                ),
            }
        )

    resolution_results: list[dict[str, Any]] = []
    for case in doc["resolution_selection"]["cases"]:
        candidates = case["candidates"]
        noncomparable = [
            item for item in candidates if item["method_group"] not in {"X_RAY", "CRYO_EM",}
        ]
        comparable = [
            item
            for item in candidates
            if item["method_group"] in {"X_RAY", "CRYO_EM"}
            and isinstance(item["resolution_angstrom"], (int, float))
            and item["resolution_angstrom"] > 0
        ]
        if noncomparable:
            status = "CROSS_METHOD_PRIORITY_UNRESOLVED"
            ids = sorted(item["candidate_id"] for item in candidates)
        elif not comparable:
            status = "NO_COMPARABLE_POSITIVE_RESOLUTION"
            ids = []
        else:
            minimum = min(item["resolution_angstrom"] for item in comparable)
            ids = sorted(
                item["candidate_id"]
                for item in comparable
                if item["resolution_angstrom"] == minimum
            )
            status = "SELECTED" if len(ids) == 1 else "RESOLUTION_TIE_UNRESOLVED"
        resolution_results.append(
            {
                "case_id": case["case_id"],
                "actual_status": status,
                "actual_candidate_ids": ids,
                "expected_match": (
                    status == case["expected_status"]
                    and ids == sorted(case["expected_candidate_ids"])
                ),
            }
        )

    chain_results = []
    for case in doc["matching_chain_handling"]["cases"]:
        status = (
            "UNIQUE_CHAIN"
            if len(case["matching_chains"]) == 1
            else "AMBIGUOUS_MATCHING_CHAINS_BLOCK_AUTO_HANDOFF"
        )
        chain_results.append(
            {
                "case_id": case["case_id"],
                "actual_status": status,
                "expected_match": status == case["expected_status"],
            }
        )

    all_results = strict_results + resolution_results + chain_results
    return {
        "strict_filter": strict_results,
        "resolution_selection": resolution_results,
        "matching_chain_handling": chain_results,
        "case_count": len(all_results),
        "all_expected": all(item["expected_match"] for item in all_results),
    }


def build() -> None:
    root = Path(__file__).resolve().parents[1]
    campaign = root / "discovery/p0/s07" / CAMPAIGN_ID
    if not campaign.is_dir():
        raise FileNotFoundError(campaign)
    reports = campaign / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    sequence_archive = root / "var/discovery-data/wwpdb-20260829/pdb_seqres.txt.gz"
    filtered_fasta = root / "var/discovery-data/wwpdb-20260829/pdb_seqres_protein.fasta"
    filtered_manifest = root / "var/discovery-data/wwpdb-20260829/pdb_seqres_protein.manifest.json"
    entries_path = root / "var/discovery-data/wwpdb-20260829/entries.idx"
    db_dir = root / "var/discovery-data/wwpdb-20260829/mmseqs2-18-8cc5c"
    tool_dir = root / "var/discovery-tools/mmseqs2-18-8cc5c"
    archive_path = tool_dir / "mmseqs-win64.zip"
    release_api_path = tool_dir / "release-api.json"
    executable_path = tool_dir / "extracted/mmseqs/bin/mmseqs.exe"
    query_path = campaign / "inputs/query-set.fasta"
    broad_path = campaign / "results/mmseqs-broad-candidates-20260829.tsv"
    gate_path = campaign / "results/mmseqs-gate-floor-20260829.tsv"

    if sha256_file(sequence_archive) != PDB_SEQUENCE_SHA256:
        raise ValueError("wwPDB sequence archive hash mismatch")
    if sha256_file(entries_path) != PDB_ENTRIES_SHA256:
        raise ValueError("wwPDB entries index hash mismatch")
    if sha256_file(archive_path) != MMSEQS_ARCHIVE_SHA256:
        raise ValueError("MMseqs2 archive hash mismatch")

    release_api = json.loads(release_api_path.read_text(encoding="utf-8"))
    if release_api["tag_name"] != MMSEQS_TAG:
        raise ValueError("MMseqs2 release tag changed")
    asset = next(
        item for item in release_api["assets"] if item["name"] == "mmseqs-win64.zip"
    )
    if asset["digest"] != f"sha256:{MMSEQS_ARCHIVE_SHA256}":
        raise ValueError("MMseqs2 API asset digest mismatch")
    version_text = (campaign / "logs/mmseqs-version.txt").read_text(
        encoding="utf-8-sig"
    ).strip()
    if version_text != MMSEQS_COMMIT:
        raise ValueError("MMseqs2 runtime version mismatch")

    query_sequences = read_fasta(query_path)
    broad_rows = read_mmseqs(broad_path)
    gate_rows = read_mmseqs(gate_path)
    entries = read_entries_index(entries_path)
    strict_rows = [row for row in broad_rows if strict_query_coverage_pass(row)]
    strict_keys = {(row["query"], row["target"]) for row in strict_rows}
    gate_keys = {(row["query"], row["target"]) for row in gate_rows}
    if strict_keys != gate_keys:
        raise ValueError("gate-floor search differs from strict post-filter result")

    strict_tsv_path = reports / "strict_candidate_metadata.tsv"
    strict_fields = [
        "query",
        "target",
        "entry_id",
        "chain_id",
        "fident",
        "qcov",
        "tcov",
        "qlen",
        "tlen",
        "qstart",
        "qend",
        "tstart",
        "tend",
        "cigar",
        "evalue",
        "bits",
        "method",
        "method_group",
        "resolution_angstrom",
        "accession_date",
    ]
    with strict_tsv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=strict_fields, delimiter="\t")
        writer.writeheader()
        for row in strict_rows:
            entry_id, chain_id = target_parts(row["target"])
            metadata = entries.get(entry_id)
            if metadata is None:
                raise ValueError(f"entry metadata missing: {entry_id}")
            writer.writerow(
                {
                    **{key: row[key] for key in strict_fields if key in row},
                    "entry_id": entry_id,
                    "chain_id": chain_id,
                    "method": metadata["method"],
                    "method_group": metadata["method_group"],
                    "resolution_angstrom": metadata["resolution_angstrom"],
                    "accession_date": metadata["accession_date"],
                }
            )

    query_audits: list[dict[str, Any]] = []
    rows_by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in broad_rows:
        rows_by_query[row["query"]].append(row)

    for query in query_sequences:
        broad = rows_by_query.get(query, [])
        identity_rows = [row for row in broad if row["fident"] > IDENTITY_THRESHOLD]
        strict = [row for row in broad if strict_query_coverage_pass(row)]
        target_coverage = [
            row
            for row in identity_rows
            if row["tcov"] > COVERAGE_THRESHOLD
        ]
        both_coverage = [
            row
            for row in identity_rows
            if row["qcov"] > COVERAGE_THRESHOLD
            and row["tcov"] > COVERAGE_THRESHOLD
        ]
        by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in strict:
            by_entry[target_parts(row["target"])[0]].append(row)
        missing_metadata = sorted(entry_id for entry_id in by_entry if entry_id not in entries)
        method_counts = Counter(
            entries[entry_id]["method_group"]
            for entry_id in by_entry
            if entry_id in entries
        )
        comparable = sorted(
            (
                entries[entry_id]["resolution_angstrom"],
                entry_id,
            )
            for entry_id in by_entry
            if entry_id in entries
            and entries[entry_id]["method_group"] in {"X_RAY", "CRYO_EM"}
            and entries[entry_id]["resolution_angstrom"] is not None
        )
        noncomparable = sorted(
            entry_id
            for entry_id in by_entry
            if entry_id in entries
            and entries[entry_id]["method_group"] not in {"X_RAY", "CRYO_EM"}
        )
        comparable_best_entries: list[str] = []
        if comparable:
            minimum = comparable[0][0]
            comparable_best_entries = [
                entry_id for resolution, entry_id in comparable if resolution == minimum
            ]
        if not strict:
            selection_status = "NO_STRICT_CANDIDATE_IN_FROZEN_SNAPSHOT"
        elif noncomparable:
            selection_status = "CROSS_METHOD_PRIORITY_UNRESOLVED"
        elif len(comparable_best_entries) > 1:
            selection_status = "RESOLUTION_TIE_UNRESOLVED"
        elif not comparable_best_entries:
            selection_status = "NO_COMPARABLE_POSITIVE_RESOLUTION"
        else:
            selected_entry = comparable_best_entries[0]
            selection_status = (
                "COMPARABLE_BEST_HAS_UNIQUE_MATCHING_CHAIN"
                if len(by_entry[selected_entry]) == 1
                else "AMBIGUOUS_MATCHING_CHAINS_BLOCK_AUTO_HANDOFF"
            )

        comparable_best = []
        for entry_id in comparable_best_entries:
            comparable_best.append(
                {
                    "entry_id": entry_id,
                    "resolution_angstrom": entries[entry_id]["resolution_angstrom"],
                    "method": entries[entry_id]["method"],
                    "matching_chains": sorted(
                        target_parts(row["target"])[1] for row in by_entry[entry_id]
                    ),
                    "usage": "FILE_VALIDATION_CANDIDATE_NOT_PRODUCTION_SELECTION",
                }
            )

        query_audits.append(
            {
                "query": query,
                "query_length": len(query_sequences[query]),
                "broad_candidate_chains": len(broad),
                "strict_query_coverage_chains": len(strict),
                "strict_query_coverage_entries": len(by_entry),
                "strict_target_coverage_chains": len(target_coverage),
                "strict_target_coverage_entries": len(
                    {target_parts(row["target"])[0] for row in target_coverage}
                ),
                "strict_both_coverages_chains": len(both_coverage),
                "strict_both_coverages_entries": len(
                    {target_parts(row["target"])[0] for row in both_coverage}
                ),
                "metadata_missing_entries": missing_metadata,
                "method_group_entry_counts": dict(sorted(method_counts.items())),
                "noncomparable_method_entry_count": len(noncomparable),
                "comparable_best": comparable_best,
                "selection_status": selection_status,
            }
        )

    validation_specs = [
        {
            "entry_id": "6Q00",
            "chains": ["A"],
            "query_prefix": "P0-DISC-001|",
            "expected_partial": False,
        },
        {
            "entry_id": "9R2Q",
            "chains": ["K", "L", "M", "N"],
            "query_prefix": "P0-DISC-002|",
            "expected_partial": True,
        },
    ]
    file_validations: list[dict[str, Any]] = []
    for spec in validation_specs:
        cif_path = campaign / "evidence/wwpdb" / spec["entry_id"] / f"{spec['entry_id']}.cif"
        cif = parse_mmcif(cif_path)
        query = next(key for key in query_sequences if key.startswith(spec["query_prefix"]))
        query_sequence = query_sequences[query]
        chain_results: list[dict[str, Any]] = []
        for chain in spec["chains"]:
            target = f"{spec['entry_id'].lower()}_{chain}"
            row = next(
                row for row in strict_rows if row["query"] == query and row["target"] == target
            )
            atoms = cif["chain_atoms"][chain]
            if len(atoms["entity_ids"]) != 1:
                raise ValueError(f"multiple entity ids for {target}")
            entity_id = next(iter(atoms["entity_ids"]))
            entity_sequence = cif["entity_sequences"][entity_id]
            aligned_query = query_sequence[row["qstart"] - 1 : row["qend"]]
            aligned_entity = entity_sequence[row["tstart"] - 1 : row["tend"]]
            if aligned_query != aligned_entity:
                raise ValueError(f"query/entity aligned sequence mismatch: {target}")
            coordinate_query_positions = map_ungapped_alignment_to_coordinates(
                row, atoms["label_seq_ids"]
            )
            partial = len(coordinate_query_positions) < len(query_sequence)
            if partial != spec["expected_partial"]:
                raise ValueError(f"unexpected partial status: {target}")
            chain_results.append(
                {
                    "chain_id": chain,
                    "entity_id": entity_id,
                    "entity_sequence_length": len(entity_sequence),
                    "search_identity": row["fident"],
                    "search_query_coverage": row["qcov"],
                    "search_target_coverage": row["tcov"],
                    "alignment": {
                        "query_start": row["qstart"],
                        "query_end": row["qend"],
                        "target_start": row["tstart"],
                        "target_end": row["tend"],
                        "cigar": row["cigar"],
                    },
                    "coordinate_target_residue_count": len(atoms["label_seq_ids"]),
                    "coordinate_target_ranges": ranges_from_positions(
                        atoms["label_seq_ids"]
                    ),
                    "coordinate_mapped_query_residue_count": len(
                        coordinate_query_positions
                    ),
                    "coordinate_mapped_query_fraction": round(
                        len(coordinate_query_positions) / len(query_sequence), 8
                    ),
                    "coordinate_mapped_query_ranges": ranges_from_positions(
                        coordinate_query_positions
                    ),
                    "partial": partial,
                }
            )
        file_validations.append(
            {
                "entry_id": spec["entry_id"],
                "query": query,
                "method": cif["methods"],
                "resolution_angstrom": cif["resolution_angstrom"],
                "deposited_date": cif["deposited_date"],
                "matching_chain_count": len(chain_results),
                "matching_chain_status": (
                    "UNIQUE_CHAIN"
                    if len(chain_results) == 1
                    else "AMBIGUOUS_MATCHING_CHAINS_BLOCK_AUTO_HANDOFF"
                ),
                "structure_file": file_ref(cif_path, root),
                "chains": chain_results,
            }
        )

    controlled = evaluate_controlled_cases(
        campaign / "inputs/controlled/strict-filter-and-selection-cases.json"
    )
    if not controlled["all_expected"]:
        raise ValueError("controlled case expectation mismatch")

    import Bio
    import numpy

    db_files = sorted(path for path in db_dir.iterdir() if path.is_file())
    report = {
        "schema_version": "s07-task3-evidence.v0.1",
        "campaign_id": CAMPAIGN_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_evidence_status": "PASS_WITH_TARGETED_RULE_GAPS",
        "production_deployment_status": "NOT_DEPLOYED",
        "scientific_acceptance": "NOT_RUN",
        "authoritative_rules_applied": {
            "identity": "fident > 0.95",
            "coverage": "qcov > 0.90 (proposed query-coverage interpretation; not yet frozen)",
            "comparable_resolution": "minimum positive Angstrom across X-ray and cryo-EM",
            "partial": "sequence-qualified structure with incomplete coordinate mapping remains partial",
            "matching_chain_ambiguity": "R-58 failure-level warning and block automatic handoff",
        },
        "runtime": {
            "mmseqs2_tag": MMSEQS_TAG,
            "mmseqs2_commit": MMSEQS_COMMIT,
            "mmseqs2_platform": "Windows beta/Cygwin package for discovery only",
            "biopython_version": Bio.__version__,
            "numpy_version": numpy.__version__,
            "initial_createindex_failure": "BusyBox helper applets absent; fixed by local hard-link installation before the successful immutable index build.",
        },
        "data_release": {
            "logical_id": "wwpdb-20260829-mmseqs2-18-8cc5c",
            "sequence_archive": file_ref(sequence_archive, root),
            "filtered_fasta": file_ref(filtered_fasta, root),
            "filtered_manifest": file_ref(filtered_manifest, root),
            "entries_index": file_ref(entries_path, root),
            "mmseqs_database_files": [file_ref(path, root) for path in db_files],
        },
        "tool_release": {
            "release_api": file_ref(release_api_path, root),
            "archive": file_ref(archive_path, root),
            "executable": file_ref(executable_path, root),
            "official_asset_digest_verified": True,
        },
        "search_profile": {
            "candidate_generation": {
                "min_seq_id": 0.90,
                "min_query_coverage": 0.80,
                "cov_mode": 2,
                "evalue": 1.0,
                "max_seqs": 10000,
                "sensitivity": 7.5,
                "purpose": "Broad evidence set before strict post-filtering",
            },
            "gate_floor_repeat": {
                "min_seq_id": 0.95,
                "min_query_coverage": 0.90,
                "cov_mode": 2,
                "same_candidate_keys_as_strict_postfilter": True,
                "candidate_key_count": len(strict_keys),
            },
        },
        "queries": query_audits,
        "selected_file_validations": file_validations,
        "controlled_cases": controlled,
        "targeted_rule_gaps": [
            {
                "gap_id": "S07-T3-G01",
                "topic": "coverage denominator",
                "observed_impact": "For the ubiquitin input, query coverage keeps 1333 PDB entries while target coverage or both coverages keep 792.",
                "recommendation": "Define S-07 coverage as input/query coverage; continue returning target coverage as an audit fact.",
                "decision_status": "TARGETED_CONFIRMATION_REQUIRED_BEFORE_PRODUCTION_CONTRACT",
            },
            {
                "gap_id": "S07-T3-G02",
                "topic": "NMR versus positive-resolution X-ray/cryo-EM",
                "observed_impact": "The ubiquitin strict pool has 537 X-ray, 694 cryo-EM, 99 solution-NMR and 3 solid-state-NMR entries; min(Angstrom) cannot rank NMR entries.",
                "recommendation": "Keep method groups separate. Prefer the best positive-resolution X-ray/cryo-EM candidate only if the expert confirms that NMR is fallback when comparable candidates exist; otherwise return method-group finalists for review.",
                "decision_status": "TARGETED_CONFIRMATION_REQUIRED_BEFORE_PRODUCTION_SELECTION",
            },
        ],
        "directly_resolved_findings": [
            "Strict equality at identity 0.95 or query coverage 0.90 fails the expert's open-interval rule.",
            "The 9R2Q sequence match covers the full 393-residue query but only 200 query positions have coordinates, so sequence coverage and coordinate coverage must be separate fields.",
            "9R2Q has four equally matching chains K/L/M/N; the existing R-58 rule blocks automatic handoff rather than choosing the first chain.",
            "O15116 and WP_505187596.1 have no candidate at the recorded local search floor in this frozen snapshot and therefore exercise the C4 fallback route.",
        ],
    }
    report_path = reports / "task3_evidence.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    audit_by_prefix = {
        item["query"].split("|", 1)[0]: item for item in report["queries"]
    }
    u = audit_by_prefix["P0-DISC-001"]
    p = audit_by_prefix["P0-DISC-002"]
    o = audit_by_prefix["P0-DISC-004"]
    w = audit_by_prefix["P0-DISC-005"]
    f6 = next(item for item in file_validations if item["entry_id"] == "6Q00")
    f9 = next(item for item in file_validations if item["entry_id"] == "9R2Q")
    p_chain = f9["chains"][0]
    markdown = f"""# S-07 任务 3 本地检索与结构读取证据

> 状态：`PASS_WITH_TARGETED_RULE_GAPS / NOT_DEPLOYED`  
> 批次：`{CAMPAIGN_ID}`  
> 数据：wwPDB 2026-08-29 序列与 entry 索引；MMseqs2 {MMSEQS_TAG}。  
> 边界：这是隔离 discovery，不是生产结构选择，也没有接入 MCP/Dify。

## 1. 实际完成的链路

```text
4 条冻结输入
  → 本地 MMseqs2 搜索 1,093,472 条 PDB protein chain 序列
  → 严格后筛 fident > 0.95 AND proposed qcov > 0.90
  → chain 聚合为 PDB entry
  → 连接同快照 entries.idx 的方法、分辨率和 accession date
  → 对可比的 X-ray/cryo-EM 候选取最小正 Å 值
  → 下载本轮文件验证候选 mmCIF
  → 独立计算序列覆盖与实际坐标覆盖
```

宽松候选集后筛得到 {len(strict_keys)} 个 query-chain 候选。再以 MMseqs2
`--min-seq-id 0.95 -c 0.90 --cov-mode 2` 重跑，候选键与后筛结果完全一致。

## 2. 四个输入的结果

| 输入 | 严格 chain | PDB entry | 方法分布 | 可比最小分辨率 | 当前处理 |
|---|---:|---:|---|---|---|
| 1UBQ ubiquitin 序列 | {u['strict_query_coverage_chains']} | {u['strict_query_coverage_entries']} | X-ray 537；cryo-EM 694；solution NMR 99；solid-state NMR 3 | 6Q00，0.85 Å，chain A | mmCIF 验证通过；跨 NMR 方法优先级未定义，不能标生产入选 |
| P04637 TP53 序列 | {p['strict_query_coverage_chains']} | {p['strict_query_coverage_entries']} | cryo-EM 8 | 9R2Q，3.2 Å，chains K/L/M/N | 四条链同等匹配，按 R-58 禁止自动交接 |
| O15116 LSM1 序列 | {o['strict_query_coverage_chains']} | {o['strict_query_coverage_entries']} | 无 | 无 | 在该冻结快照中进入 AlphaFold DB fallback 测试路径 |
| WP_505187596.1 序列 | {w['strict_query_coverage_chains']} | {w['strict_query_coverage_entries']} | 无 | 无 | 在该冻结快照中进入 AlphaFold DB/accession fallback 测试路径 |

“无”只表示这次完整本地快照和记录参数没有候选，不表示其他版本或更宽阈值下绝对没有同源结构。

## 3. 结构文件读取结论

- 6Q00：X-ray，0.85 Å，A 链目标序列 76/76，实际坐标映射也是 76/76；文件 SHA-256
  `{f6['structure_file']['sha256']}`。
- 9R2Q：cryo-EM，3.2 Å，K/L/M/N 四条链都对目标序列达到 identity=1、query coverage=1；
  每条链实际只有 {p_chain['coordinate_mapped_query_residue_count']}/393 个目标位置有坐标，
  即 {p_chain['coordinate_mapped_query_fraction']:.2%}，映射区间为目标位置 92–291。因此它必须
  标注 `partial`，不能因为序列检索 coverage=100% 就声称坐标完整。

9R2Q 的四条匹配链属于同一目标实体，但空间位置不同。专家已有 R-58 多链规则规定“无法唯一
确定设计链→failure 级 WARNING + 禁止自动交接”，所以这里直接执行现有规则，不新增一个让用户
决定“随便选哪条链”的问题。

## 4. 边界和选择规则验证

受控夹具共 {controlled['case_count']} 个，全部符合预期：

- identity=0.95 不通过；coverage=0.90 不通过；两者都严格大于阈值才通过。
- X-ray 2.0 Å 与 cryo-EM 3.5 Å 可比时选 2.0 Å。
- 相同分辨率不按返回顺序选第一条，保留为未决 tie。
- 0、负值和 null 不参与正 Å 最小值。
- NMR 与有分辨率的 X-ray/cryo-EM 不强行比较。
- 多条同等匹配链按 R-58 阻止自动交接。

夹具见 [strict-filter-and-selection-cases.json](../inputs/controlled/strict-filter-and-selection-cases.json)，
逐候选事实见 [strict_candidate_metadata.tsv](strict_candidate_metadata.tsv)，机器报告见
[task3_evidence.json](task3_evidence.json)。

## 5. 现在真正需要定点确认的两件事

### S07-T3-G01：coverage 的分母

S-07 原文只写 `coverage>90%`，没有像 C20 ToolSpec 那样明确写 query coverage。本次实测中，
ubiquitin 若使用 query coverage 保留 {u['strict_query_coverage_entries']} 个 entry；若使用 target
coverage，或要求两侧都超过 90%，只保留 {u['strict_target_coverage_entries']} 个。候选集合会改变，
所以这不是字段命名问题。

**建议**：S-07 将 coverage 明确为输入/query 序列覆盖率，因为它直接回答“目标序列有多少被实验
结构序列覆盖”；target coverage 同时保留作审计事实，但不加入现有 Hard Filter。生产契约冻结前
需要专家确认这一句。

### S07-T3-G02：NMR 和有正分辨率结构怎样排优先级

ubiquitin 的严格候选实际同时出现 X-ray、cryo-EM、solution NMR 和 solid-state NMR。原文能在
X-ray/cryo-EM 内按最小正 Å 选择 6Q00，但 NMR 没有可比的 Å 数值；ToolSpec 只写“NMR 单列
优先级+WARNING”，没有给出优先级。

**建议**：按方法组保留候选；当存在合格 X-ray/cryo-EM 时，先取其中最小正 Å，NMR 作为备选并
警告；只有无可比候选时再进入 NMR 选择。若专家不同意，应返回各方法组最优项供明确选择，不能
使用数据库返回顺序。

## 6. 尚未完成的生产工作

- 当前只保存 6Q00、9R2Q 两个文件验证候选，没有部署完整本地 mmCIF archive。
- Windows MMseqs2 包只证明检索口径可执行；目标 Linux 二进制、索引、资源和离线健康检查仍待验收。
- 两项规则确认、完整结构文件发布和最终契约完成前，不实现生产适配器，不把任何候选写成生产选择。
"""
    markdown_path = reports / "TASK3_EVIDENCE_REPORT.md"
    markdown_path.write_text(markdown, encoding="utf-8")

    campaign_files = sorted(
        path
        for path in campaign.rglob("*")
        if not path.is_symlink()
        and not any(part.startswith("tmp-") for part in path.relative_to(campaign).parts)
        and path.is_file()
        and path.name != "artifact_manifest.json"
    )
    manifest = {
        "schema_version": "s07-task3-artifact-manifest.v0.1",
        "campaign_id": CAMPAIGN_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_deployment_status": "NOT_DEPLOYED",
        "campaign_files": [file_ref(path, root) for path in campaign_files],
        "external_frozen_dependencies": [
            file_ref(sequence_archive, root),
            file_ref(filtered_fasta, root),
            file_ref(filtered_manifest, root),
            file_ref(entries_path, root),
            file_ref(release_api_path, root),
            file_ref(archive_path, root),
            file_ref(executable_path, root),
            *[file_ref(path, root) for path in db_files],
        ],
    }
    (reports / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["overall_evidence_status"],
                "strict_candidate_keys": len(strict_keys),
                "controlled_cases": controlled["case_count"],
                "file_validations": len(file_validations),
                "report": str(markdown_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    build()
