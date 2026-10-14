"""Archived target bytes and tampered copies; no model reruns."""
import copy
import hashlib
import json

import pytest
import yaml

from scripts.audit_esmfold2_r03 import EVIDENCE, ROOT, REQUIRED, audit


@pytest.fixture
def inputs():
    files = {name: (EVIDENCE / name).read_bytes() for name in REQUIRED | {'manifest.json'}}
    job = json.loads((EVIDENCE / 'cluster-job.json').read_bytes())
    bundle = list(yaml.safe_load_all((ROOT / 'deploy/esmfold2-standard/validation.r03.rancher.yaml').read_text(encoding='utf-8')))
    return files, job, bundle


def rehash(files):
    result = json.loads(files['result.json'])
    result['structure']['sha256'] = hashlib.sha256(files['structure.cif']).hexdigest()
    files['result.json'] = json.dumps(result).encode()
    files['manifest.json'] = json.dumps({'files': [
        {'path': n, 'size_bytes': len(files[n]), 'sha256': hashlib.sha256(files[n]).hexdigest()}
        for n in sorted(REQUIRED)]}).encode()


def test_real_output_audit(inputs):
    result = audit(*inputs)
    assert result['structure']['residue_count'] == 76
    assert result['structure']['sequence_matches']
    assert result['scientific_gate'] == 'CLOSED' and result['usable_for_pipeline'] is False
    assert result['original_bytes'] == 67351


@pytest.mark.parametrize('damage', ['sequence', 'coordinates', 'backbone', 'confidence', 'residue', 'duplicate'])
def test_rehashed_structural_corruption_rejected(inputs, damage):
    files, job, bundle = inputs
    lines = files['structure.cif'].decode().splitlines()
    columns = [line.strip().removeprefix('_atom_site.') for line in lines if line.startswith('_atom_site.')]
    first = next(i for i, line in enumerate(lines) if line.startswith('ATOM'))
    values = lines[first].split()
    if damage == 'sequence':
        for key in ('label_comp_id', 'auth_comp_id'):
            values[columns.index(key)] = 'ALA'
    elif damage == 'coordinates':
        values[columns.index('Cartn_x')] = 'nan'
    elif damage == 'backbone':
        values[columns.index('label_atom_id')] = 'XX'
    elif damage == 'confidence':
        values[columns.index('B_iso_or_equiv')] = '101'
    elif damage == 'residue':
        values[columns.index('label_seq_id')] = '999'
    elif damage == 'duplicate':
        lines.insert(first + 1, lines[first])
    lines[first] = ' '.join(values)
    files['structure.cif'] = ('\n'.join(lines) + '\n').encode()
    rehash(files)
    with pytest.raises(ValueError):
        audit(files, job, bundle)


@pytest.mark.parametrize('name,key,value', [
    ('metrics', 'mean_plddt', 0.1), ('execution', 'elapsed_seconds', float('nan')),
    ('execution', 'asset_manifest_sha256', '0' * 64),
    ('result', 'sequence_sha256', '0' * 64), ('result', 'engine', 'other'),
])
def test_rehashed_metadata_corruption_rejected(inputs, name, key, value):
    files, job, bundle = inputs
    data = json.loads(files[name + '.json'])
    data[key] = value
    files[name + '.json'] = json.dumps(data).encode()
    rehash(files)
    with pytest.raises(ValueError):
        audit(files, job, bundle)


def test_incomplete_checkpoint_rejected(inputs):
    files, job, bundle = inputs
    data = json.loads(files['checkpoint-loading.json'])
    data['esmfold2']['missing_keys'] = ['missing.weight']
    files['checkpoint-loading.json'] = json.dumps(data).encode()
    rehash(files)
    with pytest.raises(ValueError, match='checkpoint'):
        audit(files, job, bundle)


def test_changed_job_or_unfinished_job_rejected(inputs):
    files, job, bundle = inputs
    changed = copy.deepcopy(job)
    changed['spec']['template']['spec']['containers'][0]['image'] = 'other'
    with pytest.raises(ValueError, match='configuration'):
        audit(files, changed, bundle)
    job['status']['succeeded'] = 0
    with pytest.raises(ValueError, match='complete'):
        audit(files, job, bundle)
