"""Prepare an immutable IEDB N03 overlay while retaining the live P2 check method."""
import argparse
import ast
import base64
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
import yaml
import prepare_m1_p1_deploy as c

OUT=c.ROOT/'deploy/m1-p4/iedb-n03-r11'
NAME='antigen-iedb-n03-r11'
FILES=('service_api/himat.py','development/blast/policy.py','development/blast/result.py',
       'development/blast/worker.py','development/blast/iedb.py','development/epitope_map/policy.py',
       'development/epitope_map/result.py','development/design_backend/permissions.py',
       'development/docker.py','development/supervisor.py')
TESTS=c.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/iedb-full-r02.junit.xml'
sha=lambda b:hashlib.sha256(b).hexdigest()


def method(source,name):
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='HiMatIntegration')
    return next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)


def keep_live_check(local,live):
    old=method(live,'check');new=method(local,'check')
    lines=local.splitlines(keepends=True)
    lines[new.lineno-1:new.end_lineno]=live.splitlines(keepends=True)[old.lineno-1:old.end_lineno]
    result=''.join(lines)
    assert ast.dump(method(result,'check'))==ast.dump(old)
    assert ast.dump(method(result,'submit_sequence'))==ast.dump(method(local,'submit_sequence'))
    compile(result,'himat.py','exec')
    return result.encode()


def sources():return {n:(c.ROOT/'src/t01_phase1_real'/n).read_bytes() for n in FILES}


def idle():
    state=c.idle();assert not state['active_jobs'] and state['gpu_state']['phase']=='idle'
    return state


def render(live,raw):
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    spec=live['spec']['template']['spec'];assert all(v['name']!=NAME for v in spec['volumes'])
    ops=[dict(op='test',path='/metadata/uid',value=live['metadata']['uid']),
         dict(op='test',path='/metadata/resourceVersion',value=live['metadata']['resourceVersion'])]
    for index,con in enumerate(spec['containers']):
        if con['name']=='service':prefix='/app/src/t01_phase1_real/';names=FILES
        elif con['name']=='worker-blast':prefix='/opt/t01/src/t01_phase1_real/';names=('development/blast/worker.py','development/blast/iedb.py')
        else:continue
        targets={prefix+n for n in names}
        mounts=[m for m in con['volumeMounts'] if m['mountPath'] not in targets]
        mounts += [dict(name=NAME,mountPath=prefix+n,subPath='p'+str(FILES.index(n)),readOnly=True) for n in names]
        assert len({m['mountPath'] for m in mounts})==len(mounts)
        ops.append(dict(op='replace',path=f'/spec/template/spec/containers/{index}/volumeMounts',value=mounts))
    ops.append(dict(op='add',path='/spec/template/spec/volumes/-',value=dict(name=NAME,configMap=dict(name=NAME))))
    cm=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),immutable=True,
        binaryData={'p'+str(i):base64.b64encode(raw[n]).decode() for i,n in enumerate(FILES)})
    return cm,ops


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');a=p.parse_args()
    raw=sources();hashes={n:sha(b) for n,b in raw.items()}
    if a.apply:
        pre=json.loads((OUT/'preflight.json').read_bytes());assert pre['source_hashes']==hashes
        for n,h in pre['prepared_sha256'].items():assert sha((OUT/n).read_bytes())==h
        for report in (TESTS,TESTS.parent/'iedb-gapped-hsp-r01.junit.xml'):
            suites=list(ET.parse(report).getroot().iter('testsuite'))
            assert suites and not any(int(s.get('failures',0)) or int(s.get('errors',0)) for s in suites)
        idle()
        subprocess.run(c.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)
        subprocess.run(c.K+['create','-f',str(OUT/'configmap.yaml')],check=True)
        subprocess.run(c.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json')],check=True)
        print('IEDB_N03_ROLLOUT_REQUESTED');return
    state=idle()
    live=json.loads(subprocess.check_output(c.K+['get','deployment','antigen-design','-o','json']))
    previous=c.remote("from pathlib import Path;import json;print(json.dumps(Path('/app/src/t01_phase1_real/service_api/himat.py').read_text()))")
    raw['service_api/himat.py']=keep_live_check(raw['service_api/himat.py'].decode(),previous)
    verification=c.remote('''import json,sys,base64,time
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
p=json.load(sys.stdin);ns=dict(__package__='t01_phase1_real.development.blast',__file__='/app/src/t01_phase1_real/development/blast/policy.py')
exec(compile(base64.b64decode(p['code']),'iedb-policy-candidate','exec'),ns)
start=time.monotonic();r=ns['verify_database']('/var/lib/t01/m1-p1-test-data/blast',p['body'])
print(json.dumps(dict(receipt=r,elapsed_seconds=time.monotonic()-start)))
''',dict(code=base64.b64encode(raw['development/blast/policy.py']).decode(),body=dict(database_id='iedb-20260924-r01',database_manifest_sha256='96be17e60c108013d320558817037d081edbf8e3c0ed2f9facf83a2d818b6e12')))
    cm,ops=render(live,raw);OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'configmap.yaml').write_text(yaml.safe_dump(cm,sort_keys=False),encoding='utf-8')
    (OUT/'deployment.patch.json').write_text(json.dumps(ops,indent=2),encoding='utf-8')
    (OUT/'himat-deployed.py').write_bytes(raw['service_api/himat.py'])
    (OUT/'himat-before.py').write_text(previous,encoding='utf-8')
    pre=dict(source_hashes=hashes,deployed_hashes={n:sha(b) for n,b in raw.items()},before_generation=live['metadata']['generation'],
        idle=state,p2_check_preserved=True,database_verification=verification,
        prepared_sha256={n:sha((OUT/n).read_bytes()) for n in ('configmap.yaml','deployment.patch.json','himat-deployed.py','himat-before.py')})
    (OUT/'preflight.json').write_text(json.dumps(pre,indent=2),encoding='utf-8')
    subprocess.run(c.K+['create','--dry-run=server','-f',str(OUT/'configmap.yaml')],check=True)
    subprocess.run(c.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)
    print('IEDB_N03_PREPARED',OUT)


if __name__=='__main__':main()
