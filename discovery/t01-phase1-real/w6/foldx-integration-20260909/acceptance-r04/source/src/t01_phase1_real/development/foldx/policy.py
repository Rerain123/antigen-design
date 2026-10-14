"""Pinned CPU FoldX profile; scientific consumption remains closed."""
from pathlib import Path
import hashlib
import math
import re

from ...common import REPO, decode, encode, ensure, profile as base_profile, sha
from ...files import no_links, read_locked
from ..glycosylation.policy import ARTIFACT_FIELDS

TOOL = "t01.real.foldx"
NODE = "N14"
HERE = Path(__file__).parent
PACKAGE = REPO / "var/t01-phase1-real/tool-assets/foldx-20270131"
EXECUTABLE = PACKAGE / "foldx_20270131"
EXECUTABLE_SHA256 = "5309d81c3f08b8405d172153aaf9792a244c06f98387c9d57a104302a9cef2cf"
IMAGE = "sha256:502f3e56812e8fff6f349a01fa4844d15c317c955a0b4d758b8fd2c22ce2693f"
SLOT = "t01p1r-foldx-development-slot"
LIMITS = dict(memory=2 * 1024**3, cpus=2, cpuset="0-1", pids=128)
ALPHABET = "ACDEFGHIKLMNPQRSTVWY"
AUTHORITY_ROOT = REPO / "工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902"
AUTHORITY = [AUTHORITY_ROOT / n for n in ("ToolSpec_C35_FoldX_v10.5.md", "AgentA_SOP_v10.5_20260902.md")]


def artifact(ref):
    ensure(isinstance(ref, dict) and set(ref) == ARTIFACT_FIELDS and ref["role"] == "result"
        and ref["media_type"] == "application/json" and ref["evidence_kind"] == "G0_REAL_OUTPUT"
        and isinstance(ref["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])
        and type(ref["size_bytes"]) is int and 0 < ref["size_bytes"] <= 32 * 1024**2,
        "INVALID_REQUEST", "Registered successful structure ArtifactRef required")


def _positions(value, length, name):
    ensure(isinstance(value, list) and value == sorted(value) and len(value) == len(set(value))
        and all(type(p) is int and 1 <= p <= length for p in value), "INVALID_REQUEST",
        name + " must be unique sorted 1-based sequence positions")


def _mutation(sequence, item):
    ensure(isinstance(item, dict) and set(item) == {"position", "wt", "mut"}, "INVALID_REQUEST", "Exact mutation record required")
    p, wt, mut = item["position"], item["wt"], item["mut"]
    ensure(type(p) is int and 1 <= p <= len(sequence) and wt == sequence[p - 1], "INVALID_REQUEST", "Mutation WT does not match sequence")
    ensure(isinstance(mut, str) and len(mut) == 1 and mut in ALPHABET and mut != wt, "INVALID_REQUEST", "Mutation target must be a different AA20 residue")


def request(raw):
    body = decode(raw)
    required = {"protein_sequence", "user_sequence_id", "structure_artifact", "mode", "fixed_positions", "scan_positions", "variants", "scope_source", "timeout_seconds"}
    ensure(isinstance(body, dict) and set(body) == required, "INVALID_REQUEST", "Exact FoldX engineering request required")
    sequence = body["protein_sequence"]
    ensure(isinstance(sequence, str) and re.fullmatch("[" + ALPHABET + "]{1,1000}", sequence), "INVALID_REQUEST", "Exact uppercase AA20 sequence, 1..1000 aa required")
    ensure(isinstance(body["user_sequence_id"], str) and 0 < len(body["user_sequence_id"]) <= 512, "INVALID_REQUEST", "Bounded user sequence label required")
    artifact(body["structure_artifact"])
    ensure(body["mode"] in ("positionscan", "buildmodel"), "INVALID_REQUEST", "FoldX mode must be positionscan or buildmodel")
    _positions(body["fixed_positions"], len(sequence), "fixed_positions")
    _positions(body["scan_positions"], len(sequence), "scan_positions")
    ensure(not set(body["fixed_positions"]).intersection(body["scan_positions"]), "INVALID_REQUEST", "fixed_positions and scan_positions must be disjoint")
    ensure(isinstance(body["variants"], list) and len(body["variants"]) <= 500, "INVALID_REQUEST", "variants must contain at most 500 entries")
    ensure(body["mode"] == "positionscan" and body["variants"] == [] or body["mode"] == "buildmodel" and body["scan_positions"] == [], "INVALID_REQUEST", "PositionScan and BuildModel scopes are mutually exclusive")
    if body["mode"] == "positionscan":
        ensure(body["scan_positions"], "INVALID_REQUEST", "PositionScan requires explicit scan_positions")
    else:
        ensure(body["variants"], "INVALID_REQUEST", "BuildModel requires explicit variants")
    ids = set()
    for variant in body["variants"]:
        ensure(isinstance(variant, dict) and set(variant) == {"variant_id", "mutations"}, "INVALID_REQUEST", "Exact FoldX variant record required")
        ensure(isinstance(variant["variant_id"], str) and 0 < len(variant["variant_id"]) <= 256 and variant["variant_id"] not in ids, "INVALID_REQUEST", "Variant IDs must be unique and bounded")
        ids.add(variant["variant_id"])
        ensure(isinstance(variant["mutations"], list) and variant["mutations"], "INVALID_REQUEST", "Each variant needs one or more mutations")
        for mutation in variant["mutations"]: _mutation(sequence, mutation)
        ensure(len({m["position"] for m in variant["mutations"]}) == len(variant["mutations"]), "INVALID_REQUEST", "Variant positions must be unique")
        ensure(not set(m["position"] for m in variant["mutations"]).intersection(body["fixed_positions"]), "INVALID_REQUEST", "Variants cannot mutate fixed_positions")
    source = body["scope_source"]
    ensure(isinstance(source, dict) and set(source) == {"purpose", "source_id"} and source["purpose"] == "ENGINEERING_STABILITY_SCOPE"
        and isinstance(source["source_id"], str) and 0 < len(source["source_id"]) <= 512, "INVALID_REQUEST", "Traceable FoldX scope is required")
    ensure(type(body["timeout_seconds"]) is int and 1 <= body["timeout_seconds"] <= 900, "INVALID_REQUEST", "Deadline must be 1..900 seconds")
    return body


def sequence_id(sequence):
    return "t01foldx_" + sha(sequence.encode())[:16]


def registered_rules():
    return dict(id="w6-foldx-repair-positionscan-buildmodel", version="0.1.0", sha256=sha(encode(dict(
        authority={p.relative_to(REPO).as_posix(): sha(p.read_bytes()) for p in AUTHORITY},
        files={p.name: sha(p.read_bytes()) for p in HERE.glob("*.py")},
        engine="FoldX 5.0", repair_required=True, scan_command="PositionScan", score_command="BuildModel",
        scan_sign="negative ddG stabilizing", scan_confidence=None, buildmodel_runs=5,
        buildmodel_confidence="std<=0.5 high; <=2 medium; >2 low", scientific_gate=False))))


def registered_profile():
    paths = list(HERE.glob("*.py")) + [HERE.parent / n for n in ("runtime.py", "registry.py", "contracts.py", "cli.py", "docker.py", "supervisor.py")]
    paths += list((REPO / "src/t01_structure_mapping").glob("*.py"))
    paths += [REPO / "requirements/foldx.Dockerfile"]
    return dict(id="w6-foldx-cpu-local-academic-candidate", version="0.1.0", sha256=sha(encode(dict(
        code={p.relative_to(REPO).as_posix(): sha(p.read_bytes()) for p in paths if p.is_file()}, image=IMAGE, limits=LIMITS,
        executable="foldx_20270131", package_sha256=sha((PACKAGE / "assets.json").read_bytes()) if (PACKAGE / "assets.json").is_file() else None,
        base=base_profile(), scientific_consumption=False, production_status="NOT_DEPLOYED"))))


def verify_assets():
    receipt = decode(read_locked(PACKAGE / "assets.json", 262144))
    ensure(receipt["required_version"] == "5.0" and receipt["executable"]["name"] == "foldx_20270131"
        and receipt["executable"]["sha256"] == EXECUTABLE_SHA256
        and receipt["image"] == IMAGE and receipt["image_status"] == "BUILT_VERIFIED"
        and receipt["license_basis"] == "USER_ATTESTED_ACADEMIC_VERSION", "ASSET_MISSING", "FoldX candidate asset registry mismatch")
    for item in receipt["files"]:
        path = no_links(REPO / item["path"])
        ensure(path.is_file() and path.stat().st_size == item["bytes"], "ASSET_MISSING", "Missing FoldX asset: " + item["path"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        ensure(digest == item["sha256"], "HASH_MISMATCH", "FoldX asset changed: " + item["path"])
    return receipt
