"""Independent file edits/expected identities and artifact tampering regressions."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]

from b1_engineering_cases import cases, cif, assert_expected
from probe_b1_input_facts import run, verify_bundle, write_json
from t01_structure_mapping.cif_facts import FactError, Source, read_cif
from t01_structure_mapping.input_facts import inspect_input
from t01_structure_mapping.probe import sha


@pytest.mark.parametrize('case', cases(), ids=lambda case: case['id'])
def test_predeclared_file_facts(case):
    facts = inspect_input(case['data'], declared_format=case['declared_format'],
                          model_index=case['model_index'], chain_selector=case['chain_selector'])
    assert_expected(case['expected'], facts)


def test_cif_lexical_values_and_positions():
    text = "\ufeffdata_x\r\n_a '?'\r\n_b ?\r\n_c '.'\r\n_d .\r\n_e 'author\'s label' # comment\r\n_f\r\n;two\r\nlines\r\n;\r\n"
    items = read_cif(Source(text))
    assert [items[key]['values'][0]['missing'] for key in ['_a', '_b', '_c', '_d']] == [None, 'unknown', None, 'not_applicable']
    assert items['_e']['values'][0]['value'] == "author's label"
    for item in items.values():
        for value in item['values']:
            loc = value['location']
            assert text[loc['start']:loc['end']] == value['raw_value']


@pytest.mark.parametrize('text,code', [
    ("data_x\n_a 'unterminated", 'PARSE_FAILED'),
    ('data_x\n_a\n;unterminated', 'PARSE_FAILED'),
    ('data_x\n_a', 'PARSE_FAILED'),
    ('data_x\nloop_\n_a\n_b\n1', 'PARSE_FAILED'),
    ('data_x\nsave_x\n_a 1\nsave_\n', 'INPUT_UNSUPPORTED'),
    ('data_x\n_a [1,2]', 'INPUT_UNSUPPORTED'),
])
def test_cif_dialect_and_damage_distinguished(text, code):
    with pytest.raises(FactError) as error:
        read_cif(Source(text))
    assert error.value.code == code


def make_bundle(tmp_path, data=None):
    data = cif() if data is None else data
    template = ROOT / '工作流设计/02-数据契约/phase1-real-v0.1/b1-review/examples/ingest-request.json'
    request = json.loads(template.read_text(encoding='utf-8'))
    request.update(declared_format='MMCIF', protein_sequence='A', protein_sequence_sha256=sha(b'A'))
    request['structure_artifact'].update(sha256=sha(data), size_bytes=len(data), media_type='chemical/x-cif')
    request['host_species'] = 'USER HOST MUST REMAIN'
    request['source_declaration'] = dict(kind='predicted', note='User statement only')
    structure = tmp_path / 'original.cif'
    structure.write_bytes(data)
    request_path = tmp_path / 'original-request.json'
    write_json(request_path, request)
    output = tmp_path / 'bundle'
    run(structure, request_path, output)
    return output, structure, request_path


def test_exact_byte_bundles_and_declarations(tmp_path):
    data = cif(metadata="_entity_src_gen.pdbx_host_org_scientific_name 'DIFFERENT EXPRESSION HOST'\n_exptl.method 'X-RAY DIFFRACTION'")
    output, structure, request = make_bundle(tmp_path, data)
    assert verify_bundle(output, reparse=True)['status'] == 'PASS'
    assert structure.read_bytes() == (output / 'input.structure').read_bytes() == data
    assert request.read_bytes() == (output / 'request.json').read_bytes()
    result = json.loads((output / 'result.json').read_text(encoding='utf-8'))
    assert result['host_species'] == 'USER HOST MUST REMAIN'
    assert result['source_declaration']['kind'] == 'predicted'
    assert all(value is None for value in result['unresolved_metadata'].values())
    with pytest.raises(FileExistsError):
        run(structure, request, output)


def test_rejected_file_keeps_separate_diagnostic_artifacts(tmp_path):
    output, _, _ = make_bundle(tmp_path, b'data_broken\nloop_\n_atom_site.id\n')
    assert verify_bundle(output, reparse=True)['outcome'] == 'rejected'
    result = json.loads((output / 'result.json').read_text(encoding='utf-8'))
    assert set(result['fact_artifacts']) == {'preflight', 'raw_metadata', 'raw_addresses'}
    assert result['mapping_status'] is None and result['error_code'] == 'PARSE_FAILED'


@pytest.mark.parametrize('filename', ['input.structure', 'request.json', 'preflight.json', 'raw_metadata.json', 'raw_addresses.json'])
def test_byte_tampering_rejected(tmp_path, filename):
    output, _, _ = make_bundle(tmp_path)
    with (output / filename).open('ab') as handle:
        handle.write(b' ')
    with pytest.raises(ValueError):
        verify_bundle(output)


@pytest.mark.parametrize('field,value', [('host_species', 'FILE HOST'), ('usable_for_pipeline', True),
    ('mapping_status', 'verified'), ('scientific_disposition', 'accepted'), ('production_status', 'DEPLOYED')])
def test_engineering_result_cannot_promote_or_overwrite(tmp_path, field, value):
    from jsonschema.exceptions import ValidationError
    output, _, _ = make_bundle(tmp_path)
    path = output / 'result.json'
    result = json.loads(path.read_text(encoding='utf-8'))
    result[field] = value
    write_json(path, result)
    with pytest.raises((ValueError, ValidationError)):
        verify_bundle(output)


def test_rehashed_cross_execution_artifact_rejected(tmp_path):
    output, _, _ = make_bundle(tmp_path)
    result = json.loads((output / 'result.json').read_text(encoding='utf-8'))
    registry = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    result['fact_artifacts']['raw_addresses']['attempt_id'] = 't01p1r-attempt-foreign'
    write_json(output / 'result.json', result)
    registry['result']['sha256'] = sha((output / 'result.json').read_bytes())
    next(a for a in registry['artifacts'] if a['path'] == 'raw_addresses.json')['ref'] = result['fact_artifacts']['raw_addresses']
    write_json(output / 'artifacts.json', registry)
    with pytest.raises(ValueError, match='Cross-execution'):
        verify_bundle(output)


def test_input_hash_mismatch_rejected_before_output(tmp_path):
    output, structure, request = make_bundle(tmp_path)
    structure.write_bytes(cif() + b'# changed\n')
    fresh = tmp_path / 'fresh'
    with pytest.raises(ValueError, match='Original structure bytes'):
        run(structure, request, fresh)
    assert not fresh.exists()


def test_metadata_without_bfactor_inference():
    facts = inspect_input(cif([dict(B_iso_or_equiv='99')]), declared_format='CIF')
    assert facts['raw_metadata']['assessment']['plddt'] is None
    assert facts['raw_addresses']['rows'][0]['fields']['B_iso_or_equiv']['value'] == '99'
    assert 'METADATA_MISSING' in {d['code'] for d in facts['raw_metadata']['diagnostics']}


def test_unknown_and_not_applicable_insertion_are_distinct_residues():
    facts = inspect_input(cif([dict(auth_seq_id='1', label_seq_id='1', pdbx_PDB_ins_code='?'),
                              dict(auth_seq_id='1', label_seq_id='1', pdbx_PDB_ins_code='.')]), declared_format='CIF')
    assert len(facts['raw_addresses']['residues']) == 2
    assert facts['raw_addresses']['residues'][0]['consumers']['integer_mapping_v0_1']['representable'] is False


def test_existing_integer_probe_and_scientific_registry_unchanged():
    from t01_structure_mapping.probe import parse_local, ProbeError
    raw = ROOT / 'discovery/t01-phase1-real/w1/b1-review-20260905/inputs/B116-noninteger-author.cif'
    # Locate the established unsupported fixture by its declared expectation.
    manifest = json.loads((raw.parents[1] / 'expected_cases.json').read_text(encoding='utf-8'))
    case = next(c for c in manifest['cases'] if 'Noninteger' in c['expected'].get('error_contains', ''))
    with pytest.raises(ProbeError, match='Noninteger'):
        parse_local(raw.parents[1] / case['structure'])
    contract = json.loads((ROOT / '工作流设计/02-数据契约/phase1-real-v0.1/contract.json').read_text(encoding='utf-8'))
    assert not any(tool['production_enabled'] for tool in contract['tools'])


def test_empty_model_and_all_model_headers_are_visible():
    pdb = (ROOT / 'tests/fixtures/structure_mapping/synthetic/partial-icode.pdb').read_bytes().replace(b'END   \n', b'')
    facts = inspect_input(b'MODEL        7\nENDMDL\nMODEL        9\n' + pdb + b'ENDMDL\nEND\n', declared_format='PDB')
    assert facts['preflight']['error_code'] == 'PARSE_FAILED'
    assert [m['model_serial'] for m in facts['raw_addresses']['models']] == ['7', '9']
    assert len(facts['raw_addresses']['model_records']) == 2
    assert facts['raw_addresses']['models'][0]['chains'] == []


def test_rehashed_origin_tampering_rejected(tmp_path):
    output, _, _ = make_bundle(tmp_path)
    path = output / 'raw_addresses.json'
    fact = json.loads(path.read_text(encoding='utf-8'))
    fact['rows'][0]['fields']['auth_seq_id']['location']['start'] += 1
    write_json(path, fact)
    result = json.loads((output / 'result.json').read_text(encoding='utf-8'))
    ref = result['fact_artifacts']['raw_addresses']
    ref.update(sha256=sha(path.read_bytes()), size_bytes=path.stat().st_size)
    write_json(output / 'result.json', result)
    registry = json.loads((output / 'artifacts.json').read_text(encoding='utf-8'))
    registry['result']['sha256'] = sha((output / 'result.json').read_bytes())
    next(a for a in registry['artifacts'] if a['path'] == path.name)['ref'] = ref
    write_json(output / 'artifacts.json', registry)
    with pytest.raises(ValueError, match='origin'):
        verify_bundle(output)


def test_sealed_campaign_and_originals():
    from check_b1_engineering import BATCH, verify
    result = verify(BATCH)
    assert result['cases'] == 40 and result['protected_files'] == 315
    assert result['production_status'] == 'NOT_DEPLOYED'


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'C:/outside', 'a\\b', 'a//b'])
def test_campaign_path_escape_rejected(path):
    from check_b1_engineering import safe_path
    with pytest.raises(ValueError):
        safe_path(ROOT, path)
