"""N13 real source pairs, explicit engineering predictors and report back-link acceptance."""
import argparse
import copy
from pathlib import Path
import subprocess
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import encode,decode,sha,RuntimeFault,now
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.epitope_protection import policy,service
from t01_phase1_real.development.variant_report import policy as report_policy
from run_variant_report_acceptance import clone,write,source

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--batch',required=True);a=p.parse_args()
    root=Path(a.root).absolute();batch=Path(a.batch).absolute()
    assert root.is_relative_to(REPO/'var/t01-phase1-real') and batch.is_relative_to(REPO/'discovery/t01-phase1-real/w6')
    assert not root.exists() and not batch.exists();root.mkdir(parents=True);batch.mkdir(parents=True)
    archive=REPO/'discovery/t01-phase1-real/w6/variant-report-integration-20260909/acceptance-r03'
    old=REPO/'var/t01-phase1-real/variant-report-acceptance-20260909-r03'
    dr=clone(old/'design',root/'design',[archive],batch);fr=clone(old/'foldx',root/'foldx',[archive],batch)
    cases=[];guards=[]
    def src(rt,j):
        j=rt.get(j['job_id']);refs=[r for r in j['artifacts'] if r['role'] in ('result','diagnostic')]
        return dict(job_id=j['job_id'],artifact=refs[0] if refs else None)
    def finish(rt,name,j,state='succeeded',code=None):
        j=rt.wait(j['job_id'],900);assert (j['state'],j['error_code'])==(state,code),(name,j.get('error_code'),rt.execution(j['job_id']))
        value=rt.result(j['job_id']) if j['artifacts'] else None
        write(batch/'cases'/name/'job.json',j);write(batch/'cases'/name/'events.json',rt.events(j['job_id']))
        if value:write(batch/'cases'/name/'result.json',value)
        for ref in j['artifacts']:write(batch/'cases'/name/'artifacts'/ref['artifact_id'],rt.artifact_bytes(j['job_id'],ref['artifact_id']))
        cases.append(dict(case=name,job_id=j['job_id'],tool_id=j['tool_id'],state=state,error_code=code,runtime_root=str(rt.root)))
        print(name,state,code,flush=True);return j,value
    def run(rt,name,body,tool=policy.TOOL,fault=None,state='succeeded',code=None):
        write(batch/'requests'/(name+'.json'),body);j=rt.submit_sequence(encode(body),'n13-'+name,tool);rt._development_fault=fault
        try:rt.dispatch(j['job_id'])
        finally:rt._development_fault=None
        if fault=='interrupt_after_claim':rt.recover(j['job_id'])
        return finish(rt,name,j,state,code)
    def empty():return {n:None for n in policy.SIDE_PRODUCERS}
    def make(rt,base):
        job=rt.get(base['job_id']);req=decode(rt._request_bytes(job))
        return dict(protein_sequence=req['protein_sequence'],user_sequence_id='N13 explicit engineering pair audit',
            upstream=dict(base_report=base),pairs=[],timeout_seconds=60)
    db=make(dr,source(dr,archive,'real-24-all-excluded'));base=dr.result(db['upstream']['base_report']['job_id'])
    original_req=decode(dr._request_bytes(dr.get(db['upstream']['base_report']['job_id'])))
    design_req=decode(dr._request_bytes(dr.get(original_req['upstream']['design_audit']['job_id'])))
    for row in base['report']['records']:
        wt=empty();wt['structure']=design_req['upstream']['structure']
        db['pairs'].append(dict(variant_id=row['id'],wt=wt,variant=empty()))
    dj,dv=run(dr,'real24-missing-variant-evidence',db)
    assert len(dv['protection']['records'])==24 and all(r['observation']['scientific_pass'] is None for r in dv['protection']['records'])
    rb=dict(original_req,n13_source=src(dr,dj));rj,rv=run(dr,'real24-report-linked',rb,report_policy.TOOL)
    assert rv['report']['outcome']=='ALL_EXCLUDED' and all(r['n13'] for r in rv['report']['records'])
    assert [(r['id'],r['esm_if1'],r['exclusion_reasons']) for r in rv['report']['records']]==[(r['id'],r['esm_if1'],r['exclusion_reasons']) for r in base['report']['records']]
    fb=make(fr,source(fr,archive,'real-foldx-three-bound'));basef=fr.result(fb['upstream']['base_report']['job_id'])
    freq=decode(fr._request_bytes(fr.get(fb['upstream']['base_report']['job_id'])))
    foldj=fr.get(freq['upstream']['foldx']['job_id']);foldreq=decode(fr._request_bytes(foldj));foldvalue=fr.result(foldj['job_id'])
    native={r['path']:fr.artifact_bytes(foldj['job_id'],r['artifact']['artifact_id']) for r in foldvalue['raw_artifacts']}
    record=basef['report']['records'][0];variant_sequence=record['sequence']
    # FoldX model is explicitly declared unknown, never AF/ESMFold or experimental.
    from structure_integration_cases import metadata
    meta=metadata(sequence=variant_sequence,fmt='PDB',source='unknown')
    meta['source_declaration']['note']='FoldX engineering mutant; not an AF/ESMFold prediction or experimental structure'
    sj=fr.submit_structure(encode(meta),'n13-foldx-mutant-local-analysis',native['output/buildmodel/target_Repair_1_0.pdb'])
    fr.dispatch(sj['job_id']);sj,sv=finish(fr,'foldx-mutant-local-analysis',sj)
    assert sv['analysis']['quality']['s11_quality_condition'] is False
    # Genuine local model executions, explicitly scoped engineering inputs; no automatic candidate flow.
    maps={}
    for side,seq in [('wt',db['protein_sequence']),('variant',base['report']['records'][0]['sequence'])]:
        nb=dict(protein_sequence=seq,user_sequence_id='N13 '+side+' explicit engineering B-cell predictor',timeout_seconds=300)
        nj,nv=run(dr,side+'-bepipred',nb,'t01.real.bepipred')
        eb=dict(protein_sequence=seq,user_sequence_id='N13 '+side+' registered N06',timeout_seconds=30,
            bepipred_input=dr.source_input(nj['job_id'],'t01.real.bepipred'),
            blast_input=dict(state='not_executed',artifact=None,reason_code='NOT_EXECUTED'),
            netmhc_input=dict(state='not_provided',artifact=None,reason_code=None))
        mj,mv=run(dr,side+'-n06',eb,'t01.real.epitope_map');maps[side]=src(dr,mj)
        assert mv['epitopes']['b_cell_antigenic_hotspot_map']['hotspots']==[]
    predicted=copy.deepcopy(db);predicted['pairs']=predicted['pairs'][:1]
    predicted['pairs'][0]['wt']['epitope_map']=maps['wt'];predicted['pairs'][0]['variant']['epitope_map']=maps['variant']
    pj,pv=run(dr,'real-paired-n06-hotspots-unavailable',predicted)
    assert all(pv['protection']['records'][0]['source_states'][s]['source_receipts']['epitope_map']['state']=='available' for s in ('wt','variant'))
    run(dr,'real24-paired-n06-report',dict(original_req,n13_source=src(dr,pj)),report_policy.TOOL)
    wt=empty();vs=empty();wt.update(structure=dict(job_id=foldreq['structure_artifact']['job_id'],artifact=foldreq['structure_artifact']))
    vs.update(structure=src(fr,sj))
    fb['pairs']=[dict(variant_id=record['id'],wt=wt,variant=vs)]
    fj,fv=run(fr,'real-paired-structure-n06',fb)
    obs=fv['protection']['records'][0]['observation'];assert obs['l1']['reason']=='EMPTY_VALIDATION_INTERVAL' and obs['l4']['value'] is None
    linked=dict(freq,n13_source=src(fr,fj));run(fr,'foldx-report-n13-linked',linked,report_policy.TOOL)
    def reject(rt,name,b,tool=policy.TOOL):
        try:rt.submit_sequence(encode(b),'n13-guard-'+name,tool)
        except RuntimeFault as exc:guards.append(dict(case=name,error_code=exc.code,reason=str(exc)))
        else:raise AssertionError('Unexpected acceptance '+name)
    wrong=copy.deepcopy(predicted);wrong['pairs'][0]['variant']['epitope_map']=maps['wt'];reject(dr,'wrong-side-sequence',wrong)
    wrong=copy.deepcopy(fb);wrong['pairs'][0]['variant_id']='absent';reject(fr,'different-batch-variant',wrong)
    wrong=copy.deepcopy(fb);wrong['pairs'][0]['wt']['structure']=src(fr,sj);reject(fr,'wrong-wt-structure',wrong)
    wrong=copy.deepcopy(fb);wrong['pairs'][0]['variant']['structure']['artifact']['sha256']='0'*64;reject(fr,'structure-hash',wrong)
    wrong=copy.deepcopy(fb);wrong['pairs'].append(wrong['pairs'][0]);reject(fr,'duplicate-pair',wrong)
    wrong=copy.deepcopy(rb);wrong['upstream']['foldx']=freq['upstream']['foldx'];reject(dr,'report-cross-root',wrong,report_policy.TOOL)
    wrong=copy.deepcopy(fb);wrong['upstream']['base_report']=src(fr,fr.get(cases[-1]['job_id']));reject(fr,'report-cycle',wrong)
    for fault,code in [('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID'),('interrupt_after_claim','INTERRUPTED')]:
        j,_=run(fr,fault,fb,fault=fault,state='failed',code=code)
        retry=fr.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=j['job_id'],idempotency_key='n13-'+fault+'-retry')))
        fr.dispatch(retry['job_id']);finish(fr,fault+'-retry',retry)
    for stop in ('cancel','timeout'):
        j=fr.submit_sequence(encode(fb),'n13-running-'+stop,policy.TOOL);original=service.evaluate
        def stopped(*args):
            with fr._tx() as tx:fr._stop(tx,fr._job(tx,j['job_id']),stop)
            return original(*args)
        service.evaluate=stopped
        try:fr.dispatch(j['job_id'])
        finally:service.evaluate=original
        _,v=finish(fr,'running-'+stop,j,'cancelled' if stop=='cancel' else 'timed_out','CANCELLED' if stop=='cancel' else 'TIMEOUT')
        assert v['protection'] is None
    # Hash mutation only in fresh copy; restore for normal documented queries.
    mapj=dr.get(maps['variant']['job_id']);ref=next(r for r in mapj['artifacts'] if r['role']=='raw')
    with dr._db() as tx:path=dr.root/tx.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    saved=path.read_bytes()
    try:path.write_bytes(b'{}');reject(dr,'raw-map-tamper',predicted)
    finally:path.write_bytes(saved)
    assert fr.submit_sequence(encode(fb),'n13-real-paired-structure-n06',policy.TOOL)['job_id']==fj['job_id']
    proc=subprocess.run([sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(dr.root),'variant-record','--job-id',rj['job_id'],'--id','sample-1'],capture_output=True)
    assert proc.returncode==0,proc.stdout+proc.stderr;write(batch/'query-sample-1.json',decode(proc.stdout))
    from t01_phase1_real.development.epitope_protection.compute import compare
    numeric_side=dict(hotspots=[dict(start=1,end=3,weighted_score=.6)],rsa=[.5]*3,quality_condition=True,
        geometry={str(i):dict(atoms={'CA':p}) for i,p in enumerate(([0.,0.,0.],[3.,0.,0.],[0.,4.,0.]),1)},domains=[dict(type='domain',start=1,end=3)],reasons=[])
    num=compare('AAA','AGA',dict(wt=numeric_side,variant=copy.deepcopy(numeric_side)))
    write(batch/'numeric-fixture.json',dict(kind='SYNTHETIC_CONTRACT_FIXTURE',wt='AAA',variant='AGA',sides=dict(wt=numeric_side,variant=numeric_side),result=num))
    write(batch/'profile.json',policy.registered_profile());write(batch/'rules.json',policy.registered_rules())
    paths=list(policy.HERE.glob('*.py'))+list((policy.HERE.parent/'variant_report').glob('*.py'))
    paths += [policy.HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py')]
    paths += [Path(__file__),REPO/'tests/test_epitope_protection_development.py']
    for path in paths:write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    files=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(batch.rglob('*')) if p.is_file()]
    write(batch/'index.json',dict(status='PASS',completed_at=now(),cases=cases,guards=guards,files=files,
        actual_predictor_jobs=2,actual_structure_jobs=1,historical_model_outputs_reused=True,real24_still_excluded=True,
        scientific_protection_pass=None,production_status='NOT_DEPLOYED',runtime_root=str(root)))

if __name__=='__main__':main()
