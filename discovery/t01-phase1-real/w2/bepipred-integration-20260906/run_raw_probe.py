"""Actual unchanged CLI run before uniform adapter admission; fixed offline resource policy."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

BASE=Path(__file__).parent;REPO=BASE.parents[3]
IMAGE=json.loads((BASE/'environment/build.json').read_bytes())['image_id']
PACKAGE=REPO/'var/t01-phase1-real/tool-assets/bepipred-3.0-98bedf2471e0'
MODELS=REPO/'var/t01-phase1-real/tool-assets/bepipred-esm2-650m'
DOCKER=['docker','--config',str(REPO/'var/t01-phase1-real/structure-demo/docker-client'),'--host','npipe:////./pipe/dockerDesktopLinuxEngine']
name=sys.argv[1];seq=sys.argv[2];folder=BASE/'raw-runs'/name
folder.mkdir(parents=True,exist_ok=False);(folder/'output').mkdir()
ident='t01seq_'+hashlib.sha256(seq.encode()).hexdigest()
(folder/'input.fasta').write_text('>'+ident+'\n'+seq+'\n',encoding='utf-8')
argv=DOCKER+['create','--pull','never','--name','t01p1r-bepipred-raw-probe','--network','none','--read-only','--cap-drop','ALL',
    '--security-opt','no-new-privileges','--pids-limit','512','--memory','10g','--memory-swap','10g','--cpus','8','--cpuset-cpus','0-7',
    '--tmpfs','/tmp:rw,noexec,nosuid,size=512m','--env','TORCH_HOME=/torch','--env','CUDA_VISIBLE_DEVICES=-1',
    '--mount',f'type=bind,source={PACKAGE},target=/app,readonly',
    '--mount',f'type=bind,source={MODELS},target=/torch/hub/checkpoints,readonly',
    '--mount',f'type=bind,source={REPO/"src/t01_phase1_real/development/bepipred/worker.py"},target=/probe.py,readonly',
    '--mount',f'type=bind,source={folder/"input.fasta"},target=/input.fasta,readonly',
    '--mount',f'type=bind,source={folder/"output"},target=/out','--workdir','/app','--entrypoint','timeout',IMAGE,
    '--signal=KILL','180','python','-B','/probe.py']
(folder/'command.json').write_text(json.dumps(argv,indent=2),encoding='utf-8')
created=subprocess.run(argv,capture_output=True);assert created.returncode==0,created.stderr
cid=created.stdout.decode().strip();start=time.monotonic()
subprocess.run(DOCKER+['start',cid],check=True,capture_output=True)
wait=subprocess.run(DOCKER+['wait',cid],capture_output=True,timeout=210)
inspect=subprocess.run(DOCKER+['inspect',cid],capture_output=True,check=True)
(folder/'inspect.json').write_bytes(inspect.stdout)
info=json.loads(inspect.stdout)[0];assert not info['State']['Running']
logs=subprocess.run(DOCKER+['logs',cid],capture_output=True)
(folder/'stdout.txt').write_bytes(logs.stdout);(folder/'stderr.txt').write_bytes(logs.stderr)
subprocess.run(DOCKER+['rm',cid],capture_output=True,check=True)
receipt=dict(image=IMAGE,sequence_length=len(seq),container_id=cid,exit_code=info['State']['ExitCode'],oom_killed=info['State']['OOMKilled'],elapsed_seconds=time.monotonic()-start,
    files={p.relative_to(folder).as_posix():dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in folder.rglob('*') if p.is_file()})
(folder/'index.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k!='files'}),flush=True)
