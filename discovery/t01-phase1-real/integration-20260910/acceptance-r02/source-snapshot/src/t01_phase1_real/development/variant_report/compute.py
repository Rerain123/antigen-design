"""Exact per-variant joins and persistent exclusions; unknowns never become passes."""
from ...common import decode,ensure,sha
from . import policy
from .ranking import hard_filter,stability

MISSING=[dict(field='epitope_violation / preservation',producer='N13',reason='NOT_EXECUTED',closes='N13 signed original/variant epitope and structure comparison'),
    dict(field='safety_excluded / host_similarity_flag',producer='S-23 / safety',reason='NO_REGISTERED_VARIANT_SAFETY',closes='Applicable registered variant safety result'),
    dict(field='devability.overall_score',producer='variant S-40 / N10 components',reason='VARIANT_RECOMPUTATION_MISSING_WT_OVERALL_NULL',closes='Variant six-dimensional recomputation and signed N10 missing components'),
    dict(field='formal mutation_burden',producer='S-28',reason='OI_008_UNSIGNED',closes='Scientific burden threshold signoff'),
    dict(field='objective_profile / candidate pools / ties / SC-10',producer='SOP step19b/20',reason='OI_009_010_011_022',closes='Applicable scientific rules, pool provenance and tie/failure decisions')]

def diff(wt,seq):
    ensure(len(wt)==len(seq),'OUTPUT_INVALID','Variant length differs')
    return [dict(position=p,wt=a,mut=b) for p,(a,b) in enumerate(zip(wt,seq),1) if a!=b]

def variants(body,files,values):
    wt=body['protein_sequence'];rows=[];fold_request=None
    if 'input/foldx-request.json' in files:fold_request=decode(files['input/foldx-request.json'])
    declared={v['variant_id']:v for v in (fold_request or {}).get('variants',[])}
    scored={r['variant_id']:r for r in (values.get('foldx') or {}).get('variant_ddg',[])}
    ensure(len(scored)==len((values.get('foldx') or {}).get('variant_ddg',[])),'OUTPUT_INVALID','Duplicate FoldX result ID')
    if body['variant_source']=='N11_DESIGN_AUDIT':
        if 'design_audit' in values:
            audit=values['design_audit']['audit']
            n11=decode(files['input/design/input/n11-result.json']) if 'input/design/input/n11-result.json' in files else None
            records={r['sample_number']:r for r in (n11 or {}).get('generation',{}).get('records',[])}
            for burden in audit['burden_records'] or []:
                n=burden['sample_number'];record=records[n];mutations=diff(wt,record['sequence'])
                ensure(mutations==[dict(position=m['position'],wt=m['wt_residue'],mut=m['mut_residue']) for m in burden['mutations']],
                    'OUTPUT_INVALID','Burden mutations differ from N11 exact diff')
                rows.append(dict(id='sample-'+str(n),sample_number=n,sequence=record['sequence'],mutations=mutations,burden=burden,
                    origin=dict(kind='N11_HISTORICAL_ENGINEERING',binding=n11['binding'])))
    else:
        for vid,v in declared.items():
            chars=list(wt)
            for m in v['mutations']:
                ensure(chars[m['position']-1]==m['wt'],'OUTPUT_INVALID','FoldX mutation WT differs')
                chars[m['position']-1]=m['mut']
            seq=''.join(chars)
            rows.append(dict(id=vid,sample_number=None,sequence=seq,mutations=diff(wt,seq),burden=None,
                origin=dict(kind='FOLDX_EXPLICIT_ENGINEERING_NOT_N11_CANDIDATE',
                    binding=(values.get('foldx') or {}).get('binding'),request_sha256=sha(files['input/foldx-request.json']),
                    source=body['upstream']['foldx'])))
    numbers={r['sample_number'] for r in rows}
    ensure(all(l['sample_number'] in numbers and l['variant_id'] in declared for l in body['foldx_bindings']),
        'OUTPUT_INVALID','Explicit link sample or FoldX variant is unavailable')
    links={l['sample_number']:l['variant_id'] for l in body['foldx_bindings']}
    for r in rows:
        vid=r['id'] if body['variant_source']=='FOLDX_EXPLICIT_ENGINEERING' else links.get(r['sample_number'])
        if vid is not None:
            ensure(r['mutations']==sorted(declared[vid]['mutations'],key=lambda m:m['position']),
                'OUTPUT_INVALID','FoldX variant ID points to a different exact sequence diff')
        r.update(sequence_sha256=sha(r['sequence'].encode()),foldx_variant_id=vid,foldx=scored.get(vid),
            stability_state='BOUND_UNREVIEWED' if vid in scored else 'UNAVAILABLE')
    return rows

def evaluate(body,files):
    receipts=decode(files['input/source-receipts.json'])
    values={n:decode(files['input/'+n+'-result.json']) for n in policy.PRODUCERS if receipts[n]['state']=='available'}
    rows=variants(body,files,values);audit=(values.get('design_audit') or {}).get('audit')
    n13=decode(files['input/n13-result.json']) if receipts.get('n13',{}).get('state')=='available' else None
    protection={r['variant_id']:r for r in (n13 or {}).get('protection',{}).get('records',[])}
    comparisons={r['sample_number']:r for r in (audit or {}).get('n11_comparison',[])}
    for r in rows:
        burden=r['burden'];n12=(burden or {}).get('n12_scoring_record');comp=comparisons.get(r['sample_number'])
        mutated={m['position'] for m in r['mutations']}
        override=any(p['constraint_override'] and p['position'] in mutated for p in audit['permissions']['per_residue']) if audit else None
        flags=dict(epitope_violation=None,safety_excluded=None,constraint_override=override,host_similarity_high=None,
            burden_exceeded=burden['engineering_thresholds']['aggregate_exceeded'] if burden else None)
        hf=hard_filter(flags);reasons=[]
        if n12 and n12['passed'] is False:reasons.append(dict(code=n12['reason_code'],source='N12 ESM-IF1',detail=n12))
        if comp and comp['violations']:reasons.append(dict(code='ENGINEERING_PERMISSION_VIOLATION',source='N11 permissions audit',detail=comp['violations']))
        reasons.extend(dict(code='ENGINEERING_'+name.upper(),source='SOP step20 / design audit',detail=flags[name]) for name in hf['reasons'])
        state='EXCLUDED' if reasons else 'UNDETERMINED'
        r.update(disposition=state,exclusion_reasons=reasons,esm_if1=n12,permissions=comp,
            engineering_hard_filter=dict(**hf,flags=flags,scientific=False),non_standard=override is True,
            qualification='DEVELOPMENT_UNREVIEWED',scientific_eligible=False,formal_hard_filter=None,
            stability_normalized_engineering=stability(r['foldx']['ddg_foldx']) if r['foldx'] else None,
            stability_units='kcal/mol',stability_source=receipts['foldx'],missing_conditions=MISSING+([
                dict(field='FoldX BuildModel',producer='N14',reason=receipts['foldx']['state'] if receipts['foldx']['state']!='available' else 'NO_EXACT_VARIANT_RESULT',closes='Exact WT/structure/sample/diff bound five-run result')] if not r['foldx'] else []),
            engineering_ranking=None,scientific_ranking=None)
        if n12 is None:r['missing_conditions']=r['missing_conditions']+[dict(field='ESM-IF1',producer='N12',reason='SAMPLE_SCORE_UNAVAILABLE',closes='Registered same-WT sample score')]
        r['n13']=protection.get(r['id'])
        r['n13_state']='ENGINEERING_OBSERVATIONS_AVAILABLE' if r['n13'] else receipts.get('n13',{}).get('state','NOT_EXECUTED')
        if r['n13_state']=='available':r['n13_state']='VARIANT_NOT_IN_N13_PAIR_SET'
        if r['n13'] is not None:
            ensure(r['n13']['sequence_sha256']==r['sequence_sha256'],'OUTPUT_INVALID','N13 variant sequence differs')
            r['missing_conditions']=[dict(item,reason='ENGINEERING_OBSERVATIONS_AVAILABLE_SCIENTIFIC_PROTECTION_UNSIGNED')
                if item['producer']=='N13' else item for item in r['missing_conditions']]
    excluded=[r['id'] for r in rows if r['disposition']=='EXCLUDED'];unknown=[r['id'] for r in rows if r['disposition']=='UNDETERMINED']
    return dict(kind='N14_N15_ENGINEERING_EVALUATION',variant_source=body['variant_source'],wt_sequence_sha256=sha(body['protein_sequence'].encode()),
        source_receipts=receipts,records=rows,summary=dict(total=len(rows),excluded=len(excluded),undetermined=len(unknown),retained=0),
        outcome='ALL_EXCLUDED' if rows and len(excluded)==len(rows) else 'INPUTS_UNAVAILABLE' if not rows else 'REVIEW_REQUIRED',
        failure_report=dict(code='NO_AVAILABLE_VARIANTS',excluded_ids=excluded,undetermined_ids=unknown,action='REVIEW_EXCLUSIONS_AND_MISSING_INPUTS_NO_SELECTION'),
        non_standard_ids=[r['id'] for r in rows if r['non_standard']],ranked_candidates=None,pareto_front=None,best_candidate=None,top20=None,
        ranking_blockers=[dict(item,reason='ENGINEERING_OBSERVATIONS_AVAILABLE_SCIENTIFIC_PROTECTION_UNSIGNED')
            if n13 and item['producer']=='N13' else item for item in MISSING],n12_original_rules=(audit or {}).get('n12_original_engineering_rules'),
        rule_basis=dict(sections=['SOP v10.5 T-01 step19b','SOP v10.5 T-01 step20','C35 BuildModel'],
            authority={p.relative_to(policy.REPO).as_posix():sha(p.read_bytes()) for p in policy.AUTHORITY}),
        formal_delivery=False,n13='ENGINEERING_OBSERVATIONS_AVAILABLE' if n13 else receipts.get('n13',{}).get('state','NOT_EXECUTED'),model_invocations=0,n12_disposition_changed=False,
        review_reasons=[dict(code='SCIENTIFIC_RANKING_AND_AGENT_C_CLOSED')])
