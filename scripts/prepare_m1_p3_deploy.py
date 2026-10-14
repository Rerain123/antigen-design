"""Deploy only P3 delivery adapters and the native PositionScan parser fix."""
import argparse
import base64
import hashlib
import json
import subprocess
import yaml
import prepare_m1_p1_deploy as common
import run_m1_p3_probe as p

OUT=common.ROOT/'deploy/m1-p3/r02'
NAME='antigen-m1-p3-code-r02'
FILES=['src/t01_phase1_real/development/local_delivery/'+n for n in ('m1.py','source.py','compute.py')]
FILES+=['src/t01_phase1_real/development/foldx/result.py']


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    idle=common.idle();assert idle['active_jobs']==[] and idle['gpu_state']['phase']=='idle','Active tasks prevent rollout'
    hashes={n:hashlib.sha256((common.ROOT/n).read_bytes()).hexdigest() for n in FILES}
    if args.apply:
        assert p.read(OUT/'preflight.json')['source_hashes']==hashes,'Code changed since preparation'
        subprocess.run(common.K+['create','-f',str(OUT/'configmap.yaml')],check=True)
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json')],check=True)
        return
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    spec=live['spec']['template']['spec'];i=next(i for i,c in enumerate(spec['containers']) if c['name']=='service')
    targets={'/app/'+n for n in FILES}
    mounts=[m for m in spec['containers'][i]['volumeMounts'] if m['mountPath'] not in targets and m['name']!='m1-p3-code']
    mounts += [dict(name='m1-p3-code',mountPath='/app/'+n,subPath='p'+str(j),readOnly=True) for j,n in enumerate(FILES)]
    volumes=[v for v in spec['volumes'] if v['name']!='m1-p3-code']
    volumes.append(dict(name='m1-p3-code',configMap=dict(name=NAME)))
    ops=[dict(op='test',path='/metadata/resourceVersion',value=live['metadata']['resourceVersion']),
         dict(op='test',path='/metadata/uid',value=live['metadata']['uid']),
         dict(op='replace',path=f'/spec/template/spec/containers/{i}/volumeMounts',value=mounts),
         dict(op='replace',path='/spec/template/spec/volumes',value=volumes)]
    cm=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),immutable=True,
        binaryData={'p'+str(j):base64.b64encode((common.ROOT/n).read_bytes()).decode() for j,n in enumerate(FILES)})
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'configmap.yaml').write_text(yaml.safe_dump(cm,sort_keys=False),encoding='utf-8')
    (OUT/'deployment.patch.json').write_text(json.dumps(ops,indent=2)+'\n',encoding='utf-8')
    (OUT/'preflight.json').write_text(json.dumps(dict(idle=idle,source_hashes=hashes,before_generation=live['metadata']['generation']),indent=2)+'\n',encoding='utf-8')
    subprocess.run(common.K+['create','--dry-run=server','-f',str(OUT/'configmap.yaml')],check=True)
    subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)


if __name__=='__main__':main()
