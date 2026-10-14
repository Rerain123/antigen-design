"""Deterministic helpers for the S-07 task 6 acceptance harness.

This package is intentionally not wired to MCP or Dify.  It evaluates frozen
acceptance inputs under the five user-approved provisional rules and keeps the
pending expert status attached to every decision that depends on those rules.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


IDENTITY_THRESHOLD = 0.95
COVERAGE_THRESHOLD = 0.90
MAX_RESULTS_PER_QUERY = 10_000
CLASSIFICATION = "NON_PRODUCTION_S07_ACCEPTANCE"
DEPLOYMENT_STATUS = "NOT_DEPLOYED"
RULE_STATUS = "PROVISIONAL_USER_APPROVED_EXPERT_PENDING"
EXPERT_CONFIRMATION_IDS = [f"S07-EQ-{number:02d}" for number in range(1, 6)]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_fasta(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    identifier: str | None = None
    chunks: list[str] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if identifier is not None:
                records[identifier] = "".join(chunks).upper()
            identifier = line[1:].split()[0]
            chunks = []
        else:
            if identifier is None:
                raise ValueError(f"FASTA sequence precedes a header: {path}")
            chunks.append("".join(line.split()))
    if identifier is not None:
        records[identifier] = "".join(chunks).upper()
    if not records or any(not sequence for sequence in records.values()):
        raise ValueError(f"FASTA contains no complete records: {path}")
    return records


def read_mmseqs(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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
            rows.append(row)
    return rows


def strict_candidate_passes(row: dict[str, Any]) -> bool:
    """Apply the expert's strict PDB gate using provisional query coverage."""

    return (
        float(row["fident"]) > IDENTITY_THRESHOLD
        and float(row["qcov"]) > COVERAGE_THRESHOLD
    )


def target_parts(target: str) -> tuple[str, str]:
    entry_id, chain_id = target.split("_", 1)
    return entry_id.upper(), chain_id


def method_group(method: str) -> str:
    normalized = method.upper()
    if "X-RAY" in normalized:
        return "X_RAY"
    if "ELECTRON MICROSCOPY" in normalized:
        return "CRYO_EM"
    if "NMR" in normalized:
        return "NMR"
    return "OTHER"


def read_entries_index(path: Path) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    with path.open(encoding="latin-1", errors="replace") as handle:
        next(handle)
        next(handle)
        for line in handle:
            columns = line.rstrip("\r\n").split("\t")
            if len(columns) < 8:
                continue
            try:
                parsed = float(columns[6])
                resolution: float | None = parsed if parsed > 0 else None
            except ValueError:
                resolution = None
            entry_id = columns[0].upper()
            entries[entry_id] = {
                "entry_id": entry_id,
                "method": columns[7],
                "method_group": method_group(columns[7]),
                "resolution_angstrom": resolution,
                "accession_date": columns[2],
            }
    return entries


def summarize_queries(
    rows: Iterable[dict[str, Any]], entries: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not strict_candidate_passes(row):
            raise ValueError(f"MMseqs output contains a row outside the strict gate: {row['target']}")
        entry_id, chain_id = target_parts(str(row["target"]))
        metadata = entries.get(entry_id)
        if metadata is None:
            raise ValueError(f"PDB entry metadata missing for {entry_id}")
        grouped[str(row["query"])].append(
            {
                **row,
                **metadata,
                "chain_id": chain_id,
            }
        )

    summaries: dict[str, dict[str, Any]] = {}
    for query, candidates in grouped.items():
        entry_ids = {item["entry_id"] for item in candidates}
        summaries[query] = {
            "query": query,
            "candidate_chain_count": len(candidates),
            "candidate_entry_count": len(entry_ids),
            "collection_complete": len(candidates) < MAX_RESULTS_PER_QUERY,
            "observed_at_cap": len(candidates) >= MAX_RESULTS_PER_QUERY,
            "selection": select_experimental_candidate(candidates),
        }
    return summaries


def select_experimental_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Select or stop under EQ-02 and R-58 without an implicit tie breaker."""

    if not candidates:
        return {
            "status": "NO_STRICT_CANDIDATE",
            "selected_entry_id": None,
            "selected_chain_id": None,
            "reason_codes": ["PDB_SEARCH_COMPLETE_EMPTY"],
        }

    by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_entry[str(candidate["entry_id"])].append(candidate)

    comparable = [
        items[0]
        for items in by_entry.values()
        if items[0]["method_group"] in {"X_RAY", "CRYO_EM"}
        and isinstance(items[0]["resolution_angstrom"], (int, float))
        and items[0]["resolution_angstrom"] > 0
    ]
    pending_rules = ["S07-EQ-02"]
    warning_codes: list[str] = []
    if comparable:
        minimum = min(item["resolution_angstrom"] for item in comparable)
        best_entries = sorted(
            item["entry_id"]
            for item in comparable
            if item["resolution_angstrom"] == minimum
        )
        if any(items[0]["method_group"] == "NMR" for items in by_entry.values()):
            warning_codes.append("NMR_CANDIDATES_RETAINED_AS_PROVISIONAL_BACKUP")
        if any(items[0]["method_group"] == "OTHER" for items in by_entry.values()):
            warning_codes.append(
                "INCOMPARABLE_METHOD_CANDIDATES_RETAINED_AS_PROVISIONAL_BACKUP"
            )
        reason = "MINIMUM_POSITIVE_ANGSTROM_UNDER_PROVISIONAL_EQ02"
    else:
        nmr_entries = sorted(
            entry_id
            for entry_id, items in by_entry.items()
            if items[0]["method_group"] == "NMR"
        )
        if not nmr_entries:
            return {
                "status": "REVIEW_REQUIRED",
                "selected_entry_id": None,
                "selected_chain_id": None,
                "reason_codes": ["NO_COMPARABLE_POSITIVE_RESOLUTION"],
                "expert_confirmation_ids": pending_rules,
            }
        best_entries = nmr_entries
        reason = "NMR_FALLBACK_UNDER_PROVISIONAL_EQ02"
        warning_codes.append("NMR_RESOLUTION_NOT_COMPARABLE")

    if len(best_entries) != 1:
        return {
            "status": "REVIEW_REQUIRED",
            "selected_entry_id": None,
            "selected_chain_id": None,
            "tied_entry_ids": best_entries,
            "reason_codes": ["BEST_ENTRY_TIE_UNRESOLVED", reason, *warning_codes],
            "expert_confirmation_ids": pending_rules,
        }

    entry_id = best_entries[0]
    chains = sorted({item["chain_id"] for item in by_entry[entry_id]})
    if len(chains) != 1:
        return {
            "status": "REVIEW_REQUIRED",
            "selected_entry_id": None,
            "selected_chain_id": None,
            "candidate_entry_id": entry_id,
            "matching_chain_ids": chains,
            "reason_codes": [
                "R58_AMBIGUOUS_MATCHING_CHAINS_BLOCK_AUTO_HANDOFF",
                reason,
                *warning_codes,
            ],
            "expert_confirmation_ids": pending_rules,
        }

    selected = by_entry[entry_id][0]
    return {
        "status": "SELECTED_PROVISIONAL",
        "selected_entry_id": entry_id,
        "selected_chain_id": chains[0],
        "method": selected["method"],
        "method_group": selected["method_group"],
        "resolution_angstrom": selected["resolution_angstrom"],
        "reason_codes": [reason, *warning_codes],
        "expert_confirmation_ids": pending_rules,
        "rule_status": RULE_STATUS,
    }


def rcsb_match_context(result: dict[str, Any]) -> dict[str, Any] | None:
    for service in result.get("services", []):
        if service.get("service_type") != "sequence":
            continue
        for node in service.get("nodes", []):
            contexts = node.get("match_context") or []
            if contexts:
                return contexts[0]
    return None


def rcsb_strict_matches(payloads: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for payload in payloads:
        for result in payload.get("result_set", []):
            context = rcsb_match_context(result)
            if context is None:
                raise ValueError(f"verbose RCSB result lacks sequence context: {result.get('identifier')}")
            query_length = int(context["query_length"])
            query_coverage = (
                int(context["query_end"]) - int(context["query_beg"]) + 1
            ) / query_length
            identity = float(context["sequence_identity"])
            if identity > IDENTITY_THRESHOLD and query_coverage > COVERAGE_THRESHOLD:
                matches.append(
                    {
                        "identifier": result["identifier"],
                        "identity": identity,
                        "query_coverage": query_coverage,
                        "target_coverage": (
                            int(context["subject_end"])
                            - int(context["subject_beg"])
                            + 1
                        )
                        / int(context["subject_length"]),
                        "evalue": context.get("evalue"),
                        "bitscore": context.get("bitscore"),
                    }
                )
    return matches


def parse_mmcif_sequence_and_coordinates(path: Path, chain_id: str) -> dict[str, Any]:
    try:
        from Bio.PDB.MMCIF2Dict import MMCIF2Dict
    except ImportError as exc:  # pragma: no cover - explicit acceptance dependency
        raise RuntimeError("Biopython is required for task 6 acceptance") from exc

    document = MMCIF2Dict(str(path))

    def values(key: str) -> list[Any]:
        value = document.get(key)
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    entity_sequences = {
        str(entity): re.sub(r"\s+", "", str(sequence)).upper()
        for entity, sequence in zip(
            values("_entity_poly.entity_id"),
            values("_entity_poly.pdbx_seq_one_letter_code_can"),
            strict=True,
        )
    }
    positions: set[int] = set()
    chain_entities: set[str] = set()
    for auth_chain, entity, position, group, model in zip(
        values("_atom_site.auth_asym_id"),
        values("_atom_site.label_entity_id"),
        values("_atom_site.label_seq_id"),
        values("_atom_site.group_PDB"),
        values("_atom_site.pdbx_PDB_model_num"),
        strict=True,
    ):
        if str(auth_chain) != chain_id or str(group) != "ATOM" or str(model) != "1":
            continue
        if str(position) in {".", "?"}:
            continue
        positions.add(int(position))
        chain_entities.add(str(entity))
    if len(chain_entities) != 1:
        raise ValueError(f"chain {chain_id} does not resolve to one entity in {path}")
    entity_id = next(iter(chain_entities))
    sequence = entity_sequences[entity_id]
    missing = sorted(set(range(1, len(sequence) + 1)) - positions)
    return {
        "entity_id": entity_id,
        "chain_id": chain_id,
        "sequence": sequence,
        "sequence_sha256": sha256_bytes(sequence.encode("ascii")),
        "sequence_length": len(sequence),
        "coordinate_count": len(positions),
        "coordinate_complete": not missing,
        "missing_positions": missing,
    }


def file_reference(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
