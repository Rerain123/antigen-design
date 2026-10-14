"""Linux process-lifecycle probe with synthetic commands and a simulated GPU guard.

No Kubernetes access, network, model execution or actual GPU is used. This proves
parking, fresh-session pickup and process-tree cancellation, not cluster release.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from t01_phase1_real import gpu_on_demand as demand
from t01_phase1_real import unified_gpu_worker as unified
from t01_phase1_real.resident_process import Command, encoded, prepare


def wait_for(predicate, process=None, timeout=15):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError('Synthetic worker exited: ' + process.communicate()[1])
        time.sleep(.02)
    raise RuntimeError('Synthetic process check timed out')


def main():
    if sys.platform != 'linux':
        raise RuntimeError('This probe requires Linux')
    with tempfile.TemporaryDirectory(prefix='t01-gpu-demand-') as temporary:
        base = Path(temporary)
        state = base / 'state'
        state.mkdir()
        registry = base / 'worker.json'
        spool = base / 'queue'
        command = Command('probe', (sys.executable, '-B', '-c',
            "from pathlib import Path; Path('ran.txt').write_text('one execution')"))
        registry.write_bytes(encoded(dict(version='0.1.0', commands=[command.document()])))
        config = base / 'unified.json'
        config.write_bytes(encoded(dict(version='0.2.0', uuid=None,
            state_root=str(state), spools=[dict(root=str(spool), config=str(registry))])))
        def submit(ident, cmd=command, cancelled=False):
            return prepare(spool, ident * 32, dict(job_id=ident, attempt_id='attempt', execution_identity=ident),
                           cmd, {'input.txt': b'synthetic'}, 20, cancel_requested=cancelled)
        def launch(session):
            # Substitution is limited to this probe. Production always runs gpu_guard.
            code = "from t01_phase1_real import gpu_on_demand as d; d.unified.gpu_guard=lambda uuid: {'qualification':'SIMULATED_GPU_GUARD'}; d.main()"
            env = dict(os.environ, T01_GPU_SESSION_ID=session, T01_GPU_POD_UID='synthetic-pod-' + session)
            return subprocess.Popen([sys.executable, '-u', '-B', '-c', code, 'worker', '--config', str(config)],
                                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def stop(process):
            process.terminate()
            process.wait(timeout=10)
            assert process.returncode == 0, process.communicate()
        processes = []
        try:
            first = submit('a')
            worker = launch('1' * 32); processes.append(worker)
            path = demand.session_file(state, '1' * 32)
            wait_for(lambda: path.exists() and unified.read_json(path)[0]['phase'] == 'quiescent', worker)
            first_receipt = (first / 'execution.json').read_bytes()
            first_stat = (first / 'output/ran.txt').stat().st_mtime_ns
            second = submit('b')
            time.sleep(.3)
            assert worker.poll() is None and not (second / 'execution.json').exists()
            stop(worker)
            device_record = unified.read_json(path.with_name(path.stem + '-gpu.json'))[0]
            assert device_record == dict(session='1' * 32, pod_uid='synthetic-pod-' + '1' * 32,
                                         device={'qualification': 'SIMULATED_GPU_GUARD'})
            worker2 = launch('2' * 32); processes.append(worker2)
            path2 = demand.session_file(state, '2' * 32)
            wait_for(lambda: path2.exists() and unified.read_json(path2)[0]['phase'] == 'quiescent', worker2)
            assert unified.read_json(second / 'execution.json')[0]['state'] == 'succeeded'
            assert (first / 'execution.json').read_bytes() == first_receipt
            assert (first / 'output/ran.txt').stat().st_mtime_ns == first_stat
            stop(worker2)

            # With no worker alive, acknowledge cancellation entirely on the CPU.
            os.environ['T01_PROCESS_REGISTRY'] = str(state / '.processes')
            cancelled = submit('c', cancelled=True)
            roots = {spool: {'probe': command}}
            demand.cancel_unstarted(roots, unified.pending(roots))
            assert unified.read_json(cancelled / 'execution.json')[0]['state'] == 'cancelled'
            assert not (cancelled / 'output/ran.txt').exists()

            # SIGTERM while running must stop the real child and its descendant.
            long = Command('probe', (sys.executable, '-B', '-c',
                "import subprocess,sys,time; from pathlib import Path; child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); Path('started').write_text(str(child.pid)); time.sleep(60)"))
            registry.write_bytes(encoded(dict(version='0.1.0', commands=[long.document()])))
            running = submit('d', long)
            worker3 = launch('3' * 32); processes.append(worker3)
            wait_for(lambda: (running / 'output/started').exists(), worker3)
            child_pid = int((running / 'output/started').read_text())
            stop(worker3)
            receipt = unified.read_json(running / 'execution.json')[0]
            assert receipt['state'] == 'cancelled' and receipt['stopped_confirmed'] is True
            # A container PID 1 may leave a dead orphan as a zombie until reaping.
            # This has no executing process or device handles; inspect state,
            # rather than treating existence of a /proc entry as continued work.
            child_status = Path('/proc/' + str(child_pid) + '/stat')
            try:
                child_state = child_status.read_text().rsplit(')', 1)[1].split()[0]
            except FileNotFoundError:
                child_state = 'ABSENT'
            assert child_state in {'ABSENT', 'Z'}, child_state
            print(json.dumps(dict(status='PASS', qualification='LOCAL_LINUX_SYNTHETIC_LIFECYCLE',
                checks=['quiescent_worker_parks', 'late_arrival_waits_for_new_session',
                        'previous_execution_not_replayed', 'prestart_cancel_without_gpu',
                        'sigterm_stops_real_process_tree', 'hardware_record_survives_worker_exit',
                        'scheduler_selected_config_loaded'],
                stopped_descendant_state=child_state,
                actual_gpu_used=False, kubernetes_operations=0, scientific_model_executions=0)))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=5)


if __name__ == '__main__':
    main()
