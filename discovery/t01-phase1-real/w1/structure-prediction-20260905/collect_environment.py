"""Read a scoped development profile; no services/settings or assets are changed."""
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

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]
DOCKER = ['docker','--host','npipe:////./pipe/dockerDesktopLinuxEngine']


def run(command):
    started = time.monotonic()
    record = dict(command=command)
    try:
        completed = subprocess.run(command,capture_output=True,timeout=40)
        def decode(value):
            return value.decode('utf-16-le' if b'\0' in value[:80] else 'utf-8',errors='replace')
        record.update(exit_code=completed.returncode,stdout=decode(completed.stdout),stderr=decode(completed.stderr))
    except (OSError,subprocess.TimeoutExpired) as exc:
        record.update(error=str(exc))
    record['elapsed_seconds'] = time.monotonic()-started
    return record


if __name__ == '__main__':
    target = BATCH/'environment.json'
    if target.exists():
        raise FileExistsError('Preserve existing profile')
    script = "import json,shutil,sys;from importlib import metadata;print(json.dumps({'python':sys.version,'commands':{n:shutil.which(n) for n in ['run_alphafold.py','esm-fold','jackhmmer','nhmmer']},'packages':{d.metadata['Name']:d.version for d in metadata.distributions() if any(t in d.metadata['Name'].lower() for t in ['alphafold','esm','torch','jax'])}}))"
    commands = [
        DOCKER+['version','--format','{{json .Server}}'],
        DOCKER+['info','--format','{"cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}},"os":"{{.OSType}}","architecture":"{{.Architecture}}"}'],
        DOCKER+['image','ls','--no-trunc','--format','{{json .}}'],
        ['nvidia-smi','--query-gpu=name,memory.total,memory.free,driver_version,compute_cap','--format=csv,noheader'],
        ['powershell','-NoProfile','-Command','Get-CimInstance Win32_OperatingSystem | Select-Object Caption,TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json -Compress'],
        ['powershell','-NoProfile','-Command','Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress'],
        ['wsl','--list','--verbose'],
        ['wsl','-d','Ubuntu','--exec','python3','-c',script],
        ['rg','--files','-g','*alphafold*','-g','*esmfold*','-g','*ESMFold*','-g','*AF3*','-g','!工具部署/**','-g','!.venv/**','-g','!legacy/**','-g','!.git/**','.'],
    ]
    observations = [run(command) for command in commands]
    expert = ROOT/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
    result = dict(recorded_at=datetime.now(timezone.utc).isoformat(),scope='LOCAL_DEVELOPMENT_NOT_CUSTOMER_SERVER',
                  platform=platform.platform(),python=sys.version,
                  python_packages={d.metadata['Name']:d.version for d in metadata.distributions() if any(t in d.metadata['Name'].lower() for t in ['alphafold','esm','torch','jax'])},
                  commands={n:shutil.which(n) for n in ['docker','wsl','nvidia-smi','run_alphafold.py','esm-fold','jackhmmer','nhmmer']},
                  disks={drive:dict(zip(['total','used','free'],shutil.disk_usage(drive))) for drive in ['C:/','D:/']},
                  observations=observations,
                  expert_sources_before={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(expert.iterdir()) if p.is_file()},
                  limitations=['No complete disk scan','Independent 工具部署 project and unrelated containers not inspected','No customer server profile supplied','GPU container compute compatibility not proven by nvidia-smi'],
                  model_execution='NOT_RUN',production_status='NOT_DEPLOYED')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'observations':len(observations),'failed':[r for r in observations if r.get('exit_code',1) not in (0,1)],'model_execution':'NOT_RUN'}))
