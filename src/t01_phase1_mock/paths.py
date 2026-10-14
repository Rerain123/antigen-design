"""Project paths and fail-closed resolution for current-phase assets."""

from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath

from .jsonio import ContractError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_CONTRACT_ROOT = PROJECT_ROOT / "工作流设计" / "02-数据契约"
IMPLEMENTATION_SPEC_ROOT = PROJECT_ROOT / "工作流设计" / "03-Dify实现"
PHASE1_RELEASE_ROOT = PROJECT_ROOT / "dify" / "t01-phase1-mock-v0.1"
FIXTURE_ROOT = PHASE1_RELEASE_ROOT / "fixtures"
REGRESSION_ROOT = PHASE1_RELEASE_ROOT / "regression"
M4_RUNS_ROOT = REGRESSION_ROOT / "runs"
TEMPLATE_ROOT = PHASE1_RELEASE_ROOT / "templates"
BINDING_ROOT = PHASE1_RELEASE_ROOT / "config"
BOUND_ROOT = PHASE1_RELEASE_ROOT / "bound"
M3_EVIDENCE_ROOT = PHASE1_RELEASE_ROOT / "evidence" / "m3"
M3_LOCAL_PROFILE_ROOT = M3_EVIDENCE_ROOT / "local_dify_1_17"
M3_TARGET_PREFLIGHT_PATH = M3_LOCAL_PROFILE_ROOT / "target-preflight.json"
M3_BINDING_EVIDENCE_PATH = M3_LOCAL_PROFILE_ROOT / "binding-evidence.json"
M3_IMPORT_EVIDENCE_PATH = M3_LOCAL_PROFILE_ROOT / "import-evidence.json"
M3_EXECUTION_MANIFEST_PATH = M3_LOCAL_PROFILE_ROOT / "execution-manifest.json"
M3_ACCEPTANCE_RESULT_PATH = (
    M3_LOCAL_PROFILE_ROOT / "T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT_v0.1.json"
)
M3_ACCEPTANCE_RESULT_SCHEMA_PATH = (
    M3_LOCAL_PROFILE_ROOT / "T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT_SCHEMA_v0.1.json"
)
DEFAULT_RUNTIME_ROOT = PROJECT_ROOT / "var" / "t01-phase1-mock-v0.1"

ENVELOPE_SCHEMA_PATH = DATA_CONTRACT_ROOT / "T01_PHASE1_MOCK_ENVELOPE_SCHEMA_v0.1.json"
SCENARIO_SCHEMA_PATH = (
    DATA_CONTRACT_ROOT / "T01_PHASE1_MOCK_SCENARIO_CATALOG_SCHEMA_v0.1.json"
)
SCENARIO_CATALOG_PATH = (
    DATA_CONTRACT_ROOT / "T01_PHASE1_MOCK_SCENARIO_CATALOG_v0.1.json"
)
ASSET_REGISTRY_SCHEMA_PATH = (
    IMPLEMENTATION_SPEC_ROOT / "T01_PHASE1_MOCK_ASSET_REGISTRY_SCHEMA_v0.1.json"
)
ASSET_REGISTRY_PATH = (
    IMPLEMENTATION_SPEC_ROOT / "T01_PHASE1_MOCK_ASSET_REGISTRY_v0.1.json"
)
FIXTURE_MANIFEST_SCHEMA_PATH = (
    FIXTURE_ROOT / "T01_PHASE1_MOCK_FIXTURE_MANIFEST_SCHEMA_v0.1.json"
)
FIXTURE_MANIFEST_PATH = FIXTURE_ROOT / "T01_PHASE1_MOCK_FIXTURE_MANIFEST_v0.1.json"
MATERIALIZATION_SCHEMA_PATH = (
    FIXTURE_ROOT / "T01_PHASE1_MOCK_FIXTURE_MATERIALIZATION_SCHEMA_v0.1.json"
)
MATERIALIZATION_PATH = (
    FIXTURE_ROOT / "T01_PHASE1_MOCK_FIXTURE_MATERIALIZATION_v0.1.json"
)
ACCEPTANCE_SCHEMA_PATH = (
    REGRESSION_ROOT / "T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_SCHEMA_v0.1.json"
)
ACCEPTANCE_CATALOG_PATH = (
    REGRESSION_ROOT / "T01_PHASE1_MOCK_ACCEPTANCE_CATALOG_v0.1.json"
)
M2_ACCEPTANCE_RESULT_PATH = (
    REGRESSION_ROOT / "T01_PHASE1_MOCK_M2_ACCEPTANCE_RESULT_v0.1.json"
)
M2_ACCEPTANCE_RESULT_SCHEMA_PATH = (
    REGRESSION_ROOT / "T01_PHASE1_MOCK_M2_ACCEPTANCE_RESULT_SCHEMA_v0.1.json"
)
M4_ACCEPTANCE_RESULT_SCHEMA_PATH = (
    REGRESSION_ROOT / "T01_PHASE1_MOCK_M4_REGRESSION_RESULT_SCHEMA_v0.1.json"
)
M4_FREEZE_MANIFEST_PATH = (
    REGRESSION_ROOT / "T01_PHASE1_MOCK_FREEZE_MANIFEST_v0.1.json"
)
M4_FREEZE_MANIFEST_SCHEMA_PATH = (
    REGRESSION_ROOT / "T01_PHASE1_MOCK_FREEZE_MANIFEST_SCHEMA_v0.1.json"
)

ENVELOPE_EXAMPLE_PATHS = (
    DATA_CONTRACT_ROOT / "examples" / "T01_PHASE1_MOCK_REQUEST_EXAMPLE_v0.1.json",
    DATA_CONTRACT_ROOT / "examples" / "T01_PHASE1_MOCK_RUN_CANDIDATE_EXAMPLE_v0.1.json",
    DATA_CONTRACT_ROOT / "examples" / "T01_PHASE1_MOCK_RUN_WT_EXAMPLE_v0.1.json",
    DATA_CONTRACT_ROOT / "examples" / "T01_PHASE1_MOCK_RUN_FAILURE_EXAMPLE_v0.1.json",
)

M1_SPEC_SOURCE_PATHS = (
    PROJECT_ROOT / "docs" / "project" / "phase1" / "PHASE1_MOCK_M1_01_SOURCE_NODE_STEP_TOOL_PRIORITY_MATRIX.md",
    PROJECT_ROOT / "docs" / "project" / "phase1" / "PHASE1_MOCK_M1_02_NODE_REGISTRY.md",
    PROJECT_ROOT / "docs" / "project" / "phase1" / "PHASE1_MOCK_M1_03_CONTROL_FLOW_STATE_GRAPH.md",
    PROJECT_ROOT / "docs" / "project" / "phase1" / "PHASE1_MOCK_M1_04_ENVELOPE_CONTRACT.md",
    PROJECT_ROOT / "docs" / "project" / "phase1" / "PHASE1_MOCK_M1_05_DETERMINISTIC_SCENARIO_MODEL.md",
    PROJECT_ROOT / "docs" / "project" / "phase1" / "PHASE1_MOCK_M1_06_NAMESPACE_DIRECTORY_GENERATION_BINDING_ISOLATION.md",
    PROJECT_ROOT / "docs" / "project" / "phase1" / "PHASE1_MOCK_M1_07_ACCEPTANCE_ASSERTIONS_FIXTURE_MANIFEST.md",
    PROJECT_ROOT / "docs" / "project" / "phase1" / "PHASE1_MOCK_M1_08_CONSISTENCY_REVIEW.md",
    ENVELOPE_SCHEMA_PATH,
    *ENVELOPE_EXAMPLE_PATHS,
    SCENARIO_SCHEMA_PATH,
    SCENARIO_CATALOG_PATH,
    ASSET_REGISTRY_SCHEMA_PATH,
    ASSET_REGISTRY_PATH,
    FIXTURE_MANIFEST_SCHEMA_PATH,
    FIXTURE_MANIFEST_PATH,
    ACCEPTANCE_SCHEMA_PATH,
    ACCEPTANCE_CATALOG_PATH,
)


def resolve_project_relative(relative_path: str, *, must_exist: bool = False) -> Path:
    """Resolve a manifest path inside this project without boundary escapes."""

    posix = PurePosixPath(relative_path)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise ContractError(f"unsafe project-relative path: {relative_path}")
    candidate = PROJECT_ROOT.joinpath(*posix.parts)
    resolved = candidate.resolve(strict=must_exist)
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ContractError(f"path leaves project root: {relative_path}") from exc
    legacy_root = (PROJECT_ROOT / "legacy").resolve()
    try:
        resolved.relative_to(legacy_root)
    except ValueError:
        pass
    else:
        raise ContractError(f"current-phase path enters legacy: {relative_path}")

    current = PROJECT_ROOT
    for part in posix.parts:
        current = current / part
        if current.exists():
            attributes = getattr(
                current.stat(follow_symlinks=False), "st_file_attributes", 0
            )
            if current.is_symlink() or attributes & getattr(
                stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0
            ):
                raise ContractError(
                    f"symlink or junction is forbidden in current fixture path: {relative_path}"
                )
    return resolved
