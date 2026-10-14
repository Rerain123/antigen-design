"""Build S-07 task 4 reports from frozen public API responses.

The script performs no network access and makes no production selection.  It
checks the evidence captured from EMBL-EBI NCBI BLAST, UniProt REST, and the
AlphaFold DB API, then records which observations are settled and which still
need a scientific rule.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any


CAMPAIGN_ID = "p0-s07-task4-uniprot-afdb-20260902-a"
BLAST_PROFILE = {
    "service": "EMBL-EBI Job Dispatcher NCBI BLAST REST API",
    "program": "blastp",
    "database": "uniprotkb_swissprot",
    "matrix": "BLOSUM62",
    "max_alignments": 100,
    "max_scores": 100,
    "expect": 10,
    "filter": "F",
    "meaning": "discovery output profile only; not a scientific acceptance rule",
}


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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_fasta(path: Path) -> str:
    return "".join(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith(">")
    ).upper()


def parse_headers(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    status_matches = re.findall(r"^HTTP/\S+\s+(\d{3})\s*(.*)$", text, re.MULTILINE)
    if not status_matches:
        raise ValueError(f"No HTTP status found in {path}")
    headers: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line or line.upper().startswith("HTTP/"):
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    code, phrase = status_matches[-1]
    return {"status_code": int(code), "reason": phrase.strip(), "headers": headers}


def normalize_models(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and payload:
        return [payload]
    return []


def parse_afdb(campaign: Path, accession: str) -> dict[str, Any]:
    directory = campaign / "evidence" / "afdb" / accession
    response = parse_headers(directory / "response.headers.txt")
    payload = read_json(directory / "response.json")
    models = normalize_models(payload)
    return {
        "accession": accession,
        "http_status": response["status_code"],
        "response_headers": {
            key: response["headers"].get(key)
            for key in ("content-type", "date", "content-length")
        },
        "error": payload.get("error") if isinstance(payload, dict) else None,
        "models": [
            {
                "entry_id": model.get("entryId") or model.get("modelEntityId"),
                "uniprot_accession": model.get("uniprotAccession"),
                "sequence": model.get("sequence") or model.get("uniprotSequence"),
                "sequence_length": len(
                    model.get("sequence") or model.get("uniprotSequence") or ""
                ),
                "sequence_checksum": model.get("sequenceChecksum"),
                "latest_version": model.get("latestVersion"),
                "global_metric_value": model.get("globalMetricValue"),
                "organism": model.get("organismScientificName"),
                "reviewed": model.get("isReviewed", model.get("isUniProtReviewed")),
                "reference_proteome": model.get(
                    "isReferenceProteome", model.get("isUniProtReferenceProteome")
                ),
                "cif_url": model.get("cifUrl"),
                "confidence_url": model.get("plddtDocUrl"),
                "pae_url": model.get("paeDocUrl"),
            }
            for model in models
        ],
    }


def parse_uniprot(campaign: Path, accession: str) -> dict[str, Any]:
    directory = campaign / "evidence" / "uniprot-api" / accession
    response = parse_headers(directory / "entry-json.headers.txt")
    payload = read_json(directory / "entry.json")
    sequence = payload.get("sequence", {})
    audit = payload.get("entryAudit", {})
    organism = payload.get("organism", {})
    return {
        "accession": payload.get("primaryAccession", accession),
        "http_status": response["status_code"],
        "entry_type": payload.get("entryType"),
        "uniprot_id": payload.get("uniProtkbId"),
        "organism": organism.get("scientificName"),
        "taxon_id": organism.get("taxonId"),
        "sequence": sequence.get("value", ""),
        "sequence_length": sequence.get("length"),
        "sequence_md5": sequence.get("md5"),
        "sequence_version": audit.get("sequenceVersion"),
        "last_sequence_update": audit.get("lastSequenceUpdateDate"),
        "api_release": response["headers"].get("x-uniprot-release"),
        "api_release_date": response["headers"].get("x-uniprot-release-date"),
        "api_deployment_date": response["headers"].get("x-api-deployment-date"),
    }


def parse_blast(campaign: Path, case_name: str) -> dict[str, Any]:
    directory = campaign / "evidence" / "blast-api" / "ebi" / case_name
    payload = read_json(directory / "result-json")
    hits: list[dict[str, Any]] = []
    for hit in payload.get("hits", []):
        hsps = hit.get("hit_hsps") or []
        if not hsps:
            continue
        hsp = hsps[0]
        query_coverage = (
            hsp["hsp_query_to"] - hsp["hsp_query_from"] + 1
        ) / payload["query_len"]
        target_coverage = (
            hsp["hsp_hit_to"] - hsp["hsp_hit_from"] + 1
        ) / hit["hit_len"]
        exact_query = (
            float(hsp["hsp_identity"]) == 100.0
            and hsp["hsp_query_from"] == 1
            and hsp["hsp_query_to"] == payload["query_len"]
            and hsp["hsp_qseq"].replace("-", "")
            == hsp["hsp_hseq"].replace("-", "")
        )
        exact_full_length = (
            exact_query
            and hit["hit_len"] == payload["query_len"]
            and hsp["hsp_hit_from"] == 1
            and hsp["hsp_hit_to"] == hit["hit_len"]
        )
        hits.append(
            {
                "rank": hit["hit_num"],
                "accession": hit["hit_acc"],
                "organism": hit.get("hit_os"),
                "target_length": hit["hit_len"],
                "identity_pct": float(hsp["hsp_identity"]),
                "query_coverage": query_coverage,
                "target_coverage": target_coverage,
                "evalue": float(hsp["hsp_expect"]),
                "bit_score": float(hsp["hsp_bit_score"]),
                "query_start": hsp["hsp_query_from"],
                "query_end": hsp["hsp_query_to"],
                "target_start": hsp["hsp_hit_from"],
                "target_end": hsp["hsp_hit_to"],
                "exact_query_sequence": exact_query,
                "exact_full_length_sequence": exact_full_length,
            }
        )
    database = payload.get("dbs", [{}])[0]
    return {
        "case": case_name,
        "job_id": (directory / "job-id.txt").read_text(encoding="utf-8").strip(),
        "terminal_status": next(
            (
                path.read_text(encoding="utf-8").strip()
                for path in sorted(directory.glob("status-*.txt"), reverse=True)
                if path.read_text(encoding="utf-8").strip() == "FINISHED"
            ),
            None,
        ),
        "program": payload.get("program"),
        "tool_version": payload.get("version"),
        "database": database.get("name"),
        "database_created": database.get("created"),
        "database_sequence_count": payload.get("db_num"),
        "database_residue_count": payload.get("db_len"),
        "query_length": payload.get("query_len"),
        "started_at": payload.get("start"),
        "ended_at": payload.get("end"),
        "reported_hit_count": len(hits),
        "hits": hits,
    }


def parse_afdb_cif_sequence(path: Path) -> str:
    try:
        from Bio.PDB.MMCIF2Dict import MMCIF2Dict
    except ImportError as exc:  # pragma: no cover - discovery dependency
        raise SystemExit("Biopython is required to parse the frozen AFDB mmCIF") from exc
    document = MMCIF2Dict(str(path))
    raw = document.get("_entity_poly.pdbx_seq_one_letter_code_can")
    if isinstance(raw, list):
        raw = raw[0]
    if raw is None:
        raise ValueError("AFDB mmCIF lacks canonical entity sequence")
    return re.sub(r"\s+", "", str(raw)).upper()


def mismatch_positions(left: str, right: str) -> list[dict[str, Any]]:
    mismatches = [
        {"position": index, "input": a, "reference": b}
        for index, (a, b) in enumerate(zip(left, right, strict=False), start=1)
        if a != b
    ]
    if len(left) != len(right):
        mismatches.append(
            {"position": None, "input_length": len(left), "reference_length": len(right)}
        )
    return mismatches


def write_case_tsv(path: Path, cases: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("case_id", "scenario", "evidence_status", "routing_fact", "rule_status"),
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(cases)


def build_report(root: Path) -> dict[str, Any]:
    campaign = root / "discovery" / "p0" / "s07" / CAMPAIGN_ID
    reports = campaign / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    inputs = {
        name: read_fasta(campaign / "inputs" / filename)
        for name, filename in {
            "O15116": "O15116.fasta",
            "O15116_one_substitution": "O15116-one-substitution.fasta",
            "synthetic_no_record": "synthetic-no-exact-record.fasta",
            "ubiquitin": "ubiquitin-1UBQ.fasta",
            "C0HLM8": "C0HLM8.fasta",
            "P80438": "P80438.fasta",
            "Q86UQ4": "Q86UQ4.fasta",
        }.items()
    }
    blast = {
        name: parse_blast(campaign, name)
        for name in (
            "O15116",
            "O15116-one-substitution",
            "synthetic-no-exact-record",
            "ubiquitin-1UBQ",
        )
    }
    uniprot = {
        accession: parse_uniprot(campaign, accession)
        for accession in (
            "O15116",
            "C0HLM8",
            "P80438",
            "Q86UQ4",
            "P62975",
            "P68197",
            "Q865C5",
        )
    }
    afdb = {
        accession: parse_afdb(campaign, accession)
        for accession in (
            "O15116",
            "C0HLM8",
            "P80438",
            "Q86UQ4",
            "P62975",
            "P68197",
            "Q865C5",
            "NP_055277.1",
        )
    }

    exact_top = blast["O15116"]["hits"][0]
    near_top = blast["O15116-one-substitution"]["hits"][0]
    no_record_hits = blast["synthetic-no-exact-record"]["hits"]
    ubiquitin_hits = blast["ubiquitin-1UBQ"]["hits"]
    ubiquitin_exact_full = [
        hit for hit in ubiquitin_hits if hit["exact_full_length_sequence"]
    ]

    o15116_models = afdb["O15116"]["models"]
    if len(o15116_models) != 1:
        raise ValueError("Expected exactly one frozen O15116 AFDB model")
    o15116_model = o15116_models[0]
    cif_sequence = parse_afdb_cif_sequence(
        campaign / "evidence" / "afdb" / "O15116" / "model.cif"
    )
    confidence = read_json(
        campaign / "evidence" / "afdb" / "O15116" / "confidence.json"
    )
    pae_payload = read_json(campaign / "evidence" / "afdb" / "O15116" / "pae.json")
    pae = pae_payload[0]
    confidence_scores = confidence["confidenceScore"]
    residue_numbers = confidence["residueNumber"]
    pae_matrix = pae["predicted_aligned_error"]

    direct_exact = (
        inputs["O15116"]
        == uniprot["O15116"]["sequence"]
        == o15116_model["sequence"]
        == cif_sequence
    )
    blast_chain_exact = (
        exact_top["accession"] == "O15116"
        and exact_top["exact_full_length_sequence"]
        and direct_exact
    )
    no_model_observations = {
        accession: {
            "uniprot_http_status": uniprot[accession]["http_status"],
            "uniprot_sequence_length": uniprot[accession]["sequence_length"],
            "afdb_http_status": afdb[accession]["http_status"],
            "afdb_model_count": len(afdb[accession]["models"]),
        }
        for accession in ("C0HLM8", "P80438")
    }
    near_mismatches = mismatch_positions(
        inputs["O15116_one_substitution"], uniprot["O15116"]["sequence"]
    )
    ubiquitin_accessions = [hit["accession"] for hit in ubiquitin_exact_full]
    ubiquitin_afdb = {
        accession: {
            "http_status": afdb[accession]["http_status"],
            "sequence_exact": bool(afdb[accession]["models"])
            and afdb[accession]["models"][0]["sequence"] == inputs["ubiquitin"],
            "global_metric_value": afdb[accession]["models"][0][
                "global_metric_value"
            ],
            "organism": afdb[accession]["models"][0]["organism"],
        }
        for accession in ubiquitin_accessions
    }
    q86_models = afdb["Q86UQ4"]["models"]
    q86_exact_models = [
        model for model in q86_models if model["sequence"] == inputs["Q86UQ4"]
    ]

    checks = [
        {
            "check_id": "T4-C01",
            "name": "direct accession resolves to an exact AFDB model",
            "passed": afdb["O15116"]["http_status"] == 200 and direct_exact,
        },
        {
            "check_id": "T4-C02",
            "name": "BLAST accession can be rechecked through UniProt and AFDB APIs",
            "passed": blast_chain_exact,
        },
        {
            "check_id": "T4-C03",
            "name": "normal BLAST no-hit remains distinct from API failure",
            "passed": blast["synthetic-no-exact-record"]["terminal_status"]
            == "FINISHED"
            and not no_record_hits,
        },
        {
            "check_id": "T4-C04",
            "name": "valid UniProt accession without AFDB model is observed as 404",
            "passed": all(
                item["uniprot_http_status"] == 200
                and item["afdb_http_status"] == 404
                and item["afdb_model_count"] == 0
                for item in no_model_observations.values()
            ),
        },
        {
            "check_id": "T4-C05",
            "name": "unsupported identifier is distinct from no model",
            "passed": afdb["NP_055277.1"]["http_status"] == 400
            and bool(afdb["NP_055277.1"]["error"]),
        },
        {
            "check_id": "T4-C06",
            "name": "near BLAST hit does not hide target/reference sequence mismatch",
            "passed": near_top["accession"] == "O15116"
            and near_top["identity_pct"] < 100.0
            and len(near_mismatches) == 1,
        },
        {
            "check_id": "T4-C07",
            "name": "multiple exact full-length accessions are retained",
            "passed": ubiquitin_accessions == ["P62975", "P68197", "Q865C5"]
            and all(item["sequence_exact"] for item in ubiquitin_afdb.values()),
        },
        {
            "check_id": "T4-C08",
            "name": "base accession response is checked at model/isoform sequence level",
            "passed": afdb["Q86UQ4"]["http_status"] == 200
            and len(q86_models) == 4
            and not q86_exact_models,
        },
        {
            "check_id": "T4-C09",
            "name": "AFDB structure, residue confidence, and PAE are internally sized",
            "passed": len(cif_sequence)
            == len(residue_numbers)
            == len(confidence_scores)
            == 133
            and len(pae_matrix) == 133
            and all(len(row) == 133 for row in pae_matrix),
        },
    ]

    cases = [
        {
            "case_id": "T4-A01",
            "scenario": "existing_valid_accession",
            "evidence_status": "PASS",
            "routing_fact": "AFDB model found; continue to S-09",
            "rule_status": "EXPERT_RULE_CLEAR",
        },
        {
            "case_id": "T4-A02",
            "scenario": "blast_finds_exact_uniprot_accession",
            "evidence_status": "PASS",
            "routing_fact": "UniProt and AFDB sequence/model round-trip succeeds",
            "rule_status": "EXPERT_RULE_CLEAR",
        },
        {
            "case_id": "T4-A03",
            "scenario": "blast_returns_no_hit",
            "evidence_status": "PASS",
            "routing_fact": "normal empty result; S-07 may return null after required sources complete",
            "rule_status": "EXPERT_RULE_CLEAR",
        },
        {
            "case_id": "T4-A04",
            "scenario": "valid_uniprot_accession_without_afdb_model",
            "evidence_status": "PASS",
            "routing_fact": "normal AFDB no-model result; continue fallback to S-08",
            "rule_status": "EXPERT_RULE_CLEAR",
        },
        {
            "case_id": "T4-A05",
            "scenario": "unsupported_identifier",
            "evidence_status": "PASS",
            "routing_fact": "invalid identifier error; must not be labelled no model",
            "rule_status": "ENGINEERING_ERROR_CLASSIFICATION_CLEAR",
        },
        {
            "case_id": "T4-A06",
            "scenario": "near_hit_sequence_mismatch",
            "evidence_status": "OBSERVED",
            "routing_fact": "candidate retained with explicit mismatch; no automatic scientific eligibility decision",
            "rule_status": "EXPERT_CONFIRMATION_REQUIRED",
        },
        {
            "case_id": "T4-A07",
            "scenario": "multiple_exact_full_length_accessions",
            "evidence_status": "OBSERVED",
            "routing_fact": "all exact candidates retained; no array-order selection",
            "rule_status": "EXPERT_CONFIRMATION_REQUIRED",
        },
        {
            "case_id": "T4-A08",
            "scenario": "base_accession_returns_nonmatching_isoforms",
            "evidence_status": "PASS",
            "routing_fact": "no matching model selected from four returned isoforms",
            "rule_status": "SEQUENCE_RECHECK_CLEAR; FINAL_ELIGIBILITY_DEPENDS_ON_T4-Q01",
        },
    ]
    write_case_tsv(reports / "api_case_matrix.tsv", cases)

    rule_gaps = [
        {
            "issue_id": "S07-T4-Q01",
            "question": "Which identity/coverage rule makes a BLAST-derived UniProt accession eligible for AFDB fallback?",
            "source_gap": "S-07 specifies BLAST versus UniProt but gives no fallback threshold; the explicit >95%/>90% rule is written for C3/PDB search.",
            "evidence": {
                "exact_case": {
                    "accession": exact_top["accession"],
                    "identity_pct": exact_top["identity_pct"],
                    "query_coverage": exact_top["query_coverage"],
                },
                "one_substitution_case": {
                    "accession": near_top["accession"],
                    "identity_pct": near_top["identity_pct"],
                    "query_coverage": near_top["query_coverage"],
                    "mismatches": near_mismatches,
                },
            },
            "impact": "Changes whether an existing AFDB model is used or S-08 predicts a new structure.",
            "recommended_interim_boundary": "Automatically accept only an exact full-length sequence match. Preserve non-exact candidates and R-58 mapping facts, but do not auto-select them until the expert sets the eligibility profile.",
            "status": "PENDING_EXPERT_CONFIRMATION",
        },
        {
            "issue_id": "S07-T4-Q02",
            "question": "How should multiple eligible accessions/models be selected, and how should organism_name participate?",
            "source_gap": "S-07 accepts organism_name but supplies no ranking or tie-break rule for multiple UniProt/AFDB records.",
            "evidence": {
                "exact_full_length_accessions": ubiquitin_accessions,
                "models": ubiquitin_afdb,
            },
            "impact": "Different accessions can have different provenance and AFDB confidence values even when their protein sequences are identical.",
            "recommended_interim_boundary": "Apply sequence eligibility first and exact organism match second. If more than one model remains, return an ambiguity result and do not select by API order, accession text, or an unapproved quality tie-break.",
            "status": "PENDING_EXPERT_CONFIRMATION",
        },
        {
            "issue_id": "S07-T4-Q03",
            "question": "Should the BLAST API search UniProtKB/Swiss-Prot only or all UniProtKB?",
            "source_gap": "The expert text says 'BLAST vs UniProt' without fixing Swiss-Prot versus Swiss-Prot plus TrEMBL.",
            "evidence": {
                "api_supported_databases": [
                    "uniprotkb_swissprot",
                    "uniprotkb_swissprotsv",
                    "uniprotkb_trembl",
                    "uniprotkb",
                    "afdb",
                ],
                "discovery_profile_used": "uniprotkb_swissprot",
            },
            "impact": "Changes coverage, reviewed status, result volume, and the chance that an accession has an AFDB model.",
            "recommended_interim_boundary": "Keep the P0 evidence profile on reviewed Swiss-Prot and expose the database as a versioned execution-profile field. Do not claim all-UniProt coverage until the expert confirms it.",
            "status": "PENDING_EXPERT_CONFIRMATION",
        },
    ]

    report = {
        "schema_version": "1.0",
        "campaign_id": CAMPAIGN_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "S-07 task 4 public API evidence",
        "execution_mode": "api_discovery",
        "overall_status": (
            "EVIDENCE_COMPLETE_RULE_CONFIRMATION_PENDING"
            if all(check["passed"] for check in checks)
            else "EVIDENCE_CHECK_FAILED"
        ),
        "production_deployment_status": "NOT_DEPLOYED",
        "scientific_acceptance": "NOT_RUN",
        "deployment_boundary": {
            "current_p0": "public APIs plus small frozen evidence files",
            "target_server": "local mirrors/caches are a later deployment option owned and validated by the receiving deployment team",
            "workstation_bulk_database": "not required for task 4",
        },
        "blast_profile": BLAST_PROFILE,
        "api_versions": {
            "blast": {
                "tool_version": blast["O15116"]["tool_version"],
                "database": blast["O15116"]["database"],
                "database_created": blast["O15116"]["database_created"],
                "database_sequence_count": blast["O15116"][
                    "database_sequence_count"
                ],
                "database_residue_count": blast["O15116"][
                    "database_residue_count"
                ],
            },
            "uniprot": {
                "release": uniprot["O15116"]["api_release"],
                "release_date": uniprot["O15116"]["api_release_date"],
                "api_deployment_date": uniprot["O15116"]["api_deployment_date"],
            },
            "afdb": {
                "model_version": o15116_model["latest_version"],
                "model_id": o15116_model["entry_id"],
            },
        },
        "checks": checks,
        "acceptance_cases": cases,
        "observations": {
            "direct_accession": {
                "accession": "O15116",
                "all_sequences_exact": direct_exact,
                "model_id": o15116_model["entry_id"],
                "model_version": o15116_model["latest_version"],
                "metadata_global_metric": o15116_model["global_metric_value"],
                "derived_mean_confidence": fmean(confidence_scores),
                "confidence_residue_count": len(confidence_scores),
                "pae_shape": [len(pae_matrix), len(pae_matrix[0])],
                "max_predicted_aligned_error": pae[
                    "max_predicted_aligned_error"
                ],
            },
            "blast_exact_round_trip": {
                "top_hit": exact_top,
                "uniprot_sequence_exact": uniprot["O15116"]["sequence"]
                == inputs["O15116"],
                "afdb_sequence_exact": o15116_model["sequence"] == inputs["O15116"],
            },
            "blast_no_hit": {
                "terminal_status": blast["synthetic-no-exact-record"][
                    "terminal_status"
                ],
                "reported_hit_count": len(no_record_hits),
            },
            "valid_accession_no_model": no_model_observations,
            "unsupported_identifier": {
                "accession": "NP_055277.1",
                "afdb_http_status": afdb["NP_055277.1"]["http_status"],
                "error": afdb["NP_055277.1"]["error"],
            },
            "near_hit_sequence_mismatch": {
                "top_hit": near_top,
                "mismatches": near_mismatches,
            },
            "one_to_many": {
                "exact_full_length_count": len(ubiquitin_exact_full),
                "exact_full_length_accessions": ubiquitin_accessions,
                "models": ubiquitin_afdb,
            },
            "base_accession_multiple_models": {
                "accession": "Q86UQ4",
                "input_length": len(inputs["Q86UQ4"]),
                "returned_model_count": len(q86_models),
                "returned_models": [
                    {
                        "entry_id": model["entry_id"],
                        "accession": model["uniprot_accession"],
                        "sequence_length": model["sequence_length"],
                    }
                    for model in q86_models
                ],
                "exact_model_count": len(q86_exact_models),
            },
        },
        "rule_gaps": rule_gaps,
        "excluded_work": [
            "The earlier workstation Swiss-Prot bulk/index experiment is not part of the API acceptance path.",
            "No AFDB bulk coordinate archive was downloaded.",
            "No target-server deployment or production adapter was performed.",
        ],
    }

    json_path = reports / "task4_api_evidence.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    evidence_paths: list[Path] = []
    for pattern in (
        "inputs/O15116.fasta",
        "inputs/O15116-one-substitution.fasta",
        "inputs/synthetic-no-exact-record.fasta",
        "inputs/ubiquitin-1UBQ.fasta",
        "inputs/C0HLM8.fasta",
        "inputs/P80438.fasta",
        "inputs/Q86UQ4.fasta",
        "evidence/blast-api/ebi/**/*",
        "evidence/uniprot-api/**/*",
        "evidence/afdb/O15116/*",
        "evidence/afdb/C0HLM8/*",
        "evidence/afdb/P80438/*",
        "evidence/afdb/Q86UQ4/*",
        "evidence/afdb/P62975/*",
        "evidence/afdb/P68197/*",
        "evidence/afdb/Q865C5/*",
        "evidence/afdb/NP_055277.1/*",
        "evidence/afdb/README.txt",
        "evidence/afdb/README.txt.headers.txt",
    ):
        evidence_paths.extend(path for path in campaign.glob(pattern) if path.is_file())
    evidence_paths.extend((json_path, reports / "api_case_matrix.tsv"))
    unique_paths = sorted(set(evidence_paths))
    manifest = {
        "schema_version": "1.0",
        "campaign_id": CAMPAIGN_ID,
        "scope": "task 4 API-path evidence only",
        "artifact_count": len(unique_paths),
        "total_size_bytes": sum(path.stat().st_size for path in unique_paths),
        "artifacts": [file_ref(path, root) for path in unique_paths],
        "explicit_exclusions": [
            "campaign logs/results from the superseded local Swiss-Prot exploration",
            "AFDB bulk directory listings used only for capacity reconnaissance",
            "transient service submission records containing session/client metadata",
        ],
    }
    (reports / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = build_report(root)
    print(
        json.dumps(
            {
                "campaign_id": report["campaign_id"],
                "overall_status": report["overall_status"],
                "checks_passed": sum(
                    check["passed"] for check in report["checks"]
                ),
                "checks_total": len(report["checks"]),
                "rule_gaps": [item["issue_id"] for item in report["rule_gaps"]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
