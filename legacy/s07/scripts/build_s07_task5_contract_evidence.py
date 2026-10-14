"""Build S-07 task-5 evidence offline from frozen task-3/4 files and labelled fixtures."""

from __future__ import annotations

import argparse
import copy
import io
import json
from pathlib import Path
from typing import Any

from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from Bio.PDB.mmcifio import MMCIFIO

import build_s07_task4_api_evidence as task4
from s07_task5_contract import (
    CONTRACT_VERSION, OPERATIONS, RULE_IDS, Candidate, EvidenceStore,
    S07Result, SourceRun, digest, immutable_write, json_bytes, method_summary, utc_now,
)


ROOT = Path(__file__).resolve().parents[1]
T3 = ROOT / "discovery/p0/s07/p0-s07-task3-mmseqs-20260902-a"
T4 = ROOT / "discovery/p0/s07/p0-s07-task4-uniprot-afdb-20260902-a"
DEFAULT_CAMPAIGN = ROOT / "discovery/p0/s07/p0-s07-task5-contract-20260903-b"
SCHEMA = ROOT / "docs/archive/p0/S07_TASK5_RESULT_CONTRACT.schema.json"


def error(code: str, category: str = "EXECUTION", retryable: bool = False) -> dict[str, Any]:
    return {
        "code": code, "category": category, "retryable": retryable,
        "message": code, "user_message": {
            "TIMEOUT": "查询超时，尚未取得完整结果。",
            "INPUT_VALIDATION": "提供的编号不受此接口支持。",
            "CANCELLED": "本次执行已取消。",
            "OUTPUT_MISSING": "结果尚未取全，不能判断为正常无命中。",
            "OUTPUT_INVALID": "保存的文件未通过完整性或格式检查。",
        }.get(category, "查询或文件读取失败，已保留错误证据。"),
        "details": {},
    }


def warning(code: str, message: str, level: str = "warning") -> dict[str, Any]:
    return {"code": code, "message": message, "details": {"level": level}}


def manifest_entries(value: Any):
    if isinstance(value, dict):
        if {"path", "sha256", "size_bytes"} <= value.keys():
            yield value
        for item in value.values():
            yield from manifest_entries(item)
    elif isinstance(value, list):
        for item in value:
            yield from manifest_entries(item)


class Builder:
    def __init__(self, campaign: Path):
        self.store = EvidenceStore(campaign)
        self.expected = {
            entry["path"]: entry
            for path in (T3 / "reports/artifact_manifest.json", T4 / "reports/artifact_manifest.json")
            for entry in manifest_entries(task4.read_json(path))
        }
        self.imported: dict[str, dict[str, Any]] = {}
        self.cases: dict[str, dict[str, Any]] = {}
        self.case_rows: list[dict[str, Any]] = []
        profile = {
            "profile_id": "s07-api-review-20260903", "intended_access_mode": "API",
            "uniprot_search_scope": "uniprotkb_swissprot",
            "rule_status": "PROVISIONAL_USER_APPROVED_EXPERT_PENDING",
            "expert_confirmation_ids": RULE_IDS,
        }
        self.profile = {
            **profile,
            "profile_artifact_id": self.store.put_json("execution-profile.json", profile, "execution_profile"),
        }

    def raw(self, path: Path) -> str:
        path = path.resolve()
        relative = path.relative_to(ROOT).as_posix()
        if relative in self.imported:
            return self.imported[relative]["artifact_id"]
        data = path.read_bytes()
        expected = self.expected.get(relative)
        if expected and (len(data), digest(data)) != (expected["size_bytes"], expected["sha256"]):
            raise ValueError(f"Frozen task-3/4 evidence has changed: {relative}")
        media = "chemical/x-mmcif" if path.suffix == ".cif" else (
            "application/json" if path.suffix == ".json" else "text/plain"
        )
        ref = self.store.put(path.name, data, "frozen_evidence", media, relative)
        self.imported[relative] = {
            "artifact_id": ref["artifact_id"], "sha256": ref["sha256"],
            "size_bytes": ref["size_bytes"], "checked_against_prior_manifest": expected is not None,
        }
        return ref["artifact_id"]

    def raw_dir(self, path: Path) -> list[str]:
        return sorted({self.raw(item) for item in path.iterdir() if item.is_file()})

    def input(self, path: Path, *, accession: str | None = None, organism: str | None = None) -> dict[str, Any]:
        sequence = task4.read_fasta(path)
        snapshot = {
            "protein_sequence": sequence, "organism_name": organism,
            "accession_hint": accession, "origin_fasta_artifact_id": self.raw(path),
        }
        return {
            "input_artifact_id": self.store.put_json("input-snapshot.json", snapshot, "immutable_input"),
            "sequence_sha256": digest(sequence.encode("ascii")), "sequence_length": len(sequence),
            "organism_name": organism, "accession_hint": accession,
        }

    def sequence(self, binding: dict[str, Any]) -> str:
        return json.loads(self.store.read(self.store.refs[binding["input_artifact_id"]]))["protein_sequence"]

    def stage(self, binding: dict[str, Any], operation: str, status: str, reason: str, *,
              count: int = 0, complete: bool | None = None, capped: bool = False,
              failures: list[dict[str, Any]] | None = None, raw: list[str] | None = None,
              endpoint: str | None = None, tool: str | None = None, version: str | None = None,
              release: str | None = None, original_time: dict[str, str | None] | None = None,
              parameters: dict[str, Any] | None = None, original_mode: str = "API") -> dict[str, Any]:
        not_run = status == "NOT_RUN"
        frozen = raw is not None and not not_run
        if complete is None:
            complete = status.startswith("SUCCEEDED") and not capped and not failures
        result = {
            "operation": operation, "status": status, "reason_code": reason,
            "bound_sequence_sha256": binding["sequence_sha256"], "returned_count": count,
            "complete": complete, "capped": capped, "failures": failures or [],
            "evidence_kind": "NOT_RUN" if not_run else "FROZEN_REPLAY" if frozen else "CONTROLLED",
            "original_access_mode": None if not_run else original_mode if frozen else "OFFLINE",
            "endpoint_or_release": endpoint if frozen else None, "tool_name": tool if frozen else None,
            "tool_version": version if frozen else None, "data_version": release if frozen else None,
            "version_note": (
                "Not executed." if not_run else "Offline controlled state; no remote invocation."
                if not frozen else "Only versions recorded in the frozen output/headers are reported; null means unreported."
            ),
            "original_time": original_time or {}, "evaluated_at": utc_now(),
            "parameters": parameters or {}, "artifact_ids": raw or [],
        }
        if not not_run and not frozen:
            result["artifact_ids"] = [self.store.put_json(
                "controlled-operation.json",
                {"fixture_only": True, "state": result, "network_calls": 0},
                "controlled_source_state",
            )]
        return SourceRun.model_validate(result).model_dump(mode="json")

    def plan(self, binding: dict[str, Any], reason: str = "UPSTREAM_NOT_COMPLETED") -> dict[str, Any]:
        return {op: self.stage(binding, op, "NOT_RUN", reason) for op in OPERATIONS}

    def pdb_empty(self, binding: dict[str, Any]) -> dict[str, Any]:
        plan = self.plan(binding)
        plan["PDB_SEARCH"] = self.stage(binding, "PDB_SEARCH", "SUCCEEDED_EMPTY", "CONTROLLED_NO_STRICT_PDB_CANDIDATES")
        for op in ("PDB_METADATA", "PDB_STRUCTURE"):
            plan[op] = self.stage(binding, op, "NOT_RUN", "NO_PDB_CANDIDATES")
        return plan

    def blast(self, binding: dict[str, Any], case: str) -> dict[str, Any]:
        parsed = task4.parse_blast(T4, case)
        if parsed["query_length"] != binding["sequence_length"]:
            raise ValueError("Frozen BLAST query length differs from the bound input")
        count = parsed["reported_hit_count"]
        return self.stage(
            binding, "BLAST_UNIPROT", "SUCCEEDED_WITH_RESULTS" if count else "SUCCEEDED_EMPTY",
            "RETURN_LIMIT_REACHED" if count >= 100 else "NORMAL_NO_HIT",
            count=count, capped=count >= 100,
            raw=self.raw_dir(T4 / "evidence/blast-api/ebi" / case),
            endpoint="https://www.ebi.ac.uk/Tools/services/rest/ncbiblast",
            tool=parsed["program"], version=parsed["tool_version"], release=parsed["database_created"],
            original_time={"started_at": parsed["started_at"], "finished_at": parsed["ended_at"]},
            parameters={"database": parsed["database"], "max_scores": 100, "max_alignments": 100,
                        "matrix": "BLOSUM62", "expect": 10, "filter": "F",
                        "parameter_scope": "TASK4_DISCOVERY_ONLY_NOT_SCIENTIFIC_THRESHOLDS",
                        "database_sequence_count": parsed["database_sequence_count"],
                        "database_residue_count": parsed["database_residue_count"],
                        "job_id": parsed["job_id"], "terminal_status": parsed["terminal_status"]},
        )

    def uniprot(self, binding: dict[str, Any], accession: str) -> dict[str, Any]:
        parsed = task4.parse_uniprot(T4, accession)
        if parsed["http_status"] != 200:
            raise ValueError("This frozen UniProt replay requires a successful record, not an invented empty result")
        headers = task4.parse_headers(T4 / "evidence/uniprot-api" / accession / "entry-json.headers.txt")
        return self.stage(
            binding, "UNIPROT_RECORD", "SUCCEEDED_WITH_RESULTS", "RECORD_RECHECKED", count=1,
            raw=self.raw_dir(T4 / "evidence/uniprot-api" / accession),
            endpoint=f"https://rest.uniprot.org/uniprotkb/{accession}.json", tool="UniProt REST",
            release=parsed["api_release"], original_time={"response_date": headers["headers"].get("date")},
            parameters={"accession": accession, "sequence_exact": parsed["sequence"] == self.sequence(binding)},
        )

    def afdb(self, binding: dict[str, Any], accession: str) -> dict[str, Any]:
        parsed = task4.parse_afdb(T4, accession)
        if parsed["http_status"] not in {200, 400, 404}:
            raise ValueError("Unmodelled AFDB status must not be converted to a normal empty result")
        count = len(parsed["models"]) if parsed["http_status"] == 200 else 0
        invalid = parsed["http_status"] == 400
        return self.stage(
            binding, "AFDB_LOOKUP", "FAILED" if invalid else "SUCCEEDED_WITH_RESULTS" if count else "SUCCEEDED_EMPTY",
            "INVALID_IDENTIFIER" if invalid else "MODELS_RETURNED" if count else "VALID_ACCESSION_NO_MODEL",
            count=count, failures=[error("INVALID_AFDB_IDENTIFIER", "INPUT_VALIDATION")] if invalid else [],
            raw=[self.raw(T4 / "evidence/afdb" / accession / name) for name in ("response.json", "response.headers.txt")],
            endpoint=f"https://alphafold.ebi.ac.uk/api/prediction/{accession}", tool="AlphaFold DB API",
            release=str(parsed["models"][0]["latest_version"]) if count else None,
            original_time={"response_date": parsed["response_headers"]["date"]},
            parameters={"accession": accession, "http_status": parsed["http_status"]},
        )

    def coordinate_candidate(self, binding: dict[str, Any], path: Path, *,
                             source: str, source_id: str, chain: str,
                             accession: str | None = None, eligible: bool = True,
                             controlled: bool = False) -> dict[str, Any]:
        doc = MMCIF2Dict(str(path))
        query = self.sequence(binding)
        keys = ["label_entity_id", "label_asym_id", "auth_asym_id", "pdbx_PDB_model_num",
                "label_seq_id", "auth_seq_id", "pdbx_PDB_ins_code", "group_PDB"]
        rows = list(zip(*(doc[f"_atom_site.{key}"] for key in keys), strict=True))
        atom_rows = [row for row in rows if row[2] == chain and row[3] == "1" and row[7] == "ATOM" and row[4] not in {".", "?"}]
        identities = {(row[0], row[1], row[2], row[3]) for row in atom_rows}
        if len(identities) != 1:
            raise ValueError("This fixture parser requires one explicitly identified entity/chain/model")
        entity_id, label, auth, model_number = next(iter(identities))
        sequences = dict(zip(doc["_entity_poly.entity_id"], doc["_entity_poly.pdbx_seq_one_letter_code_can"], strict=True))
        reference = "".join(sequences[entity_id].split())
        offset = reference.find(query)
        if offset < 0 or reference.find(query, offset + 1) >= 0:
            raise ValueError("Observed fixture mapping must be an unambiguous ungapped sequence match")
        structure_id = (
            self.store.put(path.name, path.read_bytes(), "controlled_structure", "chemical/x-mmcif")["artifact_id"]
            if controlled else self.raw(path)
        )
        by_position: dict[int, dict[str, Any]] = {}
        for entity, lbl, au, model, label_seq, auth_seq, icode, _ in atom_rows:
            value = {"entity_id": entity, "label_asym_id": lbl, "auth_asym_id": au,
                     "model_number": int(model), "label_seq_id": int(label_seq),
                     "auth_seq_id": auth_seq, "insertion_code": None if icode in {".", "?"} else icode}
            if int(label_seq) in by_position and by_position[int(label_seq)] != value:
                raise ValueError("Atom rows disagree about residue numbering")
            by_position[int(label_seq)] = value
        per_residue = [by_position.get(index + offset) for index in range(1, len(query) + 1)]
        missing = [index for index, value in enumerate(per_residue, 1) if value is None]
        ranges: list[list[int]] = []
        for position in missing:
            if ranges and ranges[-1][1] == position - 1:
                ranges[-1][1] = position
            else:
                ranges.append([position, position])
        mapping_id = self.store.put_json("sequence-coordinate-map.json", {
            "fixture_only": controlled, "source_structure_artifact_id": structure_id,
            "input_sequence_sha256": binding["sequence_sha256"], "query_offset_in_entity": offset,
            "input_to_coordinate": per_residue,
        }, "sequence_coordinate_mapping")
        alignment_id = self.store.put_json("sequence-alignment.json", {
            "input_sequence": query, "reference_sequence": reference, "offset": offset,
            "evidence": "Frozen sequence equality/unique substring; not a new alignment algorithm.",
            "source_structure_artifact_id": structure_id,
        }, "sequence_alignment")
        resolution = doc.get("_refine.ls_d_res_high", doc.get("_em_3d_reconstruction.resolution", [None]))[0]
        candidate = {
            "candidate_id": f"{source_id}-{label}-{auth}-{model_number}",
            "source": source, "source_object_id": source_id,
            "entry_id": source_id if source == "experimental" else None,
            "entity_id": entity_id, "label_asym_id": label, "auth_asym_id": auth,
            "model_number": int(model_number), "assembly_id": None,
            "accession": accession, "model_version": "6" if source == "alphafolddb" else None,
            "organism_name": binding["organism_name"],
            "method": doc.get("_exptl.method", [None])[0] if source == "experimental" else None,
            "resolution_angstrom": float(resolution) if source == "experimental" and resolution else None,
            "alignment": {
                "query_length": len(query), "reference_length": len(reference),
                "query_sha256": digest(query.encode()), "reference_sha256": digest(reference.encode()),
                "identity_pct": 100.0, "query_coverage": 1.0, "target_coverage": len(query) / len(reference),
                "exact_full_length": query == reference, "evidence_artifact_id": alignment_id,
            },
            "coordinate_mapping": {
                "status": "PARTIAL" if missing else "FULL", "target_length": len(query),
                "mapped_count": len(query) - len(missing), "missing_ranges": ranges,
                "per_residue_artifact_id": mapping_id,
            },
            "eligibility": "ELIGIBLE_PROVISIONAL" if eligible else "REVIEW_REQUIRED",
            "reason_codes": ["CONTROLLED_UNIQUE_CANDIDATE" if controlled else "FROZEN_SEQUENCE_COORDINATE_CHECK"],
            "structure_artifact_id": structure_id, "confidence_artifact_ids": [],
            "raw_confidence_summary": {}, "quality_assessment": "PENDING_S09",
        }
        return Candidate.model_validate(candidate).model_dump(mode="json")

    def afdb_candidate(self, binding: dict[str, Any], accession: str = "O15116") -> dict[str, Any]:
        model = task4.parse_afdb(T4, accession)["models"][0]
        query = self.sequence(binding)
        uni = task4.parse_uniprot(T4, accession)
        path = T4 / "evidence/afdb" / accession / "model.cif"
        if not query == uni["sequence"] == model["sequence"] == task4.parse_afdb_cif_sequence(path):
            raise ValueError("Input, UniProt, AFDB metadata and file sequence must all be identical")
        candidate = self.coordinate_candidate(binding, path, source="alphafolddb",
                                              source_id=model["entry_id"], chain="A", accession=accession)
        confidence = task4.read_json(path.parent / "confidence.json")
        pae = task4.read_json(path.parent / "pae.json")[0]["predicted_aligned_error"]
        scores = confidence["confidenceScore"]
        if len(scores) != len(query) or confidence["residueNumber"] != list(range(1, len(query) + 1)):
            raise ValueError("Raw confidence positions do not match the input")
        if len(pae) != len(query) or any(len(row) != len(query) for row in pae):
            raise ValueError("PAE dimensions do not match the model")
        if any(not 0 <= score <= 100 for score in scores):
            raise ValueError("Observed AFDB confidence is not within its recorded 0-100 scale")
        candidate["model_version"] = str(model["latest_version"])
        candidate["organism_name"] = model["organism"]
        candidate["confidence_artifact_ids"] = [self.raw(path.parent / name) for name in ("confidence.json", "pae.json")]
        candidate["raw_confidence_summary"] = {
            "scale": "0-100", "residue_count": len(scores), "pae_shape": [len(pae), len(pae[0])],
            "metadata_global_metric": model["global_metric_value"],
            "mean_of_saved_residue_scores": sum(scores) / len(scores),
            "normalized_for_s09": False,
        }
        return Candidate.model_validate(candidate).model_dump(mode="json")

    def metadata_candidates(self, binding: dict[str, Any], accession: str) -> list[dict[str, Any]]:
        query = self.sequence(binding)
        output = []
        for model in task4.parse_afdb(T4, accession)["models"]:
            ref = model["sequence"]
            exact = query == ref
            evidence = self.store.put_json("model-sequence-check.json", {
                "input_sequence": query, "model_sequence": ref,
                "mismatches": task4.mismatch_positions(query, ref),
                "source_response_artifact_id": self.raw(T4 / "evidence/afdb" / accession / "response.json"),
            }, "sequence_alignment")
            output.append(Candidate.model_validate({
                "candidate_id": model["entry_id"], "source": "alphafolddb", "source_object_id": model["entry_id"],
                "entry_id": None, "entity_id": None, "label_asym_id": None, "auth_asym_id": None,
                "model_number": None, "assembly_id": None, "accession": model["uniprot_accession"],
                "model_version": str(model["latest_version"]), "organism_name": model["organism"],
                "method": None, "resolution_angstrom": None,
                "alignment": {
                    "query_length": len(query), "reference_length": len(ref),
                    "query_sha256": digest(query.encode()), "reference_sha256": digest(ref.encode()),
                    "identity_pct": 100.0 if exact else None, "query_coverage": 1.0 if exact else None,
                    "target_coverage": 1.0 if exact else None, "exact_full_length": exact,
                    "evidence_artifact_id": evidence,
                },
                "coordinate_mapping": None, "eligibility": "REVIEW_REQUIRED",
                "reason_codes": ["AMBIGUOUS_CANDIDATES" if exact else "SEQUENCE_MISMATCH"],
                "structure_artifact_id": None, "confidence_artifact_ids": [],
                "raw_confidence_summary": {"metadata_global_metric": model["global_metric_value"]},
                "quality_assessment": "PENDING_S09",
            }).model_dump(mode="json"))
        return output

    def finish(self, name: str, title: str, binding: dict[str, Any], plan: dict[str, Any], *,
               status: str, outcome: str | None = None, candidates: list[dict[str, Any]] | None = None,
               selected: str | None = None, failure: dict[str, Any] | None = None,
               reviews: list[str] | None = None, warnings: list[dict[str, Any]] | None = None,
               attempt: int = 1, run: str | None = None, previous: str | None = None,
               component: bool = False) -> dict[str, Any]:
        candidates, reviews, warnings = candidates or [], reviews or [], warnings or []
        source_list = [plan[op] for op in OPERATIONS]
        abnormal = any(item["failures"] for item in source_list)
        if abnormal:
            warnings.append(warning("SOURCE_FAILURE", "来源调用失败或部分失败，原始错误已保存。", "failure"))
        candidate_manifest = self.store.put_json("candidate-manifest.json", {
            "scope": "CONTROLLED_COMPOSITION_NOT_A_NEW_FULL_DATABASE_SEARCH", "items": candidates,
        }, "candidate_manifest")
        source_manifest = self.store.put_json("source-manifest.json", source_list, "source_manifest")
        generated_at = utc_now()
        method_summary_id = self.store.put_json(
            "method-summary.json",
            method_summary([SourceRun.model_validate(item) for item in source_list], generated_at),
            "method_summary",
        )
        result = {
            "contract_version": CONTRACT_VERSION, "record_kind": "S07_INTERNAL_RESULT",
            "execution_kind": "OFFLINE_CONTRACT_CHECK", "deployment_status": "NOT_DEPLOYED",
            "scientific_acceptance": "NOT_RUN",
            "case_scope": "COMPONENT_PROBE" if component else "CONTROLLED_COMPOSITION",
            "run_id": run or f"task5-{name}", "step_id": "S-07", "attempt": attempt, "generated_at": generated_at,
            "status": status, "input": binding, "profile": self.profile, "retrieval_outcome": outcome,
            "selected_candidate_id": selected, "selection_reason_codes": ["EXPLICIT_CONTROLLED_CANDIDATE_SET"] if selected else [],
            "next_step": "S-09" if selected else "S-08" if outcome == "NO_ELIGIBLE_EXISTING_STRUCTURE" else None,
            "reliability": "UNRELIABLE" if abnormal or failure or any(
                item["details"].get("level") == "failure" for item in warnings
            ) else "RELIABLE",
            "requires_review": bool(reviews), "review_reasons": reviews,
            "source_runs": source_list, "candidates": candidates, "candidate_total": len(candidates),
            "candidate_summary_complete": True, "candidate_manifest_artifact_id": candidate_manifest,
            "source_manifest_artifact_id": source_manifest, "method_summary_artifact_id": method_summary_id,
            "prior_attempt_result_artifact_id": previous,
            "artifacts": [], "warnings": warnings, "error": failure,
        }
        # Resolve this result's transitive evidence only. Unrelated earlier cases are excluded.
        def references(value: Any) -> set[str]:
            if isinstance(value, str):
                return {value} if value in self.store.refs else set()
            if isinstance(value, dict):
                return set().union(*(references(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(references(item) for item in value))
            return set()

        needed, visited = references(result), set()
        while needed - visited:
            artifact_id = next(iter(needed - visited))
            visited.add(artifact_id)
            ref = self.store.refs[artifact_id]
            if ref["media_type"] == "application/json":
                needed.update(references(json.loads(self.store.read(ref))))
        result["artifacts"] = [self.store.refs[key] for key in sorted(needed)]
        ref = self.store.save_result(result)
        self.cases[name] = result
        self.case_rows.append({
            "case_id": name, "name": title, "status": status, "next_step": result["next_step"],
            "passed": True, "result_artifact_id": ref["artifact_id"],
            "result_path": f"results/{result['run_id']}/attempt-{attempt:03d}.json",
            "scope": result["case_scope"],
        })
        return ref


def pdb_selected_plan(builder: Builder, binding: dict[str, Any], candidate: dict[str, Any],
                      controlled: bool = False) -> dict[str, Any]:
    plan = builder.plan(binding, "PDB_SELECTED")
    plan["PDB_SEARCH"] = builder.stage(
        binding, "PDB_SEARCH", "SUCCEEDED_WITH_RESULTS", "CONTROLLED_CLOSED_CANDIDATE_SET",
        count=1, parameters={"fixture_candidate_ids": [candidate["candidate_id"]]},
    )
    for op in ("PDB_METADATA", "PDB_STRUCTURE"):
        plan[op] = builder.stage(
            binding, op, "SUCCEEDED_WITH_RESULTS", "CONTROLLED_FILE" if controlled else "SAVED_MMCIF_REPLAY",
            count=1, raw=None if controlled else [candidate["structure_artifact_id"]],
            tool="BioPython MMCIF2Dict", version=__import__("Bio").__version__,
            endpoint="Frozen wwPDB mmCIF", original_mode="LOCAL",
            parameters={"structure_artifact_id": candidate["structure_artifact_id"],
                        "candidate_id": candidate["candidate_id"]},
        )
    return plan


def afdb_selected_plan(builder: Builder, binding: dict[str, Any], *, closed_blast: bool = False) -> dict[str, Any]:
    plan = builder.pdb_empty(binding)
    if closed_blast:
        plan["BLAST_UNIPROT"] = builder.stage(
            binding, "BLAST_UNIPROT", "SUCCEEDED_WITH_RESULTS", "CONTROLLED_CLOSED_EXACT_ACCESSION_SET",
            count=1, parameters={
                "fixture_accessions": ["O15116"],
                "note": "One-candidate controlled set; the actual top-100 response remains capped in a separate case.",
            },
        )
    else:
        plan["BLAST_UNIPROT"] = builder.stage(binding, "BLAST_UNIPROT", "NOT_RUN", "ACCESSION_HINT")
    plan["UNIPROT_RECORD"] = builder.uniprot(binding, "O15116")
    plan["AFDB_LOOKUP"] = builder.afdb(binding, "O15116")
    model = task4.parse_afdb(T4, "O15116")["models"][0]
    plan["AFDB_STRUCTURE"] = builder.stage(
        binding, "AFDB_STRUCTURE", "SUCCEEDED_WITH_RESULTS", "MODEL_AND_CONFIDENCE_FILES_CHECKED",
        count=1, raw=builder.raw_dir(T4 / "evidence/afdb/O15116"), endpoint=model["cif_url"],
        tool="AlphaFold DB model files", release=str(model["latest_version"]),
        parameters={"model_id": model["entry_id"], "confidence_scale": "0-100"},
    )
    return plan


def partial_fixture(builder: Builder) -> Path:
    source = T3 / "evidence/wwpdb/6Q00/6Q00.cif"
    document = MMCIF2Dict(str(source))
    keep = [
        index for index, (group, label_seq, auth) in enumerate(zip(
            document["_atom_site.group_PDB"], document["_atom_site.label_seq_id"],
            document["_atom_site.auth_asym_id"], strict=True,
        )) if group == "ATOM" and auth == "A" and label_seq not in {".", "?"} and int(label_seq) <= 70
    ]
    for key in document:
        if key.startswith("_atom_site."):
            document[key] = [document[key][index] for index in keep]
    document["data_"] = "CONTROLLED_PARTIAL_6Q00_NOT_AN_EXPERIMENT"
    output = io.StringIO()
    writer = MMCIFIO()
    writer.set_dict(document)
    writer.save(output)
    path = builder.store.root / "controlled" / "partial-6Q00.cif"
    immutable_write(path, output.getvalue().encode())
    builder.store.put_json("partial-fixture-definition.json", {
        "fixture_only": True, "derived_from_artifact_id": builder.raw(source),
        "transformation": "Keep the 76-residue entity sequence; retain ATOM rows for chain A label_seq_id 1..70.",
        "purpose": "Validate null padding and partial routing only; no scientific conclusion.",
    }, "controlled_fixture_definition")
    return path


def build_cases(builder: Builder) -> None:
    selected_outcome = "EXISTING_STRUCTURE_SELECTED"
    none_outcome = "NO_ELIGIBLE_EXISTING_STRUCTURE"
    ubq = builder.input(T3 / "inputs/samples/P0-DISC-001.fasta")
    experimental = builder.coordinate_candidate(
        ubq, T3 / "evidence/wwpdb/6Q00/6Q00.cif", source="experimental", source_id="6Q00", chain="A",
    )
    plan = pdb_selected_plan(builder, ubq, experimental)
    builder.finish("R01", "完整实验结构进入 S-09", ubq, plan, status="SUCCEEDED",
                   outcome=selected_outcome, candidates=[experimental], selected=experimental["candidate_id"])

    partial = builder.coordinate_candidate(
        ubq, partial_fixture(builder), source="experimental", source_id="CONTROLLED-PARTIAL-6Q00",
        chain="A", controlled=True,
    )
    builder.finish(
        "R02", "受控 partial 保留 6 个 null 并进入 S-09", ubq,
        pdb_selected_plan(builder, ubq, partial, controlled=True), status="DEGRADED",
        outcome=selected_outcome, candidates=[partial], selected=partial["candidate_id"],
        warnings=[warning("PARTIAL_STRUCTURE", "坐标仅覆盖输入的 70/76；第 71–76 位保留 null。")],
    )

    direct = builder.input(T4 / "inputs/O15116.fasta", accession="O15116", organism="Homo sapiens")
    af = builder.afdb_candidate(direct)
    builder.finish("R03", "已有 accession 的 AFDB 结构进入 S-09", direct, afdb_selected_plan(builder, direct),
                   status="SUCCEEDED", outcome=selected_outcome, candidates=[af], selected=af["candidate_id"])

    no_hint = builder.input(T4 / "inputs/O15116.fasta", organism="Homo sapiens")
    af_no_hint = builder.afdb_candidate(no_hint)
    builder.finish(
        "R04", "受控完整 BLAST→UniProt→AFDB 链进入 S-09", no_hint,
        afdb_selected_plan(builder, no_hint, closed_blast=True), status="SUCCEEDED",
        outcome=selected_outcome, candidates=[af_no_hint], selected=af_no_hint["candidate_id"],
    )

    no_hit = builder.input(T4 / "inputs/synthetic-no-exact-record.fasta")
    plan = builder.pdb_empty(no_hit)
    plan["BLAST_UNIPROT"] = builder.blast(no_hit, "synthetic-no-exact-record")
    for op in OPERATIONS[4:]:
        plan[op] = builder.stage(no_hit, op, "NOT_RUN", "NO_VERIFIED_IDENTIFIER")
    builder.finish("R05", "BLAST 正常零命中；C4 未执行；进入 S-08", no_hit, plan,
                   status="SUCCEEDED", outcome=none_outcome)

    no_model = builder.input(T4 / "inputs/C0HLM8.fasta", accession="C0HLM8")
    plan = builder.pdb_empty(no_model)
    plan["BLAST_UNIPROT"] = builder.stage(no_model, "BLAST_UNIPROT", "NOT_RUN", "ACCESSION_HINT")
    plan["UNIPROT_RECORD"] = builder.uniprot(no_model, "C0HLM8")
    plan["AFDB_LOOKUP"] = builder.afdb(no_model, "C0HLM8")
    plan["AFDB_STRUCTURE"] = builder.stage(no_model, "AFDB_STRUCTURE", "NOT_RUN", "NO_AFDB_MODEL")
    builder.finish("R06", "合法 accession 的 404 无模型（来源探针）", no_model, plan,
                   status="SUCCEEDED", outcome=none_outcome, component=True,
                   warnings=[warning("COMPONENT_PROBE_ONLY", "12 aa 探针只验证来源状态；完整 T-01 会先被 S-01 长度守卫拦截。")])

    invalid = builder.input(T4 / "inputs/O15116.fasta", accession="NP_055277.1")
    plan = builder.pdb_empty(invalid)
    plan["AFDB_LOOKUP"] = builder.afdb(invalid, "NP_055277.1")
    builder.finish("R07", "非法编号 400 保留错误", invalid, plan, status="FAILED",
                   failure=error("INVALID_AFDB_IDENTIFIER", "INPUT_VALIDATION"), component=True)

    near = builder.input(T4 / "inputs/O15116-one-substitution.fasta")
    plan = builder.pdb_empty(near)
    plan["BLAST_UNIPROT"] = builder.blast(near, "O15116-one-substitution")
    plan["UNIPROT_RECORD"] = builder.uniprot(near, "O15116")
    plan["AFDB_LOOKUP"] = builder.afdb(near, "O15116")
    plan["AFDB_STRUCTURE"] = builder.stage(near, "AFDB_STRUCTURE", "NOT_RUN", "REVIEW_REQUIRED")
    builder.finish(
        "R08", "非精确 AFDB 候选保留待复核", near, plan, status="WAITING_USER",
        candidates=builder.metadata_candidates(near, "O15116"),
        reviews=["S07-EQ-03_SEQUENCE_MISMATCH", "BLAST_CANDIDATES_CAPPED"],
        warnings=[warning("CANDIDATES_INCOMPLETE", "BLAST 返回达到 100 条上限，候选完整性未知。")],
    )

    multi = builder.input(T4 / "inputs/ubiquitin-1UBQ.fasta")
    plan = builder.pdb_empty(multi)
    plan["BLAST_UNIPROT"] = builder.blast(multi, "ubiquitin-1UBQ")
    accessions = ["P62975", "P68197", "Q865C5"]
    candidates = [item for accession in accessions for item in builder.metadata_candidates(multi, accession)]
    for op, relative in (("UNIPROT_RECORD", "uniprot-api"), ("AFDB_LOOKUP", "afdb")):
        plan[op] = builder.stage(
            multi, op, "SUCCEEDED_WITH_RESULTS", "THREE_EXACT_RECORDS_REPLAYED", count=3,
            raw=sorted({ref for accession in accessions for ref in builder.raw_dir(T4 / "evidence" / relative / accession)}),
            tool="UniProt REST" if op == "UNIPROT_RECORD" else "AlphaFold DB API",
            release="2026_03" if op == "UNIPROT_RECORD" else "6",
            parameters={"accessions": accessions, "selection_by_api_order": False},
        )
    plan["AFDB_STRUCTURE"] = builder.stage(multi, "AFDB_STRUCTURE", "NOT_RUN", "REVIEW_REQUIRED")
    builder.finish(
        "R09", "三个精确 accession 不按返回顺序选择", multi, plan, status="WAITING_USER",
        candidates=candidates, reviews=["S07-EQ-04_MULTIPLE_EXACT_MODELS", "BLAST_CANDIDATES_CAPPED"],
        warnings=[warning("CANDIDATES_INCOMPLETE", "三个已知精确命中不代表完整候选集。")],
    )

    isoform = builder.input(T4 / "inputs/Q86UQ4.fasta", accession="Q86UQ4")
    plan = builder.pdb_empty(isoform)
    plan["BLAST_UNIPROT"] = builder.stage(isoform, "BLAST_UNIPROT", "NOT_RUN", "ACCESSION_HINT")
    plan["UNIPROT_RECORD"] = builder.uniprot(isoform, "Q86UQ4")
    plan["AFDB_LOOKUP"] = builder.afdb(isoform, "Q86UQ4")
    plan["AFDB_STRUCTURE"] = builder.stage(isoform, "AFDB_STRUCTURE", "NOT_RUN", "REVIEW_REQUIRED")
    builder.finish(
        "R10", "四个 isoform 与输入不一致，保留待复核", isoform, plan, status="WAITING_USER",
        candidates=builder.metadata_candidates(isoform, "Q86UQ4"),
        reviews=["S07-EQ-03_SEQUENCE_MISMATCH", "S07-EQ-04_ISOFORM_SELECTION"], component=True,
    )

    metadata_error = error("PDB_METADATA_UNAVAILABLE", "TOOL_UNAVAILABLE", retryable=True)
    plan = afdb_selected_plan(builder, direct)
    plan["PDB_SEARCH"] = builder.stage(direct, "PDB_SEARCH", "SUCCEEDED_WITH_RESULTS", "CONTROLLED_CANDIDATE_SET", count=1)
    plan["PDB_METADATA"] = builder.stage(direct, "PDB_METADATA", "FAILED", "ALL_CANDIDATE_METADATA_FAILED", failures=[metadata_error])
    plan["PDB_STRUCTURE"] = builder.stage(direct, "PDB_STRUCTURE", "NOT_RUN", "METADATA_UNAVAILABLE")
    builder.finish(
        "R11", "PDB 元数据全部失败后 AFDB 成功", direct, plan, status="DEGRADED",
        outcome=selected_outcome, candidates=[af], selected=af["candidate_id"],
        reviews=["PDB_METADATA_FAILURE_REQUIRES_REVIEW_BEFORE_SCIENTIFIC_DELIVERY"],
    )

    plan = copy.deepcopy({op: item for op, item in zip(OPERATIONS, builder.cases["R06"]["source_runs"], strict=True)})
    plan["PDB_SEARCH"] = builder.stage(no_model, "PDB_SEARCH", "SUCCEEDED_WITH_RESULTS", "CONTROLLED_CANDIDATE_SET", count=1)
    plan["PDB_METADATA"] = builder.stage(no_model, "PDB_METADATA", "FAILED", "ALL_CANDIDATE_METADATA_FAILED", failures=[metadata_error])
    plan["PDB_STRUCTURE"] = builder.stage(no_model, "PDB_STRUCTURE", "NOT_RUN", "METADATA_UNAVAILABLE")
    builder.finish("R12", "PDB 元数据失败且 AFDB 无模型，不误入 S-08", no_model, plan, status="FAILED",
                   failure=error("REQUIRED_SOURCE_INCOMPLETE", "TOOL_UNAVAILABLE", retryable=True), component=True)

    plan = builder.plan(ubq, "UPSTREAM_FAILURE")
    timeout = error("PDB_SEARCH_TIMEOUT", "TIMEOUT", retryable=True)
    plan["PDB_SEARCH"] = builder.stage(ubq, "PDB_SEARCH", "FAILED", "TIMEOUT", failures=[timeout])
    prior = builder.finish("R13", "查询超时保存第 1 次失败", ubq, plan, status="FAILED",
                           failure=timeout, run="task5-retry")
    builder.finish("R14", "相同输入和 profile 重试，第 1 次证据保留", ubq,
                   pdb_selected_plan(builder, ubq, experimental), status="SUCCEEDED", outcome=selected_outcome,
                   candidates=[experimental], selected=experimental["candidate_id"], attempt=2,
                   run="task5-retry", previous=prior["artifact_id"])

    plan = builder.plan(ubq, "CANCELLED_UPSTREAM")
    cancellation = error("USER_CANCELLED", "CANCELLED")
    plan["PDB_SEARCH"] = builder.stage(ubq, "PDB_SEARCH", "CANCELLED", "USER_CANCELLED", failures=[cancellation])
    builder.finish("R15", "取消后停止后续来源和路由", ubq, plan, status="CANCELLED", failure=cancellation)

    plan = afdb_selected_plan(builder, no_hint, closed_blast=True)
    plan["BLAST_UNIPROT"] = builder.blast(no_hint, "O15116")
    builder.finish(
        "R16", "真实 BLAST 返回 100 条，禁止宣称候选收集完成", no_hint, plan, status="FAILED",
        candidates=[af_no_hint], failure=error("BLAST_CANDIDATES_INCOMPLETE", "OUTPUT_MISSING"),
        warnings=[warning("CANDIDATES_INCOMPLETE", "已查到精确模型，但返回上限阻止确认候选收集完整性。")],
    )

    tp53 = builder.input(T3 / "inputs/samples/P0-DISC-002.fasta")
    chains = [
        builder.coordinate_candidate(tp53, T3 / "evidence/wwpdb/9R2Q/9R2Q.cif",
                                     source="experimental", source_id="9R2Q", chain=chain, eligible=False)
        for chain in ("K", "L", "M", "N")
    ]
    plan = pdb_selected_plan(builder, tp53, chains[0])
    plan["PDB_SEARCH"] = builder.stage(tp53, "PDB_SEARCH", "SUCCEEDED_WITH_RESULTS", "CONTROLLED_ONE_ENTRY_FOUR_CHAINS", count=4)
    for op in OPERATIONS[3:]:
        plan[op] = builder.stage(tp53, op, "NOT_RUN", "REVIEW_REQUIRED")
    builder.finish("R17", "9R2Q 四条匹配链按 R-58 停止自动交接", tp53, plan, status="WAITING_USER",
                   candidates=chains, reviews=["R58_AMBIGUOUS_DESIGN_CHAIN"],
                   warnings=[warning("R58_CHAIN_AMBIGUITY", "四条匹配链均为 200/393 坐标覆盖，不能自动选第一条。", "failure")])

    plan = afdb_selected_plan(builder, direct)
    bad_file = builder.store.put("controlled-broken-model.cif", b"not_a_valid_mmcif\n",
                                 "controlled_corrupt_structure", "chemical/x-mmcif")
    invalid_file = error("STRUCTURE_PARSE_FAILED", "OUTPUT_INVALID", retryable=True)
    plan["AFDB_STRUCTURE"] = builder.stage(
        direct, "AFDB_STRUCTURE", "FAILED", "CONTROLLED_CORRUPT_FILE", failures=[invalid_file],
        parameters={"corrupt_artifact_id": bad_file["artifact_id"], "expected_model": "AF-O15116-F1"},
    )
    builder.finish("R18", "损坏结构文件保存原字节并报错", direct, plan, status="FAILED", failure=invalid_file)

    plan = pdb_selected_plan(builder, ubq, experimental)
    plan["PDB_SEARCH"] = builder.stage(ubq, "PDB_SEARCH", "SUCCEEDED_WITH_RESULTS", "CONTROLLED_TWO_CANDIDATES", count=2)
    plan["PDB_METADATA"] = builder.stage(
        ubq, "PDB_METADATA", "SUCCEEDED_WITH_RESULTS", "PARTIAL_METADATA_FAILURE",
        count=1, complete=False, failures=[metadata_error],
    )
    plan["PDB_STRUCTURE"] = builder.stage(ubq, "PDB_STRUCTURE", "NOT_RUN", "METADATA_INCOMPLETE")
    for op in OPERATIONS[3:]:
        plan[op] = builder.stage(ubq, op, "NOT_RUN", "UPSTREAM_FAILURE")
    builder.finish("R19", "PDB 元数据部分失败，不把剩余候选当作最优", ubq, plan, status="FAILED",
                   candidates=[experimental], failure=error("PDB_METADATA_PARTIAL", "TOOL_UNAVAILABLE", retryable=True))


def rejection_cases(builder: Builder) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}

    def case(name: str, original: str) -> dict[str, Any]:
        values[name] = copy.deepcopy(builder.cases[original])
        return values[name]

    value = case("N01_threshold_identity_equals_95", "R01")
    value["candidates"][0]["alignment"].update(
        identity_pct=95.0, exact_full_length=False, reference_sha256=digest(b"identity-boundary-reference"),
    )
    value = case("N02_threshold_coverage_equals_90", "R01")
    value["candidates"][0]["alignment"].update(
        query_coverage=.90, exact_full_length=False, reference_sha256=digest(b"boundary-reference"),
    )
    case("N03_illegal_source_none", "R03")["candidates"][0]["source"] = "none"
    case("N04_premature_s09_confidence", "R03")["candidates"][0]["confidence"] = "high"
    value = case("N05_nonexact_afdb_autoselection", "R03")
    value["candidates"][0]["alignment"].update(
        identity_pct=99.2, exact_full_length=False, reference_sha256=digest(b"near-reference"),
    )
    value = case("N06_unverified_uniprot_sequence", "R03")
    value["source_runs"][4]["parameters"]["sequence_exact"] = False
    value = case("N07_unexecuted_source_claims_response_time", "R01")
    value["source_runs"][3]["original_time"] = {"response_date": "controlled-invalid-claim"}
    case("N08_missing_partial_warning", "R02")["warnings"] = []
    case("N09_cancelled_routes_to_s08", "R15")["next_step"] = "S-08"
    value = case("N10_metadata_failure_becomes_normal_none", "R12")
    value.update(status="DEGRADED", error=None, retrieval_outcome="NO_ELIGIBLE_EXISTING_STRUCTURE", next_step="S-08")
    value = case("N11_capped_blast_autoselection", "R16")
    value.update(status="SUCCEEDED", error=None, retrieval_outcome="EXISTING_STRUCTURE_SELECTED",
                 next_step="S-09", selected_candidate_id=value["candidates"][0]["candidate_id"],
                 selection_reason_codes=["INVALID_CAPPED_SELECTION"])
    value = case("N12_capped_blast_becomes_normal_none", "R05")
    value["source_runs"][3].update(status="SUCCEEDED_WITH_RESULTS", returned_count=100, capped=True, complete=False)
    value = case("N13_not_run_becomes_normal_none", "R05")
    value["source_runs"][3] = builder.stage(value["input"], "BLAST_UNIPROT", "NOT_RUN", "UPSTREAM_FAILURE")
    case("N14_missing_artifact_reference", "R01")["artifacts"] = []
    value = case("N15_ambiguous_chain_autoselection", "R17")
    value.update(status="SUCCEEDED", retrieval_outcome="EXISTING_STRUCTURE_SELECTED",
                 next_step="S-09", selected_candidate_id=value["candidates"][0]["candidate_id"])
    value = case("N16_duplicate_source_operation", "R01")
    value["source_runs"].append(copy.deepcopy(value["source_runs"][0]))
    case("N17_wrong_missing_coordinate_ranges", "R02")["candidates"][0]["coordinate_mapping"]["missing_ranges"] = [[70, 76]]
    case("N18_rebound_source_sequence", "R03")["source_runs"][5]["bound_sequence_sha256"] = digest(b"other-sequence")
    value = case("N19_hidden_partial_metadata_failure", "R19")
    value["source_runs"][1]["complete"] = True
    case("N20_retry_without_previous_result", "R14")["prior_attempt_result_artifact_id"] = None
    return values


def check_rejections(builder: Builder) -> list[dict[str, Any]]:
    from pydantic import ValidationError

    checks = []
    for name, raw in rejection_cases(builder).items():
        try:
            S07Result.model_validate(raw)
        except ValidationError as exc:
            checks.append({"check_id": name, "passed": True, "rejection": exc.errors(include_input=False)[0]["msg"]})
        else:
            raise AssertionError(f"Invalid scientific/result state was accepted: {name}")
    return checks


def storage_checks(builder: Builder) -> list[dict[str, Any]]:
    checks = []

    def expect_rejection(name: str, operation, expected: type[Exception] | tuple[type[Exception], ...]):
        try:
            operation()
        except expected as exc:
            checks.append({"check_id": name, "passed": True, "rejection": str(exc).splitlines()[0]})
        else:
            raise AssertionError(f"Expected artifact/recovery guard did not reject: {name}")

    probe = EvidenceStore(builder.store.root / "controlled/storage-probes")
    ref = probe.put("same-length-corruption.bin", b"abc", "controlled_integrity_probe", "application/octet-stream")
    corrupt = probe.root / "objects" / ref["sha256"]
    corrupt.write_bytes(b"abd")  # Deliberately corrupt only this new controlled probe.
    expect_rejection("F01_same_size_hash_mismatch", lambda: probe.read(ref), ValueError)
    absent = copy.deepcopy(ref)
    absent.update(sha256=digest(b"missing"), size_bytes=7, artifact_id=f"sha256-{digest(b'missing')}")
    absent["resource_uri"] = f"artifact://{absent['artifact_id']}"
    expect_rejection("F02_missing_object", lambda: probe.read(absent), FileNotFoundError)
    immutable = probe.root / "immutable.json"
    immutable_write(immutable, b"original\n")
    expect_rejection("F03_overwrite_previous_evidence", lambda: immutable_write(immutable, b"replacement\n"), ValueError)
    if immutable.read_bytes() != b"original\n":
        raise AssertionError("Original bytes changed after a rejected overwrite")

    row = builder.case_rows[0]
    result_path = builder.store.root / row["result_path"]
    before = result_path.read_bytes()
    loaded = json.loads(before)
    builder.store.verify(loaded)
    builder.store.save_result(loaded)
    if result_path.read_bytes() != before:
        raise AssertionError("Repeated reads/saving the same result changed evidence")
    checks.append({"check_id": "F04_repeat_read_same_bytes_no_new_invocation", "passed": True, "sha256": digest(before)})

    changed = copy.deepcopy(loaded)
    snapshot = json.loads(builder.store.read(builder.store.refs[changed["input"]["input_artifact_id"]]))
    snapshot["organism_name"] = "CONTROLLED_DIFFERENT_ORGANISM"
    new_id = builder.store.put_json("changed-input-probe.json", snapshot, "controlled_binding_probe")
    changed["input"].update(input_artifact_id=new_id, organism_name=snapshot["organism_name"])
    changed["artifacts"].append(builder.store.refs[new_id])
    expect_rejection("F05_same_run_cannot_rebind_input", lambda: builder.store.save_result(changed), ValueError)

    first = next(item for item in builder.case_rows if item["case_id"] == "R13")
    second = next(item for item in builder.case_rows if item["case_id"] == "R14")
    prior_bytes = (builder.store.root / first["result_path"]).read_bytes()
    current = json.loads((builder.store.root / second["result_path"]).read_bytes())
    builder.store.verify(current)
    if current["prior_attempt_result_artifact_id"] != first["result_artifact_id"]:
        raise AssertionError("Retry lost the first result")
    if digest(prior_bytes) != builder.store.refs[first["result_artifact_id"]]["sha256"]:
        raise AssertionError("Retry overwrote its prior evidence")
    checks.append({"check_id": "F06_retry_preserves_prior_attempt_hash", "passed": True, "prior_sha256": digest(prior_bytes)})

    broken = next(ref for ref in builder.store.refs.values() if ref["artifact_type"] == "controlled_corrupt_structure")
    expect_rejection("F07_actual_mmcif_parse_failure",
                     lambda: MMCIF2Dict(str(builder.store.root / "objects" / broken["sha256"])), ValueError)
    return checks


def verify_campaign(campaign: Path) -> dict[str, Any]:
    index = task4.read_json(campaign / "artifact_index.json")
    store = EvidenceStore(campaign)
    for entry in index["artifacts"]:
        ref = entry["ref"]
        store.refs[ref["artifact_id"]] = ref
        store.origins[ref["artifact_id"]] = entry["origins"]
        store.read(ref)
    paths = sorted((campaign / "results").glob("*/attempt-*.json"))
    for path in paths:
        raw_bytes = path.read_bytes()
        store.verify(json.loads(raw_bytes))
        if f"sha256-{digest(raw_bytes)}" not in store.refs:
            raise ValueError(f"Result is missing from the external hash index: {path}")
    return {"status": "PASS", "result_count": len(paths), "artifact_count": len(store.refs), "network_calls": 0}


def build(campaign: Path) -> dict[str, Any]:
    from jsonschema import Draft202012Validator

    campaign = campaign.resolve()
    if not campaign.is_relative_to(ROOT):
        raise ValueError("Task-5 evidence must remain inside the workspace")
    if campaign.exists() and any(campaign.iterdir()):
        raise ValueError("Campaign already contains evidence; use --verify or a new --campaign name")
    builder = Builder(campaign)
    build_cases(builder)
    schema = S07Result.model_json_schema()
    Draft202012Validator.check_schema(schema)
    structural_validator = Draft202012Validator(schema)
    for raw in builder.cases.values():
        structural_validator.validate(raw)
    rejections = check_rejections(builder)
    files = storage_checks(builder)
    report = {
        "contract_version": CONTRACT_VERSION, "campaign_id": campaign.name, "generated_at": utc_now(),
        "status": "PASS_OFFLINE_CONTRACT_ONLY", "deployment_status": "NOT_DEPLOYED",
        "scientific_acceptance": "NOT_RUN", "network_calls": 0,
        "source_file_count": len(builder.imported),
        "source_file_bytes": sum(item["size_bytes"] for item in builder.imported.values()),
        "source_files_checked_against_prior_manifest": sum(
            item["checked_against_prior_manifest"] for item in builder.imported.values()
        ),
        "route_case_count": len(builder.case_rows), "rejection_check_count": len(rejections),
        "storage_check_count": len(files), "total_checks": len(builder.case_rows) + len(rejections) + len(files),
        "rule_status": "PROVISIONAL_USER_APPROVED_EXPERT_PENDING", "expert_confirmation_ids": RULE_IDS,
        "route_cases": builder.case_rows, "rejection_checks": rejections, "storage_checks": files,
        "limits": [
            "All route cases are controlled compositions or component probes, not new live end-to-end searches.",
            "R01 has a controlled one-candidate pool; the frozen 6Q00 file is real. It is not claimed as a new global optimum.",
            "R02 is a derived partial fixture. Real 9R2Q remains four-chain ambiguous in R17.",
            "R04 uses a controlled complete BLAST candidate set. Actual positive task-4 BLAST outputs hit the 100-row cap (R16).",
            "R06/R12 use a 12-aa component probe which a full T-01 run would reject at the earlier length guard.",
            "No S-09 confidence tier, CandidateRecord, production adapter, Dify deployment, or async runtime was created.",
            "Online API reruns may observe changed releases; frozen evidence replay alone guarantees byte-identical reads.",
        ],
    }
    immutable_write(campaign / "reports/task5_contract_evidence.json", json_bytes(report))
    immutable_write(campaign / "reports/source_evidence_index.json", json_bytes(builder.imported))
    immutable_write(campaign / "schema/S07_TASK5_RESULT_CONTRACT.schema.json", json_bytes(schema))
    # This is a generated review artifact, separate from frozen campaign results.
    SCHEMA.write_bytes(json_bytes(schema))
    immutable_write(campaign / "campaign.json", json_bytes({
        "campaign_id": campaign.name, "scope": "S-07 task 5 offline contract review",
        "execution_mode": "offline_contract_evidence", "production_deployment_status": "NOT_DEPLOYED",
        "network_calls": 0, "rules": RULE_IDS, "rules_status": report["rule_status"],
        "builder": "scripts/build_s07_task5_contract_evidence.py",
        "contract": "scripts/s07_task5_contract.py",
    }))
    builder.store.write_index()
    replay = verify_campaign(campaign)
    if replay["result_count"] != len(builder.case_rows):
        raise AssertionError("Saved-result replay count differs from the build")
    return {key: report[key] for key in (
        "campaign_id", "status", "route_case_count", "rejection_check_count", "storage_check_count",
        "total_checks", "source_file_count", "source_file_bytes", "source_files_checked_against_prior_manifest",
        "deployment_status", "network_calls",
    )}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument("--verify", action="store_true", help="Read saved artifacts only; do not rebuild or invoke APIs.")
    args = parser.parse_args()
    output = verify_campaign(args.campaign) if args.verify else build(args.campaign)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
