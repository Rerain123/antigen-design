"""Record B1 input facts in a NEW local directory; no runtime Worker is registered."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from check_w1_b1_review import validate_request
from check_w1_contract import strict_json
from t01_structure_mapping.input_facts import inspect_input
from t01_structure_mapping.probe import sha

CONTRACT = ROOT / '工作流设计/02-数据契约/phase1-real-v0.1/b1-engineering'
FACT_NAMES = ('preflight', 'raw_metadata', 'raw_addresses')


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def run(structure, request_path, output_dir):
    request_bytes = Path(request_path).read_bytes()
    request = validate_request(strict_json(request_bytes))
    if request['tool_id'] != 't01.real.ingest_structure':
        raise ValueError('The facts probe only accepts an ingest draft request, not a mapping request')
    data = Path(structure).read_bytes()
    ref = request['structure_artifact']
    if ref['sha256'] != sha(data) or ref['size_bytes'] != len(data):
        raise ValueError('Original structure bytes do not match the request ArtifactRef')
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    # Store exact input bytes before inspection, including rejected structures.
    (output / 'input.structure').write_bytes(data)
    (output / 'request.json').write_bytes(request_bytes)
    facts = inspect_input(data, declared_format=request['declared_format'], **request['selection'])
    identity = uuid.uuid4().hex
    binding = dict(run_id=request['run_id'], request_id=request['request_id'],
        job_id='t01p1r-job-b1-facts-' + identity, attempt_id='t01p1r-attempt-b1-facts-' + identity,
        request_sha256=sha(request_bytes), sequence_sha256=request['protein_sequence_sha256'], structure_sha256=sha(data))
    refs, files = {}, [dict(path='input.structure', ref=ref)]
    for name in FACT_NAMES:
        facts[name]['binding'] = binding
        write_json(output / (name + '.json'), facts[name])
        content = (output / (name + '.json')).read_bytes()
        refs[name] = dict(artifact_id='t01p1r-artifact-b1-' + name.replace('_', '-') + '-' + identity,
            run_id=request['run_id'], job_id=binding['job_id'], attempt_id=binding['attempt_id'],
            role='result', media_type='application/json', sha256=sha(content), size_bytes=len(content),
            evidence_kind='ENGINEERING_FIXTURE')
        files.append(dict(path=name + '.json', ref=refs[name]))
    pf = facts['preflight']
    result = dict(extension_version='0.1.0', contract_status='DRAFT_ENGINEERING_EXTENSION',
        identity_scope='LOCAL_PROBE_NOT_RUNTIME_ISSUED', tool_id='t01.dev.structure_input_facts',
        binding=binding, outcome='recorded' if pf['status'] == 'ready_for_review' else 'rejected',
        error_code=pf['error_code'], fact_artifacts=refs,
        host_species=request['host_species'], source_declaration=request['source_declaration'],
        unresolved_metadata=dict(source=None, plddt=None, missing_atom_fraction=None),
        mapping_status=None, scientific_disposition='not_evaluated', review_required=True,
        usable_for_pipeline=False, production_status='NOT_DEPLOYED')
    write_json(output / 'result.json', result)
    write_json(output / 'artifacts.json', dict(identity_scope=result['identity_scope'], artifacts=files,
        request=dict(path='request.json', sha256=sha(request_bytes), size_bytes=len(request_bytes)),
        result=dict(path='result.json', sha256=sha((output / 'result.json').read_bytes())),
        recorded_at=datetime.now(timezone.utc).isoformat()))
    return result


def verify_bundle(output_dir, *, reparse=False):
    """Validate pair, all exact input/output bytes, origin spans and optionally re-read."""
    from jsonschema import Draft202012Validator
    output = Path(output_dir)
    request_bytes = (output / 'request.json').read_bytes()
    request = validate_request(strict_json(request_bytes))
    result = strict_json((output / 'result.json').read_bytes())
    Draft202012Validator(strict_json((CONTRACT / 'result.schema.json').read_bytes())).validate(result)
    registry = strict_json((output / 'artifacts.json').read_bytes())

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(request['tool_id'] == 't01.real.ingest_structure', 'Facts are not a mapping result')
    binding = result['binding']
    require(binding['request_sha256'] == sha(request_bytes), 'Original request bytes changed')
    require(binding['run_id'] == request['run_id'] and binding['request_id'] == request['request_id'], 'Cross-request binding')
    require(binding['sequence_sha256'] == request['protein_sequence_sha256'] and
            binding['structure_sha256'] == request['structure_artifact']['sha256'], 'Input binding mismatch')
    require(result['host_species'] == request['host_species'] and result['source_declaration'] == request['source_declaration'],
            'File metadata overwrote the user declaration')
    require(registry['identity_scope'] == result['identity_scope'], 'Invented runtime identity')
    require(registry['request'] == dict(path='request.json', sha256=sha(request_bytes), size_bytes=len(request_bytes)), 'Request registry drift')
    require(registry['result'] == dict(path='result.json', sha256=sha((output / 'result.json').read_bytes())), 'Result registry drift')
    expected_refs = {'input.structure': request['structure_artifact'],
                     **{name + '.json': result['fact_artifacts'][name] for name in FACT_NAMES}}
    require(len(registry['artifacts']) == len(expected_refs), 'Artifact closure mismatch')
    seen, facts = set(), {}
    for item in registry['artifacts']:
        path, ref = item['path'], item['ref']
        require(path in expected_refs and path not in seen and expected_refs[path] == ref, 'Foreign/duplicate artifact path or ref')
        seen.add(path)
        content = (output / path).read_bytes()
        require(sha(content) == ref['sha256'] and len(content) == ref['size_bytes'], 'Artifact bytes/hash mismatch')
        require(ref['run_id'] == binding['run_id'], 'Cross-run artifact')
        if path != 'input.structure':
            require(ref['job_id'] == binding['job_id'] and ref['attempt_id'] == binding['attempt_id'], 'Cross-execution artifact')
            facts[path[:-5]] = strict_json(content)
            fact = facts[path[:-5]]
            require(fact['binding'] == binding and fact['structure_sha256'] == binding['structure_sha256'], 'Fact binding mismatch')
            require(fact['scientific_disposition'] == 'not_evaluated' and fact['usable_for_pipeline'] is False, 'Fact claims science')
    identities = [ref['artifact_id'] for ref in expected_refs.values()]
    require(len(set(identities)) == len(identities), 'Duplicate artifact identity')
    pf = facts['preflight']
    require(pf['declared_format'] == request['declared_format'] and pf['requested_selection'] == request['selection'], 'Selection drift')
    require(result['outcome'] == ('recorded' if pf['status'] == 'ready_for_review' else 'rejected')
            and result['error_code'] == pf['error_code'], 'Preflight outcome mismatch')
    require(result['outcome'] != 'rejected' or pf['ingestion_observation'] is None, 'Rejected preflight has a normal selection')
    require(facts['raw_metadata']['assessment'] == dict(source=None, plddt=None, missing_atom_fraction=None,
            scientific_disposition='not_evaluated'), 'Metadata claims science')
    data = (output / 'input.structure').read_bytes()
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        text = ''
    from t01_structure_mapping.cif_facts import Source
    source = Source(text)

    def origins(value):
        if isinstance(value, dict):
            if value.get('location') is not None and 'raw_value' in value:
                loc = value['location']
                require(0 <= loc['start'] <= loc['end'] <= len(text), 'Invalid origin range')
                actual = source.field(loc['start'], loc['end'])
                require(actual['raw_value'] == value['raw_value'] and actual['location'] == loc, 'Raw value/origin mismatch')
            for child in value.values():
                origins(child)
        elif isinstance(value, list):
            for child in value:
                origins(child)
    for fact in facts.values():
        origins(fact)
    if reparse:
        fresh = inspect_input(data, declared_format=request['declared_format'], **request['selection'])
        for name in FACT_NAMES:
            fresh[name]['binding'] = binding
            # JSON normalization makes tuple identity pairs portable lists.
            require(json.loads(json.dumps(fresh[name])) == facts[name], 'Fresh facts differ: ' + name)
    return dict(status='PASS', outcome=result['outcome'], reparsed=reparse,
                atom_count=facts['raw_addresses']['atom_count'], usable_for_pipeline=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    record = commands.add_parser('record')
    record.add_argument('--structure', type=Path, required=True)
    record.add_argument('--request', type=Path, required=True)
    record.add_argument('--output-dir', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('--output-dir', type=Path, required=True)
    check.add_argument('--reparse', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'verify':
            result = verify_bundle(args.output_dir, reparse=args.reparse)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        result = run(args.structure, args.request, args.output_dir)
        verify_bundle(args.output_dir, reparse=True)
        print(json.dumps({key: result[key] for key in ('outcome', 'error_code', 'production_status')}, ensure_ascii=False))
        return 0 if result['outcome'] == 'recorded' else 1
    except (ValueError, OSError) as exc:
        print(json.dumps(dict(status='FAIL', error=str(exc)), ensure_ascii=False))
        return 20


if __name__ == '__main__':
    sys.exit(main())
