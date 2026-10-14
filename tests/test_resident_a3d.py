"""Nested process ownership fixtures, not scientific acceptance."""
from contextlib import contextmanager
import copy
from datetime import datetime,timezone
import json
import pytest
from t01_phase1_real import resident_a3d as a3d
from t01_phase1_real.common import sha,RuntimeFault
from t01_phase1_real.resident_process import prepare,atomic
from t01_phase1_real.resident_assembly import command


class Runtime:
    def __init__(self,root):
        self.root=root;self.ex={}
        self.job=dict(job_id='job',attempt_id='attempt',execution_identity='identity',stop_reason=None,
                      started_at=datetime.now(timezone.utc).isoformat())
    def get(self,_):return dict(self.job)
    def execution(self,_):return copy.deepcopy(self.ex)
    @contextmanager
    def _tx(self):yield None
    def _execution(self,*_):return copy.deepcopy(self.ex)
    def _execution_store(self,db,j,ex):self.ex=copy.deepcopy(ex)


@pytest.fixture
def nested(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);cmd=command('aggrescan3d')
    config=dict(version='0.1.0',runtime_volume_root=str(tmp_path),tools={'aggrescan3d':dict(
        root=str(tmp_path/'spool'),command=cmd.document(),source_image_id=a3d.IMAGE_ID)})
    monkeypatch.setattr(a3d,'configuration',lambda:(config,'fingerprint'))
    target,_,_=a3d.context(rt,rt.job,{})
    rt.ex=dict(a3d_resident_target=str(target),a3d_resident_config_sha256='fingerprint',a3d_resident_input_sha256=sha(b'input'))
    prepare(target.parent,target.name,a3d.binding(rt.job),cmd,{'input.pdb':b'input'},30)
    return rt,target,cmd


def receipt(rt,target,**changes):
    raw=(target/'request.json').read_bytes()
    r=dict(backend='resident-process',binding=a3d.binding(rt.job),execution_id=target.name,
           request_sha256=sha(raw),stopped_confirmed=True,state='failed',exit_code=7,outputs={})
    r.update(changes);atomic(target/'execution.json',r);return r


def test_recovery_waits_for_stop_and_never_relaunches(nested,monkeypatch):
    rt,target,cmd=nested
    monkeypatch.setattr(a3d,'prepare',lambda *a,**k:pytest.fail('recovery must not stage'))
    assert not a3d.cleanup_interrupted(rt,rt.job,rt.ex)
    assert (target/'cancel').exists()
    receipt(rt,target)
    assert a3d.cleanup_interrupted(rt,rt.job,rt.ex)
    assert rt.ex['a3d_resident_stop_confirmed'] is True


@pytest.mark.parametrize('change',[{'binding':{'job_id':'foreign'}},{'request_sha256':'wrong'},{'execution_id':'foreign'}])
def test_recovery_rejects_foreign_receipt(nested,change):
    rt,target,cmd=nested;receipt(rt,target,**change)
    assert not a3d.cleanup_interrupted(rt,rt.job,rt.ex)
    assert not (target/'cancel').exists()


def test_recovery_rejects_configuration_drift(nested):
    rt,target,cmd=nested;receipt(rt,target)
    rt.ex['a3d_resident_config_sha256']='changed'
    assert not a3d.cleanup_interrupted(rt,rt.job,rt.ex)
    assert not (target/'cancel').exists()


def test_published_evidence_rejects_other_parent_and_changed_output(nested):
    rt,target,cmd=nested
    raw=b'diagnostic';r=receipt(rt,target,outputs={'output/stderr.txt':dict(size_bytes=len(raw),sha256=sha(raw))})
    request=json.loads((target/'request.json').read_bytes())
    ex=dict(status='failed',resident=dict(request=request,receipt=r))
    files={'input/a3d-structure.pdb':b'input','output/a3d-resident/stderr.txt':raw}
    a3d.validate(ex,files,rt.job)
    with pytest.raises(RuntimeFault):a3d.validate(ex,files,dict(rt.job,attempt_id='other'))
    files['output/a3d-resident/stderr.txt']=b'tampered'
    with pytest.raises(RuntimeFault):a3d.validate(ex,files,rt.job)
