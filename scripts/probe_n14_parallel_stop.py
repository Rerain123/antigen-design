"""Bounded Linux process-tree cancellation of two concurrent FoldX-shaped children."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.development.foldx import policy
from t01_phase1_real.common import encode

CODE=r'''
import importlib.util,json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,'/project/src')
spec=importlib.util.spec_from_file_location('posix_control','/project/src/t01_phase1_real/process_control/posix.py')
posix=importlib.util.module_from_spec(spec);spec.loader.exec_module(posix)
root=Path(tempfile.mkdtemp());posix.REGISTRY=root/'registry';posix.REGISTRY.mkdir()
child_code="""
import concurrent.futures,sys
from pathlib import Path
sys.path.insert(0,'/project/src')
from t01_phase1_real.development.foldx import worker
worker.OUT=Path(sys.argv[1])
native="import os,time; print('native-running',flush=True); time.sleep(60)"
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 list(pool.map(lambda i:worker.run([sys.executable,'-c',native],worker.OUT,str(i)+'.txt'),range(2)))
"""
job=posix.Job('parallel-owned')
process=posix.Process([sys.executable,'-c',child_code,str(root)],'/tmp',job);process.resume()
for _ in range(200):
 if all((root/(str(i)+'.txt')).exists() and b'native-running' in (root/(str(i)+'.txt')).read_bytes() for i in range(2)):break
 time.sleep(.05)
else:raise AssertionError('Both parallel children did not start')
job.stop();unconfirmed=0
for _ in range(100):
 process.poll()
 # SIGKILL delivery is asynchronous; expired leader + still exiting children
 # must remain unconfirmed rather than being counted as a successful stop.
 try:
  if job.active()==0:break
 except OSError:unconfirmed+=1
 time.sleep(.02)
assert job.active()==0 and posix.alive(process.identity) is False
assert all(b'native-running' in (root/(str(i)+'.txt')).read_bytes() for i in range(2))
print(json.dumps(dict(status='PASS',parallel_children_started=2,active_after_stop=0,partial_logs_retained=True,transient_unconfirmed_polls=unconfirmed,scientific_tasks=0)))
'''

if __name__=='__main__':
    out=ROOT/'reports/n14-performance-20260928'
    done=subprocess.run(['docker','run','--rm','--network','none','--cpus','2','--memory','512m',
        '--mount',f'type=bind,source={ROOT},target=/project,readonly','--entrypoint','python',policy.IMAGE,'-B','-c',CODE],
        capture_output=True,timeout=60)
    suffix='r02'
    (out/f'parallel-stop-{suffix}.stdout.txt').write_bytes(done.stdout);(out/f'parallel-stop-{suffix}.stderr.txt').write_bytes(done.stderr)
    if done.returncode:raise RuntimeError(done.stderr.decode(errors='replace')[-2500:])
    value=json.loads(done.stdout);(out/'parallel-stop.json').write_bytes(encode(value));print(value)
