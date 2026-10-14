"""Run the local R-58 development probe in a fresh evidence directory."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from t01_structure_mapping.probe import parse_local, propose, read_sequence, sha


def mapping_validator():
    path = ROOT / '工作流设计/02-数据契约/tool-interface-v0.1/structure_mapping/validate_mapping.py'
    spec = importlib.util.spec_from_file_location('r58_mapping_validator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def run(structure, sequence_file, output_dir, evidence_kind, model_index=None, chain_id=None):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    evidence = {'scope': 'LOCAL_PARSING_AND_MAPPING_PROBE', 'production_status': 'NOT_DEPLOYED',
                'scientific_acceptance': 'NOT_RUN', 'evidence_kind': evidence_kind,
                'python': sys.version, 'platform': platform.platform(), 'command': sys.argv,
                'started_at': started, 'network_retrieval': 'NONE_IMPLEMENTED', 'files': []}
    try:
        seq = read_sequence(sequence_file)
        inventory = parse_local(structure)
        mapping = propose(seq, inventory, evidence_kind=evidence_kind, model_index=model_index, requested_chain=chain_id)
        errors = mapping_validator().validate_mapping(mapping, sequence=seq, structure_sha256=sha(Path(structure).read_bytes()))
        if errors:
            raise ValueError('Generated mapping failed validation: ' + '; '.join(errors))
        evidence.update(status='PASS', parse_status='succeeded', mapping_status=mapping['mapping_status'],
                        target_chain_id=mapping['target_chain_id'], mapped_positions=sum(e['structure_residue'] is not None for e in mapping['entries']),
                        sequence_length=len(seq), structure_sha256=inventory['structure_sha256'], sequence_sha256=mapping['sequence_sha256'],
                        sequence_file_sha256=sha(Path(sequence_file).read_bytes()), biopython=inventory['parser']['version'])
        write_json(output / 'structure_inventory.json', inventory)
        write_json(output / 'mapping.json', mapping)
        for name in ['structure_inventory.json', 'mapping.json']:
            data = (output / name).read_bytes()
            evidence['files'].append({'path': name, 'size_bytes': len(data), 'sha256': sha(data)})
    except Exception as exc:
        evidence.update(status='FAIL', parse_or_mapping_error=str(exc))
    evidence['finished_at'] = datetime.now(timezone.utc).isoformat()
    write_json(output / 'probe_result.json', evidence)
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structure', type=Path, required=True)
    parser.add_argument('--sequence-file', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--evidence-kind', choices=['local_input','synthetic_fixture'], required=True)
    parser.add_argument('--model-index', type=int)
    parser.add_argument('--chain-id', help='Ingestion chain request; cannot resolve competing design chains by itself')
    args = parser.parse_args(argv)
    if args.model_index is not None and args.model_index < 0:
        parser.error('--model-index must be nonnegative')
    try:
        result = run(args.structure, args.sequence_file, args.output_dir, args.evidence_kind, args.model_index, args.chain_id)
    except OSError as exc:
        print(json.dumps({'status':'FAIL','output_directory_error':str(exc)},ensure_ascii=False))
        return 20
    print(json.dumps({k:result[k] for k in ['status','scope','scientific_acceptance','mapping_status','target_chain_id','mapped_positions','parse_or_mapping_error'] if k in result},ensure_ascii=False,indent=2))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
