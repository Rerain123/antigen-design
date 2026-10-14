import base64
import copy
import importlib
import sys
from pathlib import Path
import pytest


@pytest.fixture
def deploy(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    return importlib.import_module('prepare_m1_p2_deploy')


def test_scale_bytes_keep_crlf_and_utf8_exact(deploy,tmp_path,monkeypatch):
    raw=b'locked-source\r\n\xe4\xb8\xad\r\n'
    (tmp_path/'scale.txt').write_bytes(raw)
    monkeypatch.setattr(deploy,'ROOT',tmp_path)
    cm=deploy.binary_configmap(['scale.txt'])
    assert cm['immutable'] and 'data' not in cm
    assert base64.b64decode(cm['binaryData']['p0'])==raw


def test_gpu_projected_directory_has_no_nested_file_mount(deploy):
    base=dict(name='worker-unified-gpu',volumeMounts=[
        dict(name='esmfold2-code',mountPath='/backend',readOnly=True),
        dict(name='m1-p2-code',mountPath='/backend/t01_phase1_real/development/esmfold2/quality.py',subPath='p4'),
        dict(name='runtime',mountPath='/var/lib/t01')])
    before=copy.deepcopy(base)
    mounts=deploy.overlay_mounts(base,deploy.FILES)
    assert [m['mountPath'] for m in mounts]==['/backend','/var/lib/t01']
    assert base==before


def test_esm_overlay_changes_only_quality_and_never_mutates_old_manifest(deploy,tmp_path,monkeypatch):
    quality='t01_phase1_real/development/esmfold2/quality.py'
    path=tmp_path/'src'/quality;path.parent.mkdir(parents=True);path.write_bytes(b'new\r\n')
    monkeypatch.setattr(deploy,'ROOT',tmp_path)
    old=dict(metadata=dict(name='old'),immutable=True,data={'q':'old\r\n','other':'keep\r\n'})
    volume=dict(configMap=dict(name='old',items=[dict(key='q',path=quality)]))
    before=copy.deepcopy((old,volume))
    result=deploy.esm_configmap(old,volume)
    assert result['data']=={'q':'new\r\n','other':'keep\r\n'}
    assert (old,volume)==before


def test_service_retains_other_overlays_and_has_one_mount_per_target(deploy):
    paths=deploy.FILES
    container=dict(name='service',volumeMounts=[
        dict(name='old',mountPath='/app/'+paths[0],subPath='old'),
        dict(name='af3',mountPath='/app/src/af3.py',readOnly=True),
        dict(name='runtime',mountPath='/var/lib/t01/runtime')])
    mounts=deploy.overlay_mounts(container,paths)
    assert len({m['mountPath'] for m in mounts})==len(mounts)
    assert all(any(m['mountPath']=='/app/'+p and m['readOnly'] for m in mounts) for p in paths)
    assert any(m['name']=='af3' for m in mounts) and any(m['name']=='runtime' for m in mounts)
