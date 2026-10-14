"""R56 engineering arithmetic; scientific booleans remain null even for empty maps."""
import math
from decimal import Decimal
from itertools import combinations
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
    if len(ps)*(len(ps)-1)//2>10000:return layer('ENGINEERING_PAIRWISE_OUTPUT_LIMIT_10000',requested_positions=len(ps))
    pairs=[]
    for i,j in combinations(ps,2):
        coords=[side[str(p)]['atoms']['CA'] for side,p in ((wt,i),(wt,j),(variant,i),(variant,j))]
        ensure(all(len(v)==3 and all(type(x) in (int,float) and math.isfinite(x) for x in v) for v in coords),'OUTPUT_INVALID','Invalid CA coordinates')
        a=math.dist(coords[0],coords[1]);b=math.dist(coords[2],coords[3]);pairs.append(dict(positions=[i,j],wt_distance_a=a,variant_distance_a=b,delta_a=b-a))
    if not pairs:return layer('NO_PAIRWISE_DISTANCES_SINGLE_POINT',rmsd=None)
    return layer(None,math.sqrt(sum(r['delta_a']**2 for r in pairs)/len(pairs)),pairs=pairs,
        method='RMS_CHANGE_OF_MATCHED_CA_PAIR_DISTANCES_NO_SUPERPOSITION',unit='angstrom',
        rmsd=None,rmsd_reason='OI_N13_SUPERPOSITION_SCOPE_MIN_POINTS_MISSING_RESIDUES_UNDEFINED',
        engineering_threshold_pass=None)

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
    quality_ok=all(s['quality_condition'] is True for s in (w,v))
    l2=rsa_delta(w['rsa'],v['rsa'],ps) if quality_ok else layer('PAIRED_STRUCTURE_QUALITY_UNAVAILABLE_OR_LOW')
    l3=geometry(w['geometry'],v['geometry'],ps) if quality_ok else layer('PAIRED_STRUCTURE_QUALITY_UNAVAILABLE_OR_LOW')
    domains=[]
    if w['domains'] is not None and v['domains'] is not None and quality_ok:
        wi={(r['type'],r['start'],r['end']):r for r in w['domains']};vi={(r['type'],r['start'],r['end']):r for r in v['domains']}
        for key in sorted(set(wi)|set(vi)):
            result=geometry(w['geometry'],v['geometry'],positions([wi[key]],len(wt))) if key in wi and key in vi else layer('FUNCTIONAL_DOMAIN_PAIR_NOT_MATCHED')
            domains.append(dict(domain=list(key),observation=result))
    if v['hotspots'] is not None:positions(v['hotspots'],len(variant))
    l4=prediction(hot,v['hotspots']) if w.get('prediction_rule_profile')==v.get('prediction_rule_profile') else layer('PREDICTION_RULE_PROFILES_DIFFER')
    return dict(l1=l1,l2=l2,l3=dict(hotspot=l3,functional_domains=domains,functional_rmsd=None,
        functional_reason='NO_DOMAINS_TO_VALIDATE' if not domains else 'RMSD_METHOD_UNDEFINED',
        shape_similarity=layer('OI_N13_SHAPE_METHOD_UNDEFINED')),l4=l4,
        validation_positions=ps,formal_structural_preservation=None,formal_prediction_preservation=None,
        epitope_violation=None,epitope_soft_penalty=None,scientific_pass=None,review_required=True,
        review_reasons=['DEVELOPMENT_UNREVIEWED','NO_IEDB_E3_E4_IN_CURRENT_SCOPE','OI_028_EMPTY_AND_DEGRADED_SEMANTICS',
            'OI_N13_RMSD_SHAPE_ALIGNMENT_METHODS']+[f'{side}:{r}' for side,s in sides.items() for r in s['reasons']])

def evaluate(body,files):
    data=decode(files['input/paired-facts.json']);records=[]
    for pair in data['pairs']:
        observed=compare(body['protein_sequence'],pair['sequence'],pair['sides'])
        records.append(dict(variant_id=pair['variant_id'],pair_id=pair['pair_id'],sequence=pair['sequence'],sequence_sha256=sha(pair['sequence'].encode()),
            source_states=pair['sides'],observation=observed))
    return dict(kind='N13_PAIRED_ENGINEERING_OBSERVATIONS',base_report=body['upstream']['base_report'],records=records,
        source_receipts=decode(files['input/source-receipts.json']),scientific_pass=None,formal_delivery=False,
        review_reasons=[dict(code='N13_SCIENTIFIC_PROTECTION_UNSIGNED')],model_invocations=0,
        rule_basis={p.relative_to(policy.REPO).as_posix():sha(p.read_bytes()) for p in policy.AUTHORITY})

from . import policy
