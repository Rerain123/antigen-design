"""P4 closeout must name the audited replacement batches explicitly."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import close_m1_p4_target as closeout


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def test_closeout_uses_explicit_replacement_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(closeout, 'BASE', tmp_path)
    digest = 'a' * 64
    save(tmp_path / 'nr-inspect-r01.json', {'result': {'size_checks_pass': True,
        'sha256sums_matches_receipt': True, 'receipt_file_count': 1113}})
    save(tmp_path / 'nr-info-r01.json', {'read_only_mount': True, 'log': 'BLASTDB Version: 5'})
    save(tmp_path / 'nr-sizes-r01.json', {'read_only_mount': True, 'result': {'pal': [1]}})
    save(tmp_path / 'nr-manifest-r01.json', {'result': {'status': 'REGISTERED_NOT_VERIFIED',
        'manifest_sha256': digest}})
    save(tmp_path / 'nr-hash-r01.json', {'read_only_mount': True, 'result': {
        'status': 'VERIFIED_FULL_SHA256', 'manifest_sha256': digest, 'files': 2227, 'bytes': 740587510662}})
    save(tmp_path / 'nr-contract-r01.json', {'status': 'REAL_TARGET_PREBUILT_CONTRACT_PASS',
        'manifest_sha256': digest})
    save(tmp_path / 'nr-deployment-verification-r01.json', {'status': 'P4_NR_DEPLOYED_READONLY_PASS',
        'read_only': True, 'manifest_sha256': digest})
    for batch, branch in (('r08', 'design'), ('r09', 'wt'), ('r07', 'failure')):
        job, run = 'job-' + batch, 'run-' + batch
        save(tmp_path / batch / 'batch.json', {'branch': branch, 'database_kind': 'target-nr',
            'request': {'analysis': {'blast': {'database_id': 'nr-20250624',
                'database_manifest_sha256': '0' * 64 if branch == 'failure' else digest}}}})
        save(tmp_path / batch / 'audit-summary.json', {'status': 'P4_TARGET_' + branch.upper() + '_PASS',
            'database': 'nr-20250624', 'p4_m1_complete': False, 'scientific_release_gate': 'CLOSED',
            'usable_for_pipeline': False, 'production_status': 'NOT_DEPLOYED',
            'job_id': job, 'run_id': run, 'target_nr_accepted': branch != 'failure',
            'verified_artifacts': 10})
        save(tmp_path / batch / 'workflow-snapshot.json', {'job': {'job_id': job, 'run_id': run,
            'state': 'failed' if branch == 'failure' else 'succeeded'}})
        if branch != 'failure':
            save(tmp_path / batch / 'download-verification.json', {'target_database_connected': True})
    closeout.close('r08', 'r09', 'r07')
    result = json.loads((tmp_path / 'p4-m1-acceptance-r01.json').read_bytes())
    assert result['status'] == 'P4_M1_MINIMAL_PASS'
    assert {k: v['batch'] for k, v in result['paths'].items()} == {
        'design': 'r08', 'wt': 'r09', 'failure': 'r07'}
    assert result['scientific_release_gate'] == 'CLOSED'


def test_closeout_rejects_reused_batch_before_reading(tmp_path, monkeypatch):
    monkeypatch.setattr(closeout, 'BASE', tmp_path)
    with pytest.raises(AssertionError):
        closeout.close('r08', 'r08', 'r07')
