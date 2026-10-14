import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import prepare_m1_p1_deploy as c
REMOTE=r'''
import json,sqlite3,sys,hashlib
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.common import decode,sha,encode
from t01_phase1_real.development.esm_if1.source import registered,sources
from t01_phase1_real.development.esm_if1 import policy
from t01_phase1_real.development.workflow.service import source
jid='t01p1r-job-7ff412a6d443473bae22b1be05429206'
with sqlite3.connect('file:/var/lib/t01/runtime/service.sqlite3?mode=ro',uri=True) as db:
 owner=db.execute('SELECT principal FROM workflows WHERE job_id=?',(jid,)).fetchone()[0]
rt=Runtime('/var/lib/t01/runtime',scope=Principal(owner,frozenset({'query'}),'audit').runtime_scope)
j=rt.get(jid);e=rt.execution(jid);rows=e['nodes'];out=[]
def differences(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  return [d for k in set(a)|set(b) for d in differences(a.get(k),b.get(k),path+'/'+k)]
 if a!=b:return [dict(path=path,stored=a,current=b)]
 return []
for name,row in rows.items():
 if not name.startswith('cheap') or row.get('state')!='succeeded':continue
 with rt._db() as db:
  job,raw,value,request,files=registered(rt,db,source(rt,row)['artifact'],'t01.real.esm_if1')
  prepared,receipt=sources(rt,db,request,expected_run_id=j['run_id'])
 diffs=[]
 for k,v in prepared.items():
  if files.get(k)!=v:
   d=dict(path=k,stored_sha256=sha(files[k]),current_sha256=sha(v))
   if k.endswith('.json'):d['fields']=differences(decode(files[k]),decode(v))
   diffs.append(d)
 out.append(dict(node=name,job_id=job['job_id'],stored_profile=job['execution_profile'],current_profile=policy.registered_profile(),differences=diffs))
manifest=json.load(sys.stdin)
actual={k:sha((Path('/app/src')/k).read_bytes()) for k in manifest}
print(json.dumps(dict(job_id=jid,run_id=j['run_id'],state=j['state'],revision=j['revision'],esm_comparisons=out,source_mismatches=[k for k in manifest if manifest[k]!=actual[k]],python=sys.version,executable_sha256=sha(Path(sys.executable).read_bytes()))))
'''
value=c.remote(REMOTE,json.loads((c.ROOT/'deploy/scientific-report/r01/source-manifest.json').read_bytes()))
out=Path(__file__).parent/'input-comparison.json'
out.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(value,ensure_ascii=False))
