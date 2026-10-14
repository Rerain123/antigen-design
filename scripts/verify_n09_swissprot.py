"""Read-only real-database and request-routing verification; no scientific job submission."""
import argparse,base64,json,subprocess
from pathlib import Path
import prepare_m1_p1_deploy as c
import prepare_n09_swissprot as deployment

REMOTE=r'''
import sys,json,types,base64,sqlite3,zlib,time,hashlib,shutil
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
p=json.load(sys.stdin)
if p.get('preview'):
 for name in ['swissprot','indexed','policy','compute','service']:
  fullname='t01_phase1_real.development.domains.'+name
  module=__import__(fullname,fromlist=['*']) if name in ('policy','compute','service') else types.ModuleType(fullname)
  module.__package__='t01_phase1_real.development.domains'
  module.__file__='/app/src/t01_phase1_real/development/domains/'+name+'.py'
  sys.modules[fullname]=module
  exec(compile(base64.b64decode(p['preview'][name]),module.__file__,'exec'),module.__dict__)
from t01_phase1_real.common import encode,sha,decode
from t01_phase1_real.development.domains import policy,service
from t01_phase1_real.development.domains.swissprot import project
root=Path('/var/lib/t01/databases/domains');folder=root/'swissprot-2026_03-r01'
manifest=(folder/'manifest.json').read_bytes();status=json.loads((folder/'status.json').read_bytes())
assert status['state']=='imported_verified'
body=dict(user_sequence_id='n09-readonly-verification',protein_sequence='A'*19,organism_name='Homo sapiens',
 database_id=folder.name,database_manifest_sha256=sha(manifest),entry_id='P69905',parent=None,user_annotations=[],timeout_seconds=60,
 topology_input=dict(state='not_provided',artifact=None,reason_code=None),structure_input=dict(state='not_provided',artifact=None,reason_code=None))
with sqlite3.connect((folder/'annotations.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
 row=db.execute('SELECT record FROM entries WHERE accession=?',('P69905',)).fetchone()
 entry,_=project(zlib.decompress(row[0]),body);body['protein_sequence']=entry['sequence']['value']
policy.request(encode(body));start=time.monotonic();receipt,files=policy.database(root,body)
v=service.evaluate(body,files);cold=time.monotonic()-start
assert v['lookup']['selected_entry']=='P69905' and v['functional_domains']
start=time.monotonic();policy.database(root,body);warm=time.monotonic()-start
positive=dict(accession='P69905',domain_count=len(v['functional_domains']),cold_seconds=cold,warm_seconds=warm)
absent=dict(body,protein_sequence='A'*19,entry_id=None,organism_name=None)
_,f=policy.database(root,absent);missing=service.evaluate(absent,f)
assert missing['lookup']['status']=='no_exact_match'
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
owner=Principal('himat-t01-test',frozenset(['submit','query','download']),'not-a-credential')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
job=rt.get('t01p1r-job-c308ede7d6c843b180c82f91b3d44dec');request=decode(rt._request_bytes(job))
archived_snapshot=rt.workflow(job['job_id']);assert archived_snapshot['nodes']['domains']['job_id'] is None
actual=dict(absent,protein_sequence=request['protein_sequence'])
_,f=policy.database(root,actual);observed=service.evaluate(actual,f)
assert rt.get(job['job_id'])==job
result=dict(status='N09_SWISSPROT_READONLY_VERIFIED',records=status['records'],database_bytes=status['database_bytes'],
 manifest_sha256=sha(manifest),positive=positive,missing=missing['lookup'],actual_233aa=observed['lookup'],
 actual_233aa_domains=len(observed['functional_domains']),free_bytes=shutil.disk_usage(root).free,
 scientific_workflow_started=False,archived_job_unchanged=True,archived_workflow_verified=True)
if not p.get('preview'):
 from t01_phase1_real.service_api.himat import HiMatIntegration,TARGET_SWISSPROT_MANIFEST_SHA256
 assert TARGET_SWISSPROT_MANIFEST_SHA256==sha(manifest)
 captured=[]
 class Capture:
  def submit(self,principal,value):captured.append(value);return dict(job_id='not-submitted',state='queued')
 adapter=HiMatIntegration(Capture(),'https://example.invalid',b'k'*32)
 adapter.submit_sequence(owner,request['protein_sequence'],'Sus scrofa')
 b=captured[0]['request'];assert b['analysis']['domains']['organism_name'] is None
 from t01_phase1_real.development.workflow.service import request_for
 native,reason=request_for(rt,b,{},'domains');assert reason is None;policy.request(encode(native))
 assert native['database_manifest_sha256']==sha(manifest)
 result['source_hashes']={n:sha((Path('/app/src/t01_phase1_real')/n).read_bytes()) for n in p['files']}
 result['himat_n09_request_valid']=True
print(json.dumps(result))
'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--preview',action='store_true');args=ap.parse_args()
    payload=dict(files=list(deployment.FILES))
    if args.preview:payload['preview']={n:base64.b64encode((c.ROOT/'src/t01_phase1_real/development/domains'/ (n+'.py')).read_bytes()).decode() for n in ('swissprot','indexed','policy','compute','service')}
    result=c.remote(REMOTE,payload)
    if not args.preview:
        assert result['source_hashes']==deployment.hashes()
        live=json.loads(subprocess.check_output(c.K+['get','deployment','antigen-design','-o','json']))
        assert live['status'].get('readyReplicas')==1 and live['status']['observedGeneration']==live['metadata']['generation']
        con=next(x for x in live['spec']['template']['spec']['containers'] if x['name']=='service')
        assert con['args'][con['args'].index('--domains-database-root')+1]=='/var/lib/t01/databases/domains'
        result['generation']=live['metadata']['generation']
    name='n09-swissprot-'+('preview' if args.preview else 'deployment')+'-r01.json'
    (c.ROOT/'discovery/t01-phase1-real/m1-p4-20260922'/name).write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))

if __name__=='__main__':main()
