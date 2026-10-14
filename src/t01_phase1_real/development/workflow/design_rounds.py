"""SOP T-01 step17 regeneration, separate from R35 threshold relaxation.

Only a complete S28 round with every candidate definitively rejected can take
this path. Missing checks and empty generation never count as rejection.
"""
from ...common import decode,ensure

ROUNDS=((24,.1),(48,.3),(64,.5))
NAMES=tuple(f'retry{r}_{kind}' for r in (1,2) for kind in ('design','rescore','design_audit','validation'))


def active(rows):
    view=dict(rows)
    for r in (1,2):
        if rows.get(f'retry{r}_design_audit',{}).get('state')=='succeeded':
            for k in ('design','rescore','design_audit','validation'):
                view[k]=rows.get(f'retry{r}_{k}',{})
    if rows.get('design',{}).get('confirmation') and view.get('design') is not rows['design']:
        view['design']=dict(view['design'],confirmation=rows['design']['confirmation'])
    return view


def disposition(generation,scoring):
    expected=[r['sample_number'] for r in generation['records']]
    rows=(scoring.get('engineering_rules') or {}).get('records') or []
    ensure(len(expected)==len(set(expected)) and expected==list(range(1,len(expected)+1)),
        'OUTPUT_INVALID','Generation sample inventory is incomplete')
    ensure([r['sample_number'] for r in rows]==expected,'OUTPUT_INVALID','Round must score every generated sample')
    ensure(all(r.get('passed') is None or type(r['passed']) is bool for r in rows),
        'OUTPUT_INVALID','Validation decisions must be booleans or explicit null')
    unknown=[r['sample_number'] for r in rows if r['passed'] is None]
    rejected=[r['sample_number'] for r in rows if r['passed'] is False]
    pool=[r['sample_number'] for r in rows if r['passed'] is True]
    return dict(status='VALIDATION_UNAVAILABLE' if unknown else 'ALL_REJECTED' if rows and not pool else
                'S28_REVIEW_REQUIRED',rejected=rejected,review_pool=pool,unavailable=unknown,
                complete_validation_passed=None,scientific_release=False)


def request(rt,body,rows,name):
    r=int(name[5]);kind=name[7:]
    prior='' if r==1 else 'retry1_'
    if rows.get(prior+'design_audit',{}).get('state')!='succeeded':return None,'PREVIOUS_ROUND_NOT_COMPLETE'
    validation=rows.get(prior+'validation',{})
    if validation.get('state')!='succeeded':return None,'S28_VALIDATION_NOT_COMPLETE'
    from .validation import verified_fact
    context=validation['validation_source']
    ensure(context['node']==prior+'validation','OUTPUT_INVALID','Retry validation round differs')
    decision=verified_fact(rt,context['workflow_job_id'],context['node'])
    from .service import source
    ensure(decision['source_jobs']['design']==source(rt,rows[prior+'design']),
           'OUTPUT_INVALID','Retry validation belongs to another generation')
    if decision['status']!='ALL_REJECTED':return None,decision['status']
    # Initial test counts do not constitute the specified 24-candidate round.
    previous=decode(rt._request_bytes(rt.get(rows[prior+'design']['job_id'])))
    ensure((previous['n_designs'],previous['sampling_temperature'])==ROUNDS[r-1],
        'OUTPUT_INVALID','Retry must follow the exact expert round sequence')
    ensure(len(decision['records'])==ROUNDS[r-1][0],'OUTPUT_INVALID','Retry requires the entire specified round')
    if kind=='design':
        return dict(previous,n_designs=ROUNDS[r][0],sampling_temperature=ROUNDS[r][1]),None
    if rows.get(f'retry{r}_design',{}).get('state')!='succeeded':return None,'RETRY_DESIGN_NOT_COMPLETE'
    if kind=='rescore':
        original=decode(rt._request_bytes(rt.get(rows['rescore']['job_id'])))
        return dict(original,n11_artifact=source(rt,rows[f'retry{r}_design'])['artifact'],
            sample_numbers=list(range(1,ROUNDS[r][0]+1)),
            baseline_artifact=source(rt,rows['rescore'])['artifact']),None
    if rows.get(f'retry{r}_rescore',{}).get('state')!='succeeded':return None,'RETRY_RESCORE_NOT_COMPLETE'
    original=decode(rt._request_bytes(rt.get(rows['design_audit']['job_id'])))
    return dict(original,upstream=dict(original['upstream'],n11=source(rt,rows[f'retry{r}_design']),
        esm_if1=source(rt,rows[f'retry{r}_rescore'])),sample_numbers=list(range(1,ROUNDS[r][0]+1))),None


def summary(rt,rows):
    rounds=[]
    for index,prefix in enumerate(('', 'retry1_', 'retry2_')):
        if rows.get(prefix+'design_audit',{}).get('state')!='succeeded':continue
        generation=rt.result(rows[prefix+'design']['job_id'])['generation']
        validation=rows.get(prefix+'validation',{})
        decision=validation.get('fact') if validation.get('state')=='succeeded' else dict(status='VALIDATION_UNAVAILABLE',review_pool=[],rejected=[],unavailable=[])
        rounds.append(dict(round_index=index,n_designs=len(generation['records']),
            sampling_temperature=ROUNDS[index][1],decision=decision,
            source_jobs={k:rows[prefix+k]['job_id'] for k in ('design','rescore','design_audit')}))
    return dict(rounds=rounds,exhausted=len(rounds)==3 and rounds[-1]['decision']['status']=='ALL_REJECTED',
        total_generated=sum(r['n_designs'] for r in rounds),scientific_release=False)
