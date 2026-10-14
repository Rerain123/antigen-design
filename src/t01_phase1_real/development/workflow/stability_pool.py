"""SOP T-01 step19b: all validated variants up to 40, otherwise verified S40 top40."""
import math
from ...common import decode,encode,ensure,sha


def choose(records,validation,scores):
    checks={r['sample_number']:r for r in validation['records']}
    ensure(len(checks)==len(validation['records'])==len(records) and set(checks)=={r['sample_number'] for r in records},
           'OUTPUT_INVALID','N14 validation inventory differs from original N11')
    selected=[];excluded=[]
    for r in records:
        check=checks[r['sample_number']]
        ensure(check['sequence_sha256']==r['sequence_sha256'],'OUTPUT_INVALID','N14 candidate sequence differs')
        reason='N12_VALIDATION_NOT_PASSED' if check['passed'] is not True else \
               'N11_PERMISSION_VIOLATION' if (r.get('permissions') or {}).get('violations') else \
               'WT_IDENTICAL_NO_MUTATION' if not r['mutations'] else None
        if reason:excluded.append(dict(sample_number=r['sample_number'],id=r['id'],reason=reason));continue
        selected.append({k:r[k] for k in ('id','sample_number','sequence_sha256','mutations')})
    eligible_count=len(selected);missing=[];deferred=[];rule='ALL_VALIDATED_UP_TO_40';reason=None
    if eligible_count>40:
        rule='VERIFIED_FIVE_DIMENSION_OVERALL_DESC_TOP40'
        missing=[r['sample_number'] for r in selected if r['sample_number'] not in scores]
        if missing:
            reason='N14_TOP40_REQUIRES_COMPLETE_RELIABLE_FIVE_DIMENSION_SCORES';selected=[]
        else:
            ensure(all(type(scores[r['sample_number']]) in (int,float) and math.isfinite(scores[r['sample_number']])
                       and 0<=scores[r['sample_number']]<=1 for r in selected),'OUTPUT_INVALID','Invalid N14 S40 score')
            selected.sort(key=lambda r:-scores[r['sample_number']])  # Stable source order for ties, disclosed below.
            deferred=[dict(id=r['id'],sample_number=r['sample_number'],reason='OUTSIDE_S40_TOP40') for r in selected[40:]]
            selected=selected[:40]
    if not eligible_count:reason='NO_VALIDATED_MUTANT_FOR_N14'
    return dict(selection_rule=rule,selected=selected,eligible_count=eligible_count,excluded=excluded,deferred=deferred,
        missing_five_dimension_scores=missing,reason_code=reason,
        tie_policy='STABLE_ORIGINAL_N11_ORDER_FIRST_VERSION',scientific_eligible=False)


def pool(rt,body,rows):
    from .service import source
    from ..variant_report.source import sources
    from ..variant_report.compute import preselection_rows
    from .validation import verified_fact
    context=rows.get('validation',{}).get('validation_source')
    if context is None:return None,'N14_S28_VALIDATION_REQUIRED'
    validation=verified_fact(rt,context['workflow_job_id'],context['node'])
    audit=source(rt,rows.get('design_audit'))
    ensure(validation['source_jobs']['design_audit']==audit,'OUTPUT_INVALID','N14 audit and validation differ')
    request=dict(protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
        upstream=dict(design_audit=audit,foldx=None),variant_source='N11_DESIGN_AUDIT',foldx_bindings=[],timeout_seconds=60)
    with rt._db() as db:files,values,_=sources(rt,db,request)
    records=preselection_rows(request,files,values)
    scores={};score_sources={}
    # Only already produced, same-candidate N10 observations may decide the cost cap.
    # New workflows provide every current candidate; older workflows retain their actual subset.
    initial=choose(records,validation,{})
    representatives=(rows.get('preselection',{}).get('fact') or {}).get('selected',[]) if initial['eligible_count']>40 else []
    from ..design_backend.source import sources as registered
    from ..developability.service import sources as dev_sources,evaluate as dev_evaluate
    from .candidate_developability import CHILDREN as N10_CHILDREN,observations
    complete_n10=any(n in rows for n in N10_CHILDREN)
    if complete_n10 and initial['eligible_count']>40:
        for item in observations(rt,body,rows,records,validation['run_id']):
            dev=(item['results']['developability'] or {}).get('developability')
            if dev and dev['overall_status']=='computed_unreviewed' and dev['stability_ddg'] is None:
                scores[item['sample_number']]=dev['overall_score']
                score_sources[str(item['sample_number'])]=item['sources']['developability']
    if complete_n10:representatives=[]
    for i,r in enumerate(representatives,1):
        row=rows.get('rep'+str(i)+'_developability',{})
        if row.get('state')!='succeeded':continue
        src=source(rt,row);job=rt.get(row['job_id'])
        ensure(job['run_id']==validation['run_id'],'FORBIDDEN','N14 five-dimensional score from another run')
        with rt._db() as db:
            nf,nv,_=registered(rt,db,dict(protein_sequence=r['sequence'],upstream={'developability':src}),
                              producers={'developability':'t01.real.developability'},enricher=lambda *a:None)
            req=decode(nf['input/developability-request.json']);verified,_,_=dev_sources(rt,db,req,validation['run_id'])
            native={item['path']:rt.artifact_bytes(job['job_id'],item['artifact']['artifact_id'])
                    for item in nv['developability']['raw_artifacts']}
            ensure(all(native.get(k)==v for k,v in verified.items()),'OUTPUT_INVALID','N14 N10 structure snapshot differs')
            expected=dev_evaluate(req,native)
            if 'weight_policy' not in nv['developability']['developability']:
                from ..developability.compute import summarize
                from .candidate_developability import FIELDS
                expected['developability']=summarize(req,*(expected[k] for k in FIELDS),legacy_weights=True)
        value=nv['developability']
        ensure(value['developability']==expected['developability'],'OUTPUT_INVALID','N14 S40 score differs from source')
        dev=value['developability'];score=dev['overall_score'];dims=dev['dimensions']
        if (dev['overall_status']=='computed_unreviewed' and dims['solubility']['reliable'] is True
                and dev['stability_ddg'] is None and type(score) in (int,float) and math.isfinite(score)):
            scores[r['sample_number']]=score;score_sources[str(r['sample_number'])]=src
    fact=choose(records,validation,scores)
    fact.update(validation_source=context,design_audit=audit,structure=source(rt,rows.get('structure')),
        candidate_inventory_sha256=sha(encode([{k:r[k] for k in ('id','sample_number','sequence_sha256','mutations')} for r in records])),
        five_dimension_scores={str(k):v for k,v in scores.items()},score_sources=score_sources,
        authority='AgentA_SOP_v10.5_20260902 T-01 step19b; C35 BuildModel 5 runs',
        n13_scope='Existing paired subset only; unassessed candidates stay unassessed in N15')
    reason=fact['reason_code']
    if reason is None:
        if rows.get('structure',{}).get('state')!='succeeded':reason='N14_WT_STRUCTURE_UNAVAILABLE'
        elif rt.result(rows['structure']['job_id'])['analysis']['quality']['quality']['confidence']=='low':reason='N14_LOW_CONFIDENCE_WT_SKIPPED'
        elif rows.get('wt_draft',{}).get('state')!='succeeded':reason='N14_MEMBRANE_STATUS_UNAVAILABLE'
        else:
            membrane=rt.result(rows['wt_draft']['job_id'])['draft']['gate']['basis'].get('is_membrane')
            if membrane is not False:reason='N14_MEMBRANE_WT_SKIPPED' if membrane else 'N14_MEMBRANE_STATUS_UNAVAILABLE'
    fact['reason_code']=reason;fact['pool_sha256']=sha(encode(fact))
    return fact,reason


def verify_report(rt,db,body):
    from . import service,engineering
    from .design_rounds import active
    parent=rt._job(db,body['n14_source']['workflow_job_id'])
    ensure(parent['tool_id']=='t01.real.local_workflow','FORBIDDEN','N14 workflow source required')
    ensure(parent.get('state') in ('running','succeeded') and not parent.get('stop_reason'),
           'INVALID_STATE','Stopped workflow cannot deliver N14 results')
    request=decode(rt._request_bytes(parent));rows=active(rt._execution(db,parent['job_id'])['nodes'])
    ensure(engineering.enabled(request) and request['protein_sequence']==body['protein_sequence'],
           'FORBIDDEN','N14 workflow identity differs')
    ensure(body['upstream']['design_audit']==service.source(rt,rows.get('design_audit')),
           'FORBIDDEN','N14 active round differs')
    fact,reason=pool(rt,request,rows);row=rows.get('stability',{})
    ensure(body['upstream']['foldx']==service.source(rt,row),'FORBIDDEN','N14 source differs from workflow child')
    if row.get('job_id'):
        job=service.verified(rt,request,'stability',row['job_id'],parent['run_id'],rows)
        ensure(job['state']=='succeeded' or service.recoverable_child_failure(request,'stability',job),
               'OUTPUT_INVALID','N14 failure is not a recoverable missing result')
        if job.get('attempt_id'):
            ensure(rt.execution(job['job_id']).get('tree_stopped') is True,'INVALID_STATE','N14 process stop is not confirmed')
        req=decode(rt._request_bytes(job))
        design=decode(rt._request_bytes(rt._job(db,rows['design']['job_id'])))
        ensure(fact is not None and reason is None and req['mode']=='buildmodel' and
            req['structure_artifact']==fact['structure']['artifact'] and
            req['fixed_positions']==design['constraints']['fixed_positions'] and
            req['variants']==[dict(variant_id=r['id'],mutations=r['mutations']) for r in fact['selected']] and
            req['scope_source']['source_id']=='N14 complete pool sha256='+fact['pool_sha256'],
            'OUTPUT_INVALID','N14 submitted pool differs from verified selection')
        if job['state']=='succeeded':
            ensure(body['foldx_bindings']==[dict(sample_number=r['sample_number'],variant_id=r['id']) for r in fact['selected']],
                   'OUTPUT_INVALID','N14 result bindings omit or mismatch a selected candidate')
        else:ensure(not body['foldx_bindings'],'OUTPUT_INVALID','Failed N14 cannot bind successful scores')
    else:
        if reason is None and rows.get('protection',{}).get('state') not in ('succeeded','skipped'):
            reason='N13_NOT_COMPLETE'
        ensure(not body['foldx_bindings'] and row.get('state')=='skipped' and row.get('reason_code')==reason,
               'OUTPUT_INVALID','N14 skipped pool reason differs')
    return dict(pool=fact,state=row.get('state'),reason_code=row.get('reason_code') or row.get('error_code'),source=body['upstream']['foldx'])
