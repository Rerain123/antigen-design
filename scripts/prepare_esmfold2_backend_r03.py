"""Prepare r03 synchronized source update; server dry-run only."""
import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path
from scripts.prepare_esmfold2_backend_r02 import ROOT, kc, encoded

OLD_IMAGE='harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:e31d68cd2ba1fd5199f86732c77abc3137ff3f342186b0a26645c562b75f2e5d'
NEW_IMAGE='harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b'
OLD_CODE='antigen-esmfold2-backend-code-r02'
NEW_CODE='antigen-esmfold2-backend-code-r03'
WORKER='t01_phase1_real/development/structure/worker.py'
QUALITY='t01_phase1_real/development/esmfold2/quality.py'

def render(deployment, oldcode):
    pod=deployment['spec']['template']['spec']
    indices={c['name']:i for i,c in enumerate(pod['containers'])}
    i=indices['service']; s=indices['worker-structure']
    v=next(i for i,x in enumerate(pod['volumes']) if x['name']=='esmfold2-code')
    oldvolume=pod['volumes'][v]['configMap']
    if pod['containers'][i]['image']!=OLD_IMAGE or oldvolume['name']!=OLD_CODE:
        raise ValueError('Unexpected deployment revision')
    if oldcode['metadata']['name']!=OLD_CODE or not oldcode.get('immutable'):
        raise ValueError('Expected immutable r02 source')
    data=copy.deepcopy(oldcode['data']); items=copy.deepcopy(oldvolume['items']); changed=[]
    for item in items:
        path=Path(item['path'])
        if path.is_absolute() or '..' in path.parts: raise ValueError('Unsafe source path')
        text=(ROOT/'src'/path).read_bytes().decode('utf-8')
        if text!=data[item['key']]: changed.append(item['path'])
        data[item['key']]=text
    if set(changed)!={'t01_phase1_real/development/esmfold2/'+x for x in ('source.py','standard.py')}:
        raise ValueError('Unexpected source changes: '+repr(changed))
    for key,path in [('r03-quality',QUALITY),('r03-structure-worker',WORKER)]:
        if key in data or any(x['path']==path for x in items): raise ValueError('Source collision')
        data[key]=(ROOT/'src'/path).read_bytes().decode('utf-8')
        items.append(dict(key=key,path=path))
    mounts=pod['containers'][s]['volumeMounts']
    target='/opt/t01/src/'+WORKER
    if any(m['mountPath']==target for m in mounts): raise ValueError('Worker mount collision')
    volume=copy.deepcopy(oldvolume);volume.update(name=NEW_CODE,items=items)
    patch=[dict(op='test',path='/metadata/resourceVersion',value=deployment['metadata']['resourceVersion']),
           dict(op='test',path=f'/spec/template/spec/containers/{i}/image',value=OLD_IMAGE),
           dict(op='test',path=f'/spec/template/spec/volumes/{v}/configMap',value=oldvolume),
           dict(op='test',path=f'/spec/template/spec/containers/{s}/volumeMounts',value=mounts),
           dict(op='replace',path=f'/spec/template/spec/containers/{i}/image',value=NEW_IMAGE),
           dict(op='replace',path=f'/spec/template/spec/volumes/{v}/configMap',value=volume),
           dict(op='add',path=f'/spec/template/spec/containers/{s}/volumeMounts/-',value=dict(name='esmfold2-code',mountPath=target,subPath=WORKER,readOnly=True))]
    return dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NEW_CODE,namespace='him-ws'),immutable=True,data=data),patch

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    if args.output_dir.exists(): raise ValueError('Use a new output directory')
    receipts=json.loads((ROOT/'.tmp/esmfold2-backend-publish-20260917-r03/publish-receipts.json').read_bytes())
    if len(receipts)!=1 or receipts[0]['status']!='VERIFIED' or receipts[0]['digest']!=NEW_IMAGE.split('@')[1]:
        raise ValueError('Verified r03 publication required')
    deployment=json.loads(kc('get','deployment','antigen-design','-o','json'))
    if deployment['status'].get('readyReplicas')!=1 or deployment['status'].get('observedGeneration')!=deployment['metadata']['generation']:
        raise ValueError('Deployment is not stable')
    oldcode=json.loads(kc('get','configmap',OLD_CODE,'-o','json'))
    code,patch=render(deployment,oldcode)
    paths=[x['path'] for x in patch[-2]['value']['items']]
    paths+=['t01_phase1_real/development/runtime.py','t01_phase1_real/development/structure/result.py']
    probe="import hashlib,json; from pathlib import Path; import t01_phase1_real; root=Path(t01_phase1_real.__file__).parent.parent; paths="+repr(paths)+"; print(json.dumps({p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}))"
    raw=subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--entrypoint','python','antigen-design:esmfold2-backend-r03','-B','-c',probe])
    expected={p:hashlib.sha256((ROOT/'src'/p).read_bytes()).hexdigest() for p in paths}
    if json.loads(raw)!=expected: raise ValueError('Image/source mismatch')
    kc('apply','--dry-run=server','-f','-',data=encoded(code))
    kc('patch','deployment','antigen-design','--type=json','--dry-run=server','-p',json.dumps(patch))
    args.output_dir.mkdir(parents=True)
    for name,value in [('worker-code.json',code),('deployment.patch.json',patch),('deployment.before.json',deployment),('source-hashes.json',expected)]:
        (args.output_dir/name).write_bytes(encoded(value))
    print('ESMFOLD2_R03_DEPLOY_SERVER_DRY_RUN_PASS',args.output_dir)
    print('No cluster resources were changed.')

if __name__=='__main__': main()
