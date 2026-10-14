"""Frozen non-scientific identities used by the Phase 1 mock runtime."""

from __future__ import annotations

import re

NAMESPACE_ROOT = "t01_phase1_mock_v01"
FILESYSTEM_RELEASE_ROOT = "t01-phase1-mock-v0.1"

TOPOLOGY_VERSION = "T01-PHASE1-18NODE-OFFLINE"
NODE_REGISTRY_VERSION = "T01-PHASE1-NODE-REGISTRY-v0.1"
CONTROL_FLOW_VERSION = "T01-PHASE1-CONTROL-FLOW-v0.1"
ENVELOPE_CONTRACT_VERSION = "T01-PHASE1-ENVELOPE-v0.1"
SCENARIO_CATALOG_VERSION = "T01-PHASE1-MOCK-SCENARIO-CATALOG-v0.1"
ASSET_REGISTRY_VERSION = "T01-PHASE1-MOCK-ASSET-REGISTRY-v0.1"
FIXTURE_MANIFEST_VERSION = "T01-PHASE1-MOCK-FIXTURE-MANIFEST-v0.1"
ACCEPTANCE_CATALOG_VERSION = "T01-PHASE1-MOCK-ACCEPTANCE-CATALOG-v0.1"
MATERIALIZATION_VERSION = "T01-PHASE1-MOCK-FIXTURE-MATERIALIZATION-v0.1"
M2_RESULT_VERSION = "T01-PHASE1-MOCK-M2-ACCEPTANCE-RESULT-v0.1"
M4_RESULT_VERSION = "T01-PHASE1-MOCK-M4-REGRESSION-RESULT-v0.1"
M4_FREEZE_MANIFEST_VERSION = "T01-PHASE1-MOCK-FREEZE-MANIFEST-v0.1"

ASSERTION_OPERATOR_NAMES = (
    "JSON_SCHEMA_VALID",
    "COUNT_EQUALS",
    "SET_EQUALS",
    "BIJECTION",
    "EXACT_CATALOG_PROJECTION",
    "FIELD_EQUALS",
    "FIELD_ABSENT",
    "MATCHES_REGEX",
    "REFERENCES_RESOLVE",
    "CONTAINS_NONE",
    "NODE_STATUS_ALL",
    "NODE_ATTEMPT_COUNT_EQUALS",
    "NODE_ATTEMPT_FIELD_SEQUENCE_EQUALS",
    "CONTROL_DECISION_SEQUENCE_EQUALS",
    "EDGE_PRESENT",
    "EDGE_ABSENT",
    "EDGE_ORDERED_SUBSEQUENCE",
    "SUBMISSION_ACTION_EQUALS",
    "IDENTITY_RELATION_EQUALS",
    "EMISSION_COUNT_EQUALS",
    "NO_CONTROL_AFTER_NODE",
    "NO_SCIENTIFIC_VALUES",
    "JOIN_PRECONDITION",
    "ORIGINAL_RUN_UNCHANGED",
    "NO_STUB_PROMOTION",
    "PATH_WITHIN",
    "HASH_UNCHANGED",
    "NORMALIZED_EQUALS",
)

NODE_IDS = tuple(f"N{number:02d}" for number in range(1, 19))
EDGE_IDS = tuple(f"E{number:03d}" for number in range(1, 28))

REQUEST_ID_PATTERN = re.compile(
    r"^t01-phase1-mock-v01-req-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
RUN_ID_PATTERN = re.compile(
    r"^t01-phase1-mock-v01-run-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
ENVELOPE_ID_PATTERN = re.compile(
    r"^t01-phase1-mock-v01-env-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
SCENARIO_REF_PATTERN = re.compile(
    r"^t01_phase1_mock_v01[.]scenario[.][a-z][a-z0-9_]*$"
)
M4_CAMPAIGN_ID_PATTERN = re.compile(
    r"^t01p1m-v01-reg-[0-9]{8}-[a-z][a-z0-9-]{0,31}$"
)

TERMINAL_RUN_STATUSES = frozenset(
    {"COMPLETED", "COMPLETED_WITH_GAPS", "FAILED", "TIMED_OUT", "CANCELLED"}
)
TERMINAL_NODE_STATUSES = frozenset(
    {
        "SUCCEEDED",
        "SKIPPED_BRANCH",
        "SKIPPED_CONDITION",
        "FAILED",
        "TIMED_OUT",
        "CANCELLED",
        "NOT_EXECUTED",
    }
)

CHECKPOINT_ACTIONS = frozenset(
    {
        "SUBMIT_CREATE",
        "POLL_SCENARIO_CHECKPOINT",
        "INJECT_SCENARIO_EVENT",
        "CANCEL_RUN",
        "REQUEST_RECOVERY",
        "POLL_TERMINAL",
    }
)

CONTROL_TYPE_BY_KEY = {
    "design_suitability": "DESIGN_SUITABILITY",
    "n12_validation": "N12_VALIDATION",
    "n15_delivery_recommendation": "N15_DELIVERY_RECOMMENDATION",
    "n16_applicability": "N16_APPLICABILITY",
    "n17_applicability": "N17_APPLICABILITY",
}

OUTPUT_COMPLETENESS_BY_MODE = {
    "COMPLETE_STUB": "COMPLETE",
    "PARTIAL_STUB": "PARTIAL",
    "NONE": "NONE",
}

MODE_BY_OUTPUT_COMPLETENESS = {
    value: key for key, value in OUTPUT_COMPLETENESS_BY_MODE.items()
}

EDGE_ENDPOINTS = {
    "E001": (None, "N01"),
    "E002": ("N01", "N02"),
    "E003": ("N02", "N03"),
    "E004": ("N03", "N04"),
    "E005": ("N04", "N05"),
    "E006": ("N05", "N06"),
    "E007": ("N06", "N07"),
    "E008": ("N07", "N08"),
    "E009": ("N08", "N09"),
    "E010": ("N09", "N10"),
    "E011": ("N10", None),
    "E012": (None, None),
    "E013": (None, "N18"),
    "E014": (None, "N11"),
    "E015": ("N11", "N12"),
    "E016": ("N12", "N11"),
    "E017": ("N12", "N13"),
    "E018": ("N12", None),
    "E019": ("N13", "N14"),
    "E020": ("N14", "N15"),
    "E021": ("N15", None),
    "E022": (None, "N16"),
    "E023": (None, "N17"),
    "E024": ("N16", None),
    "E025": ("N17", None),
    "E026": (None, "N18"),
    "E027": ("N18", None),
}

UPSTREAM_NODE_IDS = {
    "N01": [],
    "N02": ["N01"],
    "N03": ["N02"],
    "N04": ["N03"],
    "N05": ["N04"],
    "N06": ["N05"],
    "N07": ["N06"],
    "N08": ["N07"],
    "N09": ["N08"],
    "N10": ["N09"],
    "N11": ["N10"],
    "N12": ["N11"],
    "N13": ["N12"],
    "N14": ["N13"],
    "N15": ["N14"],
    "N16": ["N15"],
    "N17": ["N15"],
    "N18": ["N16", "N17"],
}

LEGACY_IDENTITY_MARKERS = (
    "T01_Master_v10",
    "T01_P0_",
    "T01_P1_",
    "T01_P2_",
    "T01_P3_",
    "T01_P4_",
    "T01_P5_",
    "T01_P6_",
    "T01_P7_",
    "t01-mock-mcp",
    "t01_mock_mcp",
    "t01_dify_workflows",
    "MOCK-",
)

PROHIBITED_RUNTIME_VALUE_TOKENS = (
    "http://",
    "https://",
    "dna_sequence",
    "codon_sequence",
    "scientific_score",
    "scientific_threshold",
    "real_candidate",
    "scientific_rejection",
    "threshold_score",
    "candidate_rank",
    "binding_score",
    "stability_score",
    "rcsb_id",
    "alphafold_db_id",
    "external_structure_id",
)
