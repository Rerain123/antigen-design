"""Immutable test-service overlay for PH1-REAL-GAP-1 item 1."""
import argparse
import base64
import json
import subprocess
import xml.etree.ElementTree as ET
import yaml
import prepare_m1_p1_deploy as common
from prepare_himat_p1_fixes import idle
from t01_phase1_real.common import sha

OUT=common.ROOT/'deploy/n13-local-rmsd/r01'
EVIDENCE=common.ROOT/'discovery/t01-phase1-real/n13-local-rmsd-20260925'
NAME='antigen-n13-local-rmsd-r01'
FILES=('development/epitope_protection/compute.py','development/epitope_protection/source.py',
    'development/epitope_protection/policy.py','development/workflow/m1.py')


def hashes():
    return {n:sha((common.ROOT/'src/t01_phase1_real'/n).read_bytes()) for n in FILES}


def render(live):
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    spec=live['spec']['template']['spec']
    assert not any(v['name']==NAME for v in spec['volumes'])
    i=next(i for i,c in enumerate(spec['containers']) if c['name']=='service')
    old=spec['containers'][i]['volumeMounts'];targets={'/app/src/t01_phase1_real/'+n for n in FILES}
    mounts=[m for m in old if m['mountPath'] not in targets]
    mounts += [dict(name=NAME,mountPath='/app/src/t01_phase1_real/'+n,subPath='p'+str(j),readOnly=True) for j,n in enumerate(FILES)]
    assert len({m['mountPath'] for m in mounts})==len(mounts)
    patch=[dict(op='test',path='/metadata/uid',value=live['metadata']['uid']),
        dict(op='test',path='/metadata/resourceVersion',value=live['metadata']['resourceVersion']),
        dict(op='replace',path=f'/spec/template/spec/containers/{i}/volumeMounts',value=mounts),
        dict(op='add',path='/spec/template/spec/volumes/-',value=dict(name=NAME,configMap=dict(name=NAME)))]
    cm=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),immutable=True,
        binaryData={'p'+str(j):base64.b64encode((common.ROOT/'src/t01_phase1_real'/n).read_bytes()).decode() for j,n in enumerate(FILES)})
    # A scoped inverse patch can be reviewed if rollback becomes necessary.
    rollback=[dict(op='test',path=f'/spec/template/spec/containers/{i}/volumeMounts',value=mounts),
        dict(op='replace',path=f'/spec/template/spec/containers/{i}/volumeMounts',value=old)]
    return cm,patch,rollback


def regression_passed():
    # The initial Windows command omitted -X utf8. Its historical-file decode
    # failures must each have a passing rerun; do not ignore or whitelist them.
    latest={}
    for name in ('full-r01.junit.xml','utf8-recheck-r01.junit.xml'):
        root=ET.parse(EVIDENCE/name).getroot()
        for case in root.iter('testcase'):
            key=(case.get('classname'),case.get('name'))
            if case.find('skipped') is not None and key in latest:continue
            latest[key]=case
    return bool(latest) and all(c.find('failure') is None and c.find('error') is None for c in latest.values())


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    state=idle()
    if args.apply:
        pre=json.loads((OUT/'preflight.json').read_bytes());assert hashes()==pre['source_hashes']
        assert all(sha((OUT/n).read_bytes())==digest for n,digest in pre['prepared_sha256'].items())
        assert regression_passed(), 'Every full-suite failure needs a passing recheck'
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)
        idle()
        subprocess.run(common.K+['create','-f',str(OUT/'configmap.yaml')],check=True)
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json')],check=True)
        print('N13_LOCAL_RMSD_ROLLOUT_REQUESTED');return
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    cm,patch,rollback=render(live);OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'configmap.yaml').write_text(yaml.safe_dump(cm,sort_keys=False),encoding='utf8')
    for name,value in [('deployment.patch.json',patch),('rollback.patch.json',rollback)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    pre=dict(source_hashes=hashes(),before_generation=live['metadata']['generation'],idle=state,
        prepared_sha256={n:sha((OUT/n).read_bytes()) for n in ('configmap.yaml','deployment.patch.json','rollback.patch.json')})
    (OUT/'preflight.json').write_text(json.dumps(pre,indent=2)+'\n',encoding='utf8')
    subprocess.run(common.K+['create','--dry-run=server','-f',str(OUT/'configmap.yaml')],check=True)
    print('N13_LOCAL_RMSD_PREPARED',OUT)


if __name__=='__main__':main()
