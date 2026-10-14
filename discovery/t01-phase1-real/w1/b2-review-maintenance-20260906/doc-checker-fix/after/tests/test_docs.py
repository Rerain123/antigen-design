from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import check_docs


def test_progressive_documentation_layout_and_links() -> None:
    assert check_docs.validate_docs() == []


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def doc_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    monkeypatch.setattr(
        check_docs, "REQUIRED_DOCUMENTS",
        ("README.md", check_docs.STATUS_PATH, "docs/project/PHASE1_DELIVERY_PLAN.md"),
    )
    monkeypatch.setattr(
        check_docs, "CURRENT_NAVIGATION", {"README.md": (check_docs.STATUS_PATH,)},
    )
    _write(tmp_path, "README.md", "[当前任务](docs/project/STATUS.md#当前任务入口)\n")
    _write(
        tmp_path, check_docs.STATUS_PATH,
        "# 状态\n\n## 当前任务入口\n\n"
        "当前任务：[PH1-REAL-W1](PHASE1_DELIVERY_PLAN.md#3-真实能力实施波次)\n",
    )
    _write(
        tmp_path, "docs/project/PHASE1_DELIVERY_PLAN.md",
        "# 计划\n\n## 3. 真实能力实施波次\n\nPH1-REAL-W1\n",
    )
    return tmp_path


def test_valid_current_task_and_chinese_anchor(doc_tree: Path) -> None:
    assert check_docs.validate_docs() == []


def test_upstream_deeptmhmm_report_is_preserved_but_navigation_still_checked(doc_tree: Path) -> None:
    folder = 'discovery/t01-phase1-real/w1/deeptmhmm-academic-20260905/runs/short/output/result/'
    report = _write(doc_tree, folder+'deeptmhmm_results.md', '![plot](/out/result/plot.png)\n')
    assert report not in check_docs.markdown_files()
    assert check_docs.validate_docs() == []
    _write(doc_tree, folder+'README.md', '[broken](missing.md)\n')
    _write(doc_tree, 'docs/deeptmhmm_results.md', '[broken](missing.md)\n')
    errors = check_docs.validate_docs()
    assert any('README.md' in error and '链接不存在' in error for error in errors)
    assert any('docs/deeptmhmm_results.md' in error and '链接不存在' in error for error in errors)


def _snapshot_fixture(root: Path) -> tuple[Path, Path, Path]:
    relative, manifest_relative = next(iter(check_docs.MANIFESTED_MARKDOWN_SNAPSHOTS.items()))
    manifest_path = root / manifest_relative
    snapshot = _write(root, relative, "[状态](../../../../docs/project/STATUS.md#当前任务入口)\n")
    original_relative = snapshot.relative_to(manifest_path.parent / "after").as_posix()
    original = _write(root, original_relative, snapshot.read_text(encoding="utf-8"))
    data = snapshot.read_bytes()
    fingerprint = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
    manifest = {
        "files": [{"path": snapshot.relative_to(manifest_path.parent).as_posix(), **fingerprint}],
        "sources": [{"path": original_relative, **fingerprint}],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return snapshot, original, manifest_path


def test_verified_source_snapshot_keeps_original_bytes_and_live_navigation(doc_tree: Path) -> None:
    snapshot, original, _ = _snapshot_fixture(doc_tree)
    before = snapshot.read_bytes()
    assert snapshot not in check_docs.markdown_files()
    assert original in check_docs.markdown_files()
    assert check_docs.validate_docs() == []
    assert snapshot.read_bytes() == before
    # Neither the live source nor another file next to the archive is exempt.
    original.write_text("[broken](missing-live.md)\n", encoding="utf-8")
    snapshot.with_name("neighbor.md").write_text("[broken](missing-archive.md)\n", encoding="utf-8")
    errors = check_docs.validate_docs()
    assert any("missing-live.md" in error for error in errors)
    assert any("missing-archive.md" in error for error in errors)
    assert snapshot not in check_docs.markdown_files()


@pytest.mark.parametrize("damage", ["bytes", "size", "source", "entry", "duplicate", "json", "missing"])
def test_unverified_snapshot_cannot_bypass_navigation(doc_tree: Path, damage: str) -> None:
    snapshot, _, manifest_path = _snapshot_fixture(doc_tree)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if damage == "bytes":
        snapshot.write_bytes(b"")
    elif damage == "size":
        manifest["files"][0]["size_bytes"] += 1
    elif damage == "source":
        manifest["sources"][0]["sha256"] = "0" * 64
    elif damage == "entry":
        manifest["files"] = []
    elif damage == "duplicate":
        manifest["files"] *= 2
    if damage == "missing":
        manifest_path.unlink()
    else:
        manifest_path.write_text("{" if damage == "json" else json.dumps(manifest), encoding="utf-8")
    assert snapshot in check_docs.markdown_files()
    assert any("封存 Markdown 快照" in error for error in check_docs.validate_docs())


@pytest.mark.parametrize(
    "extra, message",
    [
        ("[缺失](missing.md)", "链接不存在"),
        ("[越界](../outside.md)", "链接越出项目"),
        ("[错误章节](docs/project/PHASE1_DELIVERY_PLAN.md#不存在)", "标题锚点不存在"),
        ("[本页错误章节](#不存在)", "标题锚点不存在"),
    ],
)
def test_invalid_navigation_is_reported(doc_tree: Path, extra: str, message: str) -> None:
    with (doc_tree / "README.md").open("a", encoding="utf-8") as handle:
        handle.write(extra + "\n")
    assert any(message in error for error in check_docs.validate_docs())


def test_missing_status_navigation_is_reported(doc_tree: Path) -> None:
    _write(doc_tree, "README.md", "# 入口\n\n状态文字不能替代导航链接。\n")
    assert any("缺少关键导航链接" in error for error in check_docs.validate_docs())


@pytest.mark.parametrize(
    "filename",
    ["PHASE1_MOCK_M3_IMPLEMENTATION_REVIEW.md", "PHASE1_MOCK_M4_BACKLOG.md"],
)
def test_missing_later_milestone_is_required(
    doc_tree: Path, monkeypatch: pytest.MonkeyPatch, filename: str,
) -> None:
    relative = f"docs/project/phase1/{filename}"
    # Keep the actual required-document list: M3/M4 must remain registered.
    assert relative in _PROJECT_REQUIRED_DOCUMENTS
    monkeypatch.setattr(
        check_docs, "REQUIRED_DOCUMENTS", (*check_docs.REQUIRED_DOCUMENTS, relative),
    )
    assert f"缺少必需文档：{relative}" in check_docs.validate_docs()


_PROJECT_REQUIRED_DOCUMENTS = check_docs.REQUIRED_DOCUMENTS


@pytest.mark.parametrize(
    "declaration, message",
    [
        ("", "必须有且仅有一个"),
        (
            "当前任务：[PH1-REAL-W1](PHASE1_DELIVERY_PLAN.md#3-真实能力实施波次)\n" * 2,
            "必须有且仅有一个",
        ),
        ("当前任务：[PH1-REAL-W9](PHASE1_DELIVERY_PLAN.md#3-真实能力实施波次)", "未在入口文档声明"),
        ("当前任务：[PH1-REAL-W1](PHASE1_DELIVERY_PLAN.md)", "必须指向具体章节"),
        ("当前任务：[PH1-REAL-W1](https://example.com/task)", "必须链接到本项目"),
        ("当前任务：[PH1-REAL-W1](../../legacy/task.md)", "docs/project 内现存"),
        ("当前任务：[PH1-REAL-W1](missing.md)", "docs/project 内现存"),
    ],
)
def test_invalid_current_task_is_reported(
    doc_tree: Path, declaration: str, message: str,
) -> None:
    _write(doc_tree, "legacy/task.md", "# PH1-REAL-W1\n")
    _write(doc_tree, check_docs.STATUS_PATH, "# 状态\n\n## 当前任务入口\n\n" + declaration + "\n")
    assert any(message in error for error in check_docs.validate_docs())


@pytest.mark.parametrize(
    "claim",
    [
        "当前仍没有可导入的一期 DSL 或 Workflow。",
        "Dify 模板的唯一未来\n生成源只在 M3 创建。",
        "Dify 生成脚本仍只在 M3 新增。",
        "当前一期必须另建 18 节点 Mock。",
    ],
)
def test_stale_live_entry_claim_is_rejected(doc_tree: Path, claim: str) -> None:
    with (doc_tree / "README.md").open("a", encoding="utf-8") as handle:
        handle.write(claim + "\n")
    assert any("过时入口表述" in error for error in check_docs.validate_docs())


def test_frozen_and_historical_statements_remain_valid(doc_tree: Path) -> None:
    historical = "# 冻结时点\n\n当前仍没有可导入的一期 DSL 或 Workflow。\nSPEC_ONLY\nDECLARED_NOT_RUN\n"
    _write(doc_tree, "docs/project/phase1/frozen-spec.md", historical)
    _write(doc_tree, "legacy/history.md", historical)
    assert check_docs.validate_docs() == []


def test_frozen_manifest_navigation_cannot_silently_disappear(
    doc_tree: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        check_docs, "CURRENT_NAVIGATION",
        {"README.md": (check_docs.STATUS_PATH, check_docs.FREEZE_MANIFEST)},
    )
    _write(doc_tree, check_docs.FREEZE_MANIFEST, "{}")
    assert any(
        "缺少关键导航链接" in error and check_docs.FREEZE_MANIFEST in error
        for error in check_docs.validate_docs()
    )
    with (doc_tree / "README.md").open("a", encoding="utf-8") as handle:
        handle.write(f"[冻结证据]({check_docs.FREEZE_MANIFEST})\n")
    assert check_docs.validate_docs() == []
    (doc_tree / check_docs.FREEZE_MANIFEST).unlink()
    assert any("链接不存在" in error for error in check_docs.validate_docs())


def test_local_links_allow_angle_quoted_paths_and_duplicate_headings(doc_tree: Path) -> None:
    _write(doc_tree, "docs/说明 (参考).md", "# 说明\n\n## 重复标题\n\n## 重复标题\n")
    with (doc_tree / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("[第二处](<docs/说明 (参考).md#重复标题-1>)\n")
    assert check_docs.validate_docs() == []
