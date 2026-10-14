"""Immutable P1 fixes plus the actual ESMFold2 import-path correction."""
import argparse
import base64
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

import yaml
import prepare_m1_p1_deploy as common
import prepare_himat_esmfold2_path_fix as esm

OUT=common.ROOT/'deploy/m1-p4/himat-p1-r07'
NAME='antigen-m1-himat-p1-r07'
VOLUME='himat-p1-r07'
FILES=('service_api/himat.py','development/workflow/engineering.py','development/workflow/policy.py','development/local_delivery/m1.py','development/blast/result.py',
       'development/workflow/service.py','development/workflow/m1.py','development/local_delivery/compute.py')
TESTS=common.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/himat-p1-full-r02.junit.xml'


def hashes():
    return {name:hashlib.sha256((common.ROOT/'src/t01_phase1_real'/name).read_bytes()).hexdigest() for name in FILES}


def render(live,old_esm):
    native,patch,previous=esm.render(live,old_esm)
    spec=live['spec']['template']['spec']
    if any(v['name']==VOLUME for v in spec['volumes']):
        raise RuntimeError('P1 overlay already exists')
    index=next(i for i,c in enumerate(spec['containers']) if c['name']=='service')
    targets={'/app/src/t01_phase1_real/'+name for name in FILES}
    mounts=[m for m in spec['containers'][index]['volumeMounts'] if m['mountPath'] not in targets]
    mounts += [dict(name=VOLUME,mountPath='/app/src/t01_phase1_real/'+name,subPath='p'+str(i),readOnly=True)
               for i,name in enumerate(FILES)]
    if len({m['mountPath'] for m in mounts})!=len(mounts):
        raise RuntimeError('Duplicate service source mount')
    patch += [dict(op='replace',path=f'/spec/template/spec/containers/{index}/volumeMounts',value=mounts),
              dict(op='add',path='/spec/template/spec/volumes/-',value=dict(name=VOLUME,configMap=dict(name=NAME)))]
    service=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),immutable=True,
                 binaryData={'p'+str(i):base64.b64encode((common.ROOT/'src/t01_phase1_real'/name).read_bytes()).decode()
                             for i,name in enumerate(FILES)})
    return dict(apiVersion='v1',kind='List',items=[native,service]),patch,previous


def idle():
    state=common.idle()
    if state['active_jobs'] or state['gpu_state']['phase']!='idle':
        raise RuntimeError('Refusing rollout while work is active')
    return state


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    state=idle()
    if args.apply:
        preflight=json.loads((OUT/'preflight.json').read_bytes())
        if preflight['source_hashes']!=hashes() or preflight['esm_hashes']!=esm.source_hashes():
            raise RuntimeError('Source changed after preflight')
        for name,digest in preflight['prepared_sha256'].items():
            if hashlib.sha256((OUT/name).read_bytes()).hexdigest()!=digest:
                raise RuntimeError('Prepared deployment bytes changed')
        suites=ET.parse(TESTS).getroot().iter('testsuite')
        suites=list(suites)
        if not suites or any(int(s.attrib['failures']) or int(s.attrib['errors']) for s in suites):
            raise RuntimeError('Current root regression must pass before rollout')
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',
                                str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)
        idle()
        subprocess.run(common.K+['create','-f',str(OUT/'configmaps.yaml')],check=True)
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json')],check=True)
        subprocess.run(common.K+['rollout','status','deployment/antigen-design','--timeout=300s'],check=True)
        return
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    volume=next(v for v in live['spec']['template']['spec']['volumes'] if v['name']==esm.VOLUME)
    old=json.loads(subprocess.check_output(common.K+['get','configmap',volume['configMap']['name'],'-o','json']))
    cms,patch,previous=render(live,old)
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'configmaps.yaml').write_text(yaml.safe_dump(cms,sort_keys=False),encoding='utf-8')
    (OUT/'deployment.patch.json').write_text(json.dumps(patch,indent=2)+'\n',encoding='utf-8')
    (OUT/'preflight.json').write_text(json.dumps(dict(idle=state,source_hashes=hashes(),esm_hashes=esm.source_hashes(),
        previous_esm_hashes=previous,before_generation=live['metadata']['generation'],
        prepared_sha256={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ('configmaps.yaml','deployment.patch.json')}),indent=2)+'\n',encoding='utf-8')
    subprocess.run(common.K+['create','--dry-run=server','-f',str(OUT/'configmaps.yaml')],check=True)
    subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',
                            str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)
    print('HIMAT_P1_PREPARED',OUT)


if __name__=='__main__':main()
