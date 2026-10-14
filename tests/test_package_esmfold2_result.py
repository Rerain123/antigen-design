"""Real archived output packaging and tamper guards; no inference or cluster calls."""
import hashlib
import json

import pytest

from scripts.package_esmfold2_result import EVIDENCE, REQUIRED, package, verify


@pytest.fixture
def packaged(tmp_path):
    target = tmp_path / 'standard'
    before = {n: (EVIDENCE / n).read_bytes() for n in REQUIRED | {'manifest.json'}}
    package(EVIDENCE, target)
    assert before == {n: (EVIDENCE / n).read_bytes() for n in before}
    assert before == {n: (target / 'raw' / n).read_bytes() for n in before}
    return target


def test_real_result_contract_and_scale(packaged):
    result = json.loads((packaged / 'result.json').read_bytes())
    model = result['models'][0]
    confidence = json.loads((packaged / model['confidence_path']).read_bytes())
    job = json.loads((EVIDENCE / 'cluster-job.json').read_bytes())
    assert result['attempt_id'] == job['metadata']['uid']
    assert result['status'] == 'succeeded' and result['errors'] == []
    assert result['scientific_gate'] == 'CLOSED'
    assert result['usable_for_pipeline'] is result['automatic_handoff'] is False
    assert model['iptm'] is None and model['raw_scores']['iptm'] == 0
    assert model['ptm'] == pytest.approx(0.7356354594230652)
    assert confidence['raw_scale'] == '0_100'
    assert len(confidence['residues']) == 76
    assert ''.join(r['amino_acid'] for r in confidence['residues']) == result['sequence']
    assert confidence['mean_plddt'] == pytest.approx(0.7986140847206116, abs=1e-6)
    for i, row in enumerate(confidence['residues'], 1):
        assert row['sequence_position'] == row['label_seq_id'] == row['auth_seq_id'] == i
        assert row['plddt'] == row['plddt_raw'] / 100
        assert row['chain_id'] == 'A' and row['missing_reason'] is None
    assert hashlib.sha256((packaged / model['structure_path']).read_bytes()).hexdigest() == model['structure_sha256']
    assert verify(packaged)['residues'] == 76


def test_parameters_and_provenance(packaged):
    parameters = json.loads((packaged / 'parameters.json').read_bytes())
    assert parameters['inference']['num_loops'] == 3
    assert parameters['inference']['num_sampling_steps'] == 50
    provenance = json.loads((packaged / 'provenance.json').read_bytes())
    assert len(provenance['native_files']) == 8
    for name, digest in provenance['native_files'].items():
        assert hashlib.sha256((packaged / 'raw' / name).read_bytes()).hexdigest() == digest


def test_duplicate_output_refused(packaged):
    before = (packaged / 'manifest.json').read_bytes()
    with pytest.raises(ValueError, match='already exists'):
        package(EVIDENCE, packaged)
    assert (packaged / 'manifest.json').read_bytes() == before


def test_output_inside_source_refused():
    with pytest.raises(ValueError, match='outside'):
        package(EVIDENCE, EVIDENCE / 'must-not-be-created')


@pytest.mark.parametrize('name', ['result.json', 'parameters.json', 'provenance.json',
    'raw/structure.cif', 'raw/checkpoint-loading.json', 'sources/auditor.py',
    'raw/cluster-job.json', 'logs/cluster.log', 'sources/run_structure.py',
    'confidence/esmfold2-seed-1-sample-0.json', 'manifest.json'])
def test_changed_output_even_rehashed_manifest_refused(packaged, name):
    target = packaged / name
    target.write_bytes(target.read_bytes() + b' ')
    if name != 'manifest.json':
        manifest = json.loads((packaged / 'manifest.json').read_bytes())
        row = next(r for r in manifest['files'] if r['path'] == name)
        row.update(size_bytes=target.stat().st_size, sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        (packaged / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        verify(packaged)


def test_extra_or_incomplete_output_refused(packaged):
    (packaged / 'extra.txt').write_bytes(b'extra')
    with pytest.raises(ValueError):
        verify(packaged)
    (packaged / 'extra.txt').unlink()
    (packaged / 'manifest.json').unlink()
    with pytest.raises(ValueError):
        verify(packaged)


def test_damaged_source_rejected_before_output(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    for name in REQUIRED | {'manifest.json', 'cluster-job.json', 'cluster.log'}:
        (source / name).write_bytes((EVIDENCE / name).read_bytes())
    (source / 'structure.cif').write_bytes(b'corrupted')
    with pytest.raises(ValueError):
        package(source, tmp_path / 'invalid-output')
    assert not (tmp_path / 'invalid-output').exists()
