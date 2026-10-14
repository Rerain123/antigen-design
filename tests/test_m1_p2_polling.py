import ast
import importlib.util
import json
from pathlib import Path
import sys
import io
import contextlib
import pytest

scripts=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(scripts))
spec=importlib.util.spec_from_file_location('p2_probe',scripts/'run_m1_p2_probe.py')
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.mark.parametrize('state',['running','reconciling','stop_requested'])
def test_polling_reconciles_every_active_execution_state(state):
    class Runtime:
        calls=[]
        def get(self,jid):
            return dict(job_id=jid,state='succeeded' if self.calls else state,
                        tool_id='t01.real.foldx',artifacts=[])
        def reconcile(self,jid):self.calls.append(jid)
        def _request_bytes(self,job):return b'{"timeout_seconds":14400}'
    rt=Runtime()
    tree=ast.parse(probe.PREAMBLE)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='export')
    scope=dict(rt=rt,decode=json.loads,TERMINAL={'succeeded','failed','cancelled','timed_out'})
    exec(compile(ast.Module(body=[function],type_ignores=[]),'p2-export','exec'),scope)
    row=scope['export'](dict(job_id='same-job'))
    assert rt.calls==['same-job'] and row['job']['state']=='succeeded'


@pytest.mark.parametrize('corrupt',[False,True])
def test_large_result_transport_preserves_bytes_and_rejects_corruption(monkeypatch,corrupt):
    def remote(code,payload):
        with monkeypatch.context() as patch:
            patch.setattr(sys,'stdin',io.StringIO(json.dumps(payload)))
            out=io.StringIO()
            with contextlib.redirect_stdout(out):exec(code,{})
        result=json.loads(out.getvalue())
        if corrupt:result['sha256']='0'*64
        return result
    monkeypatch.setattr(probe._deployment,'remote',remote)
    body={'fact':'真实值'*100000,'missing':None}
    code='import sys,json;print(json.dumps(json.load(sys.stdin),ensure_ascii=False))'
    if corrupt:
        with pytest.raises(ValueError,match='hash mismatch'):probe.compressed_remote(code,body)
    else:assert probe.compressed_remote(code,body)==body
