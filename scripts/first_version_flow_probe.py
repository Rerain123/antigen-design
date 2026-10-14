"""Fresh existing-sequence HiMat run; secrets remain in the service container.

Start is explicitly separate from status. No consent is invented or submitted.
All snapshots omit signed download URLs and credentials.
"""
import argparse
import json
from datetime import datetime,timezone
import prepare_m1_p1_deploy as common

OUT=common.ROOT/'discovery/t01-phase1-real/first-version-flow-20260926'
OLD='t01p1r-job-c308ede7d6c843b180c82f91b3d44dec'
REMOTE=r'''
import json,sys,urllib.request,hashlib
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.common import decode,sha
p=json.load(sys.stdin)
owner=Principal('himat-t01-test',frozenset(['submit','query','download']),'not-a-credential')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
credential=next(r for r in json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials'] if r['principal']==owner.principal_id)
def rpc(name,args):
    req=urllib.request.Request('http://127.0.0.1:18083/mcp',headers={'Content-Type':'application/json','X-T01-MCP-Authorization':'Bearer '+credential['token']},data=json.dumps(dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name=name,arguments=args))).encode())
    with urllib.request.urlopen(req,timeout=60) as response:value=json.load(response)
    if 'error' in value:raise RuntimeError('MCP request failed')
    result=value['result']
    if result.get('isError'):raise RuntimeError('MCP tool failed')
    return result.get('structuredContent',result)
if p['action']=='start':
    old=rt.get(p['old']);body=decode(rt._request_bytes(old))
    args=dict(protein_sequence=body['protein_sequence'],host_species=body['host_species'],run_key='first-version-flow-20260926-r01')
    first=rpc('workflow_submit_sequence',args)
    second=rpc('workflow_submit_sequence',args)
    assert first['job_id']==second['job_id']
    print(json.dumps(dict(job_id=first['job_id'],sequence_sha256=sha(body['protein_sequence'].encode()),sequence_length=len(body['protein_sequence']),host_species=body['host_species'],idempotency_verified=True,source_request_job=p['old'],new_run=True,user_confirmation_submitted=False)))
else:
    jid=p['job_id'];card=rpc('workflow_check',dict(job_id=jid))
    job=rt.get(jid);body=decode(rt._request_bytes(job));ex=rt.execution(jid)
    nodes={name:{k:row.get(k) for k in ('node_id','job_id','state','reason_code','detail')} for name,row in ex.get('nodes',{}).items()}
    pending=ex.get('pending_confirmation')
    active_progress={n:card['node_progress'][n] for n in card.get('current_nodes',[])}
    batch_progress={}
    for name,row in nodes.items():
        if not name.endswith('netmhc') or not row.get('job_id'):continue
        ne=rt.execution(row['job_id']);ids=ne.get('batches',[])
        if ids:
            counts={}
            for child_id in ids:
                state=rt.get(child_id)['state'];counts[state]=counts.get(state,0)+1
            batch_progress[name]=dict(submitted=len(ids),states=counts,storage_preflight=ne.get('storage_preflight'))
    extra={}
    for name in ('design_inputs','design','rescore','variant_report'):
        row=nodes.get(name) or {}
        if row.get('state')!='succeeded':continue
        result=rt.result(row['job_id'])
        if name=='design_inputs':
            audit=result['audit'];perm=audit['permissions']
            extra[name]=dict(fixed=len(perm['fixed_positions']),restricted=len(perm['restricted_positions']),open=len(perm['open_positions']),confirmation_required=audit.get('confirmation_required',False),mask_conversion_error=audit['mask_conversion_error'])
        elif name=='design':extra[name]=dict(count=len(result['generation']['records']))
        elif name=='rescore':extra[name]=result.get('engineering_rules')
        else:extra[name]={k:result['report'].get(k) for k in ('outcome','summary','ranked_candidates')}
    downloads=[]
    for attachment in card.get('data',{}).get('attachments',[]):
        location=urlsplit(attachment['fileUrl'])
        assert location.path.startswith('/antigen-design/attachments/'+jid+'/')
        expected=parse_qs(location.query)['sha256'][0]
        with urllib.request.urlopen('http://127.0.0.1:18083'+location.path+'?'+location.query,timeout=60) as response:
            raw=response.read(128*1024**2+1)
        assert len(raw)<=128*1024**2 and sha(raw)==expected
        downloads.append(dict(file_name=attachment['fileName'],bytes=len(raw),sha256=expected,verified=True))
    print(json.dumps(dict(job_id=jid,run_id=job['run_id'],state=job['state'],error_code=job['error_code'],nodes=nodes,pending_confirmation=pending,facts=extra,batch_progress=batch_progress,active_progress=active_progress,card_type=card.get('type'),card_summary=card.get('data',{}).get('summaryText'),controlled_downloads=downloads,transport='service loopback HiMat MCP and attachment routes; not browser UI',scientific_gate='CLOSED',public_report_api_called=False)))
'''


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=('start','status'));a=ap.parse_args()
    batch=OUT/'himat-submit-r01.json'
    if a.action=='start':
        result=common.remote(REMOTE,dict(action='start',old=OLD))
        if batch.exists():assert json.loads(batch.read_bytes())['job_id']==result['job_id']
        else:batch.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    else:
        task=json.loads(batch.read_bytes())
        result=common.remote(REMOTE,dict(action='status',job_id=task['job_id']))
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        (OUT/('status-'+stamp+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
