"""Consume an existing verified B1 facts bundle into a new FreeSASA probe directory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from probe_b1_input_facts import ROOT, FACT_NAMES, verify_bundle, write_json
from check_w1_contract import strict_json
from t01_structure_mapping.freesasa_consumer import ConsumerError, prepare
from t01_structure_mapping.probe import sha

PROFILE = ROOT / 'docs/project/phase1/PHASE1_REAL_W1_FREESASA_PROFILE.json'


def read(path):
    return strict_json(path.read_bytes())


def run(bundle, output_dir, *, route, model_index, context_chain_ids):
    bundle, output = Path(bundle), Path(output_dir)
    verify_bundle(bundle, reparse=True)
    request, result = read(bundle / 'request.json'), read(bundle / 'result.json')
    facts = {name: read(bundle / (name + '.json')) for name in FACT_NAMES}
    data = (bundle / 'input.structure').read_bytes()
    output.mkdir(parents=True, exist_ok=False)
    # A self-contained, byte-identical upstream bundle is kept at this boundary.
    upstream = output / 'b1_input'
    upstream.mkdir()
    for name in ['input.structure', 'request.json', 'result.json', 'artifacts.json', *(n + '.json' for n in FACT_NAMES)]:
        (upstream / name).write_bytes((bundle / name).read_bytes())
    selection = dict(route=route, model_index=model_index, context_chain_ids=context_chain_ids)
    write_json(output / 'consumer_selection.json', selection)
    binding = dict(b1_binding=result['binding'], b1_result_sha256=sha((bundle / 'result.json').read_bytes()),
        b1_structure_artifact=request['structure_artifact'], b1_fact_artifacts=result['fact_artifacts'],
        consumer_selection_sha256=sha((output / 'consumer_selection.json').read_bytes()),
        profile_sha256=sha(PROFILE.read_bytes()))
    record = dict(scope='B1_FREESASA_CONSUMER_PREPARATION', binding=binding, route=route,
        status=None, error_code=None, error=None, error_details=None, preparation_sha256=None,
        scientific_approval=None, usable_for_pipeline=False, production_status='NOT_DEPLOYED',
        tool_invoked=False, calculation_started=False)
    try:
        preparation = prepare(data, facts, **selection)
        preparation['binding'] = binding
        pdb = preparation.pop('pdb_text')
        if pdb is not None:
            (output / 'prepared.pdb').write_bytes(pdb.encode('ascii'))
        write_json(output / 'preparation.json', preparation)
        record.update(status='READY_FOR_TOOL_PROBE', preparation_sha256=sha((output / 'preparation.json').read_bytes()))
    except ConsumerError as error:
        record.update(status='REJECTED_BEFORE_TOOL', error_code=error.code, error=str(error), error_details=error.details)
    write_json(output / 'consumer_result.json', record)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--route', choices=['pdb_file', 'native_atoms'], required=True)
    parser.add_argument('--model-index', type=int, required=True)
    parser.add_argument('--context-chain', action='append', required=True)
    args = parser.parse_args()
    try:
        result = run(args.bundle, args.output_dir, route=args.route, model_index=args.model_index, context_chain_ids=args.context_chain)
        print(json.dumps({key: result[key] for key in ['status', 'error_code', 'tool_invoked', 'production_status']}, ensure_ascii=False))
        sys.exit(0 if result['status'] == 'READY_FOR_TOOL_PROBE' else 1)
    except (ValueError, OSError) as error:
        print(json.dumps(dict(status='PREPARATION_ERROR', error=str(error)), ensure_ascii=False))
        sys.exit(20)
