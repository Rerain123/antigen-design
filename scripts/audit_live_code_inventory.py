"""Read-only hashes of project code in the serving Pod; never imports tool models."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import prepare_m1_p1_deploy as common

OUT=common.ROOT/'reports/n12-validation-20260926/live-code-inventory.json'
REMOTE='''import hashlib,importlib.util,json,sys
from pathlib import Path
rows={}
for root in ('/app/src','/opt/t01/src'):
    base=Path(root)
    for package in ('t01_phase1_real','t01_structure_mapping'):
        folder=base/package
        if not folder.is_dir():continue
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p.suffix in ('.py','.json'):
                raw=p.read_bytes()
                rows[str(p)]=dict(sha256=hashlib.sha256(raw).hexdigest(),
                    text_sha256=hashlib.sha256(raw.replace(b'\\r\\n',b'\\n')).hexdigest())
spec=importlib.util.find_spec('t01_phase1_real')
print('CODE_INVENTORY='+json.dumps(dict(files=rows,sys_path=sys.path,
    package_origin=spec.origin if spec else None)))
'''


def main():
    def kubectl(*args):return json.loads(subprocess.check_output(common.K+list(args)))
    live=kubectl('get','deployment','antigen-design','-o','json')
    pods=kubectl('get','pods','-l','app.kubernetes.io/name=antigen-design','-o','json')['items']
    ready=[p for p in pods if p['status']['phase']=='Running' and
        any(c['type']=='Ready' and c['status']=='True' for c in p['status']['conditions'])]
    assert len(ready)==1
    pod=ready[0]
    def audit(container):
        name=container['name']
        python='/opt/t01/supervisor/bin/python3.11' if name in (
            'worker-unified-gpu','worker-deeptmhmm','worker-bepipred','worker-blast','worker-foldx') else 'python'
        p=subprocess.run(common.K+['exec',pod['metadata']['name'],'-c',name,'--',python,'-B','-c',REMOTE],
            capture_output=True,timeout=60)
        if p.returncode:return dict(container=name,error=p.stderr.decode(errors='replace')[-1000:])
        rows=[line[len('CODE_INVENTORY='):] for line in p.stdout.decode().splitlines() if line.startswith('CODE_INVENTORY=')]
        assert len(rows)==1,(name,'missing inventory')
        result=json.loads(rows[0]);same=[];different=[];extra=[]
        mounts={m['mountPath']:m['name'] for m in container.get('volumeMounts',[])}
        for remote,digests in result['files'].items():
            digest=digests['sha256']
            relative=remote.split('/src/',1)[1];local=common.ROOT/'src'/relative
            row=dict(path=remote,relative=relative,remote_sha256=digest,overlay=mounts.get(remote))
            if local.is_file():
                row['local_sha256']=hashlib.sha256(local.read_bytes()).hexdigest()
                row['text_equal']=digests['text_sha256']==hashlib.sha256(local.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                (same if row['local_sha256']==digest else different).append(row)
            else:extra.append(row)
        result.update(container=name,image=container['image'],identical=same,different=different,remote_only=extra)
        del result['files']
        if name=='service':
            observed={r['relative'] for r in same+different+extra if r['path'].startswith('/app/src/')}
            result['local_only']=[p.relative_to(common.ROOT/'src').as_posix()
                for package in ('t01_phase1_real','t01_structure_mapping')
                for p in sorted((common.ROOT/'src'/package).rglob('*'))
                if p.is_file() and p.suffix in ('.py','.json') and p.relative_to(common.ROOT/'src').as_posix() not in observed]
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        inventories=list(pool.map(audit,pod['spec']['containers']))
    after=kubectl('get','deployment','antigen-design','-o','json')
    assert after['metadata']['generation']==live['metadata']['generation'],'Deployment changed during audit'
    value=dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        generation=live['metadata']['generation'],pod=pod['metadata']['name'],containers=inventories,
        scope='Python/JSON project files in /app/src and /opt/t01/src; third-party model environments excluded',
        read_only=True)
    OUT.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    print(json.dumps([dict(container=r['container'],origin=r.get('package_origin'),error=r.get('error'),
        identical=len(r.get('identical',[])),different=len(r.get('different',[])),
        text_differences=sum(not row['text_equal'] for row in r.get('different',[])),
        remote_only=len(r.get('remote_only',[])),local_only=r.get('local_only',[])) for r in inventories]))


if __name__=='__main__':main()
