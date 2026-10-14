"""Prepare/apply an immutable P4 service overlay only while native queues are idle."""
import argparse
import base64
import hashlib
import json
import subprocess
import yaml
import prepare_m1_p1_deploy as common

OUT=common.ROOT/'deploy/m1-p4/r02'
NAME='antigen-m1-p4-code-r02'
FILES=['src/t01_phase1_real/development/'+n for n in (
    'workflow/m1.py','workflow/service.py','workflow/policy.py',
    'local_delivery/m1.py','blast/policy.py','blast/prebuilt.py')]
FILES+=['src/t01_phase1_real/service_api/transport.py']


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    idle=common.idle();assert not idle['active_jobs'] and idle['gpu_state']['phase']=='idle'
    hashes={n:hashlib.sha256((common.ROOT/n).read_bytes()).hexdigest() for n in FILES}
    if args.apply:
        assert json.loads((OUT/'preflight.json').read_bytes())['source_hashes']==hashes
        subprocess.run(common.K+['create','-f',str(OUT/'configmap.yaml')],check=True)
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json')],check=True)
        return
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    spec=live['spec']['template']['spec'];i=next(i for i,c in enumerate(spec['containers']) if c['name']=='service')
    targets={'/app/'+n for n in FILES}
    mounts=[m for m in spec['containers'][i]['volumeMounts'] if m['mountPath'] not in targets and m['name']!='m1-p4-code']
    mounts += [dict(name='m1-p4-code',mountPath='/app/'+n,subPath='p'+str(j),readOnly=True) for j,n in enumerate(FILES)]
    volumes=[v for v in spec['volumes'] if v['name']!='m1-p4-code']
    volumes.append(dict(name='m1-p4-code',configMap=dict(name=NAME)))
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
