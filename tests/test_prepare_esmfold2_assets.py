import hashlib
import importlib.util
import io
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('prepare_esmfold2_assets', Path(__file__).resolve().parents[1] / 'scripts/prepare_esmfold2_assets.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class Response(io.BytesIO):
    def __init__(self, data, status, headers):
        super().__init__(data)
        self.status = status
        self.headers = headers


def test_resume_and_verify_lfs(tmp_path, monkeypatch):
    payload = b'correct-model-payload'
    target = tmp_path / 'model.safetensors'
    target.with_name(target.name + '.partial').write_bytes(payload[:7])
    entry = {'size': len(payload), 'lfs': {'sha256': hashlib.sha256(payload).hexdigest()}}
    calls = []
    def request(url, headers):
        calls.append(headers)
        return Response(payload[7:], 206, {'Content-Range': f'bytes 7-{len(payload)-1}/{len(payload)}'})
    monkeypatch.setattr(mod, 'request', request)
    assert mod.download('https://huggingface.co/example', target, entry) == entry['lfs']['sha256']
    assert target.read_bytes() == payload
    assert calls == [{'Range': 'bytes=7-'}]


def test_reject_ignored_range_without_appending(tmp_path, monkeypatch):
    import pytest
    target = tmp_path / 'model'
    partial = tmp_path / 'model.partial'
    partial.write_bytes(b'abc')
    monkeypatch.setattr(mod, 'request', lambda *_: Response(b'abcdef', 200, {}))
    with pytest.raises(ValueError, match='resume range'):
        mod.download('https://huggingface.co/example', target, {'size': 6})
    assert partial.read_bytes() == b'abc'


def test_verify_git_blob_and_reject_existing_corruption(tmp_path):
    import pytest
    target = tmp_path / 'config.json'
    target.write_bytes(b'{}')
    entry = {'size': 2, 'blobId': hashlib.sha1(b'blob 2\0{}').hexdigest()}
    assert mod.validate(target, entry) == hashlib.sha256(b'{}').hexdigest()
    target.write_bytes(b'[]')
    with pytest.raises(ValueError, match='differs'):
        mod.download('https://huggingface.co/example', target, entry)
