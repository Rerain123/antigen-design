"""Linux-only real process stop and stale-identity adversarial regression."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

spec=importlib.util.spec_from_file_location('posix_control',Path(__file__).resolve().parents[1]/'src/t01_phase1_real/process_control/posix.py')
posix=importlib.util.module_from_spec(spec);spec.loader.exec_module(posix)
posix.REGISTRY=Path(tempfile.mkdtemp(prefix='t01-stop-probe-'))
job=posix.Job('real-owned');process=posix.Process([sys.executable,'-c','import time;time.sleep(60)'],'/tmp',job)
process.resume();original=job.path.read_bytes();record=json.loads(original)
record['leader']['birth']='expired';job.path.write_text(json.dumps(record))
try:
    job.stop()
except OSError:pass
else:raise AssertionError('Stale identity was accepted')
assert posix.alive(process.identity) is True
job.path.write_bytes(original)
# Prove that the new implementation does not use numeric process-group kill.
def forbidden(*args):raise AssertionError('killpg must never be used')
os.killpg=forbidden
job.stop()
for _ in range(100):
    process.poll()
    if job.active()==0:break
    time.sleep(.02)
assert job.active()==0 and posix.alive(process.identity) is False
print(json.dumps(dict(stale_identity_refused=True,unrelated_process_survived=True,pidfd_stop_verified=True,active_after_stop=0)))
