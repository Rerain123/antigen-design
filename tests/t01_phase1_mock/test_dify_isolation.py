from __future__ import annotations

import re

from t01_phase1_mock.jsonio import load_json
from t01_phase1_mock.paths import M3_EVIDENCE_ROOT, PHASE1_RELEASE_ROOT, PROJECT_ROOT


def test_m3_source_does_not_import_or_reference_legacy_implementations() -> None:
    source_roots = [
        PROJECT_ROOT / "src" / "t01_phase1_mock" / "dify",
        PROJECT_ROOT / "scripts" / "t01_phase1_mock",
    ]
    forbidden = ("t01_mock_mcp", "t01_dify_workflows", "legacy/full-t01", "legacy\\full-t01")
    for root in source_roots:
        for path in root.glob("*.py"):
            text = path.read_text(encoding="utf-8").casefold()
            assert not any(marker in text for marker in forbidden), path


def test_m3_assets_contain_no_secret_or_remote_science_endpoint() -> None:
    secret_value = re.compile(r"(?i)(bearer\s+[a-z0-9._-]+|sk-[a-z0-9]{8,}|password\s*[:=])")
    science_url = re.compile(r"(?i)https?://[^\s]*(uniprot|ncbi|alphafold|rcsb|blast|interpro)")
    for path in PHASE1_RELEASE_ROOT.rglob("*"):
        if path.is_file() and path.suffix.casefold() in {".json", ".yml", ".yaml"}:
            text = path.read_text(encoding="utf-8")
            assert secret_value.search(text) is None, path
            assert science_url.search(text) is None, path


def test_m3_evidence_records_closed_scope_guards() -> None:
    for path in M3_EVIDENCE_ROOT.rglob("*.json"):
        value = load_json(path)
        if value.get("document_type") == "T01_PHASE1_MOCK_M3_ACCEPTANCE_RESULT":
            assert value["himat_backend_access_count"] == 0
            assert value["legacy_implementation_reuse_count"] == 0
            assert value["scientific_network_request_count"] == 0

