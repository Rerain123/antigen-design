"""Independent numerical comparison and convergence study, without G1 approval."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import time

import numpy as np
from Bio.PDB import Atom, Chain, Model, Residue, Structure
from Bio.PDB.SASA import ShrakeRupley
import Bio.PDB.SASA
import freesasa


def fingerprint(path):
    data = Path(path).read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def bio_areas(coords, radii, points, probe=1.4):
    # Each atom's element is a radius lookup token in this numerical-only entity.
    # No chemical identity or source PDB is modified; exact shared coordinates/radii
    # isolate the numerical algorithm from atom-selection and radius-model differences.
    structure = Structure.Structure("numerical_reference")
    model = Model.Model(0); structure.add(model)
    chain = Chain.Chain("A"); model.add(chain)
    residue = Residue.Residue((" ", 1, " "), "NUM", " "); chain.add(residue)
    radii_dict = {}
    for i, (xyz, radius) in enumerate(zip(coords, radii)):
        atom = Atom.Atom(str(i), np.asarray(xyz, dtype=np.float64), 0.0, 1.0, " ", str(i), i, element="C")
        atom.element = f"RADIUS_{i}"
        radii_dict[atom.element] = radius
        residue.add(atom)
    ShrakeRupley(probe_radius=probe, n_points=points, radii_dict=radii_dict).compute(structure)
    return [float(a.sasa) for a in structure.get_atoms()]


def analytic_spheres(radii, distance=None):
    """Exact exposed area of one sphere or two distinct-center spheres."""
    if len(radii) == 1:
        return [4 * math.pi * radii[0] ** 2]
    r, s = radii
    if distance >= r + s:
        return [4 * math.pi * r*r, 4 * math.pi * s*s]
    if distance <= abs(r-s):
        return [4 * math.pi * r*r, 0.0] if r > s else [0.0, 4 * math.pi * s*s]
    a = (distance*distance + r*r - s*s)/(2*distance)
    b = (distance*distance + s*s - r*r)/(2*distance)
    return [2*math.pi*r*(r+a), 2*math.pi*s*(s+b)]


def aggregate(atom_areas, atoms):
    areas = defaultdict(float)
    for area, atom in zip(atom_areas, atoms):
        areas[(atom['chain'], atom['residue_number'], atom['residue_name'])] += area
    return [{"chain": key[0], "residue_number": key[1], "residue_name": key[2], "absolute_sasa_a2": area}
            for key, area in areas.items()]


def compare(left, right, maxima):
    rows = []
    for a, b in zip(left['residues'], right['residues']):
        assert (a['chain'], a['residue_number'], a['residue_name']) == (b['chain'], b['residue_number'], b['residue_name'])
        denominator = maxima[a['residue_name']]
        rsa_a, rsa_b = a['absolute_sasa_a2']/denominator, b['absolute_sasa_a2']/denominator
        rows.append({"chain": a['chain'], "residue_number": a['residue_number'], "residue_name": a['residue_name'],
                     "delta_sasa_a2": a['absolute_sasa_a2'] - b['absolute_sasa_a2'],
                     "delta_rsa": rsa_a - rsa_b, "left_rsa": rsa_a, "right_rsa": rsa_b,
                     "buried_020_differs": (rsa_a < .2) != (rsa_b < .2)})
    absolute = sorted(abs(r['delta_rsa']) for r in rows)
    return {"left": left['id'], "right": right['id'],
            "total_delta_a2": left['total_sasa_a2'] - right['total_sasa_a2'],
            "total_relative_error": abs(left['total_sasa_a2'] - right['total_sasa_a2'])/right['total_sasa_a2'],
            "max_abs_residue_sasa_delta_a2": max(abs(r['delta_sasa_a2']) for r in rows),
            "max_abs_rsa_delta": max(absolute), "p95_abs_rsa_delta": absolute[math.ceil(.95*len(rows))-1],
            "buried_classification_differences": [r['residue_number'] for r in rows if r['buried_020_differs']],
            "residue_comparison": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--reference-spec', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(exist_ok=False)
    spec = json.loads(args.reference_spec.read_text())
    structure = freesasa.Structure(str(args.input), classifier=freesasa.Classifier.getStandardClassifier('protor'),
                                  options={'hetatm':False, 'hydrogen':False, 'join-models':False, 'skip-unknown':False, 'halt-at-unknown':True})
    atoms = [{'chain':structure.chainLabel(i), 'residue_number':structure.residueNumber(i).strip(),
              'residue_name':structure.residueName(i).strip(), 'atom_name':structure.atomName(i).strip(),
              'coordinate':list(structure.coord(i)), 'radius':structure.radius(i)} for i in range(structure.nAtoms())]
    coords = [a['coordinate'] for a in atoms]; radii = [a['radius'] for a in atoms]
    assert all(r>0 and math.isfinite(r) for r in radii)
    (args.output_dir/'shared_geometry.json').write_text(json.dumps(atoms,indent=2)+'\n')
    runs = []
    for slices in spec['lee_richards_slices']:
        timer=time.perf_counter()
        parameters={'algorithm':'LeeRichards','probe-radius':1.4,'n-slices':slices,'n-threads':1}
        result=freesasa.calc(structure, freesasa.Parameters(parameters))
        areas=[result.atomArea(i) for i in range(result.nAtoms())]
        run={'id':f'FreeSASA-LR-{slices}','parameters':parameters,'total_sasa_a2':result.totalArea(),
             'atoms_sasa_a2':areas,'residues':aggregate(areas,atoms),'elapsed_seconds':time.perf_counter()-timer}
        runs.append(run)
        (args.output_dir/(run['id']+'.json')).write_text(json.dumps(run,indent=2,allow_nan=False)+'\n')
        print(run['id'],run['total_sasa_a2'],flush=True)
    for points in spec['biopython_sphere_points']:
        timer=time.perf_counter()
        areas=bio_areas(coords,radii,points)
        run={'id':f'Biopython-SR-{points}','parameters':{'probe-radius':1.4,'n-points':points},
             'total_sasa_a2':sum(areas),'atoms_sasa_a2':areas,'residues':aggregate(areas,atoms),
             'elapsed_seconds':time.perf_counter()-timer}
        runs.append(run)
        (args.output_dir/(run['id']+'.json')).write_text(json.dumps(run,indent=2,allow_nan=False)+'\n')
        print(run['id'],run['total_sasa_a2'],flush=True)
    geometry=[]
    for case in spec['analytic_cases']:
        radii=case['atomic_radii_a']; xyz=case['coordinates_a']
        expected=analytic_spheres([r+1.4 for r in radii],case.get('distance_a'))
        result=freesasa.calcCoord([v for point in xyz for v in point],radii,
                                 freesasa.Parameters({'algorithm':'LeeRichards','probe-radius':1.4,'n-slices':200,'n-threads':1}))
        free=[result.atomArea(i) for i in range(result.nAtoms())]
        bio=bio_areas(xyz,radii,15360)
        geometry.append({'case_id':case['id'],'expected_analytic_a2':expected,'freesasa_lr200_a2':free,'biopython_sr15360_a2':bio})
    maxima=spec['tien_theoretical_by_three_letter']
    reference=runs[-1]
    comparisons=[compare(r,reference,maxima) for r in runs[:-1]]
    output={'scope':'NUMERICAL_REFERENCE_AND_CONVERGENCE_ONLY','recorded_at':datetime.now(timezone.utc).isoformat(),
            'freesasa_version':metadata.version('freesasa'),'biopython_version':metadata.version('biopython'),
            'freesasa_module':fingerprint(freesasa.__file__),'biopython_sasa_source':fingerprint(Bio.PDB.SASA.__file__),
            'input':fingerprint(args.input),'reference_spec':fingerprint(args.reference_spec),'probe_source':fingerprint(__file__),
            'network_interfaces':sorted(p.name for p in Path('/sys/class/net').iterdir()),
            'comparisons':comparisons,'analytic_cases':geometry,
            'independence':'Biopython SR is independent surface-integration code; geometry and ProtOr radius assignments are deliberately shared',
            'limitations':['One real protein, no held-out population','Shared radii and input do not validate chemical context or experimental truth','No scientific tolerance is approved by this script'],
            'production_approved':False}
    (args.output_dir/'comparison.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
