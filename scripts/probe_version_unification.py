"""Import-only compatibility check in existing containers; no worker polling."""
import base64
import concurrent.futures
import json
from pathlib import Path
import subprocess
import prepare_m1_p1_deploy as common
from version_bundle import build, encode, sha

OUT = common.ROOT / 'reports/version-unification-20260927'
REMOTE = r'''
import base64,importlib,json,os,subprocess,sys,tempfile
from pathlib import Path
p=json.load(sys.stdin)
with tempfile.TemporaryDirectory(prefix='source-compat-',dir='/var/lib/t01') as tmp:
    root=Path(tmp)
    for name in ('archive','manifest','installer'):
        (root/name).write_bytes(base64.b64decode(p[name]))
    namespace={'__name__':'bundle_installer'}
    exec(compile((root/'installer').read_bytes(),'bundle_installer','exec'),namespace)
    namespace['install'](root/'archive',root/'manifest',root/'src',p['sha256'])
    sys.path.insert(0,str(root/'src'))
    from t01_phase1_real.resident_worker import commands_from_file
    from t01_phase1_real.unified_gpu_worker import configured
    commandline=Path('/proc/1/cmdline').read_bytes().decode().split('\0')
    configs=[]
    if p['container']=='service':
        # Match repo-relative schema/asset lookups at the real /app/src location.
        for name in ('工作流设计','discovery','var','scripts'):
            if (Path('/app')/name).exists(): (root/name).symlink_to(Path('/app')/name,target_is_directory=True)
        from t01_phase1_real.linux_service import install_platform_modules
        install_platform_modules()
        for name in ('service_api.transport','service_api.himat','resident_a3d',
                     'development.workflow.validation','development.workflow.design_rounds',
                     'development.variant_report.selection','development.workflow.stability_scope'):
            importlib.import_module('t01_phase1_real.'+name)
        from t01_phase1_real.development.variant_report.selection import diversity
        assert diversity([dict(id='a',family='mixed')],{'a':'ACDE'})['ids']==['a']
    elif p['container']=='worker-unified-gpu':
        config,spools=configured('/etc/t01/unified-gpu.json')
        configs=[c for commands in spools.values() for c in commands.values()]
    else:
        configs=list(commands_from_file('/opt/t01/worker.json').values())
    checked=[]
    for command in configs:
        env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1',
             'HOME':str(root),'TMPDIR':str(root)}
        env.update(dict(command.environment))
        # Original tool interpreter and dependency paths; only project code redirected.
        env['PYTHONPATH']=str(root/'src')+':'+env.get('PYTHONPATH','')
        argv=list(command.argv)
        if '-m' in argv:
            module=argv[argv.index('-m')+1]
            code='import importlib,json; m=importlib.import_module('+repr(module)+'); print(json.dumps(dict(module=m.__name__,origin=m.__file__)))'
        else:
            script=next(a for a in argv if '/src/t01_phase1_real/' in a)
            staged=root/'src'/script.split('/src/',1)[1]
            # File-based workers deliberately avoid package __init__ dependencies.
            code='import sys,runpy,json;sys.path.insert(0,'+repr(str(staged.parent))+');runpy.run_path('+repr(str(staged))+',run_name="compatibility_probe");print(json.dumps(dict(origin='+repr(str(staged))+')))'
        done=subprocess.run([argv[0],'-B','-c',code],env=env,capture_output=True,timeout=45)
        if done.returncode:raise RuntimeError(command.tool+': '+done.stderr.decode(errors='replace')[-1600:])
        checked.append(dict(tool=command.tool,import_result=json.loads(done.stdout)))
    print('PROBE='+json.dumps(dict(container=p['container'],status='PASS',native_entry_imports=checked,
        source_sha256=p['sha256'],models_executed=False)))
'''


def main():
    archive, manifest = build(common.ROOT / 'src')
    payload = {k: base64.b64encode(v).decode() for k,v in dict(archive=archive,
        manifest=encode(manifest), installer=Path(__file__).with_name('version_bundle.py').read_bytes()).items()}
    payload['sha256'] = sha(encode(manifest))
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    def probe(container):
        name=container['name']
        python='python' if name=='service' else '/opt/t01/supervisor/bin/python3.11'
        done=subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c',name,'--',python,'-B','-c',REMOTE],
            input=encode(dict(payload,container=name)),capture_output=True,timeout=150)
        if done.returncode:return dict(container=name,status='FAIL',error=done.stderr.decode(errors='replace')[-2200:])
        return json.loads(next(line[6:] for line in done.stdout.decode().splitlines() if line.startswith('PROBE=')))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(probe,live['spec']['template']['spec']['containers']))
    (OUT/'predeploy-imports.json').write_bytes(encode(results)+b'\n')
    print(json.dumps(results))
    if any(row['status']!='PASS' for row in results):raise SystemExit(1)


if __name__=='__main__':main()
