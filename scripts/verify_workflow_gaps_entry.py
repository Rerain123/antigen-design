"""Installed HiMat request capture and read-only service checks; no submission."""
import json
from pathlib import Path
import prepare_m1_p1_deploy as common
from version_bundle import encode

OUT=common.ROOT/'reports/workflow-gaps-20261009'
REMOTE=r'''
import copy,hashlib,json,sqlite3,urllib.request
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import encode
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.development.workflow.policy import request as validate
from t01_phase1_real.development.workflow.revision_v2 import SELECTION
from t01_phase1_real.development.workflow.revision_sequence import observation
from t01_phase1_real.service_api.client_guide import WORKFLOW_USAGE

def inventory():
 with sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True) as db:
  return [row[0] for row in db.execute('SELECT data FROM jobs ORDER BY rowid')]
before=inventory()
cancelled=next(json.loads(row) for row in before if json.loads(row)['job_id']=='t01p1r-job-7d298b4c99c342cfbdf8709ebe2b0041')
assert cancelled['state']=='cancelled'
captured=[]
class Capture:
 def submit(self,principal,body):
  captured.append(copy.deepcopy(body))
  return dict(job_id='capture-only-not-submitted',state='queued')
owner=Principal('himat-t01-test',frozenset({'submit','query'}),'capture-only')
adapter=HiMatIntegration(Capture(),'https://example.invalid',b'capture-only-test-key-32-bytes-long')
seq='ACDEFGHIKLMNPQRSTVWY'
for _ in range(2):adapter.submit_sequence(owner,seq,'猪')
assert captured[0]==captured[1]
body=captured[0]['request'];accepted=validate(encode(body));cfg=accepted['revision_config']
assert cfg['policies']['l4']['selection_rule_id']==cfg['policies']['foldx_pool']['selection_rule_id']==SELECTION
assert SELECTION=='v2-stage-complete-dimension-group-dev-roundrobin-id-v2'
assert body['interaction_policy']=='PREAUTHORIZED_T4_CONTINUE_WITH_WARNING_V1'
assert '不再中途询问' in WORKFLOW_USAGE
assert cfg['structure_eval_max']==24 and cfg['l4_eval_max']==cfg['foldx_variant_max']==20 and cfg['foldx_number_of_runs']==5
assert cfg['formal_round_sizes']==[24,48,64]
row=dict(candidate_id='synthetic-deploy-check',content_hash=hashlib.sha256(seq.encode()).hexdigest(),
 sequence=seq,reference_id='synthetic-WT',calculation_config_id=cfg['calculation_config_id'],
 rule_version=cfg['rule_version'],generation_source={'engineering_fixture':True})
metric=observation(row)
assert metric['execution_status']=='SUCCEEDED' and metric['threshold_applied'] is False
# Exercise the live HTTP MCP discovery using an installed credential without logging it.
credentials=json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials']
credential=next(r for r in credentials if r['principal']=='himat-t01-test')
req=urllib.request.Request('http://127.0.0.1:18083/mcp',data=encode(dict(jsonrpc='2.0',id=1,method='tools/list')),
 headers={'Content-Type':'application/json','Authorization':'Bearer '+credential['token']})
with urllib.request.urlopen(req,timeout=20) as response:discovery=json.load(response)
assert 'error' not in discovery
tools=discovery['result']['tools'];assert len(tools)==3
assert any(t['name']=='workflow_submit_sequence' and '后台' in t['description'] for t in tools)
assert inventory()==before
print(json.dumps(dict(status='PASS',new_jobs=0,job_count=len(before),cancelled_job_preserved=True,
 complete_job_inventory_unchanged=True,entry_captured_only=True,selection_rule_id=SELECTION,
 calculation_config_id=cfg['calculation_config_id'],interaction_policy=body['interaction_policy'],
 structure_budget=cfg['structure_eval_max'],l4_budget=cfg['l4_eval_max'],foldx_budget=cfg['foldx_variant_max'],
 foldx_internal_runs=cfg['foldx_number_of_runs'],prestructure_metrics=metric['expressibility'],
 mcp_tools=[t['name'] for t in tools],models_executed=False)))
'''

if __name__=='__main__':
    value=common.remote(REMOTE)
    (OUT/'deployed-entry-verification.json').write_bytes(encode(value))
    print(json.dumps(value,ensure_ascii=False))
