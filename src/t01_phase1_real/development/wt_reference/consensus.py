"""SOP S-31 R-40: compare native engine ranks, never average energies.

FoldX's registered rank is per-position AA20; ThermoMPNN's registered rank
is across requested non-self substitutions. Keep their denominators explicit.
Unspecified combinations are review gaps, not invented low consensus.
"""
from ...common import ensure


def classify(a,b):
    if a is None and b is None:return 'no_consensus'
    if a is None or b is None:return 'single_engine'
    if a<=.2 and b<=.2:return 'high_consensus'
    if min(a,b)<=.2 and max(a,b)<=.5:return 'medium_consensus'
    if min(a,b)>.5:return 'low_consensus'
    return None


def evaluate(engines):
    if any(e.get('coverage',{}).get('duplicate_mutation_count',0) or
           (e['records'] and e.get('coverage',{}).get('complete') is False) for e in engines.values()):
        return dict(records=[],reason='SCAN_REQUESTED_SCOPE_INCOMPLETE',scientific_pass=None,
            authority='SOP v10.5 S-31 R-40',absolute_energies_combined=False)
    indexed={};percentiles={}
    for name in ('foldx','thermompnn'):
        rows=engines[name]['records'];indexed[name]={};percentiles[name]={}
        counts={p:sum(r['position']==p for r in rows) for p in {r['position'] for r in rows}}
        total=sum(r['wt']!=r['mut'] for r in rows)
        for r in rows:
            key=(r['position'],r['wt'],r['mut'])
            ensure(key not in indexed[name],'OUTPUT_INVALID','Duplicate mutation in consensus')
            indexed[name][key]=r
            rank=r.get('rank_'+name);denominator=counts[r['position']] if name=='foldx' else total
            if rank is not None:
                ensure(type(rank) is int and 1<=rank<=denominator,'OUTPUT_INVALID','Invalid engine rank')
                percentiles[name][key]=dict(rank=rank,comparison_count=denominator,fraction=rank/denominator)
    out=[]
    for key in sorted(set(indexed['foldx'])|set(indexed['thermompnn'])):
        if key[1]==key[2]:continue  # WT self is coverage evidence, not a mutation proposal.
        pair={n:percentiles[n].get(key) for n in indexed}
        a,b=(pair[n]['fraction'] if pair[n] else None for n in indexed)
        present=[key in indexed[n] for n in indexed]
        rank=classify(a,b)
        missing_rank=any(exists and pair[n] is None for exists,n in zip(present,indexed))
        if missing_rank:rank=None
        out.append(dict(position=key[0],wt=key[1],mut=key[2],consensus_rank=rank,engines=pair,
            ddg={n:indexed[n].get(key,{}).get('ddg_'+n) for n in indexed},combined_ddg=None,
            reason='ENGINE_RANK_MISSING' if missing_rank else 'R40_COMBINATION_UNDEFINED' if rank is None else None))
    return dict(records=out,authority='SOP v10.5 S-31 R-40',scientific_pass=None,
        comparison_sets=dict(foldx='NATIVE_PER_POSITION_AA20',thermompnn='NATIVE_REQUESTED_NON_SELF_MUTATIONS'),
        missing_positions_not_imputed=True,absolute_energies_combined=False,
        warnings=['ENGINE_COMPARISON_SETS_DIFFER','WT_SELF_EXCLUDED_FROM_MUTATION_PROPOSALS'])
