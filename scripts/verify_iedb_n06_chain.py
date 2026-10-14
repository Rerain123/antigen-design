"""Verify new same-run N03 evidence reaches N06 without historical reuse."""
import argparse
import json
import prepare_m1_p1_deploy as c
from verify_iedb_n03_native import OUT,PRELUDE


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['start','finish']);a=p.parse_args()
    source=next(r for r in json.loads((OUT/'jobs.json').read_bytes()) if r['case']=='original-233')
    if a.action=='start':
        r=c.remote(PRELUDE+'''
j=rt.get(p['job_id']);request=decode(rt._request_bytes(j))
b=dict(protein_sequence=request['protein_sequence'],user_sequence_id='N03 to N06 same-run engineering check',timeout_seconds=180)
child=rt.submit_sequence_in_run(j['run_id'],encode(b),'iedb-n06-bepipred-r01','t01.real.bepipred')
child=rt.dispatch(child['job_id'])
print(json.dumps(dict(job_id=child['job_id'],run_id=child['run_id'],state=child['state'])))
''',source)
        (OUT/'bepipred-job.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r));return
    source['bepipred_job_id']=json.loads((OUT/'bepipred-job.json').read_bytes())['job_id']
    r=c.remote(PRELUDE+'''
bepi=rt.reconcile(p['bepipred_job_id'])
if bepi['state'] not in ('succeeded','failed','timed_out','cancelled'):
 print(json.dumps(dict(state=bepi['state'],complete=False)))
else:
 assert bepi['state']=='succeeded',bepi
 blast=rt.reconcile(p['job_id']);assert blast['state']=='succeeded'
 request=decode(rt._request_bytes(blast));seq=request['protein_sequence']
 b=dict(protein_sequence=seq,user_sequence_id='N03 to N06 same-run engineering check',timeout_seconds=30,
   bepipred_input=rt.source_input(bepi['job_id'],'t01.real.bepipred'),
   netmhc_input=dict(state='not_provided',artifact=None,reason_code=None),
   blast_input=rt.source_input(blast['job_id'],'t01.real.blast'))
 j=rt.submit_sequence_in_run(blast['run_id'],encode(b),'iedb-n06-map-r01','t01.real.epitope_map');j=rt.dispatch(j['job_id'])
 result=rt.result(j['job_id']);assert j['state']=='succeeded',result
 e=result['epitopes'];bm=e['b_cell_epitope_map'];tm=e['t_cell_presentation_map'];hs=e['b_cell_antigenic_hotspot_map']
 regions=(bm.get('regions') or [])+(tm.get('evidence_regions') or [])
 assert len(regions)==len(rt.result(blast['job_id'])['iedb_prior']['epitope_regions'])
 assert all(row['evidence_provenance']['source_artifact']==b['blast_input']['artifact'] for row in regions)
 assert hs['hotspots'] is None and hs['proof'] is None and hs['status']=='review_required'
 for ref in j['artifacts']:rt.artifact_bytes(j['job_id'],ref['artifact_id'])
 print(json.dumps(dict(complete=True,job=j,result=result,summary=dict(state=j['state'],run_id=j['run_id'],
  same_run=blast['run_id']==bepi['run_id']==j['run_id'],b_regions=len(bm['regions']),t_regions=len(tm['evidence_regions']),
  all_iedb_source_ids_preserved=True,empty_hotspot_proof_invalidated=True,scientific_gate='CLOSED'))))
''',source)
    if r.get('complete'):(OUT/'n06-chain.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(r.get('summary',r),indent=2))


if __name__=='__main__':main()
