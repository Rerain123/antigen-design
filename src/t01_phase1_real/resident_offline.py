"""Inherited socket restriction for the registered Linux/amd64 native tools.

Uses the Linux seccomp ABI (kernel.org/doc/html/latest/userspace-api/seccomp_filter.html).
This is an offline execution guard, not a sandbox for untrusted executable code.
"""
import ctypes
import errno
import platform


def restrict_sockets():
    if platform.machine() != 'x86_64':
        raise RuntimeError('Resident scientific profile requires Linux amd64')
    class Filter(ctypes.Structure):
        _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte),
                    ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint)]
    class Program(ctypes.Structure):
        _fields_ = [('len', ctypes.c_ushort), ('filter', ctypes.POINTER(Filter))]
    allow = 0x7fff0000
    deny = 0x00050000 | errno.EPERM
    # seccomp_data: nr at 0, arch at 4, args[0] at 16. AF_UNIX is for
    # local IPC, AF_NETLINK for interface enumeration. Reject alternate ABIs and io_uring,
    # which could otherwise issue socket operations outside this filter.
    rows = [(0x20,0,0,4), (0x15,1,0,0xc000003e), (0x06,0,0,deny),
            (0x20,0,0,0), (0x35,0,1,0x40000000), (0x06,0,0,deny),
            (0x15,0,1,425), (0x06,0,0,deny),
            (0x15,1,0,41), (0x06,0,0,allow),
            (0x20,0,0,16), (0x15,2,0,1), (0x15,1,0,16),
            (0x06,0,0,deny), (0x06,0,0,allow)]
    filters = (Filter * len(rows))(*(Filter(*row) for row in rows))
    program = Program(len(rows), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) or libc.prctl(22, 2, ctypes.byref(program), 0, 0):
        raise OSError(ctypes.get_errno(), 'Cannot install resident offline socket restriction')
    return 'seccomp-local-sockets-only-v1'
