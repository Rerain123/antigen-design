"""Real Linux process/lock/offline probe; deliberately does not load model weights."""
import concurrent.futures
import json
import os
from pathlib import Path
import time

from t01_phase1_real.resident_process import Command, prepare, run
from t01_phase1_real.development.esmfold2 import worker


def main():
    root=Path('/tmp/esmfold2-linux-probe');root.mkdir()
    code = '''import json,socket,time
for family in (socket.AF_INET,socket.AF_INET6):
 try:
  s=socket.socket(family,socket.SOCK_STREAM)
 except PermissionError: pass
 else: raise RuntimeError('INET socket was allowed')
start=time.monotonic();time.sleep(0.3)
print(json.dumps(dict(start=start,end=time.monotonic())))
'''
    command=Command('esmfold2',('/usr/local/bin/python','-B','-c',code),tuple(sorted(dict(
        T01_RESIDENT_OFFLINE='1',T01_SHARED_GPU_LOCK=str(root/'gpu.lock')).items())),256*1024**3)
    targets=[]
    for i in (1,2):
        folder=root/str(i);folder.mkdir()
        target=prepare(folder, str(i)*32, dict(job_id='job-'+str(i),attempt_id='attempt-'+str(i),execution_identity='exec-'+str(i)),
                       command,{'input.json':b'{}'},10)
        targets.append(folder/(str(i)*32))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(run,t,command) for t in targets]
        results=[f.result() for f in futures]
    assert all(r['state']=='succeeded' and r['stopped_confirmed'] for r in results),results
    intervals=sorted(
        [json.loads((t/'output/stdout.txt').read_bytes()) for t in targets],key=lambda r:r['start'])
    assert intervals[0]['end'] <= intervals[1]['start'],intervals
    print('ESMFOLD2_LINUX_IMPORT_OFFLINE_GPU_LOCK_PASS',json.dumps(intervals))


if __name__=='__main__':main()
