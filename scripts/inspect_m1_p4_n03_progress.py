"""Read only the active N03 execution phases for current P4 batches."""
import argparse
import json

import prepare_m1_p1_deploy as deploy


BASE = deploy.ROOT / 'discovery/t01-phase1-real/m1-p4-20260922'
CODE = '''import json,sys
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from pathlib import Path
tasks=json.load(sys.stdin)
rows=[]
for task in tasks:
    rt=Runtime('/var/lib/t01/runtime',scope='svc-'+task['owner'][:24],
        blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
    parent=rt.workflow(task['job_id'])
    child=parent['nodes']['blast']
    if child.get('job_id'):
        job=rt.get(child['job_id'])
        execution=rt.execution(child['job_id'])
        target=Path(execution['resident_target']) if execution.get('resident_target') else None
        receipt=target/'execution.json' if target else None
        native=target/'output/native' if target else None
        state=json.loads(receipt.read_bytes()) if receipt and receipt.is_file() else None
        rows.append(dict(batch=task['batch'],parent_job_id=parent['job']['job_id'],
            blast_job_id=job['job_id'],parent_state=parent['job']['state'],
            blast_state=job['state'],blast_started_at=job.get('started_at'),
            blast_updated_at=job.get('updated_at'),phase=execution.get('phase'),
            database_verified=bool(execution.get('database_receipt')),
            resident_target_committed=bool(execution.get('resident_target')),
            resident_config_sha256=execution.get('resident_config_sha256'),
            resident_state=state.get('state') if state else None,
            cancel_marker=bool(target and (target/'cancel').is_file()),
            native_runtime_started=bool(native and (native/'runtime_started.json').is_file()),
            native_runtime_finished=bool(native and (native/'runtime.json').is_file()),
            error_code=job.get('error_code')))
print(json.dumps(rows))
'''


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--batch',action='append',required=True)
    args=ap.parse_args()
    tasks=[]
    for name in args.batch:
        batch=json.loads((BASE/name/'batch.json').read_bytes())
        tasks.append(dict(batch=name,owner=batch['owner'],job_id=batch['job_id']))
    for row in deploy.remote(CODE,tasks):
        print(json.dumps(row,sort_keys=True))


if __name__=='__main__':
    main()
