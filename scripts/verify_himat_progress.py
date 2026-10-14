"""Read-only P2 live-code, MCP, historical-snapshot and receipt verification."""
import json
import subprocess
import prepare_m1_p1_deploy as c
import prepare_himat_progress_fix as deployment
import verify_himat_p1_fixes as old

OUT=c.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/himat-progress-deployment-r12.json'


def main():
    state=c.idle();assert not state['active_jobs']
    pre=json.loads((deployment.OUT/'preflight.json').read_bytes())
    service=c.remote(old.REMOTE,dict(job_id=old.JOB,files=list(deployment.FILES)))
    assert service['source_hashes']==pre['source_hashes']==deployment.hashes()
    snapshot=json.loads((OUT.parent/'himat-progress-live-replay-r01.json').read_bytes())['source_snapshot']
    check=c.remote('''import json,sys,sqlite3,urllib.request,inspect
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.service_api.progress import project,execution_status
from t01_phase1_real.service_api.transport import Phase1RealServiceServer
p=json.load(sys.stdin);snap=p['snapshot']
class Snapshot:
 def status(self,principal,job_id):
  assert job_id==snap['job_id']
  return dict(snap,terminal=False,scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')
owner=Principal('himat-t01-test',frozenset(['query','submit']),'not-a-credential')
adapter=HiMatIntegration(Snapshot(),'https://example.invalid',b'x'*32)
replay=adapter.check(owner,snap['job_id'])
assert replay['total_nodes']==18 and replay['completed_nodes']==2 and replay['current_nodes']==['N03']
assert replay['internal_step_counts']['total']==51 and replay['internal_step_counts']['finished']==3
rt=Runtime('/var/lib/t01/runtime',scope='iedb-n03-engineering-r01',blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
child=rt.get('t01p1r-job-ad9e4b67b35440c483ada5b5303b5a7b')
assert execution_status(rt,child['job_id'],child['run_id'])['phase']=='finished'
class CollectionReplay:
 def get(self,jid):return dict(rt.get(jid),state='reconciling')
 def execution(self,jid):return rt.execution(jid)
receipt_replay=execution_status(CollectionReplay(),child['job_id'],child['run_id'])
assert receipt_replay['phase']=='finalizing' and receipt_replay['stopped_confirmed']
assert execution_status(CollectionReplay(),child['job_id'],'foreign')['phase']=='unknown'
class Capture:
 def submit(self,principal,body):self.body=body;return dict(state='queued')
capture=Capture();HiMatIntegration(capture,'https://example.invalid',b'x'*32).submit_sequence(owner,'ACDEFGHIKLMNPQRSTVWY','Homo sapiens')
blast=capture.body['request']['analysis']['blast']
assert blast['database_id']=='iedb-20260924-r01' and blast['thresholds']==dict(identity_percent_min=70,query_coverage_percent_min=80)
credentials=json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials']
credential=next(r for r in credentials if r['principal']=='himat-t01-test')
def rpc(method,params):
 req=urllib.request.Request('http://127.0.0.1:18083/mcp',headers={'Content-Type':'application/json','X-T01-MCP-Authorization':'Bearer '+credential['token']},data=json.dumps(dict(jsonrpc='2.0',id=1,method=method,params=params)).encode())
 with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
tools=rpc('tools/list',{})['result']['tools'];description=next(t['description'] for t in tools if t['name']=='workflow_check')
assert '18' in description and 'waiting_worker' in description and 'finalizing' in description
cards=[]
for jid in ('t01p1r-job-429765bbfc954bb2af8a11570a8d0cbc','t01p1r-job-df485abbd2664ac68030f08bdaa0032a'):
 card=rpc('tools/call',dict(name='workflow_check',arguments=dict(job_id=jid)))['result']
 assert card['type']=='primer_design_output'
 cards.append(dict(job_id=jid,type=card['type'],summary=card['data']['summaryText']))
print(json.dumps(dict(historical_replay=replay,receipt_replay=receipt_replay,receipt_replay_is_hypothetical_collection_state=True,
    tools_description=description,iedb_submission_preserved=blast,cancelled_cards=cards,new_workflow_submitted=False)))
''',dict(snapshot=snapshot))
    live=json.loads(subprocess.check_output(c.K+['get','deployment','antigen-design','-o','json']))
    assert live['status'].get('readyReplicas')==1 and live['status']['observedGeneration']==live['metadata']['generation']
    after=c.idle();assert not after['active_jobs']
    value=dict(status='HIMAT_P2_PROGRESS_DEPLOYED_VERIFIED',generation=live['metadata']['generation'],
        service=service,verification=check,idle_before=state,idle_after=after,
        scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')
    OUT.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(status=value['status'],generation=value['generation'],historical_completed_nodes=check['historical_replay']['completed_nodes'],
        total_nodes=18,current_nodes=check['historical_replay']['current_nodes'],iedb_preserved=True,new_workflow_submitted=False)))


if __name__=='__main__':main()
