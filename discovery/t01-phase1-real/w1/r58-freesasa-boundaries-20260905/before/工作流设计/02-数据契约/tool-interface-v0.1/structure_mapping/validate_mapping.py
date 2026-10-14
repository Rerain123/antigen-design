"""Portable structural checks for a mapping file; does not approve scientific alignment."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys

from jsonschema import Draft202012Validator, FormatChecker

BASE = Path(__file__).resolve().parent
AA = dict(zip(['ALA', 'ARG', 'ASN', 'ASP', 'CYS', 'GLU', 'GLN', 'GLY', 'HIS', 'ILE', 'LEU', 'LYS', 'MET', 'PHE', 'PRO', 'SER', 'THR', 'TRP', 'TYR', 'VAL'], 'ARNDCEQGHILKMFPSTWYV'))


def strict_json(path):
    # Load only the shared local JSON reader; no network or Biopython dependency.
    spec = importlib.util.spec_from_file_location('shared_interface_json', BASE.parent / 'validate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.strict_json(path)


def validate_mapping(value, *, sequence=None, structure_sha256=None, expected_status=None):
    schema = strict_json(BASE / 'mapping.schema.json')
    Draft202012Validator.check_schema(schema)
    errors = [f"{'.'.join(map(str,e.absolute_path))}: {e.message}" for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)]
    if errors:
        return errors
    seq = value['sequence']
    if hashlib.sha256(seq.encode()).hexdigest() != value['sequence_sha256']:
        errors.append('sequence_sha256 mismatch')
    if sequence is not None and seq != sequence:
        errors.append('mapping sequence does not match request')
    if structure_sha256 is not None and value['structure_sha256'] != structure_sha256:
        errors.append('mapping structure_sha256 does not match structure')
    if expected_status is not None and value['mapping_status'] != expected_status:
        errors.append('mapping_status does not match request')
    expected_namespace = 'auth_asym_id' if value['format'] == 'mmcif' else 'pdb_chain_id'
    if value['parser']['chain_namespace'] != expected_namespace:
        errors.append('author chain namespace mismatch')
    entries = value['entries']
    if len(entries) != len(seq) or [e['sequence_position'] for e in entries] != list(range(1,len(seq)+1)):
        errors.append('entries must cover each input position exactly once in order')
    if ''.join(e['sequence_residue'] for e in entries) != seq:
        errors.append('entry residues do not match input sequence')
    addresses = set()
    for entry in entries:
        a = entry['structure_residue']
        if a is None:
            if entry['reason'] == 'mapped':
                errors.append('null address cannot be mapped')
            continue
        if entry['reason'] != 'mapped' or a['chain_id'] != value['target_chain_id']:
            errors.append('mapped address must use selected target chain')
        if AA.get(a['residue_name']) != entry['sequence_residue']:
            errors.append('mapped residue identity differs; this method does not permit substitutions')
        key = (a['chain_id'], a['res_seq'], a['insertion_code'])
        if key in addresses:
            errors.append('duplicate author chain/resSeq/iCode address')
        addresses.add(key)
    candidates = value['chain_candidates']
    if len({c['chain_id'] for c in candidates}) != len(candidates):
        errors.append('duplicate candidate chain ID')
    selected = [c for c in candidates if c['chain_id'] == value['target_chain_id']]
    if value['target_chain_id'] is None:
        if addresses or value['mapping_status'] != 'unreliable' or value['fixed_chain_ids']:
            errors.append('unresolved chain must not publish mapped or fixed positions')
        if any(e['reason'] != 'unresolved_mapping' for e in entries):
            errors.append('unresolved mapping cannot claim confirmed missing residues')
    else:
        if value['model_index'] is None or len(selected) != 1 or selected[0]['match_status'] not in {'exact','partial_unique'}:
            errors.append('selected chain/model must have a unique supported candidate')
        else:
            c = selected[0]
            mapped = [e for e in entries if e['structure_residue'] is not None]
            if c['positions'] != [e['sequence_position'] for e in mapped] or c['observed_sequence'] != ''.join(e['sequence_residue'] for e in mapped):
                errors.append('selected candidate and mapping entries differ')
        if len([c for c in candidates if c['match_status'] != 'no_match']) != 1:
            errors.append('other candidate chains are still possible or unresolved')
        if value['target_chain_id'] in value['fixed_chain_ids']:
            errors.append('target chain cannot also be fixed')
    for c in candidates:
        positions = c['positions']
        if positions is not None:
            if (len(positions) != len(c['observed_sequence']) or positions != sorted(set(positions)) or any(p > len(seq) for p in positions)):
                errors.append('invalid candidate positions')
            elif ''.join(seq[p-1] for p in positions) != c['observed_sequence']:
                errors.append('candidate positions disagree with sequence')
        if (c['match_status'] in {'exact','partial_unique'}) != (positions is not None):
            errors.append('candidate position availability does not match state')
    if value['mapping_status'] == 'verified' and any(i['code'] in {'G1_REVIEW_PENDING','MAPPING_NOT_UNIQUE','UNSUPPORTED_RESIDUE_OR_ADDRESS'} for i in value['issues']):
        errors.append('verified mapping still carries unresolved blocking issues')
    return errors


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        errors=validate_mapping(strict_json(args.mapping))
    except (OSError,ValueError) as exc:
        errors=[str(exc)]
    print(json.dumps({'status':'FAIL' if errors else 'PASS','scope':'mapping_structure_and_consistency_only','scientific_approval':'NOT_EVALUATED','errors':errors},ensure_ascii=False,indent=2))
    return 1 if errors else 0


if __name__=='__main__':
    sys.exit(main())
