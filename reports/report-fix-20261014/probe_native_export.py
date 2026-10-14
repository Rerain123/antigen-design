"""Read-only size/memory check of the new exporter against existing registered files."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'scripts'))
import prepare_m1_p1_deploy as common

REMOTE = r'''
import hashlib,io,json,resource,sqlite3,sys,time,zipfile
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
p=json.load(sys.stdin);start=time.monotonic()
jid='t01p1r-job-d6498f2fecdf4632b274c3bc6ebd165e'
with sqlite3.connect('file:/var/lib/t01/runtime/service.sqlite3?mode=ro',uri=True) as db:
 owner=db.execute('SELECT principal FROM workflows WHERE job_id=?',(jid,)).fetchone()[0]
rt=Runtime('/var/lib/t01/runtime',scope=Principal(owner,frozenset({'query','download'}),'export-audit').runtime_scope)
job=rt.get(jid);before=json.dumps(job,sort_keys=True)
ref=next(a for a in job['artifacts'] if a['sha256']==p['package_sha256'])
package=rt.artifact_bytes(jid,ref['artifact_id'])
report=dict(job_id=jid,content=package,sha256=p['package_sha256'])
assert hashlib.sha256(p['source'].encode()).hexdigest()==p['source_sha256']
namespace=dict(__name__='t01_phase1_real.service_api.native_results_probe',__package__='t01_phase1_real.service_api')
exec(compile(p['source'],'export-probe','exec'),namespace)
snapshot,archive=namespace['collect'](rt,jid,report,include_raw=True)
with zipfile.ZipFile(io.BytesIO(archive)) as z:
 manifest=json.loads(z.read('manifest.json'))
 for entry in manifest['files']:
  raw=z.read(entry['path'])
  assert len(raw)==entry['size_bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
 assert z.read('original-workflow-package.zip')==package
 total=sum(i.file_size for i in z.infolist());members=len(z.infolist())
assert json.dumps(rt.get(jid),sort_keys=True)==before
print(json.dumps(dict(status='PASS',source_sha256=p['source_sha256'],expanded_bytes=total,
 compressed_bytes=len(archive),archive_sha256=hashlib.sha256(archive).hexdigest(),members=members,
 maximum_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
 manifest_hashes_verified=True,original_package_unchanged=True,new_scientific_jobs=0,
 elapsed_seconds=round(time.monotonic()-start,3))))
'''

source = (common.ROOT / 'src/t01_phase1_real/service_api/native_results.py').read_bytes().decode()
payload = dict(source=source, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
               package_sha256=json.loads((HERE/'implementation.json').read_bytes())['source_packages']['new']['sha256'])
process = subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',REMOTE],
                         input=json.dumps(payload).encode(),capture_output=True,timeout=600)
if process.returncode: raise RuntimeError(process.stderr.decode(errors='replace')[-1800:])
value=json.loads(process.stdout)
(HERE/'export-probe.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
print(json.dumps(value))
