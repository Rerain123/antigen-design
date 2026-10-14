"""Read only deployed ESMFold2 package hashes, without environment/credentials."""
import json
import subprocess
import hashlib
import run_m1_p2_probe as p

def main():
    rows={}
    code="import pathlib,hashlib,json;root=pathlib.Path(__import__('sys').argv[1]);print(json.dumps({q.name:hashlib.sha256(q.read_bytes()).hexdigest() for q in root.iterdir() if q.suffix in ('.py','.json')}))"
    for container,interpreter,root in (
        ('service','python','/app/src/t01_phase1_real/development/esmfold2'),
        ('worker-unified-gpu','/opt/t01/supervisor/bin/python3.11','/backend/t01_phase1_real/development/esmfold2')):
        raw=subprocess.check_output(p.deploy.K+['exec','deployment/antigen-design','-c',container,'--',interpreter,'-B','-c',code,root])
        rows[container]=json.loads(raw)
    rows['local']={q.name:hashlib.sha256(q.read_bytes()).hexdigest() for q in (p.ROOT/'src/t01_phase1_real/development/esmfold2').iterdir() if q.suffix in ('.py','.json')}
    differences={n:{k:v.get(n) for k,v in rows.items()} for n in set().union(*(v.keys() for v in rows.values())) if len({v.get(n) for v in rows.values()})>1}
    p.save('esmfold2-profile-inspection.json',dict(packages=rows,differences=differences,status='PASS' if not differences else 'MISMATCH'))
    print(json.dumps(differences,indent=2))
    if differences:raise SystemExit(1)

if __name__=='__main__':main()
