"""Fresh local copy of verified prior N11/N12 plus new source-backed S27/S28 audit cases."""
import argparse
import copy
from pathlib import Path
import shutil
import subprocess
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import encode,decode,sha,RuntimeFault,now
from t01_phase1_real.development import Runtime,docker
from t01_phase1_real.development.design_backend import policy,service
from t01_phase1_real.development.proteinmpnn import policy as mpnn
from t01_phase1_real.development.proteinmpnn.source import sources as prepare_mpnn
from t01_phase1_real.development.domains import policy as n09
from t01_phase1_real.development.homology import policy as n08
from t01_phase1_real.development.glycosylation import policy as n07
from t01_phase1_real.development.epitope_map import policy as n06
from run_domains_acceptance import database,entry,feature,ABSENT,write
from run_homology_acceptance import make_database


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--batch',required=True)
    args=p.parse_args();root=Path(args.root).absolute();batch=Path(args.batch).absolute()
    assert root.is_relative_to(REPO/'var/t01-phase1-real') and batch.is_relative_to(REPO/'discovery/t01-phase1-real/w5')
    assert not root.exists() and not batch.exists();batch.mkdir(parents=True)
    original=REPO/'var/t01-phase1-real/esm-if1-acceptance-r01'
    archive=REPO/'discovery/t01-phase1-real/w5/esm-if1-integration-20260908/acceptance-r01'
    index=decode((archive/'index.json').read_bytes())
    for item in index['files']:
        raw=(archive/item['path']).read_bytes();assert len(raw)==item['bytes'] and sha(raw)==item['sha256']
    shutil.copytree(original,root)
    # Restore only intentionally damaged artifacts in the NEW copy from verified archive.
    # Original runtime, original archive, IDs and historical execution profiles stay untouched.
    rt=Runtime(root,domains_database_root=batch/'domains-databases',homology_database_root=batch/'homology-databases')
    restored=[]
    for name in ('n11-real24','documented'):
        folder=archive/'cases'/name;job=decode((folder/'job.json').read_bytes())
        for ref in job['artifacts']:
            with rt._db() as db:relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
            data=(folder/'artifacts'/ref['artifact_id']).read_bytes();target=root/relative
            if target.read_bytes()!=data:
                assert target.resolve().is_relative_to(root.resolve())
                restored.append(dict(path=relative,copied_before_sha256=sha(target.read_bytes()),restored_sha256=sha(data)))
                target.write_bytes(data)
    write(batch/'historical-copy.json',dict(source_root=str(original),source_index=str(archive/'index.json'),
        source_index_sha256=sha((archive/'index.json').read_bytes()),copied_root=str(root),restored_artifacts=restored,
        semantics='Copied historical identities, not newly executed model evidence; only this fresh runtime copy is mutable'))
    profile=policy.registered_profile();write(batch/'profile.json',profile);write(batch/'rules.json',policy.registered_rules())
    snapshots=[p for p in policy.HERE.glob('*') if p.is_file()]+[Path(__file__),REPO/'scripts/probe_design_backend_masks.py',REPO/'tests/test_design_backend_development.py']
    snapshots += [policy.HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py')]
    for path in snapshots:write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    cases=[];guards=[]
    def source(job):
        final=rt.get(job['job_id']);refs=[r for r in final['artifacts'] if r['role'] in ('result','diagnostic')]
        return dict(job_id=final['job_id'],artifact=refs[0] if refs else None)
    def finish(name,job,state='succeeded',error=None,kind='REAL_BACKEND'):
        job=rt.wait(job['job_id'],180);value=rt.result(job['job_id']) if job['artifacts'] else None
        write(batch/'cases'/name/'job.json',job);write(batch/'cases'/name/'events.json',rt.events(job['job_id']))
        if job['attempt_id']:write(batch/'cases'/name/'execution.json',rt.execution(job['job_id']))
        if value:write(batch/'cases'/name/'result.json',value)
        for ref in job['artifacts']:
            data=rt.artifact_bytes(job['job_id'],ref['artifact_id']);assert len(data)==ref['size_bytes'] and sha(data)==ref['sha256']
            write(batch/'cases'/name/'artifacts'/ref['artifact_id'],data)
        assert job['state']==state and job['error_code']==error,(name,job['state'],job['error_code'],value and value['execution'])
        if value:assert not value['usable_for_pipeline'] and not value['automatic_handoff'] and value['scientific_signoff'] is None
        if job['tool_id']==policy.TOOL and value:
            assert value['design_permissions'] is None and value['mutation_burden'] is None and value['validation'] is None
        cases.append(dict(case=name,job_id=job['job_id'],tool_id=job['tool_id'],state=state,error_code=error,kind=kind))
        print(name,state,error,flush=True);return job,value
    def run(name,body,tool=policy.TOOL,fault=None,state='succeeded',error=None):
        write(batch/'requests'/(name+'.json'),body);job=rt.submit_sequence(encode(body),name,tool);rt._development_fault=fault
        try:rt.dispatch(job['job_id'])
        finally:rt._development_fault=None
        if fault=='interrupt_after_claim':rt.recover(job['job_id'])
        return finish(name,job,state,error,'CONTROLLED_FAULT' if fault else 'REAL_BACKEND')
    def load(name):return rt.get(decode((archive/'cases'/name/'job.json').read_bytes())['job_id'])
    n11=load('n11-real24');scored=load('native-baseline-and24');structure=load('structure-real-1ubq')
    for name,job in (('historical-n11',n11),('historical-n12',scored),('historical-structure',structure)):
        finish(name,job,kind='HISTORICAL_REAL_OUTPUT_REUSED')
    seq=rt.result(n11['job_id'])['generation']['records'][0]['sequence']
    with rt._db() as db:seq=decode(rt._input(db,n11['request_artifact'],n11['run_id']))['protein_sequence']
    body=dict(protein_sequence=seq,user_sequence_id='S27 S28 real historical WT audit',upstream={n:None for n in policy.PRODUCERS},
        user_regions=[],objective='general',epitope_policy='PRESERVE',epitope_mode='both',membrane_design_confirm=False,
        sample_numbers=[],timeout_seconds=60)
    _,missing=run('all-sources-missing',body);assert not missing['audit']['permissions']['open_positions']
    for name,job in (('structure',structure),('n11',n11),('esm_if1',scored)):body['upstream'][name]=source(job)
    body['sample_numbers']=list(range(1,25))
    main,actual=run('historical-24-burden',body)
    assert len(actual['audit']['burden_records'])==24 and actual['audit']['n12_original_engineering_rules']['all_excluded']
    assert all(r['values']['epitope_proximity'] is None for r in actual['audit']['burden_records'])
    # Real N07 and N06 missing-input failure, registered with exact same WT.
    gb=dict(protein_sequence=seq,user_sequence_id='linked N07',timeout_seconds=5,
        hotspot_input=dict(state='not_provided',hotspots=None,source=None,reason_code=None))
    glyco,_=run('real-n07',gb,n07.TOOL)
    eb=dict(protein_sequence=seq,user_sequence_id='linked N06 missing predictors',timeout_seconds=5,
        **{n+'_input':copy.deepcopy(ABSENT) for n in ('blast','bepipred','netmhc')})
    eb['blast_input'].update(state='not_executed',reason_code='NOT_EXECUTED')
    epitope,_=run('real-n06-unavailable',eb,n06.TOOL,state='failed',error='TOOL_FAILED')
    db,_=database(batch/'domains-databases',[entry(seq=seq,features=[feature('Domain',2,5),feature('Active site',9,9)])])
    db['protein_sequence']=seq;db['user_annotations']=[dict(type='user_function',start=12,end=13,note='explicit engineering annotation')]
    domains,_=run('real-n09',db,n09.TOOL)
    # Actual offline MSA using a local engineering collection with this exact WT.
    hb,folder=make_database(batch/'homology-databases',count=24,length=len(seq))
    import random
    rng=random.Random(2712);annotations=decode((folder/'annotations.json').read_bytes());seqs={}
    for i,row in enumerate(annotations):
        chars=list(seq)
        if i:
            for p in rng.sample(range(30,len(seq)),6):chars[p]=rng.choice(policy.AA.replace(chars[p],''))
        seqs[row['id']]=''.join(chars);row['host_species']='engineering-host-'+str(i%3)
    from t01_phase1_real.development.homology.compute import format_fasta
    (folder/'sequences.fasta').write_bytes(format_fasta(seqs).encode());(folder/'annotations.json').write_bytes(encode(annotations))
    manifest=decode((folder/'manifest.json').read_bytes())
    manifest['source']['reference']='run_design_backend_acceptance.py; source WT identity with synthetic substitutions and labels; not a biological database'
    manifest['files']=[dict(path=n,bytes=(folder/n).stat().st_size,sha256=sha((folder/n).read_bytes())) for n in ('annotations.json','sequences.fasta')]
    (folder/'manifest.json').write_bytes(encode(manifest));hb.update(protein_sequence=seq,database_manifest_sha256=sha(encode(manifest)))
    homology,_=run('real-n08',hb,n08.TOOL)
    for name,job in (('glycosylation',glyco),('epitope_map',epitope),('domains',domains),('homology',homology)):body['upstream'][name]=source(job)
    body['user_regions']=[dict(start=1,end=1,permission='FIXED',allowed_residues=None,source_id='explicit engineering anchor'),
        dict(start=2,end=2,permission='OPEN',allowed_residues=None,source_id='explicit engineering HARD override')]
    linked,combined=run('combined-real-sources',body)
    audit=combined['audit'];assert audit['permissions']['constraint_override'] and audit['n11_request_draft'] is not None
    assert audit['n12_original_engineering_rules']==actual['audit']['n12_original_engineering_rules']
    assert any(r['values']['functional_proximity'] is not None for r in audit['burden_records'])
    # Explicit original parser/featurizer exercise, without sampling or loading weights.
    maskdir=batch/'mask-probe';native=maskdir/'native';out=maskdir/'output';native.mkdir(parents=True);out.mkdir()
    with rt._db() as transaction:prepared,receipt=prepare_mpnn(rt,transaction,audit['n11_request_draft'])
    for name,data in prepared.items():
        if name.startswith('native/'):write(native/name[7:],data)
    write(native/'request.json',audit['n11_request_draft']);write(maskdir/'source-receipt.json',receipt)
    cmd=['docker','--config',str(REPO/'tmp/proteinmpnn-docker'),'--host','npipe:////./pipe/dockerDesktopLinuxEngine','run','--rm',
        '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','2g','--cpus','2',
        '--pids-limit','128','--tmpfs','/tmp:rw,noexec,nosuid,size=128m',
        '-v',str(mpnn.PACKAGE)+':/app:ro','-v',str(native)+':/native:ro','-v',str(out)+':/out:rw',
        '-v',str(REPO/'scripts/probe_design_backend_masks.py')+':/probe.py:ro',mpnn.IMAGE,'python','-B','/probe.py']
    proc=subprocess.run(cmd,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    write(maskdir/'command.json',dict(argv=cmd,exit_code=proc.returncode,stdout=proc.stdout.decode(),stderr=proc.stderr.decode()))
    assert proc.returncode==0,proc.stderr.decode()
    probe=decode((out/'mask-probe.json').read_bytes());assert probe['generation_invocations']==0 and probe['network_interfaces']==[[1,'lo']]
    for fault,code in [('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID'),('interrupt_after_claim','INTERRUPTED')]:
        failed,_=run(fault,body,fault=fault,state='failed',error=code)
        retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=failed['job_id'],idempotency_key=fault+'-retry')))
        rt.dispatch(retry['job_id']);finish(fault+'-retry',retry)
    queued=rt.submit_sequence(encode(body),'queued-cancel',policy.TOOL)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=queued['job_id'],idempotency_key='queued-stop')))
    finish('queued-cancel',queued,'cancelled','CANCELLED','LIFECYCLE')
    conflict=copy.deepcopy(body);conflict['user_regions'].append(dict(start=2,end=2,permission='FIXED',allowed_residues=None,source_id='overlapping engineering instruction'))
    _,cv=run('conflicting-user-regions',conflict);assert cv['audit']['n11_request_draft'] is None
    for key in ('domains','epitope_map'):
        empty=copy.deepcopy(body);empty['upstream'][key]=None;run('missing-'+key,empty)
    empty=copy.deepcopy(body);empty['sample_numbers']=[];_,ev=run('empty-selection',empty);assert ev['audit']['burden_records']==[]
    # Reuse historical WT-only generation and scoring for zero-mutation guards.
    multi=load('n11-multichain-wt-only');ms=load('structure-multichain');mi=load('multichain-wt-identical')
    mb=copy.deepcopy(body)
    with rt._db() as transaction:mb['protein_sequence']=decode(rt._input(transaction,multi['request_artifact'],multi['run_id']))['protein_sequence']
    mb.update(upstream={n:None for n in policy.PRODUCERS},user_regions=[],sample_numbers=[1,2])
    for n,j in (('structure',ms),('n11',multi),('esm_if1',mi)):mb['upstream'][n]=source(j)
    _,zero=run('real-wt-zero-mutations',mb);assert all(r['values']['count']==0 and r['values']['functional_proximity']==0 for r in zero['audit']['burden_records'])
    def reject(name,changed):
        write(batch/'rejected-requests'/(name+'.json'),changed)
        try:rt.submit_sequence(encode(changed),name,policy.TOOL)
        except RuntimeFault as exc:guards.append(dict(case=name,error_code=exc.code,reason=str(exc)))
        else:raise AssertionError('Invalid request accepted: '+name)
    bad=copy.deepcopy(body);bad['protein_sequence']='A'+seq[1:];reject('wrong-wt',bad)
    bad=copy.deepcopy(body);bad['upstream']['structure']=source(ms);reject('wrong-structure',bad)
    bad=copy.deepcopy(body);bad['upstream']['esm_if1']=source(mi);reject('wrong-n12',bad)
    bad=copy.deepcopy(body);bad['upstream']['n11']['artifact']['sha256']='0'*64;reject('forged-n11',bad)
    bad=copy.deepcopy(body);bad['sample_numbers']=[25];reject('out-of-range-sample',bad)
    assert rt.submit_sequence(encode(body),'combined-real-sources',policy.TOOL)['job_id']==linked['job_id']
    try:rt.submit_sequence(encode(dict(body,user_sequence_id='changed')),'combined-real-sources',policy.TOOL)
    except RuntimeFault as exc:assert exc.code=='IDEMPOTENCY_CONFLICT';guards.append(dict(case='changed-duplicate',error_code=exc.code))
    else:raise AssertionError('Changed duplicate accepted')
    argv=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(root),'design-audit',
        '--input',str(batch/'requests/combined-real-sources.json'),'--key','documented','--run','--wait','60']
    proc=subprocess.run(argv,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    write(batch/'cli/documented.json',dict(argv=argv,exit_code=proc.returncode,stdout=proc.stdout.decode(),stderr=proc.stderr.decode()))
    assert proc.returncode==0,proc.stderr.decode()
    value=decode(proc.stdout);documented=rt.get(value['job']['job_id']);finish('documented',documented)
    pending=rt.submit_sequence(encode(body),'late-source-tamper',policy.TOOL)
    with rt._db() as transaction:relative=transaction.execute('SELECT relative_path FROM artifacts WHERE id=?',(source(domains)['artifact']['artifact_id'],)).fetchone()[0]
    with (root/relative).open('ab') as stream:stream.write(b' controlled source tamper')
    rt.dispatch(pending['job_id']);finish('late-source-tamper',pending,'failed','HASH_MISMATCH','CONTROLLED_SOURCE_TAMPER')
    with rt._db() as transaction:relative=transaction.execute('SELECT relative_path FROM artifacts WHERE id=?',(source(documented)['artifact']['artifact_id'],)).fetchone()[0]
    with (root/relative).open('ab') as stream:stream.write(b' controlled result tamper')
    try:rt.result(documented['job_id'])
    except RuntimeFault as exc:assert exc.code=='HASH_MISMATCH';guards.append(dict(case='published-tamper',error_code=exc.code))
    else:raise AssertionError('Published tamper accepted')
    assert profile==policy.registered_profile();write(batch/'guards.json',guards)
    files=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(batch.rglob('*')) if p.is_file()]
    write(batch/'index.json',dict(status='PASS',completed_at=now(),profile=profile,cases=cases,guards=guards,files=files,
        runtime_root=str(root),scope='S27_S28_ENGINEERING_AUDIT',scientific_signoff=None,usable_for_pipeline=False,automatic_handoff=False,
        formal_design=False,formal_validation=False,production_status='NOT_DEPLOYED'))
    print('DESIGN_BACKEND_ENGINEERING_PASS',flush=True)


if __name__=='__main__':main()
