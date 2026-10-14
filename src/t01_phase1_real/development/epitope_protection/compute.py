"""R56 engineering arithmetic; scientific booleans remain null even for empty maps."""
import math
from decimal import Decimal
import numpy as np
from ...common import decode,encode,ensure,sha

def layer(reason,value=None,**facts):
    return dict(status='NOT_COMPUTED' if reason else 'COMPUTED_UNREVIEWED',value=value,reason=reason,scientific_pass=None,**facts)

def positions(intervals,length):
    out=set()
    for r in intervals:
        ensure(type(r['start']) is int and type(r['end']) is int and 1<=r['start']<=r['end']<=length,'OUTPUT_INVALID','Interval outside paired sequence')
        out.update(range(r['start'],r['end']+1))
    return sorted(out)

def identity(wt,variant,ps):
    if ps is None:return layer('HOTSPOTS_UNAVAILABLE')
    if not ps:return layer('EMPTY_VALIDATION_INTERVAL')
    rows=[dict(position=p,wt=wt[p-1],variant=variant[p-1],identical=wt[p-1]==variant[p-1]) for p in ps]
    return layer(None,all(r['identical'] for r in rows),residues=rows,identity_fraction=sum(r['identical'] for r in rows)/len(rows))

def rsa_delta(wt,variant,ps):
    if ps is None:return layer('HOTSPOTS_UNAVAILABLE')
    if not ps:return layer('EMPTY_VALIDATION_INTERVAL')
    if wt is None or variant is None:return layer('PAIRED_RSA_UNAVAILABLE')
    rows=[]
    for p in ps:
        a,b=wt[p-1],variant[p-1]
        if a is None or b is None:return layer('RSA_MISSING_AT_VALIDATION_POSITION',missing_position=p)
        ensure(all(type(x) in (float,int) and math.isfinite(x) and 0<=x<=1 for x in (a,b)),'OUTPUT_INVALID','RSA outside [0,1]')
        rows.append(dict(position=p,wt=a,variant=b,delta=float(Decimal(str(b))-Decimal(str(a)))))
    delta=sum(Decimal(str(r['delta'])) for r in rows)/len(rows)
    return layer(None,float(delta),residues=rows,mean_wt=sum(r['wt'] for r in rows)/len(rows),mean_variant=sum(r['variant'] for r in rows)/len(rows),
        reference_threshold='delta > -0.15',engineering_threshold_pass=delta>Decimal('-.15'))

def geometry(wt,variant,ps):
    if ps is None:return layer('REGIONS_UNAVAILABLE')
    if not ps:return layer('EMPTY_VALIDATION_INTERVAL')
    if wt is None or variant is None:return layer('PAIRED_CA_UNAVAILABLE')
    missing=[p for p in ps if str(p) not in wt or str(p) not in variant or 'CA' not in wt[str(p)]['atoms'] or 'CA' not in variant[str(p)]['atoms']]
    if missing:return layer('MATCHED_CA_MISSING',missing_positions=missing)
    coords=[[side[str(p)]['atoms']['CA'] for p in ps] for side in (wt,variant)]
    ensure(all(len(v)==3 and all(type(x) in (int,float) and math.isfinite(x) for x in v)
        for points in coords for v in points),'OUTPUT_INVALID','Invalid CA coordinates')
    # Fit and score the exact same local set. No global fit, scaling, reflection,
    # rematching, or silent removal of missing residues (SOP step19 / N13 L3).
    if len(ps)<3:return layer('INSUFFICIENT_MATCHED_CA',matched_count=len(ps),rmsd=None)
    a,b=(np.asarray(points,dtype=float) for points in coords)
    ac,bc=a.mean(axis=0),b.mean(axis=0);x,y=a-ac,b-bc
    if min(np.linalg.matrix_rank(x),np.linalg.matrix_rank(y))<2:
        return layer('DEGENERATE_LOCAL_CA_GEOMETRY',matched_count=len(ps),rmsd=None)
    u,_,vt=np.linalg.svd(y.T@x)
    correction=np.eye(3);correction[2,2]=1 if np.linalg.det(u@vt)>0 else -1
    rotation=u@correction@vt;translation=ac-bc@rotation
    fitted=b@rotation+translation;distances=np.linalg.norm(fitted-a,axis=1)
    rmsd=float(np.sqrt(np.mean(distances**2)))
    residues=[dict(position=p,wt_address=wt[str(p)].get('address'),variant_address=variant[str(p)].get('address'),
        wt_raw_row=wt[str(p)].get('raw_rows',{}).get('CA'),variant_raw_row=variant[str(p)].get('raw_rows',{}).get('CA'),
        wt_ca=coords[0][i],variant_ca=coords[1][i],aligned_variant_ca=fitted[i].tolist(),distance_a=float(distances[i]))
        for i,p in enumerate(ps)]
    return layer(None,rmsd,rmsd=rmsd,method='LOCAL_CA_KABSCH_PROPER_ROTATION',unit='angstrom',
        fit_positions=ps,score_positions=ps,matched_count=len(ps),residues=residues,
        transform=dict(convention='variant_row_vector @ rotation + translation',rotation=rotation.tolist(),translation=translation.tolist()),
        reference_threshold='rmsd < 2.0 angstrom',engineering_threshold_pass=rmsd<2.0,
        acceptance_domain='COMPLETE_ONE_TO_ONE_SUBSTITUTION_MAPPING_AT_LEAST_3_NONCOLLINEAR_CA')

def prediction(wt,variant):
    if wt is None or variant is None:return layer('PAIRED_WEIGHTED_HOTSPOTS_UNAVAILABLE_OI_007_026')
    if not wt or not variant:return layer('EMPTY_PREDICTION_INTERVAL')
    def indexed(rows):
        keys=[(r['start'],r['end']) for r in rows]
        ensure(len(keys)==len(set(keys)),'OUTPUT_INVALID','Duplicate prediction interval')
        return dict(zip(keys,rows))
    a,b=indexed(wt),indexed(variant)
    if set(a)!=set(b):return layer('OI_N13_SPLIT_MERGE_SHIFT_ALIGNMENT_UNDEFINED',wt_intervals=list(a),variant_intervals=list(b))
    rows=[]
    for key in sorted(a):
        x,y=a[key].get('weighted_score'),b[key].get('weighted_score')
        if x is None or y is None:return layer('WEIGHTED_SCORE_UNAVAILABLE')
        ensure(all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in (x,y)),'OUTPUT_INVALID','Invalid weighted prediction score')
        rows.append(dict(start=key[0],end=key[1],wt=x,variant=y,absolute_delta=float(abs(Decimal(str(x))-Decimal(str(y))))))
    mean=sum(Decimal(str(r['absolute_delta'])) for r in rows)/len(rows)
    return layer(None,float(mean),intervals=rows,alignment='EXACT_IDENTICAL_INTERVALS_ONLY',reference_threshold='delta < 0.2',engineering_threshold_pass=mean<Decimal('.2'))

def compare(wt,variant,sides):
    ensure(len(wt)==len(variant),'OUTPUT_INVALID','N13 requires substitution-only paired coordinates')
    w,v=sides['wt'],sides['variant'];hot=w['hotspots'];ps=None if hot is None else positions(hot,len(wt))
    l1=identity(wt,variant,ps)
    # E3 stays a source for S-19; it is not silently promoted to an E4 contact.
    e4=w.get('e4_positions',[])
    validation=None if ps is None else sorted(set(ps)|set(e4))
    quality_ok=all(s['quality_condition'] is True for s in (w,v))
    l2=rsa_delta(w['rsa'],v['rsa'],validation) if quality_ok else layer('PAIRED_STRUCTURE_QUALITY_UNAVAILABLE_OR_LOW')
    l3=geometry(w['geometry'],v['geometry'],validation) if quality_ok else layer('PAIRED_STRUCTURE_QUALITY_UNAVAILABLE_OR_LOW')
    domains=[]
    if w['domains'] is not None:
        for region in w['domains']:
            result=geometry(w['geometry'],v['geometry'],positions([region],len(wt))) if quality_ok else layer('PAIRED_STRUCTURE_QUALITY_UNAVAILABLE_OR_LOW')
            domains.append(dict(domain=[region['type'],region['start'],region['end']],source_region=region,
                correspondence='WT_REGION_SAME_SEQUENCE_POSITIONS_SUBSTITUTION_ONLY',observation=result))
    functional_reason=('FUNCTIONAL_DOMAINS_UNAVAILABLE' if w['domains'] is None else 'NO_DOMAINS_TO_VALIDATE') if not domains else (
        'FUNCTIONAL_DOMAIN_NOT_EVALUATED' if any(r['observation']['value'] is None for r in domains) else None)
    functional_rmsd=None if functional_reason else max(r['observation']['value'] for r in domains)
    if v['hotspots'] is not None:positions(v['hotspots'],len(variant))
    l4=prediction(hot,v['hotspots']) if w.get('prediction_rule_profile')==v.get('prediction_rule_profile') else layer('PREDICTION_RULE_PROFILES_DIFFER')
    return dict(l1=l1,l2=l2,l3=dict(hotspot=l3,functional_domains=domains,functional_rmsd=functional_rmsd,
        functional_reason=functional_reason,
        shape_similarity=layer('OI_N13_SHAPE_METHOD_UNDEFINED')),l4=l4,
        validation_positions=validation,hotspot_positions=ps,e4_positions=e4,formal_structural_preservation=None,formal_prediction_preservation=None,
        epitope_violation=None,epitope_soft_penalty=None,scientific_pass=None,review_required=True,
        review_reasons=['DEVELOPMENT_UNREVIEWED','OI_028_EMPTY_AND_DEGRADED_SEMANTICS',
            'LOCAL_RMSD_ACCEPTANCE_DOMAIN_UNSIGNED','OI_N13_SHAPE_METHOD_UNDEFINED']+[f'{side}:{r}' for side,s in sides.items() for r in s['reasons']])

def evaluate(body,files):
    data=decode(files['input/paired-facts.json']);records=[]
    for entry in data['pairs']:
        indexed=data.get('format')=='PER_PAIR_V1'
        if indexed:
            ensure(sha(files[entry['path']])==entry['sha256'],'HASH_MISMATCH','Paired fact changed')
            pair=decode(files[entry['path']])
        else:pair=entry
        observed=compare(body['protein_sequence'],pair['sequence'],pair['sides'])
        states=pair['sides']
        if indexed:
            detail=files[entry['observation_path']]
            ensure(sha(detail)==entry['observation_sha256'] and decode(detail)==observed,
                'OUTPUT_INVALID','Pair observation differs from original geometry')
            # Detailed coordinates/residuals remain in the hashed per-pair artifact.
            # Avoid repeating whole WT/variant structures in every assembled result.
            def compact(value):
                if isinstance(value,dict):return {k:compact(v) for k,v in value.items() if k!='residues'}
                if isinstance(value,list):return [compact(v) for v in value]
                return value
            observed=compact(observed)
            observed['detail_source']=dict(path=entry['observation_path'],sha256=entry['observation_sha256'])
            states={name:dict(sequence_sha256=side['sequence_sha256'],structure_artifact=side['structure_artifact'],
                quality_condition=side['quality_condition'],reasons=side['reasons'],
                detail_source=dict(path=entry['path'],sha256=entry['sha256'],side=name)) for name,side in states.items()}
        if body['preselection'].get('selection_scope')=='ALL_VALIDATED':
            observed['l4_diagnostic']=observed['l4']
            observed['l4']=layer('OI_022_L4_TOP20_POOL_UNDEFINED')
            observed['review_reasons'].append('OI_022_L4_TOP20_POOL_UNDEFINED')
        records.append(dict(variant_id=pair['variant_id'],pair_id=pair['pair_id'],sequence=pair['sequence'],sequence_sha256=sha(pair['sequence'].encode()),
            source_states=states,observation=observed))
    return dict(kind='N13_PAIRED_ENGINEERING_OBSERVATIONS',preselection=body['preselection'],records=records,
        source_receipts=decode(files['input/source-receipts.json']),scientific_pass=None,formal_delivery=False,
        review_reasons=[dict(code='N13_SCIENTIFIC_PROTECTION_UNSIGNED')],model_invocations=0,
        rule_basis={p.relative_to(policy.REPO).as_posix():sha(p.read_bytes()) for p in policy.AUTHORITY})

from . import policy
