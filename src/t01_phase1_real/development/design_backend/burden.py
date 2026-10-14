"""C18/S-28 six dimensions with independent engineering threshold observations."""
from decimal import Decimal
from itertools import combinations
import math
from ...common import ensure


def distance(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))


def proximity(positions,regions,residues):
    if regions is None:return None,[],['REGIONS_UNAVAILABLE']
    if not regions:return 0.,[],[]
    rows=[];errors=[]
    for pos in positions:
        if any(r['start']<=pos<=r['end'] for r in regions):
            rows.append(dict(position=pos,distance_a=0.,within=True,reason='WITHIN_INTERVAL'));continue
        target=(residues.get(str(pos)) or {}).get('atoms')
        bounds=sorted({p for r in regions for p in (r['start'],r['end'])})
        if not target or any(not (residues.get(str(p)) or {}).get('atoms') or residues[str(p)].get('missing_heavy_atoms')
            for p in bounds+[pos]):
            rows.append(dict(position=pos,distance_a=None,within=None,reason='BOUNDARY_OR_MUTATION_ATOMS_MISSING'))
            errors.append('BOUNDARY_OR_MUTATION_ATOMS_MISSING');continue
        best=min(distance(a,b) for a in target.values() for p in bounds for b in residues[str(p)]['atoms'].values())
        rows.append(dict(position=pos,distance_a=best,within=best<=5.,reason=None))
    return (None if errors else sum(r['within'] for r in rows)/len(positions)),rows,sorted(set(errors))


def compute(wt,record,geometry,domains,hotspots,objective,scales):
    sequence=record['sequence']
    ensure(len(wt)==len(sequence),'OUTPUT_INVALID','Variant length differs from WT')
    mutations=[dict(position=i,wt_residue=a,mut_residue=b,source='ProteinMPNN') for i,(a,b) in enumerate(zip(wt,sequence),1) if a!=b]
    ensure(mutations==record['mutations'],'OUTPUT_INVALID','Declared N11 mutations differ from exact sequence diff')
    count=len(mutations);per=[]
    for m in mutations:
        a,b=m['wt_residue'],m['mut_residue']
        changes={k:float(abs(Decimal(str(scales[k][a]))-Decimal(str(scales[k][b])))) for k in ('charge','hydrophobicity','volume')}
        changes['polarity']=int((a in scales['polar'])!=(b in scales['polar']))
        per.append(dict(**m,**changes,chemical_exceeded=any(changes[k]>v for k,v in scales['thresholds']['chemical'].items())))
    chemical={k:float(sum(Decimal(str(r[k])) for r in per)) for k in ('charge','hydrophobicity','volume','polarity')}
    positions=[m['position'] for m in mutations];residues=geometry.get('residues') or {};pairs=[];reasons=[]
    for i,j in combinations(positions,2):
        atoms=[]
        for p in (i,j):
            atom='CA' if wt[p-1]=='G' else 'CB'
            atoms.append((residues.get(str(p)) or {}).get('atoms',{}).get(atom))
        d=distance(*atoms) if all(a is not None for a in atoms) else None
        pairs.append(dict(positions=[i,j],distance_a=d,atoms=['CA' if wt[p-1]=='G' else 'CB' for p in (i,j)],
            clustered=None if d is None else d<scales['thresholds']['spatial_distance'],
            adjacent=None if d is None else d<scales['thresholds']['epistasis_distance']))
    if any(r['distance_a'] is None for r in pairs):
        spatial=None;epistasis=None;reasons.append('MUTATION_PAIR_CB_OR_GLY_CA_MISSING')
    else:
        spatial=sum(r['clustered'] for r in pairs)/len(pairs) if pairs else 0.
        adjacent=sum(r['adjacent'] for r in pairs);epistasis='HIGH' if adjacent>=2 else 'MEDIUM' if adjacent==1 else 'LOW'
    if count:
        # No functional object is not a zero distance/burden observation.
        functional,fa,fr=(None,[],['CONFIRMED_EMPTY_NO_COMPARISON_OBJECT']) if domains==[] else proximity(positions,domains,residues)
        epitope,ea,er=proximity(positions,hotspots,residues)
        reasons += ['FUNCTIONAL_'+r for r in fr]+['EPITOPE_'+r for r in er]
    else:
        functional=None if domains==[] else 0.;epitope=0.;fa=[];ea=[]
        if domains==[]:reasons.append('FUNCTIONAL_CONFIRMED_EMPTY_NO_COMPARISON_OBJECT')
    values=dict(count=count,chemical=chemical,spatial_clustering=spatial,functional_proximity=functional,
        epitope_proximity=epitope,epistasis_risk=epistasis)
    limits=scales['thresholds'][objective]
    exceeded={k:None if values[k] is None else values[k]>limit for k,limit in limits.items()}
    exceeded.update(chemical=any(r['chemical_exceeded'] for r in per),epistasis_risk=None if epistasis is None else epistasis=='HIGH')
    aggregate=True if any(v is True for v in exceeded.values()) else None if any(v is None for v in exceeded.values()) else False
    return dict(sample_number=record['sample_number'],mutations=mutations,values=values,
        per_mutation_chemical=per,mutation_pairs=pairs,functional_distance_audit=fa,epitope_distance_audit=ea,
        review_reasons=sorted(set(reasons+['OI_008_ENGINEERING_THRESHOLDS_UNSIGNED','WT_STRUCTURE_SCIENTIFICALLY_UNREVIEWED'])),
        engineering_thresholds=dict(objective=objective,limits=limits,per_dimension_exceeded=exceeded,
            known_exceeded=[k for k,v in exceeded.items() if v is True],unavailable=[k for k,v in exceeded.items() if v is None],
            any_known_exceeded=any(v is True for v in exceeded.values()),aggregate_exceeded=aggregate),
        formal_mutation_burden=None,formal_burden_exceeded=None,hard_filter_eligible=False)
