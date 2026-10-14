"""Verify real HiMat query/download, entry configuration and immutable old run."""
import json
import subprocess

import prepare_m1_p1_deploy as common
from version_bundle import encode, sha

OUT=common.ROOT/'reports/himat-report-repair-20261008'
REMOTE=r'''
import io,json,sqlite3,sys,time,urllib.error,urllib.parse,urllib.request,zipfile
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import encode,decode,sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow.policy import request as validate,order
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.service_api.client_guide import CHECK_TOOL
from t01_phase1_real.service_api.himat import HiMatIntegration
p=json.load(sys.stdin)
credentials=json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials']
credential=next(r for r in credentials if r['principal']=='himat-t01-test')
owner=Principal(credential['principal'],frozenset(credential['scopes']),'not-a-credential')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
def count():
 with sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True) as db:
  return db.execute('SELECT count(*) FROM jobs').fetchone()[0]
def request(path,token=None,data=None):
 headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 started=time.monotonic()
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18083'+path,headers=headers,data=data),timeout=240) as response:
  raw=response.read();assert response.status==200
  return raw,round(time.monotonic()-started,3)
before=count();job=rt.get(p['job_id']);job_hash=sha(encode(job));original=rt._request_bytes(job);request_hash=sha(original)
message=dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name=CHECK_TOOL,arguments=dict(job_id=p['job_id'])))
raw,seconds=request('/mcp',credential['token'],encode(message))
response=decode(raw);assert 'error' not in response and not response['result'].get('isError')
card=response['result']['data']
assert len(card['attachments'])==4 and card['primaryAttachmentId']=='attachment_user_report'
assert 'DESIGN_NOT_EXECUTED' in card['summaryText'] and 'NO_DESIGNABLE_POSITIONS' in card['summaryText']
downloaded=[]
for attachment in card['attachments']:
 aid=attachment['attachmentId']
 if aid not in ('attachment_user_report','attachment_native_results','attachment_zip'):continue
 url=urllib.parse.urlsplit(attachment['fileUrl']);raw,elapsed=request(url.path+'?'+url.query)
 name={'attachment_user_report':'antigen-report.html','attachment_native_results':'antigen-tool-results.zip',
       'attachment_zip':'original-workflow-package.zip'}[aid]
 assert sha(raw)==p['files'][name]['sha256'] and len(raw)==p['files'][name]['size_bytes']
 if aid=='attachment_native_results':
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   manifest=decode(z.read('manifest.json'))
   assert len(manifest['files'])==331
   for item in manifest['files']:
    content=z.read(item['path']);assert len(content)==item['size_bytes'] and sha(content)==item['sha256']
 downloaded.append(dict(name=name,sha256=sha(raw),size_bytes=len(raw),elapsed_seconds=elapsed))
endpoint='/v1/workflows/'+p['job_id']+'/native-results'
foreign=next(r for r in credentials if r['principal']!=credential['principal'] and 'download' in r['scopes'])
for token,expected in ((None,401),(foreign['token'],403)):
 try:request(endpoint,token)
 except urllib.error.HTTPError as exc:assert exc.code==expected
 else:raise AssertionError('Private native export was accessible without its owner')
# Inspect installed submission construction using a capture-only sink. Never Service.submit.
captured=[]
class Capture:
 def submit(self,principal,body):
  captured.append(body)
  return dict(job_id='captured-only',state='queued')
adapter=HiMatIntegration(Capture(),'https://example.invalid',b'capture-only-test-key-32-bytes-long')
body=decode(original)
first=adapter.submit_sequence(owner,body['protein_sequence'],body['host_species'])
adapter.submit_sequence(owner,body['protein_sequence'],body['host_species'])
cfg=captured[0]['request']['revision_config'];accepted=validate(encode(captured[0]['request']))
assert cfg['rule_version']=='expert-revision-20260929-v2' and 'revision_design' in order(accepted)
assert captured[0]==captured[1] and cfg['parameter_status']=='SUGGESTED_UNCALIBRATED'
assert 'revision_config' not in body and count()==before
assert sha(encode(rt.get(p['job_id'])))==job_hash and sha(rt._request_bytes(job))==request_hash
print(json.dumps(dict(status='PASS',job_id=p['job_id'],job_count=before,new_jobs=0,new_model_calls=0,
 original_request_and_job_unchanged=True,card_query_seconds=seconds,attachment_count=4,downloads=downloaded,
 unauthenticated_rejected=True,foreign_owner_rejected=True,new_entry_rule=cfg['rule_version'],
 new_entry_config_id=cfg['calculation_config_id'],new_entry_only_captured_not_submitted=True,
 scientific_gate='CLOSED',production_status='NOT_DEPLOYED')))
'''


def main():
    receipt=json.loads((OUT/'read-only-rebuild.json').read_bytes())
    package=(common.ROOT/'reports/himat-report-audit-20261008/original-workflow-package.zip').read_bytes()
    payload=dict(job_id=receipt['job_id'],files={**receipt['files'],
        'original-workflow-package.zip':dict(sha256=sha(package),size_bytes=len(package))})
    done=subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',REMOTE],
        input=encode(payload),capture_output=True,timeout=720)
    if done.returncode:raise RuntimeError(done.stderr.decode(errors='replace')[-2500:])
    result=json.loads(done.stdout)
    (OUT/'deployed-himat-check.json').write_bytes(encode(result))
    print(json.dumps(result))


if __name__=='__main__':main()
