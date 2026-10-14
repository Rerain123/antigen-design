"""Prepare/apply a scoped immutable overlay for expert-plan item 2."""
import argparse
import base64
import json
import subprocess
import xml.etree.ElementTree as ET

import yaml
import prepare_m1_p1_deploy as common
from prepare_himat_p1_fixes import idle
from t01_phase1_real.common import sha

NAME='antigen-phase1-item2-r04'
OUT=common.ROOT/'deploy/phase1-item2/r04'
EVIDENCE=common.ROOT/'discovery/t01-phase1-real/phase1-item2-20260925'
FILES=('development/netmhc/policy.py','development/netmhc/pan.py','development/netmhc/service.py','development/netmhc/pan-support.json',
       'development/runtime.py','development/epitope_map/policy.py','development/epitope_map/result.py',
       'development/epitope_map/composition.py','development/glycosylation/result.py',
       'development/blast/policy.py','development/blast/iedb.py','development/bepipred/result.py',
       'development/workflow/service.py','development/workflow/m1.py','service_api/himat.py',
       'development/epitope_protection/source.py')


def sources():return {name:(common.ROOT/'src/t01_phase1_real'/name).read_bytes() for name in FILES}
def hashes():return {name:sha(raw) for name,raw in sources().items()}


def render(live):
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    spec=live['spec']['template']['spec'];assert not any(v['name']==NAME for v in spec['volumes'])
    patch=[dict(op='test',path='/metadata/uid',value=live['metadata']['uid']),
           dict(op='test',path='/metadata/resourceVersion',value=live['metadata']['resourceVersion'])]
    rollback=[]
    for i,con in enumerate(spec['containers']):
        if con['name']=='service':prefix='/app/src/t01_phase1_real/';names=FILES
        elif con['name']=='worker-blast':prefix='/opt/t01/src/t01_phase1_real/';names=('development/blast/iedb.py',)
        else:continue
        original=con['volumeMounts'];targets={prefix+n for n in names}
        mounts=[m for m in original if m['mountPath'] not in targets]
        mounts += [dict(name=NAME,mountPath=prefix+n,subPath='p'+str(FILES.index(n)),readOnly=True) for n in names]
        assert len({m['mountPath'] for m in mounts})==len(mounts)
        path=f'/spec/template/spec/containers/{i}/volumeMounts'
        patch.append(dict(op='replace',path=path,value=mounts))
        rollback += [dict(op='test',path=path,value=mounts),dict(op='replace',path=path,value=original)]
    patch.append(dict(op='add',path='/spec/template/spec/volumes/-',value=dict(name=NAME,configMap=dict(name=NAME))))
    raw=sources()
    cm=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),immutable=True,
        binaryData={'p'+str(i):base64.b64encode(raw[n]).decode() for i,n in enumerate(FILES)})
    return cm,patch,rollback


def regression_passed():
    reports=sorted(EVIDENCE.glob('*junit.xml'))
    latest={}
    for path in reports:
        for case in ET.parse(path).getroot().iter('testcase'):
            key=(case.get('classname'),case.get('name'))
            if case.find('skipped') is not None and key in latest:continue
            latest[key]=case
    return len(latest)>2400 and all(c.find('failure') is None and c.find('error') is None for c in latest.values())


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    state=idle()
    if args.apply:
        pre=json.loads((OUT/'preflight.json').read_bytes())
        assert pre['source_hashes']==hashes()
        assert all(sha((OUT/n).read_bytes())==digest for n,digest in pre['prepared_sha256'].items())
        assert regression_passed(),'Current regression failures require a passing recheck'
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)
        idle()
        subprocess.run(common.K+['create','-f',str(OUT/'configmap.yaml')],check=True)
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json')],check=True)
        print('PHASE1_ITEM2_ROLLOUT_REQUESTED');return
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    cm,patch,rollback=render(live);OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'configmap.yaml').write_text(yaml.safe_dump(cm,sort_keys=False),encoding='utf8')
    for name,value in [('deployment.patch.json',patch),('rollback.patch.json',rollback)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    pre=dict(source_hashes=hashes(),before_generation=live['metadata']['generation'],idle=state,
        prepared_sha256={n:sha((OUT/n).read_bytes()) for n in ('configmap.yaml','deployment.patch.json','rollback.patch.json')})
    (OUT/'preflight.json').write_text(json.dumps(pre,indent=2)+'\n',encoding='utf8')
    subprocess.run(common.K+['create','--dry-run=server','-f',str(OUT/'configmap.yaml')],check=True)
    print('PHASE1_ITEM2_PREPARED',OUT)


if __name__=='__main__':main()
