"""Reproduce this batch's bounded local inventory; never run a scientific tool."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sys

from Bio.PDB.MMCIF2Dict import MMCIF2Dict

ROOT = Path(__file__).resolve().parents[4]
SAMPLES = ROOT / "tests/fixtures/structure_mapping/real"
MAPPING = ROOT / "discovery/t01-phase1-real/w1/r58-local-20260905/real-1ubq/mapping.json"


def fingerprint(path):
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def rows(data, prefix):
    columns = {key[len(prefix):]: values for key, values in data.items() if key.startswith(prefix)}
    if not columns:
        return []
    lengths = {len(values) for values in columns.values()}
    if len(lengths) != 1:
        raise ValueError(f"Unequal column lengths: {prefix}")
    return [dict(zip(columns, values)) for values in zip(*columns.values())]


def missing_to_empty(value):
    return "" if value in {".", "?"} else value


def audit_sample(sample_id):
    data = MMCIF2Dict(str(SAMPLES / f"{sample_id}.cif"))
    atoms = rows(data, "_atom_site.")
    polymer_atoms = [a for a in atoms if a["label_seq_id"] not in {".", "?"}]
    residues = {}
    for atom in polymer_atoms:
        address = (atom["pdbx_PDB_model_num"], atom["auth_asym_id"], atom["auth_seq_id"],
                   missing_to_empty(atom["pdbx_PDB_ins_code"]), atom["label_comp_id"])
        residues.setdefault(address, set()).add(atom["label_atom_id"])
    result = {
        "sample_id": sample_id,
        "method_reported_in_file": data.get("_exptl.method", []),
        "refinement_resolution_reported_in_file": data.get("_refine.ls_d_res_high", []),
        "atom_rows": len(atoms), "polymer_atom_rows": len(polymer_atoms),
        "nonpolymer_atom_rows": len(atoms) - len(polymer_atoms),
        "polymer_residue_count": len(residues),
        "polymer_residues_by_author_chain": dict(Counter(a[1] for a in residues)),
        "models": sorted({a["pdbx_PDB_model_num"] for a in atoms}),
        "all_atom_names": sorted({a["label_atom_id"] for a in atoms}),
        "all_atoms_are_ca": all(a["label_atom_id"] == "CA" for a in atoms),
        "nonpolymer_residue_names": sorted({a["label_comp_id"] for a in atoms if a["label_seq_id"] in {".", "?"}}),
        "polymer_altloc_values": sorted({a["label_alt_id"] for a in polymer_atoms}),
        "polymer_occupancy_values": sorted({a["occupancy"] for a in polymer_atoms}),
        "polymer_residues_missing_named_backbone_atoms": [
            {"address": list(address), "absent_names": sorted({"N", "CA", "C", "O"} - names)}
            for address, names in residues.items() if not {"N", "CA", "C", "O"}.issubset(names)
        ],
        "observed_atoms_by_polymer_residue": [
            {"model": a[0], "author_chain": a[1], "author_seq_id": a[2], "insertion_code": a[3],
             "residue_name": a[4], "atom_names": sorted(names)} for a, names in residues.items()
        ] if sample_id == "1UBQ" else [],
        "full_atom_completeness": "NOT_ASSESSED",
        "missing_atom_fraction": None, "freesasa_context": "NOT_APPROVED",
        "scientific_acceptance": "NOT_RUN",
    }
    if sample_id == "1UBQ":
        sequence = "".join(line.strip() for line in (SAMPLES / "1UBQ.fasta").read_text().splitlines()
                           if line.strip() and not line.startswith(">"))
        entities = rows(data, "_entity_poly.")
        entity_sequence = "".join(entities[0]["pdbx_seq_one_letter_code_can"].split())
        mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
        scheme = rows(data, "_pdbx_poly_seq_scheme.")
        comparisons = []
        for entry, item in zip(mapping["entries"], scheme):
            residue = entry["structure_residue"]
            expected = (item["pdb_strand_id"], item["auth_seq_num"],
                        missing_to_empty(item["pdb_ins_code"]), item["mon_id"])
            actual = (residue["chain_id"], str(residue["res_seq"]), residue["insertion_code"], residue["residue_name"])
            matching_atoms = [a for a in polymer_atoms if a["label_asym_id"] == item["asym_id"]
                              and a["label_seq_id"] == item["seq_id"]]
            coordinate_addresses = {(a["auth_asym_id"], a["auth_seq_id"],
                                     missing_to_empty(a["pdbx_PDB_ins_code"]), a["label_comp_id"])
                                    for a in matching_atoms}
            comparisons.append(expected == actual and coordinate_addresses == {expected}
                               and entry["sequence_position"] == int(item["seq_id"]))
        checks = {"entity_sequence_equals_fasta": entity_sequence == sequence,
                  "one_polymer_entity": len(entities) == 1,
                  "row_counts_match": len(scheme) == len(sequence) == len(mapping["entries"]),
                  "all_scheme_and_coordinate_addresses_match": bool(comparisons) and all(comparisons)}
        result["entity_scheme_comparison"] = {
            "method": "Compare deposited entity sequence and scheme/atom columns directly; do not call t01_structure_mapping",
            "independence_limit": "Same deposited file and Biopython tokenizer; not an independent scientific gold standard",
            "checks": checks, "checked_positions": len(comparisons),
            "mapping_status_unchanged": mapping["mapping_status"],
        }
        if not all(checks.values()):
            raise ValueError("1UBQ entity/scheme comparison failed")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.relative_to(ROOT)
    if output.exists():
        raise SystemExit("Use a fresh output directory; prior evidence must not be overwritten")
    dependencies = {}
    for name in ("biopython", "numpy", "jsonschema", "freesasa", "alphafold3", "esm", "deeptmhmm"):
        try:
            dependencies[name] = {"observation": "DISTRIBUTION_METADATA_FOUND", "version": metadata.version(name)}
        except metadata.PackageNotFoundError:
            dependencies[name] = {"observation": "NO_DISTRIBUTION_METADATA_IN_THIS_PYTHON", "version": None}
    environment = {
        "profile_id": "w1-local-development-windows", "scope": "CURRENT_PROCESS_ONLY_NOT_CUSTOMER_TARGET",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "os": {"system": platform.system(), "release": platform.release(), "version": platform.version(), "machine": platform.machine()},
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "logical_cpu_count": os.cpu_count(), "workspace_disk_free_bytes": shutil.disk_usage(ROOT).free,
        "python_distributions": dependencies,
        "commands_on_current_path": {name: shutil.which(name) for name in ("freesasa", "nvidia-smi", "docker", "wsl")},
        "limitations": ["No container, WSL, remote host, alternate Python or independent deployment-project inventory",
                        "PATH and distribution lookup cannot establish model identity, installed assets, license or offline execution",
                        "No scientific executable or model was run; no package was installed"],
        "customer_target_profile": None, "target_g0": "NOT_RUN", "production_status": "NOT_DEPLOYED",
    }
    manifest = json.loads((SAMPLES / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    for sample in manifest["samples"]:
        for source in sample["files"]:
            actual = fingerprint(SAMPLES / source["path"])
            if actual["sha256"] != source["sha256"] or actual["bytes"] != source["bytes"]:
                raise ValueError(f"Source mismatch: {source['path']}")
    audit = {"scope": "LOCAL_SAMPLE_FACTS_ONLY", "samples": [audit_sample(s) for s in ("1UBQ", "5XZC")]}
    inputs = [Path(__file__).resolve(), SAMPLES / "SOURCE_MANIFEST.json", MAPPING,
              ROOT / "requirements/structure-mapping.txt"]
    inputs += [SAMPLES / f"{s}.{ext}" for s in ("1UBQ", "5XZC") for ext in ("cif", "fasta")]
    output.mkdir(parents=True)
    for name, value in (("environment.json", environment), ("sample_audit.json", audit)):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {"scope": "W1_01_02_LOCAL_PREPARATION", "command_argv": [sys.executable, *sys.argv],
              "status": "PASS", "inputs": [fingerprint(p) for p in inputs],
              "outputs": [fingerprint(output / n) for n in ("environment.json", "sample_audit.json")],
              "target_g0": "NOT_RUN", "g1": "NOT_RUN", "production_status": "NOT_DEPLOYED"}
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "output_dir": str(output), "inputs": len(inputs), "samples": 2}))


if __name__ == "__main__":
    main()
