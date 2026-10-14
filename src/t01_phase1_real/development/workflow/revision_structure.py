"""Revision structure allocation and model roles, separate from legacy R-04.

Policy absence blocks model consumption; the schedule and multi-engine
reservations remain executable and testable without declaring a science policy.
"""
from ...common import ensure
from .revision_contract import check,diagnostic
from .revision_sampling import select_structure
from .revision_budget import reserve


LEGACY_MODEL_POLICY='primary_af3_secondary_c11'
SINGLE_MODEL_POLICY='single_engine_gt10pct_same_engine_20261013'


def route(length,count,cfg=None):
    ensure(type(length) is int and length>0 and type(count) is int and 0<=count<=length,
           'OUTPUT_INVALID','Invalid WT mutation count')
    policy=(cfg or {}).get('policies',{}).get('model_roles') or {}
    if policy.get('model_role_policy')==SINGLE_MODEL_POLICY:
        # Latest expert rule, confirmed by user: strictly greater than 10%.
        return ['esmfold2'] if count*10>length else ['af3']
    return ['af3'] if count<=5 else ['af3','esmfold2'] if count*10<=length else ['esmfold2']


def scheduled_engines(length,count,cfg):
    from .revision_v2 import enabled
    engines=route(length,count,cfg)
    if (enabled(cfg) and engines==['esmfold2']
            and cfg['policies']['model_roles']['model_role_policy']!=SINGLE_MODEL_POLICY):return []
    return engines


def plan(records,scored,ledger,cfg,policy):
    used={o for r in ledger['reservations'].values() if r['stage']=='structure' for o in r['objects']}
    remaining=max(0,cfg['structure_eval_max']-len(used))
    from .revision_v2 import enabled
    selected=select_structure([r for r in records if r['content_hash'] not in used],scored,remaining,
                              require_sequence_metrics=enabled(cfg))
    result=[]
    for row in records:
        reasons=[];engines=[]
        if row['constraint_check']['check_status']=='FAIL':reasons=['EARLY_HARD_FAIL']
        elif row['disposition']!='FORMAL_POOL':reasons=[row['disposition']]
        elif row['candidate_id'] not in selected:reasons=['not_selected_for_structure_budget' if remaining==0 else 'CHEAP_CHECKS_NOT_PASSED']
        elif enabled(cfg):
            engines=scheduled_engines(len(row['sequence']),len(row['mutations']),cfg)
            if not engines:reasons=['C11_ONLY_SUPPLY_UNDECLARED']
        elif not isinstance(policy,dict) or not policy.get('model_roles'):
            reasons=['configuration_incomplete']
        else:
            engines=route(len(row['sequence']),len(row['mutations']))
            if any(policy['model_roles'].get(e) not in ('mandatory','advisory') for e in engines):
                engines=[];reasons=['configuration_incomplete']
        result.append(dict(candidate_id=row['candidate_id'],content_hash=row['content_hash'],engines=engines,
            **check('NOT_ASSESSED',*reasons,execution='NOT_RUN')))
    return result


def reserve_engines(ledger,cfg,record,round_id):
    """Atomic all-engine allocation: failed second reservation spends nothing."""
    import copy
    tentative=copy.deepcopy(ledger)
    for engine in record['engines']:
        if not reserve(tentative,cfg,f'{round_id}:{record["candidate_id"]}:{engine}',
                       'structure',[record['content_hash']]):return False
    ledger.clear();ledger.update(tentative)
    return True
