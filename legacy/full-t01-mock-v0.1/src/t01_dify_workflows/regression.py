"""Master-level Dify regression helpers for the 25 deterministic Mock scenarios.

The runner deliberately treats Dify as the orchestration engine.  It submits
inputs to Dify's Workflow Service API and can collect local Dify trace records
from PostgreSQL afterwards.  No scientific result is calculated here.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from t01_mock_mcp.catalog import SCENARIOS


MASTER_NAME = "T01_Master_v10"
CAMPAIGN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_expectations(path: Path) -> dict[str, Any]:
    document = read_json(path)
    defaults = document.get("defaults", {})
    profiles = document.get("profiles", {})
    cases = document.get("cases", [])
    if document.get("workflow_name") != MASTER_NAME:
        raise ValueError(f"expected workflow_name={MASTER_NAME!r}")
    if not isinstance(profiles, dict) or not isinstance(cases, list):
        raise ValueError("expectation file must contain profiles and cases")

    scenario_ids = [case.get("scenario_id") for case in cases]
    if scenario_ids != list(SCENARIOS):
        raise ValueError("expectation scenario order must exactly match SCENARIOS")

    expanded: list[dict[str, Any]] = []
    list_fields = ("required_nodes", "forbidden_nodes", "assertions")
    for case in cases:
        profile_name = case.get("profile")
        if profile_name not in profiles:
            raise ValueError(f"unknown profile for {case.get('scenario_id')}: {profile_name}")
        profile = profiles[profile_name]
        merged = deepcopy(defaults)
        for key, value in profile.items():
            if key in list_fields:
                merged[key] = [*defaults.get(key, []), *value]
            else:
                merged[key] = deepcopy(value)
        for key, value in case.items():
            if key in list_fields:
                merged[key] = [*merged.get(key, []), *value]
            else:
                merged[key] = deepcopy(value)
        for key in list_fields:
            merged.setdefault(key, [])
        expanded.append(merged)

    return {
        **{
            key: value
            for key, value in document.items()
            if key not in {"defaults", "profiles", "cases"}
        },
        "defaults": defaults,
        "profiles": profiles,
        "cases": expanded,
    }


def build_manifest(
    expectations: Mapping[str, Any],
    base_input: Mapping[str, Any],
    campaign: str,
) -> dict[str, Any]:
    if not CAMPAIGN_RE.fullmatch(campaign):
        raise ValueError(
            "campaign must start with an ASCII letter/digit and contain only "
            "letters, digits, dot, underscore, or hyphen (max 80 chars)"
        )

    cases: list[dict[str, Any]] = []
    for index, expected in enumerate(expectations["cases"], start=1):
        run_id = f"{campaign}-{index:02d}"
        if not RUN_ID_RE.fullmatch(run_id):
            raise ValueError(f"generated invalid run_id: {run_id}")
        scenario_id = expected["scenario_id"]
        cases.append(
            {
                "index": index,
                "run_id": run_id,
                "scenario_id": scenario_id,
                "inputs": {
                    "run_id": run_id,
                    "scenario_id": scenario_id,
                    "t01_input_json": json.dumps(
                        base_input, ensure_ascii=False, separators=(",", ":")
                    ),
                    "execution_mode": "mock",
                },
                "expected": expected,
            }
        )

    return {
        "schema_version": "0.1.0",
        "workflow_name": MASTER_NAME,
        "campaign": campaign,
        "generated_at": utc_now(),
        "case_count": len(cases),
        "cases": cases,
    }


def write_batch_csv(path: Path, manifest: Mapping[str, Any]) -> None:
    """Write a UTF-8-BOM CSV matching the four Master Start variables."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["run_id", "scenario_id", "t01_input_json", "execution_mode"],
        )
        writer.writeheader()
        for case in manifest["cases"]:
            writer.writerow(case["inputs"])


def prepare_campaign(
    *,
    expectations_path: Path,
    base_input_path: Path,
    campaign: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    expectations = load_expectations(expectations_path)
    base_input = read_json(base_input_path)
    manifest = build_manifest(expectations, base_input, campaign)
    manifest_path = output_dir / "manifest.json"
    csv_path = output_dir / "inputs.csv"
    write_json(manifest_path, manifest)
    write_batch_csv(csv_path, manifest)
    return manifest_path, csv_path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
    return records


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def _write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(value, ensure_ascii=False, separators=(",", ":")) for value in values]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def invoke_workflow(
    *,
    base_url: str,
    api_key: str,
    inputs: Mapping[str, Any],
    user: str,
    timeout: float,
) -> tuple[int, Any]:
    body = json.dumps(
        {"inputs": inputs, "response_mode": "blocking", "user": user},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/workflows/run",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload)
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"raw": payload}
        return exc.code, parsed


def run_campaign(
    *,
    manifest_path: Path,
    results_path: Path,
    base_url: str,
    api_key: str,
    user: str = "t01-master-regression",
    timeout: float = 180.0,
    resume: bool = True,
) -> list[dict[str, Any]]:
    manifest = read_json(manifest_path)
    existing = _read_jsonl(results_path) if resume else []
    completed = {record["run_id"] for record in existing}
    if not resume and results_path.exists():
        results_path.unlink()

    for case in manifest["cases"]:
        if case["run_id"] in completed:
            continue
        started_at = utc_now()
        try:
            http_status, response = invoke_workflow(
                base_url=base_url,
                api_key=api_key,
                inputs=case["inputs"],
                user=user,
                timeout=timeout,
            )
            record = {
                "run_id": case["run_id"],
                "scenario_id": case["scenario_id"],
                "started_at": started_at,
                "finished_at": utc_now(),
                "http_status": http_status,
                "response": response,
            }
        except Exception as exc:  # Preserve evidence and continue the campaign.
            record = {
                "run_id": case["run_id"],
                "scenario_id": case["scenario_id"],
                "started_at": started_at,
                "finished_at": utc_now(),
                "http_status": None,
                "response": None,
                "runner_error": f"{type(exc).__name__}: {exc}",
            }
        _append_jsonl(results_path, record)

    return _read_jsonl(results_path)


def _sql_literal_list(values: Iterable[str]) -> str:
    checked = []
    for value in values:
        if not RUN_ID_RE.fullmatch(value):
            raise ValueError(f"unsafe or invalid run_id for trace query: {value!r}")
        checked.append("'" + value.replace("'", "''") + "'")
    if not checked:
        raise ValueError("at least one run_id is required")
    return ",".join(checked)


def _psql_json_lines(
    sql: str,
    *,
    docker_bin: str,
    db_container: str,
    db_user: str,
    db_name: str,
) -> list[dict[str, Any]]:
    command = [
        docker_bin,
        "exec",
        db_container,
        "psql",
        "-XqAt",
        "-U",
        db_user,
        "-d",
        db_name,
        "-c",
        sql,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]


def _collect_local_trace_records(
    run_ids: Sequence[str],
    *,
    docker_bin: str,
    db_container: str,
    db_user: str,
    db_name: str,
) -> list[dict[str, Any]]:
    literals = _sql_literal_list(run_ids)

    runs_sql = f"""
SELECT json_build_object(
  'kind', 'workflow_run',
  'logical_run_id', wr.inputs::jsonb ->> 'run_id',
  'workflow_run_id', wr.id::text,
  'app_name', a.name,
  'app_id', wr.app_id::text,
  'status', wr.status,
  'triggered_from', wr.triggered_from,
  'outputs', CASE WHEN COALESCE(wr.outputs, '') = '' THEN NULL ELSE wr.outputs::jsonb END,
  'error', wr.error,
  'total_steps', wr.total_steps,
  'created_at', wr.created_at,
  'finished_at', wr.finished_at
)::text
FROM workflow_runs wr
JOIN apps a ON a.id = wr.app_id
WHERE wr.inputs::jsonb ->> 'run_id' IN ({literals})
ORDER BY wr.created_at, a.name;
"""
    nodes_sql = f"""
SELECT json_build_object(
  'kind', 'node_execution',
  'logical_run_id', wr.inputs::jsonb ->> 'run_id',
  'workflow_run_id', wr.id::text,
  'app_name', a.name,
  'node_index', ne.index,
  'node_id', ne.node_id,
  'title', ne.title,
  'node_type', ne.node_type,
  'status', ne.status,
  'outputs', CASE WHEN COALESCE(ne.outputs, '') = '' THEN NULL ELSE ne.outputs::jsonb END,
  'error', ne.error,
  'elapsed_time', ne.elapsed_time,
  'created_at', ne.created_at,
  'finished_at', ne.finished_at
)::text
FROM workflow_node_executions ne
JOIN workflow_runs wr ON wr.id = ne.workflow_run_id
JOIN apps a ON a.id = wr.app_id
WHERE wr.inputs::jsonb ->> 'run_id' IN ({literals})
ORDER BY wr.created_at, ne.index;
"""
    return [
        *_psql_json_lines(
            runs_sql,
            docker_bin=docker_bin,
            db_container=db_container,
            db_user=db_user,
            db_name=db_name,
        ),
        *_psql_json_lines(
            nodes_sql,
            docker_bin=docker_bin,
            db_container=db_container,
            db_user=db_user,
            db_name=db_name,
        ),
    ]


def _trace_document(run_ids: Sequence[str], records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "collected_at": utc_now(),
        "run_ids": list(run_ids),
        "records": list(records),
    }


def collect_local_traces(
    *,
    results_path: Path,
    traces_path: Path,
    docker_bin: str = "docker",
    db_container: str = "docker-db_postgres-1",
    db_user: str = "postgres",
    db_name: str = "dify",
) -> dict[str, Any]:
    results = _read_jsonl(results_path)
    run_ids = [record["run_id"] for record in results]
    records = _collect_local_trace_records(
        run_ids,
        docker_bin=docker_bin,
        db_container=db_container,
        db_user=db_user,
        db_name=db_name,
    )
    document = _trace_document(run_ids, records)
    write_json(traces_path, document)
    return document


def build_editor_result_records(
    manifest: Mapping[str, Any],
    trace_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build API-shaped results for runs launched from Dify's editor.

    The editor does not return a Workflow Service API response to this script,
    so the authoritative top-level status and output are read from Dify's local
    PostgreSQL trace.  Only completed Master records are emitted; unrun cases
    remain absent and are reported as such by the evaluator.
    """

    latest_master_by_run: dict[str, Mapping[str, Any]] = {}
    for record in trace_records:
        if record.get("kind") != "workflow_run" or record.get("app_name") != MASTER_NAME:
            continue
        logical_run_id = record.get("logical_run_id")
        if isinstance(logical_run_id, str):
            latest_master_by_run[logical_run_id] = record

    result_records: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        run_id = case["run_id"]
        master = latest_master_by_run.get(run_id)
        if master is None or master.get("finished_at") is None:
            continue
        result_records.append(
            {
                "run_id": run_id,
                "scenario_id": case["scenario_id"],
                "started_at": master.get("created_at"),
                "finished_at": master.get("finished_at"),
                "http_status": None,
                "source": "dify_editor_database",
                "response": {
                    "data": {
                        "workflow_run_id": master.get("workflow_run_id"),
                        "status": master.get("status"),
                        "outputs": master.get("outputs"),
                        "error": master.get("error"),
                    }
                },
            }
        )
    return result_records


def collect_local_editor_campaign(
    *,
    manifest_path: Path,
    results_path: Path,
    traces_path: Path,
    docker_bin: str = "docker",
    db_container: str = "docker-db_postgres-1",
    db_user: str = "postgres",
    db_name: str = "dify",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collect results and traces for runs launched through Dify's editor UI."""

    manifest = read_json(manifest_path)
    run_ids = [case["run_id"] for case in manifest["cases"]]
    records = _collect_local_trace_records(
        run_ids,
        docker_bin=docker_bin,
        db_container=db_container,
        db_user=db_user,
        db_name=db_name,
    )
    results = build_editor_result_records(manifest, records)
    document = _trace_document(run_ids, records)
    _write_jsonl(results_path, results)
    write_json(traces_path, document)
    return results, document


def get_path(value: Any, path: str) -> Any:
    current = value
    if not path:
        return current
    for segment in path.split("."):
        if isinstance(current, list):
            current = current[int(segment)]
        elif isinstance(current, dict):
            current = current[segment]
        else:
            raise KeyError(path)
    return current


def _workflow_status(response_record: Mapping[str, Any] | None) -> str | None:
    if not response_record:
        return None
    response = response_record.get("response")
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, dict):
        return data.get("status")
    return response.get("status")


def evaluate_campaign(
    *,
    manifest: Mapping[str, Any],
    result_records: Sequence[Mapping[str, Any]],
    trace_document: Mapping[str, Any] | None,
    require_trace: bool = True,
) -> dict[str, Any]:
    results_by_run = {record["run_id"]: record for record in result_records}
    trace_records = list(trace_document.get("records", [])) if trace_document else []

    report_cases = []
    for case in manifest["cases"]:
        run_id = case["run_id"]
        expected = case["expected"]
        response_record = results_by_run.get(run_id)
        actual_status = _workflow_status(response_record)
        issues: list[str] = []

        if response_record is None:
            issues.append("没有 API 运行记录")
        elif response_record.get("runner_error"):
            issues.append(response_record["runner_error"])
        if actual_status != expected.get("expected_workflow_status"):
            issues.append(
                f"顶层状态期望 {expected.get('expected_workflow_status')}，实际 {actual_status}"
            )

        case_traces = [record for record in trace_records if record.get("logical_run_id") == run_id]
        node_records = [record for record in case_traces if record.get("kind") == "node_execution"]
        node_map = {
            f"{record.get('app_name')}::{record.get('node_id')}": record
            for record in node_records
        }

        if require_trace and not case_traces:
            issues.append("没有本地 Dify 追踪证据")
        if case_traces:
            for node_key in expected.get("required_nodes", []):
                if node_key not in node_map:
                    issues.append(f"缺少必经节点 {node_key}")
            for node_key in expected.get("forbidden_nodes", []):
                if node_key in node_map:
                    issues.append(f"出现不应执行的节点 {node_key}")
            for assertion in expected.get("assertions", []):
                node_key = assertion["node"]
                record = node_map.get(node_key)
                if record is None:
                    issues.append(f"断言节点不存在 {node_key}")
                    continue
                try:
                    actual = get_path(record, assertion["path"])
                except (KeyError, IndexError, ValueError, TypeError):
                    issues.append(f"断言路径不存在 {node_key}:{assertion['path']}")
                    continue
                if actual != assertion.get("equals"):
                    issues.append(
                        f"{node_key}:{assertion['path']} 期望 {assertion.get('equals')!r}，实际 {actual!r}"
                    )

        report_cases.append(
            {
                "index": case["index"],
                "run_id": run_id,
                "scenario_id": case["scenario_id"],
                "expected_behavior": expected.get("expected_behavior"),
                "actual_workflow_status": actual_status,
                "trace_workflow_count": sum(
                    record.get("kind") == "workflow_run" for record in case_traces
                ),
                "trace_node_count": len(node_records),
                "verdict": "PASS" if not issues else "FAIL",
                "issues": issues,
            }
        )

    passed = sum(case["verdict"] == "PASS" for case in report_cases)
    return {
        "schema_version": "0.1.0",
        "workflow_name": manifest["workflow_name"],
        "campaign": manifest["campaign"],
        "generated_at": utc_now(),
        "summary": {
            "total": len(report_cases),
            "passed": passed,
            "failed": len(report_cases) - passed,
        },
        "cases": report_cases,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# T01 Master 回归报告：{report['campaign']}",
        "",
        f"- 工作流：`{report['workflow_name']}`",
        f"- 场景：{summary['total']}",
        f"- 通过：{summary['passed']}",
        f"- 失败：{summary['failed']}",
        f"- 生成时间：{report['generated_at']}",
        "",
        "| # | 场景 | run_id | Dify 状态 | 追踪节点 | 判定 | 说明 |",
        "|---:|---|---|---|---:|---|---|",
    ]
    for case in report["cases"]:
        issue_text = "；".join(case["issues"]) if case["issues"] else case["expected_behavior"]
        issue_text = str(issue_text).replace("|", "\\|").replace("\n", " ")
        lines.append(
            "| {index} | `{scenario_id}` | `{run_id}` | {status} | {nodes} | "
            "{verdict} | {issues} |".format(
                index=case["index"],
                scenario_id=case["scenario_id"],
                run_id=case["run_id"],
                status=case["actual_workflow_status"] or "—",
                nodes=case["trace_node_count"],
                verdict=case["verdict"],
                issues=issue_text,
            )
        )
    lines.append("")
    lines.append("> 本报告只验证 Mock 契约和 Dify 路由，不代表真实科学计算已部署或通过验收。")
    lines.append("")
    return "\n".join(lines)
