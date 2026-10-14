"""Compact read-only observations of the active v2 continuation and native files."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode

OUT=run.common.ROOT/'reports/expert-revision-v2-resume-20260930'
REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
from t01_phase1_real.common import now
from datetime import datetime
job=rt.get(p['job_id']);ex=rt.execution(p['job_id']);children={}
for name,row in ex.get('nodes',{}).items():
 if not row.get('job_id') or name in p['reused']:continue
 child=rt.get(row['job_id']);cx=rt.execution(child['job_id']);target=cx.get('resident_target')
 files=[];tail=[]
 if target:
  root=Path(target)
  files=[dict(path=f.relative_to(root).as_posix(),bytes=f.stat().st_size,modified=f.stat().st_mtime)
   for f in sorted(root.rglob('*')) if f.is_file() and not f.name.endswith('.lock')]
  log=root/'output/native/raw/inference.log'
  if log.is_file():
   with log.open('rb') as stream:
    stream.seek(-min(log.stat().st_size,4096),2)
    tail=stream.read().decode('utf8',errors='replace').splitlines()[-10:]
 batches={}
 for child_id in cx.get('batches',[]):
  state=rt.get(child_id)['state'];batches[state]=batches.get(state,0)+1
 children[name]=dict(job_id=child['job_id'],state=child['state'],error_code=child.get('error_code'),
  started_at=child.get('started_at'),finished_at=child.get('finished_at'),
  execution={k:cx.get(k) for k in ('phase','tree_stopped','resident_target','resident_diagnostic','backend')},
  observed_files=files,progress_log_tail=tail,batch_states=batches)
print(json.dumps(dict(observed_at=now(),job_id=job['job_id'],run_id=job['run_id'],state=job['state'],
 phase=ex.get('phase'),dispatcher=ex.get('dispatcher'),fatal_error=ex.get('fatal_error'),
 fatal_detail=ex.get('fatal_detail'),pending_confirmation=ex.get('pending_confirmation'),
 original_started_at=ex.get('started_at'),children=children,
 node_states={n:r['state'] for n,r in ex.get('nodes',{}).items()},
 native_models_called_by_observation=False)))
'''

if __name__=='__main__':
    submitted=run.active_submission()
    reused=submitted.get('continuation',{}).get('reused_children',{})
    value=run.common.remote(REMOTE,dict(job_id=submitted['job_id'],owner=submitted['owner'],reused=list(reused)))
    path=OUT/'runtime-observation.json'
    prior=json.loads(path.read_bytes()) if path.exists() else {}
    path.write_bytes(encode(value)+b'\n')
    summary={k:v for k,v in value.items() if k not in ('children','node_states')}
    summary['completed_child_count']=sum(c['state']=='succeeded' for c in value['children'].values())
    summary['children']={}
    for name,child in value['children'].items():
        if child['state'] in ('succeeded','failed','cancelled','timed_out') and child['state']==prior.get('children',{}).get(name,{}).get('state'):continue
        shown={k:v for k,v in child.items() if k!='observed_files'}
        shown.update(progress_log_tail=child['progress_log_tail'][-4:],observed_file_count=len(child['observed_files']))
        summary['children'][name]=shown
    print(json.dumps(summary,ensure_ascii=False))
