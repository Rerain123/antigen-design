"""Pinned official ThermoMPNN profile and explicit engineering scan scope."""
from pathlib import Path
import re

from ...common import REPO, decode, encode, ensure, profile as base_profile, sha
from ...files import no_links, read_locked
from ..glycosylation.policy import ARTIFACT_FIELDS


TOOL = "t01.real.thermompnn"
NODE = "N17"
HERE = Path(__file__).parent
PACKAGE = REPO / "var/t01-phase1-real/tool-assets/thermompnn-2b04fd370e39"
COMMIT = "2b04fd370e399911b1fa5848112cc9013f084110"
MODEL = "thermoMPNN_default.pt"
IMAGE = "sha256:3cbd3c12b792a8b344347e6e9171d03deb7c5a115a6c4b8af27b84847dfdd847"
SLOT = "t01p1r-thermompnn-development-slot"
LIMITS = dict(memory=6 * 1024**3, cpus=2, cpuset="0-1", pids=128)
ALPHABET = "ACDEFGHIKLMNPQRSTVWY"
AUTHORITY_ROOT = REPO / "工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902"
AUTHORITY = [
    AUTHORITY_ROOT / "ToolSpec_C43_ThermoMPNN_v10.5.md",
    AUTHORITY_ROOT / "ToolSpec_C35_FoldX_v10.5.md",
    AUTHORITY_ROOT / "AgentA_SOP_v10.5_20260902.md",
]


def artifact(ref):
    ensure(
        isinstance(ref, dict)
        and set(ref) == ARTIFACT_FIELDS
        and ref["role"] == "result"
        and ref["media_type"] == "application/json"
        and ref["evidence_kind"] == "G0_REAL_OUTPUT"
        and isinstance(ref["sha256"], str)
        and re.fullmatch("[0-9a-f]{64}", ref["sha256"])
        and type(ref["size_bytes"]) is int
        and 0 < ref["size_bytes"] <= 32 * 1024**2,
        "INVALID_REQUEST",
        "Registered successful structure ArtifactRef required",
    )


def request(raw):
    body = decode(raw)
    ensure(
        isinstance(body, dict)
        and set(body)
        == {
            "protein_sequence",
            "user_sequence_id",
            "structure_artifact",
            "scan_positions",
            "excluded_positions",
            "scope_source",
            "timeout_seconds",
        },
        "INVALID_REQUEST",
        "Exact ThermoMPNN engineering request required",
    )
    sequence = body["protein_sequence"]
    ensure(
        isinstance(sequence, str) and re.fullmatch("[" + ALPHABET + "]{1,1000}", sequence),
        "INVALID_REQUEST",
        "Exact uppercase AA20 sequence, 1..1000 aa required",
    )
    ensure(
        isinstance(body["user_sequence_id"], str) and 0 < len(body["user_sequence_id"]) <= 512,
        "INVALID_REQUEST",
        "Bounded user sequence label required",
    )
    artifact(body["structure_artifact"])
    for key in ("scan_positions", "excluded_positions"):
        positions = body[key]
        ensure(
            isinstance(positions, list)
            and len(positions) == len(set(positions))
            and positions == sorted(positions)
            and all(type(position) is int and 1 <= position <= len(sequence) for position in positions),
            "INVALID_REQUEST",
            key + " must be unique sorted 1-based sequence positions",
        )
    ensure(
        0 < len(body["scan_positions"]) <= len(sequence),
        "INVALID_REQUEST",
        "Explicit scan scope must contain 1..sequence-length positions",
    )
    source = body["scope_source"]
    ensure(
        isinstance(source, dict)
        and set(source) == {"purpose", "source_id"}
        and source["purpose"] == "ENGINEERING_EXPLICIT_SCAN_SCOPE"
        and isinstance(source["source_id"], str)
        and 0 < len(source["source_id"]) <= 512,
        "INVALID_REQUEST",
        "Explicit traceable engineering scan scope is required",
    )
    ensure(
        type(body["timeout_seconds"]) is int and 1 <= body["timeout_seconds"] <= 900,
        "INVALID_REQUEST",
        "Deadline must be 1..900 seconds",
    )
    return body


def sequence_id(sequence):
    return "t01tmpnn_" + sha(sequence.encode())[:16]


def registered_rules():
    return dict(
        id="w6-thermompnn-full-native-ssm-engineering",
        version="0.1.0",
        sha256=sha(
            encode(
                dict(
                    authority={path.relative_to(REPO).as_posix(): sha(path.read_bytes()) for path in AUTHORITY},
                    files={path.name: sha(path.read_bytes()) for path in HERE.glob("*.py")},
                    commit=COMMIT,
                    native_output="20 amino-acid rows per covered residue, including WT self row",
                    selected_comparison="explicit scan positions minus explicit exclusions; WT self rows unranked",
                    sign_transform=None,
                    scientific_gate=False,
                )
            )
        ),
    )


def registered_profile():
    paths = list(HERE.glob("*.py")) + list(HERE.glob("*.json"))
    paths += [HERE.parent / name for name in ("runtime.py", "registry.py", "contracts.py", "cli.py", "docker.py", "supervisor.py")]
    paths += list((HERE.parent / "proteinmpnn").glob("*.py"))
    paths += list((REPO / "src/t01_structure_mapping").glob("*.py"))
    paths.append(REPO / "requirements/thermompnn.Dockerfile")
    return dict(
        id="w6-thermompnn-gpu-local-development",
        version="0.1.0",
        sha256=sha(
            encode(
                dict(
                    code={path.relative_to(REPO).as_posix(): sha(path.read_bytes()) for path in paths},
                    image=IMAGE,
                    limits=LIMITS,
                    device="cuda:0",
                    official_commit=COMMIT,
                    official_entrypoint="analysis/custom_inference.py",
                    full_output_strategy="unfiltered official custom inference plus exact 20xL coverage validation",
                    base=base_profile(),
                    scientific_consumption=False,
                )
            )
        ),
    )


def verify_assets():
    receipt = decode(read_locked(HERE / "assets.json", 262144))
    ensure(
        receipt["commit"] == COMMIT and receipt["image"] == IMAGE and receipt["model"] == MODEL,
        "ASSET_MISSING",
        "Pinned ThermoMPNN asset registry mismatch",
    )
    for item in receipt["files"]:
        path = no_links(REPO / item["path"])
        ensure(
            path.is_file() and path.stat().st_size == item["bytes"],
            "ASSET_MISSING",
            "Missing ThermoMPNN asset: " + item["path"],
        )
        import hashlib

        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024**2), b""):
                digest.update(block)
        ensure(digest.hexdigest() == item["sha256"], "HASH_MISMATCH", "ThermoMPNN asset changed: " + item["path"])
    return receipt
