"""Read-only live HiMat entry verification; submission is captured, never sent."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import prepare_m1_p1_deploy as common
CODE=r'''import json,urllib.request
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import policy,revision_v2 as v,revision_structure as s
from t01_phase1_real.common import encode,decode
owner=Principal('himat-t01-test',frozenset(['submit','query','download']),'capture-only')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
job=rt.get('t01p1r-job-7ff412a6d443473bae22b1be05429206');old=decode(rt._request_bytes(job))
captured=[]
class Capture:
 def submit(self,principal,body):
  captured.append(body);return dict(job_id='captured-only',state='queued')
adapter=HiMatIntegration(Capture(),'https://example.invalid',b'x'*32)
for _ in range(2):adapter.submit_sequence(owner,old['protein_sequence'],old['host_species'])
new=captured[0];cfg=new['request']['revision_config']
assert captured[0]==captured[1]
assert policy.request(encode(new['request']))['prediction']['engine']=='af3'
assert cfg['calculation_config_id']=='himat-expert-v2-20261013-same-engine-v2'
assert cfg['max_mutation_fraction']==cfg['design_site_fraction']==.07
assert s.route(233,16,cfg)==['af3'] and s.route(300,20,cfg)==['af3']
assert s.route(100,10,cfg)==['af3'] and s.route(100,11,cfg)==['esmfold2']
original=v.config
try:
 v.config=lambda *a,**kw:old['revision_config']
 adapter.submit_sequence(owner,old['protein_sequence'],old['host_species'])
finally:v.config=original
assert new['idempotency_key']!=captured[2]['idempotency_key']
credential=next(r for r in json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials'] if r['principal']==owner.principal_id)
req=urllib.request.Request('http://127.0.0.1:18083/mcp',headers={'Content-Type':'application/json','X-T01-MCP-Authorization':'Bearer '+credential['token']},data=json.dumps(dict(jsonrpc='2.0',id=1,method='tools/list',params={})).encode())
with urllib.request.urlopen(req,timeout=20) as response:catalog=json.load(response)
names=sorted(t['name'] for t in catalog['result']['tools'])
assert names==['workflow_check','workflow_confirm_design','workflow_submit_sequence']
print(json.dumps(dict(status='PASS',configuration=cfg['calculation_config_id'],wt_engine='af3',same_sequence_new_policy_not_old_replay=True,repeated_new_request_stable=True,mutation_budget=.07,tools=names,source_report_job_preserved=job['job_id'],new_scientific_jobs=0,submission_capture_only=True)))
'''
if __name__=='__main__':
 value=common.remote(CODE)
 Path(__file__).with_name('entry-verification.json').write_text(json.dumps(value,indent=2),encoding='utf8')
 print(json.dumps(value))
