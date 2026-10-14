"""Explicit M1 P2 test ranking over registered same-run calculations only."""
import math
from ...common import decode, encode, ensure, sha

PRODUCERS={'epitope_map':'t01.real.epitope_map','glycosylation':'t01.real.glycosylation',
           'developability':'t01.real.developability'}


def request(value):
    from ..epitope_protection.policy import source
    ensure(isinstance(value,dict) and set(value)=={'wt','representatives'},'INVALID_REQUEST','Exact M1 P2 sources required')
    ensure(isinstance(value['wt'],dict) and set(value['wt'])==set(PRODUCERS),'INVALID_REQUEST','Explicit WT comparators required')
    for item in value['wt'].values():
        ensure(item is not None,'INVALID_REQUEST','WT source missing');source(item)
    rows=value['representatives']
    ensure(isinstance(rows,list) and 1<=len(rows)<=64,'INVALID_REQUEST','At most 64 validated candidates')
    for row in rows:
        ensure(isinstance(row,dict) and set(row)=={'sample_number','prediction','structure',*PRODUCERS},
               'INVALID_REQUEST','Exact representative calculations required')
        ensure(type(row['sample_number']) is int and 1<=row['sample_number']<=64,'INVALID_REQUEST','Original generation sample number required')
        for name in ('prediction','structure',*PRODUCERS):
            ensure(row[name] is not None,'INVALID_REQUEST','Explicit result or failure source required');source(row[name])
    ensure(len({r['sample_number'] for r in rows})==len(rows),'INVALID_REQUEST','Duplicate representative')


def selection(rows):
    eligible=[r for r in rows if r.get('esm_if1') and type(r['esm_if1'].get('esm_if1_score')) in (int,float)
              and math.isfinite(r['esm_if1']['esm_if1_score']) and r['mutations']]
    ordered=sorted(eligible,key=lambda r:(r['disposition']=='EXCLUDED',-r['esm_if1']['esm_if1_score'],r['id']))
    return [r['sample_number'] for r in ordered[:3]]


def verified_preselection(rt,db,sequence,label,design_audit,validation_source=None,selection_scope=None):
    """Replay N11/N12 producers and persist only an internal representative fact."""
    from .source import sources
    from .compute import preselection_rows
    body=dict(protein_sequence=sequence,user_sequence_id=label,
        upstream=dict(design_audit=design_audit,foldx=None),variant_source='N11_DESIGN_AUDIT',
        foldx_bindings=[],timeout_seconds=60)
    files,values,receipts=sources(rt,db,body)
    ensure(receipts['design_audit']['state']=='available','OUTPUT_INVALID','N12 audit required for preselection')
    rows=preselection_rows(body,files,values)
    eligible=rows
    if validation_source is not None:
        from ..workflow.validation import verified_fact
        validation=verified_fact(rt,validation_source['workflow_job_id'],validation_source['node'])
        ensure(validation['source_jobs']['design_audit']==design_audit,'OUTPUT_INVALID','S28 validation audit differs')
        eligible=[r for r in rows if r['sample_number'] in validation['review_pool'] and r['disposition']!='EXCLUDED']
    ensure(selection_scope in (None,'ALL_VALIDATED') and (selection_scope is None or validation_source is not None),
           'INVALID_REQUEST','Full reassessment requires complete S28 validation')
    numbers=[r['sample_number'] for r in eligible if r['mutations']] if selection_scope else selection(eligible)
    projection=[dict(id=r['id'],sample_number=r['sample_number'],sequence=r['sequence'],
        sequence_sha256=r['sequence_sha256'],mutations=r['mutations'],esm_if1=r['esm_if1'],
        disposition=r['disposition'],exclusion_reasons=r['exclusion_reasons']) for r in rows]
    selected=[next(r for r in projection if r['sample_number']==n) for n in numbers]
    if validation_source is not None:
        for row in selected:
            row['validation']=next(r for r in validation['records'] if r['sample_number']==row['sample_number'])
    fact=dict(kind='N12_REPRESENTATIVE_PRESELECTION',source=design_audit,
        sample_numbers=numbers,records_sha256=sha(encode(projection)),total_records=len(rows),
        selected=selected,scientific_eligible=False)
    if validation_source is not None:fact['validation_source']=validation_source
    if selection_scope is not None:fact['selection_scope']=selection_scope
    return fact


def sources(rt,db,body,files,values,receipts):
    from ..design_backend.source import sources as registered
    from ..epitope_protection.source import side_enrich
    from ..n12_prediction_evidence import inspect
    from .compute import evaluate
    option=body['m1_test'];request(option)
    ensure(body['variant_source']=='N11_DESIGN_AUDIT' and body.get('n13_source') is not None,
           'INVALID_REQUEST','M1 P2 needs original design audit and N13 paired observations')
    # Evaluate the existing formal/exclusion record without enabling any qualification.
    base=evaluate({k:v for k,v in body.items() if k!='m1_test'},files)
    n13_request=decode(files['input/n13-request.json'])
    context=n13_request['preselection'].get('validation_source')
    selected=verified_preselection(rt,db,body['protein_sequence'],body['user_sequence_id'],
        body['upstream']['design_audit'],context,n13_request['preselection'].get('selection_scope'))['sample_numbers'] if context is not None else selection(base['records'])
    ensure([r['sample_number'] for r in option['representatives']]==selected,
           'OUTPUT_INVALID','Representatives differ from deterministic real-score selection')
    design_request=decode(files['input/design_audit-request.json'])
    scoring=design_request['upstream']['esm_if1']['artifact']
    run_id=scoring['run_id']
    ensure(all(r['run_id']==run_id for r in receipts.values() if r.get('verified')),
           'FORBIDDEN','M1 sources belong to another run')
    observations={};wt_requests={};wt_values={}
    def load(label,sequence,upstream,producers):
        sf,sv,sr=registered(rt,db,dict(protein_sequence=sequence,upstream=upstream),
                           producers=producers,enricher=lambda *args:None)
        ensure(all(r['run_id']==run_id for r in sr.values()),'FORBIDDEN','M1 side belongs to another run')
        for name,data in sf.items():files['input/m1/'+label+'/'+name]=data
        return sf,sv,sr
    wf,wv,wr=load('wt',body['protein_sequence'],option['wt'],PRODUCERS)
    for name in PRODUCERS:
        wt_requests[name]=decode(wf['input/'+name+'-request.json'])
        wt_values[name]=wv.get(name)
    observations['wt']=dict(sources=wr,results=wt_values)
    records={r['sample_number']:r for r in base['records']};observations['representatives']=[]
    n13_request=decode(files['input/n13-request.json'])
    pairs={r['variant_id']:r for r in n13_request['pairs']}
    host=decode(files['input/design/input/structure-request.json'])['host_species']
    for item in option['representatives']:
        row=records[item['sample_number']];seq=row['sequence'];vid=row['id']
        upstream={n:item[n] for n in ('structure',*PRODUCERS)}
        sf,sv,sr=load(vid,seq,upstream,dict(structure='t01.real.ingest_structure',**PRODUCERS))
        # Rebuild structural/epitope observations and recursively verify native predictors.
        paired_body=dict(protein_sequence=seq,upstream={'structure':item['structure'],'epitope_map':item['epitope_map'],'domains':None})
        registered(rt,db,paired_body,producers={'structure':'t01.real.ingest_structure','epitope_map':'t01.real.epitope_map','domains':'t01.real.domains'},enricher=side_enrich)
        pair=pairs.get(vid)
        ensure(pair is not None and pair['variant']['structure']==item['structure']
               and pair['variant']['epitope_map']==item['epitope_map'] and pair['wt']['epitope_map']==option['wt']['epitope_map'],
               'OUTPUT_INVALID','N13 paired sources differ from M1 recomputation')
        pj=rt._job(db,item['prediction']['job_id'])
        ensure(item['prediction']['artifact'] in pj['artifacts'] and item['prediction']['artifact']['role']=='result',
               'FORBIDDEN','Prediction result reference differs')
        linked=inspect(rt,db,scoring,item['sample_number'],pj['job_id'],host)
        structure_request=decode(sf['input/structure-request.json'])
        ensure(structure_request['structure_artifact']==linked['prediction']['structure_artifact'],
               'OUTPUT_INVALID','Structure assessment not derived from selected prediction')
        for name in PRODUCERS:
            req=decode(sf['input/'+name+'-request.json']);wt=wt_requests[name]
            ignored={'protein_sequence','user_sequence_id','structure_input','hotspot_input','bepipred_input','netmhc_input','blast_input'}
            ensure({k:v for k,v in req.items() if k not in ignored}=={k:v for k,v in wt.items() if k not in ignored},
                   'OUTPUT_INVALID','WT and variant parameters differ: '+name)
            ensure(sr[name]['execution_profile']==wr[name]['execution_profile'] and sr[name]['rule_profile']==wr[name]['rule_profile'],
                   'OUTPUT_INVALID','WT and variant versions differ: '+name)
            if name=='developability':
                ensure(req['structure_input']['artifact']==item['structure']['artifact'],'OUTPUT_INVALID','Variant developability uses another structure')
                ensure(wt['structure_input']['artifact']==design_request['upstream']['structure']['artifact'],'OUTPUT_INVALID','WT developability uses another structure')
            if name=='glycosylation':
                ensure(req['hotspot_input']['source']['artifact']==item['epitope_map']['artifact'] and wt['hotspot_input']['source']['artifact']==option['wt']['epitope_map']['artifact'],
                       'OUTPUT_INVALID','Glycosylation not bound to recomputed hotspot map')
            if name=='epitope_map':
                for predictor in ('bepipred','netmhc'):
                    a=req[predictor+'_input']['artifact'];b=wt[predictor+'_input']['artifact']
                    ensure(a is not None and b is not None and a['job_id']!=b['job_id'],'OUTPUT_INVALID','Variant predictor was not rerun')
                    aj=rt._job(db,a['job_id']);bj=rt._job(db,b['job_id'])
                    ensure(aj['run_id']==bj['run_id']==run_id and aj['execution_profile']==bj['execution_profile'],'OUTPUT_INVALID','Predictor version/run mismatch')
                    ar=decode(rt._request_bytes(aj));br=decode(rt._request_bytes(bj))
                    ensure({k:v for k,v in ar.items() if k not in ('protein_sequence','user_sequence_id')}==
                           {k:v for k,v in br.items() if k not in ('protein_sequence','user_sequence_id')},'OUTPUT_INVALID','Predictor parameters differ')
        observations['representatives'].append(dict(sample_number=item['sample_number'],sources=sr,
            results=sv,prediction=linked,comparison='SAME_PINNED_TOOL_PARAMETERS_DISTINCT_VERIFIED_SEQUENCE_AND_STRUCTURE'))
    files['input/m1-observations.json']=encode(observations)


def ranking(report,files):
    observation=decode(files['input/m1-observations.json'])
    reps={r['sample_number']:r for r in observation['representatives']};rows=[]
    ranked=sorted(report['records'],key=lambda r:(r['esm_if1'] is None or r['esm_if1']['esm_if1_score'] is None,
        -(r['esm_if1']['esm_if1_score'] if r['esm_if1'] and r['esm_if1']['esm_if1_score'] is not None else 0),r['id']))
    for r in ranked:
        evidence=reps.get(r['sample_number']);results=(evidence or {}).get('results',{})
        dev=(results.get('developability') or {}).get('developability')
        rows.append(dict(candidate_id=r['id'],sequence_sha256=r['sequence_sha256'],sample_number=r['sample_number'],
            test_rank=len(rows)+1 if r['esm_if1'] and r['esm_if1']['esm_if1_score'] is not None else None,
            esm_if1=r['esm_if1'],disposition=r['disposition'],exclusion_reasons=r['exclusion_reasons'],
            selected_for_recomputation=evidence is not None,
            recomputation_state='EXECUTED_WITH_GAPS' if evidence else 'NOT_SELECTED_NOT_COMPUTED',
            debug_only=r['disposition']=='EXCLUDED',prediction=(evidence or {}).get('prediction'),
            recomputation_sources=(evidence or {}).get('sources'),structure=(results.get('structure') or {}).get('analysis'),
            epitopes=(results.get('epitope_map') or {}).get('epitopes'),glycosylation=results.get('glycosylation'),
            developability=dev,n13=r['n13'],foldx=r['foldx'],foldx_source=r['stability_source'],
            missing_conditions=r['missing_conditions'],scientific_eligible=False))
        if evidence and dev is not None:
            rows[-1]['missing_conditions']=[m for m in r['missing_conditions'] if m['producer']!='variant S-40 / N10 components']+[
                dict(field='developability.'+name,reason=d['exclusion_reason'] or d['status'])
                for name,d in dev['dimensions'].items() if not d['included_in_overall']]
    scope=decode(files.get('input/n13-request.json',b'{}')).get('preselection',{}).get('selection_scope')
    return dict(purpose='M1_P2_INTERNAL_TEST_ONLY',selection='ALL_VALIDATED_CURRENT_ROUND_SOURCE_ORDER' if scope=='ALL_VALIDATED' else 'PREFER_NOT_EXCLUDED_THEN_ESM_IF1_DESC_CANDIDATE_ID_ASC_MAX_3',
        sort='ESM_IF1_DESC_CANDIDATE_ID_ASC',records=rows,wt=observation['wt'],
        scientific_release_gate='CLOSED',usable_for_pipeline=False,automatic_handoff=False,production_status='NOT_DEPLOYED',
        formal_ranking_changed=False,missing_data_policy='NULL_WITH_REASON_NO_ZERO_IMPUTATION')
