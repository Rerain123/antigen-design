"""Read-only reconstruction of observed v2 candidate facts while the run continues."""
import json
import run_expert_revision_v2_native as run
from version_bundle import encode

OUT=run.common.ROOT/'reports/expert-revision-v2-resume-20260930'
REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
from t01_phase1_real.common import now
from t01_phase1_real.development.workflow import revision_controller as rc
argv=Path('/proc/1/cmdline').read_bytes().decode().split('\0')
for flag,name in [('--blast-database-root','blast_database_root'),('--homology-database-root','homology_database_root'),('--domains-database-root','domains_database_root')]:
 setattr(rt,name,Path(argv[argv.index(flag)+1]) if flag in argv else None)
job=rt.get(p['job_id']);body=decode(rt._request_bytes(job));data,reason=rc.inputs(rt,p['job_id'],body);assert reason is None
fact=rc.assemble(rt,p['job_id'],body,data)
rows=[]
for r in fact['formal_records']:
 if r['disposition']!='FORMAL_POOL':continue
 rows.append(dict(candidate_id=r['candidate_id'],sample_number=r['sample_number'],mutation_count=len(r['mutations']),
  s28=r['validation'],structure_observations=r.get('structure_observations'),protection=r.get('protection'),
  l4=r.get('l4'),foldx=r.get('foldx'),nonstability_score=r.get('nonstability_score'),
  acceptance_status=r['acceptance_status'],provisional_acceptance_status=r['provisional_acceptance_status']))
print(json.dumps(dict(observed_at=now(),status='PASS_READ_ONLY_LIVE_FACTS',job_id=job['job_id'],state=job['state'],
 records=rows,run_audit=fact['run_audit'],downstream_allocations=fact.get('downstream_allocations'),
 native_models_called_by_audit=False,scientific_gate='CLOSED')))
'''

if __name__=='__main__':
    submitted=run.active_submission()
    value=run.common.remote(REMOTE,dict(job_id=submitted['job_id'],owner=submitted['owner']))
    (OUT/'live-facts.json').write_bytes(encode(value)+b'\n')
    summary=[]
    for record in value['records']:
        summary.append(dict(sample=record['sample_number'],mutations=record['mutation_count'],
            s28=record['s28']['check_status'],structures={engine:{k:v.get(k) for k in ('check_status','execution_status','plddt')}
                for engine,v in (record['structure_observations'] or {}).items()},
            protection={k:(record['protection'] or {}).get(k) for k in ('check_status','reason_codes')},
            l4={k:(record['l4'] or {}).get(k) for k in ('check_status','reason_codes')},
            nonstability_score=record['nonstability_score']))
    print(json.dumps(dict(status=value['status'],records=summary),ensure_ascii=False))
