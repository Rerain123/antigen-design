import json
import os
from pathlib import Path
import sys
import threading
import time

import pytest

from t01_phase1_real.resident_process import (
    Command, DEFAULT_FILE_SIZE_BYTES, MAX_FILE_SIZE_BYTES, cancel, inventory,
    prepare, run,
)


BINDING = dict(job_id='job-a', attempt_id='attempt-a', execution_identity='execution-a')


@pytest.mark.skipif(sys.platform != 'linux', reason='Native directory aliases require Linux')
@pytest.mark.parametrize('database_id', ['approved', '../outside', '/etc', 'missing'])
def test_native_layout_switches_tmp_and_rejects_unregistered_database(tmp_path, database_id):
    slot = tmp_path / 'slot'
    database_root = tmp_path / 'databases'
    (database_root / 'approved').mkdir(parents=True)
    package = tmp_path / 'package'
    package.mkdir()
    (package / 'model.txt').write_text('original')
    (package / 'local.yaml').write_text('original config')
    (package / 'analysis').mkdir()
    (package / 'analysis/main.py').write_text('original Python source')
    script = (
        "import os; from pathlib import Path; s=Path(os.environ['T01_RESIDENT_SLOT']); "
        "assert not (s/'tmp/sentinel').exists(); (s/'tmp/sentinel').write_text('new'); "
        "assert (s/'package/model.txt').read_text()=='original'; "
        "assert (s/'package/local.yaml').read_text()=='execution config'; "
        "assert (s/'upstream/local.yaml').read_text()=='original config'; "
        "assert (s/'package/analysis/main.py').resolve().parent.parent==(s/'package').resolve(); "
        "assert (s/'package/analysis/main.py').read_text()=='original Python source'; "
        "assert (s/'database').resolve().name=='approved'"
    )
    native = Command('layout', (sys.executable, '-B', '-c', script), tuple(sorted(dict(
        T01_RESIDENT_SLOT=str(slot), T01_PRIVATE_TMP='1', T01_NATIVE_PACKAGE=str(package),
        T01_THERMOMPNN_LAYOUT='1', T01_DATABASE_ROOT=str(database_root)).items())))
    for repeat in range(2):
        target = prepare(tmp_path / 'spool', str(repeat + 1) * 32, BINDING, native, {
            'input.json': json.dumps(dict(database_id=database_id)).encode(),
            'native/runtime-local.yaml': b'execution config'}, 10)
        receipt = run(target, native)
        assert receipt['stopped_confirmed']
        assert (receipt['state'] == 'succeeded') == (database_id == 'approved')
        assert (target / 'work/tmp/sentinel').exists() == (database_id == 'approved')
    assert (package / 'local.yaml').read_text() == 'original config'


def command(script="print('ok')"):
    return Command('probe', (sys.executable, '-B', '-c', script))


def test_command_file_size_limit_is_explicit_and_bounded():
    assert 'file_size_bytes' not in command().document()
    assert Command('probe', ('/usr/bin/python3',), file_size_bytes=512 * 1024**2).document()['file_size_bytes'] == 512 * 1024**2
    for value in (True, DEFAULT_FILE_SIZE_BYTES - 1, MAX_FILE_SIZE_BYTES + 1):
        with pytest.raises(ValueError, match='file size'):
            Command('probe', ('/usr/bin/python3',), file_size_bytes=value).document()


@pytest.mark.parametrize('name', ['../escape', '/etc/passwd', 'a/../../b', 'a\\b', '.', 'a//b'])
def test_input_paths_rejected_before_creation(tmp_path, name):
    with pytest.raises(ValueError):
        prepare(tmp_path, 'a'*32, BINDING, command(), {name: b'x'}, 5)
    assert not (tmp_path / ('a'*32)).exists()


def test_replay_requires_identical_command_binding_and_input(tmp_path):
    original = prepare(tmp_path, 'a'*32, BINDING, command(), {'a.txt': b'original'}, 5)
    assert prepare(tmp_path, 'a'*32, BINDING, command(), {'a.txt': b'original'}, 5) == original
    for binding, cmd, inputs in [(dict(BINDING, attempt_id='other'), command(), {'a.txt': b'original'}),
                                 (BINDING, command('print(2)'), {'a.txt': b'original'}),
                                 (BINDING, command(), {'a.txt': b'changed'})]:
        with pytest.raises(ValueError, match='conflict'):
            prepare(tmp_path, 'a'*32, binding, cmd, inputs, 5)


def test_invalid_executable_and_deadline(tmp_path):
    with pytest.raises(ValueError, match='executable'):
        prepare(tmp_path, 'a'*32, BINDING, Command('probe', ('python',)), {'a': b'a'}, 1)
    with pytest.raises(ValueError, match='deadline'):
        prepare(tmp_path, 'a'*32, BINDING, command(), {'a': b'a'}, True)


def test_foldx_long_deadline_reaches_immutable_resident_request(tmp_path):
    native=Command('foldx',('/app/foldx_20270131',))
    target=prepare(tmp_path,'a'*32,BINDING,native,{'input.json':b'{}'},14400)
    assert json.loads((target/'request.json').read_bytes())['timeout_seconds']==14400
    assert prepare(tmp_path,'a'*32,BINDING,native,{'input.json':b'{}'},14400)==target
    for value in (14401,True,0):
        with pytest.raises(ValueError,match='deadline'):
            prepare(tmp_path,'b'*32,BINDING,native,{'input.json':b'{}'},value)
    with pytest.raises(ValueError,match='deadline'):
        prepare(tmp_path,'c'*32,BINDING,command(),{'input.json':b'{}'},7201)


def test_blast_long_deadline_reaches_immutable_resident_request(tmp_path):
    native=Command('blast',('/blast/bin/blastp.REAL',))
    target=prepare(tmp_path,'a'*32,BINDING,native,{'input.json':b'{}'},14400)
    assert json.loads((target/'request.json').read_bytes())['timeout_seconds']==14400
    with pytest.raises(ValueError,match='deadline'):
        prepare(tmp_path,'b'*32,BINDING,native,{'input.json':b'{}'},14401)


@pytest.fixture
def linux(tmp_path, monkeypatch):
    if sys.platform != 'linux': pytest.skip('Real Linux process behavior is exercised in container probe')
    from t01_phase1_real.process_control import posix
    monkeypatch.setattr(posix, 'REGISTRY', tmp_path / 'registry')
    return tmp_path / 'executions'


def test_real_process_replay_and_tamper(linux):
    cmd = command("from pathlib import Path; Path('result.txt').write_text('one')")
    target = prepare(linux, 'a'*32, BINDING, cmd, {'a.txt': b'original'}, 5)
    first = run(target, cmd)
    assert first['state'] == 'succeeded' and first['stopped_confirmed']
    assert first['usable_for_pipeline'] is False
    assert run(target, cmd) == first
    (target / 'output/result.txt').write_text('tampered')
    with pytest.raises(ValueError, match='outputs changed'): run(target, cmd)


def test_precancel_and_failure(linux):
    cmd = command('raise SystemExit(7)')
    target = prepare(linux, 'a'*32, BINDING, cmd, {'a': b'a'}, 5)
    cancel(target)
    assert run(target, cmd)['state'] == 'cancelled'
    assert not (target / 'output/stdout.txt').exists()
    target = prepare(linux, 'b'*32, BINDING, cmd, {'a': b'a'}, 5)
    result = run(target, cmd)
    assert result['state'] == 'failed' and result['exit_code'] == 7


def test_timeout_stops_descendant(linux):
    cmd = command("import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']); time.sleep(60)")
    target = prepare(linux, 'a'*32, BINDING, cmd, {'a': b'a'}, 1)
    result = run(target, cmd)
    assert result['state'] == 'timed_out' and result['stopped_confirmed']


def test_missing_process_registry_never_claims_stopped(linux):
    from t01_phase1_real.resident_process import atomic, digest
    cmd = command('raise SystemExit(99)')
    target = prepare(linux, 'a'*32, BINDING, cmd, {'a': b'a'}, 1)
    # Lost registration cannot prove an earlier process never launched.
    atomic(target / 'execution.json', dict(request_sha256=digest((target/'request.json').read_bytes()),
        state='starting', stopped_confirmed=False, outputs={}, binding=BINDING))
    with pytest.raises(RuntimeError, match='stop is unconfirmed'): run(target, cmd)
    assert not (target/'output/stdout.txt').exists()


def test_running_cancel_and_next_task_same_supervisor(linux):
    cmd = command("import time; print('started',flush=True); time.sleep(60)")
    target = prepare(linux, 'a'*32, BINDING, cmd, {'a': b'a'}, 30)
    def trigger():
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            path = target / 'output/stdout.txt'
            if path.exists() and 'started' in path.read_text():
                cancel(target); return
            time.sleep(.02)
    thread = threading.Thread(target=trigger, daemon=True); thread.start()
    result = run(target, cmd); thread.join(timeout=10)
    assert result['state'] == 'cancelled' and result['stopped_confirmed']
    next_cmd = command("print('second task')")
    second = prepare(linux, 'b'*32, dict(BINDING, attempt_id='next'), next_cmd, {'a': b'a'}, 5)
    assert run(second, next_cmd)['state'] == 'succeeded'


def test_real_supervisor_crash_stops_existing_process_without_replay(linux):
    import subprocess
    from t01_phase1_real.process_control import posix
    cmd = command("from pathlib import Path; import time; Path('started').write_text('once'); time.sleep(60)")
    target = prepare(linux, 'a'*32, BINDING, cmd, {'a': b'a'}, 30)
    source = "from t01_phase1_real.resident_process import Command,run; run(%r,Command('probe',%r))" % (str(target), cmd.argv)
    environment = dict(os.environ, T01_PROCESS_REGISTRY=str(posix.REGISTRY))
    process = subprocess.Popen([sys.executable, '-B', '-c', source], env=environment)
    try:
        deadline = time.monotonic()+10
        while not (target/'output/started').exists() and time.monotonic()<deadline:
            assert process.poll() is None
            time.sleep(.02)
        assert (target/'output/started').exists()
        process.kill(); process.wait(timeout=5)
        result = run(target, cmd)
        assert result['state'] == 'interrupted' and result['stopped_confirmed']
        assert (target/'output/started').read_text() == 'once'
        assert run(target, cmd) == result
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=5)


def test_native_freesasa_repeated_in_one_resident_process(linux):
    pytest.importorskip('freesasa')
    source = "import freesasa,json; from pathlib import Path; data=json.loads(Path('{input}/atoms.json').read_text()); a=freesasa.calcCoord(data['coordinates'],data['radii']); Path('sasa.json').write_text(json.dumps({'total':a.totalArea(),'atoms':[a.atomArea(0),a.atomArea(1)]}))"
    cmd = Command('freesasa-probe', (sys.executable, '-B', '-c', source))
    outputs = []
    for eid in ('c'*32, 'd'*32):
        sample = json.dumps(dict(coordinates=[0.,0.,0.,4.,0.,0.], radii=[1.7,1.7])).encode()
        target = prepare(linux, eid, dict(BINDING, attempt_id=eid), cmd, {'atoms.json': sample}, 5)
        result = run(target, cmd)
        assert result['state'] == 'succeeded' and result['stopped_confirmed']
        outputs.append(json.loads((target/'output/sasa.json').read_bytes()))
    assert outputs[0] == outputs[1]
    assert outputs[0]['total'] > 0
    assert abs(sum(outputs[0]['atoms']) - outputs[0]['total']) < 1e-8


def test_worker_registry_rejects_unregistered_or_request_supplied_command(linux):
    from t01_phase1_real.resident_worker import cycle
    registered = command()
    prepare(linux, 'a'*32, BINDING, command('print(123)'), {'a': b'a'}, 5)
    rows = cycle(linux, {'probe': registered})
    assert rows[0]['state'] == 'unconfirmed' and 'command changed' in rows[0]['diagnostic']
    assert not (linux/('a'*32)/'output/stdout.txt').exists()
    assert cycle(linux, {})[0]['state'] == 'unconfirmed'


def test_resident_cli_handles_two_separate_arrivals(linux, tmp_path):
    import subprocess
    from t01_phase1_real.resident_process import encoded
    cmd = command("from pathlib import Path; Path('result.txt').write_text('done')")
    config = tmp_path/'worker.json'
    config.write_bytes(encoded(dict(version='0.1.0', commands=[cmd.document()])))
    process = subprocess.Popen([sys.executable, '-B', '-m', 't01_phase1_real.resident_worker',
                               '--root', str(linux), '--config', str(config)])
    try:
        for eid in ('a'*32, 'b'*32):
            target = prepare(linux, eid, dict(BINDING, attempt_id=eid), cmd, {'a': b'a'}, 5)
            deadline = time.monotonic()+10
            while time.monotonic()<deadline:
                assert process.poll() is None
                state = target/'execution.json'
                if state.exists() and json.loads(state.read_bytes()).get('stopped_confirmed'): break
                time.sleep(.05)
            assert json.loads(state.read_bytes())['state'] == 'succeeded'
            assert (target/'output/result.txt').read_text() == 'done'
        process.terminate(); assert process.wait(timeout=5) == 0
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=5)


def test_offline_guard_is_inherited_by_native_child(linux):
    source = """import socket, subprocess, sys
assert socket.if_nameindex()
socket.socket(socket.AF_UNIX).close()
for family in (socket.AF_INET,socket.AF_INET6):
    try: socket.socket(family)
    except PermissionError: pass
    else: raise AssertionError('Internet socket was allowed')
result=subprocess.run([sys.executable,'-c','import socket; socket.socket()'],capture_output=True)
assert result.returncode != 0 and b'PermissionError' in result.stderr
print('offline child verified')
"""
    cmd = Command('offline-probe', (sys.executable, '-B', '-c', source), (('T01_RESIDENT_OFFLINE','1'),))
    target = prepare(linux, 'e'*32, BINDING, cmd, {'a': b'a'}, 5)
    assert run(target, cmd)['state'] == 'succeeded', (target / 'output/stderr.txt').read_text()
    observation = json.loads((target / 'output/executor-observation.json').read_bytes())
    assert observation['network_restriction'] == 'seccomp-local-sockets-only-v1'
