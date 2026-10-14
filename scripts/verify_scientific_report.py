"""Check the live result card and immutable downloads without launching science."""
import argparse
import json
import subprocess

import prepare_m1_p1_deploy as common
from version_bundle import encode

OUT=common.ROOT/'reports/scientific-report-20261011/deployment'
REVIEW=OUT.parent
REMOTE_DIR='/var/lib/t01/scientific-report-verification-20261011-r02'

# Keep the long HTTP check inside the Pod so a gateway exec timeout cannot
# interrupt report collection. No credential or signed URL is written to disk.
WORKER=r'''
import hashlib,json,sqlite3,time,urllib.parse,urllib.request
from pathlib import Path
from t01_phase1_real.service_api.app import Credentials
from t01_phase1_real.service_api.client_guide import CHECK_TOOL
from t01_phase1_real.service_api.object_storage import RustFSPublisher
root=Path(__file__).parent;p=json.loads((root/'input.json').read_bytes())
def write(name,value):
 raw=json.dumps(value,ensure_ascii=False).encode();temp=root/(name+'.tmp');temp.write_bytes(raw);temp.replace(root/name)
def snapshot():
 with sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True) as db:
  def h(table):
   return hashlib.sha256(json.dumps(db.execute('SELECT data FROM '+table+' ORDER BY data').fetchall(),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
  return dict(job_count=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],jobs_sha256=h('jobs'),executions_sha256=h('executions'))
def get(path,body=None,token=None):
 headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18083'+path,headers=headers,data=body),timeout=1200) as r:
  assert r.status==200
  return r.read(),dict(r.headers)
start=time.monotonic()
try:
 before=snapshot();assert before==p['before']
 with sqlite3.connect('file:/var/lib/t01/runtime/service.sqlite3?mode=ro',uri=True) as db:
  owner=db.execute('SELECT principal FROM workflows WHERE job_id=?',(p['job_id'],)).fetchone()[0]
 token=next(raw.decode() for raw,principal in Credentials.from_environment()._rows if principal.principal_id==owner)
 write('progress.json',dict(stage='requesting_existing_result_card'))
 message=dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name=CHECK_TOOL,arguments=dict(job_id=p['job_id'])))
 raw,_=get('/mcp',json.dumps(message).encode(),token);response=json.loads(raw)
 if 'error' in response or response['result'].get('isError'):
  write('request-error.json',response.get('error') or response['result'].get('structuredContent'))
  raise AssertionError('Result card failed')
 card=response['result']['data'];assert card['status']=='COMPLETED' and card['publicationStatus']=='verified'
 assert card['primaryAttachmentId']=='attachment_user_report' and len(card['attachments'])==4
 write('progress.json',dict(stage='verifying_stored_attachments'))
 storage=RustFSPublisher.from_environment();downloads=[]
 for item in card['storageAttachments']:
  baseline=next(r for r in p['expected'] if r['filename']==item['fileName'])
  assert item['sha256']==baseline['sha256'] and item['sizeBytes']==baseline['size_bytes']
  status,headers,_=storage._request('HEAD',item['storageKey']);assert status==200
  status,_,raw=storage._request('GET',item['storageKey'],anonymous=True,max_bytes=baseline['size_bytes'])
  assert status==200 and len(raw)==baseline['size_bytes'] and hashlib.sha256(raw).hexdigest()==baseline['sha256']
  downloads.append(dict(filename=item['fileName'],sha256=item['sha256'],size_bytes=len(raw),url=item['fileUrl'],public_bytes_verified=True))
 write('progress.json',dict(stage='verifying_signed_html_download'))
 signed=next(a for a in card['attachments'] if a['attachmentId']=='attachment_user_report')
 url=urllib.parse.urlsplit(signed['fileUrl']);raw,headers=get(url.path+'?'+url.query)
 assert hashlib.sha256(raw).hexdigest()==p['html_sha256']==headers['X-Content-SHA256']
 assert '抗原设计科学报告'.encode() in raw and b't01p1r-job-' not in raw
 after=snapshot();assert before==after
 # Prior published HTML remains immutable and readable.
 old=p['old_html'];status,_,raw=storage._request('GET',old['storage_key'],anonymous=True,max_bytes=old['size_bytes'])
 assert status==200 and hashlib.sha256(raw).hexdigest()==old['sha256']
 write('result.json',dict(status='PASS',job_id=p['job_id'],report_name=card['reportName'],downloads=downloads,
  signed_html_download_verified=True,old_html_preserved=True,original_other_attachments_unchanged=True,
  state=after,new_scientific_jobs=0,elapsed_seconds=round(time.monotonic()-start,3)))
except Exception as exc:
 write('result.json',dict(status='FAIL',error_type=type(exc).__name__,elapsed_seconds=round(time.monotonic()-start,3)))
 raise
'''


def start():
    old=json.loads((common.ROOT/'reports/report-storage-20261011/deployed-report-verification.json').read_bytes())
    review=json.loads((REVIEW/'closeout.json').read_bytes())
    expected=[dict(filename=r['filename'],sha256=r['sha256'],size_bytes=r['size_bytes']) for r in old['downloads']]
    html=next(r for r in expected if r['filename'].endswith('.html'))
    html.update(sha256=review['output']['sha256'],size_bytes=review['output']['size_bytes'])
    payload=dict(job_id=old['job_id'],before=json.loads((OUT/'previous-task-before.json').read_bytes()),
                 expected=expected,html_sha256=html['sha256'],old_html=next(r for r in old['downloads'] if r['filename'].endswith('.html')))
    result=common.remote(r'''
import json,os,subprocess,sys
from pathlib import Path
p=json.load(sys.stdin);root=Path(p['root']);root.mkdir(exist_ok=False)
(root/'input.json').write_text(json.dumps(p['payload']));(root/'verify.py').write_text(p['code'])
with (root/'worker.log').open('wb') as log:
 process=subprocess.Popen([sys.executable,'-B',str(root/'verify.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps(dict(status='STARTED',pid=process.pid)))
''',dict(root=REMOTE_DIR,payload=payload,code=WORKER))
    (OUT/'report-check-started.json').write_bytes(encode(result));print(json.dumps(result))


def check():
    result=common.remote(r'''
import json,sys
from pathlib import Path
root=Path(json.load(sys.stdin)['root']);done=root/'result.json';progress=root/'progress.json'
print(done.read_text() if done.exists() else json.dumps(dict(status='RUNNING',progress=json.loads(progress.read_bytes()) if progress.exists() else {})))
''',dict(root=REMOTE_DIR))
    if result['status']!='RUNNING':(OUT/'deployed-report-verification.json').write_bytes(encode(result))
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['start','check'])
    globals()[parser.parse_args().action]()
