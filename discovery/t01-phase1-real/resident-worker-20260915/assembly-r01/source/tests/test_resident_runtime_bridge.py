"""Engineering lifecycle checks; no synthetic scientific results are accepted."""
import json
from pathlib import Path

import pytest

from t01_phase1_real.common import encode, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.bepipred import policy
from t01_phase1_real import resident_execution as bridge
from t01_phase1_real.resident_process import atomic, encoded


@pytest.fixture
def setup(tmp_path, monkeypatch):
    rt = Runtime(tmp_path / 'runtime')
    command = dict(tool='bepipred', argv=['/usr/local/bin/python', '-B', '/worker.py'], memory_bytes=1024**3,
                   environment=dict(T01_SOURCE_IMAGE_ID=policy.IMAGE, T01_RESIDENT_OFFLINE='1'))
    config = tmp_path / 'resident.json'
    config.write_bytes(encode(dict(version='0.1.0', runtime_volume_root=str(tmp_path), tools={
        'bepipred': dict(root=str(tmp_path / 'spool'), source_image_id=policy.IMAGE, command=command)})))
    monkeypatch.setenv('T01_RESIDENT_CONFIG_FILE', str(config))
    monkeypatch.setattr(policy, 'verify_assets', lambda: None)
    raw = encode(dict(protein_sequence='ACDEFGHIKLMNPQRSTVWY', user_sequence_id='bridge-test', timeout_seconds=30))
    job = rt.submit_sequence(raw, 'resident-test', policy.TOOL)
    return rt, job, config


def complete(rt, job, state='failed', code=7):
    target = Path(rt.execution(job['job_id'])['resident_target'])
    raw = (target / 'request.json').read_bytes()
    request = json.loads(raw)
    receipt = dict(version='0.1.0', backend='resident-process', binding=request['binding'],
                   execution_id=target.name, request_sha256=sha(raw), stopped_confirmed=True,
                   state=state, exit_code=code, outputs={})
    atomic(target / 'execution.json', receipt)
    return target


def test_dispatch_recover_reuses_original_identity_and_native_failure(setup):
    rt, job, _ = setup
    assert rt.dispatch(job['job_id'])['state'] == 'running'
    before = rt.execution(job['job_id'])
    assert before['backend'] == 'resident-process'
    assert rt.recover(job['job_id'])['state'] == 'reconciling'
    assert rt.execution(job['job_id'])['resident_target'] == before['resident_target']
    complete(rt, job)
    end = rt.reconcile(job['job_id'])
    assert end['state'] == 'failed' and end['error_code'] == 'TOOL_FAILED'
    result = rt.result(job['job_id'])
    assert result['raw_scores'] is None and not result['usable_for_pipeline']
    assert result['execution']['backend'] == 'resident-process'
    assert 'image_id' not in result['execution']  # derived runtime is not the old Docker image
    assert rt.reconcile(job['job_id']) == end


def test_cancel_waits_for_worker_stop_receipt(setup):
    rt, job, _ = setup
    rt.dispatch(job['job_id'])
    rt.control(encode(dict(contract_version='0.1.0', operation='cancel', job_id=job['job_id'], idempotency_key='cancel')))
    assert rt.reconcile(job['job_id'])['state'] not in ('cancelled', 'succeeded')
    target = Path(rt.execution(job['job_id'])['resident_target'])
    assert (target / 'cancel').exists()
    complete(rt, job, 'cancelled', None)
    end = rt.reconcile(job['job_id'])
    assert end['state'] == 'cancelled' and end['stop_confirmed']


def test_wrong_receipt_binding_never_confirms_stop(setup):
    rt, job, _ = setup
    rt.dispatch(job['job_id'])
    target = complete(rt, job)
    receipt = json.loads((target / 'execution.json').read_bytes())
    receipt['binding']['attempt_id'] = 'foreign'
    atomic(target / 'execution.json', receipt)
    assert rt.reconcile(job['job_id'])['state'] == 'reconciling'
    assert (target / 'cancel').exists()


def test_clean_exit_without_native_result_is_invalid(setup):
    rt, job, _ = setup
    rt.dispatch(job['job_id'])
    complete(rt, job, 'succeeded', 0)
    end = rt.reconcile(job['job_id'])
    assert end['state'] == 'failed' and end['error_code'] == 'OUTPUT_INVALID'


def test_changed_request_command_is_never_executed(setup):
    rt, job, _ = setup
    rt.dispatch(job['job_id'])
    target = Path(rt.execution(job['job_id'])['resident_target'])
    raw = json.loads((target / 'request.json').read_bytes())
    raw['command']['argv'] = ['/bin/sh', '-c', 'echo should-not-run']
    atomic(target / 'request.json', raw)
    assert rt.reconcile(job['job_id'])['state'] == 'reconciling'
    assert not (target / 'execution.json').exists()


def test_partial_stage_replays_after_controller_crash(tmp_path):
    from t01_phase1_real.resident_process import Command, prepare
    binding = dict(job_id='job', attempt_id='attempt', execution_identity='execution')
    target = tmp_path / ('a'*32)
    (target / 'input').mkdir(parents=True)
    (target / 'input/a').write_bytes(b'unchanged')
    command = Command('probe', ('/usr/bin/python3',))
    assert prepare(tmp_path, target.name, binding, command, {'a': b'unchanged', 'b': b'new'}, 5) == target
    assert json.loads((target / 'request.json').read_bytes())['binding'] == binding


def test_changed_configuration_requests_stop_without_claiming_it(setup):
    rt, job, config = setup
    rt.dispatch(job['job_id'])
    config.write_bytes(config.read_bytes() + b' ')
    assert rt.reconcile(job['job_id'])['state'] == 'reconciling'
    assert (Path(rt.execution(job['job_id'])['resident_target']) / 'cancel').exists()


def test_output_tamper_after_confirmed_stop_is_terminal_failure(setup):
    rt, job, _ = setup
    rt.dispatch(job['job_id'])
    target = complete(rt, job, 'succeeded', 0)
    (target / 'output/unexpected').write_bytes(b'changed')
    end = rt.reconcile(job['job_id'])
    assert end['state'] == 'failed' and end['error_code'] == 'OUTPUT_INVALID'


def test_timeout_receipt_sets_business_timeout(setup):
    rt, job, _ = setup
    rt.dispatch(job['job_id'])
    complete(rt, job, 'timed_out', -9)
    end = rt.reconcile(job['job_id'])
    assert end['state'] == 'timed_out' and end['stop_confirmed']
