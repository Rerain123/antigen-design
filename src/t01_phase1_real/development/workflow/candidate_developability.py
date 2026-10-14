"""All current S28 candidates: native N10 inputs before N14, no WT substitution."""
from ...common import decode,encode,ensure,sha

CHILDREN={f'c_s{n}_{kind}':kind for n in range(1,65) for kind in ('structure','developability')}
ORDER=tuple(CHILDREN)
FIELDS=('expressibility','tag_exposure','ph_stability','aggregation','solubility')


def number(name):
    ensure(name in CHILDREN,'INVALID_REQUEST','Unknown candidate N10 child')
    return int(name.split('_')[1][1:])


def candidate(rt,rows,name):
    from .design_rounds import active
    rows=active(rows);n=number(name)
    generated=rt.result(rows['design']['job_id'])['generation']['records']
    found=[r for r in generated if r['sample_number']==n]
    ensure(len(found)==1,'OUTPUT_INVALID','Candidate absent from active N11 round')
    return found[0]


def request(rt,body,rows,name,*,verified_facts=None):
    from .design_rounds import active
    from .validation import verified_fact
    from .service import typed,source
    rows=active(rows);context=rows.get('validation',{}).get('validation_source')
    if context is None:return None,'N10_CANDIDATE_VALIDATION_UNAVAILABLE'
    # Reuse only a replay performed in this dispatcher traversal. No persistent
    # trusted flag/cache: each tick and every final consumer replays the sources.
    # Admission still rehashes every upstream artifact before creating a child.
    key=(context['workflow_job_id'],context['node'])
    fact=(verified_facts or {}).get(key)
    if fact is None:fact=verified_fact(rt,*key)
    else:ensure(rows['validation'].get('fact')==fact,'OUTPUT_INVALID','Validation changed during traversal')
    ensure(fact['source_jobs']['design']==source(rt,rows.get('design')) and
        fact['source_jobs']['design_audit']==source(rt,rows.get('design_audit')),
        'OUTPUT_INVALID','N10 validation does not belong to the active generation')
    n=number(name);check=next((r for r in fact['records'] if r['sample_number']==n),None)
    if check is None or check['passed'] is not True:return None,'N10_CANDIDATE_NOT_VALIDATED'
    original=candidate(rt,rows,name);seq=original['sequence']
    ensure(sha(seq.encode())==check['sequence_sha256'],'OUTPUT_INVALID','N10 candidate sequence differs from S28')
    if CHILDREN[name]=='structure':
        if check['selected'] is None:return None,'N10_CANDIDATE_NO_STRUCTURE'
        engine=check['selected']
        return dict(protein_sequence=seq,host_species=body['host_species'],structure_artifact=check['structure'],
            structure_name=engine+'.cif',declared_format='MMCIF',selection=dict(model_index=0,chain_selector='A'),
            context_chain_ids=['A'],source_declaration=dict(kind='predicted',note=engine+' job '+check['engines'][engine]['source']['job_id']),timeout_seconds=120),None
    option=body['analysis']['developability']
    if option is None:return None,'N10_NOT_REQUESTED'
    return dict(option,protein_sequence=seq,user_sequence_id=body['user_sequence_id'],
        structure_input=typed(rt,rows,f'c_s{n}_structure')),None


def reuse(rt,body,rows,name,req,run_id):
    """Reuse an already computed representative only if its exact request matches."""
    from .service import verified
    from .design_rounds import active
    rows=active(rows)
    kind=CHILDREN[name];n=number(name)
    selected=(rows.get('preselection',{}).get('fact') or {}).get('selected',[])
    for i,r in enumerate(selected,1):
        old=rows.get(f'rep{i}_{kind}',{})
        if r['sample_number']!=n or old.get('state')!='succeeded':continue
        job=verified(rt,body,name,old['job_id'],run_id,rows)
        actual=decode(rt._request_bytes(job))
        if {k:v for k,v in actual.items() if k!='timeout_seconds'}=={k:v for k,v in req.items() if k!='timeout_seconds'}:
            return job['job_id']
    return None


def verified_value(rt,db,src,seq,run_id):
    from ..design_backend.source import sources as registered
    from ..developability.service import sources,evaluate
    from ..developability.compute import summarize
    nf,nv,_=registered(rt,db,dict(protein_sequence=seq,upstream={'developability':src}),
        producers={'developability':'t01.real.developability'},enricher=lambda *a:None)
    job=rt._job(db,src['job_id']);ensure(job['run_id']==run_id,'FORBIDDEN','N10 candidate belongs to another run')
    if job['state']!='succeeded':return None
    value=nv['developability'];req=decode(nf['input/developability-request.json'])
    verified,_,_=sources(rt,db,req,run_id)
    native={item['path']:rt.artifact_bytes(job['job_id'],item['artifact']['artifact_id']) for item in value['raw_artifacts']}
    ensure(all(native.get(k)==v for k,v in verified.items()),'OUTPUT_INVALID','N10 native structure snapshot differs')
    expected=evaluate(req,native)
    components=value.get('steps') or {}
    ensure(all(components.get(k)==expected[k] for k in FIELDS),'OUTPUT_INVALID','N10 native components differ')
    prior=summarize(req,*(expected[k] for k in FIELDS),legacy_weights='weight_policy' not in value['developability'])
    ensure(value['developability']==prior,'OUTPUT_INVALID','N10 published summary differs from native components')
    # A fresh derived summary uses current defaults; archived source bytes stay intact.
    return dict(value,developability=expected['developability'])


def observations(rt,body,rows,records,run_id,*,verify_requests=True):
    from .service import source,verified,recoverable_child_failure
    result=[];verified_facts={}
    for r in records:
        name=f'c_s{r["sample_number"]}_developability';row=rows.get(name,{})
        src=source(rt,row);value=None
        if src:
            job=verified(rt,body,name,row['job_id'],run_id,rows)
            ensure(job['state']=='succeeded' or recoverable_child_failure(body,name,job),'OUTPUT_INVALID','Invalid candidate N10 terminal')
            if job.get('attempt_id'):ensure(rt.execution(job['job_id']).get('tree_stopped') is True,'INVALID_STATE','N10 candidate process not stopped')
            if verify_requests:
                from .design_rounds import active
                from .validation import verified_fact
                context=active(rows)['validation']['validation_source']
                key=(context['workflow_job_id'],context['node'])
                if key not in verified_facts:verified_facts[key]=verified_fact(rt,*key)
                expected,why=request(rt,body,rows,name,verified_facts=verified_facts);actual=decode(rt._request_bytes(job))
                ensure(expected is not None and {k:v for k,v in actual.items() if k!='timeout_seconds'}==
                    {k:v for k,v in expected.items() if k!='timeout_seconds'},'OUTPUT_INVALID','N10 candidate source/configuration differs')
                structure=rows.get(f'c_s{r["sample_number"]}_structure',{})
                if structure.get('job_id'):
                    sj=verified(rt,body,f'c_s{r["sample_number"]}_structure',structure['job_id'],run_id,rows)
                    se,_=request(rt,body,rows,f'c_s{r["sample_number"]}_structure',verified_facts=verified_facts);sa=decode(rt._request_bytes(sj))
                    ensure(se is not None and {k:v for k,v in sa.items() if k!='timeout_seconds'}==
                        {k:v for k,v in se.items() if k!='timeout_seconds'},'OUTPUT_INVALID','N10 structure not from selected S28 prediction')
            with rt._db() as db:value=verified_value(rt,db,src,r['sequence'],run_id)
        result.append(dict(sample_number=r['sample_number'],sequence_sha256=r['sequence_sha256'],
            sources={'developability':src},state=row.get('state','not_executed'),reason_code=row.get('reason_code'),
            results={'developability':value}))
    return result


def report_sources(rt,db,body,records):
    from .design_rounds import active
    parent=rt._job(db,body['n14_source']['workflow_job_id']);request_body=decode(rt._request_bytes(parent))
    rows=active(rt._execution(db,parent['job_id'])['nodes'])
    if not any(name in rows for name in CHILDREN):return None
    return dict(records=observations(rt,request_body,rows,records,parent['run_id']),
        scope='ALL_CURRENT_ROUND_CANDIDATES',authority='SOP v10.5 S-40 and T-01 step19b')
