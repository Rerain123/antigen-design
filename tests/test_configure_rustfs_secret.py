import base64
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec=importlib.util.spec_from_file_location('configure_rustfs_secret',Path(__file__).resolve().parents[1]/'scripts/configure_rustfs_secret.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_secret_is_scoped_and_credentials_are_stdin_only(monkeypatch):
    payload=mod.document('dummy-access','dummy-secret')
    assert payload['metadata']=={'name':'antigen-design-rustfs','namespace':'him-ws'}
    assert set(payload['data'])==set(mod.KEYS)
    assert base64.b64decode(payload['data']['RUSTFS_SECRET_ACCESS_KEY'])==b'dummy-secret'
    assert 'annotations' not in payload['metadata']
    import json
    raw=json.dumps(payload).encode()
    def invoke(argv,**kwargs):
        assert all('dummy-' not in a for a in argv)
        assert kwargs['input']==raw
        assert kwargs['capture_output']
        return SimpleNamespace(returncode=0,stdout=b'secret/antigen-design-rustfs',stderr=b'')
    monkeypatch.setattr(mod.subprocess,'run',invoke)
    mod.call('create','-f','-','-o','name',data=raw)


def test_api_error_cannot_echo_submitted_secret(monkeypatch):
    monkeypatch.setattr(mod.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=1,stdout=b'',stderr=b'error containing dummy-secret'))
    with pytest.raises(RuntimeError) as error:
        mod.call('create','-f','-',data=b'dummy-secret')
    assert 'dummy-secret' not in str(error.value)


def test_rejects_corrupted_paste_without_echo():
    with pytest.raises(ValueError) as error:
        mod.document('dummy-access',' dummy-secret\n')
    assert 'dummy-secret' not in str(error.value)
