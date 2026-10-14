"""Render an isolated 393-residue capacity Job; does not change service limits."""
import copy
import hashlib
import json
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
NAME='antigen-esmfold2-capacity393-r01'
OUT=ROOT/'deploy/esmfold2-standard/capacity393.r01.json'

def render():
    base=list(yaml.safe_load_all((ROOT/'deploy/esmfold2-standard/validation.r03.rancher.yaml').read_text(encoding='utf-8')))
    fasta=ROOT/'tests/fixtures/structure_mapping/real/5XZC.fasta'
    raw=fasta.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='a5c70cd6ea90eedac06af5c41218f472405bd4024d6041595c1a0a95b210f341':raise ValueError('FASTA differs from registered source')
    seq=''.join(l.strip() for l in raw.decode().splitlines() if not l.startswith('>'))
    if len(seq)!=393 or hashlib.sha256(seq.encode()).hexdigest()!='e3ca60f18e3b6e98986ad6749215ee3b7a3abc09c191675213d1f243c035c9a3':raise ValueError('Sequence mismatch')
    cm=copy.deepcopy(base[1]);cm['metadata']['name']=NAME
    profile=json.loads(cm['data']['profile.json']);profile.update(id='esmfold2-capacity393-experimental-r01',max_sequence_length=393,max_timeout_seconds=1800)
    request=json.loads(cm['data']['request.json']);request.update(request_id=NAME,asset_profile_id=profile['id'])
    request['inputs'].update(sequence_id='tp53-p04637-capacity-r01',sequence=seq)
    request['parameters']['timeout_seconds']=1800
    cm['data']['profile.json']=json.dumps(profile,indent=2)
    cm['data']['request.json']=json.dumps(request,indent=2)
    cm['data']['sequence-provenance.json']=json.dumps(dict(identifier='UniProtKB:P04637',length=393,
        source_file=str(fasta.relative_to(ROOT)),source_file_sha256=hashlib.sha256(raw).hexdigest(),sequence_sha256=hashlib.sha256(seq.encode()).hexdigest(),
        use='Fresh engineering capacity run only; no historical structure or acceptance reused',scientific_gate='CLOSED'))
    cm['data']['resident_offline.py']=(ROOT/'src/t01_phase1_real/resident_offline.py').read_bytes().decode()
    # Source hashes pin the existing strict loader and native implementation.
    hashes={n:hashlib.sha256(cm['data'][n].encode()).hexdigest() for n in ('run_structure.py','esmc_strict_loader.py','resident_offline.py')}
    cm['data']['launch.py']='''import fcntl,hashlib,json,os,runpy,socket,sys
from pathlib import Path
expected=HASHES
for name,digest in expected.items():
    assert hashlib.sha256((Path('/config')/name).read_bytes()).hexdigest()==digest
sys.path.insert(0,'/config')
lock=os.open('/shared/.gpu-execution.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
print('CAPACITY_WAITING_FOR_GPU_LOCK',flush=True)
fcntl.flock(lock,fcntl.LOCK_EX)
from resident_offline import restrict_sockets
restriction=restrict_sockets()
for family in (socket.AF_INET,socket.AF_INET6):
    try: socket.socket(family,socket.SOCK_STREAM)
    except PermissionError: pass
    else: raise RuntimeError('INET socket allowed')
root=Path('/shared/capacity393-20260918-r01')
root.mkdir(exist_ok=False)
(root/'network.json').write_text(json.dumps(dict(restriction=restriction,socket_probe='INET_INET6_DENIED')))
for name in ('request.json','profile.json','sequence-provenance.json'):
    (root/name).write_bytes((Path('/config')/name).read_bytes())
sys.argv=['/config/run_structure.py','--input','/config/request.json','--output-dir',str(root/'native'),'--profile','/config/profile.json']
print('ESMFOLD2_CAPACITY_START 393 experimental_not_supported_range',flush=True)
runpy.run_path('/config/run_structure.py',run_name='__main__')
print('ESMFOLD2_CAPACITY_NATIVE_COMPLETED_REQUIRES_AUDIT',flush=True)
'''.replace('HASHES',repr(hashes))
    job=copy.deepcopy(base[2]);job['metadata']['name']=NAME
    job['spec']['activeDeadlineSeconds']=1800
    pod=job['spec']['template']['spec']
    job['spec']['template']['metadata'].pop('annotations',None)
    pod['affinity']={'podAffinity':{'requiredDuringSchedulingIgnoredDuringExecution':[dict(labelSelector=dict(matchLabels={'app.kubernetes.io/name':'antigen-design'}),topologyKey='kubernetes.io/hostname')]}}
    c=pod['containers'][0];c['command']=['python','-u','-B','/config/launch.py'];c.pop('args',None)
    c['volumeMounts']=[m for m in c['volumeMounts'] if m['name']!='runtime']+[dict(name='shared',mountPath='/shared')]
    pod['volumes']=[v for v in pod['volumes'] if v['name']!='runtime']+[dict(name='shared',persistentVolumeClaim=dict(claimName='antigen-design-runtime'))]
    next(v for v in pod['volumes'] if v['name']=='config')['configMap']['name']=NAME
    network=copy.deepcopy(base[0]);network['metadata']['name']=NAME+'-no-egress'
    network['spec']['podSelector']['matchLabels']={'app':NAME}
    job['metadata']['labels']={'app':NAME};job['spec']['template']['metadata']['labels']={'app':NAME}
    return dict(apiVersion='v1',kind='List',items=[network,cm,job])

if __name__=='__main__':
    doc=render()
    OUT.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('CAPACITY393_MANIFEST_PREPARED',OUT)
