"""Fixed, offline FreeSASA development worker for prepared B1 consumer cases."""
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import sys

import freesasa

sys.path.insert(0, '/code/src')
from t01_structure_mapping.freesasa_consumer import ConsumerError, load_preparation, validate_tool_atoms, join_areas, require
from t01_structure_mapping.probe import sha


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def run_case(folder, output, profile):
    summary = dict(status='REJECTED', error_code=None, error=None, tool_invoked=False,
                   calculation_started=False, usable_for_pipeline=False, scientific_approval=None,
                   normal_rsa_result=None, buried_fraction=None, production_status='NOT_DEPLOYED')
    try:
        prepared, prepared_result = load_preparation(folder, Path('/profile.json').read_bytes())
        binding = prepared['binding']
        summary.update(route=prepared['route'], binding=binding, preparation_sha256=prepared_result['preparation_sha256'])
        summary['tool_invoked'] = True
        classifier = freesasa.Classifier.getStandardClassifier(profile['calculation']['classifier'])
        radii = [dict(raw_row_index=a['raw_row_index'], raw_residue_id=a['raw_residue_id'],
                      radius=classifier.radius(a['residue_name'], a['atom_name'])) for a in prepared['atoms']]
        write(output / 'classifier.json', radii)
        require(all(math.isfinite(row['radius']) and row['radius'] > 0 for row in radii),
                'UNKNOWN_PROTOR_RADIUS', 'Classifier returned an unknown radius; guessing is forbidden', radii)
        if prepared['route'] == 'pdb_file':
            path = folder / 'prepared.pdb'
            require(sha(path.read_bytes()) == prepared['pdb_sha256'], 'PDB_HASH_MISMATCH', 'Derived PDB changed')
            structure = freesasa.Structure(str(path), classifier=classifier, options=profile['calculation']['structure_options'])
        else:
            structure = freesasa.Structure(classifier=classifier, options=profile['calculation']['structure_options'])
            for atom in prepared['atoms']:
                structure.addAtom(atom['tool_atom_name'], atom['residue_name'], atom['tool_residue_token'],
                                  atom['chain_id'], *atom['coordinate_tool'])
        observed = [dict(tool_atom_index=i, chain_id=structure.chainLabel(i),
            tool_residue_token=structure.residueNumber(i).strip(), raw_tool_residue_number=structure.residueNumber(i),
            residue_name=structure.residueName(i).strip(), atom_name=structure.atomName(i).strip(),
            raw_tool_atom_name=structure.atomName(i),
            coordinate=list(structure.coord(i)), radius=structure.radius(i)) for i in range(structure.nAtoms())]
        write(output / 'tool_atoms.json', observed)  # Raw tool identity evidence precedes checking.
        joined = validate_tool_atoms(prepared, observed)
        expected_radii = {row['raw_row_index']: row['radius'] for row in radii}
        require(all(row['radius'] == expected_radii[row['raw_row_index']] for row in joined),
                'TOOL_RADIUS_MISMATCH', 'Tool radii differ from the explicit classifier')
        write(output / 'verified_atoms.json', joined)
        parameters = profile['calculation']['parameters']
        summary['calculation_started'] = True
        result = freesasa.calc(structure, freesasa.Parameters(parameters))
        areas = [dict(tool_atom_index=i, absolute_sasa_a2=result.atomArea(i)) for i in range(result.nAtoms())]
        total = result.totalArea()
        numeric = dict(parameters=parameters, freesasa_version=version('freesasa'), atom_areas=areas, total_sasa_a2=total)
        if any(not math.isfinite(a['absolute_sasa_a2']) for a in areas) or not math.isfinite(total):
            (output / 'nonfinite_numeric.txt').write_text(repr(numeric), encoding='utf-8')
            raise ConsumerError('INVALID_NUMERIC_OUTPUT', 'Non-finite raw output retained')
        write(output / 'raw_areas.json', numeric)
        result_by_raw = join_areas(prepared, observed, areas)
        summed = math.fsum(a['absolute_sasa_a2'] for a in areas)
        require(total >= 0 and abs(summed - total) <= math.ulp(max(summed, total)) * max(1, len(areas)),
                'TOTAL_AREA_MISMATCH', 'Reported total is inconsistent with its atom areas')
        write(output / 'raw_residue_areas.json', dict(result_by_raw, binding=binding,
            preparation_sha256=summary['preparation_sha256'], raw_areas_sha256=sha((output / 'raw_areas.json').read_bytes())))
        summary.update(status='SUCCESS_RAW_ONLY', atom_count=len(areas), residue_count=len(result_by_raw['residues']),
                       total_sasa_a2=total, identity_check='PASS', radius_check='PASS')
    except ConsumerError as error:
        summary.update(status='REJECTED', error_code=error.code, error=str(error))
    except Exception as error:
        summary.update(status='REJECTED', error_code='TOOL_EXECUTION_ERROR', error=str(error))
    write(output / 'result.json', summary)
    return summary


def main():
    output = Path('/out/results')
    output.mkdir(exist_ok=False)
    profile = read(Path('/profile.json'))
    runtime = dict(python=platform.python_version(), freesasa=version('freesasa'), biopython=version('biopython'), numpy=version('numpy'))
    require(all(value == profile['runtime'][key] for key, value in runtime.items()), 'VERSION_MISMATCH', 'Unexpected tool/dependency version')
    plan = read(Path('/cases/expected_cases.json'))
    summary = []
    for case in plan['cases']:
        prepared = Path('/cases/prepared') / case['id']
        if read(prepared / 'consumer_result.json')['status'] != 'READY_FOR_TOOL_PROBE':
            continue
        target = output / case['id']
        target.mkdir()
        record = run_case(prepared, target, profile)
        summary.append(dict(id=case['id'], **record))
        print(case['id'], record['status'], record['error_code'], flush=True)
    write(Path('/out/campaign.json'), dict(scope='B1_FREESASA_CONSUMER_DEVELOPMENT',
        network_interfaces=os.listdir('/sys/class/net'), freesasa_version=version('freesasa'),
        observed_runtime=runtime,
        profile_sha256=sha(Path('/profile.json').read_bytes()), plan_sha256=sha(Path('/cases/expected_cases.json').read_bytes()),
        cases=summary, production_status='NOT_DEPLOYED', scientific_approval=None))


if __name__ == '__main__':
    main()
