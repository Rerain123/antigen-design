"""Prepare the published r02 image plus matching immutable Worker source; dry-run only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OLD_IMAGE = 'harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:1c8b3f7c233580acd616d7e5b62a2c135fb9283d035399ead6dfde06420a2677'
NEW_IMAGE = 'harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:e31d68cd2ba1fd5199f86732c77abc3137ff3f342186b0a26645c562b75f2e5d'
OLD_CODE = 'antigen-esmfold2-backend-code-r01'
NEW_CODE = 'antigen-esmfold2-backend-code-r02'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()


def kc(*args, data=None):
    p=subprocess.run(['kubectl','--kubeconfig',str(ROOT/'.tmp/himat.kubeconfig'),'-n','him-ws',
                      '--request-timeout=45s',*args],input=data,capture_output=True)
    if p.returncode: raise RuntimeError(p.stderr.decode(errors='replace'))
    return p.stdout


def render(deployment, oldcode):
    pod=deployment['spec']['template']['spec']
    i=next(i for i,c in enumerate(pod['containers']) if c['name']=='service')
    v=next(i for i,v in enumerate(pod['volumes']) if v['name']=='esmfold2-code')
    volume=pod['volumes'][v]
    if pod['containers'][i]['image']!=OLD_IMAGE or volume['configMap']['name']!=OLD_CODE:
        raise ValueError('Unexpected deployment revision')
    if oldcode['metadata']['name']!=OLD_CODE or not oldcode.get('immutable'):
        raise ValueError('Expected immutable r01 source')
    data=copy.deepcopy(oldcode['data']);changed=[]
    for item in volume['configMap']['items']:
        path=Path(item['path'])
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Invalid projected source path')
        raw=(ROOT/'src'/path).read_bytes()
        text=raw.decode('utf-8')
        if text!=data[item['key']]: changed.append(item['path'])
        data[item['key']]=text
    if changed!=['t01_phase1_real/development/esmfold2/standard.py']:
        raise ValueError('Expected only standard.py fix; found '+repr(changed))
    code=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NEW_CODE,namespace='him-ws'),immutable=True,data=data)
    patch=[dict(op='test',path='/metadata/resourceVersion',value=deployment['metadata']['resourceVersion']),
           dict(op='test',path=f'/spec/template/spec/containers/{i}/image',value=OLD_IMAGE),
           dict(op='test',path=f'/spec/template/spec/volumes/{v}/configMap/name',value=OLD_CODE),
           dict(op='replace',path=f'/spec/template/spec/containers/{i}/image',value=NEW_IMAGE),
           dict(op='replace',path=f'/spec/template/spec/volumes/{v}/configMap/name',value=NEW_CODE)]
    return code,patch


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    if args.output_dir.exists(): raise ValueError('Use a new output directory')
    receipts=json.loads((ROOT/'.tmp/esmfold2-backend-publish-20260917-r02/publish-receipts.json').read_bytes())
    if len(receipts)!=1 or receipts[0]['status']!='VERIFIED' or receipts[0]['digest']!=NEW_IMAGE.split('@')[1]:
        raise ValueError('Verified r02 publication required')
    deployment=json.loads(kc('get','deployment','antigen-design','-o','json'))
    if deployment['status'].get('readyReplicas')!=1 or deployment['status'].get('observedGeneration')!=deployment['metadata']['generation']:
        raise ValueError('Deployment is not stable')
    oldcode=json.loads(kc('get','configmap',OLD_CODE,'-o','json'))
    code,patch=render(deployment,oldcode)
    # Independently require every ESMFold2 file in the published image to match
    # the exact local bytes projected to the worker (including line endings).
    probe="from t01_phase1_real.development.esmfold2 import policy; import hashlib,json; print(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in policy.HERE.iterdir() if p.suffix in ('.py','.json')}))"
    raw=subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--entrypoint','python',
                                 'antigen-design:esmfold2-backend-r02','-B','-c',probe])
    expected={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src/t01_phase1_real/development/esmfold2').iterdir() if p.suffix in ('.py','.json')}
    if json.loads(raw)!=expected: raise ValueError('Image/source mismatch')
    kc('apply','--dry-run=server','-f','-',data=encoded(code))
    kc('patch','deployment','antigen-design','--type=json','--dry-run=server','-p',json.dumps(patch))
    args.output_dir.mkdir(parents=True)
    for name,value in [('worker-code.json',code),('deployment.patch.json',patch),('deployment.before.json',deployment)]:
        (args.output_dir/name).write_bytes(encoded(value))
    print('ESMFOLD2_R02_DEPLOY_SERVER_DRY_RUN_PASS',args.output_dir)
    print('No cluster resources were changed.')


if __name__=='__main__': main()
