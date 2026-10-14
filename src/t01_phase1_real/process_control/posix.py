"""Linux/POSIX implementation using owned process groups and PID birth tokens."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
import resource
import signal
import time

REGISTRY = Path(os.environ.get("T01_PROCESS_REGISTRY", "/tmp/t01-process-control"))


def _record_path(name):
    REGISTRY.mkdir(mode=0o700, parents=True, exist_ok=True)
    return REGISTRY / (hashlib.sha256(name.encode("utf-8")).hexdigest() + ".json")


def _stat(pid):
    raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="ascii")
    fields = raw[raw.rfind(")") + 2:].split()
    return {"state": fields[0], "pgrp": int(fields[2]), "birth": fields[19]}


def current_identity():
    return {"pid": os.getpid(), "birth": _stat(os.getpid())["birth"], "platform": "linux"}


def alive(identity):
    if not identity: return None
    try:
        observed = _stat(identity["pid"])
        return observed["birth"] == str(identity["birth"]) and observed["state"] != "Z"
    except FileNotFoundError: return False
    except (KeyError, OSError, ValueError): return None


@contextmanager
def initialization_lock(name):
    path = _record_path("lock:" + name)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    acquired = False; deadline = time.monotonic() + 15
    try:
        while not acquired:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB); acquired = True
            except BlockingIOError:
                if time.monotonic() >= deadline: raise OSError("Runtime initialization lock unavailable")
                time.sleep(0.02)
        yield
    finally:
        if acquired: fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


@contextmanager
def locked_file(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    stream = os.fdopen(descriptor, "rb")
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_SH); yield stream
    finally:
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN); stream.close()


def _members(pgid):
    result = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit(): continue
        try:
            observed = _stat(int(entry.name))
            if observed["pgrp"] == pgid and observed["state"] != "Z": result.append(int(entry.name))
        except (FileNotFoundError, PermissionError, ValueError): continue
    return result


class Process:
    """Create a stopped process group; resume only after durable registration."""

    def __init__(self, argv, cwd, job=None):
        self.pid = os.fork(); self._status = None
        if self.pid == 0:  # pragma: no cover - child path
            try:
                os.chdir(cwd); os.setsid()
                if job is not None:
                    if job.memory_bytes: resource.setrlimit(resource.RLIMIT_AS, (job.memory_bytes, job.memory_bytes))
                    # RLIMIT_NPROC is per UID rather than per owned process
                    # group, so using it here would let one concurrent job
                    # starve unrelated jobs. The group is still observed and
                    # the Pod/container pids limit is the platform boundary.
                os.kill(os.getpid(), signal.SIGSTOP)
                os.execv(str(argv[0]), [str(item) for item in argv])
            except BaseException: os._exit(127)
        waited, status = os.waitpid(self.pid, os.WUNTRACED)
        if waited != self.pid or not os.WIFSTOPPED(status): raise OSError("Child did not enter registration barrier")
        self.identity = {"pid": self.pid, "birth": _stat(self.pid)["birth"], "platform": "linux"}
        if job is not None: job._register(self.identity)

    def resume(self): os.kill(self.pid, signal.SIGCONT)

    def poll(self):
        if self._status is not None: return self._status
        try: waited, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError: return 0 if alive(self.identity) is False else None
        if waited == 0: return None
        if os.WIFEXITED(status): self._status = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status): self._status = 128 + os.WTERMSIG(status)
        return self._status

    def close(self): return


class Job:
    def __init__(self, name, create=True, memory_bytes=1024 * 1024**2, active_limit=4):
        self.name = name; self.handle = True; self.memory_bytes = memory_bytes; self.active_limit = active_limit
        self.path = _record_path("job:" + name)
        if create:
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(descriptor)
        elif not self.path.is_file():
            raise FileNotFoundError(errno.ENOENT, "Execution process group is absent", self.path)

    def _register(self, identity):
        payload = {"name": self.name, "pgid": identity["pid"], "leader": identity,
                   "memory_bytes": self.memory_bytes, "active_limit": self.active_limit}
        descriptor = os.open(self.path, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":")); stream.flush(); os.fsync(stream.fileno())

    def _record(self):
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("name") != self.name or not isinstance(raw.get("pgid"), int): raise OSError("Process group ownership record differs")
        return raw

    def active(self):
        record = self._record()
        leader = record.get("leader")
        if not isinstance(leader, dict) or record["pgid"] != leader.get("pid"):
            raise OSError("Process group leader identity is missing")
        if alive(leader) is True:
            if _stat(leader["pid"])["pgrp"] != record["pgid"]:
                raise OSError("Process group ownership changed")
            return len(_members(record["pgid"]))
        # A vanished leader does not prove its descendants have exited. Never
        # claim stop confirmation while a group with that ID is still present.
        if _members(record["pgid"]):
            raise OSError("Leader identity expired; process group ownership is unconfirmed")
        return 0

    def limits(self):
        return {"flags": "kill-process-group", "active_limit": self.active_limit,
                "job_memory": self.memory_bytes, "platform": "linux-process-group-rlimit",
                "active_limit_enforcement": "container-or-pod-pids-limit"}

    def stop(self):
        record = self._record(); leader = record.get("leader")
        if not isinstance(leader, dict) or record["pgid"] != leader.get("pid"):
            raise OSError("Process group leader identity is missing")
        if alive(leader) is not True:
            if _members(record["pgid"]):
                raise OSError("Expired leader; refusing to signal an unowned process group")
            return
        if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
            raise OSError("Race-safe Linux process stopping requires pidfd support")
        handles = {}
        try:
            # Holding pidfds and checking birth AFTER opening them prevents PID
            # reuse between identity verification and signalling. Never killpg.
            def freeze(pid, expected_birth=None):
                fd = os.pidfd_open(pid)
                try:
                    observed = _stat(pid)
                    if observed['pgrp'] != record['pgid'] or (expected_birth is not None and observed['birth'] != str(expected_birth)):
                        raise OSError('Process identity changed before stop')
                    signal.pidfd_send_signal(fd, signal.SIGSTOP)
                    handles[pid] = fd
                except BaseException:
                    os.close(fd); raise
            freeze(leader['pid'], leader['birth'])
            # Stop newly observed children before taking another membership
            # snapshot. A bounded failure leaves ownership unconfirmed.
            for _ in range(64):
                pending = [pid for pid in _members(record['pgid']) if pid not in handles]
                if not pending: break
                for pid in pending:
                    try: freeze(pid)
                    except ProcessLookupError: pass
            else: raise OSError('Process group did not quiesce')
            for fd in handles.values():
                try: signal.pidfd_send_signal(fd, signal.SIGKILL)
                except ProcessLookupError: pass
        finally:
            for fd in handles.values(): os.close(fd)

    def close(self): self.handle = None


def inspect_job(name, stop=False):
    try: job = Job(name, create=False)
    except FileNotFoundError: return 0
    try:
        if stop:
            job.stop(); deadline = time.monotonic() + 5
            while job.active() and time.monotonic() < deadline: time.sleep(0.02)
        return job.active()
    except (OSError, ValueError, json.JSONDecodeError): return None
    finally: job.close()
