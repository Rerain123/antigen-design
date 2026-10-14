"""Windows Job Object implementation retained behind the platform interface."""

import ctypes as C
from ctypes import wintypes as W
from contextlib import contextmanager
import msvcrt
import os
import subprocess

K = C.WinDLL("kernel32", use_last_error=True)
HANDLE = W.HANDLE


def bind(name, args, result=W.BOOL):
    fn = getattr(K, name); fn.argtypes = args; fn.restype = result
    return fn


Close = bind("CloseHandle", [HANDLE])
CreateJob = bind("CreateJobObjectW", [C.c_void_p, W.LPCWSTR], HANDLE)
OpenJob = bind("OpenJobObjectW", [W.DWORD, W.BOOL, W.LPCWSTR], HANDLE)
SetJob = bind("SetInformationJobObject", [HANDLE, C.c_int, C.c_void_p, W.DWORD])
QueryJob = bind("QueryInformationJobObject", [HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p])
Assign = bind("AssignProcessToJobObject", [HANDLE, HANDLE])
TerminateJob = bind("TerminateJobObject", [HANDLE, W.UINT])
OpenProcess = bind("OpenProcess", [W.DWORD, W.BOOL, W.DWORD], HANDLE)
Wait = bind("WaitForSingleObject", [HANDLE, W.DWORD], W.DWORD)
GetTimes = bind("GetProcessTimes", [HANDLE, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p])
GetExit = bind("GetExitCodeProcess", [HANDLE, C.POINTER(W.DWORD)])
Resume = bind("ResumeThread", [HANDLE], W.DWORD)
TerminateProcess = bind("TerminateProcess", [HANDLE, W.UINT])
CreateFile = bind("CreateFileW", [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, HANDLE], HANDLE)
CreateMutex = bind("CreateMutexW", [C.c_void_p, W.BOOL, W.LPCWSTR], HANDLE)
ReleaseMutex = bind("ReleaseMutex", [HANDLE])


@contextmanager
def initialization_lock(name):
    handle = ok(CreateMutex(None, False, name)); acquired = False
    try:
        acquired = Wait(handle, 15000) in (0, 128)
        if not acquired: raise OSError("Runtime initialization lock unavailable")
        yield
    finally:
        if acquired: ReleaseMutex(handle)
        Close(handle)


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_longlong), ("job_time", C.c_longlong), ("flags", W.DWORD),
                ("working_min", C.c_size_t), ("working_max", C.c_size_t), ("active_limit", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]


class IO(C.Structure):
    _fields_ = [(n, C.c_ulonglong) for n in ["read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes"]]


class Extended(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", IO), ("process_memory", C.c_size_t),
                ("job_memory", C.c_size_t), ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]


class Accounting(C.Structure):
    _fields_ = [(n, C.c_longlong) for n in ["user", "kernel", "period_user", "period_kernel"]] + [
        ("page_faults", W.DWORD), ("total", W.DWORD), ("active", W.DWORD), ("terminated", W.DWORD)]


class Startup(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR), ("title", W.LPWSTR),
                *[(n, W.DWORD) for n in ["x", "y", "xsize", "ysize", "xchars", "ychars", "fill", "flags"]],
                ("show", W.WORD), ("reserved2", W.WORD), ("bytes", C.c_void_p),
                ("stdin", HANDLE), ("stdout", HANDLE), ("stderr", HANDLE)]


class ProcessInfo(C.Structure):
    _fields_ = [("process", HANDLE), ("thread", HANDLE), ("pid", W.DWORD), ("tid", W.DWORD)]


CreateProcess = bind("CreateProcessW", [W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD,
                                        C.c_void_p, W.LPCWSTR, C.POINTER(Startup), C.POINTER(ProcessInfo)])


def ok(value):
    if not value: raise C.WinError(C.get_last_error())
    return value


def birth(handle):
    values = [C.c_ulonglong() for _ in range(4)]
    ok(GetTimes(handle, *[C.byref(v) for v in values]))
    return str(values[0].value)


def current_identity():
    handle = ok(OpenProcess(0x1000 | 0x100000, False, os.getpid()))
    try: return {"pid": os.getpid(), "birth": birth(handle), "platform": "windows"}
    finally: Close(handle)


def alive(identity):
    if not identity: return None
    handle = OpenProcess(0x1000 | 0x100000, False, identity["pid"])
    if not handle: return False if C.get_last_error() == 87 else None
    try:
        if birth(handle) != identity["birth"]: return False
        return Wait(handle, 0) == 258
    except OSError: return None
    finally: Close(handle)


@contextmanager
def locked_file(path):
    handle = CreateFile(str(path), 0x80000000, 1, None, 3, 0x00200000, None)
    if handle == C.c_void_p(-1).value: raise C.WinError(C.get_last_error())
    fd = msvcrt.open_osfhandle(int(handle), os.O_RDONLY | os.O_BINARY)
    with os.fdopen(fd, "rb") as stream: yield stream


class Process:
    def __init__(self, argv, cwd, job=None):
        info, startup = ProcessInfo(), Startup(); startup.cb = C.sizeof(startup)
        command = C.create_unicode_buffer(subprocess.list2cmdline([str(a) for a in argv]))
        ok(CreateProcess(None, command, None, None, False, 0x00000004 | 0x08000000,
                         None, str(cwd), C.byref(startup), C.byref(info)))
        self.handle, self.thread, self.pid = info.process, info.thread, info.pid
        try:
            self.identity = {"pid": self.pid, "birth": birth(self.handle), "platform": "windows"}
            if job: ok(Assign(job.handle, self.handle))
        except BaseException:
            TerminateProcess(self.handle, 1); Close(self.thread); Close(self.handle); raise

    def resume(self):
        if Resume(self.thread) == 0xFFFFFFFF:
            error = C.WinError(C.get_last_error()); TerminateProcess(self.handle, 1); self.close(); raise error
        Close(self.thread); self.thread = None

    def poll(self):
        if Wait(self.handle, 0) == 258: return None
        result = W.DWORD(); ok(GetExit(self.handle, C.byref(result))); return result.value

    def close(self):
        if self.thread: Close(self.thread); self.thread = None
        if self.handle: Close(self.handle); self.handle = None


class Job:
    def __init__(self, name, create=True, memory_bytes=256 * 1024**2, active_limit=4):
        self.name = name
        self.handle = CreateJob(None, name) if create else OpenJob(0x0004 | 0x0008, False, name)
        if not self.handle: raise C.WinError(C.get_last_error())
        if create:
            if C.get_last_error() == 183:
                Close(self.handle); self.handle = None; raise RuntimeError("Execution Job Object already exists")
            limits = Extended(); limits.basic.flags = 0x2000 | 0x0008 | 0x0200
            limits.basic.active_limit = active_limit; limits.job_memory = memory_bytes
            try: ok(SetJob(self.handle, 9, C.byref(limits), C.sizeof(limits)))
            except BaseException: self.close(); raise

    def active(self):
        info = Accounting(); ok(QueryJob(self.handle, 1, C.byref(info), C.sizeof(info), None)); return info.active

    def limits(self):
        info = Extended(); ok(QueryJob(self.handle, 9, C.byref(info), C.sizeof(info), None))
        return {"flags": info.basic.flags, "active_limit": info.basic.active_limit,
                "job_memory": info.job_memory, "platform": "windows-job-object"}

    def stop(self): ok(TerminateJob(self.handle, 1))

    def close(self):
        if self.handle: Close(self.handle); self.handle = None


def inspect_job(name, stop=False):
    try: job = Job(name, create=False)
    except OSError as exc: return 0 if exc.winerror == 2 else None
    try:
        if stop: job.stop()
        return job.active()
    except OSError: return None
    finally: job.close()

