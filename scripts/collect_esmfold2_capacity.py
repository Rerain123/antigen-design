"""Read-only collection and audit of the completed isolated capacity Job."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.audit_esmfold2_r03 import audit, require
from scripts.prepare_esmfold2_capacity import ROOT, NAME, OUT as MANIFEST

OUT=ROOT/'discovery/t01-phase1-real/esmfold2-target-20260917/capacity393-20260918-r01'
REMOTE=r'''
import base64,json
from pathlib import Path
root=Path('/var/lib/t01/capacity393-20260918-r01')
paths=list(root.rglob('*'))
assert not any(p.is_symlink() for p in paths)
files=[p for p in paths if p.is_file()]
assert sum(p.stat().st_size for p in files)<64*1024**2
print(json.dumps({p.relative_to(root).as_posix():base64.b64encode(p.read_bytes()).decode() for p in files}))
'''

def main():
    kc=['kubectl','--kubeconfig',str(ROOT/'.tmp/himat.kubeconfig'),'-n','him-ws','--request-timeout=45s']
    def fetch(*args):return subprocess.check_output(kc+list(args),timeout=60)
    job=json.loads(fetch('get','job',NAME,'-o','json'))
    require(job.get('status',{}).get('succeeded')==1,'Job not completed')
    pods=json.loads(fetch('get','pods','-l','job-name='+NAME,'-o','json'))
    require(len(pods['items'])==1,'Unexpected Pod count')
    pod=pods['items'][0]
    require(pod['metadata']['ownerReferences'][0]['uid']==job['metadata']['uid'],'Pod owner mismatch')
    require(all(c['state'].get('terminated',{}).get('exitCode')==0 for c in pod['status']['containerStatuses']),'Nonzero container exit')
    bundle=json.loads(MANIFEST.read_bytes())['items']
    cm=json.loads(fetch('get','configmap',NAME,'-o','json'))
    require(cm['data']==bundle[1]['data'] and cm['immutable'],'Source ConfigMap differs')
    reply=subprocess.run(kc+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-'],input=REMOTE.encode(),capture_output=True,timeout=60,check=True)
    files={n:base64.b64decode(b,validate=True) for n,b in json.loads(reply.stdout).items()}
    native={n.removeprefix('native/'):b for n,b in files.items() if n.startswith('native/')}
    summary=audit(native,job,bundle,expected_request_id=NAME)
    require(set(files)=={'native/'+n for n in native}|{'request.json','profile.json','sequence-provenance.json','network.json'},'Unexpected outer result files')
    for n in ('request.json','profile.json','sequence-provenance.json'):
        require(json.loads(files[n])==json.loads(cm['data'][n]),'Input provenance mismatch')
    network=json.loads(files['network.json'])
    require(network==dict(restriction='seccomp-local-sockets-only-v1',socket_probe='INET_INET6_DENIED'),'Missing actual offline probe')
    summary.update(network_probe=network,status='CAPACITY393_ENGINEERING_AUDIT_PASS',backend_supported_max_aa=76,
        limitations=['One 393-residue case only; backend limit unchanged at 76.',
        'No scientific accuracy or stereochemical signoff.', '1000-1500 and >1500 residues NOT_RUN.',
        'Peak GPU memory is PyTorch allocated, not total GPU consumption.',
        'Elapsed time includes integrity verification, loading and inference.',
        'Fixed environment uses PyTorch fallback kernels; no fused-kernel numerical equivalence established.'])
    summary['collector_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    records=dict(files)
    records.update({'cluster-job.json':json.dumps(job,indent=2).encode(),'cluster-pod.json':json.dumps(pod,indent=2).encode(),
        'cluster-log.txt':fetch('logs',pod['metadata']['name']), 'audit-summary.json':json.dumps(summary,ensure_ascii=False,indent=2).encode()})
    for n,b in records.items():
        path=OUT/n
        require(not path.exists() or path.read_bytes()==b,'Refusing changed evidence overwrite: '+n)
    for n,b in records.items():
        path=OUT/n;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b)
    print(summary['status']);print(json.dumps(dict(structure={k:v for k,v in summary['structure'].items() if k!='residue_plddt_0_to_1'},metrics=summary['metrics'],execution=summary['execution']),ensure_ascii=False));print('SAVED',OUT)

if __name__=='__main__':main()
