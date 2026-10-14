"""ThermoMPNN native output coverage, mapping and signed ddG validation."""
import csv
import io
import math

from ...common import RuntimeFault, decode, encode, ensure, sha
from . import policy


def finite(value):
    value = float(value)
    ensure(math.isfinite(value), "OUTPUT_INVALID", "Non-finite ThermoMPNN ddG")
    return value


def validate_observation(body, files):
    runtime = decode(files["output/runtime.json"])
    receipt = decode((policy.HERE / "assets.json").read_bytes())
    environment = receipt["environment"]
    ensure(
        runtime["python_exit_code"] == 0
        and runtime["official_source_modified"] is False
        and runtime["network_interfaces"] == [[1, "lo"]]
        and runtime["cpu_affinity"] == [0, 1],
        "OUTPUT_INVALID",
        "No clean offline ThermoMPNN execution",
    )
    for key in (
        "python",
        "torch",
        "cuda",
        "pandas",
        "biopython",
        "omegaconf",
        "pytorch_lightning",
        "torchmetrics",
        "scikit_learn",
        "scipy",
        "gpu_name",
        "gpu_capability",
    ):
        ensure(runtime[key] == environment[key], "OUTPUT_INVALID", "ThermoMPNN environment differs: " + key)
    ensure(runtime["gpu_available"] is True, "OUTPUT_INVALID", "Pinned ThermoMPNN GPU unavailable")
    ensure(
        runtime["input_sha256"] == sha(files["input.json"])
        and runtime["input_fasta_sha256"] == sha(files["input.fasta"]),
        "OUTPUT_INVALID",
        "Executed ThermoMPNN request identity differs",
    )
    expected_assets = {item["package_path"]: item["sha256"] for item in receipt["files"]}
    ensure(runtime["source_sha256"] == expected_assets, "OUTPUT_INVALID", "Executed official ThermoMPNN assets differ")
    inventory = runtime["native_output_sha256"]
    ensure(
        set(inventory) == {name[7:] for name in files if name.startswith("output/") and name != "output/runtime.json"}
        and all(sha(files["output/" + name]) == digest for name, digest in inventory.items()),
        "OUTPUT_INVALID",
        "ThermoMPNN native output inventory/hash mismatch",
    )
    expected_native = {path[7:]: sha(raw) for path, raw in files.items() if path.startswith("native/")}
    ensure(runtime["native_input_sha256"] == expected_native, "OUTPUT_INVALID", "ThermoMPNN staged native input differs")
    payload = decode(files["native/payload.json"])
    conversion = decode(files["native/conversion.json"])
    ensure(
        payload["protein_sequence"] == body["protein_sequence"]
        and payload["scan_positions"] == body["scan_positions"]
        and payload["excluded_positions"] == body["excluded_positions"]
        and payload["conversion_sha256"] == sha(files["native/conversion.json"]),
        "OUTPUT_INVALID",
        "ThermoMPNN native request projection differs",
    )
    observation = decode(files["output/observation.json"])
    if len(payload["chain_sequences"]) > 1:
        ensure(
            observation
            == dict(
                status="skipped_multichain",
                reason_code="R39_THERMOMPNN_MONOMER_ONLY",
                protein_chain_count=len(payload["chain_sequences"]),
                target_chain=payload["target_chain"],
                tool_invoked=False,
            )
            and runtime["tool_invoked"] is False
            and not any(name.startswith("output/native/") for name in files),
            "OUTPUT_INVALID",
            "R-39 multi-chain skip was not preserved",
        )
        return dict(
            status="skipped_multichain",
            reason_code="R39_THERMOMPNN_MONOMER_ONLY",
            complete_native_output=False,
            native_prediction_count=0,
            expected_native_prediction_count=0,
            effective_positions=[],
            predictions=[],
            conversion=conversion,
            engine_runtime=runtime,
        )
    ensure(runtime["tool_invoked"] is True and runtime["model_loaded_by_official_cli"] is True, "OUTPUT_INVALID", "ThermoMPNN CLI was not executed")
    help_text = files["output/native-help.txt"]
    ensure(
        all(flag in help_text for flag in (b"--pdb", b"--chain", b"--model_path", b"--out_dir"))
        and b"--threshold" not in help_text
        and runtime["threshold_parameter"] is False,
        "OUTPUT_INVALID",
        "Pinned official ThermoMPNN CLI capability differs",
    )
    command = runtime["commands"]["scan"]["argv"]
    expected_command = [
        command[0],
        "-B",
        "/app/analysis/custom_inference.py",
        "--pdb",
        "/native/target.pdb",
        "--chain",
        payload["target_chain"],
        "--model_path",
        "/app/models/thermoMPNN_default.pt",
        "--out_dir",
        "/out/native",
    ]
    ensure(command == expected_command and runtime["commands"]["scan"]["exit_code"] == 0, "OUTPUT_INVALID", "Official ThermoMPNN arguments differ")
    raw_csv = files["output/native/ThermoMPNN_inference_target.csv"]
    ensure(observation["native_csv_sha256"] == sha(raw_csv), "OUTPUT_INVALID", "ThermoMPNN observation CSV hash differs")
    rows = list(csv.DictReader(io.StringIO(raw_csv.decode("utf-8"))))
    sequence = body["protein_sequence"]
    ensure(len(rows) == 20 * len(sequence), "OUTPUT_INVALID", "ThermoMPNN did not emit complete 20xL native predictions")
    by_position = {position: [] for position in range(len(sequence))}
    for index, row in enumerate(rows):
        ensure(
            set(row) == {"", "Model", "Dataset", "ddG_pred", "position", "wildtype", "mutation", "pdb", "chain"}
            and int(row[""]) == index
            and row["Model"] == "ThermoMPNN"
            and row["Dataset"] == "target"
            and row["pdb"] == "target"
            and row["chain"] == payload["target_chain"],
            "OUTPUT_INVALID",
            "ThermoMPNN native row identity/format differs",
        )
        position = int(row["position"])
        ensure(0 <= position < len(sequence), "OUTPUT_INVALID", "ThermoMPNN native position outside sequence")
        ensure(row["wildtype"] == sequence[position] and row["mutation"] in policy.ALPHABET, "OUTPUT_INVALID", "ThermoMPNN residue identity differs")
        ddg = finite(row["ddG_pred"])
        if row["mutation"] == row["wildtype"]:
            ensure(abs(ddg) <= 1e-7, "OUTPUT_INVALID", "ThermoMPNN WT self prediction is not zero")
        by_position[position].append((row["mutation"], ddg))
    ensure(
        all([mutation for mutation, _ in values] == list(policy.ALPHABET) for values in by_position.values()),
        "OUTPUT_INVALID",
        "ThermoMPNN native mutation alphabet/order is incomplete",
    )
    excluded = set(body["excluded_positions"])
    effective = [position for position in body["scan_positions"] if position not in excluded]
    addresses = {row["sequence_position"]: row for row in conversion["rows"] if row["chain_id"] == payload["target_chain"]}
    candidates = []
    self_rows = []
    for position in effective:
        ensure(position in addresses, "OUTPUT_INVALID", "Selected ThermoMPNN position has no unique author mapping")
        address = addresses[position]
        for mutation, ddg in by_position[position - 1]:
            item = dict(
                position=position,
                native_position_zero_based=position - 1,
                wt=sequence[position - 1],
                mut=mutation,
                ddg_thermompnn=ddg,
                unit="kcal/mol",
                rank_thermompnn=None,
                author_address=dict(
                    chain_id=address["chain_id"],
                    auth_seq_id=address["author_resseq"],
                    insertion_code=address["insertion_code"],
                ),
                mapping_failed=False,
                is_wt_self=mutation == sequence[position - 1],
            )
            (self_rows if item["is_wt_self"] else candidates).append(item)
    ordered = sorted(candidates, key=lambda item: (item["ddg_thermompnn"], item["position"], item["mut"]))
    for rank, item in enumerate(ordered, 1):
        item["rank_thermompnn"] = rank
    predictions = sorted(ordered + self_rows, key=lambda item: (item["position"], policy.ALPHABET.index(item["mut"])))
    return dict(
        status="predicted_unreviewed",
        reason_code=None,
        complete_native_output=True,
        native_prediction_count=len(rows),
        expected_native_prediction_count=20 * len(sequence),
        native_wt_self_count=len(sequence),
        requested_positions=body["scan_positions"],
        excluded_positions=body["excluded_positions"],
        effective_positions=effective,
        selected_prediction_count=len(predictions),
        ranked_nonself_prediction_count=len(candidates),
        predictions=predictions,
        comparison_set_sha256=sha(encode([(item["position"], item["mut"], item["ddg_thermompnn"]) for item in ordered])),
        conversion=conversion,
        engine_runtime=runtime,
        raw_csv_sha256=sha(raw_csv),
        raw_ddg_sign_preserved=True,
        sign_convention="negative_is_stabilizing_per_project_contract_unreviewed",
    )


def result(job, body, files, execution, fault=None):
    binding = {key: job[key] for key in ("run_id", "request_id", "job_id", "attempt_id", "execution_identity", "execution_profile", "rule_profile")}
    binding.update(
        input_sha256=job["request_artifact"]["sha256"],
        sequence_sha256=sha(body["protein_sequence"].encode()),
        structure_artifact=body["structure_artifact"],
        scan_scope_sha256=sha(encode({key: body[key] for key in ("scan_positions", "excluded_positions", "scope_source")})),
    )
    value = dict(
        contract_version="0.1.0",
        tool_id=policy.TOOL,
        binding=binding,
        evidence_kind="G0_REAL_OUTPUT",
        qualification="DEVELOPMENT_UNREVIEWED",
        scientific_signoff=None,
        usable_for_pipeline=False,
        automatic_handoff=False,
        production_status="NOT_DEPLOYED",
        requires_review=True,
        execution=execution,
        controlled_fault=fault,
        status="unreliable",
        scan=None,
        scientific_gate="NOT_EVALUATED",
        null_reason=execution.get("error_code"),
        warnings=[],
        source_receipt=execution.get("source_receipt"),
        method_summary=dict(
            engine="ThermoMPNN",
            commit=policy.COMMIT,
            model=policy.MODEL,
            unit="kcal/mol",
            raw_sign_transform=None,
            official_entrypoint="analysis/custom_inference.py",
            official_threshold_parameter=False,
            full_output_validation="20 native AA rows for every covered monomer residue",
            scan_scope=body["scan_positions"],
            excluded_positions=body["excluded_positions"],
            scope_source=body["scope_source"],
            cross_engine_absolute_ddg_comparison=False,
            consensus_filtering_performed=False,
        ),
    )
    if execution.get("error_code"):
        value["warnings"] = [
            dict(
                code=execution["error_code"],
                level="failure",
                severity="WARNING",
                message="ThermoMPNN 单体稳定性预测失败——原生输出不可消费；" + str(execution.get("diagnostic") or execution["error_code"]),
            )
        ]
        return value
    try:
        ensure(
            execution["stopped_confirmed"] and execution["exit_code"] == 0 and execution["image_id"] == policy.IMAGE,
            "OUTPUT_INVALID",
            "No clean stopped pinned ThermoMPNN run",
        )
        if fault == "corrupt_output":
            raise RuntimeFault("OUTPUT_INVALID", "Controlled native output corruption")
        scan = validate_observation(body, files)
        if scan["status"] == "skipped_multichain":
            value.update(status="skipped_multichain_unreviewed", scan=scan, null_reason=scan["reason_code"])
            value["warnings"] = [
                dict(
                    code="R39_THERMOMPNN_MONOMER_ONLY",
                    level="quality",
                    severity="WARNING",
                    message="R-39 铁律：ThermoMPNN 仅用于单体；该多链结构已明确跳过，未裁链、未执行模型。",
                )
            ]
        else:
            value.update(status="predicted_unreviewed", scan=scan, null_reason=None)
            value["warnings"] = [
                dict(
                    code="ENGINEERING_STABILITY_NOT_SCIENTIFICALLY_SIGNED",
                    level="quality",
                    severity="WARNING",
                    message="真实 ThermoMPNN 原始 ΔΔG 仅供工程核验；未执行跨引擎绝对值比较，N14/N17 科学筛选与自动交接未放行。",
                )
            ]
    except (RuntimeFault, KeyError, ValueError, TypeError, IndexError, OSError, UnicodeError, csv.Error) as exc:
        execution.update(error_code="OUTPUT_INVALID", diagnostic=str(exc))
        value.update(null_reason="OUTPUT_INVALID")
        value["warnings"] = [
            dict(
                code="OUTPUT_INVALID",
                level="failure",
                severity="WARNING",
                message="ThermoMPNN 原生输出未通过覆盖、身份、坐标或哈希校验，整组隔离；" + str(exc),
            )
        ]
    return value

