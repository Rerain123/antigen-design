"""Prepare a narrow immutable P1 overlay; never search for a server database."""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
K=['C:/Program Files/Docker/Docker/resources/bin/kubectl.exe','--kubeconfig',
   str(ROOT/'.tmp/himat.kubeconfig'),'--request-timeout=90s','-n','him-ws']
NAME='antigen-m1-p1-code-r01'
OUT=ROOT/'deploy/m1-p1/r01'
DATABASE=ROOT/'discovery/t01-phase1-real/w2/blast-integration-20260907/acceptance-r03/databases/engineering-n03'
DATABASE_ROOT='/var/lib/t01/m1-p1-test-data/blast'
FILES=('development/workflow/policy.py','development/workflow/service.py',
       'development/proteinmpnn/policy.py','development/wt_draft/policy.py',
       'development/wt_draft/compute.py','development/wt_draft/service.py',
       'development/epitope_map/policy.py','development/epitope_map/result.py',
       'development/glycosylation/result.py','development/domains/service.py',
       'development/local_delivery/policy.py','development/local_delivery/compute.py',
       'development/local_delivery/service.py')


def remote(code, payload=None):
    args=K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',code]
    p=subprocess.run(args,input=json.dumps(payload).encode() if payload is not None else b'',capture_output=True,timeout=110)
    if p.returncode:raise RuntimeError('Cluster operation failed: '+p.stderr.decode(errors='replace')[-1500:])
    return json.loads(p.stdout)


def idle():
    return remote("""import json,sqlite3
from pathlib import Path
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
active=[{'job_id':r['job_id'],'state':r['state']} for (raw,) in db.execute('SELECT data FROM jobs')
        if (r:=json.loads(raw))['state'] not in ('succeeded','failed','cancelled','timed_out')]
p=Path('/var/lib/t01/resident/unified-gpu/state.json')
print(json.dumps({'active_jobs':active,'gpu_state':json.loads(p.read_bytes()) if p.exists() else None}))
""")


def patch(live):
    if live['spec']['replicas']!=1 or live['spec']['strategy']!={'type':'Recreate'}:
        raise ValueError('Expected singleton Recreate')
    spec=live['spec']['template']['spec'];ops=[
        dict(op='test',path='/metadata/resourceVersion',value=live['metadata']['resourceVersion']),
        dict(op='test',path='/metadata/uid',value=live['metadata']['uid'])]
    targets={'/app/src/t01_phase1_real/'+p for p in FILES}
    for i,c in enumerate(spec['containers']):
        if c['name']=='service':
            mounts=[m for m in c['volumeMounts'] if m['mountPath'] not in targets]
            mounts += [dict(name='m1-p1-code',mountPath='/app/src/t01_phase1_real/'+p,
                            subPath=p.replace('/','--'),readOnly=True) for p in FILES]
            args=list(c['args'])
            if '--blast-database-root' in args:raise ValueError('Do not replace an existing operator database root')
            args+=['--blast-database-root',DATABASE_ROOT]
            ops += [dict(op='replace',path=f'/spec/template/spec/containers/{i}/volumeMounts',value=mounts),
                    dict(op='replace',path=f'/spec/template/spec/containers/{i}/args',value=args)]
        elif c['name']=='worker-blast':
            if any(m['mountPath']=='/t01/databases/blast' for m in c['volumeMounts']):
                raise ValueError('Do not replace an existing BLAST database mount')
            ops.append(dict(op='add',path=f'/spec/template/spec/containers/{i}/volumeMounts/-',value=dict(
                name='runtime',mountPath='/t01/databases/blast',subPath='m1-p1-test-data/blast',readOnly=True)))
    ops.append(dict(op='add',path='/spec/template/spec/volumes/-',value=dict(name='m1-p1-code',configMap=dict(name=NAME))))
    return ops


def stage_database():
    from t01_phase1_real.development.blast.policy import verify_database
    digest=hashlib.sha256((DATABASE/'manifest.json').read_bytes()).hexdigest()
    receipt=verify_database(DATABASE.parent,dict(database_id='engineering-n03',database_manifest_sha256=digest))
    payload={p.name:base64.b64encode(p.read_bytes()).decode() for p in DATABASE.iterdir() if p.is_file()}
    # Only this registered 50 KiB test package is copied. Existing differing bytes fail closed.
    result=remote("""import json,base64,sys,hashlib
from pathlib import Path
root=Path('/var/lib/t01/m1-p1-test-data/blast/engineering-n03')
root.mkdir(parents=True,exist_ok=True)
rows={}
for name,data in json.load(sys.stdin).items():
    assert Path(name).name==name
    raw=base64.b64decode(data,validate=True);path=root/name
    if path.exists():assert path.read_bytes()==raw
    else:
        with path.open('xb') as f:f.write(raw)
    rows[name]=hashlib.sha256(path.read_bytes()).hexdigest()
assert {p.name for p in root.iterdir()}==set(rows)
print(json.dumps({'status':'REGISTERED_MINIMAL_TEST_DATABASE_COPIED','sha256':rows,'target_database':False}))
""",payload)
    receipt.pop('mount_path')
    return dict(source=DATABASE.relative_to(ROOT).as_posix(),receipt=receipt,target=result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Apply the prepared, dry-run checked P1 rollout')
    args=parser.parse_args()
    state=idle()
    if state['active_jobs']:raise RuntimeError('Active tasks must finish before the rollout')
    if args.apply:
        subprocess.run(K+['apply','-f',str(OUT/'configmap.yaml')],check=True)
        subprocess.run(K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json')],check=True)
        print('M1_P1_ROLLOUT_SUBMITTED');return
    live=json.loads(subprocess.check_output(K+['get','deployment','antigen-design','-o','json']))
    operations=patch(live)
    database=stage_database()
    data={p.replace('/','--'):(ROOT/'src/t01_phase1_real'/p).read_text(encoding='utf-8') for p in FILES}
    cm=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),immutable=True,data=data)
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'configmap.yaml').write_text(yaml.safe_dump(cm,sort_keys=False),encoding='utf-8')
    (OUT/'deployment.patch.json').write_text(json.dumps(operations,indent=2)+'\n',encoding='utf-8')
    (OUT/'preflight.json').write_text(json.dumps(dict(database=database,idle=state,
        before_generation=live['metadata']['generation'],before_resource_version=live['metadata']['resourceVersion'],
        source_hashes={p:hashlib.sha256((ROOT/'src/t01_phase1_real'/p).read_bytes()).hexdigest() for p in FILES}),indent=2)+'\n',encoding='utf-8')
    subprocess.run(K+['apply','--dry-run=server','-f',str(OUT/'configmap.yaml')],check=True)
    subprocess.run(K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)
    print('M1_P1_DEPLOYMENT_PREPARED',OUT)


if __name__=='__main__':main()
