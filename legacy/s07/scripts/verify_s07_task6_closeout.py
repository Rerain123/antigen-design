"""Close out the immutable S-07 task-6 acceptance campaign.

The script performs a read-only audit of the evidence captured by
``run_s07_task6_acceptance.py``, runs the repository validation gates, and
appends closeout records to the selected campaign.  It never rewrites the
original campaign report or its artifact manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CAMPAIGN = "p0-s07-task6-acceptance-20260903-c"
EXPECTED_CHECK_IDS = [f"T6-C{number:02d}" for number in range(1, 11)]
EXPECTED_EXPERT_IDS = [f"S07-EQ-{number:02d}" for number in range(1, 6)]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def immutable_write(path: Path, data: bytes) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite immutable closeout file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_reference(path: Path, workspace: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(workspace).as_posix(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_original_manifest(
    manifest_path: Path, workspace: Path
) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    verified = 0
    total_bytes = 0
    for record in manifest["files"]:
        path = workspace / record["path"]
        require(path.is_file(), f"Manifest file missing: {record['path']}")
        actual_size = path.stat().st_size
        actual_sha = sha256_file(path)
        require(
            actual_size == record["size_bytes"],
            f"Manifest size mismatch: {record['path']}",
        )
        require(
            actual_sha == record["sha256"],
            f"Manifest SHA-256 mismatch: {record['path']}",
        )
        verified += 1
        total_bytes += actual_size
    require(verified == manifest["file_count"], "Manifest file count mismatch")
    require(total_bytes == manifest["total_bytes"], "Manifest byte total mismatch")
    return {
        "status": "PASS",
        "verified_file_count": verified,
        "verified_total_bytes": total_bytes,
        "manifest": file_reference(manifest_path, workspace),
    }


def run_validation(
    workspace: Path, reports: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    python = workspace / ".venv" / "Scripts" / "python.exe"
    require(python.is_file(), f"Project Python is missing: {python}")
    junit = reports / "pytest_results.xml"
    pytest_log = reports / "pytest_output.txt"
    docs_log = reports / "docs_check_output.txt"
    for path in (junit, pytest_log, docs_log):
        require(not path.exists(), f"Validation output already exists: {path}")

    temp_root = workspace / ".tmp"
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="task6-closeout-", dir=temp_root) as base_temp:
        pytest_command = [
            str(python),
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "-q",
            f"--basetemp={base_temp}",
            f"--junitxml={junit}",
        ]
        pytest_run = subprocess.run(
            pytest_command,
            cwd=workspace,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    immutable_write(
        pytest_log,
        (
            "$ " + subprocess.list2cmdline(pytest_command) + "\n\n"
            + pytest_run.stdout
            + ("\n[stderr]\n" + pytest_run.stderr if pytest_run.stderr else "")
        ).encode("utf-8"),
    )
    require(pytest_run.returncode == 0, "Full pytest validation failed")
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    test_count = sum(int(suite.attrib.get("tests", 0)) for suite in suites)
    failures = sum(int(suite.attrib.get("failures", 0)) for suite in suites)
    errors = sum(int(suite.attrib.get("errors", 0)) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", 0)) for suite in suites)
    require(test_count >= 116, f"Expected at least 116 tests, observed {test_count}")
    require(failures == 0 and errors == 0, "JUnit records test failures or errors")

    docs_command = [str(python), str(workspace / "scripts" / "check_docs.py")]
    docs_run = subprocess.run(
        docs_command,
        cwd=workspace,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    immutable_write(
        docs_log,
        (
            "$ " + subprocess.list2cmdline(docs_command) + "\n\n"
            + docs_run.stdout
            + ("\n[stderr]\n" + docs_run.stderr if docs_run.stderr else "")
        ).encode("utf-8"),
    )
    require(docs_run.returncode == 0, "Documentation validation failed")
    require("documentation_status=PASS" in docs_run.stdout, "Docs PASS marker missing")

    return (
        {
            "status": "PASS",
            "command": pytest_command,
            "tests": test_count,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "junit": file_reference(junit, workspace),
            "log": file_reference(pytest_log, workspace),
        },
        {
            "status": "PASS",
            "command": docs_command,
            "log": file_reference(docs_log, workspace),
        },
    )


def verify_acceptance(
    workspace: Path, campaign: Path, report: dict[str, Any]
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(check_id: str, condition: bool, evidence: Any) -> None:
        require(condition, f"Closeout check failed: {check_id}")
        checks.append({"check_id": check_id, "status": "PASS", "evidence": evidence})

    campaign_record = read_json(campaign / "campaign.json")
    check(
        "CLOSE-T6-01",
        campaign_record["status"]
        == "COMPLETE_NONPRODUCTION_ACCEPTANCE_WITH_RELEASE_GATES"
        and report["task6_status"]
        == "COMPLETE_NONPRODUCTION_ACCEPTANCE_WITH_RELEASE_GATES"
        and report["production_deployment_status"] == "NOT_DEPLOYED"
        and report["scientific_acceptance"] == "NOT_RUN",
        {
            "campaign_status": campaign_record["status"],
            "deployment": report["production_deployment_status"],
            "scientific_acceptance": report["scientific_acceptance"],
        },
    )

    task_checks = {item["check_id"]: item["passed"] for item in report["checks"]}
    check(
        "CLOSE-T6-02",
        list(task_checks) == EXPECTED_CHECK_IDS and all(task_checks.values()),
        {"passed": len(task_checks), "expected_ids": EXPECTED_CHECK_IDS},
    )

    local = report["local_acceptance"]
    local_queries = local["query_summaries"]
    ubiquitin = local_queries[
        "P0-DISC-001|1UBQ_1|ubiquitin|discovery_control"
    ]
    tp53 = local_queries[
        "P0-DISC-002|UniProtKB_P04637|TP53_HUMAN|discovery_control"
    ]
    check(
        "CLOSE-T6-03",
        local["database"]["release_id"] == "wwpdb-20260829-mmseqs2-18-8cc5c"
        and local["strict_candidate_count"] == 2466
        and ubiquitin["candidate_chain_count"] == 2442
        and ubiquitin["candidate_entry_count"] == 1333
        and ubiquitin["selection"]["selected_entry_id"] == "6Q00"
        and tp53["selection"]["status"] == "REVIEW_REQUIRED"
        and tp53["selection"]["matching_chain_ids"] == ["K", "L", "M", "N"],
        {
            "release": local["database"]["release_id"],
            "strict_candidate_count": local["strict_candidate_count"],
            "ubiquitin_selection": ubiquitin["selection"],
            "tp53_selection": tp53["selection"],
        },
    )

    mappings = local["structure_mappings"]
    check(
        "CLOSE-T6-04",
        mappings["6Q00"]["mapping"]["coordinate_complete"] is True
        and mappings["6Q00"]["mapping"]["coordinate_count"] == 76
        and mappings["9R2Q"]["mapping"]["coordinate_complete"] is False
        and mappings["9R2Q"]["mapping"]["coordinate_count"] == 200,
        {
            "6Q00": mappings["6Q00"]["mapping"]["coordinate_count"],
            "9R2Q": mappings["9R2Q"]["mapping"]["coordinate_count"],
        },
    )

    api_1ubq = report["api_acceptance"]["API-1UBQ"]
    api_o15116 = report["api_acceptance"]["API-O15116"]
    check(
        "CLOSE-T6-05",
        api_1ubq["return_all_hits"] is True
        and api_1ubq["reported_total_count"] == 1623
        and api_1ubq["returned_result_count"] == 1623
        and api_1ubq["strict_candidate_entity_count"] == 1588
        and api_1ubq["candidate_chain_count"] == 2422
        and api_1ubq["metadata_collection_complete"] is True
        and api_1ubq["graphql_request_count"] == 16
        and api_o15116["search_http_status"] == 204
        and api_o15116["returned_result_count"] == 0,
        {
            "API-1UBQ": {
                "total": api_1ubq["reported_total_count"],
                "strict_entities": api_1ubq["strict_candidate_entity_count"],
                "chains": api_1ubq["candidate_chain_count"],
                "graphql_requests": api_1ubq["graphql_request_count"],
            },
            "API-O15116": {
                "http_status": api_o15116["search_http_status"],
                "total": api_o15116["returned_result_count"],
            },
        },
    )

    graphql_body = next(
        (campaign / "evidence" / "api" / "rcsb" / "API-1UBQ" / "metadata").glob(
            "chunk-*/request.body.json"
        )
    ).read_text(encoding="utf-8-sig")
    candidates = read_json(
        campaign / "results" / "api" / "rcsb" / "API-1UBQ-candidates.json"
    )
    integrative = [
        item for item in candidates if item["entry_id"] in {"8ZZ4", "9A1L"}
    ]
    selection_reasons = api_1ubq["selection"]["reason_codes"]
    check(
        "CLOSE-T6-06",
        "experimental_method" in graphql_body
        and len(integrative) == 3
        and all(
            item["method"] == "Integrative" and item["method_group"] == "OTHER"
            for item in integrative
        )
        and "INCOMPARABLE_METHOD_CANDIDATES_RETAINED_AS_PROVISIONAL_BACKUP"
        in selection_reasons,
        {
            "metadata_field": "rcsb_entry_info.experimental_method",
            "integrative_candidate_count": len(integrative),
            "selection_reason_codes": selection_reasons,
        },
    )

    fallback = report["o15116_fallback"]
    check(
        "CLOSE-T6-07",
        fallback["uniprot_release"] == "2026_03"
        and fallback["model_id"] == "AF-O15116-F1"
        and fallback["model_version"] == "6"
        and all(fallback["sequence_checks"].values())
        and fallback["confidence_dimensions_valid"] is True
        and fallback["coordinate_mapping"]["coordinate_complete"] is True,
        {
            "uniprot_release": fallback["uniprot_release"],
            "model_id": fallback["model_id"],
            "model_version": fallback["model_version"],
            "sequence_checks": fallback["sequence_checks"],
        },
    )

    task5 = report["task5_contract_and_handoffs"]
    handoff_counts = {
        key: value["count"] for key, value in task5["handoffs"].items()
    }
    check(
        "CLOSE-T6-08",
        task5["validated_result_count"] == 19
        and handoff_counts == {"BLOCKED": 11, "S-08": 2, "S-09": 6}
        and task5["fault_and_recovery"]
        == {
            "rejection_check_count": 20,
            "route_case_count": 19,
            "status": "PASS",
            "storage_check_count": 7,
        },
        {
            "validated_results": task5["validated_result_count"],
            "handoffs": handoff_counts,
            "fault_and_recovery": task5["fault_and_recovery"],
        },
    )

    blast = report["blast_no_accession_positive_path"]
    check(
        "CLOSE-T6-09",
        blast["reported_hit_count"] == 100
        and blast["configured_max_alignments"] == 100
        and blast["candidate_collection_complete"] is False
        and blast["automatic_selection_allowed"] is False
        and blast["status"] == "REVIEW_REQUIRED_INCOMPLETE_CANDIDATE_COLLECTION",
        blast,
    )

    expert_path = workspace / "docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md"
    expert_text = expert_path.read_text(encoding="utf-8-sig")
    headings = re.findall(r"^## \d+\. (S07-EQ-\d{2})：", expert_text, re.MULTILINE)
    pending_rows = re.findall(
        r"^\| (S07-EQ-\d{2}) .*?\| `PENDING` \|$", expert_text, re.MULTILINE
    )
    check(
        "CLOSE-T6-10",
        headings == EXPECTED_EXPERT_IDS
        and pending_rows[:5] == EXPECTED_EXPERT_IDS
        and report["expert_confirmation_ids"] == EXPECTED_EXPERT_IDS
        and report["rule_status"]
        == "PROVISIONAL_USER_APPROVED_EXPERT_PENDING",
        {
            "expert_confirmation_ids": EXPECTED_EXPERT_IDS,
            "status": "PENDING",
            "source": file_reference(expert_path, workspace),
        },
    )

    gate_status = report["gate_status"]
    check(
        "CLOSE-T6-11",
        gate_status
        == {
            "dify_workflow": "NOT_DEPLOYED",
            "expert_scientific_rules": "PENDING_5_ITEMS",
            "mcp_adapter": "NOT_DEPLOYED",
            "oi_017_production_job_runtime": "NOT_IMPLEMENTED_PENDING_V0_6",
            "positive_blast_candidate_completeness": "BLOCKED_AT_PROFILE_CAP",
            "s08_consumer": "NOT_DEPLOYED",
            "s09_consumer": "NOT_DEPLOYED",
            "target_server_local_profile": "HANDOFF_PENDING_RECEIVING_TEAM",
            "task6_nonproduction_acceptance": "PASS",
        },
        gate_status,
    )

    prior_a = read_json(
        workspace
        / "discovery/p0/s07/p0-s07-task6-acceptance-20260903-a/campaign.json"
    )
    prior_b = read_json(
        workspace
        / "discovery/p0/s07/p0-s07-task6-acceptance-20260903-b/campaign.json"
    )
    check(
        "CLOSE-T6-12",
        prior_a["status"] == "FAILED_INCOMPLETE"
        and prior_a["failure"] == "Task 6 acceptance checks failed: ['T6-C06']"
        and prior_b["status"]
        == "COMPLETE_NONPRODUCTION_ACCEPTANCE_WITH_RELEASE_GATES"
        and [item["status"] for item in prior_b["run_history"]]
        == [
            "FAILED_AFTER_ACCEPTANCE_DURING_MANIFEST_PACKAGING",
            "FINALIZED_WITHOUT_REEXECUTING_EVIDENCE",
        ],
        {
            "campaign_a": prior_a,
            "campaign_b_run_history": prior_b["run_history"],
            "authoritative_campaign": DEFAULT_CAMPAIGN,
        },
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--campaign-id", default=DEFAULT_CAMPAIGN)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    campaign = workspace / "discovery" / "p0" / "s07" / args.campaign_id
    reports = campaign / "reports"
    report_path = reports / "task6_acceptance.json"
    manifest_path = reports / "artifact_manifest.json"
    require(campaign.is_dir(), f"Campaign does not exist: {campaign}")
    require(report_path.is_file(), f"Acceptance report is missing: {report_path}")
    require(manifest_path.is_file(), f"Artifact manifest is missing: {manifest_path}")

    outputs = {
        "runtime": reports / "runtime_dependency_matrix.json",
        "component": reports / "p0_s07_component_candidate.json",
        "verification": reports / "closeout_verification.json",
        "manifest": reports / "closeout_manifest.json",
    }
    for path in outputs.values():
        require(not path.exists(), f"Closeout output already exists: {path}")

    report = read_json(report_path)
    require(report["campaign_id"] == args.campaign_id, "Campaign ID mismatch")
    manifest_audit = verify_original_manifest(manifest_path, workspace)
    acceptance_checks = verify_acceptance(workspace, campaign, report)

    runtime_matrix = {
        "schema_version": "s07-task6-runtime-matrix.v1",
        "campaign_id": args.campaign_id,
        "generated_at": utc_now(),
        "classification": "NON_PRODUCTION_ACCEPTANCE_HANDOFF",
        "current_profile": {
            "execution": "Windows acceptance workstation",
            "local_search": {
                "tool": "MMseqs2",
                "version": "18-8cc5c",
                "database_release": "wwPDB 2026-08-29",
                "threads": 8,
                "max_results_per_query": 10000,
                "wall_time_seconds": report["resource_measurements"]["local_search"][
                    "wall_time_seconds"
                ],
                "sampled_peak_working_set_bytes": report["resource_measurements"][
                    "local_search"
                ]["peak_working_set_bytes"],
                "tool_reported_estimated_memory_bytes": report[
                    "resource_measurements"
                ]["local_search"]["tool_reported_estimated_memory_bytes"],
            },
            "api": {
                "request_count": report["resource_measurements"]["http"][
                    "request_count"
                ],
                "total_http_wall_time_seconds": report["resource_measurements"][
                    "http"
                ]["total_http_wall_time_seconds"],
                "total_download_bytes": report["resource_measurements"]["http"][
                    "total_download_bytes"
                ],
                "allowlist_hosts": [
                    "search.rcsb.org",
                    "data.rcsb.org",
                    "files.rcsb.org",
                    "rest.uniprot.org",
                    "alphafold.ebi.ac.uk",
                ],
            },
            "python": report["environment"]["python"],
            "python_packages": report["environment"]["packages"],
        },
        "data_and_license_handoff": [
            {
                "asset": "MMseqs2",
                "license": "MIT",
                "acceptance_version": "18-8cc5c",
            },
            {
                "asset": "wwPDB/RCSB PDB data",
                "license": "CC0 1.0",
                "acceptance_release": "2026-08-29",
            },
            {
                "asset": "UniProt data",
                "license": "CC BY 4.0",
                "observed_release": report["o15116_fallback"]["uniprot_release"],
            },
            {
                "asset": "AlphaFold DB data",
                "license": "CC BY 4.0",
                "observed_model_version": report["o15116_fallback"]["model_version"],
            },
        ],
        "production_profile": {
            "status": "NOT_IMPLEMENTED_PENDING_P0_V0_6",
            "target_server_local_databases": "HANDOFF_PENDING_RECEIVING_TEAM",
            "job_state_machine": "OI-017_PENDING",
            "await_cancel_resume": "OI-017_PENDING",
            "per_tool_execution_profiles": "P0_V0_6_PENDING",
        },
        "source": file_reference(report_path, workspace),
    }
    immutable_write(outputs["runtime"], json_bytes(runtime_matrix))

    component_candidate = {
        "schema_version": "p0-s07-component-candidate.v1",
        "component": "S-07_STRUCTURE_ACQUISITION",
        "status": "STAGED_ACCEPTANCE_EVIDENCE_ONLY",
        "deployable": False,
        "production_mode_enabled": False,
        "campaign_id": args.campaign_id,
        "generated_at": utc_now(),
        "acceptance": {
            "task6_nonproduction_acceptance": "PASS",
            "scientific_acceptance": "NOT_RUN",
            "rule_status": "PROVISIONAL_USER_APPROVED_EXPERT_PENDING",
            "checks_passed": 10,
        },
        "implementation_entries": [
            file_reference(workspace / "src/t01_s07_acceptance/backend.py", workspace),
            file_reference(
                workspace / "scripts/run_s07_task6_acceptance.py", workspace
            ),
            file_reference(
                workspace / "scripts/run-s07-task6-windows.ps1", workspace
            ),
            file_reference(
                workspace / "scripts/verify_s07_task6_closeout.py", workspace
            ),
        ],
        "contract_and_handoff_entries": [
            file_reference(
                workspace / "docs/archive/p0/S07_TASK5_RESULT_CONTRACT.md",
                workspace,
            ),
            file_reference(
                workspace
                / "docs/archive/p0/S07_TASK5_RESULT_CONTRACT.schema.json",
                workspace,
            ),
            file_reference(
                workspace
                / "docs/archive/p0/S07_LOCAL_DATA_AND_RUNTIME_PLAN.md",
                workspace,
            ),
            file_reference(
                workspace
                / "docs/archive/p0/S07_EXPERT_CONFIRMATIONS.md",
                workspace,
            ),
            file_reference(
                workspace
                / "docs/archive/p0/S07_TASK6_ACCEPTANCE_AND_HANDOFF.md",
                workspace,
            ),
        ],
        "evidence": {
            "acceptance_report": file_reference(report_path, workspace),
            "original_artifact_manifest": file_reference(manifest_path, workspace),
            "runtime_dependency_matrix": file_reference(outputs["runtime"], workspace),
        },
        "release_gates": report["gate_status"],
        "next_authorized_work": "Rewrite and review P0_IMPLEMENTATION_PLAN.md as v0.6 before production adapter work.",
    }
    immutable_write(outputs["component"], json_bytes(component_candidate))

    # The project documentation links to the two records above.  Create them
    # before running the documentation gate, then append the self-contained
    # verification and closeout manifest after the gate succeeds.
    pytest_result, docs_result = run_validation(workspace, reports)

    verification = {
        "schema_version": "s07-task6-closeout.v1",
        "campaign_id": args.campaign_id,
        "generated_at": utc_now(),
        "status": "PASS",
        "classification": "NON_PRODUCTION_ACCEPTANCE_CLOSEOUT",
        "manifest_audit": manifest_audit,
        "acceptance_checks": acceptance_checks,
        "validation": {"pytest": pytest_result, "documentation": docs_result},
        "appended_records": {
            "runtime_dependency_matrix": file_reference(outputs["runtime"], workspace),
            "p0_s07_component_candidate": file_reference(outputs["component"], workspace),
        },
        "conclusion": {
            "task6": "COMPLETE_NONPRODUCTION_ACCEPTANCE_WITH_RELEASE_GATES",
            "production_deployment_status": "NOT_DEPLOYED",
            "scientific_acceptance": "NOT_RUN",
            "expert_confirmation": "PENDING_5_ITEMS",
            "next_task": "P0_V0_6_IMPLEMENTATION_PLAN_REWRITE_AND_REVIEW",
        },
    }
    immutable_write(outputs["verification"], json_bytes(verification))

    appended = [
        reports / "pytest_results.xml",
        reports / "pytest_output.txt",
        reports / "docs_check_output.txt",
        outputs["runtime"],
        outputs["component"],
        outputs["verification"],
    ]
    closeout_manifest = {
        "schema_version": "s07-task6-closeout-manifest.v1",
        "campaign_id": args.campaign_id,
        "generated_at": utc_now(),
        "scope": "Files appended after the original immutable artifact manifest.",
        "file_count": len(appended),
        "total_bytes": sum(path.stat().st_size for path in appended),
        "files": [file_reference(path, workspace) for path in appended],
    }
    immutable_write(outputs["manifest"], json_bytes(closeout_manifest))
    print(
        json.dumps(
            {
                "status": "PASS",
                "campaign_id": args.campaign_id,
                "tests": pytest_result["tests"],
                "manifest_files_verified": manifest_audit["verified_file_count"],
                "closeout_files": closeout_manifest["file_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
