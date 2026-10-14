"""Read-only replay of real 24-candidate validation into retry and report code.

The validation context exists only in memory. No archived workflow is rewritten,
and the derived 48-candidate request is never submitted.
"""
import json
import prepare_m1_p1_deploy as common
import prepare_n12_validation as deploy

REMOTE='''import copy,json,sys
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import decode,encode,sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import validation,design_rounds,service
from t01_phase1_real.development.variant_report import policy,source,compute
from t01_phase1_real.service_api.user_report import render
p=json.load(sys.stdin)
rt=Runtime('/var/lib/t01/runtime',scope='svc-'+p['owner'][:24],blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
jid=p['job_id'];before=rt.get(jid);original=rt.execution(jid);body=decode(rt._request_bytes(before))
with rt._db() as db:count_before=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
fact=validation.assemble(rt,body,original['nodes'],'validation',before['run_id'])
context=dict(workflow_job_id=jid,node='validation')
view=copy.deepcopy(original)
view['nodes']['validation']=dict(state='succeeded',origin='INTERNAL_FACT',fact=fact,validation_source=context)
class ReadOnlyView:
    def __getattr__(self,name):
        if name in ('_tx','dispatch','recover','control','submit_sequence','submit_workflow'):
            raise AssertionError('Mutation is forbidden in read-only replay')
        return getattr(rt,name)
    def execution(self,job):return copy.deepcopy(view) if job==jid else rt.execution(job)
proxy=ReadOnlyView()
assert validation.verified_fact(proxy,jid,'validation')==fact
request,reason=design_rounds.request(proxy,body,view['nodes'],'retry1_design')
assert reason is None and request['n_designs']==48 and request['sampling_temperature']==.3
prior=decode(rt._request_bytes(rt.get(original['nodes']['design']['job_id'])))
assert {k:v for k,v in request.items() if k not in ('n_designs','sampling_temperature')}=={
    k:v for k,v in prior.items() if k not in ('n_designs','sampling_temperature')}
report_body=policy.request(encode(dict(protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
    upstream=dict(design_audit=service.source(rt,original['nodes']['design_audit']),foldx=None),
    variant_source='N11_DESIGN_AUDIT',foldx_bindings=[],timeout_seconds=60,validation_source=context)))
with rt._db() as db:
    files,_,_=source.sources(proxy,db,report_body)
report=compute.evaluate(report_body,files)
assert report['n12_validation']==fact and len(report['records'])==24
assert all(r['disposition']=='EXCLUDED' and r['s28_validation']['passed'] is False for r in report['records'])
data=dict(n12_validation=[fact],variant_report=report)
html=render(data,preview_note='工程回放：真实归档候选重算；未启动新设计，不作为新运行报告。')
assert '逐轮候选验证' in html.decode() and '候选对比' in html.decode()
assert rt.get(jid)==before and rt.execution(jid)==original
with rt._db() as db:assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==count_before
print(json.dumps(dict(status='S28_REAL_AUDIT_RETRY_AND_REPORT_REPLAY_PASS',run_id=before['run_id'],
    mode='READ_ONLY_IN_MEMORY_VALIDATION_CONTEXT',archived_state_unchanged=True,new_jobs=0,
    derived_retry=dict(n_designs=request['n_designs'],sampling_temperature=request['sampling_temperature'],
        remaining_request_fields_unchanged=True,submitted=False),report_summary=report['summary'],
    records=len(report['records']),html_sha256=sha(html),report_data=data,
    scientific_gate='CLOSED',usable_for_pipeline=False)))
'''


def main():
    batch=json.loads((common.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/r16/batch.json').read_bytes())
    value=common.remote(REMOTE,dict(owner=batch['owner'],job_id=batch['job_id']))
    from t01_phase1_real.service_api.user_report import render
    html=render(value['report_data'],preview_note='工程回放：真实归档候选重算；未启动新设计，不作为新运行报告。')
    from t01_phase1_real.common import sha
    assert sha(html)==value['html_sha256']
    with (deploy.EVIDENCE/'control-report-replay.json').open('x',encoding='utf8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
    (deploy.EVIDENCE/'control-report-replay.html').write_bytes(html)
    print(json.dumps({k:value[k] for k in ('status','records','derived_retry','new_jobs')}))


if __name__=='__main__':main()
