"""Read-only receipt timing for the continued original HiMat workflow."""
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode

REMOTE = r'''
import datetime,json
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
rt=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset({'query'}),'x').runtime_scope)
jid='t01p1r-job-c5c86fb69d434248b18127febd10ec38'
parent=rt.get(jid); rows=[]
for child_id in rt.execution(jid).get('batches',[]):
 job=rt.get(child_id);ex=rt.execution(child_id)
 row=dict(job_id=child_id,state=job['state'],started_at=job.get('started_at'),collected_at=job.get('finished_at'))
 target=ex.get('resident_target')
 path=Path(target)/'execution.json' if target else None
 if path and path.exists():
  receipt=json.loads(path.read_bytes());row['native_state']=receipt['state']
  if receipt.get('stopped_confirmed'):
   written=datetime.datetime.fromtimestamp(path.stat().st_mtime,datetime.timezone.utc)
   row['receipt_written_at']=written.isoformat()
   if row['collected_at']:
    row['collection_lag_seconds']=round((datetime.datetime.fromisoformat(row['collected_at'].replace('Z','+00:00'))-written).total_seconds(),6)
 rows.append(row)
print(json.dumps(dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 parent_job_id=jid,run_id=parent['run_id'],parent_state=parent['state'],batches=rows,new_submission=False)))
'''

if __name__ == '__main__':
    value=common.remote(REMOTE)
    (common.ROOT/'reports/controller-recovery-20261008/mhc-collection-after.json').write_bytes(encode(value))
    print(json.dumps(value,ensure_ascii=False))
