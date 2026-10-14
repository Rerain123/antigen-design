"""SOP v10.5 T-01 step20 arithmetic, for explicitly isolated contract fixtures.

No candidate-pool truncation, family assignment or tie-breaking is invented here.
The runtime report never accepts caller-supplied scientific flags or scores.
"""
import math
from decimal import Decimal
from ...common import ensure

WEIGHTS={'general':(.50,.10,.30,.10),'solubility':(.60,.10,.20,.10),'thermostability':(.25,.45,.20,.10)}
COUNTS={'general':12,'solubility':15,'thermostability':12}

def finite(value):return type(value) in (float,int) and math.isfinite(value)

def stability(ddg):
    if ddg is None:return .5
    ensure(finite(ddg),'OUTPUT_INVALID','Finite signed FoldX ddG required')
    x=-ddg/2
    return 1/(1+math.exp(-x)) if x>=0 else math.exp(x)/(1+math.exp(x))

def hard_filter(flags):
    names=('epitope_violation','safety_excluded','constraint_override','host_similarity_high','burden_exceeded')
    ensure(set(flags)==set(names) and all(v is None or type(v) is bool for v in flags.values()),'INVALID_REQUEST','Five explicit tri-state filters required')
    excluded=[k for k in names if flags[k] is True]
    missing=[k for k in names if flags[k] is None]
    return dict(state='EXCLUDED' if excluded else 'UNDETERMINED' if missing else 'RETAINED',reasons=excluded,missing=missing,
        non_standard=flags['constraint_override'] is True)

def rank_fixture(records,objective,*,evidence_kind):
    ensure(evidence_kind=='SYNTHETIC_CONTRACT_FIXTURE','FORBIDDEN','Unsigned arithmetic only accepts explicitly labelled fixtures')
    ensure(objective in WEIGHTS,'INVALID_REQUEST','Unknown objective')
    ids=[r['id'] for r in records]
    ensure(len(ids)==len(set(ids)),'INVALID_REQUEST','Unique fixture IDs required')
    computed=[];filters=[]
    for r in records:
        hf=hard_filter(r['flags']);filters.append(dict(id=r['id'],**hf))
        if hf['state']!='RETAINED':continue
        dev=r['overall'];count=r['count'];epi=r['epitope']
        ensure(finite(dev) and 0<=dev<=1,'INVALID_REQUEST','Available normalized developability required')
        ensure(count is None or type(count) is int and count>=0,'INVALID_REQUEST','Nonnegative mutation count required')
        ensure(epi in (1.,1.3,None) and r['epitope_state'] in ('VERIFIED','NO_STRUCTURE_DEGRADED'),
            'INVALID_REQUEST','N13 not executed is not neutral epitope evidence')
        ensure(epi is not None or r['epitope_state']=='NO_STRUCTURE_DEGRADED','INVALID_REQUEST','Only declared no-structure degradation uses neutral epitope value')
        ensure(type(r['soft_penalty']) is bool and type(r['host_medium']) is bool,'INVALID_REQUEST','Explicit penalties required')
        c=count or 0;e=1. if epi is None else epi;s=stability(r['ddg'])
        norms=[dev,s,e,max(0.,1-c/COUNTS[objective])]
        score=sum(Decimal(str(w))*Decimal(str(n)) for w,n in zip(WEIGHTS[objective],norms))
        score-=Decimal('.10')*r['soft_penalty']+Decimal('.05')*r['host_medium']
        computed.append(dict(id=r['id'],pareto=[dev,s,e,-c],norms=norms,score=float(score),
            neutral_fields=[k for k in ('ddg','count','epitope') if r[k] is None]))
    front=[r for r in computed if not any(all(a>=b for a,b in zip(u['pareto'],r['pareto']))
        and any(a>b for a,b in zip(u['pareto'],r['pareto'])) for u in computed)]
    groups=[dict(score=s,ids=sorted(r['id'] for r in front if r['score']==s)) for s in sorted({r['score'] for r in front},reverse=True)]
    return dict(kind=evidence_kind,objective=objective,filters=filters,computed=computed,pareto_ids=sorted(r['id'] for r in front),
        score_groups=groups,tie_break='NOT_COMPUTED_OI_022',top20=None,best_candidate=None,scientific_ranking=None,
        warning='SOP reference weights and null rules are unsigned engineering arithmetic; OI-009/010/011/022 remain open')
