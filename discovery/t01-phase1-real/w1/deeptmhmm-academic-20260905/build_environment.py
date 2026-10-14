"""Build only the declared dependency environment; do not execute the supplied model or upload its package."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import time

BATCH=Path(__file__).resolve().parent
ENV=BATCH/'environment'
DOCKER=['docker','--host','npipe:////./pipe/dockerDesktopLinuxEngine']
TAG='t01-deeptmhmm-academic:1.0-cpu-20260905'


def main():
    record=ENV/'build.json'
    if record.exists() or (ENV/'build.stdout').exists():raise SystemExit('Use a new build attempt directory instead of overwriting logs')
    original=BATCH/'package_sources/requirements.txt'
    (ENV/'requirements.txt').write_bytes(original.read_bytes())
    command=DOCKER+['build','--progress','plain','--tag',TAG,str(ENV)]
    started=datetime.now(timezone.utc).isoformat();timer=time.perf_counter()
    with (ENV/'build.stdout').open('wb') as stdout,(ENV/'build.stderr').open('wb') as stderr:
        result=subprocess.run(command,stdout=stdout,stderr=stderr)
    data={'command':command,'started_at':started,'elapsed_seconds':time.perf_counter()-timer,
          'exit_code':result.returncode,'image_tag':TAG,'model_execution':'NOT_RUN_DURING_DEPENDENCY_BUILD'}
    if result.returncode==0:
        inspect=subprocess.run(DOCKER+['image','inspect',TAG],capture_output=True,check=True)
        (ENV/'image-inspect.json').write_bytes(inspect.stdout)
        data['image_id']=json.loads(inspect.stdout)[0]['Id']
        for name in ['torch-install-report.json','dependency-install-report.json','python-freeze.txt','system-packages.txt']:
            fetch=subprocess.run(DOCKER+['run','--rm','--network','none','--read-only','--cap-drop','ALL',
                                  '--entrypoint','cat',data['image_id'],'/'+name],capture_output=True,check=True)
            (ENV/name).write_bytes(fetch.stdout)
    record.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data))
    return result.returncode


if __name__=='__main__':raise SystemExit(main())
