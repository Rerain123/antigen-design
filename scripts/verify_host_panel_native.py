"""Read and verify the new host-panel native receipts, without dispatching jobs."""
import json
import prepare_m1_p1_deploy as common
from host_panel_flow_probe import OUT

REMOTE=r'''
import json,sys,hashlib
from pathlib import Path
from datetime import datetime
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.common import decode
from t01_phase1_real.development.netmhc import host_panel,service
rt=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset(['query']),'none').runtime_scope)
flow=rt.get(json.load(sys.stdin)['job_id']);nodes=rt.execution(flow['job_id'])['nodes']
job=rt.get(nodes['netmhc']['job_id']);assert job['state']=='succeeded'
body=decode(rt._request_bytes(job));result=rt.result(job['job_id'])
assert body['panel_mode']==host_panel.MODE and job['run_id']==flow['run_id']
service.verify_sources(rt,job,result)
assert result['panel_selection']['requested_counts']==dict(mhc_i=76,mhc_ii=0)
assert result['channels']['mhc_i']['status']=='parsed_unreviewed'
assert result['channels']['mhc_ii']['status']=='unavailable'
rows=[];alleles=[]
for child_id in rt.execution(job['job_id'])['batches']:
 child=rt.get(child_id);ex=rt.execution(child_id);req=decode(rt._request_bytes(child))
 assert child['state']=='succeeded' and child['run_id']==job['run_id']
 raw=(Path(ex['resident_target'])/'output/native/runtime.json').read_bytes()
 digest=hashlib.sha256(raw).hexdigest()
 assert digest==ex['resident_receipt']['outputs']['output/native/runtime.json']['sha256']
 native=json.loads(raw);i=native['commands']['mhc_i'];ii=native['commands']['mhc_ii']
 assert i['exit_code']==0 and ii['not_executed'] and ii['argv']==[] and ii['exit_code'] is None
 assert req['mhc_ii_alleles']==[]
 alleles+=req['mhc_i_alleles']
 rows.append(dict(job_id=child_id,runtime_sha256=digest,mhc_i_seconds=i['elapsed_seconds'],
                  mhc_ii_not_executed=True,alleles=req['mhc_i_alleles']))
assert len(rows)==4 and alleles==host_panel.manifest(body['host_species'])['channels']['mhc_i']['alleles']
stamp=lambda s:datetime.fromisoformat(s.replace('Z','+00:00'))
print(json.dumps(dict(job_id=job['job_id'],run_id=job['run_id'],state=job['state'],
 elapsed_seconds=(stamp(job['finished_at'])-stamp(job['started_at'])).total_seconds(),
 timeout_seconds=body['timeout_seconds'],sequence_length=len(body['protein_sequence']),
 panel_selection=result['panel_selection'],warnings=result['warnings'],batches=rows,
 scientific_gate='CLOSED',usable_for_pipeline=False)))
'''

if __name__=='__main__':
    task=json.loads((OUT/'host-panel-flow-submit.json').read_bytes())
    value=common.remote(REMOTE,dict(job_id=task['job_id']))
    path=OUT/'host-panel-native.json'
    with path.open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in value.items() if k not in ('panel_selection','batches')},ensure_ascii=False))
