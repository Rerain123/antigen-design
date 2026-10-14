"""Execute the evidence-only P0-M1B S-07 candidate campaign.

The runner deliberately exposes no MCP endpoint and performs no scientific
classification, eligibility decision, structure selection, or workflow route.
Its only job is to preserve the real output shapes needed to review S07-D09.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


CLASSIFICATION = "NON_PRODUCTION_OUTPUT_AUDIT"
DEPLOYMENT_STATUS = "NOT_DEPLOYED"
RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
AFDB_API_ROOT = "https://alphafold.ebi.ac.uk/api/prediction"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _absolute_without_link_resolution(path: Path) -> Path:
    """Make a path absolute while preserving Windows subst/junction aliases."""

    return Path(os.path.abspath(str(path)))


def _safe_child(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes its allowed root: {relative}")
    return candidate


def _require_identifier(value: str, pattern: str, label: str) -> None:
    if not re.fullmatch(pattern, value):
        raise ValueError(f"invalid {label}: {value!r}")


def load_and_validate_plan(path: Path) -> dict[str, Any]:
    """Load the bounded evidence plan and reject production-like settings."""

    plan = read_json(path)
    if plan.get("classification") != CLASSIFICATION:
        raise ValueError("P0-M1B plan must be classified as non-production output audit")
    if plan.get("production_deployment_status") != DEPLOYMENT_STATUS:
        raise ValueError("P0-M1B plan must remain NOT_DEPLOYED")
    limits = plan.get("audit_limits", {})
    rows = int(limits.get("rcsb_rows_per_page", 0))
    max_pages = int(limits.get("rcsb_max_pages_per_query", 0))
    if not 1 <= rows <= 100:
        raise ValueError("RCSB audit page size must be between 1 and 100")
    if not 1 <= max_pages <= 50:
        raise ValueError("RCSB audit page guard must be between 1 and 50")
    if int(limits.get("http_timeout_seconds", 0)) <= 0:
        raise ValueError("HTTP timeout must be positive")
    if int(limits.get("blast_timeout_seconds", 0)) <= 0:
        raise ValueError("BLAST timeout must be positive")

    searches = plan.get("rcsb_searches", [])
    if not searches:
        raise ValueError("at least one RCSB search is required")
    for item in searches:
        _require_identifier(item["case_id"], r"P0-DISC-[0-9]{3}", "case ID")
        if not str(item.get("request_template", "")).startswith("requests/rcsb/"):
            raise ValueError("RCSB request templates must come from the frozen campaign")
    for item in plan.get("rcsb_materialization_probes", []):
        _require_identifier(item["entry_id"], r"[A-Za-z0-9]{4}", "PDB entry ID")
        _require_identifier(item["entity_id"], r"[0-9]+", "polymer entity ID")
        _require_identifier(item["chain_id"], r"[A-Za-z0-9]+", "chain ID")
    for item in plan.get("afdb_queries", []):
        _require_identifier(item["accession"], r"[A-Za-z0-9_.-]+", "AFDB identifier")

    forbidden = set(plan.get("forbidden_outputs", []))
    required_forbidden = {
        "scientific_classification",
        "eligibility_decision",
        "selected_candidate",
        "production_route",
    }
    if not required_forbidden.issubset(forbidden):
        raise ValueError("plan does not forbid all scientific decision outputs")
    return plan


def build_rcsb_page_request(
    template: dict[str, Any], *, start: int, rows: int, query_id: str
) -> dict[str, Any]:
    """Create one page request without mutating the frozen template."""

    if start < 0 or rows <= 0:
        raise ValueError("pagination start and rows must be non-negative/positive")
    request = copy.deepcopy(template)
    options = request.setdefault("request_options", {})
    options["paginate"] = {"start": start, "rows": rows}
    request.setdefault("request_info", {})["query_id"] = query_id
    return request


def _http_status(exchange: dict[str, Any] | None) -> int | None:
    if not exchange:
        return None
    metrics = exchange.get("curl", {}).get("metrics", {})
    value = metrics.get("http_code") or metrics.get("response_code")
    if value is None and isinstance(metrics.get("unparsed_stdout"), str):
        match = re.search(
            r'"(?:http_code|response_code)"\s*:\s*([0-9]+)',
            metrics["unparsed_stdout"],
        )
        value = match.group(1) if match else None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _run_capture(
    command: list[str], *, workspace: Path, label: str, events: list[dict[str, Any]]
) -> int:
    completed = subprocess.run(
        command,
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    events.append(
        {
            "label": label,
            "exit_code": completed.returncode,
            "stderr_tail": completed.stderr[-1000:] if completed.stderr else "",
        }
    )
    return completed.returncode


def _capture_http(
    *,
    workspace: Path,
    campaign_id: str,
    label: str,
    method: str,
    url: str,
    output_dir: Path,
    response_name: str,
    timeout_seconds: int,
    events: list[dict[str, Any]],
    body_file: Path | None = None,
    accept: str = "application/json",
) -> dict[str, Any] | None:
    helper = workspace / "scripts" / "capture_http_evidence.py"
    command = [
        sys.executable,
        str(helper),
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
        str(timeout_seconds),
    ]
    if sys.platform == "win32":
        command.append("--ssl-revoke-best-effort")
    if body_file is not None:
        command.extend(["--body-file", str(body_file)])
    _run_capture(command, workspace=workspace, label=label, events=events)
    exchange_path = output_dir / "exchange.json"
    return read_json(exchange_path) if exchange_path.is_file() else None


def _capture_cli(
    *,
    workspace: Path,
    campaign_id: str,
    label: str,
    output_dir: Path,
    timeout_seconds: int,
    command_to_run: list[str],
    events: list[dict[str, Any]],
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    helper = workspace / "scripts" / "capture_cli_evidence.py"
    command = [
        sys.executable,
        str(helper),
        "--exchange-id",
        f"{campaign_id}--{label}",
        "--output-dir",
        str(output_dir),
        "--timeout-seconds",
        str(timeout_seconds),
    ]
    if cwd is not None:
        command.extend(["--cwd", str(cwd)])
    for key, value in sorted((environment or {}).items()):
        command.extend(["--env", f"{key}={value}"])
    command.append("--")
    command.extend(command_to_run)
    _run_capture(command, workspace=workspace, label=label, events=events)
    exchange_path = output_dir / "exchange.json"
    return read_json(exchange_path) if exchange_path.is_file() else None


def _copy_frozen_inputs(
    *, source_root: Path, campaign_root: Path, plan_path: Path, plan: dict[str, Any]
) -> None:
    (campaign_root / "plan").mkdir(parents=True)
    shutil.copyfile(plan_path, campaign_root / "plan" / "plan.json")
    shutil.copytree(source_root / "samples", campaign_root / "inputs" / "samples")
    for search in plan["rcsb_searches"]:
        source = _safe_child(source_root, search["request_template"])
        target = campaign_root / "inputs" / "request-templates" / "rcsb" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    profile_source = _safe_child(source_root, plan["blast"]["profile"])
    profile_target = campaign_root / "inputs" / "blast" / "discovery-profile.json"
    profile_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(profile_source, profile_target)


def _run_rcsb_searches(
    *,
    workspace: Path,
    source_root: Path,
    campaign_root: Path,
    campaign_id: str,
    plan: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    limits = plan["audit_limits"]
    rows = int(limits["rcsb_rows_per_page"])
    max_pages = int(limits["rcsb_max_pages_per_query"])
    timeout = int(limits["http_timeout_seconds"])

    for search in plan["rcsb_searches"]:
        case_id = search["case_id"]
        template = read_json(_safe_child(source_root, search["request_template"]))
        case_root = campaign_root / "evidence" / "rcsb-search" / case_id
        pages: list[dict[str, Any]] = []
        total_count: int | None = None
        stop_reason = "MAX_PAGE_GUARD_REACHED"
        for page_number in range(1, max_pages + 1):
            start = (page_number - 1) * rows
            request = build_rcsb_page_request(
                template,
                start=start,
                rows=rows,
                query_id=f"{campaign_id}--{case_id}--page-{page_number:04d}",
            )
            request_path = (
                campaign_root
                / "requests"
                / "rcsb"
                / case_id
                / f"page-{page_number:04d}.json"
            )
            write_json(request_path, request)
            page_dir = case_root / f"page-{page_number:04d}"
            exchange = _capture_http(
                workspace=workspace,
                campaign_id=campaign_id,
                label=f"{case_id}--rcsb-search-page-{page_number:04d}",
                method="POST",
                url=RCSB_SEARCH_URL,
                output_dir=page_dir,
                response_name="response.json",
                timeout_seconds=timeout,
                events=events,
                body_file=request_path,
            )
            status = _http_status(exchange)
            page_record: dict[str, Any] = {
                "page_number": page_number,
                "start": start,
                "rows_requested": rows,
                "http_status": status,
                "result_count": None,
                "reported_total_count": None,
            }
            response_path = page_dir / "response.json"
            if status == 204:
                page_record["result_count"] = 0
                page_record["reported_total_count"] = 0
                total_count = 0
                pages.append(page_record)
                stop_reason = "SUCCESSFUL_EMPTY_RESPONSE"
                break
            if status != 200 or not response_path.is_file():
                pages.append(page_record)
                stop_reason = "SOURCE_OR_TRANSPORT_FAILURE"
                break
            try:
                response = read_json(response_path)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pages.append(page_record)
                stop_reason = "UNPARSEABLE_RESPONSE"
                break
            result_count = len(response.get("result_set", []))
            reported_total = int(response.get("total_count", result_count))
            total_count = reported_total if total_count is None else total_count
            page_record["result_count"] = result_count
            page_record["reported_total_count"] = reported_total
            pages.append(page_record)
            if start + result_count >= reported_total:
                stop_reason = "REPORTED_RESULT_SET_EXHAUSTED"
                break
            if result_count == 0:
                stop_reason = "EMPTY_PAGE_BEFORE_REPORTED_TOTAL"
                break

        returned = sum(int(item["result_count"] or 0) for item in pages)
        write_json(
            case_root / "pagination-run.json",
            {
                "case_id": case_id,
                "classification": CLASSIFICATION,
                "production_deployment_status": DEPLOYMENT_STATUS,
                "page_size": rows,
                "page_guard": max_pages,
                "reported_total_count": total_count,
                "returned_result_count": returned,
                "pages": pages,
                "stop_reason": stop_reason,
                "guard_is_production_default": False,
            },
        )


def _run_rcsb_materializations(
    *,
    workspace: Path,
    campaign_root: Path,
    campaign_id: str,
    plan: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    timeout = int(plan["audit_limits"]["http_timeout_seconds"])
    for probe in plan.get("rcsb_materialization_probes", []):
        case_id = probe["case_id"]
        probe_id = probe["probe_id"]
        entry = probe["entry_id"].upper()
        entity = probe["entity_id"]
        chain = probe["chain_id"]
        root = campaign_root / "evidence" / "rcsb-materialized" / case_id / probe_id
        requests = [
            (
                "entry",
                f"https://data.rcsb.org/rest/v1/core/entry/{entry}",
                "response.json",
                "application/json",
            ),
            (
                "polymer-entity",
                f"https://data.rcsb.org/rest/v1/core/polymer_entity/{entry}/{entity}",
                "response.json",
                "application/json",
            ),
            (
                "polymer-instance",
                f"https://data.rcsb.org/rest/v1/core/polymer_entity_instance/{entry}/{chain}",
                "response.json",
                "application/json",
            ),
            (
                "mmcif",
                f"https://files.rcsb.org/download/{entry}.cif",
                f"{entry}.cif",
                "chemical/x-cif",
            ),
        ]
        for kind, url, response_name, accept in requests:
            _capture_http(
                workspace=workspace,
                campaign_id=campaign_id,
                label=f"{probe_id}--{kind}",
                method="GET",
                url=url,
                output_dir=root / kind,
                response_name=response_name,
                timeout_seconds=timeout,
                events=events,
                accept=accept,
            )


def _safe_download_name(url: str, fallback: str) -> str:
    name = Path(urlparse(url).path).name
    return name if re.fullmatch(r"[A-Za-z0-9_.-]+", name or "") else fallback


def _run_afdb(
    *,
    workspace: Path,
    campaign_root: Path,
    campaign_id: str,
    plan: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    timeout = int(plan["audit_limits"]["http_timeout_seconds"])
    derived = [
        ("cifUrl", "model-cif", "model.cif", "chemical/x-cif"),
        ("plddtDocUrl", "confidence", "confidence.json", "application/json"),
        ("paeDocUrl", "pae", "pae.json", "application/json"),
    ]
    for item in plan.get("afdb_queries", []):
        case_id = item["case_id"]
        accession = item["accession"]
        root = campaign_root / "evidence" / "afdb" / case_id / accession
        metadata_dir = root / "metadata"
        exchange = _capture_http(
            workspace=workspace,
            campaign_id=campaign_id,
            label=f"{case_id}--afdb-metadata--{accession}",
            method="GET",
            url=f"{AFDB_API_ROOT}/{accession}",
            output_dir=metadata_dir,
            response_name="response.json",
            timeout_seconds=timeout,
            events=events,
        )
        response_path = metadata_dir / "response.json"
        if _http_status(exchange) != 200 or not response_path.is_file():
            continue
        try:
            payload = read_json(response_path)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            continue
        metadata = payload[0]
        for field, label, fallback, accept in derived:
            url = metadata.get(field)
            if not isinstance(url, str) or not url.startswith("https://alphafold.ebi.ac.uk/"):
                continue
            _capture_http(
                workspace=workspace,
                campaign_id=campaign_id,
                label=f"{case_id}--afdb-{label}--{accession}",
                method="GET",
                url=url,
                output_dir=root / label,
                response_name=_safe_download_name(url, fallback),
                timeout_seconds=timeout,
                events=events,
                accept=accept,
            )


def _dependency_ref(path: Path) -> dict[str, Any]:
    return {
        "path": str(_absolute_without_link_resolution(path)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _run_blast(
    *,
    workspace: Path,
    campaign_root: Path,
    campaign_id: str,
    plan: dict[str, Any],
    blast_bin: Path,
    blast_db: Path,
    events: list[dict[str, Any]],
) -> None:
    profile = read_json(campaign_root / "inputs" / "blast" / "discovery-profile.json")
    if profile.get("production_approved") is not False:
        raise ValueError("P0-M1B may only use the unapproved discovery BLAST profile")
    blastp = blast_bin / ("blastp.exe" if sys.platform == "win32" else "blastp")
    formatter = (
        blast_bin / ("blast_formatter.exe" if sys.platform == "win32" else "blast_formatter")
    )
    blastdbcmd = (
        blast_bin / ("blastdbcmd.exe" if sys.platform == "win32" else "blastdbcmd")
    )
    for executable in (blastp, formatter, blastdbcmd):
        if not executable.is_file():
            raise FileNotFoundError(executable)
    if not blast_db.parent.is_dir() or not list(blast_db.parent.glob(blast_db.name + ".*")):
        raise FileNotFoundError(f"BLAST database files not found for base: {blast_db}")

    dependencies = {
        "classification": CLASSIFICATION,
        "production_deployment_status": DEPLOYMENT_STATUS,
        "executables": {
            "blastp": _dependency_ref(blastp),
            "blast_formatter": _dependency_ref(formatter),
            "blastdbcmd": _dependency_ref(blastdbcmd),
        },
        "database_base": str(blast_db),
        "database_files": [
            _dependency_ref(path)
            for path in sorted(blast_db.parent.glob(blast_db.name + ".*"))
            if path.is_file()
        ],
        "profile_sha256": sha256_file(
            campaign_root / "inputs" / "blast" / "discovery-profile.json"
        ),
    }
    write_json(campaign_root / "runtime-dependencies.json", dependencies)

    timeout = int(plan["audit_limits"]["blast_timeout_seconds"])
    search = profile["search_parameters"]
    formats = profile["derived_formats"]
    environment = {"BLASTDB": str(blast_db.parent)}
    _capture_cli(
        workspace=workspace,
        campaign_id=campaign_id,
        label="blast-database-info",
        output_dir=campaign_root / "evidence" / "blast" / "database-info",
        timeout_seconds=timeout,
        command_to_run=[
            str(blastdbcmd),
            "-db",
            str(blast_db),
            "-dbtype",
            "prot",
            "-info",
        ],
        events=events,
        cwd=blast_db.parent,
        environment=environment,
    )

    for item in plan["blast"]["cases"]:
        case_id = item["case_id"]
        query_name = Path(item["sequence_file"]).name
        query = campaign_root / "inputs" / "samples" / query_name
        if not query.is_file():
            raise FileNotFoundError(query)
        case_root = campaign_root / "evidence" / "blast" / case_id
        search_dir = case_root / "search"
        archive = search_dir / "result.asn"
        exchange = _capture_cli(
            workspace=workspace,
            campaign_id=campaign_id,
            label=f"{case_id}--blastp-search",
            output_dir=search_dir,
            timeout_seconds=timeout,
            command_to_run=[
                str(blastp),
                "-task",
                str(search["task"]),
                "-query",
                str(query),
                "-db",
                str(blast_db),
                "-evalue",
                str(search["evalue"]),
                "-max_target_seqs",
                str(search["max_target_seqs"]),
                "-num_threads",
                str(search["num_threads"]),
                "-outfmt",
                str(search["archive_outfmt"]),
                "-out",
                str(archive),
            ],
            events=events,
            cwd=blast_db.parent,
            environment=environment,
        )
        if not exchange or exchange.get("exit_code") != 0 or not archive.is_file():
            continue
        _capture_cli(
            workspace=workspace,
            campaign_id=campaign_id,
            label=f"{case_id}--blast-format-tabular",
            output_dir=case_root / "format-tabular",
            timeout_seconds=timeout,
            command_to_run=[
                str(formatter),
                "-archive",
                str(archive),
                "-outfmt",
                str(formats["tabular_outfmt"]),
                "-out",
                str(case_root / "format-tabular" / "result.tsv"),
            ],
            events=events,
            cwd=blast_db.parent,
            environment=environment,
        )
        _capture_cli(
            workspace=workspace,
            campaign_id=campaign_id,
            label=f"{case_id}--blast-format-json",
            output_dir=case_root / "format-json",
            timeout_seconds=timeout,
            command_to_run=[
                str(formatter),
                "-archive",
                str(archive),
                "-outfmt",
                str(formats["json_outfmt"]),
                "-out",
                str(case_root / "format-json" / "result.json"),
            ],
            events=events,
            cwd=blast_db.parent,
            environment=environment,
        )


def run_campaign(
    *,
    workspace: Path,
    plan_path: Path,
    campaign_root: Path,
    campaign_id: str,
    blast_bin: Path | None,
    blast_db: Path | None,
    skip_network: bool = False,
    skip_blast: bool = False,
) -> dict[str, Any]:
    """Run a fresh, immutable P0-M1B evidence campaign."""

    workspace = _absolute_without_link_resolution(workspace)
    plan_path = _absolute_without_link_resolution(plan_path)
    campaign_root = _absolute_without_link_resolution(campaign_root)
    _require_identifier(campaign_id, r"p0-s07-m1b-[A-Za-z0-9-]+", "campaign ID")
    if campaign_root.exists() and any(campaign_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite campaign: {campaign_root}")
    plan = load_and_validate_plan(plan_path)
    source_root = workspace / "discovery" / "p0" / "s07" / plan["source_campaign"]
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)
    campaign_root.mkdir(parents=True, exist_ok=True)
    _copy_frozen_inputs(
        source_root=source_root,
        campaign_root=campaign_root,
        plan_path=plan_path,
        plan=plan,
    )

    started_at = utc_now()
    events: list[dict[str, Any]] = []
    write_json(
        campaign_root / "campaign.json",
        {
            "campaign_id": campaign_id,
            "classification": CLASSIFICATION,
            "production_deployment_status": DEPLOYMENT_STATUS,
            "source_campaign": plan["source_campaign"],
            "plan_id": plan["plan_id"],
            "plan_sha256": sha256_file(plan_path),
            "started_at": started_at,
            "execution_status": "RUNNING",
            "scope": "S07-D09 output evidence only",
            "network_skipped": skip_network,
            "blast_skipped": skip_blast,
            "contains_scientific_decisions": False,
            "connected_to_mcp_or_workflow": False,
        },
    )

    if not skip_network:
        _run_rcsb_searches(
            workspace=workspace,
            source_root=source_root,
            campaign_root=campaign_root,
            campaign_id=campaign_id,
            plan=plan,
            events=events,
        )
        _run_rcsb_materializations(
            workspace=workspace,
            campaign_root=campaign_root,
            campaign_id=campaign_id,
            plan=plan,
            events=events,
        )
        _run_afdb(
            workspace=workspace,
            campaign_root=campaign_root,
            campaign_id=campaign_id,
            plan=plan,
            events=events,
        )
    if not skip_blast:
        if blast_bin is None or blast_db is None:
            raise ValueError("BLAST paths are required unless --skip-blast is used")
        _run_blast(
            workspace=workspace,
            campaign_root=campaign_root,
            campaign_id=campaign_id,
            plan=plan,
            blast_bin=_absolute_without_link_resolution(blast_bin),
            blast_db=_absolute_without_link_resolution(blast_db),
            events=events,
        )

    finished_at = utc_now()
    failed_captures = [event for event in events if event["exit_code"] != 0]
    summary = {
        "campaign_id": campaign_id,
        "classification": CLASSIFICATION,
        "production_deployment_status": DEPLOYMENT_STATUS,
        "started_at": started_at,
        "finished_at": finished_at,
        "execution_status": "COMPLETE" if not failed_captures else "COMPLETE_WITH_CAPTURE_FAILURES",
        "capture_count": len(events),
        "capture_process_failure_count": len(failed_captures),
        "events": events,
        "contains_scientific_decisions": False,
        "connected_to_mcp_or_workflow": False,
    }
    write_json(campaign_root / "run-summary.json", summary)
    campaign = read_json(campaign_root / "campaign.json")
    campaign.update(
        {
            "finished_at": finished_at,
            "execution_status": summary["execution_status"],
            "capture_count": len(events),
            "capture_process_failure_count": len(failed_captures),
        }
    )
    write_json(campaign_root / "campaign.json", campaign)
    return summary
