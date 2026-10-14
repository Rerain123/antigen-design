"""Read-only paired N10 timing and science comparison for the authorized retest."""
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode
from run_pcv2_n10_continuation import OUT,SOURCE

REMOTE=r'''
import json,sys,time
from datetime import datetime
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.common import encode,sha
p=json.load(sys.stdin)
rt=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset(['query']),'not-a-credential').runtime_scope)
old=rt.execution(p['source'])['nodes'];new=rt.execution(p['job_id'])['nodes']
def duration(j):
 return (datetime.fromisoformat(j['finished_at'].replace('Z','+00:00'))-datetime.fromisoformat(j['started_at'].replace('Z','+00:00'))).total_seconds()
def scientific(value):
 # Only execution identity envelopes are excluded. All measurements, input,
 # thresholds, quality, warnings and missing values remain in the comparison.
 if isinstance(value,dict):return {k:scientific(v) for k,v in value.items() if k!='binding'}
 if isinstance(value,list):return [scientific(v) for v in value]
 return value
def differences(a,b,path=''):
 if type(a)!=type(b):return [path]
 if isinstance(a,dict):
  out=[path+'/'+k for k in a.keys()^b.keys()]
  for k in a.keys()&b.keys():out+=differences(a[k],b[k],path+'/'+k)
  return out
 if isinstance(a,list):
  if len(a)!=len(b):return [path+'/length']
  return [d for i,(x,y) in enumerate(zip(a,b)) for d in differences(x,y,path+'/'+str(i))]
 return [] if a==b else [path]
def measurements(value):
 if isinstance(value,dict):
  # Execution identity/log/SVG metadata are not scores. Keep their differences
  # separately above; preserve success/failure flags in the numeric projection.
  return {k:({f:v[f] for f in ('error_code','exit_code','stopped_confirmed','status') if f in v}
             if k=='execution' and isinstance(v,dict) else measurements(v)) for k,v in value.items()}
 if isinstance(value,list):return [measurements(v) for v in value]
 return value
rows=[]
for n in range(1,5):
 for kind in ('structure','developability'):
  name=f'c_s{n}_{kind}'
  if name not in new or not new[name].get('job_id'):continue
  a=rt.get(old[name]['job_id']);b=rt.get(new[name]['job_id'])
  if b['state']!='succeeded':continue
  av=rt.result(a['job_id']);bv=rt.result(b['job_id'])
  for j in (a,b):
   for ref in j['artifacts']:assert sha(rt.artifact_bytes(j['job_id'],ref['artifact_id']))==ref['sha256']
  keys=('analysis',) if kind=='structure' else ('steps','developability','warnings','status','null_reason')
  left=scientific({k:av[k] for k in keys});right=scientific({k:bv[k] for k in keys})
  diff=differences(left,right)
  ml,mr=measurements(left),measurements(right)
  rows.append(dict(node=name,old_job_id=a['job_id'],new_job_id=b['job_id'],
   before_seconds=duration(a),after_seconds=duration(b),speedup=duration(a)/duration(b),
   scientific_equal=not diff,different_paths=diff,old_scientific_sha256=sha(encode(left)),new_scientific_sha256=sha(encode(right)),
   measurements_equal=ml==mr,measurement_differences=differences(ml,mr),old_measurements_sha256=sha(encode(ml)),new_measurements_sha256=sha(encode(mr))))
print(json.dumps(dict(source_job_id=p['source'],job_id=p['job_id'],comparisons=rows,
 excluded_fields=['recursive binding: per-execution identifiers and implementation profile'],
 all_measurements_equal=bool(rows) and all(r['measurements_equal'] for r in rows))))
'''

if __name__=='__main__':
    submitted=json.loads((OUT/'continuation-submission.json').read_bytes())
    value=common.remote(REMOTE,dict(source=SOURCE,job_id=submitted['job_id']))
    (OUT/'paired-comparison.json').write_bytes(encode(value))
    print(json.dumps(value,ensure_ascii=False))
