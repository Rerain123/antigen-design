"""Reproducible W3 N07/S-12 local development campaign; not scientific signoff."""
import argparse
import itertools
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import RuntimeFault, decode, encode, now, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.glycosylation import policy
from t01_phase1_real.development.glycosylation.result import scan


def write(path,value):
    raw=value if isinstance(value,bytes) else encode(value)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw)


def context(state='not_provided',hotspots=None,source=None,reason=None):
    return dict(state=state,hotspots=hotspots,source=source,reason_code=reason)


def request(sequence,hotspot_input=None,alias='W3-local-input'):
    return dict(protein_sequence=sequence,user_sequence_id=alias,
        hotspot_input=hotspot_input if hotspot_input is not None else context(),timeout_seconds=5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--batch',required=True)
    args=parser.parse_args();root=Path(args.root).absolute();batch=Path(args.batch).absolute()
    assert root.is_absolute() and not root.exists(),'Use a fresh absolute runtime root'
    assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w3') and not batch.exists(),'Use a fresh W3 evidence batch'
    batch.mkdir(parents=True);rt=Runtime(root);entries=[]
    for path in [*sorted((REPO/'src/t01_phase1_real/development/glycosylation').glob('*.py')),
        REPO/'src/t01_phase1_real/development/runtime.py',REPO/'src/t01_phase1_real/development/registry.py',
        REPO/'src/t01_phase1_real/development/contracts.py',REPO/'src/t01_phase1_real/development/cli.py',
        REPO/'scripts/t01_runtime.py',REPO/'scripts/run_glycosylation_acceptance.py',REPO/'requirements/glycosylation.txt']:
        write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    write(batch/'profile.json',policy.registered_profile());write(batch/'rule-profile.json',policy.registered_rules())
    write(batch/'authority.json',[dict(path=p.relative_to(REPO).as_posix(),sha256=sha(p.read_bytes()),size_bytes=p.stat().st_size)
        for p in policy.AUTHORITY])

    alphabet='ACDEFGHIKLMNPQRSTVWY';observed=[]
    for triplet in map(''.join,itertools.product(alphabet,repeat=3)):
        if scan(request(triplet))['glycosylation']['sites']:observed.append(triplet)
    expected=[f'N{x}{end}' for x in alphabet if x!='P' for end in 'ST']
    assert observed==expected
    write(batch/'reference/exhaustive-triplets.json',dict(total_triplets=8000,expected_matches=38,observed_matches=len(observed),
        predicate='first=N, second!=P, third=S/T',matched_triplets=observed,qualification='DETERMINISTIC_RULE_REFERENCE'))

    def cli(name,argv,expected_code=0):
        command=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),*argv]
        run=subprocess.run(command,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch/'cli'/(name+'.json'),dict(argv=command,exit_code=run.returncode,stdout=run.stdout.decode('utf-8'),stderr=run.stderr.decode('utf-8')))
        assert run.returncode==expected_code,(name,run.returncode,run.stdout,run.stderr)
        return decode(run.stdout)

    def submit(name,value,fault=None):
        path=batch/'requests'/(name+'.json');write(path,value)
        job=cli(name+'-submit',['glycosylation','--input',str(path),'--key',name])
        rt._development_fault=fault
        try:rt.dispatch(job['job_id'])
        finally:rt._development_fault=None
        return rt.get(job['job_id'])

    def finish(name,job,state='succeeded',error=None,expected_sites=None):
        final=rt.get(job['job_id']);assert final['state']==state and final['error_code']==error,(name,final)
        write(batch/'cases'/name/'job.json',final);write(batch/'cases'/name/'events.json',rt.events(job['job_id']))
        if final['attempt_id']:write(batch/'cases'/name/'execution.json',rt.execution(job['job_id']))
        result=None
        if final['artifacts']:
            result=rt.result(job['job_id']);write(batch/'cases'/name/'result.json',result)
            assert not result['usable_for_pipeline'] and not result['automatic_handoff']
            for ref in final['artifacts']:
                raw=rt.artifact_bytes(job['job_id'],ref['artifact_id'])
                assert sha(raw)==ref['sha256'] and len(raw)==ref['size_bytes']
                write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
        if expected_sites is not None:
            assert result['glycosylation']['sites']==expected_sites
        if state!='succeeded' and result:assert result['glycosylation'] is None
        entry=dict(case=name,state=state,error_code=error,job_id=job['job_id'],artifacts_verified=len(final['artifacts']))
        entries.append(entry);return final,result

    full=cli('documented-independent-command',['glycosylation','--sequence','NNSTAAANPSAAANAT','--user-id','overlap-reference',
        '--key','documented-independent','--run'])
    independent,independent_result=finish('independent-overlap',full['job'],expected_sites=[1,2,14])
    assert independent_result['glycosylation']['expression_hint']=='真核表达优先'
    assert cli('same-key-duplicate',['glycosylation','--sequence','NNSTAAANPSAAANAT','--user-id','overlap-reference',
        '--key','documented-independent','--run'])==full
    assert cli('same-key-conflict',['glycosylation','--sequence','NAS','--key','documented-independent'],20)['error']['code']=='IDEMPOTENCY_CONFLICT'
    entries.append(dict(case='duplicate-and-conflict',state='PASS',same_job_id=True))

    finish('valid-empty',submit('valid-empty',request('ANPSAAAA')),expected_sites=[])
    sequence=list('A'*25)
    for position,motif in [(1,'NAS'),(20,'NAT'),(23,'NVT')]:sequence[position-1:position+2]=motif
    source=dict(node_id='N06',source_id='w3-hotspot-contract-fixture',sha256='a'*64)
    provided=context('available',[dict(start=1,end=20)],source)
    _,hotspot_result=finish('hotspot-contract',submit('hotspot-contract',request(''.join(sequence),provided)),expected_sites=[1,20,23])
    assert hotspot_result['glycosylation']['shielding_risk'] and hotspot_result['hotspot_assessment']['windows'][0]['site_count']==2
    _,empty_hotspot=finish('available-empty-hotspots',submit('available-empty-hotspots',request('NAS',context('available',[],source))),expected_sites=[1])
    assert empty_hotspot['hotspot_assessment']['status']=='EVALUATED'
    failed_source=dict(node_id='N06',source_id='w3-upstream-failure-fixture',sha256=None)
    _,unavailable=finish('upstream-unavailable',submit('upstream-unavailable',request('NAS',context('upstream_unavailable',None,failed_source,'N06_FAILED'))),expected_sites=[1])
    assert unavailable['hotspot_assessment']['status']=='NOT_PERFORMED'
    invalid=request('A'*30,context('available',[dict(start=1,end=19)],source));invalid_path=batch/'requests/invalid-window.json';write(invalid_path,invalid)
    assert cli('invalid-window',['glycosylation','--input',str(invalid_path),'--key','invalid-window'],20)['error']['code']=='INVALID_REQUEST'
    entries.append(dict(case='invalid-hotspot-window',state='PASS',rejected_before_admission=True))

    queued=cli('queued-submit',['glycosylation','--sequence','NAS','--key','queued'])
    cancelled=cli('queued-cancel',['cancel','--job-id',queued['job_id'],'--key','queued-cancel'])
    finish('queued-cancel',cancelled,'cancelled','CANCELLED')
    retry=cli('cancel-retry',['retry','--job-id',queued['job_id'],'--key','cancel-retry']);rt.dispatch(retry['job_id'])
    finish('cancel-retry',retry,expected_sites=[1])
    compute=submit('compute-failure',request('NAS'),fault='compute_failure');finish('compute-failure',compute,'failed','TOOL_FAILED')
    compute_retry=cli('compute-retry',['retry','--job-id',compute['job_id'],'--key','compute-retry']);rt.dispatch(compute_retry['job_id'])
    finish('compute-retry',compute_retry,expected_sites=[1])
    corrupt=submit('corrupt-output',request('NAS'),fault='corrupt_output');finish('corrupt-output',corrupt,'failed','OUTPUT_INVALID')
    interrupted=submit('interrupted',request('NAS'),fault='interrupt_after_claim');assert interrupted['state']=='running'
    recovered=cli('interrupted-recover',['recover','--job-id',interrupted['job_id']]);finish('interrupted-recover',recovered,'failed','INTERRUPTED')
    interrupted_retry=cli('interrupted-retry',['retry','--job-id',interrupted['job_id'],'--key','interrupted-retry']);rt.dispatch(interrupted_retry['job_id'])
    finish('interrupted-retry',interrupted_retry,expected_sites=[1])

    tamper=submit('artifact-tamper',request('NAS'));final,_=finish('artifact-tamper-original',tamper,expected_sites=[1])
    ref=next(row for row in final['artifacts'] if row['role']=='result')
    target=root/rt.attempt_path(final)/'published'/(ref['artifact_id']+'.bin');original=target.read_bytes()
    write(batch/'controlled-damage/original-result.bin',original);target.write_bytes(original+b' controlled-damage')
    try:rt.result(final['job_id'])
    except RuntimeFault as exc:assert exc.code=='HASH_MISMATCH'
    else:raise AssertionError('Tampered result was readable')
    write(batch/'controlled-damage/detection.json',dict(job_id=final['job_id'],artifact_id=ref['artifact_id'],detected='HASH_MISMATCH'))
    entries.append(dict(case='artifact-tamper-detection',state='PASS',error_code='HASH_MISMATCH'))

    inventory={p.relative_to(batch).as_posix():dict(sha256=sha(p.read_bytes()),size_bytes=p.stat().st_size)
        for p in batch.rglob('*') if p.is_file()}
    write(batch/'index.json',dict(completed_at=now(),status='PASS',qualification='LOCAL_DEVELOPMENT_ONLY',scientific_signoff=None,
        usable_for_pipeline=False,automatic_handoff=False,production_status='NOT_DEPLOYED',runtime_root=str(root),
        profile=policy.registered_profile(),rule_profile=policy.registered_rules(),reference=dict(total_triplets=8000,matched=38),
        independent_scan_case='independent-overlap',hotspot_contract_case='hotspot-contract',
        hotspot_full_chain_validated=False,cases=entries,files=inventory))
    print(encode(dict(status='PASS',cases=len(entries),index=str(batch/'index.json'))).decode())


if __name__=='__main__':main()
