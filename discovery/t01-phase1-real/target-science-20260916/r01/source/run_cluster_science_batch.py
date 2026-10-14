import argparse,base64,importlib.util,json,sys,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import deploy_resident_cluster as d
OUT=ROOT/'discovery/t01-phase1-real/target-science-20260916/r01'
REMOTE_ROOT='/var/lib/t01/target-science-20260916-r01'
REMOTE='''
import base64,json,sys,time
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.common import encode,sha,TERMINAL
a=json.load(sys.stdin)
rt=Runtime(Path(a['root']))
if a['action']=='start':
    if a.get('data'):j=rt.submit_structure(encode(a['body']),a['case'],base64.b64decode(a['data']))
    else:j=rt.submit_sequence(encode(a['body']),a['case'],a['tool'])
    if j['state']=='queued':j=rt.dispatch(j['job_id'])
elif a['action']=='cancel':
    j=rt.get(a['job_id']);ex=rt.execution(j['job_id']);target=Path(ex['resident_target'])
    for _ in range(100):
        if (target/'output/native/runtime_started.json').exists() or (target/'execution.json').exists() and json.loads((target/'execution.json').read_bytes()).get('stopped_confirmed'):break
        time.sleep(.1)
    before=dict(job=j,execution=rt.execution(j['job_id']),native_started=(target/'output/native/runtime_started.json').exists(),resident_receipt=json.loads((target/'execution.json').read_bytes()) if (target/'execution.json').exists() else None)
    assert before['native_started'],'Native execution has not started'
    assert not (before['resident_receipt'] or {}).get('stopped_confirmed'),'Native process already stopped; cannot claim in-flight cancellation'
    j=rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=a['job_id'],idempotency_key=a['case']+'-cancel')))
elif a['action']=='recover':
    before=dict(job=rt.get(a['job_id']),execution=rt.execution(a['job_id']))
    j=rt.recover(a['job_id'])
else:
    j=rt.get(a['job_id'])
    if j['state'] not in TERMINAL:j=rt.reconcile(j['job_id'])
value=dict(job=j,execution=rt.execution(j['job_id']),events=rt.events(j['job_id']))
if a['action'] in ('cancel','recover'):value['lifecycle_before']=before
if j['state'] in TERMINAL:
    value['request']=json.loads(rt._request_bytes(j))
    value['artifacts']=[]
    for ref in j['artifacts']:
        raw=rt.artifact_bytes(j['job_id'],ref['artifact_id'])
        assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256']
        value['artifacts'].append(dict(ref=ref,data=base64.b64encode(raw).decode()))
    if j['artifacts']:value['result']=rt.result(j['job_id'])
assert not j['usable_for_pipeline']
print(json.dumps(value))
'''
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(d.encoded(value))
def ref(case):
    j=json.loads((OUT/case/'job.json').read_bytes());assert j['state']=='succeeded'
    return next(a for a in j['artifacts'] if a['role']=='result')
def source(case):
    j=json.loads((OUT/case/'job.json').read_bytes())
    return dict(job_id=j['job_id'],artifact=next((a for a in j['artifacts'] if a['role'] in ('result','diagnostic')),None))
def payload(case):
    from structure_integration_cases import SEQUENCE,metadata,cases
    if case=='structure-design':
        raw=(ROOT/'discovery/t01-phase1-real/w5/esm-if1-assets-20260908/reference.pdb').read_bytes()
        return dict(body=metadata(fmt='PDB',source='unknown'),data=base64.b64encode(raw).decode())
    if case=='structure-n10':
        c=next(c for c in cases() if c['name']=='normal-cif')
        return dict(body=c['request'],data=base64.b64encode(c['data']).decode())
    if case.startswith('proteinmpnn'):
        from run_proteinmpnn_acceptance import request
        return dict(body=request(SEQUENCE,ref('structure-design'),'target new independent engineering sample',n_designs=1,seed=31),tool='t01.real.proteinmpnn')
    if case=='esm-if1':
        return dict(body=dict(protein_sequence=SEQUENCE,user_sequence_id='target new engineering rescore',structure_artifact=ref('structure-design'),n11_artifact=ref('proteinmpnn'),sample_numbers=[1],baseline_artifact=None,timeout_seconds=180),tool='t01.real.esm_if1')
    if case=='thermompnn':
        from run_thermompnn_acceptance import request
        return dict(body=request(ref('structure-design')),tool='t01.real.thermompnn')
    if case.startswith('foldx'):
        from run_foldx_acceptance import scan_request,build_request
        body=scan_request(ref('structure-design')) if case.startswith('foldx-scan') else build_request(ref('structure-design'))
        return dict(body=body,tool='t01.real.foldx')
    if case=='n10':
        from run_developability_acceptance import request
        return dict(body=request(SEQUENCE,dict(state='available',artifact=ref('structure-n10'),reason_code=None)),tool='t01.real.developability')
    if case=='n16':
        from run_codon_acceptance import body
        return dict(body=body(),tool='t01.real.optimize_codons')
    if case=='wt-reference':
        from t01_phase1_real.development.wt_reference import policy
        body=dict(protein_sequence=SEQUENCE,user_sequence_id='target fresh engineering scan reference; no scientific signoff',upstream={n:None for n in policy.PRODUCERS},timeout_seconds=60)
        body['upstream'].update(structure=source('structure-design'),foldx=source('foldx-scan-r02'),thermompnn=source('thermompnn'))
        return dict(body=body,tool=policy.TOOL)
    if case=='scan-report':
        from t01_phase1_real.development.local_delivery import policy
        body=dict(protein_sequence=SEQUENCE,user_sequence_id='target fresh engineering report with explicit failed ThermoMPNN',host_species=None,expression_host=None,dna_bindings=[],upstream={n:None for n in policy.PRODUCERS},timeout_seconds=60)
        body['upstream']['wt_reference']=source('wt-reference')
        return dict(body=body,tool=policy.TOOL)
    raise ValueError(case)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('action');ap.add_argument('case',nargs='?');a=ap.parse_args()
    if a.action=='batch':
        for name in a.case.split(',') if a.case else ['proteinmpnn','esm-if1','thermompnn','foldx-scan','foldx-build','structure-n10','n10','n16']:
            try:
                p=OUT/name/'job.json'
                sys.argv=[sys.argv[0],'poll' if p.exists() else 'start',name];main()
                if name.endswith('-cancel') or name.endswith('-recover'):
                    sys.argv=[sys.argv[0],name.rsplit('-',1)[1],name];main()
                deadline=time.monotonic()+1800
                while json.loads(p.read_bytes())['state'] not in ('succeeded','failed','cancelled','timed_out'):
                    if time.monotonic()>deadline:raise RuntimeError('Collection deadline; do not submit dependent GPU work')
                    time.sleep(5);sys.argv=[sys.argv[0],'poll',name];main()
            except Exception as exc:
                save(OUT/name/'harness-error.json',dict(error=str(exc)));print(name,str(exc),flush=True)
                if p.exists() and json.loads(p.read_bytes())['state'] not in ('succeeded','failed','cancelled','timed_out'):raise
        return
    if a.action in ('snapshot','snapshot-final'):
        dep=d.get('deployment',d.NAME);pods=d.current_pods(dep)
        value=dict(generation=dep['metadata']['generation'],observed=dep['status']['observedGeneration'],pods=[dict(name=p['metadata']['name'],node=p['spec']['nodeName'],containers=[{k:c.get(k) for k in ('name','image','imageID','ready','restartCount')} for c in p['status']['containerStatuses']],resources=[dict(name=c['name'],resources=c.get('resources')) for c in p['spec']['containers']]) for p in pods])
        save(OUT/('site.json' if a.action=='snapshot' else 'site-final.json'),value);print(json.dumps(dict(generation=value['generation'],observed=value['observed'],pods=[dict(name=p['name'],ready=sum(c['ready'] for c in p['containers']),restarts=sum(c['restartCount'] for c in p['containers'])) for p in value['pods']])));return
    if a.action=='diagnose':
        code='''
import json,hashlib,importlib.metadata as md
from pathlib import Path
from t01_phase1_real.development.foldx import policy as f
from t01_phase1_real.development.codon import policy as c
rows=[]
for p in [f.PACKAGE,f.PACKAGE/'assets.json',f.EXECUTABLE]:
    rows.append(dict(path=str(p),exists=p.exists(),is_file=p.is_file()))
m=json.loads((c.HERE/'assets/manifest.json').read_bytes());packages=[]
for name,entry in m['packages'].items():
    try:dist=md.distribution(name)
    except md.PackageNotFoundError:
        packages.append(dict(name=name,version=None,expected_version=entry['version'],matched=0,mismatches=[dict(reason='PACKAGE_MISSING')]));continue
    mismatches=[];matched=0
    for item in entry['files']:
        p=Path(dist.locate_file(item['path']))
        if not p.is_file():mismatches.append(dict(path=item['path'],reason='missing'));continue
        raw=p.read_bytes()
        if len(raw)==item['size_bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']:matched+=1;continue
        lf=raw.replace(b'\\r\\n',b'\\n')
        newline=any(len(x)==item['size_bytes'] and hashlib.sha256(x).hexdigest()==item['sha256'] for x in (lf,lf.replace(b'\\n',b'\\r\\n')))
        mismatches.append(dict(path=item['path'],actual_size=len(raw),actual_sha256=hashlib.sha256(raw).hexdigest(),newline_only=newline))
    packages.append(dict(name=name,version=dist.version,expected_version=entry['version'],matched=matched,mismatches=mismatches))
print(json.dumps(dict(foldx_paths=rows,codon=packages)))
'''
        value=json.loads(d.kubectl('exec','deployment/'+d.NAME,'-c','service','--','python','-B','-c',code))
        save(OUT/'deployment-diagnostics.json',value)
        print(json.dumps(dict(foldx_paths=value['foldx_paths'],codon=[dict(name=r['name'],matched=r['matched'],mismatched=len(r['mismatches']),newline_only=sum(x.get('newline_only',False) for x in r['mismatches'])) for r in value['codon']])));return
    if a.action=='foldx-check':
        manifest=(ROOT/'var/t01-phase1-real/tool-assets/foldx-20270131/assets.json').read_bytes()
        code='''
import sys,json,hashlib
from pathlib import Path
m=json.load(sys.stdin);rows=[]
for r in m['files']:
    p=Path('/app')/r['path'];raw=p.read_bytes()
    assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256'],str(p)
    rows.append(dict(path=r['path'],sha256=r['sha256'],bytes=len(raw)))
print(json.dumps(dict(status='PASS',files=rows)))
'''
        value=json.loads(d.kubectl('exec','-i','deployment/'+d.NAME,'-c','service','--','python','-B','-c',code,data=manifest))
        save(OUT/'foldx-asset-verification.json',value)
        save(OUT/'foldx-registry-source.json',dict(path='var/t01-phase1-real/tool-assets/foldx-20270131/assets.json',sha256=hashlib.sha256(manifest).hexdigest(),bytes=len(manifest)))
        print(json.dumps(dict(status=value['status'],verified=len(value['files']))));return
    if a.action=='foldx-supplement':
        assert json.loads((OUT/'foldx-asset-verification.json').read_bytes())['status']=='PASS'
        manifest=(ROOT/'var/t01-phase1-real/tool-assets/foldx-20270131/assets.json').read_bytes()
        identity=json.loads((OUT/'foldx-registry-source.json').read_bytes())
        assert hashlib.sha256(manifest).hexdigest()==identity['sha256']
        dep=d.get('deployment',d.NAME);current=d.current_pods(dep);assert len(current)==1
        service=next(c for c in current[0]['status']['containerStatuses'] if c['name']=='service')
        name='antigen-foldx-registry-r01'
        code='''
import base64,json,hashlib,sys
from pathlib import Path
raw=base64.b64decode(sys.argv[1]);m=json.loads(raw);root=Path('/assets')
for r in m['files']:
    rel=Path(r['path']).relative_to('var/t01-phase1-real/tool-assets')
    p=root/rel;assert not p.is_symlink() and p.resolve().is_relative_to(root)
    b=p.read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
p=root/'foldx-20270131/assets.json'
assert not p.exists(),'Do not overwrite existing registry'
with p.open('xb') as f:f.write(raw)
assert p.read_bytes()==raw
print(json.dumps(dict(status='PASS',created=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),verified_assets=len(m['files']))))
'''
        pod=dict(apiVersion='v1',kind='Pod',metadata=dict(name=name,namespace=d.NS,labels={'app':name}),spec=dict(
            restartPolicy='Never',activeDeadlineSeconds=180,automountServiceAccountToken=False,nodeName=current[0]['spec']['nodeName'],
            securityContext=dict(runAsNonRoot=True,runAsUser=10001,runAsGroup=10001,fsGroup=10001),
            imagePullSecrets=current[0]['spec'].get('imagePullSecrets',[]),volumes=[dict(name='assets',persistentVolumeClaim=dict(claimName='antigen-design-assets'))],
            containers=[dict(name='registry',image=service['imageID'],imagePullPolicy='IfNotPresent',command=['python','-B','-c',code,base64.b64encode(manifest).decode()],
                securityContext=dict(allowPrivilegeEscalation=False,readOnlyRootFilesystem=True,capabilities=dict(drop=['ALL'])),
                resources=dict(requests=dict(cpu='50m',memory='64Mi'),limits=dict(cpu='500m',memory='128Mi')),
                volumeMounts=[dict(name='assets',mountPath='/assets')])]))
        save(OUT/'foldx-registry-pod.json',pod)
        d.kubectl('create','-f','-',data=d.encoded(pod));print('Registry supplement pod created',flush=True)
        for _ in range(30):
            p=d.get('pod',name)
            if p['status']['phase'] in ('Succeeded','Failed'):break
            time.sleep(3)
        save(OUT/'foldx-registry-pod-status.json',dict(name=name,phase=p['status']['phase'],containers=p['status'].get('containerStatuses')))
        log=d.kubectl('logs',name,'-c','registry');(OUT/'foldx-registry-pod.log').write_bytes(log)
        assert p['status']['phase']=='Succeeded',log.decode()
        print(log.decode(),flush=True)
        assert p['metadata']['labels']['app']==name and p['spec']['volumes'][0]['persistentVolumeClaim']['claimName']=='antigen-design-assets'
        d.kubectl('delete','pod',name,'--wait=false');print('Temporary registry pod removed; PVC retained');return
    case=OUT/a.case
    data=dict(action=a.action,case=a.case,root=REMOTE_ROOT)
    if a.action=='start':
        assert not (case/'job.json').exists(),'Use poll/recover; do not resubmit an uncertain dispatch'
        data.update(payload(a.case));save(case/'submission.json',data)
    else:data['job_id']=json.loads((case/'job.json').read_bytes())['job_id']
    value=json.loads(d.kubectl('exec','-i','deployment/'+d.NAME,'-c','service','--','python','-B','-c',REMOTE,data=json.dumps(data).encode()))
    for key in ('job','execution','events','request','result','lifecycle_before'):
        if key in value:save(case/(key+'.json'),value[key])
    for artifact in value.get('artifacts',[]):
        raw=base64.b64decode(artifact['data']);r=artifact['ref']
        assert len(raw)==r['size_bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256']
        p=case/'artifacts'/r['artifact_id'];p.parent.mkdir(exist_ok=True);p.write_bytes(raw)
    print(json.dumps(dict(case=a.case,**{k:value['job'].get(k) for k in ('job_id','attempt_id','state','error_code')},artifacts=len(value.get('artifacts',[])))),flush=True)
if __name__=='__main__':main()
