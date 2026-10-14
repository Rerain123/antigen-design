"""Read-only replay of corrected N12 preselection against preserved r16 producers."""
import json

import prepare_m1_p1_deploy as common
from t01_phase1_real.development.variant_report.m1 import selection

BASE=common.ROOT/'discovery/t01-phase1-real/m1-p4-20260922'
OUT=BASE/'route-preselection-replay-r01.json'
REMOTE="""
import json,sys
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow.service import source
from t01_phase1_real.development.variant_report.m1 import verified_preselection
task=json.load(sys.stdin)
rt=Runtime('/var/lib/t01/runtime',scope='svc-'+task['owner'][:24],blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
job=rt.get(task['job_id']);rows=rt.execution(job['job_id'])['nodes']
audit=source(rt,rows['design_audit'])
with rt._db() as db:
    fact=verified_preselection(rt,db,task['protein_sequence'],task['user_sequence_id'],audit)
print(json.dumps(dict(job_id=job['job_id'],run_id=job['run_id'],fact=fact)))
"""


def main():
    old=BASE/'r16'
    batch=json.loads((old/'batch.json').read_bytes())
    result=common.remote(REMOTE,dict(owner=batch['owner'],job_id=batch['job_id'],
        protein_sequence=batch['request']['protein_sequence'],user_sequence_id=batch['request']['user_sequence_id']))
    recorded=json.loads((old/'selection_report.json').read_bytes())['result']['report']['records']
    expected=selection(recorded)
    fact=result['fact']
    assert result['job_id']==batch['job_id'] and fact['sample_numbers']==expected
    assert fact['total_records']==len(recorded)==24
    assert [r['id'] for r in fact['selected']]==['sample-'+str(n) for n in expected]
    evidence=dict(status='N12_PRESELECTION_REAL_SOURCE_REPLAY_PASS',source_run_id=result['run_id'],
        historical_run_is_control_only=True,selected_sample_numbers=expected,
        total_records=fact['total_records'],records_sha256=fact['records_sha256'],
        new_run_required_for_route_acceptance=True)
    assert not OUT.exists()
    OUT.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(evidence['status'],expected)


if __name__=='__main__':main()
