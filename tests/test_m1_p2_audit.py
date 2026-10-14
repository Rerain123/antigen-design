import copy
import importlib.util
import sys
from pathlib import Path


scripts=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(scripts))
spec=importlib.util.spec_from_file_location('p2_audit',scripts/'audit_m1_p2.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
scope={}
exec(module.EXECUTION_CHECKS,scope)
check=scope['execution_checks']


def fixture():
    jobs={str(i):dict(started_at=f'2026-09-21T00:0{i}:00Z',finished_at=f'2026-09-21T00:0{i}:30Z',
        state='succeeded',stopped=True,resident_stopped=True,backend='resident-process') for i in range(4)}
    return jobs,dict.fromkeys(jobs,{}),dict.fromkeys(jobs,'seccomp-local-sockets-only-v1')


def test_gpu_overlap_or_unconfirmed_stop_cannot_pass_audit():
    jobs,native,offline=fixture()
    assert all(check(jobs,native,offline).values())
    overlap=copy.deepcopy(jobs)
    overlap['1']['started_at']=jobs['0']['started_at']
    assert not check(overlap,native,offline)['serial_gpu_intervals']
    jobs['0']['resident_stopped']=False
    assert not check(jobs,native,offline)['serial_gpu_intervals']


def test_missing_gpu_execution_or_offline_receipt_cannot_pass_audit():
    jobs,native,offline=fixture()
    del native['3']
    assert not check(jobs,native,offline)['required_real_gpu_jobs']
    del offline['2']
    assert not check(jobs,native,offline)['native_offline']
    assert not check({}, {}, {})['native_offline']
