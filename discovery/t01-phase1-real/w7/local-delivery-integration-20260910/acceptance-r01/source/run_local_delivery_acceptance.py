"""N17/N18 new-batch assembly of real historical records, without scientific reruns."""
import argparse
import copy
import io
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from t01_phase1_real.common import REPO,decode,encode,sha,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.wt_reference import policy as reference
from t01_phase1_real.development.local_delivery import policy as delivery
from t01_phase1_real.development.wt_draft import policy as draft
from run_variant_report_acceptance import clone,source,write

def src(j):return dict(job_id=j['job_id'],artifact=next((r for r in j['artifacts'] if r['role'] in ('result','diagnostic')),None))
def request(seq,p):
    b=dict(protein_sequence=seq,user_sequence_id='historical same-WT local engineering assembly',upstream={n:None for n in p.PRODUCERS},timeout_seconds=60)
    if p==delivery:b.update(host_species=None,expression_host=None,dna_bindings=[])
    if p==draft:b.update(host_species=None,organism=None)
    return b

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--batch',required=True);a=ap.parse_args();assert a.batch.replace('-','').isalnum()
    root=REPO/'var/t01-phase1-real'/('local-delivery-20260910-'+a.batch)
    batch=REPO/'discovery/t01-phase1-real/w7/local-delivery-integration-20260910'/a.batch
    assert not root.exists() and not batch.exists();root.mkdir(parents=True);batch.mkdir(parents=True)
    base=REPO/'discovery/t01-phase1-real'
    n13=base/'w6/n13-integration-20260909/acceptance-r05';supp=base/'w6/n13-integration-20260909/supplement-r01'
    reports=base/'w6/variant-report-integration-20260909/acceptance-r03'
    design=base/'w5/design-backend-integration-20260908/acceptance-r02';esm=base/'w5/esm-if1-integration-20260908/acceptance-r01'
    fold=base/'w6/foldx-integration-20260909/acceptance-r05';thermo=base/'w6/thermompnn-integration-20260908/acceptance-r05'
    dr=clone(REPO/'var/t01-phase1-real/n13-acceptance-20260909-r05/design',root/'design',[esm,design,reports,n13,supp],batch)
    fr=clone(REPO/'var/t01-phase1-real/n13-acceptance-20260909-r05/foldx',root/'foldx',[fold,reports,n13,supp],batch)
    tr=clone(Path(decode((thermo/'index.json').read_bytes())['runtime_root']),root/'thermo',[thermo],batch)
    cases=[];guards=[]
    def finish(rt,name,j):
        j=rt.get(j['job_id']);v=rt.result(j['job_id']) if j['artifacts'] else None
        write(batch/'cases'/name/'job.json',j);write(batch/'cases'/name/'request.json',rt._request_bytes(j))
        write(batch/'cases'/name/'events.json',rt.events(j['job_id']))
        if v:write(batch/'cases'/name/'result.json',v)
        for r in j['artifacts']:write(batch/'cases'/name/'artifacts'/r['artifact_id'],rt.artifact_bytes(j['job_id'],r['artifact_id']))
        if v and v.get('delivery'):
            for r in v['raw_artifacts']:
                if r['path'] in ('output/package.zip','output/report.md','output/package-manifest.json'):
                    write(batch/'cases'/name/Path(r['path']).name,rt.artifact_bytes(j['job_id'],r['artifact']['artifact_id']))
            with zipfile.ZipFile(batch/'cases'/name/'package.zip') as z:
                for file in ('data.json','manifest.json'):write(batch/'cases'/name/file,z.read(file))
        cases.append(dict(case=name,job_id=j['job_id'],runtime_root=str(rt.root),state=j['state'],error_code=j['error_code']))
        print(name,j['state'],j['error_code'],flush=True);return j,v
    def run(rt,name,b,p,fault=None):
        write(batch/'requests'/(name+'.json'),b);j=rt.submit_sequence(encode(b),name,p.TOOL);rt._development_fault=fault
        try:rt.dispatch(j['job_id'])
        finally:rt._development_fault=None
        if fault=='interrupt_after_claim':rt.recover(j['job_id'])
        j,v=finish(rt,name,j);assert j['state']==('failed' if fault else 'succeeded'),(j,v)
        return j,v
    def reject(rt,name,b,p):
        try:rt.submit_sequence(encode(b),name,p.TOOL)
        except RuntimeFault as exc:guards.append(dict(case=name,code=exc.code,reason=str(exc)))
        else:raise AssertionError(name+' accepted')
    # 76aa design/N13 report: retain all 24 original exclusions and partial WT facts.
    report=source(dr,n13,'real24-paired-n06-report');rreq=decode(dr._request_bytes(dr.get(report['job_id'])))
    audit=rreq['upstream']['design_audit'];areq=decode(dr._request_bytes(dr.get(audit['job_id'])))
    b=request(rreq['protein_sequence'],reference);b['upstream'].update(structure=areq['upstream']['structure'],design_audit=audit,topology=areq['upstream']['topology'])
    rj,_=run(dr,'real24-wt-reference-missing-scans',b,reference)
    wb=request(b['protein_sequence'],draft)
    for n in wb['upstream']:
        if n in areq['upstream']:wb['upstream'][n]=areq['upstream'][n]
    if wb['upstream']['structure']:
        sr=decode(dr._request_bytes(dr.get(wb['upstream']['structure']['job_id'])));wb['host_species']=sr['host_species']
    wj,_=run(dr,'real24-wt-draft',wb,draft)
    db=request(b['protein_sequence'],delivery);db['host_species']=wb['host_species'];db['upstream'].update(wt_draft=src(wj),variant_report=report,wt_reference=src(rj))
    dj,dv=run(dr,'real24-all-excluded-delivery',db,delivery)
    d=dv['delivery'];assert d['outcome']=='ALL_EXCLUDED' and d['variant_report']['summary']['excluded']==24
    assert all(r['exclusion_reasons'] for r in d['variant_report']['records']) and d['best_candidate'] is None
    # The two engines bind different registered WT structure analyses: keep separate.
    refbodies=[]
    for rt,archive,name,engine in ((fr,fold,'positionscan-two-positions','foldx'),(tr,thermo,'monomer-full-ssm','thermompnn')):
        scan=source(rt,archive,name);req=decode(rt._request_bytes(rt.get(scan['job_id'])))
        rb=request(req['protein_sequence'],reference);rb['upstream'].update(structure=dict(job_id=req['structure_artifact']['job_id'],artifact=req['structure_artifact']),**{engine:scan})
        j,v=run(rt,engine+'-wt-reference',rb,reference);assert v['reference']['engines'][engine]['records']
        pb=request(req['protein_sequence'],delivery);pb['upstream']['wt_reference']=src(j)
        run(rt,engine+'-local-delivery',pb,delivery);refbodies.append(rb)
    wrong=copy.deepcopy(refbodies[0]);wrong['upstream']['foldx']=source(fr,fold,'buildmodel-three-variants-five-runs');reject(fr,'buildmodel-is-not-wt-scan',wrong,reference)
    wrong=copy.deepcopy(refbodies[0]);wrong['protein_sequence']=db['protein_sequence'];reject(fr,'wrong-wt-sequence',wrong,reference)
    wrong=copy.deepcopy(refbodies[0]);wrong['upstream']['thermompnn']=refbodies[1]['upstream']['thermompnn'];reject(fr,'cross-runtime-engine-join',wrong,reference)
    wrong=copy.deepcopy(db);wrong['upstream']['wt_reference']=src(j);reject(dr,'cross-batch-delivery',wrong,delivery)
    for rt,archive,name,engine in ((fr,fold,'tool-failure','foldx'),(tr,thermo,'multichain-r39-skip','thermompnn')):
        scan=source(rt,archive,name);req=decode(rt._request_bytes(rt.get(scan['job_id'])))
        if engine=='foldx':
            # Failure fixture is BuildModel; cannot substitute it for a scan.
            wrong=copy.deepcopy(refbodies[0]);wrong['upstream']['foldx']=scan;reject(rt,'failed-buildmodel-still-not-scan',wrong,reference);continue
        rb=request(req['protein_sequence'],reference);rb['upstream'].update(structure=dict(job_id=req['structure_artifact']['job_id'],artifact=req['structure_artifact']),**{engine:scan})
        _,v=run(rt,'thermo-multichain-reference',rb,reference);assert v['reference']['engines'][engine]['records']==[]
    run(dr,'missing-input-delivery',request('ACDEFGHIK',delivery),delivery)
    for fault in ('compute_failure','corrupt_output','interrupt_after_claim'):
        j,_=run(dr,'delivery-'+fault,db,delivery,fault)
        retry=dr.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=j['job_id'],idempotency_key='retry-'+fault)))
        dr.dispatch(retry['job_id']);j,_=finish(dr,'delivery-retry-'+fault,retry);assert j['state']=='succeeded'
    assert dr.submit_sequence(encode(db),'real24-all-excluded-delivery',delivery.TOOL)['job_id']==dj['job_id']
    wrong=copy.deepcopy(db);wrong['user_sequence_id']='changed';reject(dr,'real24-all-excluded-delivery',wrong,delivery)
    wrong=copy.deepcopy(db);wrong['upstream']['variant_report']['artifact']['sha256']='0'*64;reject(dr,'damaged-reference',wrong,delivery)
    # Preserve pristine bytes in the batch before tampering a new publication.
    j,v=run(dr,'publication-before-tamper',request('ACDEFGHIK',delivery),delivery)
    ref=next(r['artifact'] for r in v['raw_artifacts'] if r['path']=='output/package.zip')
    with dr._db() as sql:path=dr.root/sql.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    path.write_bytes(b'corrupt')
    try:dr.artifact_bytes(j['job_id'],ref['artifact_id'])
    except RuntimeFault as exc:guards.append(dict(case='published-package-tamper',code=exc.code))
    else:raise AssertionError('Corrupt zip accepted')
    for module in ('wt_reference','local_delivery'):
        for p in (REPO/'src/t01_phase1_real/development'/module).glob('*.py'):write(batch/'source'/module/p.name,p.read_bytes())
    for name in ('runtime.py','registry.py','contracts.py','cli.py'):write(batch/'source'/name,(REPO/'src/t01_phase1_real/development'/name).read_bytes())
    write(batch/'source/run_local_delivery_acceptance.py',Path(__file__).read_bytes())
    write(batch/'guards.json',guards)
    index=dict(cases=cases,guards=guards,original_24_exclusions_preserved=True,scientific_handoff=False,
        profiles={p.TOOL:dict(execution=p.registered_profile(),rules=p.registered_rules()) for p in (reference,delivery)},
        files=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(batch.rglob('*')) if p.is_file()])
    write(batch/'index.json',index);print('SEALED',len(index['files']),'files',flush=True)

if __name__=='__main__':main()
