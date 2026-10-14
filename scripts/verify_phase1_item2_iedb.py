"""Real local IEDB/BepiPred and N06/N07 branch check; no design workflow."""
import argparse
import json

import prepare_m1_p1_deploy as c
from verify_phase1_item2 import PRELUDE, save
from prepare_phase1_item2 import EVIDENCE


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['start','audit']);args=ap.parse_args()
    if args.action=='start':
        cases=json.loads((c.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/iedb-native-cases-r01.json').read_bytes())
        case=next(r for r in cases['cases'] if r['case']=='original-233')
        result=c.remote(PRELUDE+'''
body=dict(protein_sequence=p['sequence'],user_sequence_id='item2-existing-sequence-engineering-check',
    database_id='iedb-20260924-r01',database_manifest_sha256='96be17e60c108013d320558817037d081edbf8e3c0ed2f9facf83a2d818b6e12',
    thresholds=dict(identity_percent_min=70,query_coverage_percent_min=80),timeout_seconds=120)
n03=rt.submit_sequence(encode(body),'item2-iedb-r01','t01.real.blast');rt.dispatch(n03['job_id'])
n04=rt.submit_sequence_in_run(n03['run_id'],encode(dict(protein_sequence=p['sequence'],
    user_sequence_id=body['user_sequence_id'],timeout_seconds=180)),'item2-bepipred-r01','t01.real.bepipred');rt.dispatch(n04['job_id'])
print(json.dumps(dict(n03_job_id=n03['job_id'],n04_job_id=n04['job_id'],run_id=n03['run_id'])))
''',case)
        save('iedb-bepi-run-r01.json',result);print(json.dumps(result));return
    run=json.loads((EVIDENCE/'iedb-bepi-run-r01.json').read_bytes())
    result=c.remote(PRELUDE+'''
n03=rt.reconcile(p['n03_job_id']);n04=rt.reconcile(p['n04_job_id'])
assert n03['state']==n04['state']=='succeeded',(n03['state'],n04['state'])
sequence=decode(rt._request_bytes(n03))['protein_sequence']
prior=rt.result(n03['job_id'])['iedb_prior']
assert prior['iedb_hit'] and prior['epitope_regions'] and not prior['contact_residues']
assert prior['e4_status']=='unavailable'
assert all(r['mapping_coverage']['mapped_residues']==len(r['residue_mapping'])==r['mapping_coverage']['source_residues']
    and r['source_iedb_id'] for r in prior['epitope_regions'])
bepi=rt.result(n04['job_id']);assert bepi['postprocessing']['canonical_parameters']==dict(
    threshold=.1512,top_fraction=.2,min_peak_length=6,gap_tolerance=2)
body=dict(protein_sequence=sequence,user_sequence_id='item2-existing-sequence-engineering-check',timeout_seconds=60,
    bepipred_input=rt.source_input(n04['job_id'],'t01.real.bepipred'),
    netmhc_input=dict(state='not_provided',artifact=None,reason_code=None),
    blast_input=rt.source_input(n03['job_id'],'t01.real.blast'))
n06=rt.submit_sequence_in_run(n03['run_id'],encode(body),'item2-iedb-map-r01','t01.real.epitope_map')
n06=rt.dispatch(n06['job_id']);assert n06['state']=='succeeded'
mapping=rt.result(n06['job_id']);hotspots=mapping['epitopes']['b_cell_antigenic_hotspot_map']
assert hotspots['hotspots'] is None and hotspots['proof'] is None
gly=dict(protein_sequence=sequence,user_sequence_id=body['user_sequence_id'],
    hotspot_input=rt.n06_hotspot_input(n06['job_id'],sequence),timeout_seconds=60)
n07=rt.submit_sequence_in_run(n03['run_id'],encode(gly),'item2-iedb-glyco-r01','t01.real.glycosylation')
n07=rt.dispatch(n07['job_id']);assert n07['state']=='succeeded'
for job in (n03,n04,n06,n07):
    for artifact in job['artifacts']:rt.artifact_bytes(job['job_id'],artifact['artifact_id'])
print(json.dumps(dict(status='REAL_IEDB_BEPI_N06_N07_PASS',n03_job=n03,n03_result=rt.result(n03['job_id']),
    n04_job=n04,n04_result=bepi,n06_job=n06,n06_result=mapping,n07_job=n07,n07_result=rt.result(n07['job_id']),
    scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')))
''',run)
    save('iedb-bepi-chain-r01.json',result)
    print(json.dumps(dict(status=result['status'],e3_regions=len(result['n03_result']['iedb_prior']['epitope_regions']))))


if __name__=='__main__':main()
