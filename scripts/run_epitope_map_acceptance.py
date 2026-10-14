"""Reproducible N06 map and N06-to-N07 local development campaign; not scientific signoff."""
import argparse
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import RuntimeFault, decode, encode, now, sha
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.bepipred import policy as bepipred
from t01_phase1_real.development.blast import policy as blast
from t01_phase1_real.development.epitope_map import policy as epitope_map
from t01_phase1_real.development.glycosylation import policy as glycosylation
from t01_phase1_real.development.netmhc import policy as netmhc

SEQ='MRYGFVRKKHRGLFLTTVAALPIWNPISEFVKWYKSHKLSQHCIRICGHLCQKHLDMFLSVIGQRWPIDVFSSVFDHQVSAIGSDIIWWFLKLFLVSFFFFF'
I_ALLELE='HLA-A02:01'
II_ALLELE='HLA-DPA10202-DPB11901'


def write(path,value):
    raw=value if isinstance(value,bytes) else encode(value)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--batch',required=True)
    args=parser.parse_args();root=Path(args.root).absolute();batch=Path(args.batch).absolute()
    assert root.is_absolute() and not root.exists(),'Use a fresh absolute runtime root'
    assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w2') and not batch.exists(),'Use a fresh W2 evidence batch'
    batch.mkdir(parents=True);database_root=batch/'databases';database_root.mkdir()
    rt=Runtime(root,blast_database_root=database_root);entries=[];profile=epitope_map.registered_profile()

    sources=[*sorted((REPO/'src/t01_phase1_real/development/epitope_map').glob('*.py')),
        REPO/'src/t01_phase1_real/development/glycosylation/policy.py',
        REPO/'src/t01_phase1_real/development/glycosylation/result.py',
        REPO/'src/t01_phase1_real/development/runtime.py',REPO/'src/t01_phase1_real/development/registry.py',
        REPO/'src/t01_phase1_real/development/contracts.py',REPO/'src/t01_phase1_real/development/cli.py',
        REPO/'src/t01_phase1_real/development/blast/policy.py',REPO/'src/t01_phase1_real/development/blast/result.py',
        REPO/'scripts/t01_runtime.py',REPO/'scripts/run_epitope_map_acceptance.py',
        REPO/'tests/test_epitope_map_development.py',REPO/'tests/test_glycosylation_development.py']
    for path in sources:write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    write(batch/'profile.json',profile);write(batch/'rule-profile.json',epitope_map.registered_rules())
    write(batch/'authority.json',[dict(path=path.relative_to(REPO).as_posix(),sha256=sha(path.read_bytes()),size_bytes=path.stat().st_size)
        for path in epitope_map.AUTHORITY])
    bepi_image=docker.call(root,['image','inspect','--format','{{.Id}} {{.Architecture}} {{.Os}}',bepipred.IMAGE])
    net_image=docker.call(root,['image','inspect','--format','{{.Id}} {{.Architecture}} {{.Os}}',netmhc.IMAGE])
    blast_image=docker.call(root,['image','inspect','--format','{{.Id}} {{.Architecture}} {{.Os}}',blast.IMAGE])
    assert bepi_image.returncode==net_image.returncode==blast_image.returncode==0
    assert bepi_image.stdout.decode().strip()==bepipred.IMAGE+' amd64 linux'
    assert net_image.stdout.decode().strip()==netmhc.IMAGE+' amd64 linux'
    assert blast_image.stdout.decode().strip()==blast.IMAGE+' amd64 linux'
    write(batch/'environment.json',dict(bepipred_image=bepi_image.stdout.decode().strip(),
        netmhc_image=net_image.stdout.decode().strip(),blast_image=blast_image.stdout.decode().strip(),
        native_inference_network='none',blast_database_qualification='ENGINEERING_FIXTURE'))

    def build_database(database_id,fasta,sequence_count):
        folder=database_root/database_id;folder.mkdir();write(folder/'source.fasta',fasta)
        argv=docker.client(root)+['run','--rm','--network','none','--mount',f'type=bind,source={folder},target=/db',
            blast.asset_receipt()['image_reference'],'makeblastdb','-in','/db/source.fasta','-dbtype','prot','-parse_seqids',
            '-blastdb_version','5','-out','/db/engineering','-title','t01-n03-n06-'+database_id]
        run=subprocess.run(argv,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch/'build'/(database_id+'-makeblastdb.json'),dict(argv=argv,exit_code=run.returncode,
            stdout=run.stdout.decode('utf-8'),stderr=run.stderr.decode('utf-8')))
        assert run.returncode==0,(database_id,run.stdout,run.stderr)
        files=[]
        for path in sorted(folder.iterdir()):
            if path.is_file():
                raw=path.read_bytes();files.append(dict(path=path.name,
                    role='source_fasta' if path.name=='source.fasta' else 'index',bytes=len(raw),sha256=sha(raw)))
        manifest=dict(schema_version='0.1.0',database_id=database_id,qualification='ENGINEERING_FIXTURE',
            purpose='N03-to-N06 artifact-chain engineering only; not a target or literature database',created_at=now(),
            source=dict(name='T-01 N03-to-N06 generated engineering FASTA',version='2026-09-08',
                release_date='2026-09-08',license='project engineering fixture',reference='run_epitope_map_acceptance.py'),
            blast=dict(db_prefix='engineering',dbtype='prot',blastdb_version=5,title='t01-n03-n06-'+database_id,
                sequence_count=sequence_count,makeblastdb_version='makeblastdb: 2.17.0+',builder_identity=blast.IMAGE),files=files)
        raw=encode(manifest);write(folder/'manifest.json',raw);return sha(raw)

    hit_manifest=build_database('engineering-n03-n06-hit',
        ('>exact_n06_sequence\n'+SEQ+'\n>decoy\n'+'P'*len(SEQ)+'\n').encode(),2)
    no_hit_manifest=build_database('engineering-n03-n06-nohit',
        ('>unrelated_poly_proline\n'+'P'*len(SEQ)+'\n').encode(),1)

    def cli(name,argv,expected=0,timeout=420):
        command=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),
            '--blast-database-root',str(database_root),*argv]
        run=subprocess.run(command,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        write(batch/'cli'/(name+'.json'),dict(argv=command,exit_code=run.returncode,
            stdout=run.stdout.decode('utf-8'),stderr=run.stderr.decode('utf-8')))
        assert run.returncode==expected,(name,run.returncode,run.stdout[:1000],run.stderr[:1000])
        return decode(run.stdout)

    def record(name,job,state='succeeded',error=None,status=None):
        final=rt.get(job['job_id']);assert final['state']==state and final['error_code']==error,(name,final['state'],final['error_code'])
        write(batch/'cases'/name/'job.json',final);write(batch/'cases'/name/'events.json',rt.events(final['job_id']))
        if final['attempt_id']:write(batch/'cases'/name/'execution.json',rt.execution(final['job_id']))
        value=None;verified=0
        if final['artifacts']:
            value=rt.result(final['job_id']);write(batch/'cases'/name/'result.json',value)
            assert not value['usable_for_pipeline'] and not value['automatic_handoff'] and value['production_status']=='NOT_DEPLOYED'
            if status:assert value['status']==status,(name,value['status'])
            for ref in final['artifacts']:
                raw=rt.artifact_bytes(final['job_id'],ref['artifact_id'])
                assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256'];verified+=1
                write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
        entries.append(dict(case=name,job_id=final['job_id'],state=state,error_code=error,
            result_status=value and value['status'],artifacts_verified=verified))
        print(encode(entries[-1]).decode(),flush=True)
        return final,value

    def n06_request(bepi_job=None,net_job=None,blast_job=None,sequence=SEQ,alias='n06'):
        return dict(protein_sequence=sequence,user_sequence_id=alias,
            bepipred_input=rt.source_input(bepi_job,bepipred.TOOL) if bepi_job else dict(state='not_provided',artifact=None,reason_code=None),
            netmhc_input=rt.source_input(net_job,netmhc.TOOL) if net_job else dict(state='not_provided',artifact=None,reason_code=None),
            blast_input=rt.source_input(blast_job,blast.TOOL) if blast_job else dict(
                state='not_executed',artifact=None,reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'),timeout_seconds=5)

    def blast_request(database_id,manifest,alias):
        path=batch/'requests'/(alias+'.json')
        write(path,dict(protein_sequence=SEQ,user_sequence_id=alias,database_id=database_id,
            database_manifest_sha256=manifest,thresholds=dict(identity_percent_min=70.0,
                query_coverage_percent_min=80.0),timeout_seconds=60))
        return path

    blast_hit_value=cli('real-blast-hit',['blast','--input',str(blast_request('engineering-n03-n06-hit',
        hit_manifest,'real-blast-hit')),'--key','real-blast-hit','--run','--wait','120'])
    blast_hit_job=blast_hit_value['job'];_,blast_hit_result=record('real-blast-hit',blast_hit_job,
        status='similarity_hits_unreviewed')
    assert blast_hit_result['search']['search_status']=='hit' and blast_hit_result['search']['qualifying_hsp_count']>=1
    assert blast_hit_result['database']['qualification']=='ENGINEERING_FIXTURE' and blast_hit_result['search']['iedb_hit'] is None

    blast_no_hit_value=cli('real-blast-no-hit',['blast','--input',str(blast_request('engineering-n03-n06-nohit',
        no_hit_manifest,'real-blast-no-hit')),'--key','real-blast-no-hit','--run','--wait','120'])
    blast_no_hit_job=blast_no_hit_value['job'];_,blast_no_hit_result=record('real-blast-no-hit',blast_no_hit_job,
        status='no_qualifying_similarity_hit')
    assert blast_no_hit_result['search']['search_status']=='no_hit' and blast_no_hit_result['search']['qualifying_hsp_count']==0

    failed_blast_path=blast_request('missing-engineering-n03-n06','0'*64,'failed-blast-source')
    failed_blast_value=cli('failed-blast-source',['blast','--input',str(failed_blast_path),'--key','failed-blast-source',
        '--run','--wait','120'])
    failed_blast_job=failed_blast_value['job'];record('failed-blast-source',failed_blast_job,'failed','ASSET_MISSING','unreliable')

    # One true native run of each upstream tool supplies the actual N06 development chain.
    bepi_value=cli('real-bepipred',['bepipred','--sequence',SEQ,'--user-id','n06-real-bepipred','--timeout','180',
        '--key','real-bepipred','--run','--wait','240'])
    bepi_job=bepi_value['job'];record('real-bepipred',bepi_job,status='raw_scores_unreviewed')
    net_value=cli('real-netmhc',['netmhc','--sequence',SEQ,'--user-id','n06-real-netmhc','--host','Homo sapiens',
        '--mhc-i-allele',I_ALLELE,'--mhc-ii-allele',II_ALLELE,'--timeout','180','--key','real-netmhc','--run','--wait','240'])
    net_job=net_value['job'];record('real-netmhc',net_job,status='raw_predictions_unreviewed')

    normal_value=cli('documented-n06',['epitope-map','--sequence',SEQ,'--user-id','n06-real-chain',
        '--blast-job-id',blast_hit_job['job_id'],'--bepipred-job-id',bepi_job['job_id'],
        '--netmhc-job-id',net_job['job_id'],'--key','normal-n06','--run'])
    normal,normal_result=record('normal-real-chain',normal_value['job'],status='maps_unreviewed')
    tmap=normal_result['epitopes']['t_cell_presentation_map']
    assert tmap['mhc_i_hits'] and tmap['mhc_ii_hits'] and len(tmap['residue_min_percent_rank'])==len(SEQ)
    assert normal_result['epitopes']['b_cell_epitope_map']['regions'] is None
    hotspot_map=normal_result['epitopes']['b_cell_antigenic_hotspot_map']
    assert hotspot_map['status']=='computed_empty_unreviewed' and hotspot_map['hotspots']==[]
    assert hotspot_map['proof']['maximum_possible_score']==.35
    assert normal_result['epitopes']['density_per_residue'] is None
    blast_fact=normal_result['blast_similarity']
    assert blast_fact['state']=='available' and blast_fact['search_status']=='hit' and blast_fact['qualifying_hsp_count']>=1
    assert blast_fact['database']['qualification']=='ENGINEERING_FIXTURE'
    assert blast_fact['iedb_evidence'] is blast_fact['epitope_evidence_level'] is blast_fact['epitope_regions'] is None
    assert normal_result['method_summary']['blast_source_bound'] and not normal_result['method_summary']['iedb_evidence_generated']
    blast_receipt=normal_result['execution']['source_receipts']['blast']
    assert blast_receipt['database_id']=='engineering-n03-n06-hit' and blast_receipt['database_manifest_sha256']==hit_manifest

    duplicate=cli('normal-duplicate',['epitope-map','--sequence',SEQ,'--user-id','n06-real-chain',
        '--blast-job-id',blast_hit_job['job_id'],'--bepipred-job-id',bepi_job['job_id'],
        '--netmhc-job-id',net_job['job_id'],'--key','normal-n06','--run'])
    assert duplicate['job']['job_id']==normal['job_id'] and duplicate['job']['attempt_id']==normal['attempt_id']
    conflict=n06_request(bepi_job['job_id'],net_job['job_id'],blast_hit_job['job_id'],alias='changed-alias');conflict_path=batch/'requests/conflict.json';write(conflict_path,conflict)
    assert cli('normal-conflict',['epitope-map','--input',str(conflict_path),'--key','normal-n06'],20)['error']['code']=='IDEMPOTENCY_CONFLICT'
    entries.append(dict(case='idempotency-duplicate-conflict',state='PASS',same_attempt=True))

    no_hit_value=cli('n06-real-blast-no-hit',['epitope-map','--sequence',SEQ,'--user-id','n06-real-blast-no-hit',
        '--blast-job-id',blast_no_hit_job['job_id'],'--bepipred-job-id',bepi_job['job_id'],
        '--netmhc-job-id',net_job['job_id'],'--key','n06-real-blast-no-hit','--run'])
    _,no_hit_result=record('n06-real-blast-no-hit',no_hit_value['job'],status='maps_unreviewed')
    assert no_hit_result['blast_similarity']['state']=='available'
    assert no_hit_result['blast_similarity']['search_status']=='no_hit'
    assert no_hit_result['blast_similarity']['raw_hsp_count']==no_hit_result['blast_similarity']['qualifying_hsp_count']==0

    unavailable_blast_value=cli('n06-failed-blast-source',['epitope-map','--sequence',SEQ,
        '--user-id','n06-failed-blast-source','--blast-job-id',failed_blast_job['job_id'],
        '--bepipred-job-id',bepi_job['job_id'],'--netmhc-job-id',net_job['job_id'],
        '--key','n06-failed-blast-source','--run'])
    _,unavailable_blast_result=record('n06-failed-blast-source',unavailable_blast_value['job'],status='maps_unreviewed')
    assert unavailable_blast_result['blast_similarity']['state']=='upstream_unavailable'
    assert unavailable_blast_result['blast_similarity']['reason_code']=='ASSET_MISSING'

    n07_value=cli('documented-n07-source',['glycosylation','--sequence',SEQ,'--user-id','n07-from-n06',
        '--n06-job-id',normal['job_id'],'--key','n07-real-source','--run'])
    _,n07_result=record('n07-real-source',n07_value['job'],status='completed_empty')
    assert n07_result['hotspot_assessment']['source_verification']=='VERIFIED_N06_ARTIFACT_REF'
    assert n07_result['hotspot_assessment']['status']=='EVALUATED'
    assert n07_result['hotspot_assessment']['source_hotspot_status']=='computed_empty_unreviewed'
    assert n07_result['method_summary']['hotspot_source_artifact_validated'] is True
    assert n07_result['method_summary']['hotspot_full_chain_validated'] is True
    assert n07_result['method_summary']['hotspot_scientific_consumption'] is False

    partial_value=cli('partial-net-only',['epitope-map','--sequence',SEQ,'--user-id','net-only',
        '--netmhc-job-id',net_job['job_id'],'--key','partial-net-only','--run'])
    _,partial=record('partial-net-only',partial_value['job'],status='partial_maps_unreviewed')
    assert partial['epitopes']['b_cell_epitope_map'] is None and partial['epitopes']['t_cell_presentation_map'] is not None

    failed_bepi_raw=encode(dict(protein_sequence=SEQ,user_sequence_id='failed-bepi',timeout_seconds=180))
    failed_bepi=rt.submit_sequence(failed_bepi_raw,'failed-bepi',bepipred.TOOL);rt._development_fault='tool_failure'
    try:rt.dispatch(failed_bepi['job_id'])
    finally:rt._development_fault=None
    failed_bepi=rt.wait(failed_bepi['job_id'],240);record('failed-bepipred-source',failed_bepi,'failed','TOOL_FAILED','unreliable')
    unavailable_raw=encode(n06_request(failed_bepi['job_id'],alias='upstream-unavailable'))
    unavailable=rt.submit_sequence(unavailable_raw,'upstream-unavailable',epitope_map.TOOL);rt.dispatch(unavailable['job_id'])
    _,unavailable_result=record('all-inputs-unavailable',unavailable,'failed','TOOL_FAILED','unreliable')
    assert unavailable_result['epitopes'] is None

    mismatch='A'*len(SEQ)
    assert cli('sequence-mismatch',['epitope-map','--sequence',mismatch,'--bepipred-job-id',bepi_job['job_id'],
        '--netmhc-job-id',net_job['job_id'],'--key','sequence-mismatch'],20)['error']['code']=='OUTPUT_INVALID'
    entries.append(dict(case='sequence-mismatch',state='PASS',rejected_before_admission=True))
    assert cli('blast-sequence-mismatch',['epitope-map','--sequence',mismatch,
        '--blast-job-id',blast_hit_job['job_id'],'--key','blast-sequence-mismatch'],20)['error']['code']=='OUTPUT_INVALID'
    entries.append(dict(case='blast-sequence-mismatch',state='PASS',rejected_before_admission=True))

    # Lifecycle cases use the same already-verified real source artifacts; N06 itself is local and bounded.
    queued=cli('queued-submit',['epitope-map','--sequence',SEQ,'--bepipred-job-id',bepi_job['job_id'],
        '--netmhc-job-id',net_job['job_id'],'--key','queued'])
    cancelled=cli('queued-cancel',['cancel','--job-id',queued['job_id'],'--key','queued-cancel']);record('queued-cancel',cancelled,'cancelled','CANCELLED')
    retried=cli('cancel-retry',['retry','--job-id',queued['job_id'],'--key','cancel-retry']);rt.dispatch(retried['job_id'])
    record('cancel-retry',retried,status='maps_unreviewed')

    def fault_case(name,fault,state='failed',error=None):
        raw=encode(n06_request(bepi_job['job_id'],net_job['job_id'],alias=name))
        job=rt.submit_sequence(raw,name,epitope_map.TOOL);rt._development_fault=fault
        try:rt.dispatch(job['job_id'])
        finally:rt._development_fault=None
        if fault=='interrupt_after_claim':
            assert rt.get(job['job_id'])['state']=='running';rt.reconcile(job['job_id']);error='INTERRUPTED'
        return record(name,job,state,error,'unreliable')

    fault_case('compute-failure','compute_failure',error='TOOL_FAILED')
    fault_case('corrupt-output','corrupt_output',error='OUTPUT_INVALID')
    fault_case('interrupted-recovery','interrupt_after_claim',error='INTERRUPTED')

    replacement=rt.source_input(net_job['job_id'],netmhc.TOOL)['artifact']
    replaced=dict(protein_sequence=SEQ,user_sequence_id='foreign-source',timeout_seconds=5,
        hotspot_input=dict(state='upstream_unavailable',hotspots=None,
            source=dict(kind='artifact_ref',node_id='N06',artifact=replacement),reason_code='N06_HOTSPOTS_REVIEW_REQUIRED'))
    replaced_path=batch/'requests/foreign-n06-artifact.json';write(replaced_path,replaced)
    assert cli('foreign-n06-artifact',['glycosylation','--input',str(replaced_path),'--key','foreign-n06-artifact'],20)['error']['code']=='FORBIDDEN'
    entries.append(dict(case='foreign-n06-artifact',state='PASS',rejected_before_admission=True))

    # Re-verification must detect damage that occurs after admission but before dispatch.
    tamper_n06=rt.submit_sequence(encode(n06_request(bepi_job['job_id'],net_job['job_id'],alias='tamper-upstream')),
        'tamper-upstream',epitope_map.TOOL)
    bepi_ref=next(row for row in bepi_job['artifacts'] if row['role']=='result')
    with rt._db() as db:bepi_path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(bepi_ref['artifact_id'],)).fetchone()[0]
    original=(root/bepi_path).read_bytes();write(batch/'controlled-damage/bepipred-result-original.bin',original)
    (root/bepi_path).write_bytes(original+b' controlled-damage')
    damaged=rt.dispatch(tamper_n06['job_id']);record('n06-upstream-hash-damage',damaged,'failed','HASH_MISMATCH')

    n07_hotspot=rt.n06_hotspot_input(normal['job_id'],SEQ)
    queued_n07=rt.submit_sequence(encode(dict(protein_sequence=SEQ,user_sequence_id='n07-tamper',
        hotspot_input=n07_hotspot,timeout_seconds=5)),'n07-tamper',glycosylation.TOOL)
    n06_ref=next(row for row in normal['artifacts'] if row['role']=='result')
    with rt._db() as db:n06_path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(n06_ref['artifact_id'],)).fetchone()[0]
    original=(root/n06_path).read_bytes();write(batch/'controlled-damage/n06-result-original.bin',original)
    (root/n06_path).write_bytes(original+b' controlled-damage')
    damaged=rt.dispatch(queued_n07['job_id']);record('n07-source-hash-damage',damaged,'failed','HASH_MISMATCH')

    tamper_blast=rt.submit_sequence(encode(n06_request(None,net_job['job_id'],blast_hit_job['job_id'],
        alias='tamper-blast-upstream')),'tamper-blast-upstream',epitope_map.TOOL)
    blast_ref=next(row for row in blast_hit_job['artifacts'] if row['role']=='result')
    with rt._db() as db:blast_path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(blast_ref['artifact_id'],)).fetchone()[0]
    original=(root/blast_path).read_bytes();write(batch/'controlled-damage/blast-result-original.bin',original)
    (root/blast_path).write_bytes(original+b' controlled-damage')
    damaged=rt.dispatch(tamper_blast['job_id']);record('n06-blast-source-hash-damage',damaged,'failed','HASH_MISMATCH')

    assert profile==epitope_map.registered_profile()
    inventory={path.relative_to(batch).as_posix():dict(sha256=sha(path.read_bytes()),size_bytes=path.stat().st_size)
        for path in batch.rglob('*') if path.is_file()}
    write(batch/'index.json',dict(completed_at=now(),status='PASS',qualification='LOCAL_DEVELOPMENT_ONLY',
        scientific_signoff=None,usable_for_pipeline=False,automatic_handoff=False,production_status='NOT_DEPLOYED',
        runtime_root=str(root),profile=profile,rule_profile=epitope_map.registered_rules(),
        real_upstream_jobs=dict(blast_hit=blast_hit_job['job_id'],blast_no_hit=blast_no_hit_job['job_id'],
            blast_unavailable=failed_blast_job['job_id'],bepipred=bepi_job['job_id'],netmhc=net_job['job_id']),
        n03_to_n06_reconnected=True,blast_similarity_only=True,iedb_evidence_generated=False,e3_e4_evidence_generated=False,
        normal_n06_job_id=normal['job_id'],n06_empty_hotspot_bound=True,
        n07_source_artifact_validated=True,n07_hotspot_full_chain_validated=True,
        unresolved=['OI-007_EVIDENCE_WEIGHTS','OI-026_BEPIPRED_POSTPROCESSING','OI-028_BLAST_TARGET_DATABASE',
            'OI-029_HOTSPOT_WINDOW_CONVERSION'],cases=entries,files=inventory))
    print(encode(dict(status='PASS',cases=len(entries),index=str(batch/'index.json'))).decode(),flush=True)


if __name__=='__main__':main()
