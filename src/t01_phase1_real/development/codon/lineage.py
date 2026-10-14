"""Recursively verified same-run N15 engineering candidate; no scientific release."""
from ...common import decode,encode,ensure,sha


def verify(rt,db,body,run_id):
    if body['input_kind']=='INDEPENDENT_ENGINEERING_SEQUENCE':return {}
    from ..design_backend.source import sources as registered
    from ..variant_report.source import sources
    from ..variant_report.compute import evaluate
    binding=body['candidate_source'];src=binding['source'];job=rt._job(db,src['job_id'])
    ensure(job['run_id']==run_id and job['state']=='succeeded','FORBIDDEN','N16 requires successful N15 in the same run')
    req=decode(rt._request_bytes(job))
    files,values,_=registered(rt,db,dict(protein_sequence=req['protein_sequence'],upstream={'report':src}),
        producers={'report':'t01.real.variant_report'},enricher=lambda *a:None)
    nested,_,_=sources(rt,db,req)
    report=values['report']['report']
    ensure(report==evaluate(req,nested),'OUTPUT_INVALID','N15 candidate report differs from verified sources')
    selected=report.get('engineering_selection') or {}
    ensure(selected.get('sc10',{}).get('overall_pass') is True and binding['candidate_id'] in selected.get('top20',[]),
        'FORBIDDEN','Candidate is not in the N15 selected set or SC10 failed')
    rows=[r for r in report['records'] if r['id']==binding['candidate_id']]
    ensure(len(rows)==1 and rows[0]['sequence']==body['protein_sequence'] and
        rows[0]['sequence_sha256']==sha(body['protein_sequence'].encode()) and not rows[0].get('non_standard') and
        not rows[0].get('exclusion_reasons'),'OUTPUT_INVALID','Candidate sequence or exclusion differs')
    return {'input/candidate-lineage.json':encode(dict(source=src,candidate_id=binding['candidate_id'],run_id=run_id,
        sequence_sha256=sha(body['protein_sequence'].encode()),report_request_sha256=sha(rt._request_bytes(job)),
        qualification='ENGINEERING_ONLY',scientific_pass=None))}
