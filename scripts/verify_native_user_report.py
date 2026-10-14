"""Verify installed report code using real owner-authenticated HTTP downloads.

Only existing terminal outputs are read. Credentials stay inside the service
container; no new workflow/model execution or scientific decision is requested.
"""
import argparse
import json
import subprocess

import prepare_m1_p1_deploy as common
from version_bundle import encode, sha
from t01_phase1_real.common import encode as native_encode

OUT=common.ROOT/'reports/expert-revision-v2-results-20260930'
RUN=OUT/'r01'
SUBMISSION=common.ROOT/'reports/expert-revision-v2-resume-20260930/continuation-submission.json'

REMOTE=r'''
import base64,io,json,sqlite3,sys,time,urllib.error,urllib.request,zipfile
from pathlib import Path
from t01_phase1_real.common import decode,encode,sha
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.development import Runtime
p=json.load(sys.stdin)
credentials=json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials']
rows=[r for r in credentials if sha(r['principal'].encode())==p['owner']]
assert len(rows)==1
credential=rows[0]
principal=Principal(credential['principal'],frozenset(credential['scopes']),'not-a-credential')
rt=Runtime('/var/lib/t01/runtime',scope=principal.runtime_scope)
parent=rt.get(p['job_id']);assert parent['state']=='succeeded'
def count():
 with sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True) as db:
  return db.execute('SELECT count(*) FROM jobs').fetchone()[0]
def request(path,token=None,data=None):
 headers={'Content-Type':'application/json'}
 if token is not None:headers['Authorization']='Bearer '+token
 started=time.monotonic()
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18083'+path,
       headers=headers,data=data),timeout=150) as response:
  raw=response.read();assert response.status==200
  return raw,dict(response.headers),round(time.monotonic()-started,3)
before=count();input_hash=sha(rt._request_bytes(parent));parent_hash=sha(encode(parent))
if p['action']=='native':
 endpoint='/v1/workflows/'+p['job_id']+'/native-results'
 foreign=[r for r in credentials if r['principal']!=credential['principal'] and 'download' in r['scopes']]
 assert foreign,'A distinct registered download identity is required for the owner test'
 for token,expected in [(None,401),(foreign[0]['token'],403)]:
  try:request(endpoint,token)
  except urllib.error.HTTPError as exc:assert exc.code==expected
  else:raise AssertionError('Private native outputs were accessible without their owner')
 raw,headers,seconds=request(endpoint,credential['token'])
 assert sha(raw)==p['native_sha256'] and len(raw)==p['native_size_bytes']
 assert headers['Digest']=='sha-256='+sha(raw) and int(headers['Content-Length'])==len(raw)
 assert headers['Content-Type']=='application/zip'
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  manifest=decode(z.read('manifest.json'));assert manifest['job_id']==p['job_id']
  for item in manifest['files']:
   value=z.read(item['path']);assert len(value)==item['size_bytes'] and sha(value)==item['sha256']
  assert sha(z.read('original-workflow-package.zip'))==p['package_sha256']
 value=dict(http_status=200,elapsed_seconds=seconds,size_bytes=len(raw),sha256=sha(raw),
   manifest_files=len(manifest['files']),original_package_sha256=p['package_sha256'],
   unauthenticated_rejected=True,foreign_owner_rejected=True)
else:
 message=dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(
   name='t01_phase1_real_service_v01.tool.workflow.report',arguments=dict(job_id=p['job_id'])))
 raw,headers,seconds=request('/mcp',credential['token'],encode(message))
 response=decode(raw);assert 'error' not in response
 result=response['result'];assert not result.get('isError')
 report=result['structuredContent'];snapshot=report['native_results']
 assert sha(encode(snapshot))==p['snapshot_sha256']
 assert report['sha256']==p['package_sha256']
 assert report['scientific_gate']=='CLOSED' and report['production_status']=='NOT_DEPLOYED'
 assert report['usable_for_pipeline'] is False
 package,package_headers,package_seconds=request('/v1/workflows/'+p['job_id']+'/report',credential['token'])
 assert sha(package)==p['package_sha256']
 from t01_phase1_real.service_api.user_report import from_workflow_package
 html=from_workflow_package(package,native_results=snapshot)
 assert sha(html)==p['html_sha256'] and len(html)==p['html_size_bytes']
 assert all(v in html.decode() for v in ('-1.758342','0.787493','108528','25.479090','CIF'))
 value=dict(http_status=200,mcp_report_seconds=seconds,original_package_seconds=package_seconds,
   html_size_bytes=len(html),html_sha256=sha(html),snapshot_sha256=sha(encode(snapshot)),
   workflow_package_sha256=sha(package),installed_user_report_rendered=True,
   report_publication_status=report.get('publication_status'))
assert count()==before and sha(rt._request_bytes(rt.get(p['job_id'])))==input_hash
assert sha(encode(rt.get(p['job_id'])))==parent_hash
value.update(status='PASS',job_id=p['job_id'],run_id=parent['run_id'],job_count=before,
 new_jobs=0,new_model_calls=0,original_results_modified=False,
 scientific_gate='CLOSED',production_status='NOT_DEPLOYED')
print(json.dumps(value))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['native','report'])
    action=parser.parse_args().action
    submitted=json.loads(SUBMISSION.read_bytes())
    old=common.ROOT/'reports/expert-revision-v2-native-20260930/r01/final/workflow-package.zip'
    native=(RUN/'antigen-tool-results.zip').read_bytes();html=(RUN/'antigen-report.html').read_bytes()
    payload=dict(action=action,owner=submitted['owner'],job_id=submitted['job_id'],
      native_sha256=sha(native),native_size_bytes=len(native),package_sha256=sha(old.read_bytes()),
      html_sha256=sha(html),html_size_bytes=len(html),
      snapshot_sha256=sha(native_encode(json.loads((RUN/'tool-results.json').read_bytes()))))
    bootstrap="import io,json,sys;p=json.load(sys.stdin);sys.stdin=io.StringIO(json.dumps(p['payload']));exec(p['code'])"
    done=subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',bootstrap],
      input=encode(dict(code=REMOTE,payload=payload)),capture_output=True,timeout=330)
    if done.returncode:raise RuntimeError('Report verification failed: '+done.stderr.decode(errors='replace')[-2500:])
    value=json.loads(done.stdout)
    with (OUT/('deployed-'+action+'-check.json')).open('xb') as stream:stream.write(encode(value)+b'\n')
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':main()
