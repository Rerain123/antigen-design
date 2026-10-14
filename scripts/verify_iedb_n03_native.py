"""Bounded real N03 checks only; never submit the design workflow."""
import argparse
import json
from pathlib import Path
import prepare_m1_p1_deploy as c

OUT=c.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/iedb-native-r01'
PRELUDE='''import json,sys,time
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.common import encode,decode,sha
rt=Runtime('/var/lib/t01/runtime',scope='iedb-n03-engineering-r01',blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
p=json.load(sys.stdin)
'''


def main():
    global OUT
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['start','status','audit'])
    ap.add_argument('--batch',choices=['r01','r02'],default='r01');args=ap.parse_args()
    OUT=OUT.parent/('iedb-native-'+args.batch)
    if args.action=='start':
        assert not OUT.exists();OUT.mkdir()
        cases=json.loads((OUT.parent/'iedb-native-cases-r01.json').read_bytes())
        cases['batch']=args.batch
        rows=c.remote(PRELUDE+'''
rows=[]
for case in p['cases']:
 body=dict(protein_sequence=case['sequence'],user_sequence_id='N03 engineering check '+case['case'],database_id='iedb-20260924-r01',database_manifest_sha256='96be17e60c108013d320558817037d081edbf8e3c0ed2f9facf83a2d818b6e12',thresholds=dict(identity_percent_min=70,query_coverage_percent_min=80),timeout_seconds=120)
 job=rt.submit_sequence(encode(body),'iedb-n03-'+p['batch']+'-'+case['case'],'t01.real.blast')
 job=rt.dispatch(job['job_id']);rows.append(dict(case=case['case'],job_id=job['job_id'],run_id=job['run_id'],state=job['state']))
print(json.dumps(rows))
''',cases)
        (OUT/'jobs.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');print(json.dumps(rows));return
    rows=json.loads((OUT/'jobs.json').read_bytes())
    if args.action=='status':
        print(json.dumps(c.remote(PRELUDE+'''
rows=[]
for r in p:
 job=rt.reconcile(r['job_id']);rows.append(dict(case=r['case'],job_id=r['job_id'],state=job['state'],error_code=job.get('error_code')))
print(json.dumps(rows))
''',rows),indent=2));return
    results=c.remote(PRELUDE+'''
results=[]
for row in p:
 job=rt.reconcile(row['job_id']);value=rt.result(job['job_id']);ex=rt.execution(job['job_id'])
 for ref in job['artifacts']:rt.artifact_bytes(job['job_id'],ref['artifact_id'])
 target=Path(ex['resident_target']);native=json.loads((target/'output/native/runtime.json').read_bytes())
 prior=value.get('iedb_prior') or {}
 results.append(dict(case=row['case'],job=job,result=value,execution=ex,native_runtime=native,
  summary=dict(case=row['case'],state=job['state'],error_code=job.get('error_code'),
    native_blast_seconds=native['commands']['blastp']['elapsed_seconds'],native_total_seconds=native['elapsed_seconds'],
    iedb_hit=prior.get('iedb_hit'),e3_regions=len(prior.get('epitope_regions',[])),e4_status=prior.get('e4_status'),
    warning_count=len(value['warnings']),artifact_count=len(job['artifacts']),
    stopped_confirmed=value['execution'].get('stopped_confirmed'),database_id=value['binding']['database_id'])))
print(json.dumps(results))
''',rows)
    for r in results:(OUT/(r['case']+'.json')).write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8')
    summaries=[r['summary'] for r in results]
    summary=dict(checks=summaries,all_succeeded=all(r['state']=='succeeded' for r in summaries),
        scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED',full_workflow_started=False)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
