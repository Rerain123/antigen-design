"""Follow up serialization/identity findings without overwriting the first probe."""
import json
import math
from pathlib import Path
from Bio.PDB import PDBIO, PDBParser
import freesasa


def safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"raw_nonfinite_token": repr(value)}
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    return value


def observe(path, bridge):
    bio = PDBParser(PERMISSIVE=False, QUIET=False).get_structure("probe", path)
    structure = freesasa.structureFromBioPDB(bio) if bridge else freesasa.Structure(str(path))
    addresses = [(structure.chainLabel(i), structure.residueNumber(i).strip(), structure.residueName(i).strip())
                 for i in range(structure.nAtoms())]
    result = freesasa.calc(structure)
    areas = [{"chain": chain, "residue_number": number.strip(), "residue_name": area.residueType,
              "absolute_sasa_a2": area.total, "native_relative_total": area.relativeTotal}
             for chain, residues in result.residueAreas().items() for number, area in residues.items()]
    return safe({"bridge": bridge, "atom_count": structure.nAtoms(), "per_atom_residue_identity": addresses,
                 "unique_residue_addresses": sorted({(a[0], a[1]) for a in addresses}),
                 "raw_residue_areas": areas, "total_sasa_a2": result.totalArea(),
                 "nonfinite_absolute_atom_indices": [i for i in range(result.nAtoms()) if not math.isfinite(result.atomArea(i))],
                 "identity_verified_for_pipeline": False})


def main():
    out = Path('/out')
    # Synthetic numbering challenge on the already converted local 1UBQ copy.
    bio = PDBParser(PERMISSIVE=False, QUIET=False).get_structure("renumbered", '/converted.pdb')
    bio[0]['A'][(' ', 43, ' ')].id = (' ', 42, 'A')
    io = PDBIO(); io.set_structure(bio)
    path = out/'synthetic-renumbered-1ubq.pdb'
    if path.exists():
        raise SystemExit('Use a fresh follow-up directory')
    io.save(str(path), preserve_atom_numbering=True)
    results = {"scope": "RAW_DIAGNOSTIC_NOT_SCIENTIFIC_ACCEPTANCE", "nonfinite_encoding": "Tagged original value; not null or zero",
               "synthetic_numbering": "Only 1UBQ A43 changed to A42A for interface identity testing; no biological claim",
               "synthetic_icode_native": observe(path, False), "synthetic_icode_bridge": observe(path, True),
               "old_toy_native": observe('/input/partial-icode.pdb', False),
               "old_toy_bridge": observe('/input/partial-icode.pdb', True)}
    (out/'inspection.json').write_text(json.dumps(results, indent=2, allow_nan=False)+'\n')
    print(json.dumps({"status": "CAPTURED", "cases": 4}))


if __name__ == '__main__':
    main()
