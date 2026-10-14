"""Source-only update of the existing split deployments; no scientific jobs."""
import argparse
import concurrent.futures
import json
import subprocess
import xml.etree.ElementTree as ET

import prepare_m1_p1_deploy as common
import prepare_version_unification as bundle
import verify_version_unification as verification
from verify_gpu_resident import check_template
from version_bundle import build, encode, sha

OUT=common.ROOT/'deploy/terminal-sync/r01'
EV=common.ROOT/'reports/terminal-sync-20261010'
NAMES=['antigen-design']+['antigen-design-worker-'+n for n in
    ('structure','deeptmhmm','bepipred','netmhc','blast','homology','foldx','aggrescan3d')]+['antigen-design-gpu-resident']


def run(args,data=None):
    p=subprocess.run(common.K+args,input=encode(data) if data is not None else None,capture_output=True,timeout=110)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-2000:])
    return json.loads(p.stdout) if '-o' in args and args[args.index('-o')+1]=='json' else p.stdout.decode()


def save(name,value):
    (EV/name).write_bytes(encode(value))


def prior_task():
    return common.remote("""import json,sqlite3,hashlib
jid='t01p1r-job-b7506c0cc61e4bd084c1e8ee466fb86e'
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
h=lambda raw:hashlib.sha256(raw.encode() if isinstance(raw,str) else raw).hexdigest()
print(json.dumps(dict(job_count=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
job_sha256=h(db.execute('SELECT data FROM jobs WHERE id=?',(jid,)).fetchone()[0]),
execution_sha256=h(db.execute('SELECT data FROM executions WHERE job_id=?',(jid,)).fetchone()[0]))))
""")


def prepared():
    manifest=json.loads((OUT/'source-manifest.json').read_bytes())
    assert build(common.ROOT/'src')[1]==manifest,'Source changed after preparation'
    return manifest,json.loads((OUT/'templates.json').read_bytes())


def regression():
    files=['full-r01.xml','targeted-r02.xml','docker-recheck.xml']
    receipts=[];latest={}
    for name in files:
        raw=(EV/name).read_bytes();cases=list(ET.fromstring(raw).iter('testcase'))
        assert len(cases)>=(3300 if name.startswith('full') else 220 if name.startswith('targeted') else 6)
        if not name.startswith('full'):
            assert not any(c.find('failure') is not None or c.find('error') is not None for c in cases),name
        for c in cases:
            key=(c.get('classname'),c.get('name'))
            if name.startswith('full') or key in latest:latest[key]=c
        receipts.append(dict(path=name,sha256=sha(raw),passed=sum(all(c.find(k) is None for k in ('skipped','failure','error')) for c in cases),
                             failed=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),
                             skipped=sum(c.find('skipped') is not None for c in cases)))
    assert not any(c.find('failure') is not None or c.find('error') is not None for c in latest.values())
    assert json.loads((EV/'frozen.json').read_bytes())['status']=='PASS'
    return dict(receipts=receipts,tests=len(latest),passed=sum(c.find('skipped') is None for c in latest.values()),
                skipped=sum(c.find('skipped') is not None for c in latest.values()),single_final_full_run=False)


def prepare():
    OUT.mkdir(parents=True,exist_ok=True);EV.mkdir(parents=True,exist_ok=True)
    state=common.idle();assert not state['active_jobs'] and state['gpu_state']['phase']=='idle'
    live={n:run(['get','deployment',n,'-o','json']) for n in NAMES}
    save('before-deployments.json',live)
    templates={};config=None;manifest=None
    for name,dep in live.items():
        cm,patch,rollback,m=bundle.render(dep)
        assert config is None or config==cm
        config=cm;manifest=m;template=patch[-1]['value']
        assert template['spec']['containers']==dep['spec']['template']['spec']['containers']
        assert len(template['spec']['containers'])==1
        templates[name]=template
        (OUT/(name+'.patch.json')).write_bytes(encode(patch))
        (OUT/(name+'.rollback.json')).write_bytes(encode(rollback))
    previous=json.loads((common.ROOT/'deploy/gpu-resident/r01/source-manifest.json').read_bytes())
    changed=sorted(k for k in set(previous)|set(manifest) if previous.get(k)!=manifest.get(k))
    assert changed==['t01_phase1_real/development/workflow/revision_controller.py','t01_phase1_real/service_api/himat.py']
    (OUT/'source-manifest.json').write_bytes(encode(manifest))
    (OUT/'templates.json').write_bytes(encode(templates))
    (OUT/'configmaps.json').write_bytes(encode(config))
    for obj in config.get('items',[config]):run(['create','--dry-run=server','-f','-','-o','name'],obj)
    for name in NAMES:
        run(['patch','deployment',name,'--type=json','--dry-run=server','--patch-file',str(OUT/(name+'.patch.json')),'-o','name'])
    save('preparation.json',dict(status='PREPARED',source_sha256=sha(encode(manifest)),files=len(manifest),
        changed_sources=changed,deployments=NAMES,resources_images_commands_unchanged=True,scientific_jobs_submitted=0))
    print('PREPARED; source files:',len(manifest))


def apply():
    manifest,templates=prepared();save('regression.json',regression())
    state=common.idle();assert not state['active_jobs'] and state['gpu_state']['phase']=='idle'
    save('idle-at-apply.json',state)
    save('previous-task-before.json',prior_task())
    before=json.loads((EV/'before-deployments.json').read_bytes())
    current={n:run(['get','deployment',n,'-o','json']) for n in NAMES}
    for n,d in current.items():
        assert d['metadata']['uid']==before[n]['metadata']['uid'] and d['spec']==before[n]['spec']
    cm=json.loads((OUT/'configmaps.json').read_bytes())
    for obj in cm.get('items',[cm]):run(['create','-f','-','-o','name'],obj)
    # Close admission while workers change source versions. No active run is stopped.
    d=current['antigen-design']
    run(['patch','deployment','antigen-design','--type=json','-p',json.dumps([
            dict(op='test',path='/metadata/resourceVersion',value=d['metadata']['resourceVersion']),
            dict(op='replace',path='/spec/replicas',value=0)]),'-o','name'])
    save('admission-closed.json',dict(replicas=0,source_sha256=sha(encode(manifest))))
    print('API paused for source upgrade; run rollout after API Pod exits')


def rollout():
    prepared();regression()
    before=json.loads((EV/'before-deployments.json').read_bytes())
    pods=run(['get','pods','-l','app.kubernetes.io/component=control-plane','-o','json'])['items']
    assert not any(p['metadata']['labels'].get('app.kubernetes.io/name')=='antigen-design' for p in pods),'API Pod still exiting'
    applied=[]
    for name in NAMES:
        current=run(['get','deployment',name,'-o','json'])
        expected=dict(before[name]['spec'])
        if name=='antigen-design':expected['replicas']=0
        assert current['metadata']['uid']==before[name]['metadata']['uid'] and current['spec']==expected
        patch=json.loads((OUT/(name+'.patch.json')).read_bytes())
        next(p for p in patch if p['path']=='/metadata/resourceVersion')['value']=current['metadata']['resourceVersion']
        path=OUT/(name+'.applied.patch.json');path.write_bytes(encode(patch))
        run(['patch','deployment',name,'--type=json','--patch-file',str(path),'-o','name']);applied.append(name)
        save('applied.json',applied)
    print('Worker source rollout submitted; API remains at zero until activate')


def activate():
    _,templates=prepared()
    for name in NAMES[1:]:
        d=run(['get','deployment',name,'-o','json']);check_template(d['spec']['template'],templates[name])
        assert d['status'].get('observedGeneration')==d['metadata']['generation']
        assert d['spec']['replicas']==d['status'].get('readyReplicas')==d['status'].get('updatedReplicas')==1
    d=run(['get','deployment','antigen-design','-o','json']);check_template(d['spec']['template'],templates['antigen-design'])
    run(['scale','deployment','antigen-design','--current-replicas=0','--replicas=1'])
    print('API activated')


def verify():
    manifest,templates=prepared()
    pods=run(['get','pods','-l','app.kubernetes.io/name=antigen-design','-o','json'])['items'];ready=[];generations={}
    for name in NAMES:
        d=run(['get','deployment',name,'-o','json']);check_template(d['spec']['template'],templates[name])
        assert d['status'].get('observedGeneration')==d['metadata']['generation']
        assert d['spec']['replicas']==d['status'].get('readyReplicas')==d['status'].get('updatedReplicas')==1
        matches=[p for p in pods if not p['metadata'].get('deletionTimestamp') and all(
            p['metadata']['labels'].get(k)==v for k,v in d['spec']['selector']['matchLabels'].items())]
        assert len(matches)==1 and all(c['ready'] and c['restartCount']==0 for c in matches[0]['status']['containerStatuses'])
        ready.append(matches[0]);generations[name]=d['metadata']['generation']
    boot="import json,sys;p=json.load(sys.stdin);exec(compile(p.pop('code'),'source-verification','exec'))"
    code=verification.REMOTE.replace('p=json.load(sys.stdin)','')
    def check(pod):
        c=pod['spec']['containers'][0]['name'];python='python' if c=='service' else '/opt/t01/supervisor/bin/python3.11'
        p=subprocess.run(common.K+['exec','-i',pod['metadata']['name'],'-c',c,'--',python,'-B','-c',boot],
            input=encode(dict(code=code,container=c,manifest=manifest)),capture_output=True,timeout=150)
        assert p.returncode==0,(c,p.stderr.decode(errors='replace')[-1500:])
        value=json.loads(next(line[7:] for line in p.stdout.decode().splitlines() if line.startswith('VERIFY=')))
        return dict(value,pod=pod['metadata']['name'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(check,ready))
    idle=common.idle();assert not idle['active_jobs'] and idle['gpu_state']['phase']=='idle'
    old=prior_task();assert old==json.loads((EV/'previous-task-before.json').read_bytes())
    save('previous-task-after.json',old)
    save('deployment-verification.json',dict(status='PASS',generations=generations,containers=results,
        source_sha256=sha(encode(manifest)),files=len(manifest),idle=idle,scientific_jobs_submitted=0))
    print('VERIFIED',len(results),'containers; API generation',generations['antigen-design'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','apply','rollout','activate','verify'])
    globals()[p.parse_args().action]()
