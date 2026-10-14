"""Immutable P2 report overlay and already registered offline scale assets."""
import argparse
import base64
import copy
import hashlib
import json
import subprocess
from pathlib import Path
import yaml
import prepare_m1_p1_deploy as common

ROOT=common.ROOT
OUT=ROOT/'deploy/m1-p2/r08'
NAME='antigen-m1-p2-code-r08'
ESM_NAME='antigen-m1-p2-esmfold2-r08'
FILES=['src/t01_phase1_real/development/variant_report/'+n for n in ('m1.py','policy.py','source.py','compute.py')]
FILES+=['src/t01_phase1_real/development/esmfold2/quality.py']
FILES+=['src/t01_phase1_real/development/foldx/policy.py']
FILES+=['src/t01_phase1_real/resident_process.py']
SCALES=json.loads((ROOT/'src/t01_phase1_real/development/design_backend/scales.json').read_bytes())['source_receipts']


def binary_configmap(paths):
    data={'p'+str(i):base64.b64encode((ROOT/p).read_bytes()).decode() for i,p in enumerate(paths)}
    return dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),immutable=True,binaryData=data)


def esm_configmap(previous,volume):
    assert previous.get('immutable') is True
    assert previous['metadata']['name']==volume['configMap']['name']
    quality_path='t01_phase1_real/development/esmfold2/quality.py'
    quality_key=next(i['key'] for i in volume['configMap']['items'] if i['path']==quality_path)
    data=copy.deepcopy(previous['data'])
    data[quality_key]=(ROOT/'src'/quality_path).read_bytes().decode('utf-8')
    return dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=ESM_NAME,namespace='him-ws'),immutable=True,data=data)


def overlay_mounts(container,paths):
    mount_map={n:'/app/'+p for n,p in enumerate(paths)} if container['name']=='service' else {}
    targets=set(mount_map.values())
    mounts=[m for m in container['volumeMounts'] if m['mountPath'] not in targets and m['name']!='m1-p2-code']
    mounts += [dict(name='m1-p2-code',mountPath=target,subPath='p'+str(n),readOnly=True) for n,target in mount_map.items()]
    return mounts


def idle_state():
    # A CPU resident container can read the same store even if a code mount
    # prevents the service container from starting. Never infer idle from failure.
    code="""import json,sqlite3
from pathlib import Path
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
active=[{'job_id':r['job_id'],'state':r['state']} for (raw,) in db.execute('SELECT data FROM jobs')
        if (r:=json.loads(raw))['state'] not in ('succeeded','failed','cancelled','timed_out')]
p=Path('/var/lib/t01/resident/unified-gpu/state.json')
print(json.dumps({'active_jobs':active,'gpu_state':json.loads(p.read_bytes()) if p.exists() else None}))
"""
    raw=subprocess.check_output(common.K+['exec','deployment/antigen-design','-c','worker-bepipred','--',
        '/opt/t01/supervisor/bin/python3.11','-B','-c',code])
    return json.loads(raw)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    parser.add_argument('--unstaged-job',help='Exact recoverable job; requires verified absent execution spool')
    args=parser.parse_args()
    idle=idle_state()
    if idle['active_jobs']:
        assert args.unstaged_job and len(idle['active_jobs'])==1 and idle['active_jobs'][0]==dict(job_id=args.unstaged_job,state='reconciling'),'Active tasks prevent rollout'
        import run_m1_p2_probe as probe
        task=probe.context();task['job_id']=args.unstaged_job
        code=r'''
j=rt.get(task['job_id']);ex=rt.execution(j['job_id']);target=Path(ex['resident_target'])
ensure(j['state']=='reconciling' and j['tool_id']=='t01.real.foldx' and ex['phase']=='resident_stage_intent'
       and ex.get('resident_diagnostic')=='Invalid deadline','FORBIDDEN','Not the known unstaged budget rejection')
ensure(target.is_relative_to(Path('/var/lib/t01/resident/foldx')) and not target.exists(),
       'FORBIDDEN','Spool exists; execution cannot be assumed absent')
print(json.dumps(dict(job_id=j['job_id'],state=j['state'],execution=ex,spool_absent=True)))
'''
        idle['unstaged_recovery']=common.remote(probe.PREAMBLE+code,task)
    if args.apply:
        subprocess.run(common.K+['create','-f',str(OUT/'configmap.yaml')],check=True)
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json')],check=True)
        return
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    for receipt in SCALES.values():
        raw=(ROOT/receipt['path']).read_bytes()
        assert len(raw)==receipt['bytes'] and hashlib.sha256(raw).hexdigest()==receipt['sha256']
    paths=FILES+[r['path'] for r in SCALES.values()]
    cm=binary_configmap(paths)
    ops=[dict(op='test',path='/metadata/resourceVersion',value=live['metadata']['resourceVersion']),
         dict(op='test',path='/metadata/uid',value=live['metadata']['uid'])]
    spec=live['spec']['template']['spec']
    for i,c in enumerate(spec['containers']):
        if c['name'] not in ('service','worker-unified-gpu'):continue
        mounts=overlay_mounts(c,paths)
        ops.append(dict(op='replace',path=f'/spec/template/spec/containers/{i}/volumeMounts',value=mounts))
    volumes=[v for v in spec['volumes'] if v['name']!='m1-p2-code']
    esm=next(v for v in volumes if v['name']=='esmfold2-code')
    previous=json.loads(subprocess.check_output(common.K+['get','configmap',esm['configMap']['name'],'-o','json']))
    esm_cm=esm_configmap(previous,esm)
    esm['configMap']['name']=ESM_NAME
    volumes.append(dict(name='m1-p2-code',configMap=dict(name=NAME)))
    ops.append(dict(op='replace',path='/spec/template/spec/volumes',value=volumes))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'configmap.yaml').write_text(yaml.safe_dump_all([cm,esm_cm],sort_keys=False),encoding='utf-8')
    (OUT/'deployment.patch.json').write_text(json.dumps(ops,indent=2)+'\n',encoding='utf-8')
    (OUT/'preflight.json').write_text(json.dumps(dict(idle=idle,before_generation=live['metadata']['generation'],
        source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}),indent=2)+'\n',encoding='utf-8')
    subprocess.run(common.K+['create','--dry-run=server','-f',str(OUT/'configmap.yaml')],check=True)
    subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)


if __name__=='__main__':main()
