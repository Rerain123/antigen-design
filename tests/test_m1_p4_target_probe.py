"""A new target run may only be prepared from the verified nr manifest identity."""
import json
import sys
import pytest
from t01_phase1_real.common import REPO

sys.path.insert(0, str(REPO / 'scripts'))
import run_m1_p4_probe as probe


def test_target_prepare_requires_full_hash_and_binds_exact_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, 'BASE', tmp_path)
    monkeypatch.setattr(probe.probe, 'OUT', tmp_path / 'placeholder')
    monkeypatch.setattr(probe.probe, 'FIXTURE', tmp_path / 'placeholder.pdb')
    monkeypatch.setattr(sys, 'argv', ['p4', 'prepare', '--batch', 'r99', '--database', 'target-nr'])
    (tmp_path / 'nr-manifest-r01.json').write_text(json.dumps(dict(result=dict(manifest_sha256='a'*64))))
    with pytest.raises(FileNotFoundError):probe.main()
    (tmp_path / 'nr-hash-r01.json').write_text(json.dumps(dict(result=dict(
        status='VERIFIED_FULL_SHA256', manifest_sha256='a'*64))))
    probe.main()
    batch=json.loads((tmp_path / 'r99/batch.json').read_bytes())
    assert batch['database_kind']=='target-nr'
    assert batch['request']['analysis']['blast']['database_id']=='nr-20250624'
    assert batch['request']['analysis']['blast']['database_manifest_sha256']=='a'*64
    assert batch['request']['analysis']['blast']['timeout_seconds']==7200
    source=json.loads((tmp_path / 'r99/input-provenance.json').read_bytes())
    assert source['target_database_connected'] and not source['formal_database_connected']
