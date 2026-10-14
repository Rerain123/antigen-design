"""Resumable P1 run through the existing authenticated MCP workflow endpoint.

Never calls workflow.report (which can publish an object). The audit reads
registered artifacts from the retained run and preserves native evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import run_cluster_workflow_probe as probe
import prepare_m1_p1_deploy as deploy
from structure_integration_cases import cases, UBQ

OUT=ROOT/'discovery/t01-phase1-real/m1-p1-20260921/r01'


def request():
    case=next(c for c in cases() if c['name']=='rsa-out-of-domain')
    b=probe.request_document('provided')
    b['user_sequence_id']='M1 P1 1UBQ explicit internal design test'
    b['structure']={k:v for k,v in case['request'].items() if k not in ('protein_sequence','host_species')}
    b['structure']['structure_name']='1UBQ-m1-test.pdb'
    b['analysis']['blast']=dict(database_id='engineering-n03',
        database_manifest_sha256=probe.sha((deploy.DATABASE/'manifest.json').read_bytes()),
        thresholds=dict(identity_percent_min=80,query_coverage_percent_min=80),timeout_seconds=120)
    b['m1_test']=dict(constraints=dict(purpose='ENGINEERING_EXPLICIT_MASKS',
        source_id='M1-P1-20260921 explicit test: termini fixed, position 2 A/Q; other sites open; no scientific permission inference',
        fixed_positions=[1,76],restricted_positions=[dict(position=2,allowed_residues='AQ')],
        open_positions=list(range(3,76))),n_designs=24,sampling_temperature=0.1,seed=17,timeout_seconds=300)
    return b,case


AUDIT=r'''
import json,sys,hashlib
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import encode,decode,ensure
from t01_phase1_real.development import Runtime
task=json.load(sys.stdin)
rt=Runtime(Path('/var/lib/t01/runtime'),scope='svc-'+task['owner'][:24],
           blast_database_root=Path('/var/lib/t01/m1-p1-test-data/blast'))
j=rt.get(task['job_id']);snap=rt.workflow(j['job_id'])
nodes=snap['nodes'];records={};artifacts=0
for name,row in nodes.items():
    if not row.get('job_id'):continue
    child=rt.get(row['job_id'])
    ensure(child['run_id']==j['run_id'],'FORBIDDEN','Foreign child run')
    request=decode(rt._request_bytes(child))
    ensure(request['protein_sequence']==task['request']['protein_sequence'],'OUTPUT_INVALID','Sequence differs')
    for ref in child['artifacts']:
        rt.artifact_bytes(child['job_id'],ref['artifact_id']);artifacts+=1
    records[name]=dict(job=child,request=request,execution=rt.execution(child['job_id']))
    if child['artifacts']:
        records[name]['result']=rt.result(child['job_id'])
design=records.get('design',{})
value=design.get('result',{})
generation=value.get('generation') or {}
native=generation.get('engine_runtime') or {}
ex=design.get('execution',{})
gate=snap['design_applicability_gate']
checks=dict(
    parent_succeeded=j['state']=='succeeded',
    same_run_artifacts_verified=True,
    known_suitable=gate is not None and gate['status']=='SUITABLE_FOR_DESIGN',
    explicit_m1=snap['internal_test']['selected'] and snap['internal_test']['eligible_for_n11'],
    upstream_executed=all(nodes[n]['state']=='succeeded' for n in
        ('structure','topology','bepipred','netmhc','epitope_map','glycosylation','developability','wt_draft')),
    blast_honest=nodes['blast']['state'] in ('succeeded','failed','unavailable'),
    n11_executed=design.get('job',{}).get('state')=='succeeded' and native.get('tool_invoked') is True,
    generated_24=generation.get('generated_count')==24,
    non_wt=any(not r['is_wt'] for r in generation.get('records',[])),
    a100=native.get('gpu_name')=='NVIDIA A100-SXM-64GB',
    process_stopped=ex.get('tree_stopped') is True and (ex.get('resident_receipt') or {}).get('stopped_confirmed') is True,
    explicit_masks=value.get('binding',{}).get('constraints_sha256')==hashlib.sha256(encode(task['request']['m1_test']['constraints'])).hexdigest(),
    closed_release=snap['scientific_release_gate']=='CLOSED' and snap['usable_for_pipeline'] is False
        and gate is not None and gate['n11_release'] is False and value.get('usable_for_pipeline') is False
        and value.get('automatic_handoff') is False and value.get('production_status')=='NOT_DEPLOYED',
    receipt_bound=(nodes.get('design',{}).get('internal_test_input') or {}).get('configuration')==task['request']['m1_test'],
    no_historical_reuse=all(r.get('origin')!='HISTORICAL_REUSE' for r in nodes.values()),
)
summary=dict(status='M1_P1_UPSTREAM_TO_N11_PASS' if all(checks.values()) else 'M1_P1_INCOMPLETE',
    checks=checks,run_id=j['run_id'],job_id=j['job_id'],verified_artifacts=artifacts,
    generated_count=generation.get('generated_count'),non_wt_count=sum(not r['is_wt'] for r in generation.get('records',[])),
    scientific_release_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED',
    p2_p4_executed=False,report_api_called=False,formal_database_connected=False)
print(json.dumps(dict(summary=summary,snapshot=snap,records=records)))
'''


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','start','status','audit'])
    parser.add_argument('--batch',default='r01')
    args=parser.parse_args()
    import re
    if not re.fullmatch(r'r\d{2,4}',args.batch):raise ValueError('Invalid batch')
    OUT=OUT.parent/args.batch
    probe.OUT=OUT
    probe.FIXTURE=OUT/'1UBQ-m1-test.pdb'
    if args.action=='prepare':
        b,case=request()
        OUT.mkdir(parents=True,exist_ok=False)
        probe.FIXTURE.write_bytes(case['data'])
        probe.save('batch.json',dict(idempotency_key='m1-p1-20260921-'+args.batch,
            input_mode='provided',request=b,input_sha256=probe.sha(case['data']),sequence_sha256=probe.sha(UBQ.encode())))
        probe.save('input-provenance.json',dict(fixture='rsa-out-of-domain',
            original=case['expected']['reference'],
            original_sha256=probe.sha((ROOT/case['expected']['reference']).read_bytes()),
            derivative_sha256=probe.sha(case['data']),occupancy_changes=case['expected']['occupancy_changes'],
            coordinates_changed=False,quality_metadata='EXPLICIT_ENGINEERING_DERIVATIVE_NOT_SCIENTIFIC_REFERENCE',
            rsa='KNOWN_OUT_OF_DOMAIN_PRESERVE_MISSING',
            homology='UNAVAILABLE_NO_REGISTERED_1UBQ_COVERAGE',domains='UNAVAILABLE_NO_REGISTERED_1UBQ_ANNOTATIONS',
            blast='REGISTERED_MINIMAL_ENGINEERING_DATABASE_NOT_TARGET_DATABASE',
            constraints='EXPLICIT_TEST_ONLY_NOT_DERIVED_FROM_UNKNOWN_ANNOTATIONS'))
        print('M1_P1_PREPARED',OUT);return
    batch=json.loads((OUT/'batch.json').read_bytes())
    if args.action=='start':probe.start(batch)
    elif args.action=='status':probe.status(batch)
    else:
        result=deploy.remote(AUDIT,batch)
        for name,row in result['records'].items():
            probe.save(name+'.json',row)
        probe.save('workflow-snapshot.json',result['snapshot'])
        probe.save('audit-summary.json',result['summary'])
        print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':main()
