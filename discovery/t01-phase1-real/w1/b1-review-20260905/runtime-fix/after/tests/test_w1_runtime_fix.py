"""Regression for observed zero-link Windows SQLite sidecars without weakening opened-file checks."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from t01_phase1_real.common import RuntimeFault
from t01_phase1_real.files import no_links,read_locked

pytestmark=pytest.mark.skipif(os.name!='nt',reason='Windows file-handle behavior')


def zero_link_metadata(monkeypatch,target):
    original=Path.lstat
    def transient(self,*args,**kwargs):
        info=original(self,*args,**kwargs)
        if self==target:
            return SimpleNamespace(st_mode=info.st_mode,st_nlink=0,st_file_attributes=info.st_file_attributes)
        return info
    monkeypatch.setattr(Path,'lstat',transient)


def test_transient_zero_link_metadata_is_not_a_hardlink(tmp_path,monkeypatch):
    sidecar=tmp_path/'state.sqlite3-wal';sidecar.write_bytes(b'owned temporary sqlite sidecar')
    zero_link_metadata(monkeypatch,sidecar)
    assert no_links(sidecar)==sidecar
    assert read_locked(sidecar)==b'owned temporary sqlite sidecar'


def test_opened_handle_still_rejects_hidden_hardlinks(tmp_path,monkeypatch):
    source=tmp_path/'original';source.write_bytes(b'bytes')
    linked=tmp_path/'linked';os.link(source,linked)
    zero_link_metadata(monkeypatch,linked)
    with pytest.raises(RuntimeFault,match='Opened file'): read_locked(linked)


def test_actual_hardlink_preflight_remains_closed(tmp_path):
    source=tmp_path/'original';source.write_bytes(b'bytes')
    linked=tmp_path/'linked';os.link(source,linked)
    with pytest.raises(RuntimeFault,match='Hard-linked'): no_links(linked)


def test_historical_source_registry_cannot_escape_evidence_root(monkeypatch):
    import hashlib
    import sys
    from t01_phase1_real.common import REPO
    sys.path.insert(0,str(REPO/'scripts'))
    import check_w1_runtime as checker
    original=checker.read
    history=checker.ROOT/'discovery/t01-phase1-real/w1/runtime-source-history.json'
    digest=hashlib.sha256((checker.DEFAULT/'manifest.json').read_bytes()).hexdigest()
    def forged(path):
        if path==history:
            return dict(archives=[dict(manifest_sha256=digest,source_root='../outside')])
        return original(path)
    monkeypatch.setattr(checker,'read',forged)
    with pytest.raises(ValueError,match='Unsafe historical'): checker.verify()
