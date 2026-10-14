"""Prepare a structure-bound FoldX request and auditable mapping payload."""
from ...common import decode, encode, ensure, sha
from ..proteinmpnn.source import sources as structure_sources
from . import policy


def _foldx_token(row, mutation=None, scan=False):
    if row.get("insertion_code") not in (None, "", " "):
        return None
    chain = row["chain_id"]
    # FoldX consumes the repaired canonical PDB emitted by the projection; its
    # auth_seq_id is therefore the reversible tool_pdb_resseq (1-based).
    resseq = row["tool_pdb_resseq"]
    wt = row["residue"]
    if scan:
        return wt + chain + str(resseq) + "a"
    # Position mapping rows record the address prefix before a concrete
    # BuildModel mutation is selected; variant rows append the target AA.
    return wt + chain + str(resseq) + (mutation or "")


def sources(runtime, database, body, expected_run_id=None):
    projected = dict(body)
    projected["constraints"] = dict(
        purpose="ENGINEERING_EXPLICIT_MASKS", source_id=body["scope_source"]["source_id"],
        fixed_positions=body["fixed_positions"], restricted_positions=[],
        open_positions=[p for p in body["scan_positions"] if p not in set(body["fixed_positions"])],
    )
    # ProteinMPNN's structure projection is the already-registered local mapping path.
    files, structure_receipt = structure_sources(
        runtime, database, projected, expected_run_id=expected_run_id,pdb_format_projection=True
    )
    conversion = decode(files["native/conversion.json"])
    target = conversion["target_chain"]
    rows = [row for row in conversion["rows"] if row["chain_id"] == target]
    ensure(len(rows) == len(body["protein_sequence"]) and [row["sequence_position"] for row in rows] == list(range(1, len(body["protein_sequence"]) + 1)),
        "OUTPUT_INVALID", "FoldX requires complete unique target-chain mapping")
    by_position = {row["sequence_position"]: row for row in rows}
    mapping = []
    mapping_failures = []
    positions = body["scan_positions"] if body["mode"] == "positionscan" else sorted({m["position"] for v in body["variants"] for m in v["mutations"]})
    positions = [position for position in positions if position not in set(body["fixed_positions"])]
    for position in positions:
        row = by_position[position]
        token = _foldx_token(row, scan=body["mode"] == "positionscan")
        item = dict(position=position, wt=row["residue"], chain=target, pdb_resseq=row["tool_pdb_resseq"], original_auth_resseq=row["author_resseq"], icode=row.get("insertion_code"), foldx_token=token, mapping_failed=token is None)
        mapping.append(item)
        if token is None: mapping_failures.append(item)
    variant_lines = []
    variants = []
    for variant in body["variants"]:
        tokens = []
        failures = []
        for mutation in variant["mutations"]:
            row = by_position[mutation["position"]]
            token = _foldx_token(row, mutation=mutation["mut"], scan=False)
            if token is None: failures.append(mutation["position"])
            else: tokens.append(token)
        variant_item = dict(variant_id=variant["variant_id"], tokens=tokens, mapping_failed=bool(failures), mapping_failed_positions=failures)
        variants.append(variant_item)
        if not failures: variant_lines.append(",".join(tokens) + ";")
    payload = dict(
        protein_sequence=body["protein_sequence"], target_chain=target, chain_sequences=conversion["chain_sequences"],
        mode=body["mode"], fixed_positions=body["fixed_positions"], scan_positions=body["scan_positions"],
        variants=variants, position_mapping=mapping, mapping_failures=mapping_failures,
        scope_source=body["scope_source"], conversion_sha256=sha(files["native/conversion.json"]),
        source_structure_sha256=conversion["source_structure_sha256"],
        scan_tokens=[item["foldx_token"] for item in mapping if item["foldx_token"]], variant_lines=variant_lines,
    )
    files["native/payload.json"] = encode(payload)
    files["native/individual_list.txt"] = ("\n".join(variant_lines) + ("\n" if variant_lines else "")).encode()
    receipt = dict(
        structure=structure_receipt, structure_artifact=body["structure_artifact"], target_chain=target,
        source_structure_sha256=conversion["source_structure_sha256"], projected_structure_sha256=sha(files["native/target.pdb"]),
        conversion_sha256=payload["conversion_sha256"], mode=body["mode"], mapping_failures=mapping_failures,
        source_sha256=sha(encode({"mode": body["mode"], "scan_positions": body["scan_positions"], "variants": body["variants"]})),
        prepared_hashes={name: sha(raw) for name, raw in files.items()},
    )
    return files, receipt
