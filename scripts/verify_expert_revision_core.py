"""Deployment checks using synthetic contract values only; never call a model."""
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode

REMOTE='''import json,sqlite3
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development.workflow import revision_contract as c,revision_sampling as s,revision_budget as b,revision_evaluation as e,revision_schema as schema
from t01_phase1_real.development.workflow.policy import order
def count():
 with sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True) as db:return db.execute('SELECT count(*) FROM jobs').fetchone()[0]
before=count();cfg=c.suggested_config('deployment-contract-fixture')
assert c.budget('A'*214,cfg,list(range(1,215)))['B']==14
assert c.budget('A'*999,cfg,list(range(1,1000)))['B']==69
assert 'revision_design' in order(dict(engineering_design='BACKEND_EVIDENCE_V1',revision_config=cfg))
assert 'revision_design' not in order(dict(engineering_design='BACKEND_EVIDENCE_V1'))
schema.validate(c.check('NOT_ASSESSED'),kind='check')
pool=e.foldx_pool([],None,20,mode='variant_score',task_id='deployment-contract-fixture')
assert pool['execution_status']=='NOT_RUN' and pool['results']==[]
ledger=b.new(cfg)
for i in range(24):assert b.reserve(ledger,cfg,'call-'+str(i),'structure',[str(i)])
assert not b.reserve(ledger,cfg,'overflow','structure',['25'])
assert b.reserve(ledger,cfg,'second-engine','structure',['0'])
assert b.summary(ledger,cfg)['structure']['unique_objects']==24
assert count()==before
print(json.dumps(dict(status='PASS',shared_contract_version=c.VERSION,contract_fixture_only=True,
 models_executed=False,new_jobs=0,checks=['214/999 mutation budget','opt-in isolation','four-state schema','empty FoldX','cross-engine task budget'])))
'''

if __name__=='__main__':
    result=common.remote(REMOTE)
    out=common.ROOT/'reports/expert-revision-core-20260929/deployed-contract-check.json'
    out.write_bytes(encode(result)+b'\n');print(json.dumps(result))
