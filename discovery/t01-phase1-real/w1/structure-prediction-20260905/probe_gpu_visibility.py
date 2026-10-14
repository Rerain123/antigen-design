"""GPU visibility only using an existing fixed image; no model or tensor computation."""
import json
from pathlib import Path
import subprocess
import time

BATCH = Path(__file__).resolve().parent
DOCKER = ['docker','--host','npipe:////./pipe/dockerDesktopLinuxEngine']

if __name__ == '__main__':
    target = BATCH/'gpu_visibility.json'
    if target.exists():
        raise FileExistsError(target)
    image = json.loads((BATCH.parent/'deeptmhmm-academic-20260905/environment/build.json').read_text())['image_id']
    command = DOCKER+['run','--rm','--pull','never','--network','none','--read-only','--cap-drop','ALL',
        '--security-opt','no-new-privileges','--pids-limit','64','--memory','256m','--cpus','1','--gpus','all',
        '--entrypoint','nvidia-smi',image,'--query-gpu=name,memory.total,driver_version,compute_cap','--format=csv,noheader']
    started = time.monotonic()
    result = subprocess.run(command,capture_output=True,text=True,timeout=40)
    record = dict(command=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr,
                  elapsed_seconds=time.monotonic()-started,model_execution='NOT_RUN',
                  interpretation='GPU visibility only; no JAX/PyTorch kernel compatibility or scientific numerical validation')
    target.write_text(json.dumps(record,indent=2))
    print(json.dumps(record))
