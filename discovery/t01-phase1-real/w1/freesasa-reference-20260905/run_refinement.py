"""Run one additional independent-reference density, preserving initial evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

BATCH=Path(__file__).resolve().parent
endpoint=subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip()
if endpoint!='npipe:////./pipe/dockerDesktopLinuxEngine':
    raise SystemExit('Expected the inspected local Docker Desktop engine')
image_id=json.loads((BATCH/'run/execution.json').read_text())['image_id']
output=BATCH/'refinement'; output.mkdir(exist_ok=False)
name='t01-freesasa-refinement-'+uuid.uuid4().hex[:12]
command=['docker','run','--rm','--name',name,'--network','none','--read-only','--cap-drop','ALL',
         '--security-opt','no-new-privileges','--cpus','2','--memory','1g','--pids-limit','64']
for source,target in [(BATCH/'run/result','/initial'),(BATCH/'compare_reference.py','/compare_reference.py'),
                      (BATCH/'refine_reference.py','/refine_reference.py'),(BATCH/'reference_spec.json','/reference_spec.json'),
                      (BATCH/'refinement_spec.json','/refinement_spec.json')]:
    command+=['--mount',f'type=bind,source={source},target={target},readonly']
command+=['--mount',f'type=bind,source={output},target=/out',image_id,'python','-B','/refine_reference.py']
start=datetime.now(timezone.utc).isoformat(); timer=time.perf_counter(); timed_out=False
try:
    process=subprocess.run(command,capture_output=True,timeout=240)
    stdout,stderr,code=process.stdout,process.stderr,process.returncode
except subprocess.TimeoutExpired as error:
    timed_out=True; stdout,stderr,code=error.stdout or b'',error.stderr or b'',None
    subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)
(output/'stdout.txt').write_bytes(stdout); (output/'stderr.txt').write_bytes(stderr)
record={'command':command,'docker_endpoint':endpoint,'image_id':image_id,'started_at':start,
        'finished_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.perf_counter()-timer,'exit_code':code,
        'timed_out':timed_out,'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scientific_approval':None,'production_status':'NOT_DEPLOYED'}
(output/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
print(stdout.decode(errors='replace')); print(stderr.decode(errors='replace'))
raise SystemExit(code if code is not None else 124)
