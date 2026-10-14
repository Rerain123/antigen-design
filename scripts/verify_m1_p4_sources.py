"""Read-only rejection probes against current registered P4 task sources."""
import json
from pathlib import Path
import prepare_m1_p1_deploy as d

PROGRAM=r'''
import copy,json,sys
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import service
from t01_phase1_real.development.proteinmpnn.source import sources
from t01_phase1_real.common import decode,RuntimeFault
b=json.load(sys.stdin);rt=Runtime('/var/lib/t01/runtime',scope='svc-'+b['owner'][:24],blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
j=rt.get(b['job_id']);body=decode(rt._request_bytes(j));rows=rt.execution(j['job_id'])['nodes'];out={}
def reject(name,operation,expected):
 try:operation()
 except RuntimeFault as e:
  assert e.code==expected,(name,e.code);out[name]=dict(rejected=True,error_code=e.code)
 else:raise AssertionError(name+' accepted')
reject('wrong_run_same_sequence',lambda:service.verified(rt,body,'structure',rows['structure']['job_id'],'t01p1r-run-'+'f'*32,rows),'FORBIDDEN')
changed=copy.deepcopy(body);changed['protein_sequence']='A'+body['protein_sequence'][1:]
reject('wrong_wt_sequence',lambda:service.verified(rt,changed,'structure',rows['structure']['job_id'],j['run_id'],rows),'OUTPUT_INVALID')
reject('historical_result_in_new_parent',lambda:service.verified(rt,body,'structure',b['historical_structure_job'],j['run_id'],rows),'FORBIDDEN')
n11=decode(rt._request_bytes(rt.get(rows['design']['job_id'])));n11['structure_artifact']['sha256']='0'*64
with rt._db() as db:
 reject('forged_structure_hash',lambda:sources(rt,db,n11,expected_run_id=j['run_id']),'FORBIDDEN')
if rows.get('rep1_prediction',{}).get('job_id') and rows.get('rep2_prediction',{}).get('job_id'):
 reject('wrong_candidate_slot',lambda:service.verified(rt,body,'rep2_prediction',rows['rep1_prediction']['job_id'],j['run_id'],rows),'OUTPUT_INVALID')
print(json.dumps(dict(status='P4_CURRENT_SOURCE_REJECTIONS_PASS',job_id=j['job_id'],run_id=j['run_id'],checks=out,mutated_server_files=False)))
'''


def main():
    root=d.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/r02'
    b=json.loads((root/'batch.json').read_bytes())
    old=json.loads((d.ROOT/'discovery/t01-phase1-real/m1-p1-20260921/r01/structure.json').read_bytes())
    b['historical_structure_job']=old['job']['job_id']
    result=d.remote(PROGRAM,b);(root/'source-rejections.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'],len(result['checks']))


if __name__=='__main__':main()
