"""Read an existing owner's results with staged report code; never submit a job."""
import base64
import io
import json
import subprocess
import zipfile
from pathlib import Path

import prepare_m1_p1_deploy as common
from version_bundle import build, encode, sha

OUT = common.ROOT/'reports/himat-report-repair-20261008'
JOB = 't01p1r-job-791a5fcf9e60409a96e6c0b4c64ccda6'
REMOTE = r'''
import base64,io,json,sqlite3,sys,tempfile,zipfile
from pathlib import Path
p=json.load(sys.stdin)
with tempfile.TemporaryDirectory(prefix='report-readonly-',dir='/var/lib/t01') as tmp:
 root=Path(tmp)
 for name in ('archive','manifest','installer'):(root/name).write_bytes(base64.b64decode(p[name]))
 ns={'__name__':'staged_installer'}
 exec(compile((root/'installer').read_bytes(),'staged_installer','exec'),ns)
 ns['install'](root/'archive',root/'manifest',root/'src',p['source_sha256'])
 for name in ('工作流设计','discovery','var','scripts'):
  if (Path('/app')/name).exists():(root/name).symlink_to(Path('/app')/name,target_is_directory=True)
 sys.path.insert(0,str(root/'src'))
 from t01_phase1_real.linux_service import install_platform_modules
 install_platform_modules()
 from t01_phase1_real.development import Runtime
 from t01_phase1_real.service_api.app import Principal
 from t01_phase1_real.service_api.native_results import collect
 from t01_phase1_real.service_api.user_report import from_workflow_package
 from t01_phase1_real.common import encode,sha
 owner=Principal('himat-t01-test',frozenset({'query','download'}),'not-a-credential')
 rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
 def count():
  with sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True) as db:
   return db.execute('SELECT count(*) FROM jobs').fetchone()[0]
 before=count();job=rt.get(p['job_id']);before_job=sha(encode(job));before_request=sha(rt._request_bytes(job))
 assert job['state']=='succeeded'
 result=rt.result(p['job_id'])
 ref=next(r['artifact'] for r in result['raw_artifacts'] if r['path']=='output/package.zip')
 assert ref in job['artifacts'] and ref['job_id']==job['job_id'] and ref['run_id']==job['run_id']
 package=rt.artifact_bytes(job['job_id'],ref['artifact_id'])
 assert sha(package)==ref['sha256']==p['package_sha256'] and len(package)==ref['size_bytes']
 snapshot,archive=collect(rt,job['job_id'],dict(content=package,sha256=sha(package),job_id=job['job_id']),include_raw=True)
 html=from_workflow_package(package,native_results=snapshot)
 assert all(x in html.decode() for x in ('118636','>776<','27.896500','mature_chain','4 个 MHC 批次'))
 assert count()==before and sha(encode(rt.get(job['job_id'])))==before_job and sha(rt._request_bytes(job))==before_request
 files={'antigen-report.html':html,'antigen-tool-results.zip':archive,'tool-results.json':encode(snapshot)}
 receipt=dict(status='PASS',job_id=job['job_id'],run_id=job['run_id'],source_sha256=p['source_sha256'],
  job_count=before,new_jobs=0,new_model_calls=0,original_results_modified=False,package_sha256=sha(package),
  files={name:dict(sha256=sha(raw),size_bytes=len(raw)) for name,raw in files.items()})
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for name,raw in files.items():z.writestr(name,raw)
 print(json.dumps(dict(receipt=receipt,bundle=base64.b64encode(out.getvalue()).decode(),bundle_sha256=sha(out.getvalue()))))
'''


def main():
    archive,manifest=build(common.ROOT/'src')
    payload={k:base64.b64encode(v).decode() for k,v in dict(archive=archive,manifest=encode(manifest),
        installer=Path(__file__).with_name('version_bundle.py').read_bytes()).items()}
    payload.update(source_sha256=sha(encode(manifest)),job_id=JOB,
        package_sha256=sha((common.ROOT/'reports/himat-report-audit-20261008/original-workflow-package.zip').read_bytes()))
    # Keep large evidence transport in the subprocess, not the conversation.
    done=subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',REMOTE],
        input=encode(payload),capture_output=True,timeout=330)
    if done.returncode:raise RuntimeError(done.stderr.decode(errors='replace')[-2500:])
    value=json.loads(done.stdout.splitlines()[-1]);bundle=base64.b64decode(value['bundle'])
    assert sha(bundle)==value['bundle_sha256']
    run=OUT/'r01';run.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(bundle)) as z:
        assert set(z.namelist())==set(value['receipt']['files'])
        for name,info in value['receipt']['files'].items():
            raw=z.read(name);assert len(raw)==info['size_bytes'] and sha(raw)==info['sha256']
            (run/name).write_bytes(raw)
    with zipfile.ZipFile(run/'antigen-tool-results.zip') as z:
        manifest=json.loads(z.read('manifest.json'))
        for row in manifest['files']:
            raw=z.read(row['path']);assert len(raw)==row['size_bytes'] and sha(raw)==row['sha256']
    value['receipt']['verified_manifest_files']=len(manifest['files'])
    (OUT/'read-only-rebuild.json').write_bytes(encode(value['receipt']))
    print(json.dumps(value['receipt']))


if __name__=='__main__':main()
