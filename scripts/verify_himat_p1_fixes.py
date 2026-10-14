"""Verify deployed P1 fixes using existing bytes and read-only policy probes."""
import json
import subprocess
from datetime import datetime,timezone

import prepare_m1_p1_deploy as common
import prepare_himat_p1_fixes as deployment
import verify_himat_esmfold2_path_fix as esm

OUT=common.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/himat-p1-deployment-r07.json'
JOB='t01p1r-job-120f08a88827456e83bfdf5e6ef19b92'

REMOTE=r'''
import hashlib,json,sqlite3,sys,urllib.request
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development.blast.result import parse_hsps,_runtime
task=json.load(sys.stdin)
root=Path('/var/lib/t01/runtime')
db=sqlite3.connect('file:'+str(root/'state.sqlite3')+'?mode=ro',uri=True)
db.execute('PRAGMA query_only=ON')
count=db.execute('select count(*) from jobs').fetchone()[0]
parent=json.loads(db.execute('select data from jobs where id=?',(task['job_id'],)).fetchone()[0])
jobs=[json.loads(raw) for (raw,) in db.execute('select data from jobs')]
blast=next(j for j in jobs if j['run_id']==parent['run_id'] and j['tool_id']=='t01.real.blast')
def read(ref):
    relative=db.execute('select relative_path from artifacts where id=?',(ref['artifact_id'],)).fetchone()[0]
    path=(root/relative).resolve();assert path.is_relative_to(root)
    raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==ref['sha256'];return raw
body=json.loads(read(blast['request_artifact']))
byhash={ref['sha256']:read(ref) for ref in blast['artifacts']}
execution=json.loads(db.execute('select data from executions where job_id=?',(blast['job_id'],)).fetchone()[0])
receipt=execution['resident_receipt']
runtime=json.loads(byhash[receipt['outputs']['output/native/runtime.json']['sha256']])
files={'input.json':byhash[runtime['input_json_sha256']],'input.fasta':byhash[runtime['input_fasta_sha256']],
       'resident/request.json':byhash[receipt['request_sha256']]}
for raw in byhash.values():
    if raw.startswith(b'{'):
        value=json.loads(raw)
        if value.get('resident_receipt',{}).get('execution_id')==receipt['execution_id']:files['resident/execution.json']=raw
for name,info in receipt['outputs'].items():
    mapped=name.replace('output/native/','output/',1) if name.startswith('output/native/') else 'resident/'+name[7:]
    files[mapped]=byhash[info['sha256']]
_runtime(files,body)
hsps=parse_hsps(files['output/blast.txt'],body)
credentials=json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials']
row=next(r for r in credentials if r['principal']=='himat-t01-test')
def rpc(method,params):
    request=urllib.request.Request('http://127.0.0.1:18083/mcp',headers={
        'Content-Type':'application/json','X-T01-MCP-Authorization':'Bearer '+row['token']},
        data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode())
    with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
tools=rpc('tools/list',{})['result']['tools']
card=rpc('tools/call',{'name':'workflow_check','arguments':{'job_id':task['job_id']}})['result']
assert set(card)=={'data','type'} and card['type']=='primer_design_output'
issues=card['data']['issues']
assert any('N01' in s and 'TOOL_FAILED' in s for s in issues)
assert any('N03' in s and 'OUTPUT_INVALID' in s for s in issues)
downloads=[]
for attachment in card['data']['attachments']:
    url=urlsplit(attachment['fileUrl'])
    with urllib.request.urlopen('http://127.0.0.1:18083'+url.path+'?'+url.query,timeout=30) as response:raw=response.read()
    digest=hashlib.sha256(raw).hexdigest();assert digest==parse_qs(url.query)['sha256'][0]
    if attachment['attachmentId']=='attachment_report':assert b'TOOL_FAILED' in raw and b'OUTPUT_INVALID' in raw
    downloads.append({'kind':attachment['attachmentId'],'sha256':digest,'bytes':len(raw)})
assert count==db.execute('select count(*) from jobs').fetchone()[0]
print(json.dumps({'source_hashes':{n:hashlib.sha256((Path('/app/src/t01_phase1_real')/n).read_bytes()).hexdigest() for n in task['files']},
 'blast_original_state':blast['state'],'blast_native_contract_pass':True,'blast_replay_hsps':len(hsps),
 'blast_replay_qualifying_hsps':sum(h['passes_registered_thresholds'] for h in hsps),
 'tool_names':[t['name'] for t in tools],'card_summary':card['data']['summaryText'],'card_issues':issues,
 'downloads':downloads,'job_count_unchanged':True,'design_input_mode':__import__('t01_phase1_real.development.workflow.engineering',fromlist=['MODE']).MODE}))
'''


def main():
    before=deployment.idle()
    if not esm.OUT.exists():esm.main()
    existing=json.loads(esm.OUT.read_bytes())
    assert existing['status']=='HIMAT_ESMFOLD2_ACTUAL_PATH_DEPLOYED_PASS'
    assert all(existing['native_worker']['hashes'][n]==digest for n,digest in deployment.esm.source_hashes().items())
    value=common.remote(REMOTE,{'job_id':JOB,'files':list(deployment.FILES)})
    assert value['source_hashes']==deployment.hashes()
    assert value['blast_replay_hsps']==500 and value['blast_original_state']=='failed'
    assert set(value['tool_names'])=={'workflow_submit_sequence','workflow_check'}
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['status'].get('readyReplicas')==1
    assert live['status']['observedGeneration']==live['metadata']['generation']==existing['generation']
    volume=next(v for v in live['spec']['template']['spec']['volumes'] if v['name']==deployment.VOLUME)
    assert volume['configMap']['name']==deployment.NAME
    after=deployment.idle()
    result=dict(status='HIMAT_P1_DEPLOYED_READONLY_VERIFIED',observed_at_utc=datetime.now(timezone.utc).isoformat(),
                generation=live['metadata']['generation'],service=value,esm_evidence=esm.OUT.relative_to(common.ROOT).as_posix(),
                active_jobs_before=before['active_jobs'],active_jobs_after=after['active_jobs'],
                new_job_submitted=False,new_233aa_inference_verified=False,
                generic_design_limit='Same-run backend audit derives masks; unresolved evidence/export conditions remain explicit and cannot force N11',
                scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')
    with OUT.open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(result['status'],OUT)


if __name__=='__main__':main()
