"""Versioned evaluation/score carriers, deliberately separate from legacy ranking.

Expert revision sections 10–16. Policies are inputs, never inferred from
missing evidence or from legacy thresholds. Runtime policy activation is closed.
"""
import math
import statistics
from ...common import encode, ensure, sha
from .revision_contract import check, diagnostic, finite


def repeats(planned_count, attempts):
    ensure(type(planned_count) is int and planned_count>0,'OUTPUT_INVALID','Positive repetition count required')
    ids=[r['repeat_id'] for r in attempts]
    ensure(len(ids)==len(set(ids)) and len(ids)<=planned_count,'OUTPUT_INVALID','Duplicate or extra repeat output')
    values=[r['value'] for r in attempts if r.get('verified') is True and finite(r.get('value'))]
    active=any(r['execution_status']=='RUNNING' for r in attempts)
    state='RUNNING' if active else 'NOT_RUN' if not attempts else 'ERROR' if not values else 'SUCCEEDED' if len(values)==planned_count else 'PARTIAL'
    return dict(execution_status=state,check_status='NOT_ASSESSED',planned_count=planned_count,valid_count=len(values),
        mean=statistics.mean(values) if values else None,std=statistics.stdev(values) if len(values)>1 else None,
        statistic_definition_id='paired-wt-ddg-sample-std-n-minus-1',selected_result_ids=[r['repeat_id'] for r in attempts
            if r.get('verified') is True and finite(r.get('value'))],repeatability=None,attempts=attempts)


def foldx_pool(records, policy, limit, *, mode, task_id):
    ensure(mode in ('variant_score','reference_scan'),'INVALID_REQUEST','Explicit FoldX mode required')
    if mode=='reference_scan':
        return dict(mode=mode,task_id=task_id,**check('NOT_ASSESSED','N17_EXPLICIT_SCAN_REQUIRED',execution='NOT_RUN'),results=[])
    if not records:
        return dict(mode=mode,task_id=task_id,**check('NOT_ASSESSED','SKIPPED_EMPTY',execution='NOT_RUN'),results=[])
    excluded=[r for r in records if r.get('hard_check_status')=='FAIL' or r.get('constraint_check',{}).get('check_status')=='FAIL']
    eligible=[r for r in records if r not in excluded and r.get('stage')=='formal' and r.get('mutations')]
    if not eligible:
        return dict(mode=mode,task_id=task_id,**check('NOT_ASSESSED','SKIPPED_EMPTY',execution='NOT_RUN'),results=[],excluded=excluded)
    required=('source_pool_id','required_check_ids','selection_rule_version','applicability','selected_candidate_ids')
    if not isinstance(policy,dict) or any(k not in policy for k in required):
        return dict(mode=mode,task_id=task_id,**check('NOT_ASSESSED','configuration_incomplete',execution='NOT_RUN'),
                    diagnostic=diagnostic('CONFIGURATION','configuration_incomplete','FoldX pool policy'),results=[],excluded=excluded)
    selected=policy['selected_candidate_ids']
    ensure(len(selected)==len(set(selected)) and len(selected)<=limit,'OUTPUT_INVALID','Invalid FoldX pool allocation')
    by_id={r['candidate_id']:r for r in eligible}
    ensure(all(cid in by_id and by_id[cid].get('source_pool_id')==policy['source_pool_id']
        and all(by_id[cid].get('checks',{}).get(k)=='PASS' for k in policy['required_check_ids']) for cid in selected),
        'OUTPUT_INVALID','FoldX candidate fails declared source or prerequisites')
    ensure(policy['applicability'] is True,'INVALID_REQUEST','FoldX applicability unconfirmed')
    return dict(mode=mode,task_id=task_id,**check('NOT_ASSESSED',execution='NOT_RUN'),results=[by_id[c] for c in selected],
                excluded=excluded,policy=policy,number_of_runs=5)


def score(values,context):
    required=('score_context_id','dimensions','calculation_modes','normalization','weights','missing_policy','formula_version')
    if not isinstance(context,dict) or any(k not in context for k in required):
        return dict(value=None,diagnostic=diagnostic('CONFIGURATION','configuration_incomplete','Score context'))
    dims=context['dimensions'];weights=context['weights']
    if (not dims or len(dims)!=len(set(dims)) or context['missing_policy']!='require_all'
        or context['formula_version']!='weighted-normalized-mean-v1'
        or any(not finite(weights.get(k)) or weights[k]<0 for k in dims)
        or sum(weights[k] for k in dims)<=0):
        return dict(value=None,score_context_id=context['score_context_id'],diagnostic=diagnostic('CONFIGURATION','invalid_configuration'))
    missing=[k for k in dims if not isinstance(values.get(k),dict) or values[k].get('reliable') is not True
        or not finite(values[k].get('normalized')) or not 0<=values[k]['normalized']<=1
        or values[k].get('mode')!=context['calculation_modes'].get(k)
        or values[k].get('normalization')!=context['normalization'].get(k)]
    return dict(value=None if missing else sum(values[k]['normalized']*weights[k] for k in dims)/sum(weights[k] for k in dims),
                score_context_id=context['score_context_id'],dimensions=dims,missing=missing)


def score_bundle(values,contexts):
    """Separate three meanings; comparison must use fixed WT non-stability axes."""
    result={}
    for kind in ('description','comparison','acceptance'):
        context=contexts.get(kind)
        if kind=='comparison' and context is not None:
            ensure('stability_ddg' not in context.get('dimensions',[]) and context.get('wt_reference_id')
                   and context.get('frozen_before_generation') is True,
                   'INVALID_REQUEST','Comparison requires frozen non-stability WT dimensions')
        result[kind+'_score']=score(values,context)
    return result


def round_robin_groups(groups,limit):
    """Budget allocation only, after each group has its own declared ordering."""
    ensure(type(limit) is int and limit>=0,'INVALID_REQUEST','Invalid group allocation budget')
    selected=[]
    for priority in (True,False):
        active=sorted((g for g in groups if g['stage_evidence_complete'] is priority),key=lambda g:g['group_id'])
        for i in range(max((len(g['ordered_candidate_ids']) for g in active),default=0)):
            for group in active:
                if len(selected)>=limit:return selected
                if i<len(group['ordered_candidate_ids']):selected.append(group['ordered_candidate_ids'][i])
    return selected


def acceptance(hard_status, evidence_complete, score_result, policy, *, nonstandard=False, applicable=None):
    formal=provisional='NOT_ASSESSED';reasons=[]
    required=('acceptance_config_id','required_check_ids','dimensions','calculation_modes','normalization','weights',
              'missing_policy','threshold','threshold_status','rule_version','score_context_id')
    complete=isinstance(policy,dict) and all(k in policy for k in required)
    if hard_status=='FAIL':formal=provisional='FAIL'
    elif applicable is False:formal=provisional='NOT_APPLICABLE'
    elif (not complete or applicable is not True or evidence_complete is not True or hard_status!='PASS'
          or not finite(score_result.get('value')) or score_result.get('score_context_id')!=(policy or {}).get('score_context_id')
          or nonstandard and (policy or {}).get('allow_nonstandard') is not True
          or not finite((policy or {}).get('threshold'))):reasons=['configuration_incomplete']
    elif policy['threshold_status']=='pending_calibration':
        provisional='PASS' if score_result['value']>=policy['threshold'] else 'FAIL'
    elif policy['threshold_status']=='calibrated' and policy.get('calibration_evidence_ref'):
        formal='PASS' if score_result['value']>=policy['threshold'] else 'FAIL';provisional='NOT_APPLICABLE'
    else:reasons=['configuration_incomplete']
    return dict(acceptance_status=formal,provisional_acceptance_status=provisional,
                acceptance_score=score_result.get('value') if complete else None,reason_codes=reasons)


def task_acceptance(statuses, coverage_complete, applicable=None):
    if applicable is False:return 'NOT_APPLICABLE'
    if 'PASS' in statuses:return 'PASS'
    if not coverage_complete or 'NOT_ASSESSED' in statuses or not statuses:return 'NOT_ASSESSED'
    if 'FAIL' in statuses:return 'FAIL'
    return 'NOT_APPLICABLE'


def evidence_group(profile, hard_status, complete, protected, *, original_profile='original'):
    if not profile:return None
    if hard_status=='FAIL':return 'E'
    if hard_status=='PASS' and complete is True and protected is True:return 'A' if profile==original_profile else 'B'
    return 'C'


def axes(dev,ddg,structural,prediction,count,b):
    valid_ddg=finite(ddg)
    # Stable sigmoid, retaining null instead of a neutral value.
    z=-ddg/2 if valid_ddg else None
    stab=(1/(1+math.exp(-z)) if z>=0 else math.exp(z)/(1+math.exp(z))) if valid_ddg else None
    return dict(dev=dev if finite(dev) else None,stab=stab,
        epi=(float(structural)+.3*float(prediction))/1.3 if type(structural) is bool and type(prediction) is bool else None,
        burden=1-count/b if type(count) is int and type(b) is int and b>0 and 0<=count<=b else None)


def rank_groups(records, policy):
    """No ranks across incomparable groups; no 95% identity rejection."""
    if not isinstance(policy,dict) or not policy.get('score_policy_version'):
        return dict(groups=[],diagnostic=diagnostic('CONFIGURATION','configuration_incomplete'))
    groups={};seen=set()
    for r in records:
        if r['content_hash'] in seen or not r.get('mutations') or r.get('evidence_group')=='E':continue
        seen.add(r['content_hash'])
        keys=tuple(sorted(k for k,v in r['axes'].items() if finite(v)))
        context=(r['evaluation_profile_id'],r['evidence_group'],r['score_context_id'],r['calculation_mode'],keys)
        gid=sha(encode(context));groups.setdefault(gid,[]).append(dict(r,rank=None,group_id=gid,axis_set=list(keys)))
    result=[]
    for gid,rows in sorted(groups.items()):
        keys=rows[0]['axis_set'];weights=policy.get('weights',{})
        if not keys or any(not finite(weights.get(k)) or weights[k]<0 for k in keys) or sum(weights[k] for k in keys)<=0:
            result.append(dict(group_id=gid,records=rows,selected=[],reason_codes=['configuration_incomplete']));continue
        for r in rows:
            r['unpenalized_score']=sum(r['axes'][k]*weights[k] for k in keys)/sum(weights[k] for k in keys)
            r['penalty']=.10 if r.get('soft_penalty_reasons') else 0.
            r['comparison_score']=r['unpenalized_score']-r['penalty']
        remaining=list(rows);ranked=[];layer=0
        while remaining:
            front=[a for a in remaining if not any(all(b['axes'][k]>=a['axes'][k] for k in keys)
                 and any(b['axes'][k]>a['axes'][k] for k in keys) for b in remaining if b is not a)]
            layer+=1
            # Diversity breaks only equal layer/score ties using full signatures.
            ordered=[]
            while front:
                def key(r):
                    signature={tuple(m[k] for k in ('position','wt','mut')) for m in r['mutations']}
                    distance=min((len(signature^{tuple(m[k] for k in ('position','wt','mut')) for m in x['mutations']})
                                  for x in ranked+ordered),default=0)
                    return (-r['comparison_score'],-distance,r['candidate_id'])
                r=min(front,key=key);front.remove(r);ordered.append(r);r['pareto_layer']=layer
            ranked.extend(ordered);remaining=[r for r in remaining if r not in ordered]
        for i,r in enumerate(ranked,1):r['group_rank']=i
        selected=[];families={}
        for r in ranked:
            family=r.get('family','unclassified')
            if families.get(family,0)<5:
                selected.append(r);families[family]=families.get(family,0)+1
            if len(selected)==20:break
        selected.extend(r for r in ranked if r not in selected)
        result.append(dict(group_id=gid,records=ranked,selected=selected[:20],
                           ranking_scope='FOUR_AXES' if len(keys)==4 else 'PARTIAL_AXES'))
    return dict(groups=result,global_rank=None,score_policy_version=policy['score_policy_version'])
