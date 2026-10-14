"""Read report identity and storage metadata without inspecting scientific content."""
import json
import subprocess

import prepare_m1_p1_deploy as common
from version_bundle import encode

JOB = 't01p1r-job-7ff412a6d443473bae22b1be05429206'
OUT = common.ROOT / 'reports/report-storage-20261011'
REMOTE = r'''
import hashlib,json,sqlite3,sys,urllib.request
from t01_phase1_real.service_api.app import Credentials
from t01_phase1_real.service_api.object_storage import RustFSPublisher,digest
p=json.load(sys.stdin)
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
job=json.loads(db.execute('SELECT data FROM jobs WHERE id=?',(p['job_id'],)).fetchone()[0])
acl=sqlite3.connect('file:/var/lib/t01/runtime/service.sqlite3?mode=ro',uri=True)
owner=acl.execute('SELECT principal FROM workflows WHERE job_id=?',(p['job_id'],)).fetchone()[0]
credentials=Credentials.from_environment()
entry=next(principal for _,principal in credentials._rows if principal.principal_id==owner)
token=next(token.decode() for token,principal in credentials._rows if principal.principal_id==owner)
storage=RustFSPublisher.from_environment()
objects=[]
if storage is not None:
 req=urllib.request.Request('http://127.0.0.1:18083/v1/workflows/'+p['job_id']+'/report',
     headers={'Authorization':'Bearer '+token})
 with urllib.request.urlopen(req,timeout=300) as response:
  package=response.read()
 refs=[(package,'report.zip')]
 # The registered Markdown is a separate original object, not an analysis of its text.
 import io,zipfile
 with zipfile.ZipFile(io.BytesIO(package)) as z:
  if 'workflow-report.md' in z.namelist():refs.append((z.read('workflow-report.md'),'report.md'))
 for raw,name in refs:
  key='/'.join([storage.prefix,entry.runtime_scope,p['job_id'],digest(raw),name])
  status,_,_=storage._request('HEAD',key)
  objects.append(dict(key=key,status=status,sha256=digest(raw),size_bytes=len(raw)))
print(json.dumps(dict(job_id=p['job_id'],state=job['state'],created_at=job['created_at'],
 finished_at=job['finished_at'],storage_enabled=storage is not None,
 owner_scope=entry.runtime_scope,bucket=storage.bucket if storage else None,
 old_publication_objects=objects,scientific_contents_reviewed=False)))
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(common.K + ['exec', '-i', 'deployment/antigen-design', '-c', 'service',
        '--', 'python', '-B', '-c', REMOTE], input=encode(dict(job_id=JOB)),
        capture_output=True, timeout=400)
    if done.returncode:
        raise RuntimeError('Report storage audit failed: ' + done.stderr.decode(errors='replace')[-1500:])
    result = json.loads(done.stdout)
    (OUT / 'diagnosis.json').write_bytes(encode(result))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
