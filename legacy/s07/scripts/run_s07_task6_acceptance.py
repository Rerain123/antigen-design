"""Run the non-production S-07 task 6 acceptance campaign.

The campaign combines a fresh search against the frozen wwPDB/MMseqs2 release,
fresh read-only calls to the official RCSB, UniProt and AlphaFold DB APIs, and
read-only validation of the task 5 error/recovery and handoff fixtures.  It is
an acceptance harness, not an MCP/Dify adapter or a production deployment.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from s07_task5_contract import S07Result
from t01_s07_acceptance.backend import (
    CLASSIFICATION,
    DEPLOYMENT_STATUS,
    EXPERT_CONFIRMATION_IDS,
    MAX_RESULTS_PER_QUERY,
    RULE_STATUS,
    file_reference,
    parse_mmcif_sequence_and_coordinates,
    read_entries_index,
    read_fasta,
    read_json,
    read_mmseqs,
    rcsb_strict_matches,
    select_experimental_candidate,
    sha256_bytes,
    sha256_file,
    strict_candidate_passes,
    summarize_queries,
    write_json,
)


CAMPAIGN_ID = "p0-s07-task6-acceptance-20260903-c"
CAMPAIGN_REL = Path("discovery/p0/s07") / CAMPAIGN_ID
RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_GRAPHQL_URL = "https://data.rcsb.org/graphql"
UNIPROT_ROOT = "https://rest.uniprot.org/uniprotkb"
AFDB_ROOT = "https://alphafold.ebi.ac.uk/api/prediction"
GRAPHQL_CHUNK_SIZE = 100
HTTP_TIMEOUT_SECONDS = 120
MMSEQS_FORMAT = (
    "query,target,pident,fident,nident,alnlen,mismatch,gapopen,qstart,qend,"
    "tstart,tend,evalue,bits,qcov,tcov,qlen,tlen,cigar"
)

TASK3_REL = Path("discovery/p0/s07/p0-s07-task3-mmseqs-20260902-a")
TASK4_REL = Path("discovery/p0/s07/p0-s07-task4-uniprot-afdb-20260902-a")
TASK5_REL = Path("discovery/p0/s07/p0-s07-task5-contract-20260903-b")
QUERY_SET_REL = TASK3_REL / "inputs/query-set.fasta"
ENTRIES_REL = Path("var/discovery-data/wwpdb-20260829/entries.idx")
MMSEQS_DB_REL = Path(
    "var/discovery-data/wwpdb-20260829/mmseqs2-18-8cc5c/pdb_seqres_protein"
)
MMSEQS_EXE_REL = Path(
    "var/discovery-tools/mmseqs2-18-8cc5c/extracted/mmseqs/bin/mmseqs.exe"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--campaign-id", default=CAMPAIGN_ID)
    parser.add_argument(
        "--finalize-existing",
        action="store_true",
        help="Finish a failed campaign when immutable acceptance outputs already passed.",
    )
    return parser.parse_args()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def immutable_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def copy_once(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, target.open("xb") as writer:
        shutil.copyfileobj(reader, writer)


def windows_peak_working_set(process: subprocess.Popen[Any]) -> int | None:
    if os.name != "nt":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    try:
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.c_void_p(int(process._handle))  # type: ignore[attr-defined]
        succeeded = ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        )
        return int(counters.PeakWorkingSetSize) if succeeded else None
    except (AttributeError, OSError, ValueError):
        return None


def run_measured(
    command: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path
) -> dict[str, Any]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    started = time.perf_counter()
    peak_working_set = 0
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr)
        while process.poll() is None:
            observed = windows_peak_working_set(process)
            if observed is not None:
                peak_working_set = max(peak_working_set, observed)
            time.sleep(0.02)
        exit_code = process.returncode
        observed = windows_peak_working_set(process)
        if observed is not None:
            peak_working_set = max(peak_working_set, observed)
    finished_at = utc_now()
    wall = time.perf_counter() - started
    return {
        "argv": command,
        "started_at": started_at,
        "finished_at": finished_at,
        "wall_time_seconds": round(wall, 6),
        "exit_code": exit_code,
        "peak_working_set_bytes": peak_working_set or None,
        "stdout": file_reference(stdout_path, cwd),
        "stderr": file_reference(stderr_path, cwd),
    }


def http_status(exchange: dict[str, Any]) -> int:
    raw = exchange.get("curl", {}).get("metrics", {}).get("http_code")
    if raw is None:
        raw = exchange.get("curl", {}).get("metrics", {}).get("response_code")
    if raw is None:
        raise ValueError("HTTP exchange has no status code")
    return int(raw)


def capture_http(
    *,
    workspace: Path,
    campaign_id: str,
    label: str,
    method: str,
    url: str,
    output_dir: Path,
    response_name: str,
    expected_statuses: set[int],
    body_file: Path | None = None,
    accept: str = "application/json",
) -> tuple[dict[str, Any], Path]:
    if output_dir.exists():
        raise ValueError(f"refusing to overwrite HTTP evidence: {output_dir}")
    command = [
        sys.executable,
        str(workspace / "scripts/capture_http_evidence.py"),
        "--exchange-id",
        f"{campaign_id}--{label}",
        "--method",
        method,
        "--url",
        url,
        "--output-dir",
        str(output_dir),
        "--response-name",
        response_name,
        "--accept",
        accept,
        "--timeout-seconds",
        str(HTTP_TIMEOUT_SECONDS),
    ]
    if os.name == "nt":
        command.append("--ssl-revoke-best-effort")
    if body_file is not None:
        command.extend(["--body-file", str(body_file)])
    completed = subprocess.run(
        command, cwd=workspace, capture_output=True, text=True, check=False
    )
    exchange_path = output_dir / "exchange.json"
    if not exchange_path.is_file():
        raise RuntimeError(
            f"HTTP capture failed before producing an exchange ({label}): "
            f"{completed.stderr[-1000:]}"
        )
    exchange = read_json(exchange_path)
    status = http_status(exchange)
    print(
        json.dumps(
            {
                "event": "http_capture",
                "label": label,
                "status": status,
                "seconds": exchange["curl"]["metrics"].get("time_total"),
                "bytes": exchange["response"]["body_size_bytes"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    if completed.returncode != 0 or status not in expected_statuses:
        raise RuntimeError(
            f"Unexpected HTTP result for {label}: process={completed.returncode}, status={status}"
        )
    return exchange, output_dir / response_name


def parse_response_headers(path: Path) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line or line.upper().startswith("HTTP/"):
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def create_rcsb_search_request(
    sequence: str, *, query_id: str
) -> dict[str, Any]:
    return {
        "query": {
            "type": "terminal",
            "service": "sequence",
            "parameters": {
                "evalue_cutoff": 1.0,
                "identity_cutoff": 0.95,
                "sequence_type": "protein",
                "value": sequence,
            },
        },
        "request_options": {
            "return_all_hits": True,
            "results_content_type": ["experimental"],
            "results_verbosity": "verbose",
            "scoring_strategy": "sequence",
        },
        "request_info": {"query_id": query_id},
        "return_type": "polymer_entity",
    }


GRAPHQL_QUERY = """query($ids:[String!]!){
  polymer_entities(entity_ids:$ids){
    rcsb_id
    rcsb_polymer_entity_container_identifiers{
      entry_id entity_id asym_ids auth_asym_ids
    }
    entity_poly{rcsb_sample_sequence_length pdbx_seq_one_letter_code_can}
    entry{
      rcsb_id
      exptl{method}
      rcsb_entry_info{
        experimental_method structure_determination_methodology resolution_combined
      }
      rcsb_accession_info{initial_release_date}
    }
  }
}"""


def normalize_graphql_candidates(
    records: list[dict[str, Any]], matches: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    match_by_id = {item["identifier"].upper(): item for item in matches}
    candidates: list[dict[str, Any]] = []
    review_metadata: list[str] = []
    incomplete_metadata: list[str] = []
    seen: set[str] = set()
    for record in records:
        identifier = str(record.get("rcsb_id", "")).upper()
        seen.add(identifier)
        container = record.get("rcsb_polymer_entity_container_identifiers") or {}
        entry = record.get("entry") or {}
        entry_info = entry.get("rcsb_entry_info") or {}
        primary_method = entry_info.get("experimental_method")
        methods = (
            [str(primary_method)]
            if primary_method
            else sorted(
                {
                    str(item.get("method"))
                    for item in entry.get("exptl") or []
                    if item.get("method")
                }
            )
        )
        resolutions = sorted(
            {
                float(value)
                for value in entry_info.get("resolution_combined")
                or []
                if isinstance(value, (int, float)) and value > 0
            }
        )
        metadata_notes: list[str] = []
        if not methods:
            metadata_notes.append("METHOD_EXPLICITLY_NULL")
        elif len(methods) > 1:
            metadata_notes.append("MULTIPLE_METHOD_VALUES")
        if len(resolutions) > 1:
            metadata_notes.append("MULTIPLE_RESOLUTION_VALUES")
        if metadata_notes:
            review_metadata.append(identifier)
        method = methods[0] if len(methods) == 1 else " / ".join(methods)
        resolution = resolutions[0] if len(resolutions) == 1 else None
        auth_chains = sorted(set(container.get("auth_asym_ids") or []))
        if not auth_chains:
            incomplete_metadata.append(identifier)
        for auth_chain in auth_chains:
            candidates.append(
                {
                    **match_by_id[identifier],
                    "entry_id": str(container.get("entry_id", "")).upper(),
                    "entity_id": str(container.get("entity_id", "")),
                    "chain_id": str(auth_chain),
                    "label_asym_ids": container.get("asym_ids") or [],
                    "method": method,
                    "method_group": (
                        "X_RAY"
                        if "X-RAY" in method.upper()
                        else "CRYO_EM"
                        if "ELECTRON MICROSCOPY" in method.upper()
                        else "NMR"
                        if "NMR" in method.upper()
                        else "OTHER"
                    ),
                    "resolution_angstrom": resolution,
                    "resolution_values": resolutions,
                    "initial_release_date": (
                        entry.get("rcsb_accession_info") or {}
                    ).get("initial_release_date"),
                    "structure_determination_methodology": entry_info.get(
                        "structure_determination_methodology"
                    ),
                    "canonical_sequence": re.sub(
                        r"\s+",
                        "",
                        str(
                            (record.get("entity_poly") or {}).get(
                                "pdbx_seq_one_letter_code_can", ""
                            )
                        ),
                    ).upper(),
                    "metadata_notes": metadata_notes,
                }
            )
    missing = sorted(set(match_by_id) - seen)
    incomplete_metadata.extend(missing)
    return (
        candidates,
        sorted(set(review_metadata)),
        sorted(set(incomplete_metadata)),
    )


def run_rcsb_case(
    *,
    workspace: Path,
    campaign: Path,
    campaign_id: str,
    case_id: str,
    sequence: str,
) -> dict[str, Any]:
    request = create_rcsb_search_request(
        sequence, query_id=f"{campaign_id}--{case_id}--rcsb"
    )
    request_path = campaign / "inputs/requests/rcsb" / f"{case_id}.json"
    immutable_write(request_path, json_bytes(request))
    exchange, response_path = capture_http(
        workspace=workspace,
        campaign_id=campaign_id,
        label=f"{case_id}-rcsb-search",
        method="POST",
        url=RCSB_SEARCH_URL,
        output_dir=campaign / "evidence/api/rcsb" / case_id / "search",
        response_name="response.json",
        expected_statuses={200, 204},
        body_file=request_path,
    )
    status = http_status(exchange)
    if status == 204:
        payload = {"query_id": request["request_info"]["query_id"], "total_count": 0, "result_set": []}
    else:
        payload = read_json(response_path)
    total = int(payload.get("total_count", 0))
    result_set = payload.get("result_set") or []
    if total != len(result_set):
        raise ValueError(
            f"RCSB return_all_hits count mismatch for {case_id}: {total} != {len(result_set)}"
        )
    matches = rcsb_strict_matches([payload])
    match_path = campaign / "results/api/rcsb" / f"{case_id}-strict-matches.json"
    immutable_write(match_path, json_bytes(matches))

    records: list[dict[str, Any]] = []
    graph_exchanges: list[dict[str, Any]] = []
    identifiers = [item["identifier"] for item in matches]
    for index, batch in enumerate(chunks(identifiers, GRAPHQL_CHUNK_SIZE), start=1):
        graph_body = {"query": GRAPHQL_QUERY, "variables": {"ids": batch}}
        graph_request = (
            campaign
            / "inputs/requests/rcsb-graphql"
            / case_id
            / f"chunk-{index:03d}.json"
        )
        immutable_write(graph_request, json_bytes(graph_body))
        graph_exchange, graph_response = capture_http(
            workspace=workspace,
            campaign_id=campaign_id,
            label=f"{case_id}-rcsb-graphql-{index:03d}",
            method="POST",
            url=RCSB_GRAPHQL_URL,
            output_dir=(
                campaign
                / "evidence/api/rcsb"
                / case_id
                / "metadata"
                / f"chunk-{index:03d}"
            ),
            response_name="response.json",
            expected_statuses={200},
            body_file=graph_request,
        )
        graph_payload = read_json(graph_response)
        if graph_payload.get("errors"):
            raise ValueError(
                f"RCSB GraphQL returned errors for {case_id} chunk {index}: "
                f"{graph_payload['errors']}"
            )
        records.extend((graph_payload.get("data") or {}).get("polymer_entities") or [])
        graph_exchanges.append(graph_exchange)

    candidates, review_metadata, incomplete_metadata = normalize_graphql_candidates(
        records, matches
    )
    selection = select_experimental_candidate(candidates)
    if incomplete_metadata:
        selection = {
            "status": "REVIEW_REQUIRED",
            "selected_entry_id": None,
            "selected_chain_id": None,
            "reason_codes": ["RCSB_METADATA_INCOMPLETE_OR_NONUNIQUE"],
            "unresolved_identifiers": incomplete_metadata,
        }
    candidate_path = campaign / "results/api/rcsb" / f"{case_id}-candidates.json"
    immutable_write(candidate_path, json_bytes(candidates))

    structure: dict[str, Any] | None = None
    if selection.get("status") == "SELECTED_PROVISIONAL":
        entry_id = selection["selected_entry_id"]
        chain_id = selection["selected_chain_id"]
        structure_exchange, cif_path = capture_http(
            workspace=workspace,
            campaign_id=campaign_id,
            label=f"{case_id}-rcsb-mmcif-{entry_id}",
            method="GET",
            url=f"https://files.rcsb.org/download/{entry_id}.cif",
            output_dir=(
                campaign / "evidence/api/rcsb" / case_id / "structure" / entry_id
            ),
            response_name=f"{entry_id}.cif",
            expected_statuses={200},
            accept="chemical/x-mmcif, text/plain;q=0.9, */*;q=0.1",
        )
        mapping = parse_mmcif_sequence_and_coordinates(cif_path, chain_id)
        selected_rows = [
            item
            for item in candidates
            if item["entry_id"] == entry_id and item["chain_id"] == chain_id
        ]
        metadata_sequences = sorted(
            {item["canonical_sequence"] for item in selected_rows if item["canonical_sequence"]}
        )
        if len(metadata_sequences) != 1 or mapping["sequence"] != metadata_sequences[0]:
            raise ValueError(
                f"RCSB Data API and mmCIF sequences disagree for {entry_id}/{chain_id}"
            )
        structure = {
            "exchange": file_reference(
                cif_path.parent / "exchange.json", workspace
            ),
            "artifact": file_reference(cif_path, workspace),
            "mapping": mapping,
            "metadata_sequence_sha256": sha256_bytes(
                metadata_sequences[0].encode("ascii")
            ),
            "input_sequence_exact": mapping["sequence"] == sequence,
            "http_seconds": structure_exchange["curl"]["metrics"].get("time_total"),
        }
    return {
        "case_id": case_id,
        "input_sequence_sha256": sha256_bytes(sequence.encode("ascii")),
        "input_length": len(sequence),
        "search_http_status": status,
        "return_all_hits": True,
        "reported_total_count": total,
        "returned_result_count": len(result_set),
        "strict_candidate_entity_count": len(matches),
        "metadata_entity_count": len(records),
        "metadata_collection_complete": len(records) == len(matches)
        and not incomplete_metadata,
        "metadata_review_identifiers": review_metadata,
        "metadata_incomplete_identifiers": incomplete_metadata,
        "candidate_chain_count": len(candidates),
        "selection": selection,
        "structure": structure,
        "search_exchange": file_reference(
            campaign / "evidence/api/rcsb" / case_id / "search/exchange.json",
            workspace,
        ),
        "strict_matches": file_reference(match_path, workspace),
        "candidate_manifest": file_reference(candidate_path, workspace),
        "graphql_request_count": len(graph_exchanges),
    }


def read_single_fasta(path: Path) -> str:
    records = read_fasta(path)
    if len(records) != 1:
        raise ValueError(f"Expected one FASTA record in {path}")
    return next(iter(records.values()))


def run_o15116_fallback(
    *, workspace: Path, campaign: Path, campaign_id: str, input_sequence: str
) -> dict[str, Any]:
    base = campaign / "evidence/api"
    uniprot_json_exchange, uniprot_json_path = capture_http(
        workspace=workspace,
        campaign_id=campaign_id,
        label="O15116-uniprot-json",
        method="GET",
        url=f"{UNIPROT_ROOT}/O15116.json",
        output_dir=base / "uniprot/O15116/entry-json",
        response_name="entry.json",
        expected_statuses={200},
    )
    uniprot_fasta_exchange, uniprot_fasta_path = capture_http(
        workspace=workspace,
        campaign_id=campaign_id,
        label="O15116-uniprot-fasta",
        method="GET",
        url=f"{UNIPROT_ROOT}/O15116.fasta",
        output_dir=base / "uniprot/O15116/entry-fasta",
        response_name="entry.fasta",
        expected_statuses={200},
        accept="text/plain",
    )
    uniprot = read_json(uniprot_json_path)
    uniprot_sequence = str((uniprot.get("sequence") or {}).get("value", "")).upper()
    fasta_sequence = read_single_fasta(uniprot_fasta_path)
    if not uniprot_sequence or uniprot_sequence != fasta_sequence:
        raise ValueError("UniProt JSON and FASTA sequences disagree for O15116")

    afdb_exchange, afdb_path = capture_http(
        workspace=workspace,
        campaign_id=campaign_id,
        label="O15116-afdb-metadata",
        method="GET",
        url=f"{AFDB_ROOT}/O15116",
        output_dir=base / "afdb/O15116/metadata",
        response_name="response.json",
        expected_statuses={200},
    )
    raw_models = read_json(afdb_path)
    models = raw_models if isinstance(raw_models, list) else [raw_models]
    exact_models = [
        model
        for model in models
        if str(model.get("uniprotAccession", "")).upper() == "O15116"
        and str(model.get("sequence") or model.get("uniprotSequence") or "").upper()
        == input_sequence
        and model.get("organismScientificName") == "Homo sapiens"
    ]
    if len(exact_models) != 1:
        return {
            "status": "REVIEW_REQUIRED",
            "reason_codes": ["EXACT_ORGANISM_MATCH_NOT_UNIQUE"],
            "model_count": len(models),
            "exact_model_count": len(exact_models),
        }
    model = exact_models[0]
    file_specs = {
        "model": (model["cifUrl"], "model.cif", "chemical/x-mmcif, text/plain;q=0.9"),
        "confidence": (model["plddtDocUrl"], "confidence.json", "application/json"),
        "pae": (model["paeDocUrl"], "pae.json", "application/json"),
    }
    files: dict[str, Any] = {}
    paths: dict[str, Path] = {}
    for kind, (url, name, accept) in file_specs.items():
        exchange, path = capture_http(
            workspace=workspace,
            campaign_id=campaign_id,
            label=f"O15116-afdb-{kind}",
            method="GET",
            url=url,
            output_dir=base / "afdb/O15116" / kind,
            response_name=name,
            expected_statuses={200},
            accept=accept,
        )
        files[kind] = {
            "artifact": file_reference(path, workspace),
            "exchange": file_reference(path.parent / "exchange.json", workspace),
            "http_seconds": exchange["curl"]["metrics"].get("time_total"),
        }
        paths[kind] = path

    mapping = parse_mmcif_sequence_and_coordinates(paths["model"], str(model["chainId"]))
    confidence = read_json(paths["confidence"])
    residue_numbers = confidence.get("residueNumber") or []
    confidence_scores = confidence.get("confidenceScore") or []
    pae_payload = read_json(paths["pae"])
    pae_record = pae_payload[0] if isinstance(pae_payload, list) else pae_payload
    pae = pae_record.get("predicted_aligned_error") or []
    sequence_checks = {
        "input_equals_uniprot_json": input_sequence == uniprot_sequence,
        "input_equals_uniprot_fasta": input_sequence == fasta_sequence,
        "input_equals_afdb_metadata": input_sequence
        == str(model.get("sequence") or model.get("uniprotSequence") or "").upper(),
        "input_equals_afdb_cif": input_sequence == mapping["sequence"],
    }
    dimensions_valid = (
        len(residue_numbers) == len(input_sequence)
        and len(confidence_scores) == len(input_sequence)
        and len(pae) == len(input_sequence)
        and all(len(row) == len(input_sequence) for row in pae)
    )
    if not all(sequence_checks.values()) or not dimensions_valid:
        raise ValueError("O15116 AFDB sequence or confidence dimensions failed validation")
    headers = parse_response_headers(
        (base / "uniprot/O15116/entry-json/response.headers.txt")
    )
    return {
        "status": "SELECTED_PROVISIONAL",
        "source": "alphafolddb",
        "accession": "O15116",
        "model_id": model.get("entryId") or model.get("modelEntityId"),
        "model_version": str(model.get("latestVersion")),
        "organism_name": model.get("organismScientificName"),
        "sequence_checks": sequence_checks,
        "confidence_dimensions_valid": dimensions_valid,
        "coordinate_mapping": mapping,
        "files": files,
        "uniprot_release": headers.get("x-uniprot-release"),
        "uniprot_release_date": headers.get("x-uniprot-release-date"),
        "afdb_global_metric": model.get("globalMetricValue"),
        "rule_status": RULE_STATUS,
        "expert_confirmation_ids": ["S07-EQ-03", "S07-EQ-04", "S07-EQ-05"],
        "api_exchanges": {
            "uniprot_json": file_reference(
                base / "uniprot/O15116/entry-json/exchange.json", workspace
            ),
            "uniprot_fasta": file_reference(
                base / "uniprot/O15116/entry-fasta/exchange.json", workspace
            ),
            "afdb_metadata": file_reference(
                base / "afdb/O15116/metadata/exchange.json", workspace
            ),
        },
        "api_seconds": {
            "uniprot_json": uniprot_json_exchange["curl"]["metrics"].get("time_total"),
            "uniprot_fasta": uniprot_fasta_exchange["curl"]["metrics"].get("time_total"),
            "afdb_metadata": afdb_exchange["curl"]["metrics"].get("time_total"),
        },
    }


def local_environment(workspace: Path) -> dict[str, Any]:
    total_memory: int | None = None
    available_memory: int | None = None
    if os.name == "nt":
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            total_memory = int(status.ullTotalPhys)
            available_memory = int(status.ullAvailPhys)
    disk = shutil.disk_usage(workspace)
    packages = {}
    for name in ("biopython", "pydantic", "pytest", "jsonschema"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "physical_memory_total_bytes": total_memory,
        "physical_memory_available_at_start_bytes": available_memory,
        "workspace_disk_total_bytes": disk.total,
        "workspace_disk_free_at_start_bytes": disk.free,
        "packages": packages,
    }


def tool_reported_peak_memory(log_path: Path) -> int | None:
    units = {"K": 1024, "M": 1024**2, "G": 1024**3}
    values = []
    for number, unit in re.findall(
        r"Estimated memory consumption:\s*([0-9.]+)([KMG])",
        log_path.read_text(encoding="utf-8", errors="replace"),
    ):
        values.append(int(float(number) * units[unit]))
    return max(values) if values else None


def build_local_acceptance(
    *, workspace: Path, campaign: Path
) -> tuple[dict[str, Any], dict[str, str]]:
    input_path = campaign / "inputs/query-set.fasta"
    copy_once(workspace / QUERY_SET_REL, input_path)
    query_records = read_fasta(input_path)
    output_path = campaign / "results/local/mmseqs-gate-floor.tsv"
    temp_path = campaign / "work/mmseqs"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(workspace / MMSEQS_EXE_REL),
        "easy-search",
        str(input_path),
        str(workspace / MMSEQS_DB_REL),
        str(output_path),
        str(temp_path),
        "--min-seq-id",
        "0.95",
        "-c",
        "0.90",
        "--cov-mode",
        "2",
        "-e",
        "1",
        "--max-seqs",
        str(MAX_RESULTS_PER_QUERY),
        "-s",
        "7.5",
        "--threads",
        "8",
        "--sort-results",
        "1",
        "--format-mode",
        "4",
        "--format-output",
        MMSEQS_FORMAT,
        "--remove-tmp-files",
        "1",
    ]
    run = run_measured(
        command,
        cwd=workspace,
        stdout_path=campaign / "logs/mmseqs.stdout.log",
        stderr_path=campaign / "logs/mmseqs.stderr.log",
    )
    if run["exit_code"] != 0 or not output_path.is_file():
        raise RuntimeError("fresh task 6 MMseqs2 acceptance run failed")
    print(json.dumps({"event": "mmseqs_complete", **run}, ensure_ascii=False), flush=True)

    floor_rows = read_mmseqs(output_path)
    strict_rows = [row for row in floor_rows if strict_candidate_passes(row)]
    strict_path = campaign / "results/local/mmseqs-strict-postfilter.tsv"
    header = MMSEQS_FORMAT.split(",")
    lines = ["\t".join(header)]
    for row in strict_rows:
        lines.append("\t".join(str(row[key]) for key in header))
    immutable_write(strict_path, ("\n".join(lines) + "\n").encode("utf-8"))

    entries = read_entries_index(workspace / ENTRIES_REL)
    summaries = summarize_queries(strict_rows, entries)
    for query_id, sequence in query_records.items():
        summaries.setdefault(
            query_id,
            {
                "query": query_id,
                "candidate_chain_count": 0,
                "candidate_entry_count": 0,
                "collection_complete": True,
                "observed_at_cap": False,
                "selection": select_experimental_candidate([]),
            },
        )
        summaries[query_id]["query_length"] = len(sequence)
        summaries[query_id]["query_sequence_sha256"] = sha256_bytes(
            sequence.encode("ascii")
        )

    structure_source = workspace / TASK3_REL / "evidence/wwpdb"
    mappings: dict[str, Any] = {}
    for entry_id, chain_id in (("6Q00", "A"), ("9R2Q", "K")):
        source = structure_source / entry_id / f"{entry_id}.cif"
        target = campaign / "evidence/frozen-wwpdb" / entry_id / f"{entry_id}.cif"
        copy_once(source, target)
        mappings[entry_id] = {
            "artifact": file_reference(target, workspace),
            "source": file_reference(source, workspace),
            "source_copy_sha256_equal": sha256_file(source) == sha256_file(target),
            "mapping": parse_mmcif_sequence_and_coordinates(target, chain_id),
        }

    main_log = campaign / "logs/mmseqs.stdout.log"
    stderr_log = campaign / "logs/mmseqs.stderr.log"
    reported_values = [
        value
        for value in (
            tool_reported_peak_memory(main_log),
            tool_reported_peak_memory(stderr_log),
        )
        if value is not None
    ]
    run["tool_reported_estimated_memory_bytes"] = (
        max(reported_values) if reported_values else None
    )
    task3_report_path = workspace / TASK3_REL / "reports/task3_evidence.json"
    task3_report = read_json(task3_report_path)
    frozen_index = next(
        item
        for item in task3_report["data_release"]["mmseqs_database_files"]
        if item["path"].endswith("pdb_seqres_protein.idx")
    )
    index_path = Path(str(workspace / MMSEQS_DB_REL) + ".idx")
    if index_path.stat().st_size != frozen_index["size_bytes"]:
        raise ValueError("MMseqs index size differs from the frozen task 3 manifest")
    return {
        "run": run,
        "input": file_reference(input_path, workspace),
        "database": {
            "release_id": "wwpdb-20260829-mmseqs2-18-8cc5c",
            "main": file_reference(workspace / MMSEQS_DB_REL, workspace),
            "index": {
                "path": index_path.relative_to(workspace).as_posix(),
                "size_bytes": index_path.stat().st_size,
                "sha256_from_frozen_manifest": frozen_index["sha256"],
                "task6_hash_recomputed": False,
                "verification_ref": file_reference(task3_report_path, workspace),
            },
            "entries": file_reference(workspace / ENTRIES_REL, workspace),
            "mmseqs_executable": file_reference(workspace / MMSEQS_EXE_REL, workspace),
        },
        "floor_candidate_count": len(floor_rows),
        "strict_candidate_count": len(strict_rows),
        "profile_max_results_per_query": MAX_RESULTS_PER_QUERY,
        "query_summaries": summaries,
        "structure_mappings": mappings,
        "output": file_reference(output_path, workspace),
        "strict_output": file_reference(strict_path, workspace),
    }, query_records


def validate_task5(workspace: Path) -> dict[str, Any]:
    task5 = workspace / TASK5_REL
    results = []
    for path in sorted((task5 / "results").glob("*/attempt-*.json")):
        result = S07Result.model_validate(read_json(path))
        results.append((path, result))
    if not results:
        raise ValueError("No task 5 results found")
    handoffs = {"S-08": [], "S-09": [], "BLOCKED": []}
    for path, result in results:
        if result.next_step == "S-09":
            selected = next(
                item
                for item in result.candidates
                if item.candidate_id == result.selected_candidate_id
            )
            if not selected.structure_artifact_id or selected.quality_assessment != "PENDING_S09":
                raise ValueError(f"Invalid S-09 handoff in {path}")
            handoffs["S-09"].append(path.relative_to(workspace).as_posix())
        elif result.next_step == "S-08":
            if result.selected_candidate_id is not None or result.retrieval_outcome != "NO_ELIGIBLE_EXISTING_STRUCTURE":
                raise ValueError(f"Invalid S-08 handoff in {path}")
            handoffs["S-08"].append(path.relative_to(workspace).as_posix())
        else:
            if result.status not in {"FAILED", "CANCELLED", "WAITING_USER"}:
                raise ValueError(f"Successful task 5 result lacks a handoff: {path}")
            handoffs["BLOCKED"].append(path.relative_to(workspace).as_posix())

    closeout_path = task5 / "reports/closeout_verification.json"
    closeout = read_json(closeout_path)
    if closeout.get("status") != "PASS":
        raise ValueError("Task 5 closeout is not PASS")
    task5_evidence_path = task5 / "reports/task5_contract_evidence.json"
    task5_evidence = read_json(task5_evidence_path)
    if task5_evidence.get("storage_check_count") != 7:
        raise ValueError("Task 5 storage/recovery check count changed")
    return {
        "validated_result_count": len(results),
        "handoffs": {key: {"count": len(value), "results": value} for key, value in handoffs.items()},
        "fault_and_recovery": {
            "status": "PASS",
            "storage_check_count": 7,
            "rejection_check_count": task5_evidence["rejection_check_count"],
            "route_case_count": task5_evidence["route_case_count"],
        },
        "source_refs": {
            "closeout": file_reference(closeout_path, workspace),
            "contract_evidence": file_reference(task5_evidence_path, workspace),
        },
        "consumer_status": {
            "S-08": "HANDOFF_SHAPE_VALIDATED_CONSUMER_NOT_DEPLOYED",
            "S-09": "HANDOFF_SHAPE_VALIDATED_CONSUMER_NOT_DEPLOYED",
        },
    }


def validate_task4_blast_cap(workspace: Path) -> dict[str, Any]:
    report_path = workspace / TASK4_REL / "reports/task4_api_evidence.json"
    report = read_json(report_path)
    profile = report["blast_profile"]
    blast_dir = workspace / TASK4_REL / "evidence/blast-api/ebi/O15116"
    payload_path = blast_dir / "result-json"
    payload = read_json(payload_path)
    hit_count = len(payload.get("hits") or [])
    if hit_count != int(profile["max_alignments"]):
        raise ValueError("The real positive BLAST cap observation changed")
    return {
        "status": "REVIEW_REQUIRED_INCOMPLETE_CANDIDATE_COLLECTION",
        "evidence_kind": "FROZEN_REPLAY",
        "reported_hit_count": hit_count,
        "configured_max_alignments": profile["max_alignments"],
        "configured_max_scores": profile["max_scores"],
        "candidate_collection_complete": False,
        "automatic_selection_allowed": False,
        "reason_code": "POSITIVE_BLAST_RESULT_OBSERVED_AT_CONFIGURED_CAP",
        "source_refs": {
            "report": file_reference(report_path, workspace),
            "raw_result": file_reference(payload_path, workspace),
            "submission_response_headers": file_reference(
                blast_dir / "submit.headers.txt", workspace
            ),
        },
    }


def build_checks(
    local: dict[str, Any], api: dict[str, Any], fallback: dict[str, Any], task5: dict[str, Any]
) -> list[dict[str, Any]]:
    summaries = local["query_summaries"]
    one_ubq = next(value for key, value in summaries.items() if "P0-DISC-001" in key)
    tp53 = next(value for key, value in summaries.items() if "P0-DISC-002" in key)
    o15116 = next(value for key, value in summaries.items() if "P0-DISC-004" in key)
    checks = [
        {
            "check_id": "T6-C01",
            "name": "fresh frozen-release candidate collection stays below the declared per-query cap",
            "passed": all(item["collection_complete"] for item in summaries.values()),
        },
        {
            "check_id": "T6-C02",
            "name": "1UBQ fixed-release selection is reproducible",
            "passed": one_ubq["selection"].get("selected_entry_id") == "6Q00"
            and one_ubq["selection"].get("selected_chain_id") == "A",
        },
        {
            "check_id": "T6-C03",
            "name": "TP53 four-chain ambiguity blocks automatic handoff",
            "passed": tp53["selection"].get("status") == "REVIEW_REQUIRED"
            and set(tp53["selection"].get("matching_chain_ids") or [])
            == {"K", "L", "M", "N"},
        },
        {
            "check_id": "T6-C04",
            "name": "fixed-release O15116 PDB search completes empty",
            "passed": o15116["candidate_chain_count"] == 0
            and o15116["collection_complete"],
        },
        {
            "check_id": "T6-C05",
            "name": "experimental full and partial coordinate mappings remain distinct",
            "passed": local["structure_mappings"]["6Q00"]["mapping"]["coordinate_complete"]
            and not local["structure_mappings"]["9R2Q"]["mapping"]["coordinate_complete"],
        },
        {
            "check_id": "T6-C06",
            "name": "live RCSB return_all_hits and metadata collection are complete",
            "passed": all(
                item["reported_total_count"] == item["returned_result_count"]
                and item["metadata_collection_complete"]
                for item in api.values()
            )
            and api["API-1UBQ"]["selection"].get("status")
            == "SELECTED_PROVISIONAL"
            and (api["API-1UBQ"].get("structure") or {}).get("input_sequence_exact")
            is True,
        },
        {
            "check_id": "T6-C07",
            "name": "live O15116 fallback is sequence-exact and ready for S-09 handoff",
            "passed": fallback.get("status") == "SELECTED_PROVISIONAL"
            and all((fallback.get("sequence_checks") or {}).values())
            and fallback.get("confidence_dimensions_valid") is True,
        },
        {
            "check_id": "T6-C08",
            "name": "task 5 failure, immutable replay and retry evidence remains valid",
            "passed": task5["fault_and_recovery"]["status"] == "PASS"
            and task5["fault_and_recovery"]["storage_check_count"] == 7,
        },
        {
            "check_id": "T6-C09",
            "name": "S-08 and S-09 handoff shapes validate while consumers remain undeployed",
            "passed": task5["handoffs"]["S-08"]["count"] > 0
            and task5["handoffs"]["S-09"]["count"] > 0,
        },
        {
            "check_id": "T6-C10",
            "name": "all five provisional rules stay attached and pending expert confirmation",
            "passed": EXPERT_CONFIRMATION_IDS
            == ["S07-EQ-01", "S07-EQ-02", "S07-EQ-03", "S07-EQ-04", "S07-EQ-05"],
        },
    ]
    return checks


def collect_http_metrics(campaign: Path) -> dict[str, Any]:
    exchanges = []
    for path in sorted((campaign / "evidence/api").rglob("exchange.json")):
        exchange = read_json(path)
        metrics = exchange["curl"]["metrics"]
        exchanges.append(
            {
                "path": path.relative_to(campaign).as_posix(),
                "status": http_status(exchange),
                "wall_time_seconds": metrics.get("time_total"),
                "download_bytes": exchange["response"]["body_size_bytes"],
                "upload_bytes": metrics.get("size_upload"),
            }
        )
    return {
        "request_count": len(exchanges),
        "total_http_wall_time_seconds": round(
            sum(float(item["wall_time_seconds"] or 0) for item in exchanges), 6
        ),
        "total_download_bytes": sum(int(item["download_bytes"]) for item in exchanges),
        "exchanges": exchanges,
    }


def artifact_manifest(campaign: Path, workspace: Path) -> dict[str, Any]:
    files = []
    for path in sorted(campaign.rglob("*")):
        relative = path.relative_to(campaign)
        # MMseqs2 may leave an inaccessible Windows/Cygwin `latest` link in its
        # disposable work directory.  Work files are never acceptance evidence.
        if relative.parts and relative.parts[0] == "work":
            continue
        try:
            if not path.is_file() or path.name == "artifact_manifest.json":
                continue
            files.append(file_reference(path, workspace))
        except OSError:
            # The manifest never silently skips evidence directories; only
            # filesystem links are allowed to be inaccessible here.
            if not path.is_symlink():
                raise
    return {
        "campaign_id": campaign.name,
        "generated_at": utc_now(),
        "file_count": len(files),
        "total_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
    }


def finalize_existing_campaign(*, workspace: Path, campaign: Path) -> int:
    if not campaign.is_dir():
        raise SystemExit(f"task 6 campaign does not exist: {campaign}")
    manifest_path = campaign / "reports/artifact_manifest.json"
    if manifest_path.exists():
        raise SystemExit(f"artifact manifest already exists: {manifest_path}")
    machine_report_path = campaign / "reports/task6_acceptance.json"
    markdown_report_path = campaign / "reports/TASK6_ACCEPTANCE_REPORT.md"
    readme_path = campaign / "README.md"
    if not all(path.is_file() for path in (machine_report_path, markdown_report_path, readme_path)):
        raise SystemExit("existing campaign lacks completed immutable acceptance outputs")
    report = read_json(machine_report_path)
    checks = report.get("checks") or []
    if len(checks) != 10 or not all(item.get("passed") is True for item in checks):
        raise SystemExit("existing campaign did not pass all 10 acceptance checks")
    previous = read_json(campaign / "campaign.json")
    if previous.get("status") != "FAILED_INCOMPLETE":
        raise SystemExit("only a FAILED_INCOMPLETE campaign can be finalized")
    failure_record_path = campaign / "reports/runner_attempts/attempt-001-failure.json"
    immutable_write(failure_record_path, json_bytes(previous))
    closeout_path = campaign / "reports/runner_resume_closeout.json"
    closeout = {
        "campaign_id": campaign.name,
        "status": "PASS",
        "action": "FINALIZE_EXISTING_IMMUTABLE_OUTPUTS",
        "completed_at": utc_now(),
        "previous_failure_type": previous.get("failure_type"),
        "previous_failure": previous.get("failure"),
        "acceptance_check_count": len(checks),
        "acceptance_checks_passed": sum(item["passed"] for item in checks),
        "evidence_files_modified": 0,
        "files_appended": [
            failure_record_path.relative_to(campaign).as_posix(),
            closeout_path.relative_to(campaign).as_posix(),
            manifest_path.relative_to(campaign).as_posix(),
        ],
    }
    immutable_write(closeout_path, json_bytes(closeout))
    write_json(
        campaign / "campaign.json",
        {
            "campaign_id": campaign.name,
            "classification": CLASSIFICATION,
            "status": "COMPLETE_NONPRODUCTION_ACCEPTANCE_WITH_RELEASE_GATES",
            "started_at": previous["started_at"],
            "finished_at": utc_now(),
            "production_deployment_status": DEPLOYMENT_STATUS,
            "scientific_acceptance": "NOT_RUN",
            "rule_status": RULE_STATUS,
            "expert_confirmation_ids": EXPERT_CONFIRMATION_IDS,
            "report": "reports/task6_acceptance.json",
            "run_history": [
                {
                    "attempt": 1,
                    "status": "FAILED_AFTER_ACCEPTANCE_DURING_MANIFEST_PACKAGING",
                    "record": failure_record_path.relative_to(campaign).as_posix(),
                },
                {
                    "attempt": 2,
                    "status": "FINALIZED_WITHOUT_REEXECUTING_EVIDENCE",
                    "record": closeout_path.relative_to(campaign).as_posix(),
                },
            ],
        },
    )
    manifest = artifact_manifest(campaign, workspace)
    immutable_write(manifest_path, json_bytes(manifest))
    print(
        json.dumps(
            {
                "status": "PASS",
                "campaign": str(campaign),
                "acceptance_checks": len(checks),
                "manifest_files": manifest["file_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def write_markdown_report(campaign: Path, report: dict[str, Any]) -> None:
    local = report["local_acceptance"]
    api = report["api_acceptance"]
    fallback = report["o15116_fallback"]
    checks = report["checks"]
    local_rows = []
    for query, item in local["query_summaries"].items():
        short = query.split("|")[0]
        selection = item["selection"]
        chosen = selection.get("selected_entry_id") or "—"
        local_rows.append(
            f"| {short} | {item['candidate_chain_count']} | {item['candidate_entry_count']} | "
            f"{selection['status']} | {chosen} |"
        )
    check_rows = [
        f"| {item['check_id']} | {item['name']} | {'PASS' if item['passed'] else 'FAIL'} |"
        for item in checks
    ]
    api_rows = [
        f"| {case_id} | {item['reported_total_count']} | {item['strict_candidate_entity_count']} | "
        f"{item['graphql_request_count']} | {item['selection']['status']} |"
        for case_id, item in api.items()
    ]
    text = f"""# S-07 任务 6 独立验收报告

> 批次：`{report['campaign_id']}`  
> 状态：`{report['task6_status']} / {report['production_deployment_status']}`  
> 科学验收：`{report['scientific_acceptance']}`；规则：`{report['rule_status']}`。

## 验收结论

本批次完成 S-07 的非生产独立验收：固定 wwPDB 发布的新 MMseqs2 实跑、当前官方 API 的
RCSB 完整候选读取、O15116 的 RCSB→UniProt→AlphaFold DB 连续回退、代表 mmCIF 的序列与
坐标读取，以及任务 5 的失败/恢复和 S-08/S-09 交接形状复核。{sum(item['passed'] for item in checks)}/{len(checks)}
项验收检查通过。

本结论不发布 MCP/Dify 适配器，不把 S-08/S-09 写成已部署，也不把五项暂行规则升级为专家
确认或科研金标准。缺 accession 的真实正命中 BLAST 仍观察到 100 条 profile 上限，因此禁止
用该批次自动选择 accession；它作为 P0 v0.6 的生产门禁保留。

## 固定发布新实跑

| 输入 | 严格 chain | entry | 结果 | 候选 |
|---|---:|---:|---|---|
{chr(10).join(local_rows)}

6Q00 A 链为 76/76 坐标完整；9R2Q K 链为
{local['structure_mappings']['9R2Q']['mapping']['coordinate_count']}/393，且 K/L/M/N 四链歧义继续按
R-58 阻止自动交接。运行墙钟为 {local['run']['wall_time_seconds']:.3f} 秒；工具日志报告的最大估计
内存为 {local['run']['tool_reported_estimated_memory_bytes']} B，采样到的主进程峰值工作集为
{local['run']['peak_working_set_bytes']} B。

## 当前 API 连续运行

| 用例 | API 总命中 | 严格实体 | GraphQL 批次 | 处理 |
|---|---:|---:|---:|---|
{chr(10).join(api_rows)}

O15116 在本轮 RCSB 严格候选为空后，UniProt `{fallback.get('uniprot_release')}` 与 AlphaFold DB
`{fallback.get('model_id')}` v{fallback.get('model_version')} 完成逐层序列回验，模型、confidence
与 PAE 维度一致，形成 `source=alphafolddb` 的 S-09 交接候选。全批次共
{report['resource_measurements']['http']['request_count']} 次 HTTP 往返，累计下载
{report['resource_measurements']['http']['total_download_bytes']} B。

## 检查矩阵

| ID | 检查 | 结果 |
|---|---|---|
{chr(10).join(check_rows)}

## 仍受门禁约束的项目

1. S07-EQ-01～05 继续 `PENDING`；专家结论不同需要换规则版本并重算。
2. 缺 accession 的真实 BLAST 正命中候选收集未完成；不得用 100 条封顶结果自动选 accession。
3. S-08/S-09 当前只完成交接结构验证，实际工具尚未部署。
4. OI-017 的生产状态机、等待/取消/恢复入口和逐工具 execution profile 等待 P0 v0.6。
5. 目标服务器本地数据库由接收方按既有交接方案部署和验收。

机器报告见 [task6_acceptance.json](task6_acceptance.json)，逐文件清单见
[artifact_manifest.json](artifact_manifest.json)。
"""
    immutable_write(
        campaign / "reports/TASK6_ACCEPTANCE_REPORT.md", text.encode("utf-8")
    )


def main() -> int:
    args = parse_args()
    workspace = args.workspace.resolve()
    campaign = workspace / "discovery/p0/s07" / args.campaign_id
    if args.finalize_existing:
        return finalize_existing_campaign(workspace=workspace, campaign=campaign)
    if campaign.exists():
        raise SystemExit(f"refusing to overwrite task 6 campaign: {campaign}")
    campaign.mkdir(parents=True)
    started_at = utc_now()
    write_json(
        campaign / "campaign.json",
        {
            "campaign_id": args.campaign_id,
            "classification": CLASSIFICATION,
            "status": "RUNNING",
            "started_at": started_at,
            "production_deployment_status": DEPLOYMENT_STATUS,
            "scientific_acceptance": "NOT_RUN",
            "rule_status": RULE_STATUS,
            "expert_confirmation_ids": EXPERT_CONFIRMATION_IDS,
        },
    )
    try:
        environment = local_environment(workspace)
        local, query_records = build_local_acceptance(
            workspace=workspace, campaign=campaign
        )
        one_ubq_sequence = next(
            sequence for key, sequence in query_records.items() if "P0-DISC-001" in key
        )
        o15116_sequence = next(
            sequence for key, sequence in query_records.items() if "P0-DISC-004" in key
        )
        api = {
            "API-1UBQ": run_rcsb_case(
                workspace=workspace,
                campaign=campaign,
                campaign_id=args.campaign_id,
                case_id="API-1UBQ",
                sequence=one_ubq_sequence,
            ),
            "API-O15116": run_rcsb_case(
                workspace=workspace,
                campaign=campaign,
                campaign_id=args.campaign_id,
                case_id="API-O15116",
                sequence=o15116_sequence,
            ),
        }
        if api["API-O15116"]["strict_candidate_entity_count"] != 0:
            raise ValueError(
                "O15116 gained a live strict PDB candidate; the frozen fallback sample must be reviewed"
            )
        fallback = run_o15116_fallback(
            workspace=workspace,
            campaign=campaign,
            campaign_id=args.campaign_id,
            input_sequence=o15116_sequence,
        )
        task5 = validate_task5(workspace)
        blast_cap = validate_task4_blast_cap(workspace)
        checks = build_checks(local, api, fallback, task5)
        if not all(item["passed"] for item in checks):
            failed = [item["check_id"] for item in checks if not item["passed"]]
            raise ValueError(f"Task 6 acceptance checks failed: {failed}")
        http = collect_http_metrics(campaign)
        report = {
            "schema_version": "s07-task6-acceptance.v1",
            "campaign_id": args.campaign_id,
            "generated_at": utc_now(),
            "task6_status": "COMPLETE_NONPRODUCTION_ACCEPTANCE_WITH_RELEASE_GATES",
            "classification": CLASSIFICATION,
            "production_deployment_status": DEPLOYMENT_STATUS,
            "scientific_acceptance": "NOT_RUN",
            "rule_status": RULE_STATUS,
            "expert_confirmation_ids": EXPERT_CONFIRMATION_IDS,
            "environment": environment,
            "local_acceptance": local,
            "api_acceptance": api,
            "o15116_fallback": fallback,
            "blast_no_accession_positive_path": blast_cap,
            "task5_contract_and_handoffs": task5,
            "resource_measurements": {"http": http, "local_search": local["run"]},
            "checks": checks,
            "gate_status": {
                "task6_nonproduction_acceptance": "PASS",
                "expert_scientific_rules": "PENDING_5_ITEMS",
                "positive_blast_candidate_completeness": "BLOCKED_AT_PROFILE_CAP",
                "oi_017_production_job_runtime": "NOT_IMPLEMENTED_PENDING_V0_6",
                "s08_consumer": "NOT_DEPLOYED",
                "s09_consumer": "NOT_DEPLOYED",
                "target_server_local_profile": "HANDOFF_PENDING_RECEIVING_TEAM",
                "mcp_adapter": "NOT_DEPLOYED",
                "dify_workflow": "NOT_DEPLOYED",
            },
        }
        report_path = campaign / "reports/task6_acceptance.json"
        immutable_write(report_path, json_bytes(report))
        write_markdown_report(campaign, report)
        readme = f"""# {args.campaign_id}

S-07 任务 6 的非生产独立验收批次。它包含固定发布的新 MMseqs2 实跑、当前官方 API 原始往返、
结构/序列回验、资源记录，以及任务 5 故障恢复和 S-08/S-09 交接复核。

- 状态：`COMPLETE_NONPRODUCTION_ACCEPTANCE_WITH_RELEASE_GATES`
- 生产部署：`NOT_DEPLOYED`
- 科学验收：`NOT_RUN`
- 待专家确认：S07-EQ-01～05
- 报告：[TASK6_ACCEPTANCE_REPORT.md](reports/TASK6_ACCEPTANCE_REPORT.md)

运行器会拒绝覆盖现有批次。要复跑必须使用新的 `campaign_id`。
"""
        immutable_write(campaign / "README.md", readme.encode("utf-8"))
        # The status file is the sole small mutable lifecycle record for an in-progress
        # campaign.  Replace it only after all immutable evidence has been written.
        write_json(
            campaign / "campaign.json",
            {
                "campaign_id": args.campaign_id,
                "classification": CLASSIFICATION,
                "status": "COMPLETE_NONPRODUCTION_ACCEPTANCE_WITH_RELEASE_GATES",
                "started_at": started_at,
                "finished_at": utc_now(),
                "production_deployment_status": DEPLOYMENT_STATUS,
                "scientific_acceptance": "NOT_RUN",
                "rule_status": RULE_STATUS,
                "expert_confirmation_ids": EXPERT_CONFIRMATION_IDS,
                "report": "reports/task6_acceptance.json",
            },
        )
        manifest = artifact_manifest(campaign, workspace)
        immutable_write(
            campaign / "reports/artifact_manifest.json", json_bytes(manifest)
        )
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "campaign": str(campaign),
                    "checks": len(checks),
                    "http_requests": http["request_count"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        write_json(
            campaign / "campaign.json",
            {
                "campaign_id": args.campaign_id,
                "classification": CLASSIFICATION,
                "status": "FAILED_INCOMPLETE",
                "started_at": started_at,
                "failed_at": utc_now(),
                "failure_type": type(exc).__name__,
                "failure": str(exc),
                "production_deployment_status": DEPLOYMENT_STATUS,
                "scientific_acceptance": "NOT_RUN",
            },
        )
        raise


if __name__ == "__main__":
    sys.exit(main())
