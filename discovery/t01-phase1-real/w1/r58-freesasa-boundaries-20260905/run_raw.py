"""Run this declared case set in the existing pinned FreeSASA image, with networking disabled."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

BATCH=Path(__file__).resolve().parent
ROOT=BATCH.parents[3]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    output=parser.parse_args().output_dir.resolve()
    if not output.is_relative_to(ROOT) or output.exists():raise SystemExit('Use a new directory in this project')
    profile=ROOT/'docs/project/phase1/PHASE1_REAL_W1_FREESASA_PROFILE.json'
    image=json.loads(profile.read_text())['runtime']['image_id']
    docker=['docker','--host','npipe:////./pipe/dockerDesktopLinuxEngine']
    inspected=subprocess.run(docker+['image','inspect','--format','{{.Id}}',image],capture_output=True,check=True)
    if inspected.stdout.decode().strip()!=image:raise SystemExit('Unexpected image ID')
    output.mkdir(parents=True)
    name='t01-r58-sasa-'+uuid.uuid4().hex[:12]
    command=docker+['run','--rm','--pull','never','--name',name,'--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--cpus','2','--memory','1g','--pids-limit','64',
            '--mount',f'type=bind,source={BATCH/"prepared"},target=/cases,readonly',
            '--mount',f'type=bind,source={ROOT/"src/t01_structure_mapping"},target=/code/src/t01_structure_mapping,readonly',
            '--mount',f'type=bind,source={BATCH/"run_raw_worker.py"},target=/worker.py,readonly',
            '--mount',f'type=bind,source={profile},target=/profile.json,readonly',
            '--mount',f'type=bind,source={output},target=/out',image,'python','-B','/worker.py']
    start=datetime.now(timezone.utc).isoformat();timer=time.perf_counter();timeout=False
    try:
        result=subprocess.run(command,capture_output=True,timeout=60)
        stdout,stderr,code=result.stdout,result.stderr,result.returncode
    except subprocess.TimeoutExpired as error:
        timeout=True;stdout,stderr,code=error.stdout or b'',error.stderr or b'',None
        cleanup=subprocess.run(docker+['rm','--force',name],capture_output=True,timeout=20)
        (output/'timeout-cleanup.stdout').write_bytes(cleanup.stdout)
        (output/'timeout-cleanup.stderr').write_bytes(cleanup.stderr)
    (output/'stdout.txt').write_bytes(stdout);(output/'stderr.txt').write_bytes(stderr)
    sources=[ROOT/'src/t01_structure_mapping/probe.py',ROOT/'src/t01_structure_mapping/sasa_probe.py',BATCH/'run_raw_worker.py',profile]
    record={'started_at':start,'elapsed_seconds':time.perf_counter()-timer,'command':command,'image_id':image,
            'exit_code':code,'timed_out':timeout,'production_status':'NOT_DEPLOYED',
            'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (output/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
    print(stdout.decode(errors='replace'));print(stderr.decode(errors='replace'))
    return code if code is not None else 124


if __name__=='__main__':raise SystemExit(main())
