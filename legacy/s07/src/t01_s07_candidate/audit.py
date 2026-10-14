"""Build a factual S07-D09 output audit from one P0-M1B campaign."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CLASSIFICATION = "NON_PRODUCTION_OUTPUT_AUDIT"
DEPLOYMENT_STATUS = "NOT_DEPLOYED"


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


def _portable(path: Path) -> str:
    return path.as_posix()


def _artifact_type(relative: Path) -> str:
    parts = relative.parts
    name = relative.name
    suffix = relative.suffix.lower()
    if name == "exchange.json":
        return "exchange_record"
    if name in {"campaign.json", "run-summary.json", "runtime-dependencies.json"}:
        return "campaign_metadata"
    if parts and parts[0] == "plan":
        return "audit_plan"
    if parts and parts[0] == "requests":
        return "rcsb_page_request"
    if suffix in {".fasta", ".fa", ".faa"}:
        return "protein_fasta"
    if name == "request.body.json":
        return "captured_http_request"
    if name == "response.headers.txt":
        return "http_response_headers"
    if name == "curl.stderr.txt":
        return "http_transport_stderr"
    if name in {"stdout.txt", "stderr.txt"}:
        return "cli_stream"
    if "rcsb-search" in parts and name == "response.json":
        return "rcsb_search_response"
    if "rcsb-search" in parts and name == "pagination-run.json":
        return "rcsb_pagination_record"
    if "rcsb-materialized" in parts and suffix == ".cif":
        return "rcsb_mmcif"
    if "rcsb-materialized" in parts and name == "response.json":
        parent = relative.parent.name
        return f"rcsb_{parent.replace('-', '_')}_metadata"
    if "afdb" in parts and "metadata" in parts and name == "response.json":
        return "afdb_metadata_response"
    if "afdb" in parts and "model-cif" in parts and suffix == ".cif":
        return "afdb_model_cif"
    if "afdb" in parts and "confidence" in parts and suffix == ".json":
        return "afdb_confidence_json"
    if "afdb" in parts and "pae" in parts and suffix == ".json":
        return "afdb_pae_json"
    if "blast" in parts and suffix == ".asn":
        return "blast_archive"
    if "blast" in parts and suffix == ".tsv":
        return "blast_tabular"
    if "blast" in parts and name == "result.json":
        return "blast_json"
    if suffix == ".json":
        return "other_json"
    if suffix == ".txt":
        return "other_text"
    return "other_binary"


def build_inventory(campaign_root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for path in sorted(campaign_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(campaign_root)
        if relative.parts and relative.parts[0] == "reports":
            continue
        records.append(
            {
                "path": _portable(relative),
                "artifact_type": _artifact_type(relative),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["artifact_type"]].append(record)
    type_summary: list[dict[str, Any]] = []
    for artifact_type, items in sorted(grouped.items()):
        sizes = [int(item["size_bytes"]) for item in items]
        type_summary.append(
            {
                "artifact_type": artifact_type,
                "file_count": len(items),
                "total_size_bytes": sum(sizes),
                "minimum_size_bytes": min(sizes),
                "median_size_bytes": int(statistics.median(sizes)),
                "maximum_size_bytes": max(sizes),
            }
        )
    return {
        "file_count": len(records),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in records),
        "empty_file_count": sum(1 for item in records if item["size_bytes"] == 0),
        "artifact_type_count": len(grouped),
        "artifact_types": type_summary,
        "files": records,
    }


def build_content_duplicate_audit(inventory: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in inventory["files"]:
        if int(record["size_bytes"]) > 0:
            groups[record["sha256"]].append(record)
    duplicates = []
    for sha256, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        duplicates.append(
            {
                "sha256": sha256,
                "size_bytes": items[0]["size_bytes"],
                "copy_count": len(items),
                "paths": [item["path"] for item in items],
            }
        )
    return {
        "scope": "byte-identical non-empty files",
        "duplicate_group_count": len(duplicates),
        "redundant_copy_count": sum(item["copy_count"] - 1 for item in duplicates),
        "groups": duplicates,
        "empty_files_excluded": inventory["empty_file_count"],
    }


def _http_status(exchange_path: Path) -> int | None:
    if not exchange_path.is_file():
        return None
    try:
        exchange = read_json(exchange_path)
    except (json.JSONDecodeError, UnicodeDecodeError):
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


def _entry_id(identifier: str) -> str:
    return identifier.split("_", 1)[0]


def build_rcsb_pagination_audit(campaign_root: Path) -> dict[str, Any]:
    root = campaign_root / "evidence" / "rcsb-search"
    cases: list[dict[str, Any]] = []
    identifier_cases: dict[str, set[str]] = defaultdict(set)
    entry_cases: dict[str, set[str]] = defaultdict(set)
    for case_root in sorted(path for path in root.glob("*") if path.is_dir()):
        case_id = case_root.name
        page_records: list[dict[str, Any]] = []
        all_identifiers: list[str] = []
        totals: list[int] = []
        seen: set[str] = set()
        across_page_duplicate_occurrences = 0
        for page_dir in sorted(path for path in case_root.glob("page-*") if path.is_dir()):
            request_path = page_dir / "request.body.json"
            request = read_json(request_path) if request_path.is_file() else {}
            pagination = request.get("request_options", {}).get("paginate", {})
            response_path = page_dir / "response.json"
            response: dict[str, Any] = {}
            if response_path.is_file() and response_path.stat().st_size:
                try:
                    loaded = read_json(response_path)
                    response = loaded if isinstance(loaded, dict) else {}
                except (json.JSONDecodeError, UnicodeDecodeError):
                    response = {}
            identifiers = [
                str(item.get("identifier"))
                for item in response.get("result_set", [])
                if item.get("identifier") is not None
            ]
            total = response.get("total_count")
            if isinstance(total, int):
                totals.append(total)
            within_duplicates = len(identifiers) - len(set(identifiers))
            for identifier in identifiers:
                if identifier in seen:
                    across_page_duplicate_occurrences += 1
                seen.add(identifier)
                identifier_cases[identifier].add(case_id)
                entry_cases[_entry_id(identifier)].add(case_id)
            all_identifiers.extend(identifiers)
            page_records.append(
                {
                    "page": page_dir.name,
                    "start": pagination.get("start"),
                    "rows_requested": pagination.get("rows"),
                    "http_status": _http_status(page_dir / "exchange.json"),
                    "reported_total_count": total,
                    "result_count": len(identifiers),
                    "within_page_duplicate_occurrences": within_duplicates,
                }
            )
        run_path = case_root / "pagination-run.json"
        run = read_json(run_path) if run_path.is_file() else {}
        reported_total = totals[0] if totals else run.get("reported_total_count")
        entries = [_entry_id(identifier) for identifier in all_identifiers]
        entry_counts = Counter(entries)
        cases.append(
            {
                "case_id": case_id,
                "page_count": len(page_records),
                "page_size": run.get("page_size"),
                "reported_total_count": reported_total,
                "returned_result_count": len(all_identifiers),
                "unique_polymer_entity_count": len(set(all_identifiers)),
                "unique_entry_count": len(set(entries)),
                "polymer_entities_sharing_an_entry_count": sum(
                    count - 1 for count in entry_counts.values() if count > 1
                ),
                "entries_with_multiple_returned_entities": [
                    {"entry_id": entry, "entity_count": count}
                    for entry, count in sorted(entry_counts.items())
                    if count > 1
                ],
                "across_page_duplicate_occurrences": across_page_duplicate_occurrences,
                "reported_total_changed_between_pages": len(set(totals)) > 1,
                "stop_reason": run.get("stop_reason"),
                "audit_guard_reached": run.get("stop_reason") == "MAX_PAGE_GUARD_REACHED",
                "all_reported_results_captured": (
                    isinstance(reported_total, int)
                    and len(all_identifiers) >= reported_total
                    and across_page_duplicate_occurrences == 0
                ),
                "pages": page_records,
            }
        )
    cross_case_entities = [
        {"identifier": identifier, "case_ids": sorted(case_ids)}
        for identifier, case_ids in sorted(identifier_cases.items())
        if len(case_ids) > 1
    ]
    cross_case_entries = [
        {"entry_id": entry, "case_ids": sorted(case_ids)}
        for entry, case_ids in sorted(entry_cases.items())
        if len(case_ids) > 1
    ]
    return {
        "cases": cases,
        "case_count": len(cases),
        "total_page_count": sum(item["page_count"] for item in cases),
        "cross_case_polymer_entity_overlap_count": len(cross_case_entities),
        "cross_case_polymer_entity_overlaps": cross_case_entities,
        "cross_case_entry_overlap_count": len(cross_case_entries),
        "cross_case_entry_overlaps": cross_case_entries,
        "deduplication_decision_made": False,
    }


def _response_body_files(root: Path) -> Iterable[Path]:
    excluded = {
        "exchange.json",
        "request.body.json",
        "response.headers.txt",
        "curl.stderr.txt",
        "stdout.txt",
        "stderr.txt",
    }
    return (path for path in sorted(root.rglob("*")) if path.is_file() and path.name not in excluded)


def build_materialization_audit(campaign_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    root = campaign_root / "evidence" / "rcsb-materialized"
    probes: list[dict[str, Any]] = []
    for item in plan.get("rcsb_materialization_probes", []):
        probe_root = root / item["case_id"] / item["probe_id"]
        bodies = [
            {
                "path": _portable(path.relative_to(campaign_root)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in _response_body_files(probe_root)
        ] if probe_root.is_dir() else []
        statuses = {
            path.parent.name: _http_status(path)
            for path in sorted(probe_root.rglob("exchange.json"))
        } if probe_root.is_dir() else {}
        probes.append(
            {
                "probe_id": item["probe_id"],
                "case_id": item["case_id"],
                "entry_id": item["entry_id"],
                "entity_id": item["entity_id"],
                "chain_id": item["chain_id"],
                "frozen_probe_not_a_selection": True,
                "response_body_count": len(bodies),
                "response_body_total_size_bytes": sum(body["size_bytes"] for body in bodies),
                "http_status_by_kind": statuses,
                "response_bodies": bodies,
            }
        )
    return {
        "probe_count": len(probes),
        "response_body_count": sum(item["response_body_count"] for item in probes),
        "response_body_total_size_bytes": sum(
            item["response_body_total_size_bytes"] for item in probes
        ),
        "probes": probes,
    }


def build_afdb_audit(campaign_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    root = campaign_root / "evidence" / "afdb"
    cases: list[dict[str, Any]] = []
    for item in plan.get("afdb_queries", []):
        item_root = root / item["case_id"] / item["accession"]
        metadata_path = item_root / "metadata" / "response.json"
        metadata: Any = None
        if metadata_path.is_file() and metadata_path.stat().st_size:
            try:
                metadata = read_json(metadata_path)
            except (json.JSONDecodeError, UnicodeDecodeError):
                metadata = None
        model = metadata[0] if isinstance(metadata, list) and metadata else None
        bodies = [
            {
                "path": _portable(path.relative_to(campaign_root)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in _response_body_files(item_root)
        ] if item_root.is_dir() else []
        cases.append(
            {
                "case_id": item["case_id"],
                "queried_identifier": item["accession"],
                "identifier_was_explicit_not_inferred": True,
                "metadata_http_status": _http_status(item_root / "metadata" / "exchange.json"),
                "metadata_shape": (
                    "MODEL_LIST" if isinstance(metadata, list) else "OBJECT_OR_ERROR"
                    if isinstance(metadata, dict) else "EMPTY_OR_UNPARSEABLE"
                ),
                "model_entity_id": model.get("modelEntityId") if isinstance(model, dict) else None,
                "latest_version": model.get("latestVersion") if isinstance(model, dict) else None,
                "response_body_count": len(bodies),
                "response_body_total_size_bytes": sum(body["size_bytes"] for body in bodies),
                "response_bodies": bodies,
            }
        )
    return {"case_count": len(cases), "cases": cases}


def _count_tsv_hits(path: Path) -> int | None:
    if not path.is_file():
        return None
    return sum(
        1
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip() and not line.startswith("#")
    )


def _file_fact(campaign_root: Path, path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return {
        "path": _portable(path.relative_to(campaign_root)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_blast_audit(campaign_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    profile_path = campaign_root / "inputs" / "blast" / "discovery-profile.json"
    profile = read_json(profile_path) if profile_path.is_file() else {}
    cap = profile.get("search_parameters", {}).get("max_target_seqs")
    cases: list[dict[str, Any]] = []
    for item in plan.get("blast", {}).get("cases", []):
        root = campaign_root / "evidence" / "blast" / item["case_id"]
        archive_path = root / "search" / "result.asn"
        tabular_path = root / "format-tabular" / "result.tsv"
        json_path = root / "format-json" / "result.json"
        hit_count = _count_tsv_hits(tabular_path)
        cases.append(
            {
                "case_id": item["case_id"],
                "tabular_hit_count": hit_count,
                "discovery_profile_cap": cap,
                "cap_was_reached": (
                    isinstance(hit_count, int) and isinstance(cap, int) and hit_count >= cap
                ),
                "cap_is_production_default": False,
                "search_exit_code": (
                    read_json(root / "search" / "exchange.json").get("exit_code")
                    if (root / "search" / "exchange.json").is_file()
                    else None
                ),
                "archive": _file_fact(campaign_root, archive_path),
                "tabular": _file_fact(campaign_root, tabular_path),
                "json": _file_fact(campaign_root, json_path),
            }
        )
    return {
        "profile_id": profile.get("profile_id"),
        "profile_classification": profile.get("classification"),
        "production_approved": profile.get("production_approved"),
        "case_count": len(cases),
        "cases": cases,
    }


def build_exchange_audit(campaign_root: Path) -> dict[str, Any]:
    outcomes: Counter[str] = Counter()
    integrity_issues: list[dict[str, str]] = []
    exchange_paths = sorted((campaign_root / "evidence").rglob("exchange.json"))
    for path in exchange_paths:
        relative = _portable(path.relative_to(campaign_root))
        try:
            exchange = read_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError):
            outcomes["UNPARSEABLE_EXCHANGE"] += 1
            integrity_issues.append({"path": relative, "issue": "exchange record is not valid JSON"})
            continue
        if exchange.get("production_deployment_status") != DEPLOYMENT_STATUS:
            integrity_issues.append({"path": relative, "issue": "deployment boundary is missing or wrong"})
        if not exchange.get("started_at") or not exchange.get("finished_at"):
            integrity_issues.append({"path": relative, "issue": "timestamps are incomplete"})
        if "curl" in exchange:
            curl_exit = exchange.get("curl", {}).get("exit_code")
            status = _http_status(path)
            if curl_exit not in (0, None):
                outcomes["HTTP_TRANSPORT_FAILURE"] += 1
            elif status == 204:
                outcomes["HTTP_NO_CONTENT"] += 1
            elif isinstance(status, int) and status >= 400:
                outcomes["HTTP_ERROR_RESPONSE"] += 1
            elif isinstance(status, int) and 200 <= status < 300:
                outcomes["HTTP_SUCCESS"] += 1
            else:
                outcomes["HTTP_STATUS_UNKNOWN"] += 1
            response = exchange.get("response", {})
            if response.get("body_file") and not response.get("body_sha256"):
                integrity_issues.append({"path": relative, "issue": "response body hash is missing"})
        else:
            exit_code = exchange.get("exit_code")
            if exchange.get("timed_out"):
                outcomes["CLI_TIMEOUT"] += 1
            elif exit_code == 0:
                outcomes["CLI_SUCCESS"] += 1
            else:
                outcomes["CLI_FAILURE"] += 1
            for stream in ("stdout", "stderr"):
                if not exchange.get(stream, {}).get("sha256"):
                    integrity_issues.append({"path": relative, "issue": f"{stream} hash is missing"})
    return {
        "exchange_count": len(exchange_paths),
        "outcome_counts": dict(sorted(outcomes.items())),
        "integrity_issue_count": len(integrity_issues),
        "integrity_issues": integrity_issues,
    }


def _size_text(value: int | None) -> str:
    if value is None:
        return "—"
    units = ["B", "KiB", "MiB", "GiB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{value} B"


def _render_markdown(audit: dict[str, Any]) -> str:
    inventory = audit["inventory"]
    pagination = audit["rcsb_pagination"]
    duplicates = audit["content_duplicates"]
    lines = [
        "# P0-M1B：S-07 真实输出审计",
        "",
        f"> 审计批次：`{audit['campaign_id']}`  ",
        f"> 生成时间：{audit['generated_at']}  ",
        "> 性质：非生产取证；未部署；不包含结构分类、可用性判断、候选选择或流程路由。",
        "",
        "## 1. 这次审计解决什么问题",
        "",
        "此前无法确认 S07-D09，是因为还不知道候选工具一次真实运行会产生多少文件、文件有多大、",
        "分页结果怎样展开，以及 entry、polymer entity、chain 和不同查询之间会出现哪些重复。",
        "本批次只把这些事实保存下来，供下一轮讨论；它不替算法负责人决定任何科学规则。",
        "",
        "## 2. 实际产生的文件",
        "",
        f"审计清单共统计 **{inventory['file_count']} 个非报告文件**，合计 **{_size_text(inventory['total_size_bytes'])}**，",
        f"识别出 **{inventory['artifact_type_count']} 类文件**；其中空文件 {inventory['empty_file_count']} 个，",
        "主要来自正常无 stderr/stdout 的调用记录。",
        "",
        "| 文件类别 | 数量 | 合计大小 | 单文件中位数 | 最大文件 |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in inventory["artifact_types"]:
        lines.append(
            "| {artifact_type} | {file_count} | {total} | {median} | {maximum} |".format(
                artifact_type=item["artifact_type"],
                file_count=item["file_count"],
                total=_size_text(item["total_size_bytes"]),
                median=_size_text(item["median_size_bytes"]),
                maximum=_size_text(item["maximum_size_bytes"]),
            )
        )
    lines.extend(
        [
            "",
            "## 3. RCSB 分页事实",
            "",
            "| 样本 | 报告总数 | 实收条目 | 页数 | 唯一 entity | 唯一 entry | 结束原因 |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in pagination["cases"]:
        lines.append(
            "| {case_id} | {reported} | {returned} | {pages} | {entities} | {entries} | {reason} |".format(
                case_id=item["case_id"],
                reported=item["reported_total_count"] if item["reported_total_count"] is not None else "—",
                returned=item["returned_result_count"],
                pages=item["page_count"],
                entities=item["unique_polymer_entity_count"],
                entries=item["unique_entry_count"],
                reason=item["stop_reason"] or "—",
            )
        )
    lines.extend(
        [
            "",
            f"跨样本重复出现的 polymer entity 有 {pagination['cross_case_polymer_entity_overlap_count']} 个，",
            f"跨样本重复出现的 PDB entry 有 {pagination['cross_case_entry_overlap_count']} 个。",
            "这些数字说明“查询结果去重”不是简单删除重复文件：entity 和 entry 是不同层级，",
            "同一 entry 还可能包含多个 entity。这里仅记录现象，没有确定正式去重键。",
            "",
            "## 4. 文件重复事实",
            "",
            f"排除空文件后，共发现 {duplicates['duplicate_group_count']} 组字节完全相同的文件，",
            f"对应 {duplicates['redundant_copy_count']} 个重复副本。字节重复只说明内容相同，",
            "不代表这些文件在业务上可以合并；请求来源、对象层级和运行批次仍需保留。",
            "",
            "## 5. 结构与其他来源的输出组成",
            "",
            f"RCSB 的 {audit['rcsb_materialization']['probe_count']} 个冻结观察对象共产生 "
            f"{audit['rcsb_materialization']['response_body_count']} 个响应正文，合计 "
            f"{_size_text(audit['rcsb_materialization']['response_body_total_size_bytes'])}。",
            f"AlphaFold DB 检查了 {audit['afdb']['case_count']} 个明确给出的标识；",
            f"本地 BLAST 检查了 {audit['blast']['case_count']} 个样本，并同时保留原始归档、表格和 JSON（存在时）。",
            "这些观察对象来自已冻结的 P0-M1 代表样本，只用于查看输出组成，不表示本次工具选中了它们。",
            "",
            "## 6. 可追溯性现状与缺口",
            "",
            f"共检查 {audit['exchanges']['exchange_count']} 条 HTTP/CLI 调用记录，发现 "
            f"{audit['exchanges']['integrity_issue_count']} 个记录完整性问题。每个非报告文件都已进入",
            "清单并计算 SHA-256。BLAST 使用的程序、数据库文件和 discovery profile 另有依赖清单。",
            "",
            "目前仍有两个明确缺口：",
            "",
            "- RCSB 与 AlphaFold DB 是在线可变数据源。本批次保存了请求、响应、时间和哈希，但没有冻结整个远端数据库版本。",
            "- 只对 4 个预先冻结的代表对象下载了完整结构元数据与坐标文件，并未为每个搜索命中都下载结构文件。",
            "",
            "## 7. 回到 S07-D09 时需要确认什么",
            "",
            "现在已有证据可以逐项讨论以下问题：",
            "",
            "1. 主结果中保留哪些轻量候选信息，哪些原始分页响应和大文件只通过产物引用提供。",
            "2. entity、entry、chain/model/assembly 是否需要分别建立身份键，而不是使用一个全局去重键。",
            "3. 一次查询快照至少保存哪些请求、分页、来源时间、数据库/工具版本和文件哈希。",
            "4. 分页对调用方采用哪种机制，以及审计保护上限与正式生产上限如何分开管理。",
            "",
            "在这些事项由 wing 评审确认前，本报告不把任何候选方案写成正式契约。D11-D17 仍等待",
            "算法/产品负责人反馈，因此本批次也不能进入 P0-M2 生产编码。",
            "",
            "## 8. 机器可读证据",
            "",
            "- `artifact_inventory.json`：逐文件路径、类型、大小与 SHA-256。",
            "- `output_audit.json`：分页、层级重复、来源输出、BLAST 和调用完整性摘要。",
            "- `report_build_manifest.json`：生成本报告的代码文件、Python 环境、大小与 SHA-256。",
            "- 原始请求与响应位于本批次的 `requests/` 与 `evidence/` 目录。",
            "",
        ]
    )
    return "\n".join(lines)


def build_report_code_manifest(campaign_root: Path) -> dict[str, Any]:
    workspace = Path(__file__).resolve().parents[2]
    relative_paths = [
        "src/t01_s07_candidate/__init__.py",
        "src/t01_s07_candidate/runner.py",
        "src/t01_s07_candidate/audit.py",
        "scripts/capture_http_evidence.py",
        "scripts/capture_cli_evidence.py",
        "scripts/run_p0_s07_m1b.py",
        "scripts/build_p0_s07_m1b_audit.py",
        "scripts/run-p0-s07-m1b-windows.ps1",
    ]
    files = []
    for relative in relative_paths:
        path = workspace / relative
        if path.is_file():
            files.append(
                {
                    "workspace_relative_path": relative,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    plan_path = campaign_root / "plan" / "plan.json"
    return {
        "classification": CLASSIFICATION,
        "production_deployment_status": DEPLOYMENT_STATUS,
        "generated_at": utc_now(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "campaign_plan": {
            "path": "plan/plan.json",
            "size_bytes": plan_path.stat().st_size,
            "sha256": sha256_file(plan_path),
        },
        "source_file_count": len(files),
        "source_files": files,
    }


def build_output_audit(campaign_root: Path) -> dict[str, Any]:
    """Build JSON and human-readable reports without calling any source."""

    campaign_root = campaign_root.resolve()
    campaign = read_json(campaign_root / "campaign.json")
    plan = read_json(campaign_root / "plan" / "plan.json")
    if campaign.get("production_deployment_status") != DEPLOYMENT_STATUS:
        raise ValueError("campaign is not marked NOT_DEPLOYED")
    if plan.get("classification") != CLASSIFICATION:
        raise ValueError("campaign plan is not a P0-M1B output audit")
    inventory = build_inventory(campaign_root)
    code_manifest = build_report_code_manifest(campaign_root)
    audit = {
        "campaign_id": campaign["campaign_id"],
        "classification": CLASSIFICATION,
        "production_deployment_status": DEPLOYMENT_STATUS,
        "generated_at": utc_now(),
        "decision_scope": "S07-D09 evidence only",
        "boundary": {
            "contains_scientific_decisions": False,
            "contains_structure_selection": False,
            "contains_workflow_route": False,
            "connected_to_mcp_or_workflow": False,
            "production_defaults_approved": False,
        },
        "run": {
            "execution_status": campaign.get("execution_status"),
            "started_at": campaign.get("started_at"),
            "finished_at": campaign.get("finished_at"),
            "capture_count": campaign.get("capture_count"),
            "capture_process_failure_count": campaign.get("capture_process_failure_count"),
        },
        "inventory": {key: value for key, value in inventory.items() if key != "files"},
        "content_duplicates": build_content_duplicate_audit(inventory),
        "rcsb_pagination": build_rcsb_pagination_audit(campaign_root),
        "rcsb_materialization": build_materialization_audit(campaign_root, plan),
        "afdb": build_afdb_audit(campaign_root, plan),
        "blast": build_blast_audit(campaign_root, plan),
        "exchanges": build_exchange_audit(campaign_root),
        "traceability_gaps": [
            {
                "gap": "REMOTE_DATABASE_RELEASE_NOT_FROZEN",
                "applies_to": ["RCSB", "AlphaFold DB"],
                "available_evidence": "request, response, retrieval timestamps, URL, headers, and SHA-256",
            },
            {
                "gap": "FULL_CANDIDATE_MATERIALIZATION_NOT_PERFORMED",
                "applies_to": ["RCSB search result set"],
                "available_evidence": "complete search pages plus four frozen output-composition probes",
            },
        ],
        "d09_review_topics": [
            "main result versus artifact references",
            "identity keys at entity/entry/chain/model/assembly levels",
            "query snapshot contents and source version evidence",
            "pagination contract and separation of safety guards from production limits",
        ],
        "report_builder": {
            "manifest": "reports/report_build_manifest.json",
            "source_file_count": code_manifest["source_file_count"],
        },
    }
    reports = campaign_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    inventory_report = {
        "campaign_id": campaign["campaign_id"],
        "classification": CLASSIFICATION,
        "production_deployment_status": DEPLOYMENT_STATUS,
        **inventory,
    }
    write_json(reports / "artifact_inventory.json", inventory_report)
    write_json(reports / "report_build_manifest.json", code_manifest)
    write_json(reports / "output_audit.json", audit)
    (reports / "P0_M1B_OUTPUT_AUDIT.md").write_text(
        _render_markdown(audit), encoding="utf-8"
    )
    return audit
