"""Validate native FoldX 5 output and assemble mode-specific results."""
import math
import re

from ...common import RuntimeFault, decode, ensure, sha
from . import policy


AA3 = {
    "A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE",
    "G": "GLY", "H": "HIS", "I": "ILE", "K": "LYS", "L": "LEU",
    "M": "MET", "N": "ASN", "P": "PRO", "Q": "GLN", "R": "ARG",
    "S": "SER", "T": "THR", "V": "VAL", "W": "TRP", "Y": "TYR",
}


def _finite(value):
    number = float(str(value).strip())
    ensure(math.isfinite(number), "OUTPUT_INVALID", "Non-finite FoldX value")
    return number


def _one(files, pattern):
    names = [name for name in files if re.fullmatch(pattern, name)]
    ensure(len(names) == 1, "OUTPUT_INVALID", "Expected exactly one FoldX output matching " + pattern)
    return names[0]


def _fxout(raw):
    header = None
    rows = []
    for line in raw.decode("utf-8", "strict").splitlines():
        if line.startswith("Pdb\t"):
            header = line.split("\t")
        elif header and line.strip():
            parts = line.split("\t")
            ensure(len(parts) == len(header), "OUTPUT_INVALID", "Malformed FoldX fxout row")
            rows.append(dict(zip(header, parts)))
    ensure(header is not None and rows, "OUTPUT_INVALID", "Missing FoldX fxout table")
    return rows


def _validate_repair(runtime, files):
    expected = ["/app/foldx_20270131", "--command=RepairPDB", "--pdb=target.pdb", "--pdb-dir=/native", "--output-dir=/out/repair"]
    ensure(runtime["commands"]["repair"] == {"argv": expected, "exit_code": 0}, "OUTPUT_INVALID", "RepairPDB command differs")
    repaired = runtime.get("repaired_pdb")
    ensure(repaired == "repair/target_Repair.pdb", "OUTPUT_INVALID", "Unexpected repaired PDB identity")
    ensure(files.get("output/" + repaired), "OUTPUT_INVALID", "Missing or empty repaired PDB")
    ensure(files.get("output/repair/target_Repair.fxout"), "OUTPUT_INVALID", "Missing or empty RepairPDB energy output")
    return repaired


def _positionscan(payload, runtime, files):
    expected = [
        "/app/foldx_20270131", "--command=PositionScan", "--pdb=target_Repair.pdb",
        "--pdb-dir=/out/repair", "--positions=" + ",".join(payload["scan_tokens"]),
        "--output-dir=/out/positionscan",
    ]
    ensure(runtime["commands"]["positionscan"] == {"argv": expected, "exit_code": 0}, "OUTPUT_INVALID", "PositionScan command differs")
    name = _one(files, r"output/positionscan/PS_.*_scanning_output\.txt")
    raw_rows = []
    for line in files[name].decode("utf-8", "strict").splitlines():
        parts = line.split("\t")
        ensure(len(parts) == 2 and re.fullmatch(r"[A-Z]{3}.+-?\d+[A-Z]", parts[0]), "OUTPUT_INVALID", "Malformed PositionScan row")
        raw_rows.append((parts[0], _finite(parts[1])))

    rows = []
    for mapping in payload["position_mapping"]:
        prefix = AA3[mapping["wt"]] + mapping["chain"] + str(mapping["pdb_resseq"])
        observed = {}
        for token, ddg in raw_rows:
            if token.startswith(prefix) and len(token) == len(prefix) + 1:
                observed.setdefault(token[-1], []).append(ddg)
        ensure(set(observed) == set(policy.ALPHABET), "OUTPUT_INVALID", "PositionScan does not cover exact AA20 at position " + str(mapping["position"]))
        for mut, values in observed.items():
            allowed = (1, 2) if mut == mapping["wt"] else (1,)
            ensure(len(values) in allowed and all(value == values[0] for value in values), "OUTPUT_INVALID", "Unexpected PositionScan duplicate")
        ensure(abs(observed[mapping["wt"]][0]) <= 1e-9, "OUTPUT_INVALID", "PositionScan WT self score must be zero")
        position = mapping["pdb_resseq"]
        for aa3 in AA3.values():
            pdb_name = "output/positionscan/" + aa3 + str(position) + "_target_Repair.pdb"
            ensure(files.get(pdb_name), "OUTPUT_INVALID", "Missing PositionScan mutant PDB: " + pdb_name)
        ensure(files.get("output/positionscan/energies_" + str(position) + "_target_Repair.txt"), "OUTPUT_INVALID", "Missing PositionScan energy detail")
        for mut in policy.ALPHABET:
            ddg = observed[mut][0]
            rows.append(dict(
                position=mapping["position"], wt=mapping["wt"], mut=mut, ddg_foldx=ddg,
                confidence=None, candidate_disposition="candidate" if ddg < -1.0 else "exclude" if ddg > 5.0 else "neutral",
                source=name,
            ))
    ensure(len(raw_rows) == len(payload["position_mapping"]) * 21, "OUTPUT_INVALID", "Unexpected PositionScan raw row count")
    rows.sort(key=lambda item: (item["position"], item["ddg_foldx"], item["mut"]))
    for position in sorted({row["position"] for row in rows}):
        for rank, row in enumerate((row for row in rows if row["position"] == position), 1):
            row["rank_foldx"] = rank
    return rows, dict(raw_rows=len(raw_rows), unique_rows=len(rows), wt_duplicate_rows=len(raw_rows) - len(rows), complete_native_output=True)


def _buildmodel(payload, runtime, files):
    expected = [
        "/app/foldx_20270131", "--command=BuildModel", "--pdb=target_Repair.pdb",
        "--pdb-dir=/out/repair", "--mutant-file=individual_list.txt", "--numberOfRuns=5",
        "--output-dir=/out/buildmodel",
    ]
    ensure(runtime["commands"]["buildmodel"] == {"argv": expected, "exit_code": 0}, "OUTPUT_INVALID", "BuildModel command differs")
    ensure(files.get("output/buildmodel/individual_list.txt") == ("\n".join(payload["variant_lines"]) + "\n").encode(), "OUTPUT_INVALID", "BuildModel mutation list differs")
    dif_name = _one(files, r"output/buildmodel/Dif_.*\.fxout")
    avg_name = _one(files, r"output/buildmodel/Average_.*\.fxout")
    _one(files, r"output/buildmodel/Raw_.*\.fxout")
    dif_rows = _fxout(files[dif_name])
    avg_rows = _fxout(files[avg_name])
    variants = [variant for variant in payload["variants"] if not variant["mapping_failed"]]
    ensure(len(dif_rows) == len(variants) * 5 and len(avg_rows) == len(variants), "OUTPUT_INVALID", "BuildModel output count differs from 5-run contract")
    grouped = {}
    for row in dif_rows:
        match = re.fullmatch(r"target_Repair_(\d+)_(\d+)\.pdb", row["Pdb"])
        ensure(match and 1 <= int(match.group(1)) <= len(variants) and 0 <= int(match.group(2)) < 5, "OUTPUT_INVALID", "Unexpected BuildModel model identity")
        ensure(int(match.group(2)) not in grouped.setdefault(int(match.group(1)), {}), "OUTPUT_INVALID", "Duplicate BuildModel run")
        grouped[int(match.group(1))][int(match.group(2))] = _finite(row["total energy"])
    results = []
    for index, variant in enumerate(variants, 1):
        values_by_run = grouped.get(index, {})
        ensure(set(values_by_run) == set(range(5)), "OUTPUT_INVALID", "BuildModel does not contain exactly five runs")
        for run in range(5):
            ensure(files.get("output/buildmodel/target_Repair_" + str(index) + "_" + str(run) + ".pdb"), "OUTPUT_INVALID", "Missing BuildModel mutant PDB")
            ensure(files.get("output/buildmodel/WT_target_Repair_" + str(index) + "_" + str(run) + ".pdb"), "OUTPUT_INVALID", "Missing BuildModel WT reference PDB")
        values = [values_by_run[run] for run in range(5)]
        mean = sum(values) / 5
        std = (sum((value - mean) ** 2 for value in values) / 5) ** 0.5
        avg = avg_rows[index - 1]
        ensure(avg["Pdb"] == "target_Repair_" + str(index), "OUTPUT_INVALID", "BuildModel average order differs")
        ensure(abs(_finite(avg["total energy"]) - mean) <= 1e-4 and abs(_finite(avg["SD"]) - std) <= 1e-4,
            "OUTPUT_INVALID", "BuildModel Average output differs from five native Dif runs")
        confidence = "high" if std <= 0.5 else "medium" if std <= 2.0 else "low"
        results.append(dict(variant_id=variant["variant_id"], ddg_foldx=mean, std=std, confidence=confidence, runs=5, native_ddg_runs=values, source=dif_name))
    return results, dict(variants=len(results), runs_per_variant=5, native_dif_rows=len(dif_rows), complete_native_output=True)


def parse(body, files):
    runtime = decode(files["output/runtime.json"])
    ensure(runtime["python_exit_code"] == 0 and runtime["network_interfaces"] == [[1, "lo"]] and runtime["cpu_affinity"] == [0, 1], "OUTPUT_INVALID", "No clean offline FoldX execution")
    ensure(runtime["input_sha256"] == sha(files["input.json"]) and runtime["input_fasta_sha256"] == sha(files["input.fasta"]), "OUTPUT_INVALID", "Executed request identity differs")
    ensure(runtime["executable_sha256"] == policy.verify_assets()["executable"]["sha256"], "OUTPUT_INVALID", "Executed FoldX executable differs")
    native_names = {name[7:]: sha(raw) for name, raw in files.items() if name.startswith("output/") and name != "output/runtime.json"}
    ensure(runtime["native_output_sha256"] == native_names, "OUTPUT_INVALID", "FoldX output inventory/hash mismatch")
    payload = decode(files["native/payload.json"])
    ensure(payload["mode"] == body["mode"] and payload["conversion_sha256"] == sha(files["native/conversion.json"]), "OUTPUT_INVALID", "FoldX mapping payload differs")
    repaired = _validate_repair(runtime, files)
    if payload["mapping_failures"]:
        ensure(not runtime["tool_invoked"], "OUTPUT_INVALID", "Mapped FoldX command must not run after a mapping failure")
        return dict(status="unreliable_mapping", rows=[], mapping_failures=payload["mapping_failures"], repaired_pdb=repaired, completeness=None, warnings=[])
    ensure(runtime["tool_invoked"], "OUTPUT_INVALID", "FoldX mode command was not invoked")
    rows, completeness = _positionscan(payload, runtime, files) if body["mode"] == "positionscan" else _buildmodel(payload, runtime, files)
    warnings = [] if body["mode"] == "buildmodel" else [dict(code="POSITIONSCAN_CONFIDENCE_NULL", level="quality", severity="WARNING", message="PositionScan lacks five-run standard deviation; confidence remains null")]
    return dict(status=body["mode"] + "_unreviewed", rows=rows, mapping_failures=[], repaired_pdb=repaired, completeness=completeness, warnings=warnings)


def result(job, body, files, execution, fault=None):
    binding = {key: job[key] for key in ("run_id", "request_id", "job_id", "attempt_id", "execution_identity", "execution_profile", "rule_profile")}
    binding.update(input_sha256=job["request_artifact"]["sha256"], sequence_sha256=sha(body["protein_sequence"].encode()), structure_artifact=body["structure_artifact"])
    value = dict(contract_version="0.1.0", tool_id=policy.TOOL, binding=binding, evidence_kind="G0_REAL_OUTPUT", qualification="DEVELOPMENT_UNREVIEWED", scientific_signoff=None,
        usable_for_pipeline=False, automatic_handoff=False, production_status="NOT_DEPLOYED", requires_review=True, execution=execution, controlled_fault=fault,
        status="unreliable", mode=body["mode"], repair=None, ddg_results=None, variant_ddg=None, native_completeness=None, scientific_gate="NOT_EVALUATED", null_reason=execution.get("error_code"), warnings=[], source_receipt=execution.get("source_receipt"),
        method_summary=dict(engine="FoldX", version="5.0", mode=body["mode"], rule_profile=job["rule_profile"], repair_required=True, scientific_permission_synthesis=False, cross_engine_averaging=False))
    if execution.get("error_code"):
        value["warnings"] = [dict(code=execution["error_code"], level="failure", severity="WARNING", message="FoldX 执行未完成；结果保持隔离：" + str(execution.get("diagnostic") or execution["error_code"]))]
        return value
    try:
        ensure(execution.get("stopped_confirmed") and execution.get("exit_code") == 0 and execution.get("image_id") == policy.IMAGE, "OUTPUT_INVALID", "No clean stopped pinned FoldX run")
        if fault == "corrupt_output":
            raise RuntimeFault("OUTPUT_INVALID", "Controlled native output corruption")
        parsed = parse(body, files)
        value.update(status=parsed["status"], repair=dict(repaired_pdb=parsed["repaired_pdb"], required=True), native_completeness=parsed["completeness"], null_reason=None, warnings=parsed["warnings"])
        if body["mode"] == "positionscan":
            value["ddg_results"] = parsed["rows"]
        else:
            value["variant_ddg"] = parsed["rows"]
        if parsed["mapping_failures"]:
            value["warnings"].append(dict(code="MAPPING_FAILED", level="failure", severity="WARNING", message="FoldX 编号映射失败，结果不可用于设计"))
    except (RuntimeFault, KeyError, ValueError, TypeError, IndexError, OSError, UnicodeError) as exc:
        execution.update(error_code="OUTPUT_INVALID", diagnostic=str(exc)); value["null_reason"] = "OUTPUT_INVALID"
        value["warnings"] = [dict(code="OUTPUT_INVALID", level="failure", severity="WARNING", message="FoldX 原生输出未通过校验，整组隔离；" + str(exc))]
    return value
