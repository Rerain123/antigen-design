"""Read-only live verification; never approves or starts a scientific task."""
import json
import subprocess
import prepare_m1_p1_deploy as c
import prepare_n11_confirmation as deployment

JOB='t01p1r-job-c308ede7d6c843b180c82f91b3d44dec'
OUT=c.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/n11-confirm-deployment-r15.json'
REMOTE=r'''
import json,sys,hashlib,io,zipfile,urllib.request
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import sha,encode,decode
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.development.design_backend.compute import evaluate
from t01_phase1_real.development.workflow import engineering,service
from t01_phase1_real.development.proteinmpnn.policy import request as native_request
p=json.load(sys.stdin)
owner=Principal('himat-t01-test',frozenset(['submit','query','download']),'not-a-credential')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope,blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
job=rt.get(p['job']);snap=rt.workflow(job['job_id']);assert job['state']=='succeeded'
aj=rt.get(snap['nodes']['design_inputs']['job_id']);old=rt.result(aj['job_id'])
files={r['path']:rt.artifact_bytes(aj['job_id'],r['artifact']['artifact_id']) for r in old['raw_artifacts']}
request=decode(rt._request_bytes(aj))
assert evaluate(request,files)==old['audit'], 'Legacy audit changed'
candidate=evaluate(dict(request,t4_handshake=True),files)
assert candidate['mask_conversion_error'] is None, candidate['mask_conversion_error']
assert candidate['confirmation_required'] and candidate['n11_request_draft'] is None
draft=candidate['pending_n11_request_draft'];assert not draft['constraints']['fixed_positions']
projection=candidate['mask_conversion']['native/conversion.json']['coordinate_projection']
class Preview:
 def __getattr__(self,n):return getattr(rt,n)
 def result(self,jid):return dict(old,audit=candidate) if jid==aj['job_id'] else rt.result(jid)
body=decode(rt._request_bytes(job));rows=dict(snap['nodes'])
assert engineering.effective(Preview(),body,rows)[1]=='T4_EMPTY_FIXED_CONFIRMATION_REQUIRED'
rows['design']=dict(state='ready',confirmation=dict(audit_job_id=aj['job_id'],draft_sha256=sha(encode(draft)),decision=True))
req,reason=service.request_for(Preview(),body,rows,'design')
assert reason is None and native_request(encode(req))['t4_empty_fixed_confirmation'] is True
result=rt.result(job['job_id']);ref=next(r['artifact'] for r in result['raw_artifacts'] if r['path']=='output/package.zip')
raw=rt.artifact_bytes(job['job_id'],ref['artifact_id'])
preview=HiMatIntegration.report_markdown(dict(content=raw)).decode()
assert '结果：DESIGN_NOT_EXECUTED' in preview and 'N11_MASK_EXPORT_BLOCKED' in preview
assert sha(raw)==ref['sha256']
credentials=json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials']
credential=next(r for r in credentials if r['principal']=='himat-t01-test')
def rpc(method,params):
 req=urllib.request.Request('http://127.0.0.1:18083/mcp',headers={'Content-Type':'application/json','X-T01-MCP-Authorization':'Bearer '+credential['token']},data=json.dumps(dict(jsonrpc='2.0',id=1,method=method,params=params)).encode())
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
catalog=rpc('tools/list',{})['result']['tools']
assert any(r['name']=='workflow_confirm_design' for r in catalog)
submit=next(r for r in catalog if r['name']=='workflow_submit_sequence')
assert 'confirm_empty_fixed' not in submit['inputSchema']['properties']
card=rpc('tools/call',dict(name='workflow_check',arguments=dict(job_id=job['job_id'])))['result']
assert card['type']=='primer_design_output' and 'DESIGN_NOT_EXECUTED' in card['data']['summaryText']
hashes={n:sha((Path('/app/src/t01_phase1_real')/n).read_bytes()) for n in p['files']}
unchanged={n:h for n,h in p['baseline_files'].items() if n not in p['files']}
assert all(sha((Path('/app/src/t01_phase1_real')/n).read_bytes())==h for n,h in unchanged.items()), 'Unrelated live source drift'
assert rt.get(job['job_id'])==job
print(json.dumps(dict(source_hashes=hashes,archived_job_unchanged=True,archived_zip_sha256=sha(raw),
    unchanged_source_files_verified=len(unchanged),
    legacy_audit_replay_equal=True,actual_233aa_audit_preview=dict(fixed=0,restricted=len(draft['constraints']['restricted_positions']),
    open=len(draft['constraints']['open_positions']),requires_confirmation=True,mask_conversion_valid=True),
    coordinate_projection=dict(decimal_places=projection['decimal_places'],unit=projection['unit'],
        rounded_atom_count=len(projection['rounded_atoms']),max_absolute_delta_angstrom=projection['max_absolute_delta_angstrom']),
    confirmed_request_preview_valid=True,preview_only_not_a_recorded_consent=True,
    mcp_tools=[r['name'] for r in catalog],card_summary=card['data']['summaryText'],
    new_scientific_workflow_started=False,user_confirmation_recorded=False)))
'''


def main():
    before=c.idle();assert not before['active_jobs']
    baseline=json.loads((c.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/n11-confirm-r01/live-source-before.json').read_bytes())
    value=c.remote(REMOTE,dict(job=JOB,files=list(deployment.FILES),baseline_files=baseline['files']))
    pre=json.loads((deployment.OUT/'preflight.json').read_bytes())
    assert value['source_hashes']==deployment.hashes()==pre['source_hashes']
    live=json.loads(subprocess.check_output(c.K+['get','deployment','antigen-design','-o','json']))
    assert live['status'].get('readyReplicas')==1 and live['status']['observedGeneration']==live['metadata']['generation']
    after=c.idle();assert not after['active_jobs'] and after['gpu_state']['phase']=='idle'
    evidence=dict(status='N11_CONFIRMATION_AND_REPORT_DEPLOYED_VERIFIED',generation=live['metadata']['generation'],
        verification=value,idle_before=before,idle_after=after,scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')
    OUT.write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps(dict(status=evidence['status'],generation=evidence['generation'],verification=value),ensure_ascii=False))


if __name__=='__main__':main()
