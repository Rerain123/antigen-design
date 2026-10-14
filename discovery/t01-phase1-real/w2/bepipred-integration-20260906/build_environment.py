"""Build dependency image separately from offline inference, retaining exact reports."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import time

BASE=Path(__file__).parent
ENV=BASE/'environment'
REPO=BASE.parents[3]
DOCKER=['docker','--config',str(REPO/'var/t01-phase1-real/structure-demo/docker-client'),'--host','npipe:////./pipe/dockerDesktopLinuxEngine']
TAG='t01-bepipred-development:3.0-bp3-0.0.12.7-20260906'
package=REPO/'var/t01-phase1-real/tool-assets/bepipred-3.0-98bedf2471e0'
with (ENV/'requirements.txt').open('xb') as stream:stream.write((package/'requirements.txt').read_bytes())
with (ENV/'bp3-0.0.12.7-py2.py3-none-any.whl').open('xb') as stream:stream.write((BASE/'bp3-0.0.12.7-py2.py3-none-any.whl').read_bytes())
command=DOCKER+['build','--progress','plain','--tag',TAG,str(ENV)]
start=time.monotonic()
with (ENV/'build.stdout').open('xb') as out,(ENV/'build.stderr').open('xb') as err:
    run=subprocess.run(command,stdout=out,stderr=err)
value=dict(command=command,completed_at=datetime.now(timezone.utc).isoformat(),exit_code=run.returncode,elapsed_seconds=time.monotonic()-start,model_execution='NOT_RUN_DURING_BUILD')
if run.returncode==0:
    raw=subprocess.run(DOCKER+['image','inspect',TAG],capture_output=True,check=True).stdout
    (ENV/'image-inspect.json').write_bytes(raw);value['image_id']=json.loads(raw)[0]['Id']
    for name in ['torch-install-report.json','dependency-install-report.json','python-freeze.txt','system-packages.txt']:
        result=subprocess.run(DOCKER+['run','--rm','--network','none','--read-only','--cap-drop','ALL','--entrypoint','cat',value['image_id'],'/'+name],capture_output=True,check=True)
        (ENV/name).write_bytes(result.stdout)
(ENV/'build.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
print(json.dumps(value),flush=True)
