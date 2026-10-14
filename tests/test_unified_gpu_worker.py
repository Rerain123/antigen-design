import json
import os
from pathlib import Path
import sys

import pytest

from t01_phase1_real.resident_process import Command, atomic, prepare
from t01_phase1_real import unified_gpu_worker as worker


def spools(tmp_path):
    result, targets = {}, []
    for index, tool in enumerate(('proteinmpnn', 'esmfold2')):
        root = tmp_path / tool
        command = Command(tool, ('/usr/bin/python3', '-V'))
        target = prepare(root, str(index + 1) * 32,
            {'job_id': 'job-' + tool, 'attempt_id': 'attempt-' + tool,
             'execution_identity': tool}, command, {'input.json': b'{}'}, 10)
        os.utime(target / 'request.json', ns=((index + 1) * 1_000_000_000,) * 2)
        result[root] = {tool: command}; targets.append(target)
    return result, targets


def receipt(target, state='succeeded', stopped=True):
    request, fingerprint = worker.read_json(target / 'request.json')
    value = {'state': state, 'stopped_confirmed': stopped,
             'binding': request['binding'], 'request_sha256': fingerprint}
    atomic(target / 'execution.json', value)
    return value


def test_fifo_is_serial_across_environments_and_does_not_reexecute(tmp_path):
    roots, _ = spools(tmp_path); calls = []; state = tmp_path / 'state.json'
    def execute(target, command, stopping):
        assert json.loads(state.read_bytes())['execution']['target'] == str(target)
        calls.append(command.tool)
        return receipt(target)
    assert worker.tick(roots, state, execute=execute)['tool'] == 'proteinmpnn'
    assert worker.tick(roots, state, execute=execute)['tool'] == 'esmfold2'
    assert worker.tick(roots, state, execute=execute) is None
    assert calls == ['proteinmpnn', 'esmfold2']


def test_unowned_uncertain_execution_blocks_every_spool(tmp_path):
    roots, targets = spools(tmp_path); receipt(targets[1], 'running', False)
    with pytest.raises(RuntimeError, match='blocks all'):
        worker.tick(roots, tmp_path / 'state.json', execute=lambda *a: pytest.fail())


def test_error_retains_owner_and_recovers_only_same_execution(tmp_path):
    roots, targets = spools(tmp_path); state = tmp_path / 'state.json'
    def fail(target, *unused):
        receipt(target, 'running', False); raise RuntimeError('lost process')
    with pytest.raises(RuntimeError, match='lost process'):
        worker.tick(roots, state, execute=fail)
    assert json.loads(state.read_bytes())['execution']['target'] == str(targets[0])
    def recover(target, *unused):
        assert target == targets[0]
        return receipt(target, 'interrupted')
    assert worker.tick(roots, state, execute=recover)['state'] == 'interrupted'


@pytest.mark.parametrize('terminal', ['succeeded','failed','cancelled','timed_out','interrupted'])
def test_only_confirmed_terminal_receipt_releases_slot(tmp_path, terminal):
    roots, _ = spools(tmp_path); state = tmp_path / 'state.json'
    row = worker.tick(roots, state, execute=lambda target, *a: receipt(target, terminal))
    assert row['state'] == terminal
    assert json.loads(state.read_bytes())['phase'] == 'idle'


def test_unconfirmed_return_does_not_release_slot(tmp_path):
    roots, _ = spools(tmp_path); state = tmp_path / 'state.json'
    with pytest.raises(RuntimeError, match='unconfirmed'):
        worker.tick(roots, state, execute=lambda target, *a: receipt(target, 'running', False))
    assert json.loads(state.read_bytes())['phase'] == 'active'


def test_completed_history_may_keep_old_command_but_pending_may_not(tmp_path):
    roots, targets = spools(tmp_path); receipt(targets[0])
    roots[targets[0].parent]['proteinmpnn'] = Command('proteinmpnn', ('/new/python', '-V'))
    assert len(worker.pending(roots)) == 1
    roots[targets[1].parent]['esmfold2'] = Command('esmfold2', ('/new/python', '-V'))
    with pytest.raises(ValueError, match='registered command'): worker.pending(roots)


def test_stop_before_start_and_receipt_binding_tamper(tmp_path):
    roots, targets = spools(tmp_path)
    assert worker.tick(roots, tmp_path / 'state.json', stopping=lambda: True) is None
    value = receipt(targets[0]); value['binding'] = {}; atomic(targets[0] / 'execution.json', value)
    with pytest.raises(ValueError, match='identity'): worker.pending(roots)


@pytest.mark.parametrize('row', [
    'NVIDIA A100-SXM4-40GB, GPU-' + 'a'*36 + ', 40960',
    'NVIDIA A100-SXM-64GB, GPU-' + 'b'*36 + ', 65536',
    'NVIDIA A100-SXM-64GB, GPU-' + 'a'*36 + ', nan',
    'NVIDIA A100-SXM-64GB, GPU-' + 'a'*36 + ', 65536\nNVIDIA A100-SXM-64GB, x, 65536'])
def test_device_guard_rejects_wrong_or_multiple_devices(monkeypatch, row):
    monkeypatch.setattr(worker.subprocess, 'check_output', lambda *a, **k: row)
    with pytest.raises(RuntimeError): worker.gpu_guard('GPU-' + 'a'*36)


def test_device_guard_accepts_only_approved_64gb(monkeypatch):
    uuid = 'GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31'
    monkeypatch.setattr(worker.subprocess, 'check_output', lambda *a, **k: f'NVIDIA A100-SXM-64GB, {uuid}, 65536')
    assert worker.gpu_guard(uuid)['memory_mib'] == 65536


@pytest.mark.parametrize('name,memory', [('NVIDIA A100-SXM4-40GB', 40960), ('NVIDIA RTX 4090', 24564)])
def test_scheduler_selected_gpu_records_actual_hardware(monkeypatch, name, memory):
    uuid = 'GPU-53cfb869-cb43-8ac4-6a0c-b46b4d5202a8'
    monkeypatch.setattr(worker.subprocess, 'check_output', lambda *a, **k: f'{name}, {uuid}, {memory}')
    observed = worker.gpu_guard(None)
    assert observed['uuid'] == uuid and observed['memory_mib'] == memory
    assert observed['allocation_policy'] == 'scheduler-assigned-exclusive-v1'


@pytest.mark.parametrize('raw', ['', 'GPU, bad, 40960', 'GPU, GPU-53cfb869-cb43-8ac4-6a0c-b46b4d5202a8, nan',
    'GPU, GPU-53cfb869-cb43-8ac4-6a0c-b46b4d5202a8, 0',
    'GPU, GPU-53cfb869-cb43-8ac4-6a0c-b46b4d5202a8, 40960\nGPU, another, 40960'])
def test_assigned_gpu_guard_still_rejects_invalid_or_multiple_devices(monkeypatch, raw):
    monkeypatch.setattr(worker.subprocess, 'check_output', lambda *a, **k: raw)
    with pytest.raises((RuntimeError, ValueError)):
        worker.gpu_guard(None)


def test_build_has_no_gpu_or_existing_deployment_mutation():
    sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
    try:
        from prepare_unified_gpu_build import documents, DOCKERFILE
        docs = documents(); pod = docs[-1]['spec']['template']['spec']
        assert [d['kind'] for d in docs] == ['ConfigMap','NetworkPolicy','PersistentVolumeClaim','Job']
        assert pod['automountServiceAccountToken'] is False
        assert 'nvidia.com/gpu' not in json.dumps(pod)
        assert 'pip install' not in DOCKERFILE and DOCKERFILE.count('@sha256:') == 3
    finally: sys.path.pop(0)


def test_deployment_replaces_one_holder_with_one_full_64gb_worker():
    sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
    try:
        from prepare_unified_gpu_deploy import patch, relocated
        before = json.loads((Path(__file__).parents[1] / '.tmp/single-gpu-cpu-r01/before.json').read_bytes())
        before['spec']['template']['spec']['containers'] = [
            row for row in before['spec']['template']['spec']['containers'] if row['name'] != 'worker-gpu']
        image = 'harbor-core.base.svc.cluster.local/qcyz/antigen-unified-gpu@sha256:' + 'a' * 64
        operations = patch(before, image)
        template = operations[-1]['value']; gpu = [row for row in template['spec']['containers']
                                                   if 'nvidia.com/gpu' in row.get('resources', {}).get('limits', {})]
        assert [row['name'] for row in gpu] == ['worker-unified-gpu']
        for kind in ('requests', 'limits'):
            assert gpu[0]['resources'][kind]['nvidia.com/gpu'] == '1'
            assert gpu[0]['resources'][kind]['nvidia.com/gpumem-percentage'] == '100'
        assert gpu[0]['resources']['requests']['memory'] == '96Gi'
        assert gpu[0]['resources']['limits']['memory'] == '128Gi'
        assert gpu[0]['resources']['requests']['cpu'] == '8'
        assert gpu[0]['resources']['limits']['cpu'] == '16'
        assert template['metadata']['annotations']['nvidia.com/use-gpuuuid'].startswith('GPU-')
        assert template['metadata']['annotations']['antigen-design/gpu-worker-host-profile'] == \
            'af3-combined-96-128gi-8-16cpu-r02'
        assert template['spec']['automountServiceAccountToken'] is False
        command = relocated({'tool': 'proteinmpnn', 'argv': ['/usr/local/bin/python', '-V'],
                             'environment': {'PATH': '/usr/local/bin:/usr/bin:/bin'},
                             'memory_bytes': 2**38})
        assert command['argv'][0] == '/opt/t01/env/proteinmpnn/bin/python'
        assert command['environment']['PYTHONHOME'] == '/opt/t01/env/proteinmpnn'
        assert relocated(command)['environment']['PATH'].count(
            '/opt/t01/env/proteinmpnn/bin') == 1
        esm = relocated({'tool': 'esmfold2', 'argv': ['/usr/local/bin/python', '-V'],
                          'environment': {'PATH': '/usr/local/bin:/usr/bin:/bin'},
                          'memory_bytes': 2**38})
        assert esm['argv'][0] == '/opt/t01/env/esmfold2/bin/python'
        assert esm['environment']['T01_RESIDENT_SLOT'] == '/run/t01-slot'
        assert esm['environment']['T01_PRIVATE_TMP'] == '1'
        assert esm['environment']['T01_PRECREATE_NATIVE'] == '0'
    finally: sys.path.pop(0)
