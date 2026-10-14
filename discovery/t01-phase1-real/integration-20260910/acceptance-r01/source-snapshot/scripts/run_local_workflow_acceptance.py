"""Fresh local model executions plus separately labelled historical exclusion reuse."""
import argparse
import copy
import io
from pathlib import Path
import sys
import time
import zipfile
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import encode,decode,sha,TERMINAL,RuntimeFault,now
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import policy
from run_variant_report_acceptance import write,clone
from structure_integration_cases import UBQ,metadata

def body():
    return dict(protein_sequence=UBQ,user_sequence_id='local real workflow integration',
                host_species='Homo sapiens',expression_host=None,organism=None,structure=None,
                analysis={n:None for n in policy.OPTIONS},reuse_jobs={},timeout_seconds=1800)

def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);args=p.parse_args()
    assert args.batch.replace('-','').isalnum()
    root=REPO/'var/t01-phase1-real'/('local-workflow-20260910-'+args.batch)
    batch=REPO/'discovery/t01-phase1-real/integration-20260910'/args.batch
    assert not root.exists() and not batch.exists();root.mkdir(parents=True);batch.mkdir(parents=True)
    rt=Runtime(root/'fresh');cases=[];guards=[]
    def save(rt,name,j):
        j=rt.get(j['job_id']);folder=batch/'cases'/name
        for file,value in [('job.json',j),('request.json',rt._request_bytes(j)),('events.json',rt.events(j['job_id'])),('execution.json',rt.execution(j['job_id']))]:write(folder/file,value)
        if j['artifacts']:
            result=rt.result(j['job_id']);write(folder/'result.json',result)
            for ref in j['artifacts']:write(folder/'artifacts'/ref['artifact_id'],rt.artifact_bytes(j['job_id'],ref['artifact_id']))
            for item in result.get('raw_artifacts',[]):
                if item['path'] in ('output/workflow-report.md','output/workflow.json','output/package.zip'):
                    write(folder/Path(item['path']).name,rt.artifact_bytes(j['job_id'],item['artifact']['artifact_id']))
        cases.append(dict(case=name,job_id=j['job_id'],runtime_root=str(rt.root),state=j['state'],error_code=j['error_code']))
    def run(rt,name,b,data=None):
        write(batch/'inputs'/(name+'.json'),b)
        if data:write(batch/'inputs'/(name+'.structure'),data)
        j=rt.submit_workflow(encode(b),name,data);write(batch/'submissions'/(name+'.json'),j)
        seen=None
        while j['state'] not in TERMINAL:
            j=rt.dispatch(j['job_id'])
            nodes=rt.execution(j['job_id']).get('nodes',{})
            progress=[(n,r['state']) for n,r in nodes.items()]
            if progress!=seen:print(name,progress,flush=True);seen=progress
            if j['state'] not in TERMINAL:time.sleep(.5)
        save(rt,name,j);view=rt.workflow(j['job_id']);write(batch/'cases'/name/'query.json',view)
        for n,row in view['nodes'].items():
            if row.get('job_id'):save(rt,name+'--'+n,rt.get(row['job_id']))
        assert rt.submit_workflow(encode(b),name,data)['job_id']==j['job_id']
        guards.append(dict(case=name+'-idempotent',passed=True))
        return j,view
    b=body();meta=metadata(sequence=UBQ,host_species=b['host_species'],source_declaration=dict(kind='experimental',note='Unchanged local 1UBQ.cif; new engineering analysis, no scientific signoff'))
    b['structure']={k:v for k,v in meta.items() if k not in ('protein_sequence','host_species')}
    b['analysis']['topology']=dict(timeout_seconds=300)
    b['analysis']['bepipred']=dict(timeout_seconds=900)
    original=REPO/'tests/fixtures/structure_mapping/real/1UBQ.cif';raw=original.read_bytes()
    write(batch/'input-origin.json',dict(path=str(original),sha256=sha(raw),size_bytes=len(raw),semantics='Unchanged local original; newly executed N01/N02/N04'))
    j,v=run(rt,'fresh-structure-predictors-report',b,raw)
    assert j['state']=='succeeded'
    for n in ('structure','topology','bepipred','epitope_map','glycosylation','local_delivery'):
        assert v['nodes'][n]['state']=='succeeded',(n,v['nodes'][n])
    # Missing inputs/assets and real upstream failure, without synthetic scientific output.
    b=body();b['analysis']['netmhc']={}
    b['analysis']['blast']=dict(database_id='integration-missing-database',database_manifest_sha256='0'*64,
        thresholds=dict(identity_percent_min=70.0,query_coverage_percent_min=80.0),timeout_seconds=30)
    j,v=run(rt,'missing-assets-and-inputs',b)
    assert j['state']=='succeeded' and v['nodes']['local_delivery']['state']=='succeeded'
    assert v['nodes']['blast']['state'] in ('failed','blocked') and v['nodes']['netmhc']['state']=='blocked'
    assert v['nodes']['epitope_map']['state']=='failed'
    # Read-only sources are cloned; original source IDs are retained and visibly marked reused.
    base=REPO/'discovery/t01-phase1-real'
    archives=[base/'w5/esm-if1-integration-20260908/acceptance-r01',base/'w5/design-backend-integration-20260908/acceptance-r02',
              base/'w6/variant-report-integration-20260909/acceptance-r03',base/'w6/n13-integration-20260909/acceptance-r05',
              base/'w6/n13-integration-20260909/supplement-r01']
    history=clone(REPO/'var/t01-phase1-real/local-delivery-20260910-acceptance-r01/design',root/'historical',archives,batch)
    report=decode((archives[3]/'cases/real24-paired-n06-report/job.json').read_bytes())
    req=decode(history._request_bytes(history.get(report['job_id'])))
    audit=history.get(req['upstream']['design_audit']['job_id']);areq=decode(history._request_bytes(audit))
    structure=history.get(areq['upstream']['structure']['job_id']);sreq=decode(history._request_bytes(structure))
    b=body();b.update(protein_sequence=req['protein_sequence'],host_species=sreq['host_species'],
        reuse_jobs=dict(structure=structure['job_id'],variant_report=report['job_id']))
    j,v=run(history,'historical-24-retained-exclusions',b)
    assert j['state']=='succeeded'
    delivery=history.result(v['nodes']['local_delivery']['job_id'])['delivery']
    assert delivery['outcome']=='ALL_EXCLUDED' and delivery['variant_report']['summary']['excluded']==24
    assert delivery['best_candidate'] is None and delivery['agent_c_payload'] is None
    assert v['nodes']['variant_report']['origin']=='HISTORICAL_REUSE'
    write(batch/'exclusion-regression.json',dict(original_report_job_id=report['job_id'],excluded=24,outcome='ALL_EXCLUDED',new_candidates=0))
    write(batch/'guards.json',guards)
    # Source snapshot permits independent reconstruction after subsequent development.
    for path in sorted((REPO/'src/t01_phase1_real').rglob('*.py')):write(batch/'source-snapshot'/path.relative_to(REPO),path.read_bytes())
    write(batch/'source-snapshot/scripts/run_local_workflow_acceptance.py',Path(__file__).read_bytes())
    rows=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(batch.rglob('*')) if p.is_file()]
    write(batch/'index.json',dict(created_at=now(),runtime_root=str(root),cases=cases,files=rows,guards=guards,
        qualification='DEVELOPMENT_UNREVIEWED',production_status='NOT_DEPLOYED',scientific_gate='CLOSED'))
    print('INDEX',len(rows),'files',len(cases),'jobs',flush=True)

if __name__=='__main__':main()
