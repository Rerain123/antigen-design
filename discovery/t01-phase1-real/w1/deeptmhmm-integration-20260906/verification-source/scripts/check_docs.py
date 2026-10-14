"""Validate document navigation and known stale entry-point claims, read-only."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".uv-cache",
    ".uv-python",
    ".venv",
    "__pycache__",
    ".tmp",
    "_generated-cache-20260904",
    "工具部署",
    # Current doctor-delivered authoritative package. Its prose uses bracket/parenthesis
    # scientific notation that resembles Markdown links. Keep the originals
    # byte-for-byte and validate their presence through 01-业务依据/README.md.
    "抗原智能体_v10.5_修订版_20260902",
}
LOCAL_LINK_RE = re.compile(r"!?\[[^\]]*\]\((<[^>\n]+>|[^)\n]+)\)")
REMOTE_PREFIXES = ("http://", "https://", "mailto:", "data:", "app://")

REQUIRED_DOCUMENTS = (
    "README.md",
    "AGENTS.md",
    "docs/README.md",
    "docs/project/ARCHITECTURE.md",
    "docs/project/STATUS.md",
    "docs/project/PHASE1_SCOPE_REBASELINE.md",
    "docs/project/PHASE1_DELIVERY_PLAN.md",
    "docs/project/ROADMAP.md",
    "docs/project/DECISIONS.md",
    "docs/project/DEFERRED_ITEMS.md",
    "docs/project/OPEN_ITEMS.md",
    "docs/project/sources/PHASE1_SCOPE_SOURCE_20260903.json",
    "docs/project/sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json",
    "docs/project/sources/PHASE1_MOCK_BASELINE_DECISION_20260904.json",
    "docs/project/phase1/README.md",
    "docs/project/phase1/PHASE1_MOCK_V01_BACKLOG.md",
    "docs/project/phase1/PHASE1_MOCK_M1_08_CONSISTENCY_REVIEW.md",
    "docs/project/phase1/PHASE1_MOCK_M2_BACKLOG.md",
    "docs/project/phase1/PHASE1_MOCK_M2_IMPLEMENTATION_REVIEW.md",
    "docs/project/phase1/PHASE1_MOCK_M3_BACKLOG.md",
    "docs/project/phase1/PHASE1_MOCK_M3_01_DIFY_TARGET_DSL_PREFLIGHT.md",
    "docs/project/phase1/PHASE1_MOCK_M3_02_WORKFLOW_INVOCATION_GRAPH_CONTRACT.md",
    "docs/project/phase1/PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md",
    "docs/project/phase1/PHASE1_MOCK_M4_BACKLOG.md",
    "docs/project/phase1/PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md",
    "dify/t01-phase1-mock-v0.1/regression/T01_PHASE1_MOCK_FREEZE_MANIFEST_v0.1.json",
    "docs/development/RUNBOOK.md",
    "legacy/README.md",
    "legacy/project-history/README.md",
    "legacy/project-history/project/DOCUMENT_CLEANUP_AUDIT_20260903.md",
    "legacy/project-history/project/DOCUMENT_CLEANUP_EXECUTION_20260903.md",
    "legacy/project-history/project/DOCUMENT_FLATTEN_EXECUTION_20260903.md",
    "legacy/project-history/project/PHASE1_MOCK_PLAN_REBASELINE_20260904.md",
    "legacy/project-history/project/SOURCE_LEGACY_REORGANIZATION_20260904.md",
    "legacy/project-history/project/ARCHITECTURE_P0_P7_MOCK_20260903.md",
    "legacy/project-history/project/PHASE1_SCOPE_WITH_P0_MAPPING_20260903.md",
    "legacy/project-history/project/ROADMAP_P0_P7_20260903.md",
    "legacy/project-history/project/P0_P7_STAGE_DELIVERY_PLAN_20260903.md",
    "legacy/project-history/p0-v07-plan/README.md",
    "legacy/full-t01-mock-v0.1/README.md",
    "legacy/full-t01-mock-v0.1/docs/development/RUNBOOK.md",
    "legacy/full-t01-mock-v0.1/工作流设计/02-数据契约/T01_Dify节点-MCP工具映射与数据契约_v0.1.md",
    "legacy/full-t01-mock-v0.1/工作流设计/03-Dify实现/T01_Dify工作流搭建与导入指南_v0.1.md",
    "legacy/full-t01-mock-v0.1/工作流设计/03-Dify实现/T01_Mock_MCP服务与Dify接入说明_v0.1.md",
    "legacy/s07/README.md",
    "legacy/s07/docs/archive/p0/S07_LEGACY_RUNBOOK.md",
    "src/README.md",
    "scripts/README.md",
    "tests/README.md",
    "dify/README.md",
    "discovery/README.md",
    "工作流设计/README.md",
    "工作流设计/01-业务依据/README.md",
    "工作流设计/01-业务依据/T01_算法图_v10_20260821.md",
    "工作流设计/01-业务依据/抗原智能体一阶段边界及核心能力说明.pdf",
    "工作流设计/02-数据契约/README.md",
    "工作流设计/03-Dify实现/README.md",
)


STATUS_PATH = "docs/project/STATUS.md"
PHASE1_INDEX = "docs/project/phase1/README.md"
FREEZE_MANIFEST = (
    "dify/t01-phase1-mock-v0.1/regression/"
    "T01_PHASE1_MOCK_FREEZE_MANIFEST_v0.1.json"
)
# Live navigation documents only, never frozen task specifications or originals.
CURRENT_NAVIGATION = {
    "AGENTS.md": (
        STATUS_PATH, "docs/README.md", "docs/development/RUNBOOK.md",
        "工作流设计/01-业务依据/README.md",
    ),
    "README.md": (STATUS_PATH, "docs/README.md", PHASE1_INDEX),
    "docs/README.md": (
        STATUS_PATH, PHASE1_INDEX, "docs/project/ARCHITECTURE.md",
        "docs/project/PHASE1_DELIVERY_PLAN.md", "docs/project/OPEN_ITEMS.md",
    ),
    PHASE1_INDEX: (
        STATUS_PATH, "docs/project/PHASE1_DELIVERY_PLAN.md", FREEZE_MANIFEST,
        "docs/project/phase1/PHASE1_MOCK_M3_BACKLOG.md",
        "docs/project/phase1/PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md",
        "docs/project/phase1/PHASE1_MOCK_M4_BACKLOG.md",
        "docs/project/phase1/PHASE1_MOCK_M4_IMPLEMENTATION_REVIEW.md",
    ),
    "工作流设计/README.md": (
        STATUS_PATH, "工作流设计/01-业务依据/README.md",
        "工作流设计/02-数据契约/README.md", "工作流设计/03-Dify实现/README.md",
    ),
    "工作流设计/02-数据契约/README.md": (STATUS_PATH, PHASE1_INDEX),
    "工作流设计/03-Dify实现/README.md": (STATUS_PATH, FREEZE_MANIFEST),
    "src/README.md": (STATUS_PATH, "src/t01_phase1_mock/dify/generator.py"),
    "scripts/README.md": (
        STATUS_PATH, "scripts/check_docs.py",
        "scripts/t01_phase1_mock/build_dify_workflows.py",
        "scripts/t01_phase1_mock/run_m4_campaign.py",
    ),
    "tests/README.md": (STATUS_PATH, "docs/development/RUNBOOK.md"),
    "dify/README.md": (STATUS_PATH, "工作流设计/03-Dify实现/README.md"),
    "discovery/README.md": (STATUS_PATH, PHASE1_INDEX),
}
# Known regressions in live entry points; this is not a prose truth checker.
OBSOLETE_ENTRY_CLAIMS = (
    r"当前仍没有可导入",
    r"唯一未来\s*生成源",
    r"Dify\s*生成脚本仍只在\s*M3\s*新增",
    r"只在\s*M3\s*创建",
    r"当前一期必须另建\s*18\s*节点\s*Mock",
)
CURRENT_TASK_RE = re.compile(
    r"^当前任务：\[(PH1-(?:REAL|MOCK)-[A-Z0-9-]+)\]\((<[^>\n]+>|[^)\n]+)\)\s*$",
    re.MULTILINE,
)

# Exact source copies are evidence, not navigation from their archive location.
# Keep this registration narrow: nearby README files and live originals are
# still checked. A copy is exempt only when both manifest entries match its bytes.
MANIFESTED_MARKDOWN_SNAPSHOTS = {
    "discovery/t01-phase1-real/w1/b2-review-20260906/after/"
    "工作流设计/02-数据契约/phase1-real-v0.1/b2-review/README.md":
    "discovery/t01-phase1-real/w1/b2-review-20260906/manifest.json",
}


def _verified_markdown_snapshot(path: Path) -> bool:
    manifest_relative = MANIFESTED_MARKDOWN_SNAPSHOTS.get(path.relative_to(ROOT).as_posix())
    if manifest_relative is None:
        return False
    try:
        manifest_path = ROOT / manifest_relative
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            return False
        archive_relative = path.relative_to(manifest_path.parent).as_posix()
        original_relative = path.relative_to(manifest_path.parent / "after").as_posix()
        copies = [entry for entry in manifest["files"] if entry["path"] == archive_relative]
        originals = [entry for entry in manifest["sources"] if entry["path"] == original_relative]
        data = path.read_bytes()
        fingerprint = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
        return copies == [{"path": archive_relative, **fingerprint}] and originals == [
            {"path": original_relative, **fingerprint}
        ]
    except (OSError, ValueError, KeyError, TypeError):
        return False


def markdown_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*.md"):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if _verified_markdown_snapshot(path):
            continue
        # Unmodified upstream output contains container-local plot/CSV links.
        # Its bytes and artifacts are checked by the raw-evidence validator;
        # neighboring project README/review files remain navigation documents.
        if relative.match(
            'discovery/t01-phase1-real/w1/deeptmhmm-academic-*/runs/*/output/result/deeptmhmm_results.md'
        ) or relative.match(
            'var/t01-phase1-real/*/runs/t01p1r-run-*/jobs/t01p1r-job-*/attempts/t01p1r-attempt-*/output/result/deeptmhmm_results.md'
        ):
            continue
        if relative.parts[:3] == ("dify", "regression", "runs"):
            continue
        if relative.parts[:5] == (
            "legacy", "full-t01-mock-v0.1", "dify", "regression", "runs",
        ):
            continue
        files.append(path)
    return sorted(files)


def _local_link(raw_target: str) -> tuple[str, str] | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if not target or target.lower().startswith(REMOTE_PREFIXES):
        return None
    # Existing project links have no titles; retain tolerance for quoted titles.
    target = target.split(' "', 1)[0].split(" '", 1)[0]
    path, _, fragment = target.partition("#")
    return unquote(path.split("?", 1)[0]), unquote(fragment)


def _markdown_anchors(text: str) -> set[str]:
    """ATX headings used by current project docs; historical anchors are not audited."""
    anchors: set[str] = set()
    fence: str | None = None
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith((chr(96) * 3, "~~~")):
            marker = stripped[:3]
            fence = None if fence == marker else (fence or marker)
            continue
        if fence:
            continue
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", match.group(1))
        slug = re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")
        anchor, suffix = slug, 0
        while anchor in anchors:
            suffix += 1
            anchor = f"{slug}-{suffix}"
        anchors.add(anchor)
    return anchors


def _resolved_link(source: Path, raw: str) -> tuple[Path, str] | None:
    local = _local_link(raw)
    if local is None:
        return None
    path, fragment = local
    return ((source.parent / path).resolve() if path else source.resolve(), fragment)


def _validate_current_task(errors: list[str]) -> None:
    source = ROOT / STATUS_PATH
    if not source.is_file():
        return
    matches = list(CURRENT_TASK_RE.finditer(source.read_text(encoding="utf-8-sig")))
    if len(matches) != 1:
        errors.append(f"{STATUS_PATH}: 必须有且仅有一个“当前任务：[PH1-...](任务包或计划章节)”入口")
        return
    task_id, raw = matches[0].groups()
    resolved = _resolved_link(source, raw)
    if resolved is None:
        errors.append(f"{STATUS_PATH}: 当前任务必须链接到本项目的任务包或计划章节")
        return
    target, fragment = resolved
    if (
        not target.is_relative_to((ROOT / "docs/project").resolve())
        or target == source.resolve()
        or target.suffix.lower() != ".md"
        or not target.is_file()
    ):
        errors.append(f"{STATUS_PATH}: 当前任务入口必须是 docs/project 内现存的任务包或计划章节")
        return
    task_text = target.read_text(encoding="utf-8-sig")
    if not re.search(rf"(?<![\w-]){re.escape(task_id)}(?![\w-])", task_text):
        errors.append(f"{STATUS_PATH}: 当前任务 {task_id} 未在入口文档声明")
    if target.name == "PHASE1_DELIVERY_PLAN.md" and not fragment:
        errors.append(f"{STATUS_PATH}: 使用交付计划作为任务入口时必须指向具体章节")


def validate_docs() -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_DOCUMENTS:
        if not (ROOT / relative).is_file():
            errors.append(f"缺少必需文档：{relative}")

    for relative in MANIFESTED_MARKDOWN_SNAPSHOTS:
        snapshot = ROOT / relative
        if snapshot.is_file() and not _verified_markdown_snapshot(snapshot):
            errors.append(f"{relative}: 封存 Markdown 快照与来源/产物清单不一致，禁止跳过导航检查")

    agents = ROOT / "AGENTS.md"
    if agents.is_file():
        line_count = len(agents.read_text(encoding="utf-8-sig").splitlines())
        # Compact instructions are valid; required navigation is checked below.
        if line_count > 120:
            errors.append(f"AGENTS.md 应保持简短，当前为 {line_count} 行（最多 120）")

    links: dict[str, set[Path]] = {}
    anchors: dict[Path, set[str]] = {}
    for source in markdown_files():
        relative = source.relative_to(ROOT).as_posix()
        text = source.read_text(encoding="utf-8-sig")
        links[relative] = set()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in LOCAL_LINK_RE.finditer(line):
                resolved = _resolved_link(source, match.group(1))
                if resolved is None:
                    continue
                target, fragment = resolved
                if not target.is_relative_to(ROOT.resolve()):
                    errors.append(f"{relative}:{line_number} 链接越出项目：{match.group(1)}")
                    continue
                links[relative].add(target)
                if not target.exists():
                    errors.append(f"{relative}:{line_number} 链接不存在：{match.group(1)}")
                elif (
                    fragment and source.relative_to(ROOT).parts[0] != "legacy"
                    and target.is_file() and target.suffix.lower() == ".md"
                ):
                    if target not in anchors:
                        anchors[target] = _markdown_anchors(target.read_text(encoding="utf-8-sig"))
                    if fragment not in anchors[target]:
                        errors.append(f"{relative}:{line_number} 标题锚点不存在：{match.group(1)}")
        if relative in CURRENT_NAVIGATION:
            for pattern in OBSOLETE_ENTRY_CLAIMS:
                if re.search(pattern, text):
                    errors.append(f"{relative}: 发现过时入口表述，请按 STATUS 和现存证据更新（{pattern}）")

    for source, targets in CURRENT_NAVIGATION.items():
        if source not in links:
            errors.append(f"缺少当前导航文档：{source}")
            continue
        for target in targets:
            if (ROOT / target).resolve() not in links[source]:
                errors.append(f"{source}: 缺少关键导航链接：{target}")

    _validate_current_task(errors)
    return errors


def main() -> int:
    errors = validate_docs()
    if errors:
        print("documentation_status=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"documentation_status=PASS markdown_files={len(markdown_files())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
