"""Rebuild P3 from registered sources, export local artifacts, verify ZIP readback."""
import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
import run_m1_p3_probe as p
from audit_local_delivery_evidence import package

AUDIT=r'''
import base64,copy
from t01_phase1_real.common import RuntimeFault,sha
from t01_phase1_real.development.local_delivery.source import sources
from t01_phase1_real.development.local_delivery.compute import evaluate,package
from t01_phase1_real.development.wt_reference.source import sources as reference_sources
j=rt.get(task['delivery_job_id']);body=decode(rt._request_bytes(j))
ensure(parent==task['p1_parent_snapshot'],'OUTPUT_INVALID','P1 parent changed')
ensure(j['state']=='succeeded' and j['run_id']==run_id,'OUTPUT_INVALID','P3 delivery not successful in original run')
with rt._db() as db: files,values,receipts=sources(rt,db,body)
data=evaluate(body,files);v=rt.result(j['job_id'])
ensure(data==v['delivery'],'OUTPUT_INVALID','N18 does not match recursively rebuilt sources')
ensure(body['upstream']['variant_report']==task['p2_final'],'OUTPUT_INVALID','N18 used stale P2 report')
verified={}
def walk(value):
    if isinstance(value,dict):
        if {'artifact_id','sha256','size_bytes','run_id','job_id','role'} <= set(value) and value.get('job_id'):
            if value['artifact_id'] in verified:
                ensure(verified[value['artifact_id']]==value,'HASH_MISMATCH','Conflicting ArtifactRef')
                return
            ensure(value['run_id']==run_id,'FORBIDDEN','Foreign ArtifactRef in N18')
            job=rt.get(value['job_id'])
            ensure(value in job['artifacts'],'FORBIDDEN','Unregistered ArtifactRef in N18')
            raw=rt.artifact_bytes(value['job_id'],value['artifact_id'])
            ensure(sha(raw)==value['sha256'] and len(raw)==value['size_bytes'],'HASH_MISMATCH','Nested artifact differs')
            verified[value['artifact_id']]=value
        for child in value.values():walk(child)
    elif isinstance(value,list):
        for child in value:walk(child)
walk(v)
expected=package(body,files,data)
published={r['path']:r['artifact'] for r in v['raw_artifacts']}
exports={}
for path,raw in expected.items():
    ref=published[path];actual=rt.artifact_bytes(j['job_id'],ref['artifact_id'])
    ensure(actual==raw,'OUTPUT_INVALID','Published ZIP/report differs from reconstruction')
    exports[path.split('/')[-1]]=dict(artifact=ref,data=base64.b64encode(raw).decode())
exports['agent-c-preview.json']=dict(data=base64.b64encode(encode(data['agent_c_preview'])).decode(),
    source=source(j),derivation='EXACT_N18_AGENT_C_PREVIEW_FIELD')
negative={}
for case in ('wrong_wt_sequence','wrong_final_artifact_hash','wrong_wt_structure','buildmodel_as_scan'):
    bad=copy.deepcopy(body)
    try:
        with rt._db() as db:
            if case=='wrong_wt_sequence':bad['protein_sequence']='A'+bad['protein_sequence'][1:]
            elif case=='wrong_final_artifact_hash':bad['upstream']['variant_report']['artifact']['sha256']='0'*64
            else:
                refjob=rt.get(body['upstream']['wt_reference']['job_id']);req=decode(rt._request_bytes(refjob))
                if case=='wrong_wt_structure':req['upstream']['structure']=task['wrong_structure']
                else:req['upstream']['foldx']=task['buildmodel']
                reference_sources(rt,db,req)
                raise AssertionError('Invalid N17 source accepted')
            sources(rt,db,bad)
    except RuntimeFault as exc:negative[case]=dict(rejected=True,code=exc.code)
    else:negative[case]=dict(rejected=False)
native={}
for name,src in task['scan_jobs'].items():
    sj=rt.get(src);sv=rt.result(src)
    ensure(sj['run_id']==run_id and sj['state']=='succeeded','OUTPUT_INVALID','Scan is not successful')
    native[name]=dict(job=sj,result=sv,files={})
    for r in sv['raw_artifacts']:
        raw=rt.artifact_bytes(src,r['artifact']['artifact_id'])
        native[name]['files'][r['path']]=dict(artifact=r['artifact'],data=base64.b64encode(raw).decode())
test=data['variant_report']['m1_test'];scan=data['n17_execution']
checks=dict(report_rebuilt=True,zip_rebuilt=True,nested_artifact_hashes=True,p1_parent_unchanged=True,
    same_run=True,p2_final_preserved=True,
    all_excluded=len(test['records'])==24 and all(r['disposition']=='EXCLUDED' for r in test['records']),
    representative_count=sum(r['selected_for_recomputation'] for r in test['records'])==3,
    unselected_count=sum(r['recomputation_state']=='NOT_SELECTED_NOT_COMPUTED' for r in test['records'])==21,
    new_native_scan_jobs=scan['verified_scan_jobs']==2,
    finite_scope=all(r['displayed_positions']==task['scan_scope']['scan_positions'] for r in scan['engines'].values()),
    full_thermompnn_retained=native['thermompnn']['result']['scan']['complete_native_output'] is True
       and scan['engines']['thermompnn']['native_prediction_count']==20*len(task['sequence']),
    n16_skipped=data['n16']['reason_code']=='NO_QUALIFIED_CANDIDATE' and data['n16']['dna'] is None,
    local_handoff_only=data['agent_c_preview']['payload'] is None and data['agent_c_preview']['sent'] is False,
    closed=data['scientific_release_gate']=='CLOSED' and v['usable_for_pipeline'] is False
       and v['production_status']=='NOT_DEPLOYED' and data['variant_report']['best_candidate'] is None,
    native_offline=all(r['execution']['resident_observation']['network_restriction']=='seccomp-local-sockets-only-v1' for r in scan['engines'].values()),
    native_stopped=all(r['execution']['stopped_confirmed'] is True and
       r['execution']['resident_receipt']['stopped_confirmed'] is True for r in scan['engines'].values()),
    source_rejections=all(r['rejected'] for r in negative.values()))
print(json.dumps(dict(checks=checks,run_id=run_id,delivery_job_id=j['job_id'],verified_artifacts=len(verified),
    negative_checks=negative,exports=exports,native=native,report_api_called=False,
    scientific_release_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')))
'''


def write_verified(path,item):
    raw=base64.b64decode(item['data'],validate=True)
    if 'artifact' in item:
        ref=item['artifact'];assert len(raw)==ref['size_bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256']
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():assert path.read_bytes()==raw,'Export changed: '+str(path)
    else:path.write_bytes(raw)
    return raw


def main():
    task=p.context();delivery=p.read(p.OUT/'local-delivery.json')
    task['p1_parent_snapshot']=p.read(p.p2.P1/'workflow-snapshot.json')['job']
    final=p.read(p.p2.OUT/'final-report.json')
    task.update(delivery_job_id=delivery['job']['job_id'],
        scan_jobs={n:p.read(p.OUT/(f+'.json'))['job']['job_id'] for n,f in [('foldx','foldx-r02'),('thermompnn','thermompnn')]},
        scan_scope=p.read(p.OUT/'scan-scope.json'),
        wrong_structure=final['request']['m1_test']['representatives'][0]['structure'],
        buildmodel=final['request']['upstream']['foldx'])
    result=p.p2.deploy.remote(p.PREAMBLE+AUDIT,task)
    exports=result.pop('exports');native=result.pop('native')
    for name,item in exports.items():
        assert Path(name).name==name
        write_verified(p.OUT/'delivery'/name,item)
    result['zip_files']=package((p.OUT/'delivery/package.zip').read_bytes(),delivery['result']['delivery'])
    for name,row in native.items():
        files=row.pop('files');p.save('native/'+name+'/task.json',row,immutable=True)
        for path,item in files.items():
            assert not Path(path).is_absolute() and '..' not in Path(path).parts
            write_verified(p.OUT/'native'/name/path,item)
    result['checks']['zip_readback']=True
    result['checks']['p1_p2_local_bytes_unchanged']=all(hashlib.sha256((p.ROOT/n).read_bytes()).hexdigest()==h
        for n,h in task['protected_evidence'].items())
    result['status']='M1_P3_WT_SCAN_LOCAL_DELIVERY_PASS' if all(result['checks'].values()) else 'M1_P3_INCOMPLETE'
    p.save('audit-summary.json',result)
    assert all(result['checks'].values()),result['checks']
    print(json.dumps(result))


if __name__=='__main__':main()
