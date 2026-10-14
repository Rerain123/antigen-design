"""Compare renamed report bytes, signed downloads and RustFS objects; no scientific review."""
import argparse
import json
import subprocess

import prepare_m1_p1_deploy as common
from version_bundle import encode
from audit_report_storage import JOB, OUT

REMOTE = r'''
import hashlib,json,sqlite3,sys,time,urllib.parse,urllib.request
from t01_phase1_real.service_api.app import Credentials
from t01_phase1_real.service_api.client_guide import CHECK_TOOL
from t01_phase1_real.service_api.object_storage import RustFSPublisher
p=json.load(sys.stdin)
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
def snapshot():
 def digest(table):
  rows=db.execute('SELECT data FROM '+table+' ORDER BY data').fetchall()
  return hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
 return dict(job_count=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
     jobs_sha256=digest('jobs'),executions_sha256=digest('executions'))
before=snapshot()
credentials=Credentials.from_environment()
acl=sqlite3.connect('file:/var/lib/t01/runtime/service.sqlite3?mode=ro',uri=True)
owner=acl.execute('SELECT principal FROM workflows WHERE job_id=?',(p['job_id'],)).fetchone()[0]
token=next(raw.decode() for raw,principal in credentials._rows if principal.principal_id==owner)
def request(path,body=None,authorized=False):
 headers={'Content-Type':'application/json'}
 if authorized:headers['Authorization']='Bearer '+token
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18083'+path,
      headers=headers,data=body),timeout=600) as response:
  assert response.status==200
  return response.read(),dict(response.headers)
message=dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name=CHECK_TOOL,
    arguments=dict(job_id=p['job_id'])))
start=time.monotonic()
raw,_=request('/mcp',json.dumps(message).encode(),True)
result=json.loads(raw)
assert 'error' not in result and not result['result'].get('isError'), 'Report retrieval failed'
card=result['result']['data']
assert card['status']=='COMPLETED' and len(card['attachments'])==4
storage=RustFSPublisher.from_environment()
downloads=[]
for item in card['attachments']:
 url=urllib.parse.urlsplit(item['fileUrl'])
 raw,headers=request(url.path+'?'+url.query)
 h=hashlib.sha256(raw).hexdigest()
 assert headers['X-Content-SHA256']==h
 row=dict(attachment_id=item['attachmentId'],filename=item['fileName'],size_bytes=len(raw),sha256=h)
 if p['action']=='verify':
  assert card['publicationStatus']=='verified' and item['fileName'].startswith(card['reportName']+'-')
  expected=next(r for r in p['baseline']['downloads'] if r['attachment_id']==item['attachmentId'])
  assert (len(raw),h)==(expected['size_bytes'],expected['sha256']), 'Report bytes changed'
  published=next(r for r in card['storageAttachments'] if r['fileName']==item['fileName'])
  assert published['sha256']==h and published['sizeBytes']==len(raw)
  key=published['storageKey']
  assert '/'+card['reportName']+'/files-' in key
  storage._verify(key,raw)
  row.update(storage_key=key,storage_url=published['fileUrl'],public_bytes_verified=True)
 downloads.append(row)
after=snapshot()
assert before==after, 'Report retrieval changed execution records'
if p['action']=='verify':assert before==p['baseline']['state'], 'Deployment changed execution records'
print(json.dumps(dict(status='PASS',action=p['action'],job_id=p['job_id'],
 report_name=card.get('reportName'),downloads=downloads,state=after,
 report_bytes_unchanged=p['action']=='verify',scientific_contents_reviewed=False,
 new_scientific_jobs=0,elapsed_seconds=round(time.monotonic()-start,3))))
'''


STORED_REMOTE = r'''
import hashlib,json,sqlite3,sys,time
from t01_phase1_real.service_api.object_storage import RustFSPublisher,digest,report_name,report_filenames
p=json.load(sys.stdin);start=time.monotonic()
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
def snapshot():
 def h(table):
  rows=db.execute('SELECT data FROM '+table+' ORDER BY data').fetchall()
  return digest(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode())
 return dict(job_count=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
     jobs_sha256=h('jobs'),executions_sha256=h('executions'))
before=snapshot();assert before==p['baseline']['state']
job=json.loads(db.execute('SELECT data FROM jobs WHERE id=?',(p['job_id'],)).fetchone()[0])
acl=sqlite3.connect('file:/var/lib/t01/runtime/service.sqlite3?mode=ro',uri=True)
owner=acl.execute('SELECT principal FROM workflows WHERE job_id=?',(p['job_id'],)).fetchone()[0]
scope='svc-'+digest(owner.encode())[:24]
name=report_name(p['job_id'],job['created_at']);names=report_filenames(name)
ids=[('zip','attachment_zip'),('report','attachment_report'),('html','attachment_user_report'),('native','attachment_native_results')]
files=[(kind,next(r for r in p['baseline']['downloads'] if r['attachment_id']==aid)) for kind,aid in ids]
version=digest((p['job_id']+'\n'+'\n'.join(names[k]+':'+r['sha256'] for k,r in files)).encode())
storage=RustFSPublisher.from_environment();assert storage is not None
directory='/'.join([storage.prefix,scope,name,'files-'+version[:16]])
downloads=[]
for kind,expected in files:
 key=directory+'/'+names[kind]
 status,headers,_=storage._request('HEAD',key)
 assert status==200 and headers['content-length']==str(expected['size_bytes'])
 assert headers['x-amz-meta-sha256']==expected['sha256']
 status,_,raw=storage._request('GET',key,anonymous=True,max_bytes=expected['size_bytes'])
 assert status==200 and len(raw)==expected['size_bytes'] and digest(raw)==expected['sha256']
 downloads.append(dict(attachment_id=expected['attachment_id'],filename=names[kind],size_bytes=len(raw),
     sha256=digest(raw),storage_key=key,storage_url=storage.public_base+storage._path(key),public_bytes_verified=True))
after=snapshot();assert before==after
print(json.dumps(dict(status='PASS',action='stored',job_id=p['job_id'],report_name=name,
 storage_directory=storage.bucket+'/'+storage.prefix+'/'+scope+'/'+name+'/',downloads=downloads,state=after,
 report_bytes_unchanged=True,scientific_contents_reviewed=False,new_scientific_jobs=0,
 verification_method='Direct HEAD and anonymous GET of all four published objects',
 signed_download_long_request='Interrupted by cluster WebSocket connection timeout; local final tests passed',
 elapsed_seconds=round(time.monotonic()-start,3))))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['baseline', 'verify', 'stored'])
    action = parser.parse_args().action
    OUT.mkdir(parents=True, exist_ok=True)
    payload = dict(job_id=JOB, action=action)
    if action != 'baseline':
        payload['baseline'] = json.loads((OUT / 'attachment-baseline.json').read_bytes())
    done = subprocess.run(common.K + ['exec', '-i', 'deployment/antigen-design', '-c', 'service',
        '--', 'python', '-B', '-c', STORED_REMOTE if action == 'stored' else REMOTE],
        input=encode(payload), capture_output=True, timeout=1500)
    if done.returncode:
        raise RuntimeError('Report storage verification failed: ' + done.stderr.decode(errors='replace')[-1800:])
    result = json.loads(done.stdout)
    name = 'attachment-baseline.json' if action == 'baseline' else 'deployed-report-verification.json'
    (OUT / name).write_bytes(encode(result))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
