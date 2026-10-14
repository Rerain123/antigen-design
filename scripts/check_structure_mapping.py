"""Reparse a local structure and compare mapping addresses with fresh probe facts."""
import argparse
import json
from pathlib import Path
import sys

from probe_structure_mapping import mapping_validator
from t01_structure_mapping.probe import parse_local, propose, read_sequence


def check(mapping_path, structure_path, sequence_path):
    validator=mapping_validator()
    value=validator.strict_json(mapping_path)
    sequence=read_sequence(sequence_path)
    inventory=parse_local(structure_path)
    errors=validator.validate_mapping(value,sequence=sequence,structure_sha256=inventory['structure_sha256'])
    if errors:
        return errors
    fresh=propose(sequence,inventory,evidence_kind=value['evidence_kind'],
                  model_index=value['selection']['requested_model_index'], requested_chain=value['selection']['requested_chain_id'])
    for key in ['target_chain_id','model_index','model_serial','fixed_chain_ids','chain_candidates','entries','parser','format','method']:
        if value[key]!=fresh[key]:
            errors.append(f'{key}: differs from fresh local parse/mapping candidate')
    return errors


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping',type=Path,required=True)
    parser.add_argument('--structure',type=Path,required=True)
    parser.add_argument('--sequence-file',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        errors=check(args.mapping,args.structure,args.sequence_file)
    except (OSError,ValueError,KeyError) as exc:
        errors=[str(exc)]
    print(json.dumps({'status':'FAIL' if errors else 'PASS','scope':'local_reparse_and_mapping_consistency','scientific_approval':'NOT_EVALUATED','errors':errors},ensure_ascii=False,indent=2))
    return 1 if errors else 0


if __name__=='__main__':
    sys.exit(main())
