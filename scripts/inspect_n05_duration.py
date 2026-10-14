"""Read existing stopped-run receipts only; never dispatch or reconcile a job."""
import json
import subprocess
from pathlib import Path
import prepare_m1_p1_deploy as common

REMOTE = r'''
import json,hashlib,statistics,sqlite3
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.common import decode
from t01_phase1_real.development.netmhc import policy
from t01_phase1_real.development.netmhc.pan import manifest,batches
rt=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset(['query']),'none').runtime_scope)
jid='t01p1r-job-ca205a3ec2c14cc29599abb3fe677714'
job=rt.get(jid);ex=rt.execution(jid);body=decode(rt._request_bytes(job))
assert job['state']=='cancelled' and ex['tree_stopped']
panel=manifest();plan=batches(body['protein_sequence'],panel)
rows=[]
def stamp(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
for i,child_id in enumerate(ex['batches']):
 child=rt.get(child_id);ce=rt.execution(child_id);b=decode(rt._request_bytes(child))
 row=dict(index=i,job_id=child_id,state=child['state'],started_at=child['started_at'],finished_at=child.get('finished_at'),
          allele_counts={k:len(b[k+'_alleles']) for k in ('mhc_i','mhc_ii')})
 if child['state']=='succeeded':
  target=Path(ce['resident_target']);path=target/'output/native/runtime.json';raw=path.read_bytes()
  expected=ce['resident_receipt']['outputs']['output/native/runtime.json']['sha256']
  assert hashlib.sha256(raw).hexdigest()==expected
  native=json.loads(raw)
  row.update(runtime_sha256=expected,job_wall_seconds=(stamp(child['finished_at'])-stamp(child['started_at'])).total_seconds(),
    native_elapsed_seconds=native['elapsed_seconds'],channel_seconds={k:v['elapsed_seconds'] for k,v in native['commands'].items()},
    channel_exit_codes={k:v['exit_code'] for k,v in native['commands'].items()},
    output_bytes=sum(v['size_bytes'] for v in ce['resident_receipt']['outputs'].values()),
    example_alleles={k:b[k+'_alleles'][:3] for k in ('mhc_i','mhc_ii')})
  if i==0:
   row['native_commands']=native['commands'];row['cpu_affinity']=native.get('cpu_affinity')
   row['executor_observation']=json.loads((target/'output/executor-observation.json').read_bytes())
 rows.append(row)
ok=[r for r in rows if r['state']=='succeeded']
def stats(values):
 return dict(min=min(values),median=statistics.median(values),mean=statistics.mean(values),max=max(values),total=sum(values))
summary={k:stats([r[k] for r in ok]) for k in ('job_wall_seconds','native_elapsed_seconds','output_bytes')}
summary['channel_seconds']={k:stats([r['channel_seconds'][k] for r in ok]) for k in ('mhc_i','mhc_ii')}
summary['non_native_seconds']=stats([r['job_wall_seconds']-r['native_elapsed_seconds'] for r in ok])
summary['between_batch_seconds']=stats([(stamp(b['started_at'])-stamp(a['finished_at'])).total_seconds() for a,b in zip(ok,ok[1:])])
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
active=[r['job_id'] for (raw,) in db.execute('SELECT data FROM jobs') if (r:=json.loads(raw))['state'] not in ('succeeded','failed','cancelled','timed_out')]
files=['service_api/himat.py','development/netmhc/policy.py','development/netmhc/pan.py','development/netmhc/service.py','development/workflow/m1.py']
print(json.dumps(dict(observed_at=datetime.now(timezone.utc).isoformat(),job_id=jid,state=job['state'],active_jobs=active,
 sequence_length=len(body['protein_sequence']),host_species=body['host_species'],panel_mode=body['panel_mode'],timeout_seconds=body['timeout_seconds'],
 total_alleles={k:v['count'] for k,v in panel['channels'].items()},required_batches=len(plan),batch_states=dict(Counter(r['state'] for r in rows)),
 predicted_rows={k:panel['channels'][k]['count']*sum(max(0,len(body['protein_sequence'])-n+1) for n in lens) for k,lens in [('mhc_i',policy.MHC_I_LENGTHS),('mhc_ii',policy.MHC_II_LENGTHS)]},
 allele_prefixes={k:dict(Counter(a.split('-')[0] for a in v['alleles'])) for k,v in panel['channels'].items()},
 summary=summary,batches=rows,source_hashes={n:hashlib.sha256((Path('/app/src/t01_phase1_real')/n).read_bytes()).hexdigest() for n in files})))
'''

if __name__ == '__main__':
    value = common.remote(REMOTE)
    live = json.loads(subprocess.check_output(common.K + ['get','deployment','antigen-design','-o','json']))
    value['worker_resources'] = {c['name']: c.get('resources') for c in live['spec']['template']['spec']['containers'] if 'netmhc' in c['name']}
    value['generation'] = live['metadata']['generation']
    out = common.ROOT / 'reports/n05-duration-20260926'
    out.mkdir(exist_ok=True)
    (out/'inspection.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in value.items() if k not in ('batches','source_hashes','allele_prefixes')},ensure_ascii=False))
