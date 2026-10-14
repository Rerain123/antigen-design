"""Query existing reports, verify actual RustFS bytes; never submit science."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'scripts'))
import prepare_m1_p1_deploy as common

REMOTE = r'''
import json, sqlite3, urllib.request, time, hashlib, re
from t01_phase1_real.service_api.app import Credentials
from t01_phase1_real.service_api.client_guide import CHECK_TOOL
from t01_phase1_real.service_api.object_storage import RustFSPublisher
p=json.load(__import__('sys').stdin)
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
def snap():
 return {t:hashlib.sha256(json.dumps(db.execute('SELECT data FROM '+t+' ORDER BY data').fetchall(),separators=(',',':')).encode()).hexdigest() for t in ('jobs','executions')}
before=snap()
count=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
acl=sqlite3.connect('file:/var/lib/t01/runtime/service.sqlite3?mode=ro',uri=True)
owner=acl.execute('SELECT principal FROM workflows WHERE job_id=?',(p['job_id'],)).fetchone()[0]
token=next(raw.decode() for raw,principal in Credentials.from_environment()._rows if principal.principal_id==owner)
body=dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name=CHECK_TOOL,arguments=dict(job_id=p['job_id'])))
req=urllib.request.Request('http://127.0.0.1:18083/mcp',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
start=time.monotonic()
with urllib.request.urlopen(req,timeout=600) as response:value=json.load(response)
assert 'error' not in value, value.get('error')
result=value['result']
if result.get('isError'):
 print(json.dumps(dict(status='QUERY_FAILED',job_id=p['job_id'],error=result),ensure_ascii=False))
 __import__('sys').exit(0)
card=result['data']
assert card['status']=='COMPLETED' and card['publicationStatus']=='verified', card['status']
assert card['reportName']==p['report_name']
assert ('去重后 '+str(p['count'])+' 条') in card['summaryText']
out=dict(job_id=p['job_id'],elapsed_seconds=round(time.monotonic()-start,3),status=card['status'],report_name=card['reportName'],publication_status=card['publicationStatus'],attachments=[])
storage=RustFSPublisher.from_environment()
for attachment in card['storageAttachments']:
 a={k:attachment.get(k) for k in ('fileName','sha256','sizeBytes','storageKey')}
 status,headers,_=storage._request('HEAD',a['storageKey'])
 assert status==200 and headers.get('content-length')==str(a['sizeBytes']) and headers.get('x-amz-meta-sha256')==a['sha256']
 status,_,raw=storage._request('GET',a['storageKey'],anonymous=True,max_bytes=a['sizeBytes'])
 assert status==200 and hashlib.sha256(raw).hexdigest()==a['sha256']
 a.update(metadata_verified=True,public_download_verified=True)
 if a['fileName'].endswith('-report.html'):
  html=raw.decode()
  forbidden=['完整验收','暂定验收','完整评估','科学复核','结果使用状态','完整覆盖']
  assert not any(word in html for word in forbidden)
  assert p['report_name'] in html and ('去重后 '+str(p['count'])+' 条') in html
  assert html.count('class="candidate-card"')==p['count']
  ids=re.findall(r'id="(candidate-[^"]+)"',html)
  assert len(ids)==len(set(ids))==p['count']
  assert set(re.findall(r'href="#(candidate-[^"]+)"',html))==set(ids)
  a.update(acceptance_labels_removed=True,unique_candidates=p['count'],internal_links_valid=True,local_preview_sha256=p['html_sha256'],matches_local_preview=a['sha256']==p['html_sha256'])
  assert a['matches_local_preview'], 'Online HTML differs from verified local preview'
 elif a['fileName']==p['report_name']+'-results.zip':
  assert a['sha256']==p['package_sha256'], 'Original scientific package changed'
  a['original_package_unchanged']=True
 out['attachments'].append(a)
assert len(out['attachments'])==4
assert any(a.get('acceptance_labels_removed') for a in out['attachments'])
assert any(a.get('original_package_unchanged') for a in out['attachments'])
assert before==snap() and count==db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
out.update(scientific_state_unchanged=True,job_count=count,new_scientific_jobs=0,status='PASS')
print(json.dumps(out,ensure_ascii=False))
'''

if __name__ == '__main__':
    label = sys.argv[1]
    assert label in ('old', 'new')
    audit = json.loads((HERE / 'results-only-audit.json').read_bytes())
    implementation = json.loads((HERE / 'implementation.json').read_bytes())
    index = 0 if label == 'old' else 1
    item = audit['reports'][index]
    payload = dict(job_id='t01p1r-job-' + ('c4081362c5294a8bac8f1d0fe26d96a1' if label == 'old' else 'd6498f2fecdf4632b274c3bc6ebd165e'),
                   count=32 if label == 'old' else 6,
                   report_name=item['file'].removesuffix('-report-corrected.html'),
                   html_sha256=item['sha256'], package_sha256=implementation['source_packages'][label]['sha256'])
    process = subprocess.run(common.K + ['exec', '-i', 'deployment/antigen-design', '-c', 'service', '--', 'python', '-B', '-c', REMOTE],
                             input=json.dumps(payload).encode(), capture_output=True, timeout=650)
    if process.returncode:
        raise RuntimeError(process.stderr.decode(errors='replace')[-1800:])
    value = json.loads(process.stdout)
    (HERE / 'deployment-r02' / (label + '-report-publication.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if value['status'] != 'PASS':
        print(json.dumps(value,ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps(dict(status=value['status'],report_name=value['report_name'],attachments=len(value['attachments']),scientific_state_unchanged=value['scientific_state_unchanged'],elapsed_seconds=value['elapsed_seconds']),ensure_ascii=False))
