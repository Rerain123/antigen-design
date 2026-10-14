"""Changing current doc rules must neither mutate nor bypass old execution evidence."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import check_b2_boundaries as checker


def test_historical_checker_requires_exact_recorded_snapshot(tmp_path,monkeypatch):
    monkeypatch.setattr(checker,'ROOT',tmp_path)
    batch=tmp_path/'batch';source=batch/'code_snapshot/scripts/check_b2_boundaries.py'
    source.parent.mkdir(parents=True);source.write_bytes(b'original checker')
    entry=dict(path='scripts/check_b2_boundaries.py',sha256=checker.digest(source),size_bytes=source.stat().st_size)
    live=tmp_path/entry['path'];live.parent.mkdir();live.write_bytes(b'current read-only verifier')
    checker.verify_historical_sources(batch,[entry])
    source.write_bytes(b'changed original')
    with pytest.raises(ValueError,match='HISTORICAL_CHECKER_SNAPSHOT_MISMATCH'):checker.verify_historical_sources(batch,[entry])


def test_scientific_and_other_sources_cannot_use_checker_exception(tmp_path,monkeypatch):
    monkeypatch.setattr(checker,'ROOT',tmp_path)
    path=tmp_path/'scripts/b2_boundary_probe.py';path.parent.mkdir();path.write_bytes(b'original observation')
    entry=checker.fingerprint(path,tmp_path)
    checker.verify_historical_sources(tmp_path/'batch',[entry])
    path.write_bytes(b'different')
    with pytest.raises(ValueError,match='ARTIFACT_HASH'):checker.verify_historical_sources(tmp_path/'batch',[entry])
