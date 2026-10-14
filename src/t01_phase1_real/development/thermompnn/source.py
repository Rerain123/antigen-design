"""Verified local-structure projection and explicit ThermoMPNN scan scope."""
from ...common import decode, encode, ensure, sha
from ..proteinmpnn.source import sources as structure_sources
from . import policy


def sources(runtime, database, body, expected_run_id=None):
    projected = dict(body)
    projected["constraints"] = dict(
        purpose="ENGINEERING_EXPLICIT_MASKS",
        source_id=body["scope_source"]["source_id"],
        fixed_positions=[],
        restricted_positions=[],
        open_positions=list(range(1, len(body["protein_sequence"]) + 1)),
    )
    files, structure_receipt = structure_sources(
        runtime, database, projected, expected_run_id=expected_run_id
    )
    conversion = decode(files["native/conversion.json"])
    rows = conversion["rows"]
    target = conversion["target_chain"]
    target_rows = [row for row in rows if row["chain_id"] == target]
    ensure(
        len(target_rows) == len(body["protein_sequence"])
        and [row["sequence_position"] for row in target_rows] == list(range(1, len(body["protein_sequence"]) + 1)),
        "OUTPUT_INVALID",
        "ThermoMPNN requires complete unique target-chain mapping",
    )
    selected = [position for position in body["scan_positions"] if position not in set(body["excluded_positions"])]
    payload = dict(
        protein_sequence=body["protein_sequence"],
        target_chain=target,
        chain_sequences=conversion["chain_sequences"],
        scan_positions=body["scan_positions"],
        excluded_positions=body["excluded_positions"],
        effective_positions=selected,
        scope_source=body["scope_source"],
        conversion_sha256=sha(files["native/conversion.json"]),
        source_structure_sha256=conversion["source_structure_sha256"],
    )
    files["native/payload.json"] = encode(payload)
    files["native/runtime-local.yaml"] = (policy.PACKAGE / "runtime-local.yaml").read_bytes()
    receipt = dict(
        structure=structure_receipt,
        structure_artifact=body["structure_artifact"],
        target_chain=target,
        protein_chain_count=len(conversion["chain_sequences"]),
        source_structure_sha256=conversion["source_structure_sha256"],
        projected_structure_sha256=sha(files["native/target.pdb"]),
        conversion_sha256=payload["conversion_sha256"],
        scan_scope_sha256=sha(encode({key: body[key] for key in ("scan_positions", "excluded_positions", "scope_source")})),
        r39_disposition="RUN_SINGLE_CHAIN" if len(conversion["chain_sequences"]) == 1 else "SKIP_MULTICHAIN",
        prepared_hashes={name: sha(raw) for name, raw in files.items()},
    )
    return files, receipt
