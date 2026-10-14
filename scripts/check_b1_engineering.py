"""Prepare/execute a new local B1 facts campaign, or verify its evidence read-only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from b1_engineering_cases import cases, assert_expected, ROOT
from probe_b1_input_facts import run, verify_bundle, write_json, FACT_NAMES, CONTRACT
from t01_structure_mapping.probe import sha

BATCH = ROOT / 'discovery/t01-phase1-real/w1/b1-engineering-20260905'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fingerprint(path, base=ROOT):
    data = path.read_bytes()
    return dict(path=path.relative_to(base).as_posix(), sha256=sha(data), size_bytes=len(data))


def safe_path(base, name):
    if not isinstance(name, str) or ':' in name or '\\' in name or any(part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('Unsafe evidence path')
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError('Evidence escaped root')
    return path


def prepare(batch):
    if (batch / 'expected_cases.json').exists() or (batch / 'results').exists():
        raise FileExistsError('Campaign already prepared/executed; choose a new directory')
    (batch / 'inputs').mkdir(parents=True, exist_ok=False)
    template = read(CONTRACT.parent / 'b1-review/examples/ingest-request.json')
    planned = []
    for case in cases():
        name = case['id']
        path = batch / 'inputs' / (name + '.structure')
        path.write_bytes(case['data'])
        request = json.loads(json.dumps(template))
        request.update(run_id='t01p1r-run-b1-eng-' + name, request_id='b1-eng-' + name,
            protein_sequence=case['sequence'], protein_sequence_sha256=sha(case['sequence'].encode()),
            declared_format=case['declared_format'], selection=dict(model_index=case['model_index'], chain_selector=case['chain_selector']),
            host_species='USER_DECLARED_HOST; engineering evidence only')
        request['structure_artifact'].update(artifact_id='t01p1r-artifact-b1-input-' + name, run_id=request['run_id'],
            media_type='chemical/x-pdb' if case['declared_format'] == 'PDB' else 'chemical/x-cif',
            sha256=sha(case['data']), size_bytes=len(case['data']))
        if 'metadata-conflicts' in name:
            request['source_declaration'] = dict(kind='predicted', note='Unassessed user statement; file methods retained alongside it')
        request_path = batch / 'inputs' / (name + '.request.json')
        write_json(request_path, request)
        source = fingerprint(ROOT / case['source']) if case['source'] else None
        planned.append(dict(id=name, input=fingerprint(path, batch), request=fingerprint(request_path, batch), source=source,
            evidence_scope='REUSED_LOCAL_FILE' if name.startswith('E-real-') else 'SYNTHETIC_ENGINEERING_BOUNDARY',
            expected=case['expected']))
    write_json(batch / 'expected_cases.json', dict(declared_before_campaign_execution=True,
        prepared_at=datetime.now(timezone.utc).isoformat(), expectation_source=fingerprint(ROOT / 'scripts/b1_engineering_cases.py'),
        independent_basis='Literal file edits, known prior atom counts and format rules; no scientific accuracy claim', cases=planned))


def execute(batch):
    if (batch / 'results').exists() or (batch / 'assessment.json').exists():
        raise FileExistsError('Existing execution evidence must not be overwritten')
    planned = read(batch / 'expected_cases.json')
    (batch / 'results').mkdir()
    actual = []
    for case in planned['cases']:
        output = batch / 'results' / case['id']
        command = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/probe_b1_input_facts.py'), 'record',
            '--structure', str(safe_path(batch, case['input']['path'])),
            '--request', str(safe_path(batch, case['request']['path'])), '--output-dir', str(output)]
        started = datetime.now(timezone.utc).isoformat()
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=60)
        observed = dict(id=case['id'], command=command, started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
                        exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
        try:
            if completed.returncode != (1 if case['expected']['error'] else 0):
                raise ValueError('Unexpected CLI exit')
            facts = {name: read(output / (name + '.json')) for name in FACT_NAMES}
            assert_expected(case['expected'], facts)
            observed.update(status='PASS', verification=verify_bundle(output, reparse=True))
        except (ValueError, AssertionError, OSError) as exc:
            observed.update(status='FAIL', error=str(exc))
        actual.append(observed)
        print(case['id'], observed['status'], flush=True)
    write_json(batch / 'assessment.json', dict(status='PASS' if all(row['status'] == 'PASS' for row in actual) else 'FAIL',
        planned_sha256=sha((batch / 'expected_cases.json').read_bytes()), cases=actual,
        scientific_acceptance='NOT_RUN', mapping_approval='NOT_GRANTED', production_status='NOT_DEPLOYED'))


def seal(batch):
    if (batch / 'manifest.json').exists():
        raise FileExistsError('Evidence already sealed')
    if read(batch / 'assessment.json')['status'] != 'PASS':
        raise ValueError('Campaign has failures; keep evidence and create a new execution batch')
    sources = [ROOT / p for p in ['src/t01_structure_mapping/input_facts.py', 'src/t01_structure_mapping/cif_facts.py',
        'src/t01_structure_mapping/probe.py', 'src/t01_structure_mapping/__init__.py', 'scripts/probe_b1_input_facts.py',
        'scripts/check_b1_engineering.py', 'scripts/b1_engineering_cases.py', 'tests/test_b1_input_facts.py',
        '工作流设计/02-数据契约/phase1-real-v0.1/b1-engineering/result.schema.json']]
    # The unchanged reused probe and the new code are recorded under after/.
    for path in sources:
        target = batch / 'after' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    outputs = [fingerprint(path, batch) for path in sorted(batch.rglob('*'))
               if path.is_file() and '__pycache__' not in path.parts]
    write_json(batch / 'manifest.json', dict(sources=[fingerprint(p) for p in sources], outputs=outputs,
        scientific_acceptance='NOT_RUN', production_status='NOT_DEPLOYED'))


def verify(batch, reparse=False):
    manifest = read(batch / 'manifest.json')
    for base, rows in [(ROOT, manifest['sources']), (batch, manifest['outputs'])]:
        for row in rows:
            if fingerprint(safe_path(base, row['path']), base) != row:
                raise ValueError('Evidence/source hash mismatch: ' + row['path'])
    protected = read(batch / 'protected_before.json') if (batch / 'protected_before.json').exists() else None
    if protected:
        for row in protected['files']:
            if fingerprint(safe_path(ROOT, row['path'])) != row:
                raise ValueError('Protected original or prior evidence changed: ' + row['path'])
    planned, actual = read(batch / 'expected_cases.json'), read(batch / 'assessment.json')
    if not planned['declared_before_campaign_execution'] or actual['planned_sha256'] != sha((batch / 'expected_cases.json').read_bytes()):
        raise ValueError('Case plan changed')
    if actual['status'] != 'PASS' or actual['mapping_approval'] != 'NOT_GRANTED' or actual['scientific_acceptance'] != 'NOT_RUN':
        raise ValueError('Campaign failed or claims science')
    if [c['id'] for c in planned['cases']] != [c['id'] for c in actual['cases']]:
        raise ValueError('Case closure mismatch')
    for case, observation in zip(planned['cases'], actual['cases']):
        for field in ('input', 'request'):
            row = case[field]
            if fingerprint(safe_path(batch, row['path']), batch) != row:
                raise ValueError('Case input changed')
        if case['source'] and fingerprint(safe_path(ROOT, case['source']['path'])) != case['source']:
            raise ValueError('Case source changed')
        output = batch / 'results' / case['id']
        if observation['status'] != 'PASS' or observation['exit_code'] != (1 if case['expected']['error'] else 0):
            raise ValueError('Missing successful CLI evidence')
        verify_bundle(output, reparse=reparse)
        assert_expected(case['expected'], {name: read(output / (name + '.json')) for name in FACT_NAMES})
        if (output / 'input.structure').read_bytes() != safe_path(batch, case['input']['path']).read_bytes():
            raise ValueError('Original input copy drift')
        if (output / 'request.json').read_bytes() != safe_path(batch, case['request']['path']).read_bytes():
            raise ValueError('Original request copy drift')
    return dict(status='PASS', cases=len(planned['cases']), artifacts=len(manifest['outputs']),
        protected_files=len(protected['files']) if protected else 0, reparsed=reparse,
        scientific_acceptance='NOT_RUN', production_status='NOT_DEPLOYED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'execute', 'seal', 'verify'], default='verify', nargs='?')
    parser.add_argument('--batch', type=Path, default=BATCH)
    parser.add_argument('--reparse', action='store_true')
    args = parser.parse_args()
    if args.mode == 'verify':
        print(json.dumps(verify(args.batch, args.reparse), ensure_ascii=False))
    else:
        globals()[args.mode](args.batch)
