"""Build reproducible P0-M1 reports from the frozen S-07 discovery evidence.

This script is deliberately campaign-specific.  It reads already captured raw
evidence and never calls a remote service.  The resulting classifications are
marked as provisional discovery facts and must not be used as production
scientific decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


CAMPAIGN_ID = "p0-s07-discovery-20260901-a"
POLICY_STATUS = "PROVISIONAL_DISCOVERY_POLICY"
DEPLOYMENT_STATUS = "NOT_DEPLOYED"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign-root",
        type=Path,
        default=Path("discovery/p0/s07") / CAMPAIGN_ID,
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable(path: Path) -> str:
    return path.as_posix()


def file_ref(campaign_root: Path, relative_path: str) -> dict[str, Any]:
    path = campaign_root / relative_path
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": portable(Path(relative_path)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def workspace_file_ref(
    workspace: Path, relative_path: str, storage_class: str
) -> dict[str, Any]:
    path = workspace / relative_path
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "workspace_relative_path": portable(Path(relative_path)),
        "storage_class": storage_class,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def read_fasta(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith(">"):
        raise ValueError(f"invalid FASTA: {path}")
    sequence = "".join(line.strip() for line in lines[1:] if line.strip()).upper()
    if not sequence or not sequence.isascii() or not sequence.isalpha():
        raise ValueError(f"invalid protein sequence: {path}")
    return lines[0][1:], sequence


def ranges_from_positions(positions: Iterable[int]) -> list[dict[str, int]]:
    ordered = sorted(set(positions))
    if not ordered:
        return []
    ranges: list[dict[str, int]] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value != previous + 1:
            ranges.append({"start": start, "end": previous})
            start = value
        previous = value
    ranges.append({"start": start, "end": previous})
    return ranges


def expand_ranges(ranges: Iterable[dict[str, int]]) -> set[int]:
    result: set[int] = set()
    for item in ranges:
        result.update(range(int(item["start"]), int(item["end"]) + 1))
    return result


def unobserved_ranges(instance: dict[str, Any]) -> list[dict[str, int]]:
    positions: list[int] = []
    for feature in instance.get("rcsb_polymer_instance_feature", []):
        if feature.get("type") != "UNOBSERVED_RESIDUE_XYZ":
            continue
        for item in feature.get("feature_positions", []):
            begin = int(item["beg_seq_id"])
            end = int(item.get("end_seq_id", begin))
            positions.extend(range(begin, end + 1))
    return ranges_from_positions(positions)


def find_rcsb_hit(response: dict[str, Any], identifier: str) -> dict[str, Any]:
    for hit in response.get("result_set", []):
        if hit.get("identifier") == identifier:
            services = hit.get("services", [])
            if isinstance(services, dict):
                services = [services]
            contexts: list[dict[str, Any]] = []
            for service in services:
                nodes = service.get("nodes", [])
                if isinstance(nodes, dict):
                    nodes = [nodes]
                for node in nodes:
                    contexts.extend(node.get("match_context", []))
            if not contexts:
                raise ValueError(f"RCSB hit has no match context: {identifier}")
            return {"hit": hit, "context": contexts[0]}
    raise ValueError(f"RCSB hit not present in captured result set: {identifier}")


def map_alignment(
    *,
    context: dict[str, Any],
    target_length: int,
    entity_length: int,
    unobserved_entity_ranges: list[dict[str, int]],
) -> dict[str, Any]:
    query = context["query_aligned_seq"]
    subject = context["subject_aligned_seq"]
    if len(query) != len(subject):
        raise ValueError("aligned sequence lengths differ")

    query_position = int(context["query_beg"]) - 1
    subject_position = int(context["subject_beg"]) - 1
    aligned_query_positions: set[int] = set()
    mapped_pairs: list[tuple[int, int]] = []
    for query_residue, subject_residue in zip(query, subject, strict=True):
        if query_residue != "-":
            query_position += 1
            aligned_query_positions.add(query_position)
        if subject_residue != "-":
            subject_position += 1
        if query_residue != "-" and subject_residue != "-":
            mapped_pairs.append((query_position, subject_position))

    unobserved = expand_ranges(unobserved_entity_ranges)
    coordinate_positions = {
        query_pos for query_pos, subject_pos in mapped_pairs if subject_pos not in unobserved
    }
    mapped_unobserved = {
        query_pos for query_pos, subject_pos in mapped_pairs if subject_pos in unobserved
    }
    all_target_positions = set(range(1, target_length + 1))
    unaligned_positions = all_target_positions - aligned_query_positions

    return {
        "target_length": target_length,
        "entity_length": entity_length,
        "sequence_identity": float(context["sequence_identity"]),
        "alignment_length": int(context["alignment_length"]),
        "mismatches": int(context["mismatches"]),
        "gaps_opened": int(context["gaps_opened"]),
        "evalue": float(context["evalue"]),
        "bitscore": float(context["bitscore"]),
        "query_alignment_range": {
            "start": int(context["query_beg"]),
            "end": int(context["query_end"]),
        },
        "entity_alignment_range": {
            "start": int(context["subject_beg"]),
            "end": int(context["subject_end"]),
        },
        "aligned_target_residue_count": len(aligned_query_positions),
        "aligned_target_fraction": round(len(aligned_query_positions) / target_length, 8),
        "coordinate_mapped_target_residue_count": len(coordinate_positions),
        "coordinate_mapped_target_fraction": round(
            len(coordinate_positions) / target_length, 8
        ),
        "coordinate_mapped_target_ranges": ranges_from_positions(coordinate_positions),
        "mapped_but_unobserved_target_ranges": ranges_from_positions(mapped_unobserved),
        "unaligned_target_ranges": ranges_from_positions(unaligned_positions),
        "unobserved_entity_ranges": unobserved_entity_ranges,
        "raw_alignment": {
            "query_aligned_sequence": query,
            "entity_aligned_sequence": subject,
        },
    }


def validate_exchange_response(exchange_path: Path) -> None:
    exchange = read_json(exchange_path)
    response = exchange.get("response")
    if not response or not response.get("body_file"):
        return
    body_path = exchange_path.parent / response["body_file"]
    if not body_path.is_file():
        raise FileNotFoundError(body_path)
    if body_path.stat().st_size != response["body_size_bytes"]:
        raise ValueError(f"size mismatch: {body_path}")
    if sha256_file(body_path) != response["body_sha256"]:
        raise ValueError(f"SHA-256 mismatch: {body_path}")


def validate_cli_streams(exchange_path: Path, workspace: Path) -> None:
    exchange = read_json(exchange_path)
    for stream_name in ("stdout", "stderr"):
        stream = exchange.get(stream_name)
        if not stream:
            continue
        if stream.get("file"):
            stream_path = exchange_path.parent / stream["file"]
        elif stream.get("workspace_relative_path"):
            stream_path = workspace / stream["workspace_relative_path"]
        else:
            continue
        if not stream_path.is_file():
            raise FileNotFoundError(stream_path)
        if stream_path.stat().st_size != stream["size_bytes"]:
            raise ValueError(f"size mismatch: {stream_path}")
        if sha256_file(stream_path) != stream["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {stream_path}")


def parse_blast_tabular(path: Path) -> dict[str, Any]:
    fields: list[str] | None = None
    declared_hit_count: int | None = None
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# Fields: "):
            fields = [item.strip() for item in line.removeprefix("# Fields: ").split(",")]
        elif line.startswith("# ") and line.endswith(" hits found"):
            match = re.match(r"# (\d+) hits found", line)
            declared_hit_count = int(match.group(1)) if match else None
        elif line and not line.startswith("#"):
            rows.append(line.split("\t"))
    if fields is None or declared_hit_count is None:
        raise ValueError(f"BLAST metadata missing: {path}")
    if len(rows) != declared_hit_count:
        raise ValueError(f"BLAST hit count mismatch: {path}")

    # Stable machine names for the exact outfmt used by the campaign.
    machine_fields = [
        "qseqid",
        "sseqid",
        "pident",
        "length",
        "mismatch",
        "gapopen",
        "qstart",
        "qend",
        "sstart",
        "send",
        "evalue",
        "bitscore",
        "qcovhsp",
        "qcovs",
        "qseq",
        "sseq",
        "stitle",
    ]
    if rows and len(rows[0]) != len(machine_fields):
        raise ValueError(f"unexpected BLAST column count: {path}")
    typed_rows: list[dict[str, Any]] = []
    for row in rows:
        item = dict(zip(machine_fields, row, strict=True))
        for key in ("pident", "evalue", "bitscore", "qcovhsp", "qcovs"):
            item[key] = float(item[key])
        for key in (
            "length",
            "mismatch",
            "gapopen",
            "qstart",
            "qend",
            "sstart",
            "send",
        ):
            item[key] = int(item[key])
        typed_rows.append(item)
    return {
        "declared_fields": fields,
        "hit_count": declared_hit_count,
        "hits": typed_rows,
    }


def exchange_outcome(exchange: dict[str, Any]) -> str:
    if "curl" in exchange:
        exit_code = int(exchange["curl"].get("exit_code", 0))
        http_code = int(exchange["curl"].get("metrics", {}).get("http_code", 0))
        if exit_code != 0:
            return "TRANSPORT_FAILURE"
        if http_code == 204:
            return "HTTP_NO_CONTENT"
        if http_code >= 400:
            return "HTTP_ERROR_RESPONSE"
        if 200 <= http_code < 300:
            return "HTTP_SUCCESS"
        return "HTTP_OTHER"
    if "exit_code" in exchange:
        if exchange.get("timed_out"):
            return "CLI_TIMEOUT"
        return "CLI_SUCCESS" if exchange["exit_code"] == 0 else "CLI_FAILURE"
    return "UNKNOWN"


def build_reports(campaign_root: Path) -> None:
    campaign_root = campaign_root.resolve()
    if campaign_root.name != CAMPAIGN_ID:
        raise ValueError(f"unexpected campaign root: {campaign_root}")
    workspace = campaign_root.parents[3]
    reports_dir = campaign_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    samples_doc = read_json(campaign_root / "samples/samples.json")
    sample_by_case = {item["case_id"]: item for item in samples_doc["cases"]}

    candidate_specs = [
        {
            "case_id": "P0-DISC-001",
            "candidate_id": "RCSB:1UBQ_1:A",
            "search_response": "evidence/rcsb/P0-DISC-001/search-exact-attempt-04/response.json",
            "search_identifier": "1UBQ_1",
            "entry": "evidence/rcsb/P0-DISC-001/entry-1UBQ/response.json",
            "entity": "evidence/rcsb/P0-DISC-001/polymer-entity-1UBQ-1/response.json",
            "instance": "evidence/rcsb/P0-DISC-001/polymer-instance-1UBQ-A/response.json",
            "artifact": "evidence/rcsb/P0-DISC-001/mmcif-1UBQ/1UBQ.cif",
            "classification": "TARGET_MATCH",
            "classification_basis": "normalized target sequence equals the complete RCSB polymer-entity canonical sequence",
        },
        {
            "case_id": "P0-DISC-002",
            "candidate_id": "RCSB:6XRE_13:M",
            "search_response": "evidence/rcsb/P0-DISC-002/search-attempt-01/response.json",
            "search_identifier": "6XRE_13",
            "entry": "evidence/rcsb/P0-DISC-002/entry-6XRE/response.json",
            "entity": "evidence/rcsb/P0-DISC-002/polymer-entity-6XRE-13/response.json",
            "instance": "evidence/rcsb/P0-DISC-002/polymer-instance-6XRE-M/response.json",
            "artifact": "evidence/rcsb/P0-DISC-002/mmcif-6XRE-attempt-02/6XRE.cif",
            "classification": "TARGET_MATCH",
            "classification_basis": "complete polymer-entity sequence is an exact target match; coordinates are independently incomplete",
        },
        {
            "case_id": "P0-DISC-002",
            "candidate_id": "RCSB:5XZC_2:B",
            "search_response": "evidence/rcsb/P0-DISC-002/search-attempt-01/response.json",
            "search_identifier": "5XZC_2",
            "entry": "evidence/rcsb/P0-DISC-002/entry-5XZC/response.json",
            "entity": "evidence/rcsb/P0-DISC-002/polymer-entity-5XZC-2/response.json",
            "instance": "evidence/rcsb/P0-DISC-002/polymer-instance-5XZC-B/response.json",
            "artifact": "evidence/rcsb/P0-DISC-002/mmcif-5XZC-attempt-02/5XZC.cif",
            "classification": "TARGET_DERIVED",
            "classification_basis": "same UniProt target but the polymer entity is target residues 92-356 rather than the complete 393-residue target",
        },
        {
            "case_id": "P0-DISC-003",
            "candidate_id": "RCSB:6PPV_1:A",
            "search_response": "evidence/rcsb/P0-DISC-003/homolog-search-attempt-01/response.json",
            "search_identifier": "6PPV_1",
            "entry": "evidence/rcsb/P0-DISC-003/entry-6PPV/response.json",
            "entity": "evidence/rcsb/P0-DISC-003/polymer-entity-6PPV-1/response.json",
            "instance": "evidence/rcsb/P0-DISC-003/polymer-instance-6PPV-A/response.json",
            "artifact": "evidence/rcsb/P0-DISC-003/mmcif-6PPV/6PPV.cif",
            "classification": "HOMOLOG_TEMPLATE",
            "classification_basis": "different UniProt sequence with a 62.5% identity local alignment over 72 target residues",
        },
    ]

    candidates: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    for spec in candidate_specs:
        sample = sample_by_case[spec["case_id"]]
        _, target_sequence = read_fasta(campaign_root / "samples" / sample["sequence_file"])
        search = read_json(campaign_root / spec["search_response"])
        hit = find_rcsb_hit(search, spec["search_identifier"])
        entry = read_json(campaign_root / spec["entry"])
        entity = read_json(campaign_root / spec["entity"])
        instance = read_json(campaign_root / spec["instance"])
        entity_sequence = entity["entity_poly"]["pdbx_seq_one_letter_code_can"].replace("\n", "")
        entity_sequence = re.sub(r"\s+", "", entity_sequence)
        entity_length = int(entity["entity_poly"]["rcsb_sample_sequence_length"])
        if len(entity_sequence) != entity_length:
            raise ValueError(f"entity sequence length mismatch: {spec['candidate_id']}")
        unobserved = unobserved_ranges(instance)
        mapping = map_alignment(
            context=hit["context"],
            target_length=len(target_sequence),
            entity_length=entity_length,
            unobserved_entity_ranges=unobserved,
        )
        mapping.update(
            {
                "case_id": spec["case_id"],
                "candidate_id": spec["candidate_id"],
                "source": "RCSB_PDB",
                "alignment_engine": "RCSB_SEQUENCE_SEARCH_MMSEQS2",
                "classification": spec["classification"],
                "classification_status": POLICY_STATUS,
            }
        )
        mappings.append(mapping)

        info = entry["rcsb_entry_info"]
        identifiers = entity["rcsb_polymer_entity_container_identifiers"]
        candidates.append(
            {
                "case_id": spec["case_id"],
                "candidate_id": spec["candidate_id"],
                "source": "RCSB_PDB",
                "structure_kind": "EXPERIMENTAL",
                "classification": spec["classification"],
                "classification_status": POLICY_STATUS,
                "classification_basis": spec["classification_basis"],
                "selected_for_production": False,
                "conservative_route": (
                    "EXISTING_STRUCTURE_CANDIDATE_PENDING_RULES"
                    if spec["classification"] == "TARGET_MATCH"
                    else "ENTER_S08_UNDER_PROVISIONAL_POLICY"
                ),
                "entry_facts": {
                    "experimental_method": info.get("experimental_method"),
                    "resolution_angstrom": (info.get("resolution_combined") or [None])[0],
                },
                "entity_facts": {
                    "entity_length": entity_length,
                    "uniprot_accessions": identifiers.get("uniprot_ids", []),
                    "artifact_monomer_count": entity["entity_poly"].get(
                        "rcsb_artifact_monomer_count"
                    ),
                    "mutation_count": entity["entity_poly"].get("rcsb_mutation_count"),
                },
                "chain_facts": {
                    "modeled_residue_count": instance["rcsb_polymer_instance_info"].get(
                        "modeled_residue_count"
                    ),
                    "unobserved_entity_ranges": unobserved,
                },
                "target_mapping_summary": {
                    "sequence_identity": mapping["sequence_identity"],
                    "aligned_target_fraction": mapping["aligned_target_fraction"],
                    "coordinate_mapped_target_fraction": mapping[
                        "coordinate_mapped_target_fraction"
                    ],
                },
                "structure_artifact": file_ref(campaign_root, spec["artifact"]),
                "evidence": {
                    "search_response": file_ref(campaign_root, spec["search_response"]),
                    "entry_response": file_ref(campaign_root, spec["entry"]),
                    "entity_response": file_ref(campaign_root, spec["entity"]),
                    "instance_response": file_ref(campaign_root, spec["instance"]),
                },
            }
        )

    # AlphaFold DB representative candidate for the same sequence as P0-DISC-003.
    afdb_case = sample_by_case["P0-DISC-004"]
    _, afdb_target_sequence = read_fasta(
        campaign_root / "samples" / afdb_case["sequence_file"]
    )
    afdb_metadata_path = campaign_root / (
        "evidence/afdb/P0-DISC-004/prediction-O15116-attempt-02/response.json"
    )
    afdb_metadata = read_json(afdb_metadata_path)[0]
    if afdb_metadata["sequence"] != afdb_target_sequence:
        raise ValueError("AlphaFold DB metadata sequence does not match the frozen target")
    afdb_cif_relative = (
        "evidence/afdb/P0-DISC-004/model-cif-v6/AF-O15116-F1-model_v6.cif"
    )
    atom_residue_ids: set[int] = set()
    for line in (campaign_root / afdb_cif_relative).read_text(encoding="utf-8").splitlines():
        if line.startswith("ATOM "):
            columns = line.split()
            atom_residue_ids.add(int(columns[8]))
    if atom_residue_ids != set(range(1, len(afdb_target_sequence) + 1)):
        raise ValueError("AlphaFold DB mmCIF does not contain ATOM rows for every target residue")

    confidence_relative = (
        "evidence/afdb/P0-DISC-004/confidence-v6/AF-O15116-F1-confidence_v6.json"
    )
    pae_relative = (
        "evidence/afdb/P0-DISC-004/pae-v6/AF-O15116-F1-predicted_aligned_error_v6.json"
    )
    confidence = read_json(campaign_root / confidence_relative)
    pae = read_json(campaign_root / pae_relative)
    if isinstance(confidence, list):
        if len(confidence) != 1:
            raise ValueError("unexpected AlphaFold DB confidence document count")
        confidence = confidence[0]
    if isinstance(pae, list):
        if len(pae) != 1:
            raise ValueError("unexpected AlphaFold DB PAE document count")
        pae = pae[0]
    if len(confidence["confidenceScore"]) != len(afdb_target_sequence):
        raise ValueError("AlphaFold DB confidence length mismatch")
    if len(pae["predicted_aligned_error"]) != len(afdb_target_sequence):
        raise ValueError("AlphaFold DB PAE row count mismatch")
    if any(len(row) != len(afdb_target_sequence) for row in pae["predicted_aligned_error"]):
        raise ValueError("AlphaFold DB PAE matrix is not square")

    afdb_mapping = {
        "case_id": "P0-DISC-004",
        "candidate_id": "AFDB:AF-O15116-F1:v6:A",
        "source": "ALPHAFOLD_DB",
        "alignment_engine": "EXACT_SEQUENCE_REVALIDATION",
        "classification": "TARGET_MATCH",
        "classification_status": POLICY_STATUS,
        "target_length": len(afdb_target_sequence),
        "entity_length": len(afdb_target_sequence),
        "sequence_identity": 1.0,
        "alignment_length": len(afdb_target_sequence),
        "mismatches": 0,
        "gaps_opened": 0,
        "query_alignment_range": {"start": 1, "end": len(afdb_target_sequence)},
        "entity_alignment_range": {"start": 1, "end": len(afdb_target_sequence)},
        "aligned_target_residue_count": len(afdb_target_sequence),
        "aligned_target_fraction": 1.0,
        "coordinate_mapped_target_residue_count": len(atom_residue_ids),
        "coordinate_mapped_target_fraction": 1.0,
        "coordinate_mapped_target_ranges": ranges_from_positions(atom_residue_ids),
        "mapped_but_unobserved_target_ranges": [],
        "unaligned_target_ranges": [],
        "unobserved_entity_ranges": [],
        "raw_alignment": {
            "query_aligned_sequence": afdb_target_sequence,
            "entity_aligned_sequence": afdb_metadata["sequence"],
        },
    }
    mappings.append(afdb_mapping)
    candidates.append(
        {
            "case_id": "P0-DISC-004",
            "candidate_id": "AFDB:AF-O15116-F1:v6:A",
            "source": "ALPHAFOLD_DB",
            "structure_kind": "PUBLIC_PREDICTED",
            "classification": "TARGET_MATCH",
            "classification_status": POLICY_STATUS,
            "classification_basis": "frozen target sequence exactly matches the AlphaFold DB v6 metadata sequence and downloaded model",
            "selected_for_production": False,
            "conservative_route": "EXISTING_STRUCTURE_CANDIDATE_PENDING_RULES",
            "model_facts": {
                "tool_used": afdb_metadata["toolUsed"],
                "model_created_date": afdb_metadata["modelCreatedDate"],
                "latest_version": afdb_metadata["latestVersion"],
                "global_metric_value": afdb_metadata["globalMetricValue"],
                "confidence_vector_length": len(confidence["confidenceScore"]),
                "pae_matrix_shape": [
                    len(pae["predicted_aligned_error"]),
                    len(pae["predicted_aligned_error"][0]),
                ],
                "max_predicted_aligned_error": pae["max_predicted_aligned_error"],
                "quality_classification_note": "native quality facts only; S-09 thresholds are not applied in P0-M1",
            },
            "target_mapping_summary": {
                "sequence_identity": 1.0,
                "aligned_target_fraction": 1.0,
                "coordinate_mapped_target_fraction": 1.0,
            },
            "structure_artifact": file_ref(campaign_root, afdb_cif_relative),
            "confidence_artifact": file_ref(campaign_root, confidence_relative),
            "pae_artifact": file_ref(campaign_root, pae_relative),
            "evidence": {
                "metadata_response": file_ref(
                    campaign_root,
                    "evidence/afdb/P0-DISC-004/prediction-O15116-attempt-02/response.json",
                )
            },
        }
    )

    blast_profile = read_json(campaign_root / "requests/blast/discovery-profile.json")
    blast_cases: list[dict[str, Any]] = []
    for case_id in ("P0-DISC-001", "P0-DISC-002", "P0-DISC-003", "P0-DISC-005"):
        tabular_relative = f"evidence/blast/{case_id}/format-tabular/result.tsv"
        archive_relative = f"evidence/blast/{case_id}/search/result.asn"
        json_relative = f"evidence/blast/{case_id}/format-json/result.json"
        parsed = parse_blast_tabular(campaign_root / tabular_relative)
        top_hit = parsed["hits"][0] if parsed["hits"] else None
        blast_cases.append(
            {
                "case_id": case_id,
                "hit_count": parsed["hit_count"],
                "result_cap": blast_profile["search_parameters"]["max_target_seqs"],
                "result_was_capped": parsed["hit_count"]
                == blast_profile["search_parameters"]["max_target_seqs"],
                "top_hit": top_hit,
                "artifacts": {
                    "archive": file_ref(campaign_root, archive_relative),
                    "tabular": file_ref(campaign_root, tabular_relative),
                    "json": file_ref(campaign_root, json_relative),
                },
            }
        )

    rcsb_004_exchange = read_json(
        campaign_root
        / "evidence/rcsb/P0-DISC-004/target-search-attempt-01/exchange.json"
    )
    rcsb_005_exchange = read_json(
        campaign_root
        / "evidence/rcsb/P0-DISC-005/target-search-attempt-01/exchange.json"
    )
    afdb_005_exchange = read_json(
        campaign_root
        / "evidence/afdb/P0-DISC-005/refseq-accession-attempt-01/exchange.json"
    )
    rcsb_search_001 = read_json(
        campaign_root
        / "evidence/rcsb/P0-DISC-001/search-exact-attempt-04/response.json"
    )
    rcsb_search_002 = read_json(
        campaign_root / "evidence/rcsb/P0-DISC-002/search-attempt-01/response.json"
    )
    rcsb_search_003 = read_json(
        campaign_root
        / "evidence/rcsb/P0-DISC-003/homolog-search-attempt-01/response.json"
    )
    blast_by_case = {item["case_id"]: item for item in blast_cases}

    case_outcomes = [
        {
            "case_id": "P0-DISC-001",
            "outcome": "TARGET_MATCH_REPRESENTATIVES_FOUND",
            "rcsb_total_count": rcsb_search_001["total_count"],
            "rcsb_returned_count": len(rcsb_search_001["result_set"]),
            "note": "many structures share the same target sequence; one fully characterized representative is retained",
        },
        {
            "case_id": "P0-DISC-002",
            "outcome": "TARGET_MATCH_AND_TARGET_DERIVED_REPRESENTATIVES_FOUND",
            "rcsb_total_count": rcsb_search_002["total_count"],
            "rcsb_returned_count": len(rcsb_search_002["result_set"]),
            "note": "sequence-level exactness and coordinate completeness are independent facts",
        },
        {
            "case_id": "P0-DISC-003",
            "outcome": "HOMOLOG_TEMPLATE_REPRESENTATIVE_FOUND",
            "rcsb_total_count": rcsb_search_003["total_count"],
            "rcsb_returned_count": len(rcsb_search_003["result_set"]),
            "blast_hit_count": blast_by_case["P0-DISC-003"]["hit_count"],
            "note": "template usability is not decided without algorithm-approved thresholds",
        },
        {
            "case_id": "P0-DISC-004",
            "outcome": "NO_EXACT_EXPERIMENTAL_TARGET_AND_AFDB_EXACT_TARGET_FOUND",
            "rcsb_http_status": rcsb_004_exchange["curl"]["metrics"]["http_code"],
            "afdb_candidate_id": "AF-O15116-F1",
            "note": "HTTP 204 is a successful empty target search, not a tool failure",
        },
        {
            "case_id": "P0-DISC-005",
            "outcome": "NO_EXACT_TARGET_EVIDENCE_HOMOLOG_USABILITY_UNDECIDED",
            "rcsb_http_status": rcsb_005_exchange["curl"]["metrics"]["http_code"],
            "afdb_http_status": afdb_005_exchange["curl"]["metrics"]["http_code"],
            "blast_hit_count": blast_by_case["P0-DISC-005"]["hit_count"],
            "blast_top_hit": blast_by_case["P0-DISC-005"]["top_hit"],
            "note": "AFDB rejected the RefSeq identifier format; weak BLAST output cannot be promoted to a usable homolog without approved thresholds",
        },
    ]

    manifest = {
        "schema_version": "p0-s07-candidate-structure-manifest.discovery.v0.1",
        "campaign_id": CAMPAIGN_ID,
        "classification": "discovery_evidence",
        "production_deployment_status": DEPLOYMENT_STATUS,
        "policy_status": POLICY_STATUS,
        "candidate_scope": "representative fully characterized candidates, not the complete search result sets",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "case_outcomes": case_outcomes,
        "decision_boundary": "No candidate is selected for production and no scientific threshold is introduced by this report.",
    }
    write_json(reports_dir / "candidate_structure_manifest.json", manifest)

    mapping_report = {
        "schema_version": "p0-s07-sequence-mapping-report.discovery.v0.1",
        "campaign_id": CAMPAIGN_ID,
        "classification": "discovery_evidence",
        "production_deployment_status": DEPLOYMENT_STATUS,
        "policy_status": POLICY_STATUS,
        "coordinate_coverage_definition": "fraction of target positions aligned to entity residues that have coordinates in the selected chain/model",
        "mapping_count": len(mappings),
        "mappings": mappings,
        "decision_boundary": "Mapping facts do not define minimum acceptable identity, alignment coverage, coordinate coverage, resolution, or confidence.",
    }
    write_json(reports_dir / "sequence_mapping_report.json", mapping_report)

    blast_archive = (
        workspace
        / "var/discovery-tools/ncbi-blast-2.17.0/ncbi-blast-2.17.0+-x64-win64.tar.gz"
    )
    blast_md5_path = blast_archive.with_name(blast_archive.name + ".md5")
    official_md5 = blast_md5_path.read_text(encoding="utf-8").split()[0].lower()
    actual_md5 = md5_file(blast_archive)
    if actual_md5 != official_md5:
        raise ValueError("NCBI BLAST+ archive MD5 mismatch")
    blast_dependency_manifest = {
        "schema_version": "p0-s07-blast-dependency-manifest.discovery.v0.1",
        "campaign_id": CAMPAIGN_ID,
        "classification": "discovery_evidence",
        "production_deployment_status": DEPLOYMENT_STATUS,
        "tool": {
            "name": "NCBI BLAST+",
            "version": "2.17.0+",
            "official_archive_url": "https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/2.17.0/ncbi-blast-2.17.0+-x64-win64.tar.gz",
            "official_md5_url": "https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/2.17.0/ncbi-blast-2.17.0+-x64-win64.tar.gz.md5",
            "archive": workspace_file_ref(
                workspace,
                "var/discovery-tools/ncbi-blast-2.17.0/ncbi-blast-2.17.0+-x64-win64.tar.gz",
                "workspace_ignored_discovery_dependency",
            ),
            "official_md5": official_md5,
            "actual_md5": actual_md5,
            "official_md5_matches": True,
        },
        "database": read_json(reports_dir / "wwpdb_protein_fasta_manifest.json"),
        "profile": blast_profile,
        "integrity_check": {
            "exchange": file_ref(
                campaign_root,
                "evidence/blast/database-integrity-full-attempt-04/exchange.json",
            ),
            "exit_code": 0,
            "result": "SUCCESS",
            "taxdb_required_for_metadata_check": True,
        },
        "cases": blast_cases,
    }
    write_json(reports_dir / "blast_dependency_and_results_manifest.json", blast_dependency_manifest)

    # Validate every exchange and build a compact inventory without recursively
    # hashing generated reports (which would make the inventory self-referential).
    exchange_records: list[dict[str, Any]] = []
    outcome_counts: Counter[str] = Counter()
    for exchange_path in sorted((campaign_root / "evidence").rglob("exchange.json")):
        exchange = read_json(exchange_path)
        if "curl" in exchange:
            validate_exchange_response(exchange_path)
        else:
            validate_cli_streams(exchange_path, workspace)
        outcome = exchange_outcome(exchange)
        outcome_counts[outcome] += 1
        record = {
            "path": portable(exchange_path.relative_to(campaign_root)),
            "exchange_id": exchange.get("exchange_id"),
            "outcome": outcome,
        }
        if "curl" in exchange:
            record["curl_exit_code"] = exchange["curl"].get("exit_code")
            record["http_code"] = exchange["curl"].get("metrics", {}).get("http_code")
        else:
            record["exit_code"] = exchange.get("exit_code")
            record["timed_out"] = exchange.get("timed_out")
        exchange_records.append(record)

    inventory_files: list[dict[str, Any]] = []
    inventory_roots = [
        campaign_root / "campaign.json",
        campaign_root / "README.md",
        campaign_root / "samples",
        campaign_root / "requests",
        campaign_root / "evidence",
    ]
    paths: list[Path] = []
    for item in inventory_roots:
        paths.extend([item] if item.is_file() else list(item.rglob("*")))
    for path in sorted({item for item in paths if item.is_file()}):
        inventory_files.append(
            {
                "path": portable(path.relative_to(campaign_root)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    inventory = {
        "schema_version": "p0-s07-evidence-inventory.v0.1",
        "campaign_id": CAMPAIGN_ID,
        "production_deployment_status": DEPLOYMENT_STATUS,
        "file_count": len(inventory_files),
        "total_size_bytes": sum(item["size_bytes"] for item in inventory_files),
        "files": inventory_files,
        "exchange_count": len(exchange_records),
        "exchange_outcome_counts": dict(sorted(outcome_counts.items())),
        "exchanges": exchange_records,
        "external_controlled_artifacts": [
            workspace_file_ref(
                workspace,
                "var/discovery-artifacts/p0-s07-discovery-20260901-a/database-integrity-full-attempt-02.stdout.txt",
                "workspace_ignored_controlled_artifact",
            )
        ],
    }
    write_json(reports_dir / "evidence_inventory.json", inventory)

    gap_table = """# P0-M1 S-07 能力缺口表

状态：`EVIDENCE_CAPTURE_COMPLETE / CONTRACT_REVIEW_REQUIRED`  
边界：以下结论只用于契约评审，不是生产科学规则，不代表 `structure.fetch` 已部署。

| ID | 实测事实 | 暴露的缺口 | P0-M2 前所需决定/实现 | 责任侧 | 阻塞 P0-M2 |
|---|---|---|---|---|---|
| S07-G01 | RCSB Search 返回 polymer entity，Data API 才提供 entry/entity/instance 事实，mmCIF 又是独立下载 | 单一“命中”对象不足以表达来源、链、实体和产物 | 冻结候选、链、实体、assembly/model 与 ArtifactRef 的层级 Schema | 开发评审 | 是 |
| S07-G02 | 6XRE entity 序列与目标 100% 相同，但 chain M 仅 314/393 个目标残基有坐标 | 序列 exact 不等于坐标完整或技术可用 | 算法负责人确认最低坐标覆盖、允许缺口位置及是否还要分辨率/方法门控 | 算法负责人 | 是 |
| S07-G03 | 5XZC 只覆盖目标 92-356，且 entity 201-233 无坐标 | `TARGET_DERIVED` 必须保存双层映射：target↔entity 与 entity↔coordinates | 冻结逐残基映射格式，以及 derived 是否可直接使用/何时必须进 S-08 | 算法负责人 + 开发 | 是 |
| S07-G04 | 6PPV 对 O15116 的局部 identity 为 62.5%，仅对齐目标 72/133；坐标映射为 69/133 | 有同源命中不等于有可用模板 | 确认 BLAST/MMseqs2 的用途、identity/coverage/e-value 规则和模板排序 | 算法负责人 | 是 |
| S07-G05 | O15116 的 RCSB target-level 查询（identity cutoff 0.9）为 HTTP 204，而 AFDB 以 O15116 返回 exact 133 aa v6 模型 | 实验结构和公共预测结构必须分来源表达，204 不能当故障 | 冻结来源优先级、AFDB 是否算“已有结构”、版本选择与序列回验规则 | 算法负责人 + 开发 | 是 |
| S07-G06 | AFDB 对 RefSeq `WP_505187596.1` 返回 HTTP 400，只接受 UniProt/支持的 AFDB ID | 权威输入只有序列时，不能直接保证找到 AFDB accession | 决定 sequence→UniProt 映射服务、物种约束、歧义处理和无映射降级 | 产品/算法负责人 | 是 |
| S07-G07 | RCSB sequence service 是 MMseqs2；独立 NCBI BLAST+ 对冻结 wwPDB FASTA 运行成功 | C6 “BLAST”不能由 RCSB Search 冒充，两套分数也不可混用 | 明确 C6 数据库、用途、输出字段与两类命中如何去重 | 算法负责人 | 是 |
| S07-G08 | 1UBQ RCSB exact 查询 total=1136、TP53 total=236；本次均只返回前 100 | 不分页/不去重会造成候选截断，排序可能随数据库更新变化 | 冻结分页上限、超量标志、去重键、排序与快照时间字段 | 开发评审 | 是 |
| S07-G09 | BLAST 前两类及同源样本均达到 `max_target_seqs=100`；P0-DISC-005 返回 42 个弱命中，首个 e-value=3.4 | discovery 参数不能充当生产阈值；“无可用结构”不能仅由有/无行决定 | 算法批准 production profile；输出 `capped` 与 `usability_undecided` | 算法负责人 | 是 |
| S07-G10 | wwPDB FASTA 含 B/O/U/X/Z；BLAST DB 需 taxdb 与正确 `BLASTDB` 才能完成元数据校验 | 输入字母、非标准残基和运行依赖未建模 | 冻结序列字符策略、DB/taxdb 版本清单、启动自检和失败码 | 开发 + 运维 | 是 |
| S07-G11 | AFDB 的 CIF/JSON 实际 Content-Type 均为 `application/octet-stream` | 不能仅凭 HTTP Content-Type 判定文件类型 | 按期望 artifact 类型做 magic/语法/维度/哈希校验，保留原始响应头 | 开发 | 是 |
| S07-G12 | 同一次活动中已观察 HTTP 0 连接故障、TLS revocation 故障、HTTP 204、HTTP 400 及 CLI 依赖故障 | “无命中”“无映射”“远端拒绝”“网络故障”必须分离 | 冻结 outcome/error 枚举、重试边界与可恢复性字段 | 开发评审 | 是 |
| S07-G13 | RCSB/AFDB/wwPDB 内容会更新；当前证据已有请求时间、来源 Last-Modified、版本和 SHA-256 | 线上重复调用不天然可复现 | 设计缓存/快照、source version、retrieved_at、request/profile hash 与过期策略 | 开发 + 运维 | 是 |
| S07-G14 | alternate location、assembly 选择、非标准残基与多 model 尚未形成代表性实测映射 | 当前 mapping 只覆盖本轮代表样本 | P0-M2 故障/边界测试中补 parser fixture；不擅自设科学选择规则 | 开发；科学规则待算法 | 否（需列入 M2 验收） |

## 本轮不能得出的结论

- 不能宣布 P0-DISC-005 已科学证明“无可用同源结构”；只能确认无 exact-target 证据，弱命中是否可用尚未决定。
- 不能因为 RCSB/AFDB 返回候选就自动路由“已有结构”。
- 不能把本轮 BLAST `evalue=10`、`max_target_seqs=100` 或 RCSB 查询 identity 参数升级为生产阈值。
- 不能把 AFDB `globalMetricValue` 直接映射为 S-09 high/medium/low。

## 建议的契约评审输入

下一步应基于 `candidate_structure_manifest.json` 与 `sequence_mapping_report.json` 逐字段评审：

1. 输入事实源与可选检索提示；
2. 检索 outcome 与标准 ToolError 的边界；
3. 候选/实体/链/model/assembly/ArtifactRef 层级；
4. 原始 sequence alignment 与 coordinate mapping；
5. 三类暂定命中语义及保守路由；
6. 分页、去重、排序、快照和证据版本。
"""
    (reports_dir / "capability_gap_table.md").write_text(gap_table, encoding="utf-8")

    summary = f"""# P0-M1：S-07 真实输出发现实验总结

状态：`EVIDENCE_CAPTURE_COMPLETE / CONTRACT_REVIEW_REQUIRED`  
Campaign：`{CAMPAIGN_ID}`  
部署状态：`{DEPLOYMENT_STATUS}`

## 完成范围

- 冻结 5 个公开 discovery case，并保留输入序列、来源、日期与哈希。
- 捕获 RCSB Search/Data/mmCIF、AlphaFold DB metadata/mmCIF/confidence/PAE 的原始交换。
- 固定 NCBI BLAST+ 2.17.0 与 2026-08-22 wwPDB protein FASTA，构建并全量校验 BLAST DB。
- 对 4 个输入保存 BLAST archive、tabular 与 JSON 输出。
- 形成 {len(candidates)} 个代表候选的 manifest 与逐候选序列—坐标映射。
- 保留成功、HTTP 204、HTTP 400、连接/TLS 故障与 CLI 依赖故障等不同输出形态。

## 关键发现

1. “序列完全一致”与“目标坐标完整”是两个字段：6XRE 为 exact entity，但 chain M 坐标覆盖仅 314/393。
2. 目标片段必须显式映射：5XZC 对齐目标 92-356，实际有坐标的目标残基为 232/393。
3. 同源命中必须与目标命中分离：6PPV 对 O15116 为 62.5% 局部 identity，坐标映射 69/133。
4. AlphaFold DB 的 O15116 v6 模型与输入 133 aa 精确一致，但 API 不能直接接受 RefSeq accession。
5. P0-DISC-005 只能报告“无 exact-target 证据且同源可用性未决”，不能在缺少阈值时宣称科学无结构。
6. HTTP 204 是成功空结果；HTTP 400/HTTP 0/CLI 非零退出应进入不同 outcome/error 分支。

## 退出产物

- `candidate_structure_manifest.json`
- `sequence_mapping_report.json`
- `capability_gap_table.md`
- `blast_dependency_and_results_manifest.json`
- `evidence_inventory.json`

## 停止线与下一步

P0-M1 的原始取证目标已经完成，但 S-07 契约尚未批准。下一步是 **S-07 契约评审**，不是直接开始
P0-M2 编码。只有命中语义、科学阈值/路由、chain/assembly 选择、AFDB accession 映射以及
outcome/error 枚举得到相应负责人确认后，才能实现生产检索适配器。

本报告及全部候选均为 discovery evidence；未接入 MCP/Dify，不用于科研结论或生产候选选择。
"""
    (reports_dir / "P0_M1_SUMMARY.md").write_text(summary, encoding="utf-8")

    print(
        json.dumps(
            {
                "campaign_id": CAMPAIGN_ID,
                "candidate_count": len(candidates),
                "mapping_count": len(mappings),
                "blast_case_count": len(blast_cases),
                "exchange_count": len(exchange_records),
                "evidence_file_count": len(inventory_files),
                "reports": sorted(path.name for path in reports_dir.iterdir()),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def main() -> int:
    args = parse_args()
    build_reports(args.campaign_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
