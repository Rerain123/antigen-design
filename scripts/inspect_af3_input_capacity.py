"""Read-only live AF3 resource/source inspection, without model invocation."""
import json
import subprocess
import prepare_m1_p1_deploy as common


def inspect():
    code='''import json,hashlib
from pathlib import Path
p=Path('/opt/t01/af3-app/alphafold/run_alphafold.py')
lines=p.read_text().splitlines()
selected={}
for i,line in enumerate(lines):
    if 'bucket' in line.lower():
        for j in range(max(0,i-1),min(len(lines),i+9)):selected[j+1]=lines[j]
print(json.dumps(dict(source_path=str(p),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                     bucket_lines=selected)))
'''
    raw=subprocess.check_output(common.K+['exec','deployment/antigen-design','-c','worker-unified-gpu',
        '--','/opt/t01/supervisor/bin/python3.11','-B','-c',code])
    result=json.loads(raw)
    result['previous_source_profile']=common.remote('''import json
from t01_phase1_real.development.af3 import policy
from t01_phase1_real.common import sha
print(json.dumps(dict(profile=policy.registered_profile(),
    source_sha256={p.name:sha(p.read_bytes()) for p in policy.HERE.iterdir() if p.suffix in ('.py','.json')})))
''')
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    worker=next(c for c in live['spec']['template']['spec']['containers'] if c['name']=='worker-unified-gpu')
    result.update(resources=worker['resources'],native_new_task_started=False,
                  conclusion='76 aa is a project admission cap, not a native AF3 bucket or model cap')
    path=common.ROOT/'reports/n12-validation-20260926/af3-input-inspection.json'
    with path.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result))


if __name__=='__main__':inspect()
