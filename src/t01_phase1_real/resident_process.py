"""Owned Linux processes for a resident worker; no Kubernetes or Docker API.

This execution primitive is not a science adapter or another business task store.
The caller supplies a server-owned Command and the original task binding. Receipts
record processes and bytes only; the existing tool parsers decide result validity.
Run this supervisor with Python 3.11; Command.argv may select another interpreter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import time
from dataclasses import dataclass

DEFAULT_FILE_SIZE_BYTES = 32 * 1024 ** 2
MAX_FILE_SIZE_BYTES = 2 * 1024 ** 3


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic(path, value):
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('wb') as stream:
        stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    if os.name == 'posix':
        fd = os.open(str(path.parent), os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)


def safe_path(root, relative):
    if not isinstance(relative, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', relative):
        raise ValueError('Expected a relative artifact name')
    parts = relative.split('/')
    if any(p in ('.', '..') for p in parts): raise ValueError('Artifact traversal')
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink(): raise ValueError('Artifact symlink')
    return path


@dataclass(frozen=True)
class Command:
    """Trusted startup configuration, never constructed from an MCP request."""
    tool: str
    argv: tuple[str, ...]
    environment: tuple[tuple[str, str], ...] = ()
    memory_bytes: int = 1024 ** 3
    file_size_bytes: int = DEFAULT_FILE_SIZE_BYTES

    def document(self):
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', self.tool): raise ValueError('Invalid tool')
        if not self.argv or not (Path(self.argv[0]).is_absolute() or PurePosixPath(self.argv[0]).is_absolute()): raise ValueError('Absolute executable required')
        if not all(isinstance(a, str) and '\0' not in a for a in self.argv): raise ValueError('Invalid argv')
        if type(self.memory_bytes) is not int or self.memory_bytes < 64 * 1024 ** 2: raise ValueError('Invalid memory bound')
        if type(self.file_size_bytes) is not int or not DEFAULT_FILE_SIZE_BYTES <= self.file_size_bytes <= MAX_FILE_SIZE_BYTES:
            raise ValueError('Invalid file size bound')
        env = dict(self.environment)
        if len(env) != len(self.environment) or any(not re.fullmatch(r'[A-Z_][A-Z0-9_]*', k) or not isinstance(v, str) or '\0' in v for k, v in env.items()):
            raise ValueError('Invalid fixed environment')
        result = dict(tool=self.tool, argv=list(self.argv), environment=env,
                      memory_bytes=self.memory_bytes)
        # The original resident workers predate the optional file-size bound
        # and serialize their default command with four fields.  Keep that
        # wire representation for the default while retaining an explicit
        # bound for AF3 and any other command that needs a larger limit.
        if self.file_size_bytes != DEFAULT_FILE_SIZE_BYTES:
            result['file_size_bytes'] = self.file_size_bytes
        return result


def canonical_command_document(value):
    """Return the comparison form for old/new resident command documents."""
    if isinstance(value, Command):
        value = value.document()
    if not isinstance(value, dict):
        return value
    result = dict(value)
    result.setdefault('file_size_bytes', DEFAULT_FILE_SIZE_BYTES)
    return result


def command_documents_equal(expected, actual):
    """Compare command documents across the optional-default transition."""
    return canonical_command_document(expected) == canonical_command_document(actual)


def prepare(root, execution_id, binding, command, inputs, timeout_seconds, *, cancel_requested=False):
    """Create one immutable execution input. Existing IDs can only replay bytes."""
    if not re.fullmatch(r'[a-f0-9]{32}', execution_id): raise ValueError('Expected opaque execution ID')
    maximum = 14400 if command.tool in ('blast', 'foldx') else 7200
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= maximum: raise ValueError('Invalid deadline')
    if not isinstance(binding, dict) or set(binding) != {'job_id', 'attempt_id', 'execution_identity'} or not all(isinstance(v, str) and v for v in binding.values()):
        raise ValueError('Original task/attempt binding required')
    if not isinstance(inputs, dict) or not inputs or len(inputs) > 128 or not all(isinstance(v, bytes) for v in inputs.values()):
        raise ValueError('Bounded input bytes required')
    if sum(map(len, inputs.values())) > 128 * 1024 ** 2: raise ValueError('Input too large')
    root = Path(root).absolute()
    if root.is_symlink(): raise ValueError('Worker root symlink')
    root.mkdir(parents=True, exist_ok=True)
    target = safe_path(root, execution_id)
    manifest = dict(version='0.1.0', execution_id=execution_id, binding=binding,
                    command=command.document(), timeout_seconds=timeout_seconds,
                    inputs={name: dict(sha256=digest(raw), size_bytes=len(raw)) for name, raw in sorted(inputs.items())})
    for name in inputs: safe_path(target / 'input', name)
    if target.exists():
        if (target / 'request.json').exists():
            if (target / 'request.json').read_bytes() != encoded(manifest): raise ValueError('Execution ID conflict')
            verify_inputs(target, manifest)
            if cancel_requested: cancel(target)
            return target
        if (target / 'execution.json').exists(): raise ValueError('Uncommitted input already executing')
    else:
        target.mkdir()
    (target / 'input').mkdir(exist_ok=True); (target / 'output').mkdir(exist_ok=True)
    for path in (target / 'input').rglob('*'):
        if path.is_symlink(): raise ValueError('Partial input symlink')
        if path.is_file() and path.relative_to(target / 'input').as_posix() not in inputs:
            raise ValueError('Unexpected partial input')
    for name, raw in inputs.items():
        path = safe_path(target / 'input', name); path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != raw: raise ValueError('Partial input differs')
            continue
        with path.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        path.chmod(0o400)
    if cancel_requested: cancel(target)
    atomic(target / 'request.json', manifest)
    return target


def verify_inputs(target, request):
    for name, info in request['inputs'].items():
        path = safe_path(target / 'input', name)
        if path.stat().st_size != info['size_bytes'] or digest(path.read_bytes()) != info['sha256']:
            raise ValueError('Input changed: ' + name)


def cancel(target):
    """The owning controller signals cancellation without selecting any PID."""
    target = Path(target)
    with (target / 'cancel').open('ab'): pass


def inventory(target):
    result = {}; total = 0
    for path in sorted((target / 'output').rglob('*')):
        if path.is_symlink(): raise ValueError('Output symlink')
        if not path.is_file(): continue
        size = path.stat().st_size; total += size
        if total > 128 * 1024 ** 2 or len(result) >= 128: raise ValueError('Output exceeds worker bound')
        result[path.relative_to(target).as_posix()] = dict(size_bytes=size, sha256=digest(path.read_bytes()))
    return result


def stop_recorded(posix, target, process_name):
    """A missing registry is lost evidence, not evidence of stopped processes."""
    state = json.loads((target / 'execution.json').read_bytes())
    if state['stopped_confirmed']: return True
    try:
        owned = posix.Job(process_name, create=False)
        record = owned._record()
        owned.close()
    except (OSError, ValueError):
        return False
    if state.get('process_identity') and record['leader'] != state['process_identity']: return False
    return posix.inspect_job(process_name, stop=True) == 0


def run(target, command, stopping=lambda: False):
    """Execute once under a shared worker slot; replay receipts, never tool work.

    A separate server/dispatcher must call this from its dedicated process worker.
    The same root serializes all tools (including GPU work). An uncertain old
    process blocks this slot instead of allowing overlapping executions.
    """
    if sys.platform != 'linux': raise RuntimeError('Resident supervisor requires Linux')
    from .process_control import posix
    target = Path(target).absolute(); root = target.parent
    if target.is_symlink(): raise ValueError('Execution symlink')
    raw = (target / 'request.json').read_bytes(); request = json.loads(raw)
    if not command_documents_equal(command, request['command']):
        raise ValueError('Registered command changed')
    if request['execution_id'] != target.name: raise ValueError('Execution directory mismatch')
    fingerprint = digest(raw)
    slot = 'resident:' + digest(str(root).encode())
    process_name = slot + ':' + target.name
    state_path = target / 'execution.json'
    active_path = root / '.active.json'
    with posix.initialization_lock(slot):
        verify_inputs(target, request)
        if active_path.exists():
            active = json.loads(active_path.read_bytes())
            if active['execution_id'] != target.name:
                previous_target = safe_path(root, active['execution_id'])
                expected = slot + ':' + previous_target.name
                if active['process_name'] != expected or not stop_recorded(posix, previous_target, expected):
                    raise RuntimeError('Previous worker process stop is unconfirmed')
        if state_path.exists():
            previous = json.loads(state_path.read_bytes())
            if previous['request_sha256'] != fingerprint: raise ValueError('Execution receipt binding changed')
            if previous['stopped_confirmed']:
                if previous['outputs'] != inventory(target): raise ValueError('Published outputs changed')
                return previous
            if not stop_recorded(posix, target, process_name):
                raise RuntimeError('Interrupted execution stop is unconfirmed')
            previous.update(state='interrupted', stopped_confirmed=True, outputs=inventory(target))
            atomic(state_path, previous)
            return previous
        state = dict(version='0.1.0', backend='resident-process', binding=request['binding'],
                     execution_id=target.name, request_sha256=fingerprint, process_name=process_name,
                     state='starting', stopped_confirmed=False, exit_code=None, outputs={},
                     scientific_signoff=None, usable_for_pipeline=False)
        if (target / 'cancel').exists() or stopping():
            state.update(state='cancelled', stopped_confirmed=True)
            atomic(state_path, state)
            return state
        atomic(active_path, dict(execution_id=target.name, process_name=process_name))
        atomic(state_path, state)
        owned = posix.Job(process_name, memory_bytes=command.memory_bytes)
        child = None
        try:
            argv = [sys.executable, '-B', str(Path(__file__).absolute()), '--child', str(target), '--expected-sha256', fingerprint]
            child = posix.Process(argv, root, job=owned)
            state.update(state='running', process_identity=child.identity)
            atomic(state_path, state)
            child.resume()
            start = time.monotonic(); reason = None
            while child.poll() is None:
                if (target / 'cancel').exists() or stopping(): reason = 'cancelled'
                elif time.monotonic() - start >= request['timeout_seconds']: reason = 'timed_out'
                if reason:
                    owned.stop(); break
                time.sleep(0.02)
            # A completed leader alone does not prove all its children stopped.
            deadline = time.monotonic() + 5
            while owned.active() and time.monotonic() < deadline: time.sleep(0.02)
            if owned.active(): raise RuntimeError('Tool descendants have not stopped')
            code = child.poll()
            verify_inputs(target, request)
            state.update(state=reason or ('succeeded' if code == 0 else 'failed'), exit_code=code,
                         stopped_confirmed=True, outputs=inventory(target))
            atomic(state_path, state)
            return state
        except BaseException:
            # Receipt stays nonterminal if process ownership cannot be resolved.
            if child is not None:
                posix.inspect_job(process_name, stop=True)
                child.poll()
            raise
        finally:
            owned.close()
            if child is not None: child.close()


def child_main(target, expected_sha256):
    """Runs inside the already registered process group, before exec."""
    import resource
    target = Path(target); raw = (target / 'request.json').read_bytes()
    if digest(raw) != expected_sha256: raise ValueError('Execution request changed before launch')
    request = json.loads(raw)
    verify_inputs(target, request)
    command = request['command']
    # Requests created by older service/worker revisions omit the default.
    file_size_bytes = command.get('file_size_bytes', DEFAULT_FILE_SIZE_BYTES)
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_size_bytes, file_size_bytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    environment = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
                   'HOME': '/tmp', 'TMPDIR': '/tmp', 'PYTHONDONTWRITEBYTECODE': '1'}
    environment.update(command['environment'])
    def expand(value):
        return (value.replace('{input}', str(target / 'input')).replace('{output}', str(target / 'output'))
                .replace('{job_id}', request['binding']['job_id']))
    argv = [expand(a) for a in command['argv']]
    environment = {k: expand(v) for k, v in environment.items()}
    # One shared-volume advisory lock across GPU worker containers. The child
    # waits under the existing supervisor deadline/cancellation process group.
    # Keep the descriptor across exec; process death releases the kernel lock.
    if environment.get('T01_SHARED_GPU_LOCK'):
        import fcntl
        lock_path = Path(environment['T01_SHARED_GPU_LOCK'])
        if not lock_path.is_absolute(): raise ValueError('Absolute shared GPU lock required')
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        os.set_inheritable(lock_fd, True)
    for number, name in ((1, 'stdout.txt'), (2, 'stderr.txt')):
        fd = os.open(str(target / 'output' / name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.dup2(fd, number); os.close(fd)
    if 'T01_RESIDENT_SLOT' in environment:
        slot = Path(environment['T01_RESIDENT_SLOT'])
        if not slot.is_absolute() or slot.is_symlink(): raise ValueError('Invalid fixed native slot')
        slot.mkdir(parents=True, exist_ok=True)
        # The root lock already excludes another execution in this worker.
        # Image-owned aliases (/out, /input.json, /native) point into current.
        # Most resident tools expect the native output directory to exist.  A
        # few native CLIs (notably ESMFold2) deliberately create it with
        # exist_ok=False, so the fixed command may opt out and retain that
        # tool-level invariant.
        if environment.get('T01_PRECREATE_NATIVE', '1') == '1':
            (target / 'output' / 'native').mkdir()
        (target / 'work').mkdir()
        if environment.get('T01_PRIVATE_TMP') == '1':
            temporary_root = target / 'work/tmp'
            temporary_root.mkdir()
            temporary_link = slot / 'tmp.pending'
            temporary_link.symlink_to(temporary_root, target_is_directory=True)
            os.replace(temporary_link, slot / 'tmp')
        pending = slot / 'current.pending'
        pending.symlink_to(target, target_is_directory=True)
        os.replace(pending, slot / 'current')
        package = environment.get('T01_NATIVE_PACKAGE')
        if package:
            original = Path(package)
            if not original.is_absolute() or not original.is_dir(): raise ValueError('Native package missing')
            selected = original
            if environment.get('T01_THERMOMPNN_LAYOUT') == '1':
                selected = target / 'work' / 'app'
                selected.mkdir()
                # The official CLI resolves __file__ before locating local.yaml.
                # Copy Python sources byte-for-byte so realpath stays inside the
                # private task view; large immutable weights remain linked.
                import shutil
                for item in sorted(original.rglob('*')):
                    relative=item.relative_to(original)
                    if relative.as_posix()=='local.yaml':continue
                    destination=selected/relative
                    if item.is_dir():destination.mkdir()
                    elif item.suffix=='.py':shutil.copyfile(item,destination)
                    else:destination.symlink_to(item)
                (selected / 'local.yaml').symlink_to(target / 'input/native/runtime-local.yaml')
            for name, destination in (('package', selected), ('upstream', original)):
                temporary = slot / (name + '.pending')
                temporary.symlink_to(destination, target_is_directory=True)
                os.replace(temporary, slot / name)
        if environment.get('T01_DATABASE_ROOT'):
            body = json.loads((target / 'input/input.json').read_bytes())
            database_id = body.get('database_id')
            if not isinstance(database_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', database_id):
                raise ValueError('Registered database ID required')
            database = safe_path(Path(environment['T01_DATABASE_ROOT']), database_id)
            if not database.is_dir(): raise ValueError('Registered database missing')
            temporary = slot / 'database.pending'
            temporary.symlink_to(database, target_is_directory=True)
            os.replace(temporary, slot / 'database')
    # Take the actual namespace/CPU observation before restricting sockets;
    # interface enumeration can itself use a non-INET socket on some libc builds.
    import socket
    import platform
    observation = dict(network_interfaces=socket.if_nameindex(), cpu_affinity=sorted(os.sched_getaffinity(0)),
                       machine=platform.machine(), source_image_id=environment.get('T01_SOURCE_IMAGE_ID'))
    if environment.get('T01_RESIDENT_OFFLINE') == '1':
        sys.path.insert(0, str(Path(__file__).parent))
        from resident_offline import restrict_sockets
        observation['network_restriction'] = restrict_sockets()
    else:
        observation['network_restriction'] = None
    atomic(target / 'output' / 'executor-observation.json', observation)
    os.chdir(environment.get('T01_NATIVE_CWD', str(target / 'output')))
    os.execve(argv[0], argv, environment)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    child_main(args.child, args.expected_sha256)
