"""Prepare, assess, seal or read-only verify a separate B1 FreeSASA consumer campaign."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from b1_freesasa_cases import cases, assert_prepared, ROOT
from check_b1_engineering import fingerprint, safe_path, read
from probe_b1_input_facts import write_json, verify_bundle
from prepare_b1_freesasa import PROFILE
from t01_structure_mapping.freesasa_consumer import load_preparation, join_areas
from t01_structure_mapping.probe import sha

BATCH = ROOT / 'discovery/t01-phase1-real/w1/b1-freesasa-consumer-20260906-r02'
SOURCES = ['src/t01_structure_mapping/freesasa_consumer.py', 'scripts/prepare_b1_freesasa.py',
    'scripts/b1_freesasa_cases.py', 'scripts/check_b1_freesasa_consumer.py',
    'scripts/run_b1_freesasa_consumer.py', 'scripts/run_b1_freesasa_worker.py', 'tests/test_b1_freesasa_consumer.py']


def prepare_campaign(batch):
    if (batch / 'expected_cases.json').exists():
        raise FileExistsError('Use a new campaign; never replace declared evidence')
    (batch / 'inputs').mkdir(parents=True, exist_ok=False)
    template = read(ROOT / '工作流设计/02-数据契约/phase1-real-v0.1/b1-review/examples/ingest-request.json')
    planned = []
    for case in cases():
        name, data = case['id'], case.pop('data')
        path = batch / 'inputs' / (name + '.structure')
        path.write_bytes(data)
        request = json.loads(json.dumps(template))
        request.update(run_id='t01p1r-run-b1-sasa-' + name, request_id='b1-sasa-' + name,
            protein_sequence=case['sequence'], protein_sequence_sha256=sha(case['sequence'].encode()),
            declared_format=case['declared_format'], selection=case['b1_selection'],
            host_species='USER HOST; engineering consumer fixture',
            source_declaration=dict(kind='unknown', note='Preserve file metadata separately; no source qualification'))
        request['structure_artifact'].update(artifact_id='t01p1r-artifact-b1-sasa-' + name, run_id=request['run_id'],
            media_type='chemical/x-pdb' if case['declared_format'] == 'PDB' else 'chemical/x-cif',
            sha256=sha(data), size_bytes=len(data))
        request_path = batch / 'inputs' / (name + '.request.json')
        write_json(request_path, request)
        case.update(input=fingerprint(path, batch), request=fingerprint(request_path, batch),
                    source=fingerprint(ROOT / case['source']) if case['source'] else None)
        planned.append(case)
    write_json(batch / 'expected_cases.json', dict(declared_before_campaign_execution=True,
        prepared_at=datetime.now(timezone.utc).isoformat(), expectation_source=fingerprint(ROOT / 'scripts/b1_freesasa_cases.py'),
        basis='Literal raw identities, atom/exclusion counts, source format constraints; tool results never define these expectations',
        scientific_reference=False, cases=planned))


def execute_preparations(batch):
    if (batch / 'preparation_execution.json').exists() or (batch / 'prepared').exists():
        raise FileExistsError('Preparation execution already exists')
    plan = read(batch / 'expected_cases.json')
    (batch / 'prepared').mkdir()
    rows = []
    for case in plan['cases']:
        name, selection = case['id'], case['consumer_selection']
        calls = [
            [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/probe_b1_input_facts.py'), 'record',
             '--structure', str(safe_path(batch, case['input']['path'])), '--request', str(safe_path(batch, case['request']['path'])),
             '--output-dir', str(batch / 'b1_bundles' / name)],
            [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/prepare_b1_freesasa.py'),
             '--bundle', str(batch / 'b1_bundles' / name), '--output-dir', str(batch / 'prepared' / name),
             '--route', selection['route'], '--model-index', str(selection['model_index'])]
            + [arg for chain in selection['context_chain_ids'] for arg in ['--context-chain', chain]],
        ]
        # The public CLI requires at least one context value. Empty-context is a direct Python API boundary case.
        if not selection['context_chain_ids']:
            from prepare_b1_freesasa import run
        actual = []
        for index, command in enumerate(calls):
            started = datetime.now(timezone.utc).isoformat()
            if index == 1 and not selection['context_chain_ids']:
                record = run(batch / 'b1_bundles' / name, batch / 'prepared' / name, **selection)
                actual.append(dict(entry='prepare_b1_freesasa.run', selection=selection, started_at=started,
                                   status=record['status'], method='DIRECT_PYTHON_API'))
            else:
                result = subprocess.run(command, capture_output=True, timeout=60)
                actual.append(dict(command=command, started_at=started, exit_code=result.returncode,
                    stdout=result.stdout.decode('utf-8'), stderr=result.stderr.decode('utf-8'), method='CLI'))
        rows.append(dict(id=name, calls=actual))
        print(name, read(batch / 'prepared' / name / 'consumer_result.json')['status'], flush=True)
    write_json(batch / 'preparation_execution.json', dict(plan_sha256=sha((batch / 'expected_cases.json').read_bytes()), cases=rows))


def assess(batch, *, reparse=False):
    plan, execution = read(batch / 'expected_cases.json'), read(batch / 'preparation_execution.json')
    assert plan['declared_before_campaign_execution']
    assert execution['plan_sha256'] == sha((batch / 'expected_cases.json').read_bytes())
    campaign = read(batch / 'execution/campaign.json')
    assert campaign['plan_sha256'] == execution['plan_sha256']
    assert campaign['network_interfaces'] == ['lo'] and campaign['scientific_approval'] is None
    assert campaign['profile_sha256'] == sha(PROFILE.read_bytes())
    process = read(batch / 'execution/execution.json')
    assert process['exit_code'] == 0 and process['timed_out'] is False
    assert process['image_id'] == read(PROFILE)['runtime']['image_id']
    assert process['plan_sha256'] == execution['plan_sha256']
    assert all(fingerprint(safe_path(ROOT, row['path'])) == row for row in process['sources'])
    assert [c['id'] for c in execution['cases']] == [c['id'] for c in plan['cases']]
    tool_rows = {c['id']: c for c in campaign['cases']}
    assert len(tool_rows) == len(campaign['cases'])
    observations, successful, prepared_ids = [], {}, []
    for case, call_record in zip(plan['cases'], execution['cases']):
        name, expected = case['id'], case['expected']
        for field in ['input', 'request']:
            assert fingerprint(safe_path(batch, case[field]['path']), batch) == case[field]
        if case['source']:
            assert fingerprint(safe_path(ROOT, case['source']['path'])) == case['source']
        upstream, folder = batch / 'b1_bundles' / name, batch / 'prepared' / name
        verify_bundle(upstream, reparse=reparse)
        verify_bundle(folder / 'b1_input', reparse=reparse)
        for file in upstream.iterdir():
            assert file.read_bytes() == (folder / 'b1_input' / file.name).read_bytes()
        assert (upstream / 'input.structure').read_bytes() == safe_path(batch, case['input']['path']).read_bytes()
        assert (upstream / 'request.json').read_bytes() == safe_path(batch, case['request']['path']).read_bytes()
        assert read(folder / 'consumer_selection.json') == case['consumer_selection']
        assert read(upstream / 'preflight.json')['error_code'] == expected['b1_error']
        assert call_record['calls'][0]['exit_code'] == (1 if expected['b1_error'] else 0)
        preparation = read(folder / 'consumer_result.json')
        assert preparation['error_code'] == expected['preparation_error']
        assert preparation['usable_for_pipeline'] is False and preparation['scientific_approval'] is None
        if call_record['calls'][1]['method'] == 'CLI':
            assert call_record['calls'][1]['exit_code'] == (1 if expected['preparation_error'] else 0)
        if expected['preparation_error']:
            assert preparation['status'] == 'REJECTED_BEFORE_TOOL' and preparation['tool_invoked'] is False
            assert name not in tool_rows and not (folder / 'preparation.json').exists()
            observations.append(dict(id=name, status='EXPECTED_PREPARATION_REJECTION', error_code=expected['preparation_error']))
            continue
        prepared_ids.append(name)
        prepared, _ = load_preparation(folder, PROFILE.read_bytes())
        assert_prepared(case, prepared)
        target, actual = batch / 'execution/results' / name, tool_rows[name]
        assert read(target / 'result.json') == {key: value for key, value in actual.items() if key != 'id'}
        assert actual['binding'] == preparation['binding'] and actual['preparation_sha256'] == preparation['preparation_sha256']
        assert actual['normal_rsa_result'] is actual['buried_fraction'] is actual['scientific_approval'] is None
        assert actual['usable_for_pipeline'] is False and actual['tool_invoked'] is True
        assert actual['error_code'] == expected['tool_error']
        if expected['tool_error']:
            assert actual['status'] == 'REJECTED' and actual['calculation_started'] is False
            assert any(row['radius'] < 0 for row in read(target / 'classifier.json'))
            assert not (target / 'raw_areas.json').exists()
            observations.append(dict(id=name, status='EXPECTED_CLASSIFIER_REJECTION', error_code=actual['error_code']))
            continue
        assert actual['status'] == 'SUCCESS_RAW_ONLY' and actual['calculation_started'] is True
        observed, areas = read(target / 'tool_atoms.json'), read(target / 'raw_areas.json')
        assert areas['parameters'] == read(PROFILE)['calculation']['parameters']
        assert actual['atom_count'] == expected['atom_count'] and actual['residue_count'] == expected['residue_count']
        joined = join_areas(prepared, observed, areas['atom_areas'])
        saved = read(target / 'raw_residue_areas.json')
        assert saved == dict(joined, binding=actual['binding'], preparation_sha256=actual['preparation_sha256'],
                             raw_areas_sha256=sha((target / 'raw_areas.json').read_bytes()))
        classifier = {r['raw_row_index']: r['radius'] for r in read(target / 'classifier.json')}
        verified = read(target / 'verified_atoms.json')
        assert all(row['radius'] == classifier[row['raw_row_index']] > 0 for row in verified)
        # Deliberately shuffle both actual tool artifacts; a positional zip cannot pass.
        assert join_areas(prepared, observed[::-1], areas['atom_areas'][::-1]) == joined
        successful[name] = dict(areas=areas, joined=joined, verified=verified)
        observations.append(dict(id=name, status='SUCCESS_RAW_ONLY', atom_count=actual['atom_count'],
                                 residue_count=actual['residue_count'], unordered_join='PASS'))
    assert list(tool_rows) == prepared_ids
    parity = []
    for group in ['integer', 'icode', 'negative', 'context-ab']:
        a, b = successful['F-' + group + '-pdb'], successful['F-' + group + '-native']
        assert a['areas'] == b['areas'] and a['joined'] == b['joined']
        # PDB residue fields include fixed-width padding; native tokens do not.
        semantic = lambda rows: [{k: v for k, v in row.items() if k != 'raw_tool_residue_number'} for row in rows]
        assert semantic(a['verified']) == semantic(b['verified'])
        parity.append(dict(group=group, status='EXACT_EQUAL', compared='tool identities/radii, atom and raw residue areas'))
    a = successful['F-context-a']['joined']['residues'][0]['absolute_sasa_a2']
    ab = successful['F-context-ab-native']['joined']['residues'][0]['absolute_sasa_a2']
    assert 0 < ab < a  # Expected direction of occlusion, not a scientific acceptance threshold.
    counts = dict(Counter(row['status'] for row in observations))
    return dict(status='PASS_ENGINEERING_ONLY', plan_sha256=execution['plan_sha256'], cases=observations, counts=counts,
        route_parity=parity, context_check=dict(status='PASS', chain_a_only_sasa_a2=a, chain_a_in_ab_sasa_a2=ab),
        scientific_acceptance='NOT_RUN', mapping_approval='NOT_GRANTED', production_status='NOT_DEPLOYED',
        production_workers_enabled=False)


def seal(batch):
    if (batch / 'manifest.json').exists():
        raise FileExistsError('Campaign already sealed')
    assert read(batch / 'assessment.json') == assess(batch, reparse=True)
    protected = read(batch / 'protected_before.json')['files']
    assert all(fingerprint(safe_path(ROOT, row['path'])) == row for row in protected)
    for name in SOURCES:
        target = batch / 'after' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    outputs = [fingerprint(path, batch) for path in sorted(batch.rglob('*')) if path.is_file() and '__pycache__' not in path.parts]
    write_json(batch / 'manifest.json', dict(sources=[fingerprint(ROOT / p) for p in SOURCES], outputs=outputs,
        scientific_acceptance='NOT_RUN', production_status='NOT_DEPLOYED'))


def verify(batch, reparse=False):
    manifest = read(batch / 'manifest.json')
    for base, rows in [(ROOT, manifest['sources']), (batch, manifest['outputs'])]:
        for row in rows:
            assert fingerprint(safe_path(base, row['path']), base) == row, row['path']
    protected = read(batch / 'protected_before.json')['files']
    assert all(fingerprint(safe_path(ROOT, row['path'])) == row for row in protected)
    assessment = assess(batch, reparse=reparse)
    assert read(batch / 'assessment.json') == assessment
    return dict(status='PASS', cases=len(assessment['cases']), counts=assessment['counts'],
        artifacts=len(manifest['outputs']), protected_files=len(protected), reparsed=reparse,
        scientific_acceptance='NOT_RUN', production_status='NOT_DEPLOYED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'prepare-inputs', 'assess', 'seal', 'verify'])
    parser.add_argument('--batch', type=Path, default=BATCH)
    parser.add_argument('--reparse', action='store_true')
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare_campaign(args.batch)
    elif args.mode == 'prepare-inputs':
        execute_preparations(args.batch)
    elif args.mode == 'assess':
        if (args.batch / 'assessment.json').exists():
            raise FileExistsError('Assessment already recorded')
        result = assess(args.batch, reparse=True)
        write_json(args.batch / 'assessment.json', result)
        print(json.dumps(result['counts']))
    elif args.mode == 'seal':
        seal(args.batch)
    else:
        print(json.dumps(verify(args.batch, args.reparse)))
