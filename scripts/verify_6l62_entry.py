"""Capture live HiMat submission intent without creating a workflow."""
import json
from pathlib import Path
import prepare_m1_p1_deploy as common

CODE=r'''
import json,sqlite3,hashlib
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.service_api import himat
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.development.workflow import policy
from t01_phase1_real.development.blast.policy import verify_database
from t01_phase1_real.common import encode
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
jid='t01p1r-job-c4081362c5294a8bac8f1d0fe26d96a1'
j=json.loads(db.execute('SELECT data FROM jobs WHERE id=?',(jid,)).fetchone()[0])
a=j['request_artifact'];p=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(a['artifact_id'],)).fetchone()[0]
raw=(Path('/var/lib/t01/runtime')/p).read_bytes();assert hashlib.sha256(raw).hexdigest()==a['sha256'];old=json.loads(raw)
captured=[]
class Capture:
 def submit(self,principal,body):
  captured.append(body);return dict(job_id='capture-only',state='queued')
owner=Principal('himat-t01-test',frozenset(['submit','query','download']),'capture-only')
adapter=himat.HiMatIntegration(Capture(),'https://example.invalid',b'x'*32)
for _ in range(2):adapter.submit_sequence(owner,old['protein_sequence'],old['host_species'])
new=captured[0];assert new==captured[1]
b=new['request']['analysis']['blast']
assert b['database_id']=='iedb-20261013-6l62-r01'
assert b['database_manifest_sha256']=='000695140d8fedf1cc897faba5356bf184928235a3417486448b3ec09c72992b'
assert policy.request(encode(new['request']))['prediction']['engine']=='af3'
assert new['request']['revision_config']==old['revision_config']
verify_database('/var/lib/t01/m1-p1-test-data/blast',b)
himat.TARGET_IEDB_DATABASE_ID=old['analysis']['blast']['database_id']
himat.TARGET_IEDB_MANIFEST_SHA256=old['analysis']['blast']['database_manifest_sha256']
adapter.submit_sequence(owner,old['protein_sequence'],old['host_species'])
assert new['idempotency_key']!=captured[2]['idempotency_key']
print(json.dumps(dict(status='PASS',database_id=b['database_id'],manifest_sha256=b['database_manifest_sha256'],wt_engine='af3',same_sequence_not_old_replay=True,repeated_new_request_stable=True,science_rules_unchanged=True,new_scientific_jobs=0,submission_capture_only=True)))
'''
if __name__=='__main__':
    value=common.remote(CODE)
    dest=common.ROOT/'reports/iedb-6l62-20261013/deployment/entry-verification.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value))
