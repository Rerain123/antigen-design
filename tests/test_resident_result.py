"""Contract-only execution receipts: not native scientific qualification."""
import copy

import pytest

from t01_phase1_real.common import encode, sha
from t01_phase1_real.resident_result import image_matches, isolation_matches


IMAGE = 'sha256:' + 'a'*64


@pytest.fixture
def recorded():
    binding = dict(job_id='job', attempt_id='attempt', execution_identity='exec')
    observation = dict(source_image_id=IMAGE, machine='x86_64', network_interfaces=[[1,'lo'],[2,'eth0']],
                       cpu_affinity=[4,5,6], network_restriction='seccomp-local-sockets-only-v1')
    request = dict(binding=binding, execution_id='a'*32, command=dict(environment={
        'T01_SOURCE_IMAGE_ID': IMAGE, 'T01_RESIDENT_OFFLINE': '1'}))
    runtime = dict(network_interfaces=observation['network_interfaces'], cpu_affinity=observation['cpu_affinity'])
    files = {'resident/executor-observation.json': encode(observation), 'resident/request.json': encode(request),
             'output/runtime.json': encode(runtime)}
    receipt = dict(backend='resident-process', state='succeeded', binding=binding, execution_id='a'*32,
                   stopped_confirmed=True, exit_code=0, request_sha256=sha(encode(request)), outputs={
                       'output/executor-observation.json': dict(sha256=sha(files['resident/executor-observation.json']), size_bytes=len(files['resident/executor-observation.json'])),
                       'output/native/runtime.json': dict(sha256=sha(files['output/runtime.json']), size_bytes=len(files['output/runtime.json']))})
    execution = dict(binding, backend='resident-process', source_image_id=IMAGE,
                     resident_receipt=receipt, resident_observation=observation)
    files['resident/execution.json'] = encode(execution)
    return runtime, files, execution


def test_resident_keeps_actual_interfaces_and_cpu_observations(recorded):
    runtime, files, execution = recorded
    original = copy.deepcopy(files)
    assert image_matches(execution, IMAGE) and isolation_matches(runtime, files, IMAGE, [0,1])
    assert files == original and runtime['cpu_affinity'] == [4,5,6]
    assert not image_matches(execution, 'wrong-image')


@pytest.mark.parametrize('damage', ['output', 'observation', 'request', 'binding', 'stopped', 'exit', 'offline', 'cpu'])
def test_missing_or_changed_receipts_reject_resident_output(recorded, damage):
    runtime, files, execution = recorded
    if damage in ('output', 'observation', 'request'):
        name = {'output':'output/runtime.json','observation':'resident/executor-observation.json','request':'resident/request.json'}[damage]
        files[name] += b' '
    elif damage == 'binding': execution['resident_receipt']['binding']['attempt_id'] = 'foreign'
    elif damage == 'stopped': execution['resident_receipt']['stopped_confirmed'] = False
    elif damage == 'exit': execution['resident_receipt']['exit_code'] = True
    elif damage == 'offline': execution['resident_observation']['network_restriction'] = None
    elif damage == 'cpu': runtime['cpu_affinity'] = [0,1]
    files['resident/execution.json'] = encode(execution)
    assert not isolation_matches(runtime, files, IMAGE, [0,1])


def test_legacy_runtime_requires_original_offline_cpu_profile():
    runtime = dict(network_interfaces=[[1,'lo']], cpu_affinity=[0,1])
    assert isolation_matches(runtime, {}, IMAGE, [0,1])
    assert not isolation_matches(runtime, {}, IMAGE, [2,3])
    runtime['network_interfaces'].append([2,'eth0'])
    assert not isolation_matches(runtime, {}, IMAGE, [0,1])
