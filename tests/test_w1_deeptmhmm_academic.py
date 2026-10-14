"""Actual offline output and format failures; no model execution during pytest."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT/'discovery/t01-phase1-real/w1/deeptmhmm-academic-20260905'


def load(name):
    spec = importlib.util.spec_from_file_location('academic_'+name, BATCH/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def audit():
    return load('audit_raw')


def test_actual_offline_evidence():
    result = load('verify_evidence').verify()
    assert result['expert_sources_unchanged'] == 22
    assert result['model_execution'] == 'EXECUTED_OFFLINE_CPU'
    assert result['production_status'] == 'NOT_DEPLOYED'


def test_real_beta_regions_do_not_count_as_alpha_helices(audit):
    rows = audit.audit_case('coverage')['records']
    for identifier in ('Q9ALY0_KLEAE', 'Q9HVD1|BETA'):
        row = rows[identifier]
        assert row['raw_tmr_count'] > 0
        assert row['alpha_tm_segment_count'] == 0
        assert 'P' in row['labels'] and 'B' in row['labels']
        assert row['required_project_guard'] == dict(topology=None, status='unreliable', failure_level='WARNING', automatic_handoff=False)
        assert sum(s['end']-s['start']+1 for s in row['segments']) == len(row['sequence'])


def test_real_single_tm_and_signal_outputs(audit):
    rows = audit.audit_case('coverage')['records']
    assert rows['P07471|TM']['alpha_tm_segment_count'] == 1
    assert rows['P07471|TM']['outside_length'] == 60
    assert rows['CLV3_ARATH']['has_signal']
    assert rows['5H2A_CRIGR']['alpha_tm_segment_count'] == 7


def test_unknown_residue_is_observed_without_broadening_project_input_domain(audit):
    row = audit.audit_case('x-residue')['records']['Q8K459_X_SYNTHETIC']
    assert row['input_outside_aa20'] == ['X']
    assert row['sequence'][10] == 'X' and len(row['labels']) == len(row['sequence'])


@pytest.mark.parametrize('text', ['', '>a\n', '>a\nAA\n>a\nAA\n', 'AA\n>a\nAA', '>a\nA A'])
def test_bad_fasta_is_rejected_before_record_pairing(audit, text):
    with pytest.raises(ValueError):
        audit.fasta(text)


@pytest.mark.parametrize('text', ['>a | GLOB\nAA\n', '>a | GLOB\nAA\nII\nII',
    '>a | GLOB\nAA\nI', '>a | GLOB\nAA\nIX', '>b | GLOB\nAA\nII',
    '>a | GLOB\nAC\nII', '>a | GLOB\nAA\nII\n>a | GLOB\nAA\nII', '>a | UNKNOWN\nAA\nII'])
def test_bad_three_line_output_cannot_be_consumed(audit, text):
    with pytest.raises(ValueError):
        audit.three_line(text, {'a':'AA'})


@pytest.mark.parametrize('body', ['a\tinside\t0\t2\t\t\t\t', 'a\toutside\t1\t2\t\t\t\t',
    'a\tinside\t1\t1\t\t\t\t', 'b\tinside\t1\t2\t\t\t\t', 'a\tinside\t1\t2',
    'a\tinside\t1\t2\t\t\t\t\na\tinside\t2\t2\t\t\t\t'])
def test_region_bounds_coverage_ids_types_and_columns(audit, body):
    rows = audit.three_line('>a | GLOB\nAA\nII', {'a':'AA'})
    with pytest.raises(ValueError):
        audit.region_table('##gff-version 3\n# a Length: 2\n# a Number of predicted TMRs: 0\n'+body, rows)


@pytest.mark.parametrize('row', ['1 A,0,0,0,1,0,0', '0 C,0,0,0,1,0,0', '0 A,0,0,0,nan,0,0', '0 A,0,0,0,1.1,0,0'])
def test_probability_csv_position_sequence_and_value_integrity(audit, row):
    with pytest.raises(ValueError):
        audit.probability_table('# a\n#AA,Beta,Periplasm,Membrane,Inside,Outside,Signal\n'+row, 'a', 'A')


def test_manifest_hash_tampering_is_detected(tmp_path):
    verify = load('verify_evidence')
    (tmp_path/'raw.txt').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        verify.verify_files(tmp_path, [dict(path='raw.txt', bytes=7, sha256='0'*64)])
    with pytest.raises(ValueError, match='Unsafe'):
        verify.verify_files(tmp_path, [dict(path='../outside', bytes=0, sha256='0'*64)])
