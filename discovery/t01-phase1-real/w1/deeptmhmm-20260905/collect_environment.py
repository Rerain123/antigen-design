"""Read scoped local environment facts; never submit sequences or start prediction jobs."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

BATCH=Path(__file__).resolve().parent
ROOT=BATCH.parents[3]


def run(command,timeout=30):
    start=datetime.now(timezone.utc).isoformat(); timer=time.perf_counter()
    try:
        p=subprocess.run(command,capture_output=True,timeout=timeout)
        def decode(data):
            return data.decode('utf-16-le' if b'\x00' in data[:80] else 'utf-8',errors='replace')
        return {'command':command,'started_at':start,'elapsed_seconds':time.perf_counter()-timer,
                'exit_code':p.returncode,'stdout':decode(p.stdout),'stderr':decode(p.stderr)}
    except (OSError,subprocess.TimeoutExpired) as error:
        return {'command':command,'started_at':start,'elapsed_seconds':time.perf_counter()-timer,'exit_code':None,'error':str(error)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(); output=args.output_dir.resolve()
    if not output.is_relative_to(ROOT): raise SystemExit('Output must be inside project')
    output.mkdir(exist_ok=False)
    expert=ROOT/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
    source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(expert.iterdir()) if p.is_file()}
    commands=[['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],
              ['docker','version','--format','{{json .Server}}'],
              ['docker','info','--format','{"cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}},"os":"{{.OSType}}","architecture":"{{.Architecture}}"}'],
              ['docker','image','ls','--no-trunc','--format','{{json .}}'],
              ['docker','ps','--format','{{.Names}} {{.Image}} {{.Status}}'],
              ['wsl','--list','--verbose'],
              ['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader']]
    records=[run(command) for command in commands]
    endpoint=records[0].get('stdout','').strip()
    if endpoint!='npipe:////./pipe/dockerDesktopLinuxEngine':
        (output/'failed_preflight.json').write_text(json.dumps(records,indent=2)+'\n')
        raise SystemExit('Local Docker Desktop context was not verified')
    linux_probe="import json,shutil,sys; from importlib import metadata; print(json.dumps({'python':sys.version,'commands':{n:shutil.which(n) for n in ['biolib','deeptmhmm','dtu_protein_predict']},'packages':{d.metadata['Name']:d.version for d in metadata.distributions() if any(t in d.metadata['Name'].lower() for t in ['biolib','deeptm','torch'])}}))"
    records.append(run(['wsl','-d','Ubuntu','--exec','python3','-c',linux_probe]))
    result={'scope':'LOCAL_DEVELOPMENT_NOT_CUSTOMER_TARGET','recorded_at':datetime.now(timezone.utc).isoformat(),
            'python':sys.version,'platform':platform.platform(),
            'commands':{n:shutil.which(n) for n in ['docker','wsl','nvidia-smi','biolib','deeptmhmm','dtu_protein_predict']},
            'python_packages':{d.metadata['Name']:d.version for d in metadata.distributions() if any(t in d.metadata['Name'].lower() for t in ['biolib','deeptm','torch'])},
            'disks':{drive:dict(zip(['total','used','free'],shutil.disk_usage(drive))) for drive in ['C:/','D:/']},
            'observations':records,'expert_sources_before':source_hashes,
            'collector_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'limitations':['No customer server access/profile supplied','No search inside unrelated Docker images or independent deployment project','No license entitlement inferred from package availability'],
            'model_execution':'NOT_RUN','production_status':'NOT_DEPLOYED'}
    (output/'environment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'COLLECTED','observations':len(records),'expert_files':len(source_hashes),'local_python_packages':result['python_packages'],'model_execution':'NOT_RUN'}))


if __name__=='__main__': main()
