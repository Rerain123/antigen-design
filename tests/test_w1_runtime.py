"""W1-09A: real harmless Windows processes, independent lifecycle and filesystem assertions."""
from concurrent.futures import ThreadPoolExecutor
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from t01_phase1_real.common import REPO, TOOL, RuntimeFault, decode, encode, profile, sha
from t01_phase1_real.files import publish, read_locked, within
from t01_phase1_real.runtime import Runtime

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Local executor qualified on Windows')
spec = importlib.util.spec_from_file_location('runtime_design_checker', REPO/'scripts/check_w1_contract.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def rt(tmp_path):
    runtime = Runtime(tmp_path/'runtime')
    yield runtime
    # Stop only this fixture's registered executions; no process-name or unrelated PID kill.
    from t01_phase1_real.winprocess import inspect_job
    with runtime._db() as db:
        executions = [decode(r[0]) for r in db.execute('SELECT data FROM executions')]
    for ex in executions:
        inspect_job(ex['job_object'], stop=True)


def request(rt, mode='echo', delay=0, key='submit-1', run=None):
    run = run or rt.create_run('run-1')['run_id']
    ref = rt.stage_request(run, encode(dict(mode=mode, payload='工程 fixture', delay_seconds=delay)))
    return dict(contract_version='0.1.0', run_id=run, request_id='request-1', idempotency_key=key,
                tool_id=TOOL, node_id=None, run_mode='engineering_example', request_artifact=ref,
                execution_profile=profile(), rule_profile=None)


def submit(rt, **kwargs): return rt.submit(encode(request(rt, **kwargs)))


def control(rt, op, job, key='control-1'):
    return rt.control(encode(dict(contract_version='0.1.0', operation=op, job_id=job['job_id'], idempotency_key=key)))


def until(predicate, timeout=8):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result: return result
        time.sleep(.025)
    raise AssertionError('Expected observable process/file condition did not arrive')


def start(rt, job):
    rt.dispatch(job['job_id'])
    value = rt.get(job['job_id'])
    until(lambda: within(rt.root, rt.attempt_path(value)+'/worker-started.json').exists())
    return rt.get(job['job_id'])


def verify(rt, value):
    checker.validate_job(value)
    assert value['usable_for_pipeline'] is False
    assert value['scientific_disposition'] in ('pending', 'not_evaluated')
    assert value['evidence_kind'] == 'ENGINEERING_FIXTURE'
    events = rt.events(value['job_id'])
    assert [e['snapshot']['revision'] for e in events] == list(range(len(events)))
    for e in events: checker.validate_job(e['snapshot'])
    for a, b in zip(events, events[1:]): checker.validate_transition(a['snapshot'], b['snapshot'])


def test_rt01_concurrent_submit_claim_exact_bytes(rt):
    raw = encode(request(rt))
    with ThreadPoolExecutor(4) as pool:
        values = list(pool.map(lambda _: Runtime(rt.root).submit(raw), range(8)))
    assert len({v['job_id'] for v in values}) == 1
    with pytest.raises(RuntimeFault, match='different bytes'): rt.submit(raw+b' ')
    job = values[0]
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: Runtime(rt.root).dispatch(job['job_id']), range(4)))
    final = rt.wait(job['job_id'])
    assert final['state'] == 'succeeded'
    assert sum(e['event']=='claimed' for e in rt.events(job['job_id'])) == 1
    assert Runtime(rt.root).submit(raw)['job_id'] == job['job_id']
    verify(rt, final)


def test_rt02_actual_admission_crash_and_committed_restart(rt, tmp_path):
    raw = encode(request(rt))
    input_path = tmp_path/'submit.json'; input_path.write_bytes(raw)
    program = '''import os,sys
sys.path.insert(0,sys.argv[1])
from t01_phase1_real.runtime import Runtime
r=Runtime(sys.argv[2])
r._fault=lambda name: os._exit(83) if name=='admission_before_commit' else None
r.submit(open(sys.argv[3],'rb').read())
'''
    result = subprocess.run([sys.executable, '-c', program, str(REPO/'src'), str(rt.root), str(input_path)],
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
    assert result.returncode == 83
    with rt._db() as db:
        assert db.execute('SELECT count(*) FROM jobs').fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM idempotency WHERE operation='submit'").fetchone()[0] == 0
    job = rt.submit(raw)
    assert Runtime(rt.root).submit(raw) == job
    assert Runtime(rt.root).get(job['job_id']) == job


@pytest.mark.parametrize('point,expected', [('after_claim','failed'), ('before_spawn','reconciling')])
def test_rt03_claim_launch_gap(rt, point, expected):
    job = submit(rt)
    def crash(name):
        if name == point: raise SystemExit(84)
    rt._fault = crash
    with pytest.raises(SystemExit): rt.dispatch(job['job_id'])
    rt._fault = None
    result = Runtime(rt.root).recover(job['job_id'])
    assert result['state'] == expected
    assert rt.dispatch(job['job_id'])['attempt_id'] == result['attempt_id']
    if expected == 'reconciling':
        with pytest.raises(RuntimeFault): control(rt, 'retry', result)
    else: assert result['error_code'] == 'INTERRUPTED'
    verify(rt, result)


def test_rt03_actual_spawn_before_dispatch_return(rt):
    job = submit(rt, mode='sleep', delay=.8)
    program = '''import os,sys
sys.path.insert(0,sys.argv[1])
from t01_phase1_real.runtime import Runtime
r=Runtime(sys.argv[2])
r._fault=lambda name: os._exit(85) if name=='after_spawn' else None
r.dispatch(sys.argv[3])
'''
    process=subprocess.run([sys.executable,'-c',program,str(REPO/'src'),str(rt.root),job['job_id']],
                           creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
    assert process.returncode==85
    final = Runtime(rt.root).wait(job['job_id'])
    assert final['state'] == 'succeeded'
    assert sum(e['event']=='claimed' for e in rt.events(job['job_id'])) == 1
    verify(rt, final)


def test_rt04_queued_cancel_and_claim_race(rt):
    queued = submit(rt)
    cancelled = control(rt, 'cancel', queued)
    assert rt.dispatch(queued['job_id']) == cancelled
    assert cancelled['attempt_id'] is None
    other = submit(rt, key='submit-2', mode='sleep', delay=.5)
    with ThreadPoolExecutor(2) as pool:
        a=pool.submit(rt.dispatch, other['job_id'])
        b=pool.submit(control, rt, 'cancel', other, 'cancel-2')
        a.result(); b.result()
    final = rt.wait(other['job_id'])
    assert final['state']=='cancelled' and final['stop_confirmed']
    verify(rt, final)


def test_rt05_cancel_descendants_leaves_unrelated_process(rt):
    from t01_phase1_real.winprocess import alive, inspect_job
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(20)'], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        job = start(rt, submit(rt, mode='tree', delay=10))
        child_path = within(rt.root, rt.attempt_path(job)+'/child.json')
        until(child_path.exists)
        child = decode(read_locked(child_path))
        worker = rt.execution(job['job_id'])['worker']
        limits = rt.execution(job['job_id'])['observed_job_limits']
        assert limits['active_limit']==4 and limits['job_memory']==256*1024**2
        assert limits['flags'] & 0x2000  # OS-reported kill-on-close limit.
        assert alive(child) is True and alive(worker) is True
        pending = control(rt, 'cancel', job)
        assert pending['state']=='stop_requested' and not pending['stop_confirmed']
        final = rt.wait(job['job_id'])
        assert final['state']=='cancelled' and final['stop_confirmed']
        assert alive(child) is False and alive(worker) is False
        assert inspect_job(rt.execution(job['job_id'])['job_object']) == 0
        assert unrelated.poll() is None
        verify(rt, final)
    finally:
        unrelated.terminate(); unrelated.wait(timeout=5)


def test_rt06_late_output_stop_wins_and_success_immutable(rt):
    rt._supervisor_fault = 'after_receipt'
    job = submit(rt)
    rt.dispatch(job['job_id'])
    current = rt.get(job['job_id'])
    until(lambda: within(rt.root, rt.attempt_path(current)+'/receipt.json').exists())
    control(rt, 'cancel', current)
    final = rt.wait(job['job_id'])
    assert final['state']=='cancelled' and not any(a['role']=='result' for a in final['artifacts'])
    rt._supervisor_fault = None
    second = submit(rt, key='submit-2')
    rt.dispatch(second['job_id']); success=rt.wait(second['job_id'])
    assert success['state']=='succeeded'
    assert control(rt, 'cancel', success, 'cancel-2') == success
    assert rt.recover(success['job_id']) == success
    verify(rt, final); verify(rt, success)


def test_rt07_timeout_stops_actual_descendants(rt):
    from t01_phase1_real.winprocess import alive
    job = start(rt, submit(rt, mode='tree', delay=10))
    child_path=within(rt.root, rt.attempt_path(job)+'/child.json')
    until(child_path.exists)
    child=decode(read_locked(child_path))
    final=rt.wait(job['job_id'])
    assert final['state']=='timed_out' and final['error_code']=='TIMEOUT' and final['stop_confirmed']
    assert alive(child) is False and alive(rt.execution(job['job_id'])['worker']) is False
    verify(rt, final)


def test_rt08_restart_adopts_identity_fences_callback(rt):
    job=start(rt, submit(rt, mode='sleep', delay=1))
    new=Runtime(rt.root).recover(job['job_id'])
    assert new['execution_identity']==job['execution_identity'] and new['attempt_id']==job['attempt_id']
    assert new['lease_epoch']>job['lease_epoch']
    with pytest.raises(RuntimeFault) as exc: rt.accept_callback(job['job_id'], job['attempt_id'], job['lease_epoch'])
    assert exc.value.code=='STALE_LEASE'
    final=rt.wait(job['job_id'])
    assert final['state']=='succeeded'
    verify(rt, final)


@pytest.mark.parametrize('point,expected', [('after_receipt','succeeded'), ('after_registration','failed')])
def test_rt09_actual_supervisor_crash_recovery(rt, point, expected):
    rt._supervisor_fault=point
    job=submit(rt); rt.dispatch(job['job_id'])
    final=Runtime(rt.root).wait(job['job_id'])
    assert final['state']==expected
    if expected=='succeeded':
        result=decode(rt.artifact_bytes(final['job_id'], final['artifacts'][0]['artifact_id']))
        assert result['attempt_id']==final['attempt_id']
    else: assert final['error_code']=='INTERRUPTED'
    verify(rt, final)


def test_rt10_unreachable_execution_never_relaunches(rt, monkeypatch):
    import t01_phase1_real.winprocess as win
    job=start(rt, submit(rt, mode='sleep', delay=1))
    with monkeypatch.context() as m:
        m.setattr(win, 'alive', lambda identity: None)
        unknown=rt.recover(job['job_id'])
        assert unknown['state']=='reconciling'
        assert rt.dispatch(job['job_id'])==unknown
        with pytest.raises(RuntimeFault): control(rt, 'retry', unknown)
    assert rt.wait(job['job_id'])['state']=='succeeded'


def test_rt11_retry_lineage_and_input_tamper(rt):
    job=submit(rt, mode='fail'); rt.dispatch(job['job_id']); failed=rt.wait(job['job_id'])
    assert failed['state']=='failed' and failed['exit_code']==7
    retried=control(rt, 'retry', failed)
    assert retried['job_id']!=failed['job_id'] and retried['retry_of_job_id']==failed['job_id']
    assert retried['request_artifact']==failed['request_artifact'] and retried['execution_profile']==failed['execution_profile']
    assert control(rt, 'retry', failed)==retried
    rt.dispatch(retried['job_id']); final=rt.wait(retried['job_id'])
    assert final['attempt_id']!=failed['attempt_id']
    with rt._db() as db:
        relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(failed['request_artifact']['artifact_id'],)).fetchone()[0]
    within(rt.root, relative).write_bytes(b'changed bytes')
    with pytest.raises(RuntimeFault) as exc: control(rt, 'retry', final, 'retry-tampered')
    assert exc.value.code=='HASH_MISMATCH'
    verify(rt, final)


def test_rt12_cross_run_scope_and_hash(rt):
    body=request(rt)
    other=rt.create_run('run-2')['run_id']
    foreign=copy.deepcopy(body); foreign['run_id']=other
    with pytest.raises(RuntimeFault): rt.submit(encode(foreign))
    job=rt.submit(encode(body))
    outsider=Runtime(rt.root, scope='different-owner')
    with pytest.raises(RuntimeFault): outsider.get(job['job_id'])
    with pytest.raises(RuntimeFault): outsider.submit(encode(body))
    ref=body['request_artifact']
    with rt._db() as db: relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    within(rt.root, relative).write_bytes(b'changed')
    final=rt.dispatch(job['job_id'])
    assert final['state']=='failed' and final['error_code']=='HASH_MISMATCH' and final['attempt_id'] is None


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'C:/outside', 'a\\b', 'a/../b', 'a//b', 'a/stream:ads'])
def test_rt12_path_escape(rt, path):
    with pytest.raises(RuntimeFault): within(rt.root, path)


def test_rt12_junction_escape_and_locked_snapshot(rt, tmp_path):
    from t01_phase1_real.winprocess import locked_file
    target=tmp_path/'outside'; target.mkdir()
    junction=rt.root/'junction'
    # Native PowerShell creates a directory junction without symlink privilege.
    command="New-Item -ItemType Junction -Path '"+str(junction).replace("'","''")+"' -Target '"+str(target).replace("'","''")+"' | Out-Null"
    subprocess.run(['powershell', '-NoProfile', '-Command', command], check=True, capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    with pytest.raises(RuntimeFault): within(rt.root, 'junction/escaped.json')
    sample=publish(rt.root, 'locked.json', b'original')
    with locked_file(sample) as stream:
        with pytest.raises(PermissionError): sample.write_bytes(b'tamper')
        assert stream.read()==b'original'


@pytest.mark.parametrize('tool', ['t01.real.ingest_structure','t01.real.map_structure','t01.real.deeptmhmm',
                                't01.real.assess_structure_quality','t01.real.freesasa','t01.real.af3','t01.real.esmfold2'])
def test_rt13_all_scientific_tools_closed(rt, tool):
    body=request(rt); body.update(tool_id=tool, node_id='N01', run_mode='g0_probe')
    with pytest.raises(RuntimeFault) as exc: rt.submit(encode(body))
    assert exc.value.code=='PROFILE_NOT_APPROVED'
    with rt._db() as db: assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==0


@pytest.mark.parametrize('mode', ['partial','wrong_identity'])
def test_rt14_malformed_outputs_not_published(rt, mode):
    job=submit(rt, mode=mode); rt.dispatch(job['job_id']); final=rt.wait(job['job_id'])
    assert final['state']=='failed' and final['error_code']=='OUTPUT_INVALID' and final['artifacts']==[]
    verify(rt, final)


def test_rt14_published_artifact_tamper_and_no_overwrite(rt):
    job=submit(rt); rt.dispatch(job['job_id']); final=rt.wait(job['job_id'])
    aid=final['artifacts'][0]['artifact_id']
    assert decode(rt.artifact_bytes(job['job_id'], aid))['job_id']==job['job_id']
    with rt._db() as db: relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(aid,)).fetchone()[0]
    with pytest.raises(FileExistsError): publish(rt.root, relative, b'overwrite')
    within(rt.root, relative).write_bytes(b'tampered')
    with pytest.raises(RuntimeFault) as exc: rt.artifact_bytes(job['job_id'], aid)
    assert exc.value.code=='HASH_MISMATCH'


@pytest.mark.parametrize('directory', ['legacy','src','docs','dify','discovery','工作流设计','工具部署','var/t01-phase1-mock-v0.1'])
def test_rt15_protected_roots(directory):
    with pytest.raises(RuntimeFault): Runtime(REPO/directory/'not-created-by-runtime')


def test_rt15_namespace_source_and_promotion(rt):
    body=request(rt); body['run_mode']='pipeline'
    with pytest.raises(RuntimeFault): rt.submit(encode(body))
    body['run_mode']='engineering_example'; body['request_id']='t01-phase1-mock-run-1'
    with pytest.raises(RuntimeFault): rt.submit(encode(body))
    import ast
    for source in (REPO/'src/t01_phase1_real').glob('*.py'):
        for node in ast.walk(ast.parse(source.read_text(encoding='utf-8'))):
            imports=[a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
            assert not any('mock' in name or name.startswith('legacy') for name in imports)


def test_concurrent_first_initialization(tmp_path):
    root=tmp_path/'new-runtime'
    with ThreadPoolExecutor(4) as pool:
        runs=list(pool.map(lambda _: Runtime(root).create_run('first'), range(4)))
    assert len({r['run_id'] for r in runs})==1


def test_hardlink_input_rejected(rt, tmp_path):
    source=tmp_path/'original'; source.write_bytes(b'bytes')
    linked=rt.root/'linked'; os.link(source,linked)
    with pytest.raises(RuntimeFault): read_locked(linked)


def test_supervisor_crash_while_descendant_live(rt):
    from t01_phase1_real import winprocess as win
    job=start(rt,submit(rt,mode='tree',delay=10))
    child_path=within(rt.root,rt.attempt_path(job)+'/child.json')
    until(child_path.exists)
    child=decode(read_locked(child_path))
    owned=rt.execution(job['job_id'])['supervisor']
    handle=win.ok(win.OpenProcess(0x1000|0x100000|1,False,owned['pid']))
    try:
        assert win.birth(handle)==owned['birth']
        win.ok(win.TerminateProcess(handle,93))
        assert win.Wait(handle,5000)==0
    finally: win.Close(handle)
    final=rt.wait(job['job_id'])
    assert final['state']=='failed' and final['error_code']=='INTERRUPTED'
    assert win.alive(child) is False
    verify(rt,final)


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"n":NaN}', b'{"n":1e999}', b'\xff', '{}'.encode('utf-16')])
def test_strict_json_rejects_invalid_bytes(raw):
    with pytest.raises(RuntimeFault): decode(raw)


def test_unknown_commands_profile_and_future_database(rt):
    body=request(rt); body['command']='whoami'
    with pytest.raises(RuntimeFault): rt.submit(encode(body))
    body.pop('command'); body['execution_profile']['sha256']='0'*64
    with pytest.raises(RuntimeFault): rt.submit(encode(body))
    with rt._db() as db: db.execute('PRAGMA user_version=99')
    with pytest.raises(RuntimeFault) as exc: Runtime(rt.root)
    assert exc.value.code=='UNSUPPORTED_VERSION'
