"""Local G0 raw FreeSASA probe. No RSA normalization or production routing."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import sys
import time


def fingerprint(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path), "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def coordinates(structure):
    return [(model.id, chain.id, list(residue.id), residue.resname, atom.name, atom.altloc,
             [round(float(v), 3) for v in atom.coord])
            for model in structure for chain in model for residue in chain.get_unpacked_list()
            for atom in residue.get_unpacked_list()]


def convert_cif(source, destination):
    from Bio.PDB import MMCIFParser, PDBIO, PDBParser
    original = MMCIFParser(QUIET=False, auth_chains=True, auth_residues=True).get_structure("probe", source)
    if len(original) != 1:
        raise ValueError("This G0 conversion only accepts a single explicitly inventoried MODEL")
    io = PDBIO()
    io.set_structure(original)
    io.save(str(destination), preserve_atom_numbering=True)
    reread = PDBParser(PERMISSIVE=False, QUIET=False).get_structure("reread", destination)
    if coordinates(original) != coordinates(reread):
        raise ValueError("PDB conversion changed residue/atom identity or rounded coordinates")
    return {"source": fingerprint(source), "derived": fingerprint(destination),
            "atom_rows": len(coordinates(original)), "identity_and_pdb_precision_roundtrip": "PASS",
            "coordinate_check": "Compare at PDB's three decimal places; not a scientific tolerance or general losslessness claim"}


def capture_raw(structure, result):
    atom_rows = []
    for index in range(structure.nAtoms()):
        atom_rows.append({"index": index, "chain": structure.chainLabel(index),
                          "residue_number": structure.residueNumber(index).strip(),
                          "residue_name": structure.residueName(index).strip(),
                          "atom_name": structure.atomName(index).strip(),
                          "coordinate": structure.coord(index), "radius": structure.radius(index),
                          "absolute_sasa_a2": result.atomArea(index)})
    residues = []
    for chain, areas in result.residueAreas().items():
        for number, area in areas.items():
            residues.append({"chain": chain, "residue_number": number.strip(),
                             "residue_name": area.residueType, "absolute_sasa_a2": area.total,
                             "main_chain_a2": area.mainChain, "side_chain_a2": area.sideChain,
                             "polar_a2": area.polar, "apolar_a2": area.apolar,
                             "native_relative_total_not_project_rsa": area.relativeTotal if area.hasRelativeAreas else None})
    values = [row["absolute_sasa_a2"] for row in atom_rows + residues] + [result.totalArea()]
    return {"total_sasa_a2": result.totalArea(), "atom_count": structure.nAtoms(),
            "result_atom_count": result.nAtoms(), "residue_count": len(residues),
            "atoms": atom_rows, "residues": residues,
            "engineering_checks": {
                "finite_nonnegative_areas": all(math.isfinite(v) and v >= 0 for v in values),
                "atom_count_matches": structure.nAtoms() == result.nAtoms(),
                "atom_sum_matches_total": math.isclose(sum(r["absolute_sasa_a2"] for r in atom_rows), result.totalArea(), rel_tol=1e-12, abs_tol=1e-8),
                "residue_sum_matches_total": math.isclose(sum(r["absolute_sasa_a2"] for r in residues), result.totalArea(), rel_tol=1e-12, abs_tol=1e-8),
            }, "check_tolerance_scope": "Floating-point aggregation sanity only, not scientific agreement"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("native", "cif-to-pdb", "biopython"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit("Use a fresh output directory")
    args.output_dir.mkdir(parents=True)
    import freesasa
    started = datetime.now(timezone.utc).isoformat()
    timer = time.perf_counter()
    params = freesasa.Parameters()
    effective = {"algorithm": params.algorithm(), "probe-radius": params.probeRadius(),
                 "n-points": params.nPoints(), "n-slices": params.nSlices(), "n-threads": params.nThreads()}
    environment = {"scope": "ISOLATED_LOCAL_DOCKER_G0_RAW_OUTPUT", "python": platform.python_version(),
                   "os": platform.platform(), "freesasa_python_version": metadata.version("freesasa"),
                   "biopython_version": metadata.version("biopython"), "numpy_version": metadata.version("numpy"),
                   "freesasa_module": fingerprint(freesasa.__file__),
                   "license_metadata": metadata.metadata("freesasa").get("License"),
                   "default_structure_options": freesasa.Structure.defaultOptions,
                   "effective_parameters": effective,
                   "parameter_scope": "Observed package defaults for G0; production profile not approved",
                   "network_interfaces": sorted(p.name for p in Path('/sys/class/net').iterdir()),
                   "network_scope": "Runtime launched with Docker network=none; dependencies fetched during image build"}
    outcome = {"input": fingerprint(args.input), "command": [sys.executable, *sys.argv],
               "started_at": started, "mode": args.mode, "production_result": None,
               "usable_for_pipeline": False, "review_required": True,
               "mapping_approval": "NOT_GRANTED", "scientific_acceptance": "NOT_RUN"}
    code = 0
    try:
        path = args.input
        if args.mode == "cif-to-pdb":
            path = args.output_dir / "converted.pdb"
            outcome["conversion"] = convert_cif(args.input, path)
        if args.mode == "biopython":
            from Bio.PDB import MMCIFParser, PDBParser
            reader = MMCIFParser(QUIET=False, auth_chains=True, auth_residues=True) if path.suffix in {".cif", ".mmcif"} else PDBParser(PERMISSIVE=False, QUIET=False)
            bio = reader.get_structure("probe", path)
            if len(bio) != 1:
                raise ValueError("This G0 bridge only accepts one MODEL")
            structure = freesasa.structureFromBioPDB(bio)
        else:
            structure = freesasa.Structure(str(path))
        result = freesasa.calc(structure, params)
        raw = capture_raw(structure, result)
        (args.output_dir / "raw.json").write_text(json.dumps(raw, indent=2, allow_nan=False) + "\n")
        outcome.update({"execution_status": "succeeded", "raw_artifact": fingerprint(args.output_dir / "raw.json")})
    except Exception as error:
        outcome.update({"execution_status": "failed", "error_type": type(error).__name__, "error": str(error)})
        code = 1
    outcome.update({"tool_probe_exit_code": code, "elapsed_seconds": time.perf_counter() - timer,
                    "finished_at": datetime.now(timezone.utc).isoformat()})
    for name, value in (("environment.json", environment), ("probe_result.json", outcome)):
        (args.output_dir / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"execution_status": outcome["execution_status"], "exit_code": code, "mode": args.mode}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
