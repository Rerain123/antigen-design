"""Verify every deployed project file, real native import path, and fixed resources."""
import concurrent.futures
import datetime
import json
import subprocess
import prepare_m1_p1_deploy as common
from prepare_version_unification import OUT, EVIDENCE
from version_bundle import encode, sha, build

REMOTE = r'''
import hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
p=json.load(sys.stdin)
roots=(['/app/src','/opt/t01/src'] if p['container']=='service' else ['/opt/t01/src'])+(['/backend'] if p['container']=='worker-unified-gpu' else [])
if p['container']!='service':
    assert os.path.islink('/app') and os.readlink('/app')=='/run/t01-slot/package'
    assert not os.path.lexists('/run/t01-slot/package') or os.path.islink('/run/t01-slot/package'), 'Native alias occupied by directory'
checked={}
for root in roots:
    files={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest()
           for package in ('t01_phase1_real','t01_structure_mapping')
           for f in (Path(root)/package).rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    assert files==p['manifest'],(root,'source snapshot mismatch')
    checked[root]=len(files)
if p['container']=='worker-structure':
    files={'t01_structure_mapping/'+str(f.relative_to('/code/t01_structure_mapping')):hashlib.sha256(f.read_bytes()).hexdigest()
           for f in Path('/code/t01_structure_mapping').rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    assert files=={k:v for k,v in p['manifest'].items() if k.startswith('t01_structure_mapping/')}
    checked['/code']=len(files)
from t01_phase1_real.resident_worker import commands_from_file
from t01_phase1_real.unified_gpu_worker import configured
configs=[];extra={}
if p['container']=='service':
    import urllib.request,sqlite3
    extra['health']=json.load(urllib.request.urlopen('http://127.0.0.1:18083/healthz',timeout=10))
    assert extra['health']['status']=='ok'
    with sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True) as db:
        extra['job_count']=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
    from t01_phase1_real.linux_service import install_platform_modules
    install_platform_modules()
    from t01_phase1_real.development.af3.policy import registered_profile as af3_profile
    from t01_phase1_real.development.esmfold2.policy import registered_profile as esmfold2_profile
    extra['profiles']={'af3':af3_profile(),'esmfold2':esmfold2_profile()}
elif p['container']=='worker-unified-gpu':
    config,spools=configured('/etc/t01/unified-gpu.json')
    configs=[c for commands in spools.values() for c in commands.values()]
    extra['gpu_state']=json.loads(Path('/var/lib/t01/resident/unified-gpu/state.json').read_bytes())
else:
    configs=list(commands_from_file('/opt/t01/worker.json').values())
native=[]
for command in configs:
    env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','HOME':'/tmp','TMPDIR':'/tmp'}
    env.update(dict(command.environment))
    argv=list(command.argv)
    if '-m' in argv:
        module=argv[argv.index('-m')+1]
        code='import importlib,json; m=importlib.import_module('+repr(module)+'); print(json.dumps(dict(origin=m.__file__,profile=m.policy.registered_profile())))'
    else:
        script=next(a for a in argv if '/src/t01_phase1_real/' in a)
        code='import sys,runpy,json;sys.path.insert(0,'+repr(str(Path(script).parent))+');runpy.run_path('+repr(script)+',run_name="compatibility_probe");print(json.dumps(dict(origin='+repr(script)+')))'
    done=subprocess.run([argv[0],'-B','-c',code],env=env,capture_output=True,timeout=45)
    assert done.returncode==0,(command.tool,done.stderr.decode(errors='replace')[-1800:])
    native.append(dict(tool=command.tool,**json.loads(done.stdout)))
print('VERIFY='+json.dumps(dict(container=p['container'],source_roots=checked,
    origin=importlib.util.find_spec('t01_phase1_real').origin,native=native,extra=extra)))
'''


def main():
    pre=json.loads((OUT/'preflight.json').read_bytes())
    assert build(common.ROOT/'src')[1]==pre['source_hashes']
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    expected=json.loads((OUT/'deployment.patch.json').read_bytes())[-1]['value']
    assert live['spec']['template']==expected
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    assert live['status']['readyReplicas']==1 and live['status']['updatedReplicas']==1
    pods=json.loads(subprocess.check_output(common.K+['get','pods','-l','app.kubernetes.io/name=antigen-design','-o','json']))['items']
    ready=[p for p in pods if not p['metadata'].get('deletionTimestamp') and p['status']['phase']=='Running'
           and any(c['type']=='Ready' and c['status']=='True' for c in p['status'].get('conditions',[]))]
    assert len(ready)==1
    pod=ready[0]
    assert pod['metadata']['annotations']['antigen-design/source-sha256']==pre['source_sha256']
    def verify(container):
        name=container['name'];python='python' if name=='service' else '/opt/t01/supervisor/bin/python3.11'
        result=subprocess.run(common.K+['exec','-i',pod['metadata']['name'],'-c',name,'--',python,'-B','-c',REMOTE],
            input=encode(dict(container=name,manifest=pre['source_hashes'])),capture_output=True,timeout=150)
        if result.returncode:raise RuntimeError(name+': '+result.stderr.decode(errors='replace')[-2200:])
        return json.loads(next(line[7:] for line in result.stdout.decode().splitlines() if line.startswith('VERIFY=')))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(verify,pod['spec']['containers']))
    service=next(r for r in results if r['container']=='service')
    gpu=next(r for r in results if r['container']=='worker-unified-gpu')
    job_count=json.loads((EVIDENCE/'before-job-count.json').read_bytes())['job_count']
    assert service['extra']['job_count']==job_count,'Job inventory changed during engineering deployment'
    for item in gpu['native']:
        if 'profile' in item:assert item['profile']==service['extra']['profiles'][item['tool']]
    before=json.loads((EVIDENCE/'before-deployment.json').read_bytes())
    old=before['spec']['template']['spec'];new=live['spec']['template']['spec']
    for a,b in zip(old['containers'],new['containers']):
        assert {k:v for k,v in a.items() if k!='volumeMounts'}=={k:v for k,v in b.items() if k!='volumeMounts'}
        if b['name']!='service':
            assert not any(m['mountPath']=='/app' or m['mountPath'].startswith('/app/') for m in b['volumeMounts'])
    old_annotations=before['spec']['template']['metadata']['annotations']
    for key,value in old_annotations.items():
        if key!='antigen-design/source-sha256':assert live['spec']['template']['metadata']['annotations'][key]==value
    final=common.idle();assert not final['active_jobs'] and final['gpu_state']['phase']=='idle'
    value=dict(status='PASS',checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_sha256=pre['source_sha256'],files_per_snapshot=len(pre['source_hashes']),
        generation=live['metadata']['generation'],pod=pod['metadata']['name'],
        containers=results,container_statuses=pod['status']['containerStatuses'],
        fixed_resources_images_commands_unchanged=True,source_profiles_match=True,idle=final,
        new_jobs=0,job_count=job_count,
        scientific_models_executed=False,scientific_gate='CLOSED',production='NOT_DEPLOYED')
    with (EVIDENCE/'deployment-verification.json').open('xb') as stream:stream.write(encode(value)+b'\n')
    print(json.dumps({k:value[k] for k in ('status','generation','pod','source_sha256','files_per_snapshot')}))


if __name__=='__main__':main()
