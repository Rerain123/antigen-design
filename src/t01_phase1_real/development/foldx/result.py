"""Validate native FoldX 5 output and assemble mode-specific results."""
import math
import re

from ...common import RuntimeFault, decode, ensure, sha
from . import policy
from ...resident_result import image_matches, isolation_matches


AA3 = {
    "A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE",
    "G": "GLY", "H": "HIS", "I": "ILE", "K": "LYS", "L": "LEU",
    "M": "MET", "N": "ASN", "P": "PRO", "Q": "GLN", "R": "ARG",
    "S": "SER", "T": "THR", "V": "VAL", "W": "TRP", "Y": "TYR",
}
NATIVE_MUTATION = {**{aa: aa for aa in AA3}, "e": "H", "o": "H"}


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


def _positionscan_one(payload, runtime, files, directory='positionscan'):
    expected = [
        "/app/foldx_20270131", "--command=PositionScan", "--pdb=target_Repair.pdb",
        "--pdb-dir=/out/repair", "--positions=" + ",".join(payload["scan_tokens"]),
        "--output-dir=/out/"+directory,
    ]
    ensure(runtime["commands"]["positionscan"] == {"argv": expected, "exit_code": 0}, "OUTPUT_INVALID", "PositionScan command differs")
    name = _one(files, r"output/"+re.escape(directory)+r"/PS_.*_scanning_output\.txt")
    raw_rows = []
    for line in files[name].decode("utf-8", "strict").splitlines():
        parts = line.split("\t")
        ensure(len(parts) == 2 and re.fullmatch(r"[A-Z]{3}.+-?\d+[A-Za-z]", parts[0]), "OUTPUT_INVALID", "Malformed PositionScan row")
        raw_rows.append((parts[0], _finite(parts[1])))

    rows = []
    for mapping in payload["position_mapping"]:
        prefix = AA3[mapping["wt"]] + mapping["chain"] + str(mapping["pdb_resseq"])
        observed = {}
        matched = []
        for token, ddg in raw_rows:
            if token.startswith(prefix) and len(token) == len(prefix) + 1:
                ensure(token[-1] in NATIVE_MUTATION, "OUTPUT_INVALID", "Unknown FoldX native mutation code")
                observed.setdefault(NATIVE_MUTATION[token[-1]], []).append(ddg)
                matched.append((NATIVE_MUTATION[token[-1]], ddg))
        ensure(set(observed) == set(policy.ALPHABET), "OUTPUT_INVALID", "PositionScan does not cover exact AA20 at position " + str(mapping["position"]))
        # Official PositionScan output starts with the new WT reference, then
        # scans AA20, including a separate self mutation. These two energies
        # need not match (https://foldxsuite.crg.eu/command/PositionScan).
        ensure(len(matched) == 21 and matched[0][0] == mapping['wt'],
               'OUTPUT_INVALID', 'PositionScan requires leading WT reference plus AA20')
        for mut, values in observed.items():
            ensure(len(values) == (2 if mut == mapping['wt'] else 1),
                   'OUTPUT_INVALID', 'Unexpected PositionScan duplicate')
        position = mapping["pdb_resseq"]
        for aa3 in AA3.values():
            pdb_name = "output/"+directory+"/" + aa3 + str(position) + "_target_Repair.pdb"
            ensure(files.get(pdb_name), "OUTPUT_INVALID", "Missing PositionScan mutant PDB: " + pdb_name)
        ensure(files.get("output/"+directory+"/energies_" + str(position) + "_target_Repair.txt"), "OUTPUT_INVALID", "Missing PositionScan energy detail")
        for mut in policy.ALPHABET:
            ddg = observed[mut][-1]
            rows.append(dict(
                position=mapping["position"], wt=mapping["wt"], mut=mut, ddg_foldx=ddg,
                confidence=None, candidate_disposition="candidate" if ddg < -1.0 else "exclude" if ddg > 5.0 else "neutral",
                source=name,
            ))
            if mut == mapping['wt'] and observed[mut][0] != observed[mut][-1]:
                rows[-1].update(native_wt_reference_ddg=observed[mut][0],
                                native_wt_self_ddg=observed[mut][-1],
                                native_self_observation=True)
    ensure(len(raw_rows) == len(payload["position_mapping"]) * 21, "OUTPUT_INVALID", "Unexpected PositionScan raw row count")
    rows.sort(key=lambda item: (item["position"], item["ddg_foldx"], item["mut"]))
    for position in sorted({row["position"] for row in rows}):
        for rank, row in enumerate((row for row in rows if row["position"] == position), 1):
            row["rank_foldx"] = rank
    return rows, dict(raw_rows=len(raw_rows), unique_rows=len(rows), wt_duplicate_rows=len(raw_rows) - len(rows), complete_native_output=True)


def _positionscan(payload,runtime,files):
    if 'scan_batches' not in runtime:return _positionscan_one(payload,runtime,files)
    from .scan_batches import plan,unpack
    expected=plan(payload);actual=runtime['scan_batches']
    ensure(len(actual)==len(expected),'OUTPUT_INVALID','FoldX batch count incomplete')
    ensure(decode(files['output/scan-plan.json'])==dict(positions_per_batch=16,batches=expected,repair_reused=True)
           and decode(files['output/scan-progress.json'])==dict(completed=actual,total=len(expected))
           and {n for n in files if n.startswith('output/batches/')}==
               {f"output/batches/{b['index']:04d}.zip" for b in expected},
           'OUTPUT_INVALID','FoldX batch plan/progress/archive inventory differs')
    rows=[];totals=dict(raw_rows=0,unique_rows=0,wt_duplicate_rows=0,complete_native_output=True)
    for batch,record in zip(expected,actual):
        directory=f"batches/{batch['index']:04d}";name='output/'+directory+'.zip'
        ensure(all(record.get(k)==v for k,v in batch.items()) and record['exit_code']==0
               and record['archive']==directory+'.zip' and name in files
               and sha(files[name])==record['sha256'] and len(files[name])==record['size_bytes'],
               'OUTPUT_INVALID','FoldX batch identity/coverage differs')
        unpacked=unpack(files[name])
        ensure(len(unpacked)==record['members'] and sum(map(len,unpacked.values()))==record['expanded_bytes'],
               'OUTPUT_INVALID','FoldX batch member inventory differs')
        local={'output/'+directory+'/'+n:raw for n,raw in unpacked.items()}
        parsed,stats=_positionscan_one(dict(payload,**{k:batch[k] for k in ('scan_tokens','position_mapping')}),
            dict(commands=dict(positionscan=dict(argv=record['argv'],exit_code=0))),local,directory)
        for r in parsed:r['source']=name+'!/'+r['source'][len('output/'+directory+'/'):]
        rows.extend(parsed)
        for k in ('raw_rows','unique_rows','wt_duplicate_rows'):totals[k]+=stats[k]
    ensure(len({(r['position'],r['mut']) for r in rows})==len(payload['position_mapping'])*20,
           'OUTPUT_INVALID','FoldX merged coverage differs')
    totals.update(batch_count=len(expected),repair_reused=True)
    return rows,totals


def _buildmodel(payload, runtime, files):
    if 'buildmodel_parallel' in runtime:
        from .parallel import verified_batches, command
        variants = [v for v in payload['variants'] if not v['mapping_failed']]
        rows = []
        for batch, name, members in verified_batches(payload, runtime, files):
            local = {'output/buildmodel/' + n: raw for n, raw in members.items()}
            one = dict(payload, variants=[variants[batch['index'] - 1]], variant_lines=[batch['mutation_line']])
            # A read-only logical view invokes the same five-run parser. Original
            # files, local model indices and recorded commands remain unchanged.
            parsed, _ = _buildmodel(one, dict(commands=dict(buildmodel=dict(argv=command('buildmodel'), exit_code=0))), local)
            for row in parsed:
                row['source'] = name + '!/' + row['source'].removeprefix('output/buildmodel/')
            rows.extend(parsed)
        return rows, dict(variants=len(rows), runs_per_variant=5, native_dif_rows=len(rows)*5,
                          complete_native_output=True, parallel_workers=2, serial_equivalence=False)
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
    archives=runtime.get('buildmodel_archives')
    if archives is not None:
        ensure(isinstance(archives,list) and len(archives)==len(variants) and
               {n for n in files if n.startswith('output/buildmodel/batches/')}==
               {f'output/buildmodel/batches/{i:04d}.zip' for i in range(1,len(variants)+1)} and
               not any(n.startswith('output/buildmodel/') and n.endswith('.pdb') for n in files),
               'OUTPUT_INVALID','BuildModel archive coverage differs')
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
        pdb_files=files
        if archives is not None:
            from .scan_batches import unpack,model_names
            record=archives[index-1];name=f'buildmodel/batches/{index:04d}.zip';raw=files['output/'+name]
            ensure(record.get('index')==index and record.get('archive')==name and
                   record.get('sha256')==sha(raw) and record.get('size_bytes')==len(raw),
                   'OUTPUT_INVALID','BuildModel archive identity/hash differs')
            models=unpack(raw)
            ensure(set(models)==set(model_names(index)) and record.get('members')==10 and
                   record.get('expanded_bytes')==sum(map(len,models.values())) and
                   record.get('member_sha256')=={n:sha(v) for n,v in models.items()},
                   'OUTPUT_INVALID','BuildModel native PDB inventory differs')
            pdb_files={'output/buildmodel/'+n:v for n,v in models.items()}
        for run in range(5):
            ensure(pdb_files.get("output/buildmodel/target_Repair_" + str(index) + "_" + str(run) + ".pdb"), "OUTPUT_INVALID", "Missing BuildModel mutant PDB")
            ensure(pdb_files.get("output/buildmodel/WT_target_Repair_" + str(index) + "_" + str(run) + ".pdb"), "OUTPUT_INVALID", "Missing BuildModel WT reference PDB")
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
    ensure(runtime["python_exit_code"] == 0 and isolation_matches(runtime, files, policy.IMAGE, [0, 1]), "OUTPUT_INVALID", "No clean offline FoldX execution")
    ensure(runtime["input_sha256"] == sha(files["input.json"]) and runtime["input_fasta_sha256"] == sha(files["input.fasta"]), "OUTPUT_INVALID", "Executed request identity differs")
    ensure(runtime["executable_sha256"] == policy.verify_assets()["executable"]["sha256"], "OUTPUT_INVALID", "Executed FoldX executable differs")
    native_names = {name[7:]: sha(raw) for name, raw in files.items() if name.startswith("output/") and name != "output/runtime.json"}
    ensure(runtime["native_output_sha256"] == native_names, "OUTPUT_INVALID", "FoldX output inventory/hash mismatch")
    payload = decode(files["native/payload.json"])
    ensure(payload["mode"] == body["mode"] and payload["conversion_sha256"] == sha(files["native/conversion.json"]), "OUTPUT_INVALID", "FoldX mapping payload differs")
    repaired = _validate_repair(runtime, files)
    if payload["mapping_failures"] and not runtime["tool_invoked"]:
        # Older whole-batch skips retain their original interpretation.
        return dict(status="unreliable_mapping", rows=[], mapping_failures=payload["mapping_failures"], repaired_pdb=repaired, completeness=None, warnings=[])
    if payload["mapping_failures"]:
        ensure(body['mode']=='buildmodel' and payload['variant_lines'] and
               any(not v['mapping_failed'] for v in payload['variants']),
               'OUTPUT_INVALID','Only mapped BuildModel variants may continue after mapping failure')
    ensure(runtime["tool_invoked"], "OUTPUT_INVALID", "FoldX mode command was not invoked")
    rows, completeness = _positionscan(payload, runtime, files) if body["mode"] == "positionscan" else _buildmodel(payload, runtime, files)
    warnings = [] if body["mode"] == "buildmodel" else [dict(code="POSITIONSCAN_CONFIDENCE_NULL", level="quality", severity="WARNING", message="PositionScan lacks five-run standard deviation; confidence remains null")]
    if 'buildmodel_parallel' in runtime:
        from .parallel import MARKER, NOTICE
        warnings.append(dict(code=MARKER, level='quality', severity='WARNING', message=NOTICE))
    if any(row.get('native_self_observation') for row in rows):
        warnings.append(dict(code='POSITIONSCAN_WT_REFERENCE_AND_SELF_DIFFER', level='quality', severity='WARNING',
                             message='Native leading WT reference and scanned WT self energies retained separately; no zero substitution'))
    return dict(status=body["mode"] + "_unreviewed", rows=rows, mapping_failures=payload['mapping_failures'], repaired_pdb=repaired, completeness=completeness, warnings=warnings)


def result(job, body, files, execution, fault=None):
    binding = {key: job[key] for key in ("run_id", "request_id", "job_id", "attempt_id", "execution_identity", "execution_profile", "rule_profile")}
    binding.update(input_sha256=job["request_artifact"]["sha256"], sequence_sha256=sha(body["protein_sequence"].encode()), structure_artifact=body["structure_artifact"])
    value = dict(contract_version="0.1.0", tool_id=policy.TOOL, binding=binding, evidence_kind="G0_REAL_OUTPUT", qualification="DEVELOPMENT_UNREVIEWED", scientific_signoff=None,
        usable_for_pipeline=False, automatic_handoff=False, production_status="NOT_DEPLOYED", requires_review=True, execution=execution, controlled_fault=fault,
        status="unreliable", mode=body["mode"], repair=None, ddg_results=None, variant_ddg=None, native_completeness=None, scientific_gate="NOT_EVALUATED", null_reason=execution.get("error_code"), warnings=[], source_receipt=execution.get("source_receipt"),
        method_summary=dict(engine="FoldX", version="5.0", mode=body["mode"], rule_profile=job["rule_profile"], repair_required=True, scientific_permission_synthesis=False, cross_engine_averaging=False))
    adjustment=[]
    if 'output/buildmodel-plan.json' in files:
        from .parallel import MARKER, NOTICE, plan
        try:
            if decode(files['output/buildmodel-plan.json'])==plan(decode(files['native/payload.json'])):
                adjustment=[dict(code=MARKER,level='quality',severity='WARNING',message=NOTICE)]
        except (KeyError,ValueError,TypeError,RuntimeFault):
            pass
    if execution.get("error_code"):
        value["warnings"] = adjustment+[dict(code=execution["error_code"], level="failure", severity="WARNING", message="FoldX 执行未完成；结果保持隔离：" + str(execution.get("diagnostic") or execution["error_code"]))]
        return value
    try:
        ensure(execution.get("stopped_confirmed") and execution.get("exit_code") == 0 and image_matches(execution, policy.IMAGE), "OUTPUT_INVALID", "No clean stopped pinned FoldX run")
        if fault == "corrupt_output":
            raise RuntimeFault("OUTPUT_INVALID", "Controlled native output corruption")
        parsed = parse(body, files)
        value.update(status=parsed["status"], repair=dict(repaired_pdb=parsed["repaired_pdb"], required=True), native_completeness=parsed["completeness"], null_reason=None, warnings=parsed["warnings"])
        if body["mode"] == "positionscan":
            value["ddg_results"] = parsed["rows"]
        else:
            value["variant_ddg"] = parsed["rows"]
        if parsed["mapping_failures"]:
            payload=decode(files['native/payload.json'])
            value['mapping_skipped_variants']=[dict(variant_id=v['variant_id'],positions=v['mapping_failed_positions'])
                for v in payload['variants'] if v['mapping_failed']]
            value["warnings"].append(dict(code="MAPPING_FAILED", level="failure", severity="WARNING",
                message="部分候选编号映射失败并跳过；仅保留已验证的其余候选五轮结果" if parsed['rows'] else "FoldX 编号映射失败，本批无可用结果"))
    except (RuntimeFault, KeyError, ValueError, TypeError, IndexError, OSError, UnicodeError) as exc:
        execution.update(error_code="OUTPUT_INVALID", diagnostic=str(exc)); value["null_reason"] = "OUTPUT_INVALID"
        value["warnings"] = adjustment+[dict(code="OUTPUT_INVALID", level="failure", severity="WARNING", message="FoldX 原生输出未通过校验，整组隔离；" + str(exc))]
    return value
