"""Read-only N13 source replay with r16's real WT/variant observations."""
import json

import prepare_m1_p1_deploy as common

BASE=common.ROOT/'discovery/t01-phase1-real/m1-p4-20260922'
OUT=BASE/'route-n13-source-replay-r01.json'
REMOTE="""
import json,sys
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import encode,decode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow.service import source
from t01_phase1_real.development.variant_report.m1 import verified_preselection
from t01_phase1_real.development.epitope_protection import policy,source as n13_source,compute
task=json.load(sys.stdin)
rt=Runtime('/var/lib/t01/runtime',scope='svc-'+task['owner'][:24],blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
job=rt.get(task['job_id']);rows=rt.execution(job['job_id'])['nodes']
audit=source(rt,rows['design_audit']);old=rt.get(rows['protection']['job_id'])
request=decode(rt._request_bytes(old))
with rt._db() as db:
    fact=verified_preselection(rt,db,request['protein_sequence'],request['user_sequence_id'],audit)
    request['upstream']={'design_audit':audit};request['preselection']=fact
    policy.request(encode(request))
    files,values,receipts=n13_source.sources(rt,db,request)
    observed=compute.evaluate(request,files)
prior=rt.result(old['job_id'])['protection']
assert {r['variant_id']:r['observation'] for r in observed['records']}=={r['variant_id']:r['observation'] for r in prior['records']}
assert not any('foldx' in name.lower() for name in files)
print(json.dumps(dict(job_id=job['job_id'],run_id=job['run_id'],sample_numbers=fact['sample_numbers'],
    pair_count=len(observed['records']),same_observations=True,source_keys=list(request['upstream']),
    foldx_consumed=False)))
"""


def main():
    batch=json.loads((BASE/'r16/batch.json').read_bytes())
    result=common.remote(REMOTE,dict(owner=batch['owner'],job_id=batch['job_id']))
    assert result['job_id']==batch['job_id'] and result['sample_numbers']==[22,4,16]
    assert result['pair_count']==3 and result['same_observations'] and result['source_keys']==['design_audit']
    assert result['foldx_consumed'] is False
    evidence=dict(status='N13_REAL_PAIRED_SOURCE_REPLAY_PASS',historical_run_is_control_only=True,
        new_run_required_for_route_acceptance=True,**result)
    assert not OUT.exists()
    OUT.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(evidence['status'])


if __name__=='__main__':main()
