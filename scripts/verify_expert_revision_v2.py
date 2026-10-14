"""Verify the deployed v2 contract with synthetic inputs and no model calls."""
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode

REMOTE = r'''
import json,sqlite3
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development.workflow import revision_contract as c,revision_v2 as v,revision_budget as b
from t01_phase1_real.development.workflow.policy import order
def count():
 with sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True) as db:return db.execute('SELECT count(*) FROM jobs').fetchone()[0]
before=count();cfg=v.config('deployment-v2-contract-fixture');c.config(cfg)
assert v.enabled(cfg) and not v.enabled(c.suggested_config('deployment-v1-fixture'))
assert c.budget('A'*214,cfg,list(range(1,215)))['B']==14
assert c.budget('A'*999,cfg,list(range(1,1000)))['B']==69
assert 'revision_design' in order(dict(engineering_design='BACKEND_EVIDENCE_V1',revision_config=cfg))
assert v.esm(-.01,-.01)['check_status']=='PASS'
assert v.esm(-.009,-.009)['check_status']=='NOT_ASSESSED'
record=dict(sequence='A'*100,mutations=[{}]*6)
primary=dict(execution_status='SUCCEEDED',plddt=.4)
secondary=dict(execution_status='SUCCEEDED',plddt=.9)
assert v.supplier(record,dict(af3=primary,esmfold2=secondary))['check_status']=='FAIL'
assert v.supplier(record,dict(af3=dict(execution_status='ERROR'),esmfold2=secondary))['degraded'] is True
assert v.select([],20,foldx=True)['selected_candidate_ids']==[]
ledger=b.new(cfg)
for i in range(24):assert b.reserve(ledger,cfg,'call-'+str(i),'structure',[str(i)])
assert not b.reserve(ledger,cfg,'overflow','structure',['25'])
assert count()==before
print(json.dumps(dict(status='PASS',rule_version=v.RULE,shared_contract_version=c.VERSION,
 contract_fixture_only=True,models_executed=False,new_jobs=0,
 checks=['v2/v1 isolation','214/999 mutation budgets','revision controller routing','ESM strict .01 boundary',
 'valid primary FAIL never replaced','dual-route fallback','empty FoldX selection','structure task budget'])))
'''

if __name__ == '__main__':
    result = common.remote(REMOTE)
    path = common.ROOT / 'reports/expert-revision-v2-deploy-20260930/deployed-contract-check.json'
    with path.open('xb') as stream:
        stream.write(encode(result) + b'\n')
    print(json.dumps(result))
