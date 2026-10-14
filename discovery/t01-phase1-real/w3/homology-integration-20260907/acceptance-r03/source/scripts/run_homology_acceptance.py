"""N08 real offline engineering campaign; always use new runtime and batch roots."""
import argparse
from pathlib import Path
import random
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import RuntimeFault, decode, encode, sha
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.homology import policy
from t01_phase1_real.development.homology.compute import format_fasta
from t01_phase1_real.winprocess import alive


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw = value if isinstance(value,bytes) else encode(value)
    with path.open('xb') as stream:stream.write(raw)


def make_database(root, database_id='engineering-n08', count=24, missing=False, grouped=False, length=120):
    folder = root/database_id;folder.mkdir(parents=True)
    rng = random.Random(808)
    alphabet = 'ACDEFGHIKLMNPQRSTVWY'
    query = ''.join(rng.choice(alphabet) for _ in range(length))
    seqs, annotations = {}, []
    for i in range(count+3):
        key = 'eng%04d'%i
        seq = list(query)
        if 0<i<count:
            for pos in rng.sample(range(max(0,length-40),length), min(6,length)):
                seq[pos] = rng.choice(alphabet.replace(seq[pos],''))
        seqs[key] = ''.join(seq)
        annotations.append(dict(id=key,organism_name='ENGINEERING_ORGANISM',protein_name='ENGINEERING_PROTEIN',
            source_label='wild' if i<=count else 'vaccine' if i==count+1 else 'lab',
            header='synthetic engineering sequence; source labels test routing, not biological claims',
            serotype=None,subtype=None if missing else 'engineering-'+('ABC'[i%3] if grouped else 'A'),genotype=None,
            host_species=None if missing else 'engineering-host-'+str(i%2),independent_stratum=None))
    write(folder/'sequences.fasta',format_fasta(seqs).encode())
    write(folder/'annotations.json',annotations)
    manifest = dict(schema_version='0.1.0',database_id=database_id,qualification='ENGINEERING_FIXTURE',
        purpose='N08_HOMOLOG_COLLECTION',source=dict(name='Deterministic synthetic N08 sequence collection',version='20260907',
        release_date='2026-09-07',license='Project engineering fixture',reference='scripts/run_homology_acceptance.py; random seed 808; no biological provenance claimed'),
        files=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(folder.iterdir())])
    write(folder/'manifest.json',manifest)
    body = dict(protein_sequence=query,user_sequence_id='N08 engineering only',organism_name='ENGINEERING_ORGANISM',
        protein_name='ENGINEERING_PROTEIN',database_id=database_id,database_manifest_sha256=sha(encode(manifest)),
        source_filter='wild_type',group_by='both',sequence_weighting='off',query_range=None,timeout_seconds=120)
    return body, folder


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True);p.add_argument('--batch',required=True)
    a = p.parse_args();root=Path(a.root).absolute();batch=Path(a.batch).absolute()
    assert not root.exists() and not batch.exists() and batch.is_relative_to(REPO/'discovery/t01-phase1-real/w3')
    batch.mkdir(parents=True);database_root=batch/'databases'
    body,folder = make_database(database_root)
    sparse,_ = make_database(database_root,'engineering-sparse',count=3,missing=True)
    grouped,_ = make_database(database_root,'engineering-grouped',grouped=True)
    short,_ = make_database(database_root,'engineering-short',count=3,length=9)
    identical,_ = make_database(database_root,'engineering-identical',count=1)
    runtime=Runtime(root,homology_database_root=database_root);entries=[]
    write(batch/'profile.json',policy.registered_profile());write(batch/'assets.json',policy.verify_assets())
    for path in [*policy.HERE.glob('*'),*[policy.HERE.parent/n for n in ('runtime.py','supervisor.py','docker.py','registry.py','contracts.py','cli.py')],Path(__file__)]:
        if path.is_file():write(batch/'source'/path.relative_to(REPO),path.read_bytes())

    def submit(name, request=None, fault=None, dispatch=True):
        value=request or body;write(batch/'requests'/(name+'.json'),value)
        job=runtime.submit_sequence(encode(value),name,policy.TOOL)
        runtime._development_fault=fault
        try:
            if dispatch:runtime.dispatch(job['job_id'])
        finally:runtime._development_fault=None
        return job

    def finish(name,job,state='succeeded',error=None):
        final=runtime.wait(job['job_id'],180)
        value=runtime.result(job['job_id']) if final['artifacts'] else None
        write(batch/'cases'/name/'job.json',final);write(batch/'cases'/name/'events.json',runtime.events(job['job_id']))
        if value:write(batch/'cases'/name/'result.json',value)
        for ref in final['artifacts']:
            raw=runtime.artifact_bytes(job['job_id'],ref['artifact_id'])
            assert sha(raw)==ref['sha256'] and len(raw)==ref['size_bytes']
            write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
        assert final['state']==state and final['error_code']==error,(name,final['state'],final['error_code'],value and value['execution'])
        assert not final['usable_for_pipeline'] and final['review_required']
        if value:assert not value['automatic_handoff'] and value['production_status']=='NOT_DEPLOYED'
        if final['attempt_id']:
            assert runtime.execution(job['job_id'])['tree_stopped']
            assert not docker.owned(root,final,docker.inspect(root,policy.SLOT))
        row=dict(case=name,job_id=job['job_id'],state=state,error_code=error,artifacts_verified=len(final['artifacts']))
        entries.append(row);print(encode(row).decode(),flush=True)
        return final,value

    full_job=submit('full-chain');full,result=finish('full-chain',full_job)
    assert result['analysis']['msa_alignment_count']==1 and result['analysis']['confidence']['N_eff']==24
    assert len(result['homolog_set']['vaccine_sequences'])==1
    assert result['analysis']['region_extraction']['review_reasons']==['SHORT_FRAGMENT_BRIDGE_ORDER_UNRESOLVED']
    _,reference=finish('identical-reference',submit('identical-reference',identical))
    assert reference['analysis']['region_extraction']['quality_flag']=='standard'
    assert reference['analysis']['region_extraction']['fixed_positions']==list(range(1,121))
    assert reference['analysis']['conservation']['score_per_residue']==[1.0]*120
    assert runtime.submit_sequence(encode(body),'full-chain',policy.TOOL)['job_id']==full_job['job_id']
    try:runtime.submit_sequence(encode(dict(body,user_sequence_id='changed')),'full-chain',policy.TOOL)
    except RuntimeFault as exc:assert exc.code=='IDEMPOTENCY_CONFLICT'
    else:raise AssertionError('Changed duplicate accepted')
    finish('sparse-missing-annotations',submit('sparse-missing-annotations',sparse))
    _,g=finish('independent-groups',submit('independent-groups',grouped))
    assert g['analysis']['region_extraction']['fixed_positions'] is None
    finish('short-input',submit('short-input',short))
    finish('zero-collection',submit('zero-collection',dict(body,protein_name='absent')),'failed','TOOL_FAILED')
    finish('missing-data',submit('missing-data',dict(body,database_id='absent')),'failed','ASSET_MISSING')
    finish('manifest-mismatch',submit('manifest-mismatch',dict(body,database_manifest_sha256='0'*64)),'failed','HASH_MISMATCH')
    finish('native-failure',submit('native-failure',fault='tool_failure'),'failed','TOOL_FAILED')
    finish('corrupt-output',submit('corrupt-output',fault='corrupt_output'),'failed','OUTPUT_INVALID')
    job=submit('queued-cancel',dispatch=False)
    runtime.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=job['job_id'],idempotency_key='queued-cancel-control')))
    finish('queued-cancel',job,'cancelled','CANCELLED')
    job=submit('running-cancel',fault='slow_worker')
    until=time.monotonic()+30
    while time.monotonic()<until:
        ex=runtime.execution(job['job_id'])
        if ex.get('container_started'):break
        time.sleep(.1)
    assert ex.get('container_started')
    runtime.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=job['job_id'],idempotency_key='running-cancel-control')))
    finish('running-cancel',job,'cancelled','CANCELLED')
    finish('timeout',submit('timeout',dict(body,timeout_seconds=1),fault='slow_worker'),'timed_out','TIMEOUT')
    interrupted=submit('crash-after-start',fault='crash_after_start')
    until=time.monotonic()+30
    while time.monotonic()<until:
        ex=runtime.execution(interrupted['job_id'])
        if ex.get('supervisor') and alive(ex['supervisor']) is False:break
        time.sleep(.1)
    assert ex.get('supervisor') and alive(ex['supervisor']) is False
    runtime.recover(interrupted['job_id'])
    finish('crash-after-start',interrupted,'failed','INTERRUPTED')
    retried=runtime.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=interrupted['job_id'],idempotency_key='retry-interrupted')))
    runtime.dispatch(retried['job_id']);finish('retry',retried)
    # Tamper only a dedicated copy's data, never a completed source manifest.
    corrupt,corrupt_folder=make_database(database_root,'engineering-corrupt')
    with (corrupt_folder/'sequences.fasta').open('ab') as stream:stream.write(b'\n')
    finish('data-tamper',submit('data-tamper',corrupt),'failed','HASH_MISMATCH')
    # Publication hash guard: mutate a dedicated published raw copy, record the fact.
    ref=next(r for r in full['artifacts'] if r['role']=='raw')
    with runtime._db() as db:row=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
    with (root/row['relative_path']).open('ab') as stream:stream.write(b'controlled tamper')
    try:runtime.artifact_bytes(full['job_id'],ref['artifact_id'])
    except RuntimeFault as exc:assert exc.code=='HASH_MISMATCH'
    else:raise AssertionError('Tampered publication accepted')
    write(batch/'guards.json',dict(idempotency=True,changed_duplicate_rejected=True,published_tamper_rejected=True,
        tampered_artifact_id=ref['artifact_id'],qualification='ENGINEERING_FIXTURE',target_database_validated=False))
    inventory=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
               for p in sorted(batch.rglob('*')) if p.is_file()]
    write(batch/'index.json',dict(status='PASS',scope='N08_LOCAL_ENGINEERING',cases=entries,files=inventory,
        usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,production_status='NOT_DEPLOYED',
        target_database_validated=False,engineering_data=True))
    print('N08_ENGINEERING_ACCEPTANCE_PASS',flush=True)


if __name__=='__main__':main()
