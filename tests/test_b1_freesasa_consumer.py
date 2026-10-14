"""Consumer-boundary failures, source identity preservation, and unordered result joins."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from b1_freesasa_cases import cases, alanines, cif, assert_prepared
from probe_b1_input_facts import run as record_facts, write_json
from prepare_b1_freesasa import run as prepare_bundle, PROFILE
from t01_structure_mapping.freesasa_consumer import ConsumerError, prepare, load_preparation, validate_tool_atoms, join_areas
from t01_structure_mapping.input_facts import inspect_input
from t01_structure_mapping.probe import sha


@pytest.mark.parametrize('case', cases(), ids=lambda c: c['id'])
def test_literal_consumer_boundaries(case):
    facts = inspect_input(case['data'], declared_format=case['declared_format'], **case['b1_selection'])
    assert facts['preflight']['error_code'] == case['expected']['b1_error']
    if case['expected']['preparation_error']:
        with pytest.raises(ConsumerError) as error:
            prepare(case['data'], facts, **case['consumer_selection'])
        assert error.value.code == case['expected']['preparation_error']
    else:
        prepared = prepare(case['data'], facts, **case['consumer_selection'])
        assert_prepared(case, prepared)


def prepared_atoms():
    data = cif([dict(auth_seq_id='043'), dict(auth_seq_id='43', Cartn_x='8')])
    facts = inspect_input(data, declared_format='MMCIF', model_index=0, chain_selector='A')
    p = prepare(data, facts, route='native_atoms', model_index=0, context_chain_ids=['A'])
    observed = [dict(tool_atom_index=i, chain_id='A', tool_residue_token=token,
                     atom_name='CA', residue_name='ALA', coordinate=coord, radius=1.88)
                for i, token, coord in [(0, '43', [8., 1., 2.]), (1, '043', [0., 1., 2.])]]
    return p, observed


def test_area_join_uses_verified_indices_and_full_raw_identity():
    p, observed = prepared_atoms()
    result = join_areas(p, observed[::-1], [dict(tool_atom_index=1, absolute_sasa_a2=11), dict(tool_atom_index=0, absolute_sasa_a2=29)])
    assert [r['absolute_sasa_a2'] for r in result['residues']] == [11, 29]
    assert [r['raw_address']['auth_seq_id'][0] for r in result['residues']] == ['043', '43']
    assert [r['source_atom_rows'] for r in result['residues']] == [[1], [2]]
    assert result['normal_rsa_result'] is None and result['usable_for_pipeline'] is False


@pytest.mark.parametrize('field,value,code', [
    ('chain_id', 'B', 'TOOL_IDENTITY_MISMATCH'), ('tool_residue_token', '0043', 'TOOL_IDENTITY_MISMATCH'),
    ('residue_name', 'GLY', 'TOOL_IDENTITY_MISMATCH'), ('atom_name', 'N', 'TOOL_IDENTITY_MISMATCH'),
    ('coordinate', [8.001, 1., 2.], 'TOOL_COORDINATE_MISMATCH'),
    ('radius', 0, 'UNKNOWN_PROTOR_RADIUS'), ('radius', float('nan'), 'UNKNOWN_PROTOR_RADIUS'),
    ('radius', True, 'UNKNOWN_PROTOR_RADIUS'), ('tool_atom_index', True, 'TOOL_INDEX_MISMATCH'),
    ('tool_atom_index', 0.0, 'TOOL_INDEX_MISMATCH'), ('tool_atom_index', 1, 'TOOL_INDEX_MISMATCH'),
])
def test_changed_tool_input_is_rejected_before_area_join(field, value, code):
    p, observed = prepared_atoms()
    observed[0][field] = value
    with pytest.raises(ConsumerError) as error:
        validate_tool_atoms(p, observed)
    assert error.value.code == code


@pytest.mark.parametrize('mode,code', [('lost', 'TOOL_ATOM_COUNT_MISMATCH'), ('duplicate', 'TOOL_IDENTITY_MISMATCH')])
def test_lost_and_duplicated_tool_atoms(mode, code):
    p, observed = prepared_atoms()
    observed = observed[:1] if mode == 'lost' else observed + observed[:1]
    with pytest.raises(ConsumerError) as error:
        validate_tool_atoms(p, observed)
    assert error.value.code == code


@pytest.mark.parametrize('areas,code', [
    ([(0, -1), (1, 2)], 'INVALID_NUMERIC_OUTPUT'), ([(0, float('inf')), (1, 2)], 'INVALID_NUMERIC_OUTPUT'),
    ([(0, True), (1, 2)], 'INVALID_NUMERIC_OUTPUT'), ([(0, 1)], 'AREA_COUNT_MISMATCH'),
    ([(0, 1), (0, 2)], 'AREA_INDEX_MISMATCH'), ([(0, 1), (2, 2)], 'AREA_INDEX_MISMATCH'),
    ([(False, 1), (1, 2)], 'AREA_INDEX_MISMATCH'),
])
def test_invalid_or_incomplete_area_outputs(areas, code):
    p, observed = prepared_atoms()
    with pytest.raises(ConsumerError) as error:
        join_areas(p, observed, [dict(tool_atom_index=i, absolute_sasa_a2=a) for i, a in areas])
    assert error.value.code == code


def test_raw_metadata_and_origins_cannot_be_forged():
    data = cif()
    facts = inspect_input(data, declared_format='MMCIF', model_index=0, chain_selector='A')
    facts['raw_metadata']['assessment']['source'] = 'experimental'
    with pytest.raises(ConsumerError, match='original structure'):
        prepare(data, facts, route='native_atoms', model_index=0, context_chain_ids=['A'])


def test_coordinate_precision_is_explicit_and_author_identity_is_unchanged():
    data = cif([dict(Cartn_x='0.123456789', auth_seq_id='43', pdbx_PDB_ins_code='A')])
    facts = inspect_input(data, declared_format='MMCIF', model_index=0, chain_selector='A')
    a = prepare(data, facts, route='native_atoms', model_index=0, context_chain_ids=['A'])
    p = prepare(data, facts, route='pdb_file', model_index=0, context_chain_ids=['A'])
    assert a['atoms'][0]['coordinate_tool'][0] == .123456789
    assert p['atoms'][0]['coordinate_source'][0] == .123456789
    assert p['atoms'][0]['coordinate_tool'][0] == .123
    assert a['atoms'][0]['raw_address'] == p['atoms'][0]['raw_address']
    assert p['pdb_text'][22:27] == '  43A'


@pytest.fixture
def bundle(tmp_path):
    data = cif(alanines())
    request = json.loads((ROOT / '工作流设计/02-数据契约/phase1-real-v0.1/b1-review/examples/ingest-request.json').read_text(encoding='utf-8'))
    request.update(declared_format='MMCIF', protein_sequence='AA', protein_sequence_sha256=sha(b'AA'),
                   selection=dict(model_index=0, chain_selector='A'), host_species='USER HOST')
    request['structure_artifact'].update(sha256=sha(data), size_bytes=len(data), media_type='chemical/x-cif')
    (tmp_path / 'input.cif').write_bytes(data)
    write_json(tmp_path / 'request.json', request)
    record_facts(tmp_path / 'input.cif', tmp_path / 'request.json', tmp_path / 'b1')
    target = tmp_path / 'consumer'
    prepare_bundle(tmp_path / 'b1', target, route='pdb_file', model_index=0, context_chain_ids=['A'])
    return target


def test_complete_upstream_pair_survives_consumer_boundary(bundle):
    prepared, result = load_preparation(bundle, PROFILE.read_bytes())
    assert len(prepared['atoms']) == 10 and prepared['source_model_serial'] == '7'
    assert result['tool_invoked'] is False and result['usable_for_pipeline'] is False
    original = bundle.parent / 'b1'
    for name in ['input.structure', 'request.json', 'result.json', 'artifacts.json', 'preflight.json', 'raw_metadata.json', 'raw_addresses.json']:
        assert (bundle / 'b1_input' / name).read_bytes() == (original / name).read_bytes()
    assert json.loads((bundle / 'b1_input/result.json').read_text())['host_species'] == 'USER HOST'


@pytest.mark.parametrize('file', ['preparation.json', 'consumer_selection.json', 'prepared.pdb', 'b1_input/input.structure',
    'b1_input/request.json', 'b1_input/result.json', 'b1_input/preflight.json', 'b1_input/raw_metadata.json', 'b1_input/raw_addresses.json'])
def test_changed_bytes_rejected_in_tool_process(bundle, file):
    path = bundle / file
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ConsumerError):
        load_preparation(bundle, PROFILE.read_bytes())


def test_profile_change_is_not_implicitly_adopted(bundle):
    with pytest.raises(ConsumerError, match='profile'):
        load_preparation(bundle, PROFILE.read_bytes() + b' ')


def test_rehashing_prepared_identity_cannot_override_original(bundle):
    prepared = json.loads((bundle / 'preparation.json').read_text())
    prepared['atoms'][0]['author_seq_id'] = 'fake'
    write_json(bundle / 'preparation.json', prepared)
    record = json.loads((bundle / 'consumer_result.json').read_text())
    record['preparation_sha256'] = sha((bundle / 'preparation.json').read_bytes())
    write_json(bundle / 'consumer_result.json', record)
    with pytest.raises(ConsumerError) as error:
        load_preparation(bundle, PROFILE.read_bytes())
    assert error.value.code == 'PREPARATION_CONTENT_MISMATCH'


def test_forged_attempt_in_both_preparation_records_rejected(bundle):
    p = json.loads((bundle / 'preparation.json').read_text())
    r = json.loads((bundle / 'consumer_result.json').read_text())
    p['binding']['b1_binding']['attempt_id'] = r['binding']['b1_binding']['attempt_id'] = 'another-attempt'
    write_json(bundle / 'preparation.json', p)
    r['preparation_sha256'] = sha((bundle / 'preparation.json').read_bytes())
    write_json(bundle / 'consumer_result.json', r)
    with pytest.raises(ConsumerError) as error:
        load_preparation(bundle, PROFILE.read_bytes())
    assert error.value.code == 'CONSUMER_BINDING_MISMATCH'


def test_existing_evidence_is_never_overwritten(bundle):
    before = (bundle / 'consumer_result.json').read_bytes()
    with pytest.raises(FileExistsError):
        prepare_bundle(bundle.parent / 'b1', bundle, route='native_atoms', model_index=0, context_chain_ids=['A'])
    assert (bundle / 'consumer_result.json').read_bytes() == before


def test_case_plan_preserves_original_bytes_and_refuses_overwrite(tmp_path):
    from check_b1_freesasa_consumer import prepare_campaign
    prepare_campaign(tmp_path)
    plan = json.loads((tmp_path / 'expected_cases.json').read_text())
    assert plan['declared_before_campaign_execution'] is True and len(plan['cases']) == 45
    for case in plan['cases']:
        assert sha((tmp_path / case['input']['path']).read_bytes()) == case['input']['sha256']
    with pytest.raises(FileExistsError):
        prepare_campaign(tmp_path)


def test_sealed_consumer_evidence_read_only():
    from check_b1_freesasa_consumer import BATCH, verify
    if not (BATCH / 'manifest.json').exists():
        pytest.skip('New evidence batch has not been sealed yet')
    result = verify(BATCH)
    assert result['cases'] == 45 and result['scientific_acceptance'] == 'NOT_RUN'


def test_checker_rejects_altered_sealed_artifact(tmp_path):
    from check_b1_freesasa_consumer import verify
    (tmp_path / 'artifact.txt').write_bytes(b'tampered')
    write_json(tmp_path / 'manifest.json', dict(sources=[], outputs=[dict(path='artifact.txt', size_bytes=8, sha256=sha(b'original'))]))
    with pytest.raises(AssertionError, match='artifact.txt'):
        verify(tmp_path)
