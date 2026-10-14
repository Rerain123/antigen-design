"""Actual dispatcher death and CLI coverage, separate from injected result faults."""
import subprocess
import sys
import time
from pathlib import Path
from t01_phase1_real.common import REPO,encode,decode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.codon import policy
from t01_phase1_real import winprocess as wp

def body():
    return dict(protein_sequence='AAAAAKKK',user_sequence_id='independent lifecycle engineering fragment',expression_host='E.coli',
        host_profile=policy.PROFILE,coding_policy=policy.CODING,input_kind='INDEPENDENT_ENGINEERING_SEQUENCE',timeout_seconds=60)

def test_actual_dispatcher_death_stops_owned_tree_and_recovers(tmp_path):
    rt=Runtime(tmp_path/'runtime');j=rt.submit_sequence(encode(body()),'crash',policy.TOOL)
    helper=tmp_path/'dispatcher.py'
    helper.write_text('import sys\nsys.path.insert(0,sys.argv[1])\nfrom t01_phase1_real.development import Runtime\n'
        'rt=Runtime(sys.argv[2]);rt._development_fault="hold_worker"\nrt.dispatch(sys.argv[3])\n',encoding='utf-8')
    child=subprocess.Popen([sys.executable,'-X','utf8',str(helper),str(REPO/'src'),str(rt.root),j['job_id']],
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline=time.monotonic()+20;ex={}
        while time.monotonic()<deadline:
            ex=rt.execution(j['job_id'])
            if ex.get('worker_started'):break
            time.sleep(.05)
        assert ex.get('worker_started')
        h=wp.ok(wp.OpenProcess(0x1000|0x100000|1,False,ex['dispatcher']['pid']))
        try:
            assert wp.birth(h)==ex['dispatcher']['birth'];wp.ok(wp.TerminateProcess(h,1))
        finally:wp.Close(h)
        child.wait(10)
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            rt.recover(j['job_id'])
            if rt.get(j['job_id'])['state']=='failed':break
            time.sleep(.05)
        assert rt.get(j['job_id'])['error_code']=='INTERRUPTED'
        assert wp.inspect_job(ex['job_object'])==0 and rt.result(j['job_id'])['dna'] is None
        retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=j['job_id'],idempotency_key='retry')))
        assert rt.dispatch(retry['job_id'])['state']=='succeeded'
    finally:
        if child.poll() is None:child.terminate();child.wait(10)

def test_cli_submit_and_hash_verified_query(tmp_path):
    request=tmp_path/'request.json';request.write_bytes(encode(body()));root=tmp_path/'runtime'
    cmd=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root)]
    result=subprocess.run(cmd+['optimize-codons','--input',str(request),'--key','cli','--run'],capture_output=True,check=True)
    v=decode(result.stdout);assert v['job']['state']=='succeeded'
    queried=subprocess.run(cmd+['result','--job-id',v['job']['job_id']],capture_output=True,check=True)
    assert decode(queried.stdout)==v['result']
