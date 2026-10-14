from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from scripts import check_docs


def test_progressive_documentation_layout_and_links() -> None:
    assert check_docs.validate_docs() == []


@pytest.mark.parametrize('damage',['none','bytes','size','hash','missing','duplicate','malformed','missing_file'])
def test_hardening_snapshot_requires_exact_local_index(doc_tree,damage):
    rows=[]
    for relative,index_relative in check_docs.LOCAL_INDEX_MARKDOWN_SNAPSHOTS.items():
        snapshot=_write(doc_tree,relative,'[archive](missing-in-snapshot.md)\n')
        index_path=doc_tree/index_relative
        data=snapshot.read_bytes()
        rows.append(dict(path=snapshot.relative_to(index_path.parent).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    value=dict(schema='t01-local-evidence-index-v1',file_count=len(rows),files=rows)
    if damage=='size':rows[-1]['bytes']+=1
    if damage=='hash':rows[-1]['sha256']='0'*64
    if damage=='duplicate':rows.append(rows[-1]);value['file_count']+=1
    if damage=='bytes':snapshot.write_bytes(b'')
    if damage=='missing_file':snapshot.unlink()
    if damage!='missing':index_path.write_text('{' if damage=='malformed' else json.dumps(value),encoding='utf-8')
    neighbor=_write(doc_tree,str(snapshot.with_name('neighbor.md').relative_to(doc_tree)),'[neighbor](missing-neighbor.md)\n')
    assert (snapshot not in check_docs.markdown_files())==(damage in ('none','missing_file'))
    errors=check_docs.validate_docs()
    assert any('封存 Markdown 快照' in error for error in errors)==(damage!='none')
    assert any('missing-neighbor.md' in error for error in errors)


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def doc_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    monkeypatch.setattr(check_docs, "DIRECT_FILE_NAVIGATION", {})
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


def test_compact_agents_keeps_required_navigation_checks(
    doc_tree: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        check_docs, "CURRENT_NAVIGATION",
        {**check_docs.CURRENT_NAVIGATION, "AGENTS.md": (check_docs.STATUS_PATH,)},
    )
    agents = _write(
        doc_tree, "AGENTS.md",
        "# 项目工作约定\n\n先读 [状态](docs/project/STATUS.md)。\n",
    )
    assert check_docs.validate_docs() == []
    agents.write_text("# 项目工作约定\n\n先看状态再工作。\n", encoding="utf-8")
    assert any(
        "AGENTS.md" in error and "缺少关键导航链接" in error
        for error in check_docs.validate_docs()
    )


def test_excessive_agents_still_reports_reading_burden(doc_tree: Path) -> None:
    _write(doc_tree, "AGENTS.md", "# 项目工作约定\n" + "重复说明\n" * 150)
    assert any("AGENTS.md 应保持简短" in error for error in check_docs.validate_docs())


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


@pytest.mark.parametrize('runtime', ['dev', 'local-workflow-20260910-r01/fresh'])
def test_current_runtime_native_report_exclusion_is_exact(doc_tree: Path, runtime: str) -> None:
    folder=f'var/t01-phase1-real/{runtime}/runs/t01p1r-run-x/jobs/t01p1r-job-x/attempts/t01p1r-attempt-x/output/result/'
    report=_write(doc_tree,folder+'deeptmhmm_results.md','![plot](/out/result/plot.png)\n')
    assert report not in check_docs.markdown_files()
    assert check_docs.validate_docs()==[]
    _write(doc_tree,folder+'README.md','[broken](missing.md)\n')
    _write(doc_tree,'var/t01-phase1-real/dev/deeptmhmm_results.md','[broken](missing.md)\n')
    errors=check_docs.validate_docs()
    assert any('README.md' in error for error in errors)
    assert any('dev/deeptmhmm_results.md' in error for error in errors)


@pytest.mark.parametrize('asset', list(check_docs.UPSTREAM_MARKDOWN_ASSETS.items()))
@pytest.mark.parametrize('damage', ['none', 'bytes', 'hash', 'missing_registry', 'duplicate'])
def test_upstream_model_docs_require_exact_manifest_and_keep_neighbors(doc_tree: Path, damage: str, asset: tuple[str, str]) -> None:
    relative, registry = asset
    upstream = _write(doc_tree, relative, '[upstream image](missing.png)\n')
    data = upstream.read_bytes()
    record = dict(path=relative, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    if damage == 'hash': record['sha256'] = '0' * 64
    if damage != 'missing_registry':
        _write(doc_tree, registry, json.dumps(dict(files=[record, record] if damage == 'duplicate' else [record])))
    if damage == 'bytes': upstream.write_bytes(data + b' ')
    neighbor = _write(doc_tree, str(Path(relative).with_name('review.md')), '[project](missing-project.md)\n')
    assert (upstream not in check_docs.markdown_files()) == (damage == 'none')
    assert neighbor in check_docs.markdown_files()
    errors = check_docs.validate_docs()
    assert any('missing-project.md' in error for error in errors)
    assert any('missing.png' in error for error in errors) == (damage != 'none')


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


def _indexed_snapshot_fixture(root: Path) -> tuple[dict[Path, Path], Path]:
    snapshots = {}
    manifest = {"final_source_files": {}, "files": {}}
    for relative, index_relative in check_docs.INDEXED_MARKDOWN_SNAPSHOTS.items():
        index_path = root / index_relative
        snapshot = _write(root, relative, "[封存时点链接](missing-at-archive-location.md)\n")
        original_relative = snapshot.relative_to(index_path.parent / "final-source").as_posix()
        original = root / original_relative
        if not original.exists():
            _write(root, original_relative, "# 现行文档\n")
        snapshots[snapshot] = original
        archive_relative = snapshot.relative_to(index_path.parent).as_posix()
        data = snapshot.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        manifest["final_source_files"][original_relative] = {
            "snapshot": archive_relative, "sha256": digest,
        }
        manifest["files"][archive_relative] = {"sha256": digest, "size_bytes": len(data)}
    index_path.write_text(json.dumps(manifest), encoding="utf-8")
    return snapshots, index_path


def test_delivery_snapshots_are_verified_without_exempting_live_or_nearby_docs(doc_tree: Path) -> None:
    snapshots, _ = _indexed_snapshot_fixture(doc_tree)
    before = {path: path.read_bytes() for path in snapshots}
    assert check_docs.validate_docs() == []
    assert all(path not in check_docs.markdown_files() for path in snapshots)
    assert all(path in check_docs.markdown_files() for path in snapshots.values())
    snapshot, original = next(iter(snapshots.items()))
    with original.open("a", encoding="utf-8") as handle:
        handle.write("[现行错误](missing-live.md)\n")
    snapshot.with_name("neighbor.md").write_text("[邻居错误](missing-neighbor.md)\n", encoding="utf-8")
    _write(doc_tree, "docs/final-source/README.md", "[普通目录](missing-ordinary.md)\n")
    errors = check_docs.validate_docs()
    assert all(any(name in error for error in errors) for name in (
        "missing-live.md", "missing-neighbor.md", "missing-ordinary.md",
    ))
    assert {path: path.read_bytes() for path in snapshots} == before


@pytest.mark.parametrize("damage", [
    "bytes", "size", "source_hash", "source_path", "source_entry", "file_entry",
    "json", "missing_index", "missing_snapshot",
])
def test_invalid_delivery_snapshot_or_index_is_reported(doc_tree: Path, damage: str) -> None:
    snapshots, index_path = _indexed_snapshot_fixture(doc_tree)
    snapshot = next(iter(snapshots))
    manifest = json.loads(index_path.read_text(encoding="utf-8"))
    source = next(iter(manifest["final_source_files"].values()))
    archive_relative = source["snapshot"]
    if damage == "bytes":
        snapshot.write_bytes(b"")
    elif damage == "size":
        manifest["files"][archive_relative]["size_bytes"] += 1
    elif damage == "source_hash":
        source["sha256"] = "0" * 64
    elif damage == "source_path":
        source["snapshot"] = "final-source/another.md"
    elif damage == "source_entry":
        manifest["final_source_files"] = {}
    elif damage == "file_entry":
        manifest["files"] = {}
    elif damage == "missing_snapshot":
        snapshot.unlink()
    if damage == "missing_index":
        index_path.unlink()
    else:
        index_path.write_text("{" if damage == "json" else json.dumps(manifest), encoding="utf-8")
    assert any("封存 Markdown 快照" in error for error in check_docs.validate_docs())
    if snapshot.exists():
        assert snapshot in check_docs.markdown_files()


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


def test_reference_links_validate_missing_files_and_fragments(doc_tree: Path) -> None:
    path = _write(doc_tree, "docs/references.md", "[阅读][source]\n\n[source]: missing.md\n")
    assert any("missing.md" in error for error in check_docs.validate_docs())
    path.write_text("[source]: project/PHASE1_DELIVERY_PLAN.md#不存在\n", encoding="utf-8")
    assert any("标题锚点不存在" in error for error in check_docs.validate_docs())
    path.write_text("[source]: <project/PHASE1_DELIVERY_PLAN.md#3-真实能力实施波次>\n", encoding="utf-8")
    assert check_docs.validate_docs() == []


def test_code_examples_are_not_navigation(doc_tree: Path) -> None:
    _write(doc_tree, "docs/example.md", "````markdown\n[示例](missing.md)\n```\n[ref]: missing-too.md\n````\n")
    assert check_docs.validate_docs() == []


def test_excluded_runtime_tree_is_pruned_before_navigation_scan(doc_tree: Path) -> None:
    runtime_doc = _write(doc_tree, ".tmp/transient/runtime.md", "[transient](missing.md)\n")
    assert runtime_doc not in check_docs.markdown_files()
    assert check_docs.validate_docs() == []


def test_archived_reference_issues_are_reported_without_changing_evidence(doc_tree: Path, capsys) -> None:
    path = _write(doc_tree, "legacy/evidence.md", "[历史][ref]\n\n[ref]: missing-original.md\n")
    before = path.read_bytes()
    assert check_docs.validate_docs() == []
    assert len(check_docs.historical_reference_issues()) == 1
    assert check_docs.main() == 0
    assert "PASS_WITH_HISTORICAL_LINK_ISSUES" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_indexed_package_internal_report_is_exactly_scoped(doc_tree: Path, monkeypatch) -> None:
    folder = doc_tree / "evidence/batch"
    report = _write(doc_tree, "evidence/batch/report.md", "[data](data.json)\n[manifest](manifest.json)\n")
    archive = folder / "package.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("data.json", "{}")
        package.writestr("manifest.json", "{}")
    rows = []
    for path in (report, archive):
        data = path.read_bytes()
        rows.append(dict(path=path.relative_to(folder).as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    _write(doc_tree, "evidence/batch/index.json", json.dumps(dict(files=rows)))
    monkeypatch.setattr(check_docs, "PACKAGE_INTERNAL_MARKDOWN_REPORTS", {
        "evidence/batch/report.md": dict(index="evidence/batch/index.json", archive="evidence/batch/package.zip"),
    })
    assert report not in check_docs.markdown_files()
    assert check_docs.validate_docs() == []
    issues = check_docs.historical_reference_issues()
    assert len(issues) == 2 and all("已验证交付包内链接" in issue for issue in issues)
    report.write_text(report.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert report in check_docs.markdown_files()
    assert any("data.json" in error for error in check_docs.validate_docs())


@pytest.mark.parametrize("target", check_docs.STAGE_PLANS)
def test_stage_navigation_requires_a_real_file_without_fragment(doc_tree: Path, monkeypatch, target) -> None:
    assert target in _PROJECT_REQUIRED_DOCUMENTS
    monkeypatch.setattr(check_docs, "DIRECT_FILE_NAVIGATION", {"README.md": (target,)})
    stage = _write(doc_tree, target, "# 阶段\n\n## 计划\n")
    readme = doc_tree / "README.md"
    original = readme.read_text(encoding="utf-8")
    readme.write_text(original + f"[阶段]({target}#计划)\n", encoding="utf-8")
    assert any("阶段入口必须直接链接" in error for error in check_docs.validate_docs())
    readme.write_text(original + f"[阶段]({target})\n", encoding="utf-8")
    assert check_docs.validate_docs() == []
    stage.unlink()
    assert any("链接不存在" in error for error in check_docs.validate_docs())


def test_current_w3_task_cannot_fall_back_to_master_plan(doc_tree: Path) -> None:
    _write(doc_tree, "docs/project/PHASE1_DELIVERY_PLAN.md", "# PH1-REAL-W3\n\n## 阶段\n")
    _write(doc_tree, check_docs.STATUS_PATH,
           "当前任务：[PH1-REAL-W3](PHASE1_DELIVERY_PLAN.md#阶段)\n")
    assert any("当前阶段任务必须直接打开" in error for error in check_docs.validate_docs())
    _write(doc_tree, check_docs.STAGE_PLANS[1], "# PH1-REAL-W3\n")
    _write(doc_tree, check_docs.STATUS_PATH,
           "## 当前任务入口\n\n当前任务：[PH1-REAL-W3](phase1/PHASE1_REAL_W3_PLAN.md)\n")
    assert check_docs.validate_docs() == []
