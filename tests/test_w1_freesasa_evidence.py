"""Evidence-integrity and conversion regressions; no FreeSASA install required."""
import copy
import importlib.util
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'discovery/t01-phase1-real/w1/freesasa-s09-20260905'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BATCH / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recorded_campaign_and_rule_sources_are_intact():
    verifier = load('w1_evidence_baseline', 'verify_evidence.py')
    result = verifier.verify()
    assert result['status'] == 'PASS'
    assert result['production_status'] == 'NOT_DEPLOYED'
    assert result['s09_execution'] == 'NOT_RUN'


def test_modified_raw_output_is_rejected(tmp_path):
    verifier = load('w1_evidence_corruption', 'verify_evidence.py')
    shutil.copytree(BATCH, tmp_path / 'batch')
    verifier.BATCH = tmp_path / 'batch'
    path = verifier.BATCH / 'runs/converted-pdb/result/raw.json'
    path.write_bytes(path.read_bytes().replace(b'4804.055641141745', b'4805.055641141745'))
    with pytest.raises(ValueError, match='raw.json'):
        verifier.verify()


def test_pending_scientific_case_cannot_be_silently_decided(monkeypatch):
    verifier = load('w1_evidence_decision', 'verify_evidence.py')
    original_read = verifier.read

    def substituted_read(path):
        data = original_read(path)
        if path.name == 'PHASE1_REAL_W1_S09_CASES.json':
            data = copy.deepcopy(data)
            pending = next(c for c in data['cases'] if c['kind'] == 'DECISION_REQUIRED')
            pending['expected_fields']['confidence'] = 'medium'
        return data

    monkeypatch.setattr(verifier, 'read', substituted_read)
    with pytest.raises(ValueError, match='fabricated expectations'):
        verifier.verify()


def test_1ubq_conversion_retains_atom_identity_and_coordinates(tmp_path):
    probe = load('w1_conversion', 'probe_raw.py')
    result = probe.convert_cif(BATCH/'inputs/1UBQ.cif', tmp_path/'converted.pdb')
    assert result['atom_rows'] == 660
    assert result['identity_and_pdb_precision_roundtrip'] == 'PASS'
    assert (BATCH/'inputs/1UBQ.cif').read_bytes() == (ROOT/'tests/fixtures/structure_mapping/real/1UBQ.cif').read_bytes()


def test_nonrepresentable_author_chain_is_not_silently_truncated(tmp_path):
    from Bio.PDB.PDBExceptions import PDBIOException
    probe = load('w1_conversion_bad_chain', 'probe_raw.py')
    with pytest.raises(PDBIOException, match='Chain id'):
        probe.convert_cif(BATCH/'inputs/partial-icode.cif', tmp_path/'bad.pdb')
