"""Fresh W4 local WT draft campaign with real N10/N06/N07 development tasks."""
import argparse
import copy
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import RuntimeFault, encode, decode, sha, now
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.wt_draft import policy, service
from t01_phase1_real.development.developability import policy as n10
from t01_phase1_real.development.glycosylation import policy as n07
from t01_phase1_real.development.epitope_map import policy as n06

SEQ='ACDEFGHIKLMNPQRSTVWY'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(value if isinstance(value,bytes) else encode(value))


def request():
    return dict(protein_sequence=SEQ,user_sequence_id='W4-local-WT-engineering',host_species=None,organism=None,
        upstream={name:None for name in policy.PRODUCERS},timeout_seconds=30)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True);parser.add_argument('--batch',required=True)
    args=parser.parse_args();root=Path(args.root).resolve();batch=Path(args.batch).resolve()
    assert root.is_relative_to(REPO/'var/t01-phase1-real') and not root.exists(),'Use a fresh runtime root'
    assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w4') and not batch.exists(),'Use a fresh W4 evidence batch'
    batch.mkdir(parents=True);rt=Runtime(root);cases=[];upstreams=[]
    for base in ('src/t01_phase1_real','src/t01_structure_mapping'):
        for path in sorted((REPO/base).rglob('*.py')):write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    for name in ('scripts/t01_runtime.py','scripts/run_wt_draft_acceptance.py','tests/test_wt_draft_development.py'):
        write(batch/'source'/name,(REPO/name).read_bytes())
    write(batch/'profile.json',policy.registered_profile());write(batch/'rules.json',policy.registered_rules())
    write(batch/'authority.json',[dict(path=p.relative_to(REPO).as_posix(),size_bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in policy.AUTHORITY])

    def closed(value):
        assert value['usable_for_pipeline'] is False and value['automatic_handoff'] is False and value['scientific_signoff'] is None
        assert value['production_status']=='NOT_DEPLOYED'
        if value.get('draft'):
            draft=value['draft'];gate=draft['gate']
            assert gate['status']=='NOT_EVALUATED' and gate['suitable_for_design'] is None and gate['design_skip_reason'] is None
            assert not any(gate[k] for k in ('n11_release','automatic_design_release','formal_wt_release','agent_c_handoff'))
            assert draft['document_kind']=='LOCAL_WT_ASSESSMENT_DRAFT' and draft['agent_c_payload'] is None

    def record(name,job,state='succeeded',error=None,upstream=False,kind='REAL_LOCAL_DEVELOPMENT'):
        job=rt.get(job['job_id']);assert job['state']==state and job['error_code']==error,(name,job)
        target=batch/('upstreams' if upstream else 'cases')/name
        write(target/'job.json',job);write(target/'events.json',rt.events(job['job_id']))
        if job['attempt_id']:write(target/'execution.json',rt.execution(job['job_id']))
        result=None
        if job['artifacts']:
            result=rt.result(job['job_id']);closed(result);write(target/'result.json',result)
            for ref in job['artifacts']:
                raw=rt.artifact_bytes(job['job_id'],ref['artifact_id']);assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256']
                write(target/'artifacts'/ref['artifact_id'],raw)
        entry=dict(case=name,job_id=job['job_id'],state=state,error_code=error,evidence_kind=kind,artifacts_verified=len(job['artifacts']))
        (upstreams if upstream else cases).append(entry)
        return result

    def submit(name,body,tool=policy.TOOL,fault=None,execute=True):
        write(batch/'requests'/(name+'.json'),body);job=rt.submit_sequence(encode(body),name,tool)
        rt._development_fault=fault
        try:return rt.dispatch(job['job_id']) if execute else job
        finally:rt._development_fault=None

    def control(job,op,key):
        return rt.control(encode(dict(contract_version='0.1.0',operation=op,job_id=job['job_id'],idempotency_key=key)))

    def reject(name,body):
        write(batch/'requests'/(name+'.json'),body)
        try:rt.submit_sequence(encode(body),name,policy.TOOL)
        except RuntimeFault as exc:
            write(batch/'cases'/name/'error.json',exc.envelope());cases.append(dict(case=name,state='REJECTED',error_code=exc.code,
                evidence_kind='CONTROLLED_INVALID_INPUT',artifacts_verified=0));return
        raise AssertionError(name+' was admitted')

    baseline=dict(protein_sequence=SEQ,user_sequence_id='real-partial-n10',structure_input=dict(state='not_provided',artifact=None,
        reason_code=None),target_ph=None,target_ph_range=[4,8],dimension_weights=None,timeout_seconds=30)
    n10job=submit('n10-partial',baseline,n10.TOOL);n10value=record('n10-partial',n10job,upstream=True)
    assert n10value['developability']['overall_score'] is None and not n10value['developability']['n10_complete']
    n06body=dict(protein_sequence=SEQ,user_sequence_id='n06-partial',timeout_seconds=5,
        bepipred_input=dict(state='not_provided',artifact=None,reason_code=None),netmhc_input=dict(state='not_provided',artifact=None,reason_code=None),
        blast_input=dict(state='not_executed',artifact=None,reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'))
    mapjob=submit('n06-missing-predictions',n06body,n06.TOOL)
    record('n06-missing-predictions',mapjob,'failed','TOOL_FAILED',upstream=True)
    n07body=dict(protein_sequence=SEQ,user_sequence_id='n07-scan',timeout_seconds=5,
        hotspot_input=dict(state='not_provided',hotspots=None,source=None,reason_code=None))
    glycojob=submit('n07-independent-scan',n07body,n07.TOOL);record('n07-independent-scan',glycojob,upstream=True)
    body=request()
    for name,job in (('developability',n10job),('epitope_map',mapjob),('glycosylation',glycojob)):
        body['upstream'][name]=service.task_source(rt,name,job['job_id'])
    full=submit('real-partial-upstreams',body);result=record('real-partial-upstreams',full)
    assert result['draft']['fields']['developability']['value']==n10value['developability']
    assert result['draft']['fields']['glycosylation']['value']['shielding_risk'] is None
    assert result['draft']['checks']['unsigned']==['glycosylation','developability']
    assert result['draft']['checks']['failed']==['epitope_map']
    assert rt.submit_sequence(encode(body),'real-partial-upstreams',policy.TOOL)==full
    altered=copy.deepcopy(body);altered['user_sequence_id']='conflict'
    try:rt.submit_sequence(encode(altered),'real-partial-upstreams',policy.TOOL)
    except RuntimeFault as exc:assert exc.code=='IDEMPOTENCY_CONFLICT'
    else:raise AssertionError('Idempotency conflict not rejected')
    cases.append(dict(case='idempotency-duplicate-conflict',state='PASS',artifacts_verified=0))

    record('missing-upstreams',submit('missing-upstreams',request()))
    failed=submit('n10-controlled-failure',baseline,n10.TOOL,'compute_failure')
    record('n10-controlled-failure',failed,'failed','TOOL_FAILED',True,'CONTROLLED_TOOL_FAILURE')
    failed_body=request();failed_body['upstream']['developability']=service.task_source(rt,'developability',failed['job_id'])
    value=record('failed-upstream',submit('failed-upstream',failed_body));assert value['draft']['checks']['failed']==['developability']
    pending=submit('n10-pending',baseline,n10.TOOL,execute=False);pending_body=request()
    pending_body['upstream']['developability']=service.task_source(rt,'developability',pending['job_id'])
    value=record('pending-upstream',submit('pending-upstream',pending_body));assert value['draft']['checks']['pending']==['developability']
    stopped=control(pending,'cancel','stop-upstream');record('n10-no-attempt-cancel',stopped,'cancelled','CANCELLED',True,'CONTROLLED_STOP')
    value=record('failed-without-artifact',submit('failed-without-artifact',pending_body))
    assert value['draft']['checks']['failed']==['developability'] and not value['draft']['assessments']['developability']['executed']

    for name,mutate in (
        ('sequence-mismatch',lambda b:b.update(protein_sequence='A'*len(SEQ))),
        ('forged-hash',lambda b:b['upstream']['developability']['artifact'].update(sha256='0'*64)),
        ('forged-attempt',lambda b:b['upstream']['developability']['artifact'].update(attempt_id='t01p1r-attempt-'+'0'*32)),
        ('self-asserted-signoff',lambda b:b.update(scientific_signoff={'reviewer':'caller'}))):
        bad=copy.deepcopy(body);mutate(bad);reject(name,bad)

    for name,error in (('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID'),('interrupt_after_claim','INTERRUPTED')):
        job=submit('wt-'+name,body,fault=name)
        if name=='interrupt_after_claim':job=rt.recover(job['job_id'])
        record('wt-'+name,job,'failed',error,kind='CONTROLLED_LOCAL_FAILURE')
        retry=control(job,'retry','retry-'+name);rt.dispatch(retry['job_id']);record('retry-'+name,retry)
    queued=submit('wt-queued-stop',body,execute=False);stopped=control(queued,'cancel','wt-cancel')
    record('wt-queued-stop',stopped,'cancelled','CANCELLED',kind='CONTROLLED_STOP')
    retry=control(stopped,'retry','retry-stopped');rt.dispatch(retry['job_id']);record('retry-stopped',retry)

    # Controlled changes touch only this newly created campaign, then restore bytes.
    ref=body['upstream']['developability']['artifact']
    with rt._db() as db:relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    path=rt.root/relative;raw=path.read_bytes();queued=submit('source-changed-after-submit',body,execute=False)
    try:
        path.write_bytes(raw+b' ');reject('damaged-source-at-admission',body)
        final=rt.dispatch(queued['job_id']);record('source-changed-after-submit',final,'failed',final['error_code'],kind='CONTROLLED_SOURCE_DAMAGE')
        assert final['attempt_id'] is None
    finally:path.write_bytes(raw)
    raw_ref=next(r for r in n10job['artifacts'] if r['role']=='raw')
    with rt._db() as db:relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(raw_ref['artifact_id'],)).fetchone()[0]
    path=rt.root/relative;raw=path.read_bytes()
    try:path.write_bytes(raw+b' ');reject('damaged-upstream-raw',body)
    finally:path.write_bytes(raw)

    command=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),'wt-draft',
        '--sequence',SEQ,'--developability-job-id',n10job['job_id'],'--key','documented-command','--run','--wait','30']
    process=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    write(batch/'documented-command.json',dict(argv=command,returncode=process.returncode,stdout=process.stdout.decode('utf-8'),stderr=process.stderr.decode('utf-8')))
    assert process.returncode==0,process.stderr
    cli_value=decode(process.stdout);record('documented-command',cli_value['job'])
    query=subprocess.run([*command[:6],'result','--job-id',cli_value['job']['job_id']],capture_output=True,timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW)
    write(batch/'documented-query.json',dict(returncode=query.returncode,stdout=query.stdout.decode('utf-8'),stderr=query.stderr.decode('utf-8')))
    assert query.returncode==0 and decode(query.stdout)==cli_value['result']
    result_ref=next(r for r in full['artifacts'] if r['role']=='result')
    with rt._db() as db:relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(result_ref['artifact_id'],)).fetchone()[0]
    path=rt.root/relative;raw=path.read_bytes()
    try:
        path.write_bytes(raw+b' ')
        try:rt.result(full['job_id'])
        except RuntimeFault as exc:write(batch/'result-tamper-check.json',exc.envelope())
        else:raise AssertionError('Damaged result query succeeded')
    finally:path.write_bytes(raw)
    cases.append(dict(case='published-result-integrity',state='PASS',artifacts_verified=0))
    assert decode((batch/'profile.json').read_bytes())==policy.registered_profile()
    files=[dict(path=p.relative_to(batch).as_posix(),size_bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
        for p in sorted(batch.rglob('*')) if p.is_file()]
    index=dict(status='PASS',scope='W4_GATE_WT_LOCAL_DRAFT_ENGINEERING',created_at=now(),runtime_root=str(root),
        cases=cases,upstreams=upstreams,files=files,file_count=len(files),
        published_artifacts_verified=sum(x['artifacts_verified'] for x in cases+upstreams),
        scientific_gate_complete=False,n10_complete=False,formal_wt_delivery_complete=False,
        agent_c_production_interface_complete=False,automatic_handoff=False,production_status='NOT_DEPLOYED',
        real_upstream_scope='Fresh no-structure partial N10 + N06 missing predictors + N07 actual scan; no models invoked',
        historical_batches_modified=False)
    write(batch/'index.json',index)
    print(encode(dict(status='PASS',cases=len(cases),upstreams=len(upstreams),files=len(files),
        artifacts=index['published_artifacts_verified'],index=str(batch/'index.json'))).decode())


if __name__=='__main__':main()
