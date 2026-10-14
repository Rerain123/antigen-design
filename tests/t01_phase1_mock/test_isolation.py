from __future__ import annotations

import ast
from pathlib import Path

from t01_phase1_mock.constants import M4_CAMPAIGN_ID_PATTERN
from t01_phase1_mock.jsonio import load_json
from t01_phase1_mock.paths import PHASE1_RELEASE_ROOT, PROJECT_ROOT, REGRESSION_ROOT


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_current_package_has_no_legacy_or_network_imports() -> None:
    source_root = PROJECT_ROOT / "src" / "t01_phase1_mock"
    forbidden = {
        "t01_mock_mcp",
        "t01_dify_workflows",
        "requests",
        "httpx",
        "urllib",
        "socket",
    }
    for path in source_root.rglob("*.py"):
        assert not (_import_roots(path) & forbidden), path


def test_control_flow_does_not_use_random_sleep_or_wall_clock() -> None:
    source_root = PROJECT_ROOT / "src" / "t01_phase1_mock"
    text = "\n".join(path.read_text(encoding="utf-8") for path in source_root.rglob("*.py"))
    assert "time.sleep(" not in text
    assert "datetime.now(" not in text
    assert "datetime.utcnow(" not in text
    assert "random." not in text


def test_m3_dify_dsl_is_confined_to_registered_template_and_bound_roots() -> None:
    actual = {
        path.relative_to(PHASE1_RELEASE_ROOT).as_posix()
        for path in PHASE1_RELEASE_ROOT.rglob("*.yml")
    }
    actual.update(
        path.relative_to(PHASE1_RELEASE_ROOT).as_posix()
        for path in PHASE1_RELEASE_ROOT.rglob("*.yaml")
    )
    assert actual == {
        "templates/T01_Phase1_Mock_v0.1.template.dify.yml",
        "templates/T01_Phase1_Mock_v0.1_Debug.template.dify.yml",
        "bound/local_dify_1_17/T01_Phase1_Mock_v0.1.bound.dify.yml",
        "bound/local_dify_1_17/T01_Phase1_Mock_v0.1_Debug.bound.dify.yml",
    }


def test_regression_runs_contain_only_m4_evidence_not_runtime_state() -> None:
    runs = REGRESSION_ROOT / "runs"
    if not runs.exists():
        return
    allowed_sections = {"main", "debug", "checks"}
    allowed_root_files = {
        "campaign.json",
        "asset-chain.json",
        "import-readback-evidence.json",
        "regression-partitions.json",
        "T01_PHASE1_MOCK_M4_REGRESSION_RESULT_v0.1.json",
    }
    for root in runs.iterdir():
        assert root.is_dir() and not root.is_symlink()
        assert M4_CAMPAIGN_ID_PATTERN.fullmatch(root.name)
        for path in root.rglob("*"):
            assert not path.is_symlink(), path
            relative = path.relative_to(root)
            if len(relative.parts) == 1:
                assert path.is_dir() or path.name in allowed_root_files, path
                if path.is_dir():
                    assert path.name in allowed_sections, path
            else:
                assert relative.parts[0] in allowed_sections, path
            assert "runtime" not in relative.parts, path
            assert path.name not in {"idempotency-index.json", "run-record.json"}, path


def test_m2_json_assets_have_no_credential_fields() -> None:
    forbidden = {
        "password",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "authorization",
        "bearer",
        "client_secret",
    }

    def keys(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key.casefold()
                yield from keys(item)
        elif isinstance(value, list):
            for item in value:
                yield from keys(item)

    for path in PHASE1_RELEASE_ROOT.rglob("*.json"):
        assert not (set(keys(load_json(path))) & forbidden), path
