import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import upload_esmfold2_environment as upload


@pytest.fixture
def transport(tmp_path, monkeypatch):
    remote = tmp_path / 'remote'
    local = tmp_path / 'local'
    local.mkdir()
    code = upload.SERVER.replace(
        'ROOT=Path("/models/esmfold2-environment-20260916-r01")',
        'ROOT=Path(' + repr(str(remote)) + ')')
    code = code.replace('("127.0.0.1",18743)', '("127.0.0.1",0)')
    code = code.replace('try:server.serve_forever()',
                        'print(server.server_address[1],flush=True)\ntry:server.serve_forever()')
    process = subprocess.Popen([sys.executable, '-u', '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    monkeypatch.setattr(upload, 'PORT', int(process.stdout.readline()))
    monkeypatch.setattr(upload, 'SOURCE', local)
    monkeypatch.setattr(upload, 'FORWARD', SimpleNamespace(poll=lambda: None))
    try:
        yield local, remote
    finally:
        upload.request('POST', '/shutdown')
        process.wait(timeout=10)
        assert process.returncode == 0


def test_resume_and_completed_reverification(transport):
    local, remote = transport
    raw = b'large-environment-fixture' * 100
    (local / 'archive.tar.gz').write_bytes(raw)
    (remote / 'archive.tar.gz.partial').write_bytes(raw[:133])
    digest = hashlib.sha256(raw).hexdigest()
    result = upload.transfer('archive.tar.gz', len(raw), digest)
    assert result['sha256'] == digest
    assert (remote / 'archive.tar.gz').read_bytes() == raw
    assert not (remote / 'archive.tar.gz.partial').exists()
    assert upload.transfer('archive.tar.gz', len(raw), digest) == result


def test_corrupt_remote_file_is_not_accepted(transport):
    local, remote = transport
    raw = b'good'
    (local / 'archive.tar.gz').write_bytes(raw)
    (remote / 'archive.tar.gz').write_bytes(b'bad!')
    with pytest.raises(RuntimeError, match='sha256 differs'):
        upload.transfer('archive.tar.gz', len(raw), hashlib.sha256(raw).hexdigest())
    assert (remote / 'archive.tar.gz').read_bytes() == b'bad!'


def test_local_corruption_refused_before_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, 'SOURCE', tmp_path)
    (tmp_path / 'archive.tar.gz').write_bytes(b'bad!')
    with pytest.raises(RuntimeError, match='local integrity'):
        upload.transfer('archive.tar.gz', 4, hashlib.sha256(b'good').hexdigest())


def test_fixed_environment_target():
    assert upload.DESTINATION == '/models/esmfold2-environment-20260916-r01'
    assert upload.DESTINATION in upload.SERVER
    assert '/models/esmfold2-standard-' not in upload.SERVER
    assert upload.PORT == 18743
