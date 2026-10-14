"""Controlled local storage, byte snapshots and immutable publication."""
import os
import stat
from pathlib import Path
from uuid import uuid4

from .common import REPO, RuntimeFault, ensure, sha


def no_links(path):
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents),path]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        ensure(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,
               'FORBIDDEN','Symbolic link or reparse point is not allowed')
        ensure(not stat.S_ISREG(info.st_mode) or info.st_nlink==1,'FORBIDDEN','Hard-linked files are not allowed')
    return path


def runtime_root(path):
    ensure(Path(path).is_absolute(),'FORBIDDEN','Runtime root must be absolute')
    path = no_links(path).resolve()
    blocked = [REPO/p for p in ['legacy','工作流设计','docs','src','tests','scripts','dify','discovery','工具部署','.git','.agents','.codex']]
    blocked.append(REPO/'var/t01-phase1-mock-v0.1')
    for target in blocked:
        ensure(not path.is_relative_to(target) and not target.is_relative_to(path),'FORBIDDEN','Protected runtime location')
    ensure(not str(path).startswith('\\\\'),'FORBIDDEN','Network database location is unsupported')
    path.mkdir(parents=True,exist_ok=True)
    no_links(path)
    return path


def within(root, relative):
    ensure(isinstance(relative,str) and relative and ':' not in relative and '\\' not in relative
           and not relative.startswith('/') and all(p not in ('','.','..') for p in relative.split('/')),
           'FORBIDDEN','Unsafe relative file reference')
    path = no_links(root/relative)
    ensure(path.resolve().is_relative_to(root.resolve()),'FORBIDDEN','File escapes runtime root')
    return path


def read_locked(path, max_bytes=1048576):
    """Windows sharing mode denies concurrent writes/deletes while bytes are copied."""
    path = no_links(path)
    if os.name=='nt':
        from .winprocess import locked_file
        try:
            with locked_file(path) as stream:
                data = stream.read(max_bytes+1)
        except OSError as exc:
            code = 'ASSET_MISSING' if not path.exists() else 'HASH_MISMATCH'
            raise RuntimeFault(code,'Cannot read immutable file snapshot') from exc
    else:
        raise RuntimeFault('PROFILE_NOT_APPROVED','Local executor has only been qualified on Windows')
    ensure(len(data)<=max_bytes,'INVALID_REQUEST','File exceeds bounded size')
    no_links(path)
    return data


def read_verified(root, relative, expected_sha, size, max_bytes=1048576):
    raw = read_locked(within(root,relative),max_bytes)
    ensure(len(raw)==size and sha(raw)==expected_sha,'HASH_MISMATCH','Stored artifact fingerprint mismatch')
    return raw


def publish(root, relative, raw):
    """Closed/fsynced bytes, then same-directory atomic no-replace publication."""
    path = within(root,relative)
    path.parent.mkdir(parents=True,exist_ok=True)
    no_links(path.parent)
    temp = path.with_name('.pending-'+uuid4().hex)
    try:
        with temp.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        no_links(path)
        # On Windows os.rename refuses an existing target. Published evidence is never replaced.
        ensure(os.name=='nt','PROFILE_NOT_APPROVED','Atomic publisher qualified on Windows only')
        os.rename(temp,path)
    except BaseException:
        if temp.exists():
            temp.unlink()  # Exact task-created file, no recursive cleanup.
        raise
    return path
