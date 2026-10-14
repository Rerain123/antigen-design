"""New-batch N16 engineering acceptance. Never reads or processes excluded variants."""
import argparse
import shutil
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from t01_phase1_real.common import REPO,encode,sha,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.codon import policy

def body(seq='ACDEFGHIKLMNPQRSTVWY'):
    return dict(protein_sequence=seq,user_sequence_id='explicit synthetic engineering fragment; not a candidate',
        expression_host='E.coli',host_profile=policy.PROFILE,coding_policy=policy.CODING,
        input_kind='INDEPENDENT_ENGINEERING_SEQUENCE',timeout_seconds=60)

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(value if isinstance(value,bytes) else encode(value))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--batch',required=True);args=ap.parse_args()
    assert args.batch.replace('-','').isalnum()
    archive=REPO/'discovery/t01-phase1-real/w7/codon-integration-20260909'/args.batch
    root=REPO/'var/t01-phase1-real'/('codon-acceptance-20260909-'+args.batch)
    assert not archive.exists() and not root.exists(),'A new batch is required'
    archive.mkdir(parents=True);rt=Runtime(root);cases=[];guards=[]
    def record(name,j,kind):
        j=rt.get(j['job_id']);result=rt.result(j['job_id']) if j['artifacts'] else None
        write(archive/'cases'/name/'job.json',j)
        if result is not None:write(archive/'cases'/name/'result.json',result)
        write(archive/'cases'/name/'request.json',rt._request_bytes(j))
        refs=[]
        for ref in j['artifacts']:
            relative='cases/'+name+'/artifacts/'+ref['artifact_id']+'.bin'
            write(archive/relative,rt.artifact_bytes(j['job_id'],ref['artifact_id']))
            refs.append(dict(path=relative,artifact=ref))
        cases.append(dict(name=name,kind=kind,job_id=j['job_id'],state=j['state'],error_code=j['error_code'],artifacts=refs))
        print(name,j['state'],j['error_code'],flush=True)
        return j,result
    def run(name,b=None,fault=None,expected='succeeded'):
        j=rt.submit_sequence(encode(b or body()),name,policy.TOOL);rt._development_fault=fault
        rt.dispatch(j['job_id']);rt._development_fault=None
        if fault=='interrupt_after_claim':rt.recover(j['job_id'])
        j,v=record(name,j,'CONTROLLED_FAULT' if fault else 'REAL_ENGINEERING_EXECUTION')
        assert j['state']==expected,(j,v)
        return j,v
    j,v=run('aa20-real');assert v['dna']['optimized_checks']['all_constraints_pass']
    assert rt.submit_sequence(encode(body()),'aa20-real',policy.TOOL)['job_id']==j['job_id']
    guards.append(dict(name='same-byte-idempotence',passed=True))
    _,v=run('gc-remediation-real',body('AAAAAKKK'))
    assert v['dna']['initial_checks']['gc_passed'] is False and v['dna']['optimized_checks']['all_constraints_pass']
    assert v['dna']['initial_dna']!=v['dna']['optimized_dna']
    _,v=run('unsatisfiable-real',body('WWWWWW'))
    assert v['dna']['returned_kind']=='unoptimized_fallback' and v['dna']['optimizer_failure']['code']=='NO_SOLUTION'
    b=body();b.update(expression_host=None,host_profile=None);_,v=run('missing-host-skip',b)
    assert v['dna'] is None and not v['execution']['worker_started']
    for host in ('CHO','HEK293','Sf9','BHK-21','VERO','MDCK','CEF','e_coli'):
        b=body();b.update(expression_host=host,host_profile=None)
        j,_=run('unsupported-'+host.replace('_','-'),b,expected='failed');assert j['error_code']=='UNSUPPORTED_EXPRESSION_HOST'
    b=body();b['host_profile']=None;j,_=run('missing-profile',b,expected='failed');assert j['error_code']=='HOST_PROFILE_REQUIRED'
    for fault in ('compute_failure','corrupt_output','interrupt_after_claim'):
        j,_=run(fault,fault=fault,expected='failed')
        retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=j['job_id'],idempotency_key='retry-'+fault)))
        rt.dispatch(retry['job_id']);r,_=record('retry-'+fault,retry,'REAL_ENGINEERING_RETRY');assert r['state']=='succeeded'
    b=body();b['timeout_seconds']=2;run('timeout',b,'hold_worker',expected='timed_out')
    j=rt.submit_sequence(encode(body()),'active-cancel',policy.TOOL);rt._development_fault='hold_worker'
    errors=[]
    def dispatch():
        try:rt.dispatch(j['job_id'])
        except Exception as exc:errors.append(str(exc))
    t=threading.Thread(target=dispatch);t.start();deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if rt.execution(j['job_id']).get('worker_started'):break
        time.sleep(.05)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='active-cancel')))
    t.join(20);rt._development_fault=None;assert not t.is_alive() and not errors
    j,_=record('active-cancel',j,'CONTROLLED_FAULT');assert j['state']=='cancelled'
    j=rt.submit_sequence(encode(body()),'queued-cancel',policy.TOOL)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='queued-cancel')))
    j,_=record('queued-cancel',rt.dispatch(j['job_id']),'LIFECYCLE');assert j['state']=='cancelled'
    def reject(name,fn,code):
        try:fn()
        except RuntimeFault as exc:
            assert exc.code==code,(name,exc.code);guards.append(dict(name=name,passed=True,code=code));return
        raise AssertionError(name+' unexpectedly accepted')
    reject('invalid-protein',lambda:rt.submit_sequence(encode(body('ACX')),'invalid',policy.TOOL),'INVALID_REQUEST')
    reject('idempotency-conflict',lambda:rt.submit_sequence(encode(body('AAA')),'aa20-real',policy.TOOL),'IDEMPOTENCY_CONFLICT')
    # Only copies inside this new acceptance root are changed for source guards.
    original=policy.ASSETS
    for change,code in (('missing','CODON_TABLE_MISSING'),('tamper','HASH_MISMATCH'),('manifest','HASH_MISMATCH')):
        assets=root/('fixture-'+change);shutil.copytree(original,assets)
        if change=='missing':(assets/'e_coli_316407.csv').unlink()
        if change=='tamper':(assets/'e_coli_316407.csv').write_bytes(b'bad')
        if change=='manifest':(assets/'manifest.json').write_bytes(b'{}')
        policy.ASSETS=assets
        try:reject('local-table-'+change,lambda:policy.source_files(body()),code)
        finally:policy.ASSETS=original
    # Query a valid published record first, then tamper only a separate new task.
    j,_=run('publication-guard-original')
    ref=next(r for r in j['artifacts'] if r['role']=='result')
    with rt._db() as db:path=root/db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    path.write_bytes(b'{}');reject('published-tamper',lambda:rt.result(j['job_id']),'HASH_MISMATCH')
    for p in policy.HERE.glob('*.py'):write(archive/'source/codon'/p.name,p.read_bytes())
    for p in original.iterdir():write(archive/'source/assets'/p.name,p.read_bytes())
    for name in ('runtime.py','registry.py','contracts.py','cli.py'):write(archive/'source'/name,(policy.HERE.parent/name).read_bytes())
    for name in ('run_codon_acceptance.py','audit_codon_evidence.py'):write(archive/'source/scripts'/name,(REPO/'scripts'/name).read_bytes())
    write(archive/'source/test_codon_development.py',(REPO/'tests/test_codon_development.py').read_bytes())
    write(archive/'guards.json',guards)
    index=dict(batch=args.batch,runtime_root=root.relative_to(REPO).as_posix(),cases=cases,guards=guards,
        execution_profile=policy.registered_profile(),rule_profile=policy.registered_rules(),original_24_processed=False,
        qualification='DEVELOPMENT_UNREVIEWED',production_status='NOT_DEPLOYED',usable_for_pipeline=False,
        files=[dict(path=p.relative_to(archive).as_posix(),size_bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
            for p in sorted(archive.rglob('*')) if p.is_file()])
    write(archive/'index.json',index)
    print('SEALED',len(index['files']),'files',sum(len(c['artifacts']) for c in cases),'published',flush=True)

if __name__=='__main__':main()
