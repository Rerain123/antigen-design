"""Internal supervisor: durable receipt only after the owned process tree is empty."""
import argparse
import copy
import os
import sys
import time

from .common import REPO, TERMINAL, RuntimeFault, encode, ensure, now, profile, sha
from .files import publish, read_locked, read_verified, within
from .runtime import Runtime
from .winprocess import Job, Process, current_identity


def supervise(root, scope, job_id, test_fault=None):
    runtime = Runtime(root, scope)
    with runtime._tx() as db:
        before = runtime._job(db, job_id)
        ex = runtime._execution(db, job_id)
        if before['state'] in TERMINAL or ex.get('phase') != 'spawn_intent' or ex.get('supervisor'):
            return
        ex['supervisor'] = current_identity()
        ex['phase'] = 'supervising'
        runtime._execution_store(db, job_id, ex)
        if before['state'] == 'reconciling':
            value = copy.deepcopy(before)
            value['state'] = 'stop_requested' if value['stop_reason'] else 'running'
            runtime._store(db, value, before, 'supervisor_attached')
    if test_fault == 'after_registration':
        os._exit(91)  # Bounded internal fault injection, never accepted in a submission.
    job, worker = None, None
    try:
        job = Job(ex['job_object'])
        value = runtime.get(job_id)
        path = runtime.attempt_path(value)
        ensure(value['execution_profile'] == profile(), 'PROFILE_NOT_APPROVED', 'Supervisor code changed')
        read_verified(runtime.root, path+'/input.json', value['request_artifact']['sha256'],
                      value['request_artifact']['size_bytes'], 65536)
        if not value['stop_reason']:
            worker = Process([sys.executable, '-X', 'utf8', str(REPO/'scripts/w1_runtime_worker.py'),
                              '--root', str(runtime.root), '--path', path, '--job-id', job_id,
                              '--attempt-id', value['attempt_id'], '--execution-identity', value['execution_identity']],
                             within(runtime.root, path), job=job)
            with runtime._tx() as db:
                ex = runtime._execution(db, job_id)
                ex['worker'] = worker.identity
                ex['worker_started_at'] = now()
                ex['observed_job_limits'] = job.limits()
                runtime._execution_store(db, job_id, ex)
            worker.resume()
        deadline = time.monotonic()+2.0
        while True:
            value = runtime.get(job_id)
            code = worker.poll() if worker else 1
            if not value['stop_reason'] and code is None and time.monotonic() >= deadline:
                with runtime._tx() as db:
                    value = runtime._stop(db, runtime._job(db, job_id), 'timeout')
            if value['stop_reason'] or code is not None:
                if job.active():
                    job.stop()  # Includes children left behind by a root process that exited.
                if job.active() == 0:
                    break
            time.sleep(.02)
        code = worker.poll() if worker else 1
        receipt = dict(job_id=job_id, attempt_id=value['attempt_id'], execution_identity=value['execution_identity'],
                       exit_code=code, sha256=None, size_bytes=None, tree_active=0, observed_at=now())
        try:
            raw = read_locked(within(runtime.root, path+'/output.json'))
            receipt.update(sha256=sha(raw), size_bytes=len(raw))
        except RuntimeFault:
            pass  # Missing/invalid output is recorded; collection decides the failure state.
        publish(runtime.root, path+'/receipt.json', encode(receipt))
        job.close()
        if test_fault == 'after_receipt':
            os._exit(92)
        with runtime._tx() as db:
            current = runtime._job(db, job_id)
            if current['state'] not in TERMINAL:
                ex = runtime._execution(db, job_id)
                ex.update(tree_stopped=True, phase='finished')
                runtime._execution_store(db, job_id, ex)
                runtime._collect(db, current, ex)
    except (OSError, RuntimeFault, RuntimeError) as exc:
        # If stop cannot be proved, recovery retains reconciling rather than fabricating a terminal state.
        stopped = job is not None and job.handle is not None
        if stopped:
            try:
                job.stop()
                for _ in range(100):
                    if job.active() == 0: break
                    time.sleep(.02)
                stopped = job.active() == 0
            except OSError:
                stopped = False
        if stopped:
            with runtime._tx() as db:
                current = runtime._job(db, job_id)
                if current['state'] not in TERMINAL:
                    ex = runtime._execution(db, job_id)
                    ex.update(tree_stopped=True, supervisor_error=type(exc).__name__)
                    runtime._finish(db, current, ex, error=exc.code if isinstance(exc, RuntimeFault) else 'TOOL_FAILED')
        raise
    finally:
        if worker: worker.close()
        if job: job.close()


def main():
    parser = argparse.ArgumentParser(description='Internal W1 engineering supervisor')
    for name in ['root', 'scope', 'job-id']: parser.add_argument('--'+name, required=True)
    parser.add_argument('--test-fault', choices=['after_registration', 'after_receipt'])
    args = parser.parse_args()
    supervise(args.root, args.scope, args.job_id, args.test_fault)
