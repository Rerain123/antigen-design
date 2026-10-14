"""Bounded pure-computation reuse within one synchronous traversal.

Call only AFTER current file/ownership/hash verification. Key the complete
input values, never paths or timestamps. No database or I/O call is cached.
"""
import copy
import hashlib
import pickle
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from threading import get_ident

_active = ContextVar('controller_pure_replay', default=None)


class Cache:
    def __init__(self, max_bytes=64*1024*1024, max_entries=64):
        self.owner = get_ident()
        self.entries = OrderedDict()
        self.size = 0
        self.max_bytes, self.max_entries = max_bytes, max_entries
        self.hits = self.misses = 0

    def call(self, function, *args, **kwargs):
        # Pickle is only an in-memory encoding of our own arguments; no pickle
        # supplied by a user/file/network is ever loaded.
        key = (function, hashlib.sha256(pickle.dumps((args, kwargs), protocol=5)).digest())
        if key in self.entries:
            self.entries.move_to_end(key)
            self.hits += 1
            return copy.deepcopy(self.entries[key][0])
        self.misses += 1
        result = function(*args, **kwargs)
        size = 8*len(pickle.dumps(result, protocol=5)) + 1024
        if size <= self.max_bytes and self.max_entries > 0:
            while self.entries and (self.size+size > self.max_bytes or len(self.entries) >= self.max_entries):
                _, (_, old) = self.entries.popitem(last=False)
                self.size -= old
            self.entries[key] = (copy.deepcopy(result), size)
            self.size += size
        return result


def current():
    value = _active.get()
    return value if value is not None and value.owner == get_ident() else None


def pure(function, *args, **kwargs):
    value = current()
    return function(*args, **kwargs) if value is None else value.call(function, *args, **kwargs)


@contextmanager
def scope():
    existing = current()
    if existing is not None:
        yield existing
        return
    value = Cache()
    token = _active.set(value)
    try:
        yield value
    finally:
        _active.reset(token)
        value.entries.clear()
        value.size = 0


def traversal(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with scope():
            return function(*args, **kwargs)
    return wrapped
