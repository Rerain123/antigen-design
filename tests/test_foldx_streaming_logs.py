"""Native diagnostics survive interruption without changing command semantics."""
import subprocess
import sys

import pytest

from t01_phase1_real.development.foldx import worker


def test_logs_are_visible_before_native_process_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'OUT', tmp_path)
    # The child itself verifies its bytes reached the diagnostic file while
    # still alive. A captured PIPE would leave the file absent until exit.
    code = """
import os
from pathlib import Path
os.write(1, b'native progress\\n')
os.write(2, b'native warning\\n')
assert Path('buildmodel.stdout.txt').read_bytes() == b'native progress\\n'
assert Path('buildmodel.stdout.stderr.txt').read_bytes() == b'native warning\\n'
raise SystemExit(7)
"""
    result = worker.run([sys.executable, '-c', code], tmp_path, 'buildmodel.stdout.txt')
    assert result.returncode == 7
    assert (tmp_path / 'buildmodel.stdout.txt').read_bytes() == b'native progress\n'


def test_interrupted_wait_preserves_written_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'OUT', tmp_path)
    argv = ['unchanged-native-command', '--numberOfRuns=5']

    def interrupted(command, **kwargs):
        assert command == argv and kwargs['cwd'] == tmp_path
        assert set(kwargs) == {'cwd', 'stdout', 'stderr'}
        kwargs['stdout'].write(b'partial native output')
        kwargs['stderr'].write(b'partial native error')
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess, 'run', interrupted)
    with pytest.raises(KeyboardInterrupt):
        worker.run(argv, tmp_path, 'buildmodel.stdout.txt')
    assert (tmp_path / 'buildmodel.stdout.txt').read_bytes() == b'partial native output'
    assert (tmp_path / 'buildmodel.stdout.stderr.txt').read_bytes() == b'partial native error'
