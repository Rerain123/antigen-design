"""Read-only current-source replay in a temporary bundle; no dispatch or submission."""
import base64
import json
import subprocess
from pathlib import Path
import prepare_m1_p1_deploy as common
from version_bundle import build,encode,sha
from inspect_pcv2_n14_capacity import OUT,SOURCE

REMOTE=r'''
import base64,json,sys,tempfile,time
from pathlib import Path
p=json.load(sys.stdin)
with tempfile.TemporaryDirectory(prefix='n14-checkpoint-',dir='/var/lib/t01') as tmp:
 root=Path(tmp)
 for name in ('archive','manifest','installer'):(root/name).write_bytes(base64.b64decode(p[name]))
 ns={'__name__':'bundle_installer'}
 exec(compile((root/'installer').read_bytes(),'bundle_installer','exec'),ns)
 ns['install'](root/'archive',root/'manifest',root/'src',p['sha256'])
 for name in ('工作流设计','var','scripts'):
  if (Path('/app')/name).exists():(root/name).symlink_to(Path('/app')/name,target_is_directory=True)
 # Integrity-sensitive archived scale references must be actual copied files,
 # never symlinked around the production no-links guard.
 scales=json.loads((root/'src/t01_phase1_real/development/design_backend/scales.json').read_bytes())
 for ref in scales['source_receipts'].values():
  target=root/ref['path'];target.parent.mkdir(parents=True,exist_ok=True)
  target.write_bytes((Path('/app')/ref['path']).read_bytes())
 sys.path.insert(0,str(root/'src'))
 from t01_phase1_real.linux_service import install_platform_modules
 install_platform_modules()
 from t01_phase1_real.development import Runtime
 from t01_phase1_real.service_api.app import Principal
 from t01_phase1_real.common import encode,decode,sha
 from t01_phase1_real.development.workflow import continuation,service
 rt=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset(['query']),'x').runtime_scope)
 source=rt.get(p['source']);body=decode(rt._request_bytes(source))
 for k,v in body['configuration'].items():setattr(rt,k,Path(v) if v else None)
 before=sha(encode(rt.execution(source['job_id'])));t=time.monotonic()
 j,b,ex,rows=continuation.prepare_stability(rt,p['source'])
 req,reason=service.request_for(rt,b,rows,'stability')
 assert reason is None and sha(encode(req))==p['request_sha256']
 assert before==sha(encode(rt.execution(source['job_id']))) and source==rt.get(source['job_id'])
 print('CHECKPOINT_RESULT='+json.dumps(dict(status='PASS',source_sha256=p['sha256'],seconds=time.monotonic()-t,
  request_sha256=sha(encode(req)),request_bytes=len(encode(req)),variants=len(req['variants']),
  reused_children={n:r['job_id'] for n,r in rows.items() if r.get('job_id')},
  old_checkpoint_unchanged=True,new_jobs_submitted=0)))
'''

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--projection',action='store_true');parser.add_argument('--parallel',action='store_true');args=parser.parse_args()
    diagnosis=json.loads((OUT/'diagnosis.json').read_bytes())
    if args.projection:
        OUT=common.ROOT/'reports/n14-projection-20260928'
        SOURCE='t01p1r-job-ae3efda979474d0ea4054053ae341afa'
    if args.parallel:
        OUT=common.ROOT/'reports/n14-performance-20260928'
        SOURCE='t01p1r-job-2c5c0ec9925e47409c3a4a3817446f71'
    OUT.mkdir(parents=True,exist_ok=True)
    archive,manifest=build(common.ROOT/'src')
    payload={k:base64.b64encode(v).decode() for k,v in dict(archive=archive,manifest=encode(manifest),
        installer=Path(__file__).with_name('version_bundle.py').read_bytes()).items()}
    payload.update(sha256=sha(encode(manifest)),source=SOURCE,
        request_sha256=diagnosis['request_sha256'])
    result=subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',REMOTE],
        input=json.dumps(payload).encode(),capture_output=True,timeout=900)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-3500:])
    (OUT/'checkpoint-replay.stdout.txt').write_bytes(result.stdout)
    lines=[line[len('CHECKPOINT_RESULT='):] for line in result.stdout.decode().splitlines() if line.startswith('CHECKPOINT_RESULT=')]
    assert len(lines)==1
    value=json.loads(lines[0]);(OUT/'checkpoint-replay.json').write_bytes(encode(value))
    print(json.dumps({k:v for k,v in value.items() if k!='reused_children'}))
