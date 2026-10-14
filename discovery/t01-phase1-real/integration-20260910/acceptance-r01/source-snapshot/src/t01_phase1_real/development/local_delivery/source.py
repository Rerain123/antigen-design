from ...common import decode,encode,ensure
from ..design_backend.source import sources as registered
from ..wt_reference.source import native
from . import policy

def enrich(rt,db,body,files,values,receipts):
    for name in policy.PRODUCERS:
        if 'input/'+name+'-request.json' not in files:continue
        req=decode(files['input/'+name+'-request.json'])
        if name=='wt_draft':
            from ..wt_draft.service import sources,evaluate
            field='draft'
            ensure(req['host_species']==body['host_species'],'OUTPUT_INVALID','WT host identity differs from delivery')
        elif name=='variant_report':
            from ..variant_report.source import sources
            from ..variant_report.compute import evaluate
            field='report'
        else:
            from ..wt_reference.source import sources
            from ..wt_reference.compute import evaluate
            field='reference'
        nested,_,nr=sources(rt,db,req)
        receipts[name]['upstream']=nr
        if name in values:ensure(values[name][field]==evaluate(req,nested),'OUTPUT_INVALID','Assembled source differs from recursive verification')
    # WT draft, report design base, and reference must name the same structure
    # when those paths supply one; matching protein sequence alone is insufficient.
    structures=[]
    if 'input/wt_draft-request.json' in files:
        structures.append(decode(files['input/wt_draft-request.json'])['upstream']['structure'])
    if 'input/wt_reference-request.json' in files:
        structures.append(decode(files['input/wt_reference-request.json'])['upstream']['structure'])
    if 'input/variant_report-request.json' in files:
        req=decode(files['input/variant_report-request.json'])
        for key in ('design_audit','foldx'):
            src=req['upstream'][key]
            if src:
                j=rt._job(db,src['job_id']);r=decode(rt._input(db,j['request_artifact'],j['run_id']))
                structures.append(r['upstream']['structure'] if key=='design_audit' else dict(job_id=r['structure_artifact']['job_id'],artifact=r['structure_artifact']))
    supplied=[s for s in structures if s is not None]
    ensure(not supplied or all(s==supplied[0] for s in supplied),'OUTPUT_INVALID','Delivery inputs refer to different WT structure batches')
    receipts['wt_identity']=dict(structure=supplied[0] if supplied else None)

def sources(rt,db,body):
    files,values,receipts=registered(rt,db,body,producers=policy.PRODUCERS,enricher=enrich)
    records={r['id']:r for r in (values.get('variant_report') or {}).get('report',{}).get('records',[])}
    dna=[]
    for i,binding in enumerate(body['dna_bindings']):
        subject=binding['subject'];src=binding['source']
        ensure(subject=='WT' or subject in records,'OUTPUT_INVALID','DNA subject is not a variant in this report')
        sequence=body['protein_sequence'] if subject=='WT' else records[subject]['sequence']
        def check(rt,db,request,extra,vals,recs):
            req=decode(extra['input/dna-request.json'])
            ensure(req['expression_host']==body['expression_host'],'OUTPUT_INVALID','DNA expression host differs')
            if 'dna' in vals:
                from ..codon.service import result
                job=rt._job(db,src['job_id']);v=vals['dna'];raw=native(rt,src,v)
                import copy
                replay=result(job,req,raw,copy.deepcopy(v['execution']),v.get('controlled_fault'))
                ensure(replay['dna']==v['dna'] and replay['status']==v['status'],'OUTPUT_INVALID','DNA validation differs from its native source')
        nf,nv,nr=registered(rt,db,dict(protein_sequence=sequence,upstream=dict(dna=src)),producers=dict(dna='t01.real.optimize_codons'),enricher=check)
        for n,data in nf.items():files['input/dna-'+str(i)+'/'+n]=data
        req=decode(nf['input/dna-request.json'])
        # Current N16 is explicitly independent, even if protein/host happen to match.
        reason='INDEPENDENT_ENGINEERING_DNA_NOT_BUSINESS_APPLICABLE' if req['input_kind']=='INDEPENDENT_ENGINEERING_SEQUENCE' else 'N16_BUSINESS_LINEAGE_UNAPPROVED'
        dna.append(dict(subject=subject,source=nr['dna'],sequence_matches=True,expression_host_matches=True,applicable=False,
            reason=reason,dna=None,source_status=(nv.get('dna') or {}).get('status')))
    files['input/dna-assessment.json']=encode(dna);receipts['dna']=dna
    files['input/source-receipts.json']=encode(receipts)
    return files,values,receipts
