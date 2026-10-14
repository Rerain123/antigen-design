"""N09 real local annotation, topology and structure integration campaign."""
import argparse
import copy
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import RuntimeFault,encode,decode,sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.domains import policy
from structure_integration_cases import cases as structure_cases, geometry as structure_rows, cif, metadata

SEQ='MRYGFVRKKHRGLFLTTVAALPIWNPISEFVKWYKSHKLSQHCIRICGHLCQKHLDMFLSVIGQRWPIDVFSSVFDHQVSAIGSDIIWWFLKLFLVSFFFFF'
ABSENT=dict(state='not_provided',artifact=None,reason_code=None)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(value if isinstance(value,bytes) else encode(value))


def feature(kind,a,b,description='engineering annotation'):
    return dict(type=kind,description=description,location=dict(start=dict(value=a,modifier='EXACT'),end=dict(value=b,modifier='EXACT')))


def entry(seq=SEQ,accession='ENGINEERING_N09',features=None,spaces=None):
    features=features if features is not None else [feature('Domain',1,10),feature('Other',15,25,'CAPSID assembly'),feature('Chain',1,len(seq))]
    return dict(primaryAccession=accession,entryType='UniProtKB reviewed (Swiss-Prot)',organism=dict(scientificName='ENGINEERING_ORGANISM'),
        sequence=dict(value=seq),features=features,coordinate_spaces=spaces or ['mature']*len(features))


def database(root,items=None,name='engineering-n09'):
    folder=root/name;folder.mkdir(parents=True)
    raw=encode(items if items is not None else [entry()]);write(folder/'entries.json',raw)
    manifest=dict(schema_version='0.1.0',database_id=name,qualification='ENGINEERING_FIXTURE',purpose='N09_LOCAL_ANNOTATIONS',
        source=dict(name='Synthetic local UniProt-shaped annotations',version='20260907',release_date='2026-09-07',
            license='Project engineering fixture',reference='scripts/run_domains_acceptance.py; reviewed flag tests routing only'),
        files=[dict(path='entries.json',bytes=len(raw),sha256=sha(raw))])
    write(folder/'manifest.json',manifest)
    return dict(protein_sequence=SEQ,user_sequence_id='N09 engineering',organism_name='ENGINEERING_ORGANISM',database_id=name,
        database_manifest_sha256=sha(encode(manifest)),entry_id=None,parent=None,topology_input=copy.deepcopy(ABSENT),
        structure_input=copy.deepcopy(ABSENT),user_annotations=[],timeout_seconds=60),folder


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True);parser.add_argument('--batch',required=True)
    a=parser.parse_args();root=Path(a.root).absolute();batch=Path(a.batch).absolute()
    assert not root.exists() and not batch.exists() and batch.is_relative_to(REPO/'discovery/t01-phase1-real/w3')
    batch.mkdir(parents=True);body,folder=database(batch/'databases')
    rt=Runtime(root,domains_database_root=batch/'databases');results=[]
    write(batch/'profile.json',policy.registered_profile());write(batch/'rules.json',policy.registered_rules())
    for path in [*policy.HERE.glob('*.py'),*[policy.HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py')],Path(__file__),REPO/'tests/test_domains_development.py']:
        if path.is_file():write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    def record(name,job,state='succeeded',error=None):
        job=rt.wait(job['job_id'],900);write(batch/'cases'/name/'job.json',job)
        write(batch/'cases'/name/'events.json',rt.events(job['job_id']))
        value=rt.result(job['job_id']) if job['artifacts'] else None
        if value:write(batch/'cases'/name/'result.json',value)
        for ref in job['artifacts']:
            raw=rt.artifact_bytes(job['job_id'],ref['artifact_id'])
            assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256'];write(batch/'cases'/name/'artifacts'/ref['artifact_id'],raw)
        assert job['state']==state and job['error_code']==error,(name,job['state'],job['error_code'],value and value['execution'])
        assert not job['usable_for_pipeline']
        if value:assert not value['automatic_handoff'] and value['production_status']=='NOT_DEPLOYED'
        row=dict(case=name,job_id=job['job_id'],state=state,error_code=error,artifacts_verified=len(job['artifacts']))
        results.append(row);print(encode(row).decode(),flush=True);return job,value
    def run(name,request=None,fault=None,state='succeeded',error=None):
        request=request or body;write(batch/'requests'/(name+'.json'),request)
        job=rt.submit_sequence(encode(request),name,policy.TOOL);rt._development_fault=fault
        try:rt.dispatch(job['job_id'])
        finally:rt._development_fault=None
        return record(name,job,state,error)
    def source(job):
        return dict(state='available',artifact=next(r for r in job['artifacts'] if r['role']=='result'),reason_code=None)

    # Actual model execution in the same registered store, no canned topology.
    top=rt.submit_sequence(encode(dict(protein_sequence=SEQ,user_sequence_id='N09-real-topology',timeout_seconds=900)),'deep-topology')
    rt.dispatch(top['job_id']);top,top_value=record('real-deeptmhmm',top)
    assert top_value['topology'] is not None
    linked=dict(body,topology_input=source(top),user_annotations=[dict(type='user_function',start=30,end=35,note='engineering user constraint')])
    main_job,main_value=run('annotated-real-topology',linked)
    assert main_value['analysis']['topology_status']=='verified_available'
    assert any(d['source']=='user_annotation' for d in main_value['analysis']['functional_domains'])
    assert main_value['database']['qualification']=='ENGINEERING_FIXTURE'
    run('no-topology',body)
    empty,_=database(batch/'databases',[entry(features=[])],'empty-features');run('empty-features',empty)
    nohit,_=database(batch/'databases',[],'no-hit');run('no-hit',nohit)
    motif,_=database(batch/'databases',[entry(seq='AKKRKARRKRRLPATGRGDDQEANPGP',features=[])],'motif')
    motif['protein_sequence']='AKKRKARRKRRLPATGRGDDQEANPGP'
    _,v=run('independent-motifs',motif);assert len(v['analysis']['motif_observations'])>=5
    user=dict(entry());user['entryType']='UniProtKB unreviewed (TrEMBL)'
    unreviewed,_=database(batch/'databases',[user],'unreviewed');_,v=run('unreviewed',unreviewed)
    assert 'UNREVIEWED_CONFIDENCE_DOWNGRADE_UNRESOLVED' in v['analysis']['review_reasons']
    multiple,_=database(batch/'databases',[entry(),entry(accession='SECOND')],'multiple');run('multiple',multiple)
    run('explicit-mismatch',dict(body,protein_sequence='A'*len(SEQ),entry_id='ENGINEERING_N09'))
    parent_seq='AAAA'+SEQ+'AAAA'
    poly,_=database(batch/'databases',[entry(seq=parent_seq,features=[feature('Domain',1,8),feature('Chain',1,len(SEQ)),feature('Region',len(parent_seq)-6,len(parent_seq))],spaces=['parent','mature','parent'])],'parent')
    poly['parent']=dict(id='engineering-parent',offset=5,sequence=parent_seq)
    _,v=run('parent-clipping-chain',poly)
    chain=next(x for x in v['analysis']['functional_domains'] if x['type']=='mature_chain')
    assert chain['start']==1 and chain['end']==len(SEQ) and chain['source']=='uniprot'
    # Reuse established structure fixtures through the real structure worker.
    originals=structure_cases()
    structural_cases=[next(c for c in originals if c['name']==name) for name in ('normal-cif','quality-unknown-source','rsa-out-of-domain')]
    rows=structure_rows()
    for row in rows:
        if int(row['label_seq_id'])<=2:row.update(label_comp_id='CYS',auth_comp_id='CYS')
    other=[dict(r,auth_asym_id='B',label_asym_id='LABEL_B',Cartn_y=str(float(r['Cartn_y'])+2.5)) for r in rows]
    structural_cases.append(dict(name='synthetic-cys-interface',data=cif(rows+other),
        request=metadata(sequence='CCDEQLIVF',source='unknown',context=['A','B'],selection=dict(model_index=0,chain_selector='A'))))
    for case in structural_cases:
        case_name=case['name']
        sj=rt.submit_structure(encode(case['request']),case_name,case['data']);rt.dispatch(sj['job_id'])
        sj,_=record('structure-'+case_name,sj)
        sb,_=database(batch/'databases',[entry(seq=case['request']['protein_sequence'],features=[])],'struct-'+case_name)
        sb.update(protein_sequence=case['request']['protein_sequence'],structure_input=source(sj))
        _,sv=run('geometry-'+case_name,sb)
        assert sv['analysis']['core_map'] is None
        if case_name!='normal-cif':
            assert all(c['burial_score'] is None for c in sv['analysis']['structure_assessment'].get('components',[]))
        if case_name=='synthetic-cys-interface':
            assert sv['analysis']['structure_assessment']['disulfide_pairs']
            assert sv['analysis']['structure_assessment']['interface_positions']
    run('missing-db',dict(body,database_id='missing'),state='failed',error='ASSET_MISSING')
    run('wrong-manifest',dict(body,database_manifest_sha256='0'*64),state='failed',error='HASH_MISMATCH')
    run('compute-failure',fault='compute_failure',state='failed',error='TOOL_FAILED')
    run('corrupt-output',fault='corrupt_output',state='failed',error='OUTPUT_INVALID')
    queued=rt.submit_sequence(encode(body),'queued-cancel',policy.TOOL)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=queued['job_id'],idempotency_key='cancel')))
    record('queued-cancel',queued,'cancelled','CANCELLED')
    job=rt.submit_sequence(encode(body),'interrupted',policy.TOOL);rt._development_fault='interrupt_after_claim'
    try:rt.dispatch(job['job_id'])
    finally:rt._development_fault=None
    rt.recover(job['job_id']);record('interrupted',job,'failed','INTERRUPTED')
    retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=job['job_id'],idempotency_key='retry')))
    rt.dispatch(retry['job_id']);record('retry',retry)
    assert rt.submit_sequence(encode(linked),'annotated-real-topology',policy.TOOL)['job_id']==main_job['job_id']
    try:rt.submit_sequence(encode(dict(linked,user_sequence_id='changed')),'annotated-real-topology',policy.TOOL)
    except RuntimeFault as exc:assert exc.code=='IDEMPOTENCY_CONFLICT'
    else:raise AssertionError('Changed duplicate accepted')
    write(batch/'requests/documented.json',linked)
    argv=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),'--domains-database-root',str(batch/'databases'),
        'domains','--input',str(batch/'requests/documented.json'),'--key','documented','--run']
    cmd=subprocess.run(argv,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    write(batch/'documented-command.json',dict(argv=argv,exit_code=cmd.returncode,stdout=cmd.stdout.decode(),stderr=cmd.stderr.decode()))
    assert cmd.returncode==0;record('documented',decode(cmd.stdout)['job'])
    bad=copy.deepcopy(linked);bad['topology_input']['artifact']['sha256']='0'*64
    try:rt.submit_sequence(encode(bad),'fake-source',policy.TOOL)
    except RuntimeFault:pass
    else:raise AssertionError('Fake upstream accepted')
    pending=rt.submit_sequence(encode(linked),'late-topology-tamper',policy.TOOL)
    ref=linked['topology_input']['artifact']
    with rt._db() as db:row=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
    with (root/row['relative_path']).open('ab') as stream:stream.write(b'controlled test tamper')
    rt.dispatch(pending['job_id']);record('late-topology-tamper',pending,'failed','HASH_MISMATCH')
    damaged,df=database(batch/'databases',name='data-tamper')
    with (df/'entries.json').open('ab') as stream:stream.write(b' ')
    run('data-tamper',damaged,state='failed',error='HASH_MISMATCH')
    write(batch/'guards.json',dict(changed_duplicate_rejected=True,forged_source_rejected=True,late_topology_tamper_rejected=True,
        original_engineering_source_preserved_in_batch=True,scientific_consumption=False,target_database_validated=False))
    files=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(batch.rglob('*')) if p.is_file()]
    write(batch/'index.json',dict(status='PASS',scope='N09_LOCAL_ENGINEERING',cases=results,files=files,
        target_database_validated=False,scientific_signoff=None,usable_for_pipeline=False,production_status='NOT_DEPLOYED'))
    print('N09_ENGINEERING_ACCEPTANCE_PASS',flush=True)


if __name__=='__main__':main()
