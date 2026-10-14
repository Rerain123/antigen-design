"""Retrieve the existing HiMat report and verify publication; no submission."""
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import prepare_m1_p1_deploy as common

REMOTE=r'''
import json,sqlite3,urllib.request,time,hashlib
from t01_phase1_real.service_api.app import Credentials
from t01_phase1_real.service_api.client_guide import CHECK_TOOL
from t01_phase1_real.service_api.object_storage import RustFSPublisher
jid='t01p1r-job-c4081362c5294a8bac8f1d0fe26d96a1'
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
def snap():
 return {t:hashlib.sha256(json.dumps(db.execute('SELECT data FROM '+t+' ORDER BY data').fetchall(),separators=(',',':')).encode()).hexdigest() for t in ('jobs','executions')}
before=snap();acl=sqlite3.connect('file:/var/lib/t01/runtime/service.sqlite3?mode=ro',uri=True)
owner=acl.execute('SELECT principal FROM workflows WHERE job_id=?',(jid,)).fetchone()[0]
token=next(raw.decode() for raw,p in Credentials.from_environment()._rows if p.principal_id==owner)
body=dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name=CHECK_TOOL,arguments=dict(job_id=jid)))
req=urllib.request.Request('http://127.0.0.1:18083/mcp',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
start=time.monotonic()
with urllib.request.urlopen(req,timeout=600) as response:value=json.load(response)
out=dict(job_id=jid,elapsed_seconds=round(time.monotonic()-start,3))
if 'error' in value:out['error']=value['error']
else:
 result=value['result'];out['isError']=result.get('isError');card=result.get('data',{})
 out.update({k:card.get(k) for k in ['status','reportName','publicationStatus']})
 if result.get('isError') or not card:out['response']=result
 out['attachments']=[{k:a.get(k) for k in ['fileName','sha256','sizeBytes','storageKey']} for a in card.get('storageAttachments',[])]
 storage=RustFSPublisher.from_environment()
 for a in out['attachments']:
  status,headers,_=storage._request('HEAD',a['storageKey'])
  a['head_status']=status;a['metadata_verified']=status==200 and headers.get('content-length')==str(a['sizeBytes']) and headers.get('x-amz-meta-sha256')==a['sha256']
  status,_,raw=storage._request('GET',a['storageKey'],anonymous=True,max_bytes=a['sizeBytes'])
  a['public_download_verified']=status==200 and hashlib.sha256(raw).hexdigest()==a['sha256']
out['scientific_state_unchanged']=before==snap();out['new_scientific_jobs']=0
print(json.dumps(out,ensure_ascii=False))
'''
if __name__=='__main__':
    p=subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',REMOTE],capture_output=True,timeout=650)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-1800:])
    value=json.loads(p.stdout)
    Path(__file__).with_name('current-report-publication.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value,ensure_ascii=False,indent=2))
