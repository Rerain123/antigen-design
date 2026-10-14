"""Prepare and apply the immutable PH1-REAL-ROUTE-1 test-service overlay."""
import argparse
import base64
import hashlib
import json
import subprocess

import yaml
import prepare_m1_p1_deploy as common

OUT=common.ROOT/'deploy/m1-p4/route-r01'
NAME='antigen-m1-route-r01'
VOLUME='m1-route-code'
FILES=(
    'development/workflow/m1.py',
    'development/workflow/policy.py',
    'development/workflow/service.py',
    'development/variant_report/compute.py',
    'development/variant_report/service.py',
    'development/variant_report/__init__.py',
    'development/variant_report/m1.py',
    'development/variant_report/source.py',
    'development/epitope_protection/policy.py',
    'development/epitope_protection/source.py',
    'development/epitope_protection/compute.py',
)


def hashes():
    return {name:hashlib.sha256((common.ROOT/'src/t01_phase1_real'/name).read_bytes()).hexdigest() for name in FILES}


def patch(live):
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    spec=live['spec']['template']['spec']
    assert not any(v['name']==VOLUME for v in spec['volumes'])
    i=next(i for i,c in enumerate(spec['containers']) if c['name']=='service')
    mounts=spec['containers'][i]['volumeMounts']
    targets={'/app/src/t01_phase1_real/'+n for n in FILES}
    replacement=[m for m in mounts if m['mountPath'] not in targets]
    replacement.extend(dict(name=VOLUME,mountPath='/app/src/t01_phase1_real/'+name,
        subPath='p'+str(j),readOnly=True) for j,name in enumerate(FILES))
    assert len({m['mountPath'] for m in replacement})==len(replacement)
    return [dict(op='test',path='/metadata/resourceVersion',value=live['metadata']['resourceVersion']),
        dict(op='test',path='/metadata/uid',value=live['metadata']['uid']),
        dict(op='replace',path=f'/spec/template/spec/containers/{i}/volumeMounts',value=replacement),
        dict(op='add',path='/spec/template/spec/volumes/-',value=dict(name=VOLUME,configMap=dict(name=NAME)))]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    idle=common.idle();assert not idle['active_jobs'] and idle['gpu_state']['phase']=='idle'
    current=hashes()
    if args.apply:
        preflight=json.loads((OUT/'preflight.json').read_bytes())
        assert preflight['source_hashes']==current
        subprocess.run(common.K+['create','-f',str(OUT/'configmap.yaml')],check=True)
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json',
            '--patch-file',str(OUT/'deployment.patch.json')],check=True)
        return
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    operations=patch(live)
    cm=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),immutable=True,
        binaryData={'p'+str(j):base64.b64encode((common.ROOT/'src/t01_phase1_real'/name).read_bytes()).decode()
            for j,name in enumerate(FILES)})
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'configmap.yaml').write_text(yaml.safe_dump(cm,sort_keys=False),encoding='utf-8')
    (OUT/'deployment.patch.json').write_text(json.dumps(operations,indent=2)+'\n',encoding='utf-8')
    (OUT/'preflight.json').write_text(json.dumps(dict(task='PH1-REAL-ROUTE-1',idle=idle,
        source_hashes=current,before_generation=live['metadata']['generation'],
        before_uid=live['metadata']['uid'],before_resource_version=live['metadata']['resourceVersion']),indent=2)+'\n',encoding='utf-8')
    subprocess.run(common.K+['create','--dry-run=server','-f',str(OUT/'configmap.yaml')],check=True)
    subprocess.run(common.K+['patch','deployment','antigen-design','--type=json',
        '--patch-file',str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)
    print('ROUTE_DEPLOYMENT_PREPARED',OUT)


if __name__=='__main__':main()
