"""Read pinned upstream MSA branch and archived input metadata; no model call."""
import json
import subprocess
import prepare_m1_p1_deploy as common
from version_bundle import encode

OUT=common.ROOT/'reports/msa-scan-20260928'
CODE=r'''
import hashlib,json
from pathlib import Path
out=[]
for path in Path('/opt/t01/af3-app/alphafold').rglob('pipeline.py'):
    if 'alphafold3/data/pipeline.py' not in path.as_posix():continue
    lines=path.read_text().splitlines();selected={}
    for i,line in enumerate(lines):
        if 'unpaired_msa' in line or 'paired_msa' in line:
            for j in range(max(0,i-3),min(len(lines),i+9)):selected[j+1]=lines[j]
    out.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),msa_lines=selected))
assert out
print(json.dumps(dict(af3_upstream=out,models_executed=False)))
'''

if __name__=='__main__':
    raw=subprocess.check_output(common.K+['exec','deployment/antigen-design','-c','worker-unified-gpu',
        '--','/opt/t01/supervisor/bin/python3.11','-B','-c',CODE])
    value=json.loads(raw);(OUT/'upstream-inspection.json').write_bytes(encode(value))
    print(json.dumps(value))
