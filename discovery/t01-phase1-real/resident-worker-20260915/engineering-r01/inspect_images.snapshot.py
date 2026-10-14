import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from t01_phase1_real.deployment.kubernetes import SCIENTIFIC_SOURCE_IMAGE_IDS

DOCKER = r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
PROBE = '''import json,sys,platform
try:
 import importlib.metadata as m
 packages={d.metadata['Name'].lower().replace('_','-'):d.version for d in m.distributions()}
except ImportError:
 import pkg_resources
 packages={d.key:d.version for d in pkg_resources.working_set}
print(json.dumps(dict(python=platform.python_version(),executable=sys.executable,packages=packages),sort_keys=True))
'''

def inspect(item):
    name, image = item
    info = json.loads(subprocess.check_output([DOCKER,'image','inspect',image], text=True))[0]
    executable = '/opt/conda/bin/python' if name == 'aggrescan3d' else 'python3' if name in ('blast','foldx') else 'python'
    run = subprocess.run([DOCKER,'run','--rm','--network','none','--read-only','--cap-drop','ALL',
        '--security-opt','no-new-privileges','--user','10001:10001','--pids-limit','64','--memory','512m',
        '--entrypoint',executable,image,'-B','-c',PROBE],capture_output=True,text=True,timeout=90)
    result = dict(tool=name,image=info['Id'],size=info['Size'],layers=info['RootFS']['Layers'],
                  architecture=info['Architecture'],os=info['Os'],exit_code=run.returncode)
    if run.returncode == 0: result['environment'] = json.loads(run.stdout)
    else: result['diagnostic'] = (run.stdout+run.stderr)[-2000:]
    print(name,run.returncode,flush=True)
    return result

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    rows=list(pool.map(inspect,SCIENTIFIC_SOURCE_IMAGE_IDS.items()))
Path(__file__).with_name('image-environments.json').write_text(json.dumps(rows,indent=2,sort_keys=True),encoding='utf-8')
for row in rows:
    env=row.get('environment',{})
    print(json.dumps(dict(tool=row['tool'],python=env.get('python'),
        packages={k:v for k,v in env.get('packages',{}).items() if k in ('torch','numpy','scipy','fair-esm','pytorch-lightning','torch-geometric','biopython')},
        error=row.get('diagnostic')),sort_keys=True))
