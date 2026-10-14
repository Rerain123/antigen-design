"""Append idempotent P2 engineering tasks to the verified P1 run; never edit P1."""
from __future__ import annotations
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import prepare_m1_p1_deploy as _deployment


COMPRESSED_REMOTE=r'''
import sys,json,io,contextlib,gzip,base64,hashlib
envelope=json.load(sys.stdin)
sys.stdin=io.StringIO(json.dumps(envelope['payload']))
buffer=io.StringIO()
with contextlib.redirect_stdout(buffer):
    exec(compile(envelope['program'],'<p2-remote>','exec'),{'__name__':'__main__'})
raw=buffer.getvalue().encode('utf-8')
print(json.dumps(dict(data=base64.b64encode(gzip.compress(raw)).decode(),sha256=hashlib.sha256(raw).hexdigest())))
'''


def compressed_remote(code,payload=None):
    result=_deployment.remote(COMPRESSED_REMOTE,dict(program=code,payload=payload))
    raw=gzip.decompress(base64.b64decode(result['data'],validate=True))
    if hashlib.sha256(raw).hexdigest()!=result['sha256']:raise ValueError('P2 transport hash mismatch')
    return json.loads(raw)


deploy=SimpleNamespace(K=_deployment.K,remote=compressed_remote)

P1=ROOT/'discovery/t01-phase1-real/m1-p1-20260921/r01'
OUT=ROOT/'discovery/t01-phase1-real/m1-p2-20260921/r01'

PREAMBLE=r'''
import json,sys
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import encode,decode,ensure,TERMINAL
from t01_phase1_real.development import Runtime
task=json.load(sys.stdin)
rt=Runtime(Path('/var/lib/t01/runtime'),scope='svc-'+task['owner'][:24],
           blast_database_root=Path('/var/lib/t01/m1-p1-test-data/blast'))
run_id=task['run_id']
parent=rt.get(task['parent_job_id'])
ensure(parent['run_id']==run_id and parent['state']=='succeeded','FORBIDDEN','P1 parent mismatch')
def source(job):
    ensure(job['run_id']==run_id and job['state']=='succeeded','FORBIDDEN','Same-run successful source required')
    refs=[r for r in job['artifacts'] if r['role']=='result']
    ensure(len(refs)==1,'OUTPUT_INVALID','One registered result required')
    for ref in job['artifacts']:rt.artifact_bytes(job['job_id'],ref['artifact_id'])
    return dict(job_id=job['job_id'],artifact=refs[0])
def submit(name,tool,body):
    job=rt.submit_sequence_in_run(run_id,encode(body),'m1-p2-r01-'+name,tool)
    if job['state']=='queued':rt.dispatch(job['job_id'])
    return rt.get(job['job_id'])
def export(job):
    job=rt.get(job['job_id'])
    if job['state'] in ('running','reconciling','stop_requested'):
        rt.reconcile(job['job_id']);job=rt.get(job['job_id'])
    row=dict(job=job,request=decode(rt._request_bytes(job)))
    if job.get('attempt_id'):row['execution']=rt.execution(job['job_id'])
    if job['state'] in ('running','reconciling') and job['tool_id']=='t01.real.foldx' and row['request']['mode']=='buildmodel':
        target=row.get('execution',{}).get('resident_target')
        if target:
            root=Path(target)
            ensure(root.is_relative_to(Path('/var/lib/t01/resident/foldx')),'FORBIDDEN','Unexpected FoldX target')
            row['native_progress']=dict(model_files_observed=len(list((root/'output/native/buildmodel').glob('target_Repair_*.pdb'))),
                expected_model_files=len(row['request']['variants'])*5,not_final_scores=True)
            receipt=root/'execution.json'
            if receipt.is_file():
                native=decode(receipt.read_bytes())
                ensure(native['binding']=={k:job[k] for k in ('job_id','attempt_id','execution_identity')},
                       'FORBIDDEN','Native progress identity mismatch')
                row['native_progress']['execution_state']=native['state']
    if job['state'] in TERMINAL and job['artifacts']:
        for ref in job['artifacts']:rt.artifact_bytes(job['job_id'],ref['artifact_id'])
        row['result']=rt.result(job['job_id'])
    return row
'''

SCORE=r'''
structure=rt.get(task['structure_job_id']);n11=rt.get(task['n11_job_id'])
s=source(structure);n=source(n11)
ensure(s['artifact']==task['structure_artifact'] and n['artifact']==task['n11_artifact'],
       'HASH_MISMATCH','P1 published identity changed')
body=dict(protein_sequence=task['sequence'],user_sequence_id='M1 P2 same-run 24 candidates and WT baseline',
    structure_artifact=s['artifact'],n11_artifact=n['artifact'],sample_numbers=list(range(1,25)),
    baseline_artifact=None,timeout_seconds=900)
job=submit('esm-if1','t01.real.esm_if1',body)
print(json.dumps(export(job)))
'''

AUDIT=r'''
from t01_phase1_real.development.design_backend.policy import PRODUCERS
upstream={}
for name in PRODUCERS:
    jid=task['upstream'].get(name)
    upstream[name]=source(rt.get(jid)) if jid else None
constraints=task['constraints'];regions=[]
for p in constraints['fixed_positions']:
    regions.append(dict(start=p,end=p,permission='FIXED',allowed_residues=None,source_id=constraints['source_id']))
for item in constraints['restricted_positions']:
    regions.append(dict(start=item['position'],end=item['position'],permission='RESTRICTED',allowed_residues=item['allowed_residues'],source_id=constraints['source_id']))
for p in constraints['open_positions']:
    regions.append(dict(start=p,end=p,permission='OPEN',allowed_residues=None,source_id=constraints['source_id']))
body=dict(protein_sequence=task['sequence'],user_sequence_id='M1 P2 explicit P1 mask audit',upstream=upstream,
    user_regions=regions,objective='general',epitope_policy='PRESERVE',epitope_mode='both',
    membrane_design_confirm=False,sample_numbers=list(range(1,25)),timeout_seconds=60)
print(json.dumps(export(submit('design-audit','t01.real.design_audit',body))))
'''

STEP=r'''
name=task['name'];body=task['body'];tool=task['tool']
if tool=='t01.real.ingest_structure':
    from t01_phase1_real.development.esmfold2.source import verified
    from t01_phase1_real.development.structure import policy as sp
    from t01_phase1_real.development.workflow.service import envelope
    with rt._tx() as db:
        ref,_=verified(rt,db,task['prediction_job_id'],body['protein_sequence'],body['host_species'],run_id)
        body=dict(body,structure_artifact=ref)
        def action():
            request_ref=rt._stage(db,run_id,encode(body),sp.TOOL)
            request=envelope(run_id,request_ref,sp,'m1-p2-r01-'+name)
            rt._admit(db,request)
            return rt._new_job(db,request,encode(request))
        job=rt._idempotent(db,'m1-p2-predicted-structure',name,encode(body),action)
    if job['state']=='queued':rt.dispatch(job['job_id'])
else:
    if tool=='t01.real.epitope_map':
        for n in ('bepipred','netmhc'):
            body[n+'_input']=rt.source_input(task[n+'_job_id'],'t01.real.'+n)
    if tool=='t01.real.glycosylation':
        body['hotspot_input']=rt.n06_hotspot_input(task['epitope_map_job_id'],body['protein_sequence'])
    job=submit(name,tool,body)
print(json.dumps(export(job)))
'''


def local(name):return json.loads((OUT/(name+'.json')).read_bytes())


def ref(row):
    job=row['job'];assert job['state']=='succeeded'
    return dict(job_id=job['job_id'],artifact=next(r for r in job['artifacts'] if r['role']=='result'))


def run_step(task,name,tool,body,**extra):
    path=OUT/(name+'.json')
    if path.exists():row=local(name)
    else:
        row=deploy.remote(PREAMBLE+STEP,dict(task,name=name,tool=tool,body=body,**extra));save(name+'.json',row)
    next_progress=0.0
    while row['job']['state'] not in ('succeeded','failed','timed_out','cancelled'):
        if time.monotonic()>=next_progress:
            print(json.dumps(dict(name=name,state=row['job']['state'],job_id=row['job']['job_id'],
                started_at=row['job'].get('started_at'),timeout_seconds=row['request']['timeout_seconds'],
                native_progress=row.get('native_progress'),
                progress='WAITING_FOR_NATIVE_RESULT')),flush=True)
            next_progress=time.monotonic()+60
        time.sleep(15)
        row=deploy.remote(PREAMBLE+"print(json.dumps(export(rt.get(task['job_id']))))",dict(task,job_id=row['job']['job_id']))
        save(name+'.json',row)
    print(json.dumps(dict(name=name,state=row['job']['state'],error_code=row['job']['error_code'])),flush=True)
    if row['job']['state']!='succeeded':raise RuntimeError('P2 task failed: '+name)
    return row


def continue_p2(task):
    base=dict(protein_sequence=task['sequence'],user_sequence_id='M1 P2 same-run engineering continuation',timeout_seconds=60)
    audit=local('design-audit')
    report_request=dict(base,upstream=dict(design_audit=ref(audit),foldx=None),variant_source='N11_DESIGN_AUDIT',foldx_bindings=[])
    selection_report=run_step(task,'selection-report','t01.real.variant_report',report_request)
    sys.path.insert(0,str(ROOT/'src'))
    from t01_phase1_real.development.variant_report.m1 import selection
    numbers=selection(selection_report['result']['report']['records'])
    selected={r['sample_number']:r for r in selection_report['result']['report']['records'] if r['sample_number'] in numbers}
    selection_evidence=dict(sample_numbers=numbers,source=ref(selection_report),
        debug_only=all(selected[n]['disposition']=='EXCLUDED' for n in numbers),
        retry=dict(state='NOT_EXECUTED',reason='PINNED_N11_PROFILE_SUPPORTS_ONLY_24_AT_0_1',
                   original_rule='AgentA_SOP_v10.5_20260902 T-01 step17 first retry: 48 designs temperature 0.3',
                   m1_limit='AT_MOST_ONE_ADDITIONAL_ROUND; no unsupported configuration or synthetic rerun'),
        scientific_release_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')
    save('selection.json',selection_evidence)
    # Same-version WT predictor/N10 calculations make the comparison independently reviewable.
    wt_structure=ref(json.loads((P1/'structure.json').read_bytes()))
    all_sources={}
    for label,seq in [('wt',task['sequence'])]+[('sample-'+str(n),selected[n]['sequence']) for n in numbers]:
        b=dict(base,protein_sequence=seq,user_sequence_id='M1 P2 '+label)
        current={}
        if label=='wt':current['structure']=wt_structure
        else:
            prediction=run_step(task,label+'-prediction','t01.real.esmfold2',dict(b,host_species=task['host'],seed=1,timeout_seconds=900))
            current['prediction']=ref(prediction)
            structure=run_step(task,label+'-structure','t01.real.ingest_structure',
                dict(protein_sequence=seq,host_species=task['host'],structure_name='esmfold2.cif',declared_format='MMCIF',
                     selection=dict(model_index=0,chain_selector='A'),context_chain_ids=['A'],
                     source_declaration=dict(kind='predicted',note='esmfold2 job '+prediction['job']['job_id']),timeout_seconds=120),
                prediction_job_id=prediction['job']['job_id'])
            current['structure']=ref(structure)
        for name in ('bepipred','netmhc'):
            body=json.loads((P1/(name+'.json')).read_bytes())['request']
            body.update(protein_sequence=seq,user_sequence_id=b['user_sequence_id'])
            row=run_step(task,label+'-'+name,'t01.real.'+name,body);current[name]=ref(row)
        em=run_step(task,label+'-epitope-map','t01.real.epitope_map',dict(b,
            blast_input=dict(state='not_executed',artifact=None,reason_code='P2_VARIANT_BLAST_NOT_EXECUTED')),
            bepipred_job_id=current['bepipred']['job_id'],netmhc_job_id=current['netmhc']['job_id'])
        current['epitope_map']=ref(em)
        glyco=run_step(task,label+'-glycosylation','t01.real.glycosylation',b,epitope_map_job_id=em['job']['job_id'])
        current['glycosylation']=ref(glyco)
        body=json.loads((P1/'developability.json').read_bytes())['request']
        body.update(protein_sequence=seq,user_sequence_id=b['user_sequence_id'],
            structure_input=dict(state='available',artifact=current['structure']['artifact'],reason_code=None))
        dev=run_step(task,label+'-developability','t01.real.developability',body);current['developability']=ref(dev)
        all_sources[label]=current
    variants=[dict(variant_id=selected[n]['id'],mutations=selected[n]['mutations']) for n in numbers]
    foldx=run_step(task,'foldx-extended','t01.real.foldx',dict(base,structure_artifact=task['structure_artifact'],mode='buildmodel',
        fixed_positions=[1,76],scan_positions=[],variants=variants,timeout_seconds=14400,
        scope_source=dict(purpose='ENGINEERING_STABILITY_SCOPE',source_id='M1-P2 same P1 WT; representative exact N11 sequence diffs')))
    report_request['upstream']['foldx']=ref(foldx)
    report_request['foldx_bindings']=[dict(sample_number=n,variant_id=selected[n]['id']) for n in numbers]
    base_report=run_step(task,'base-report','t01.real.variant_report',report_request)
    pairs=[dict(variant_id=selected[n]['id'],wt=dict(structure=wt_structure,epitope_map=all_sources['wt']['epitope_map'],domains=None),
        variant=dict(structure=all_sources[selected[n]['id']]['structure'],epitope_map=all_sources[selected[n]['id']]['epitope_map'],domains=None)) for n in numbers]
    protection=run_step(task,'protection','t01.real.epitope_protection',dict(base,upstream=dict(base_report=ref(base_report)),pairs=pairs))
    report_request['n13_source']=ref(protection)
    names=('epitope_map','glycosylation','developability')
    report_request['m1_test']=dict(wt={n:all_sources['wt'][n] for n in names},representatives=[
        dict(sample_number=n,**{k:all_sources[selected[n]['id']][k] for k in ('prediction','structure',*names)}) for n in numbers])
    run_step(task,'final-report','t01.real.variant_report',report_request)

def save(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def context():
    batch=json.loads((P1/'batch.json').read_bytes())
    audit=json.loads((P1/'audit-summary.json').read_bytes())
    assert audit['status']=='M1_P1_UPSTREAM_TO_N11_PASS'
    structure=json.loads((P1/'structure.json').read_bytes())
    design=json.loads((P1/'design.json').read_bytes())
    ref=lambda row:next(r for r in row['job']['artifacts'] if r['role']=='result')
    return dict(owner=batch['owner'],run_id=audit['run_id'],parent_job_id=audit['job_id'],
        sequence=batch['request']['protein_sequence'],host=batch['request']['host_species'],
        structure_job_id=structure['job']['job_id'],structure_artifact=ref(structure),
        n11_job_id=design['job']['job_id'],n11_artifact=ref(design),
        p1_evidence_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in P1.iterdir() if p.is_file()})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['score','audit','poll','continue','logs','retry'])
    parser.add_argument('--name',default='esm-if1')
    args=parser.parse_args();task=context()
    if (OUT/'continuation.json').exists():assert json.loads((OUT/'continuation.json').read_bytes())==task
    else:save('continuation.json',task)
    if args.action=='continue':
        if (OUT/'esm-if1-r08.json').exists():
            from finish_m1_p2_probe import main as finish_current_profile
            finish_current_profile()
        else:continue_p2(task)
        return
    if args.action in ('logs','retry'):
        name=args.name;assert name.replace('-','').isalnum()
        previous=local(name);task['job_id']=previous['job']['job_id']
        if args.action=='logs':
            code=r'''
j=rt.get(task['job_id']);v=rt.result(j['job_id'])
print(json.dumps({i['path']:rt.artifact_bytes(j['job_id'],i['artifact']['artifact_id']).decode(errors='replace')[-12000:]
    for i in v['raw_artifacts'] if i['path'].endswith(('stderr.txt','stdout.txt'))}))
'''
            result=deploy.remote(PREAMBLE+code,task);save(name+'-logs.json',result);print(json.dumps(result));return
        save(name+'-failed-'+task['job_id']+'.json',previous)
        code=r'''
job=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=task['job_id'],idempotency_key='m1-p2-retry-'+task['job_id'])))
if job['state']=='queued':rt.dispatch(job['job_id'])
print(json.dumps(export(job)))
'''
        row=deploy.remote(PREAMBLE+code,task);save(name+'.json',row);print(row['job']['state']);return
    if args.action=='score':row=deploy.remote(PREAMBLE+SCORE,task);name='esm-if1'
    elif args.action=='audit':
        task['upstream']={n:json.loads((P1/(n+'.json')).read_bytes())['job']['job_id']
            for n in ('structure','topology','epitope_map','glycosylation')}
        task['upstream'].update(n11=task['n11_job_id'],esm_if1=json.loads((OUT/'esm-if1.json').read_bytes())['job']['job_id'])
        task['constraints']=json.loads((P1/'design.json').read_bytes())['request']['constraints']
        row=deploy.remote(PREAMBLE+AUDIT,task);name='design-audit'
    else:
        name=args.name;assert name.replace('-','').isalnum()
        task['job_id']=json.loads((OUT/(name+'.json')).read_bytes())['job']['job_id']
        row=deploy.remote(PREAMBLE+"print(json.dumps(export(rt.get(task['job_id']))))",task)
    save(name+'.json',row)
    print(json.dumps(dict(name=name,job_id=row['job']['job_id'],state=row['job']['state'],error_code=row['job']['error_code'])))

if __name__=='__main__':main()
