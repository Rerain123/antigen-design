import base64
import importlib.util
import json
from pathlib import Path

import pytest


def load_probe():
    path = Path(__file__).resolve().parents[1] / 'scripts/run_cluster_workflow_probe.py'
    spec = importlib.util.spec_from_file_location('cluster_probe', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('mode',['provided','esmfold2','af3'])
def test_request_is_valid_and_does_not_reuse_candidates(mode):
    from t01_phase1_real.development.workflow.policy import request
    probe = load_probe()
    body = probe.request_document(mode)
    request(json.dumps(body).encode())
    assert body['reuse_jobs'] == {}
    assert all(body['analysis'][name] is None for name in ('blast', 'domains', 'homology'))
    if mode in ('esmfold2', 'af3'):
        assert body['structure'] is None
        expected_timeout = 2400 if mode == 'af3' else 600
        assert body['prediction'] == {'engine': mode, 'seed': 1, 'timeout_seconds': expected_timeout}
        assert body['expression_host'] == 'Escherichia coli K-12 W3110'
    else:
        assert 'prediction' not in body and body['structure'] is not None


def test_lost_submission_response_keeps_same_key_and_upload(tmp_path, monkeypatch):
    probe = load_probe()
    monkeypatch.setattr(probe, 'OUT', tmp_path)
    monkeypatch.setattr(probe, 'rpc', lambda *args: {})
    batch = dict(input_sha256=probe.sha(probe.FIXTURE.read_bytes()), request=probe.request_document(), idempotency_key='fixed-key')
    submissions = []
    uploads = []

    def tool(batch, name, args):
        if name == 'structure.upload':
            uploads.append(args)
            return dict(upload_id='fixed-upload', sha256=batch['input_sha256'])
        submissions.append(args.copy())
        if len(submissions) == 1:
            raise RuntimeError('Response lost after acceptance')
        return dict(job_id='t01p1r-job-' + 'a' * 32, state='running')

    monkeypatch.setattr(probe, 'tool', tool)
    with pytest.raises(RuntimeError, match='Response lost'):
        probe.start(batch)
    resumed = json.loads((tmp_path / 'batch.json').read_bytes())
    probe.start(resumed)
    assert len(uploads) == 1
    assert len(submissions) == 3
    assert all(item == submissions[0] for item in submissions)


def test_esmfold2_start_has_no_upload_and_replays_same_request(tmp_path, monkeypatch):
    probe = load_probe()
    monkeypatch.setattr(probe, 'OUT', tmp_path)
    monkeypatch.setattr(probe, 'rpc', lambda *args: {})
    request = probe.request_document('esmfold2')
    batch = dict(request=request, idempotency_key='first-chain', input_mode='esmfold2',
                 sequence_sha256=probe.sha(request['protein_sequence'].encode()))
    calls = []

    def tool(batch, name, args):
        calls.append((name, args.copy()))
        return dict(job_id='t01p1r-job-' + 'b' * 32, state='running')

    monkeypatch.setattr(probe, 'tool', tool)
    probe.start(batch)
    assert [name for name, _ in calls] == ['workflow.submit', 'workflow.submit']
    assert all('structure_upload_id' not in args for _, args in calls)
    assert calls[0][1] == calls[1][1]
    assert json.loads(calls[0][1]['request_json']) == request


def test_bad_report_hash_is_rejected_before_writing(tmp_path, monkeypatch):
    probe = load_probe()
    monkeypatch.setattr(probe, 'OUT', tmp_path)
    monkeypatch.setattr(probe, 'status', lambda batch: dict(state='succeeded'))
    monkeypatch.setattr(probe, 'tool', lambda *args: dict(content_base64=base64.b64encode(b'bad').decode(), sha256='0'*64, size_bytes=3))
    with pytest.raises(RuntimeError, match='hash mismatch'):
        probe.download(dict(job_id='test'))
    assert not (tmp_path / 'report.zip').exists()


def test_new_batch_retains_old_identity(tmp_path, monkeypatch):
    import sys
    probe = load_probe()
    monkeypatch.setattr(probe, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['probe', 'prepare'])
    probe.main()
    first = probe.OUT / 'batch.json'
    raw = first.read_bytes()
    monkeypatch.setattr(sys, 'argv', ['probe', 'prepare', '--batch', 'r02'])
    probe.main()
    assert first.read_bytes() == raw
    assert json.loads(raw)['idempotency_key'] != json.loads((probe.OUT / 'batch.json').read_bytes())['idempotency_key']


def test_prepare_esmfold2_batch_records_fixed_sequence_identity(tmp_path, monkeypatch):
    import sys
    probe = load_probe()
    monkeypatch.setattr(probe, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['probe', 'prepare', '--batch', 'r03', '--input-mode', 'esmfold2'])
    probe.main()
    batch = json.loads((probe.OUT / 'batch.json').read_bytes())
    assert batch['input_mode'] == 'esmfold2'
    assert batch['sequence_sha256'] == probe.sha(probe.SEQUENCE.encode())
    assert 'input_sha256' not in batch and batch['request']['structure'] is None
