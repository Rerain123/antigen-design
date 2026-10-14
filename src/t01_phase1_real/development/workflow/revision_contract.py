"""Executable, opt-in contract for the 2026-09-29 expert core revision.

Authority: revision sections 1.2, 4, 6, 10, 14. No scientific policy is
implicitly promoted from the v10.5 compatibility path.
"""
from decimal import Decimal
import math
from ...common import RuntimeFault, encode, ensure, sha

VERSION = 't01-core-20260929-v1'
RULE = 'expert-revision-20260929-core-v1'
CHECKS = ('PASS', 'FAIL', 'NOT_ASSESSED', 'NOT_APPLICABLE')
EXECUTIONS = ('NOT_RUN', 'RUNNING', 'SUCCEEDED', 'PARTIAL', 'ERROR')
IDENTITY = ('candidate_id', 'content_hash', 'reference_id', 'calculation_config_id', 'rule_version')
SCOPE = IDENTITY + ('evaluation_profile_id', 'stage_id', 'target_scope_id', 'required_set_id')


def finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def diagnostic(category, code, *details):
    return dict(error_category=category, reason_codes=[code], reason_details=list(details))


def check(status, *reasons, execution='SUCCEEDED', **extra):
    ensure(status in CHECKS and execution in EXECUTIONS, 'OUTPUT_INVALID', 'Invalid revision status')
    return dict(check_status=status, passed={'PASS': True, 'FAIL': False}.get(status),
                execution_status=execution, reason_codes=list(reasons), **extra)


def suggested_config(config_id, seeds=(17, 29)):
    """Engineering suggestion only; caller must explicitly persist this configuration."""
    return dict(shared_contract_version=VERSION, calculation_config_id=config_id, rule_version=RULE,
        parameter_status='SUGGESTED_UNCALIBRATED', presampling_n=24, presampling_batches=2,
        sampling_temperature=.1, design_site_fraction=.07, max_mutation_fraction=.07,
        max_mutations_abs=None, formal_round_sizes=[24,48,64], random_seeds=list(seeds),
        nomination_seed=41, structure_eval_max=24, l4_eval_max=20, foldx_variant_max=20,
        foldx_number_of_runs=5, allow_esm_relaxation=False,
        # Known limits and unknown limits are different. No undeclared automatic retry.
        max_tool_attempts=1, call_limits={}, time_limits={},
        policies=dict(s28=None, model_roles=None, foldx_pool=None, score=None, acceptance=None,
                      hotspot=None, geometry=None, l4=None, esm_near_zero=None))


def config(value):
    ensure(isinstance(value, dict) and value.get('shared_contract_version') == VERSION,
           'INVALID_REQUEST', 'CONTRACT: contract_incompatible')
    expected=set(suggested_config('schema'))
    ensure(set(value)==expected, 'INVALID_REQUEST', 'CONFIGURATION: configuration_incomplete')
    for key in ('calculation_config_id','rule_version'):
        ensure(isinstance(value[key],str) and 0<len(value[key])<=128,
               'INVALID_REQUEST','CONFIGURATION: invalid_configuration '+key)
    from . import revision_v2
    ensure(value['rule_version'] in (RULE,revision_v2.RULE) and value['parameter_status']=='SUGGESTED_UNCALIBRATED',
           'INVALID_REQUEST','Unregistered revision rule or calibration claim')
    for key in ('design_site_fraction','max_mutation_fraction'):
        ensure(finite(value[key]) and 0<=value[key]<=1, 'INVALID_REQUEST', 'CONFIGURATION: invalid_configuration '+key)
    for key in ('presampling_n','presampling_batches','structure_eval_max','l4_eval_max','foldx_variant_max',
                'nomination_seed','max_tool_attempts'):
        ensure(type(value[key]) is int and value[key]>=0,'INVALID_REQUEST','CONFIGURATION: invalid_configuration '+key)
    ensure(value['presampling_batches']==2 and value['presampling_n']<=24 and value['presampling_n']%2==0
           and value['structure_eval_max']<=24 and value['l4_eval_max']<=20 and value['foldx_variant_max']<=20
           and value['max_tool_attempts']==1 and value['sampling_temperature']==.1
           and value['formal_round_sizes']==[24,48,64] and value['foldx_number_of_runs']==5
           and value['allow_esm_relaxation'] is False,
           'INVALID_REQUEST','CONFIGURATION: unsupported revision resource or relaxation policy')
    absolute=value['max_mutations_abs']
    ensure(absolute is None or type(absolute) is int and absolute>=0,'INVALID_REQUEST','CONFIGURATION: invalid_configuration absolute cap')
    seeds=value['random_seeds']
    ensure(isinstance(seeds,list) and len(seeds)==2 and len(set(seeds))==2
           and all(type(s) is int and 1<=s<=2147483647 for s in seeds),
           'INVALID_REQUEST','CONFIGURATION: two explicit distinct seeds required')
    for key in ('call_limits','time_limits'):
        stages={'proposal','formal','esm_if1','structure','l4','foldx'}|({'analysis'} if revision_v2.enabled(value) else set())
        ensure(isinstance(value[key],dict) and set(value[key])<=stages,
               'INVALID_REQUEST','CONFIGURATION: invalid_configuration '+key)
        ensure(all((type(n) is int and n>=0) if key=='call_limits' else (finite(n) and n>=0)
                   for n in value[key].values()),'INVALID_REQUEST','CONFIGURATION: invalid_configuration '+key)
    if revision_v2.enabled(value):revision_v2.validate(value['policies'])
    else:
        from .revision_runtime import validate_policies
        validate_policies(value['policies'])
    return value


def budget(wt, cfg, eligible):
    config(cfg)
    ensure(isinstance(wt,str) and wt and set(wt)<=set('ACDEFGHIKLMNPQRSTVWY'),
           'INVALID_REQUEST','CONFIGURATION: invalid_configuration WT')
    ensure(len(set(eligible))==len(eligible) and all(type(p) is int and 1<=p<=len(wt) for p in eligible),
           'INVALID_REQUEST','Invalid eligible positions')
    length=len(wt)
    b=int(Decimal(str(cfg['max_mutation_fraction']))*length)
    if cfg['max_mutations_abs'] is not None:b=min(b,cfg['max_mutations_abs'])
    return dict(L=length,B=b,K=min(int(Decimal(str(cfg['design_site_fraction']))*length),b,len(eligible)),
        max_mutation_fraction=cfg['max_mutation_fraction'],design_site_fraction=cfg['design_site_fraction'],
        max_mutations_abs=cfg['max_mutations_abs'],config_id=cfg['calculation_config_id'])


def aggregate(scope, required, summaries):
    """Only typed check summaries in one declared scope may be aggregated."""
    incomplete=not isinstance(required,dict) or any(not scope.get(k) for k in SCOPE)
    roles=(required or {}).get('check_roles',{})
    ids=(required or {}).get('required_check_ids',[])
    incomplete |= (not isinstance(ids,list) or len(ids)!=len(set(ids)) or
                   any(roles.get(k)!='mandatory' for k in ids))
    accepted={};quarantine=[]
    for row in summaries:
        if (any(row.get(k)!=scope.get(k) for k in SCOPE) or row.get('check_status') not in CHECKS
                or not row.get('summary_id')):
            quarantine.append(row);continue
        key=row.get('check_id')
        if key in accepted and accepted[key]!=row:
            incomplete=True;continue
        accepted[key]=row
    states=[accepted[k]['check_status'] if k in accepted else 'NOT_ASSESSED' for k in ids]
    # Known mandatory failures survive other missing configuration and receipts.
    status='FAIL' if 'FAIL' in states else 'NOT_ASSESSED' if incomplete or 'NOT_ASSESSED' in states else (
        'PASS' if 'PASS' in states else 'NOT_APPLICABLE' if states or (required or {}).get('confirmed_not_applicable') else 'NOT_ASSESSED')
    out=check(status, *(['configuration_incomplete'] if incomplete else []), scope_key=dict(scope),
              check_summaries=list(accepted.values()),quarantine_receipts=quarantine)
    if incomplete:out['diagnostic']=diagnostic('CONFIGURATION','configuration_incomplete')
    return out


def attach(candidate, receipt, attempts, artifacts):
    """No positional association, no invented attempt for a cached artifact."""
    out=dict(candidate)
    out['receipts']=[*candidate.get('receipts',[]),receipt]
    valid=all(receipt.get(k)==candidate.get(k) for k in IDENTITY)
    attempt=receipt.get('attempt_id')
    valid &= bool(attempt and attempt in attempts and attempts[attempt].get('attempt_id')==attempt)
    valid &= all(attempts.get(attempt,{}).get(k)==candidate.get(k) for k in IDENTITY)
    valid &= bool(receipt.get('input_artifact_refs')) and all(
        r.get('artifact_id') in artifacts and artifacts[r['artifact_id']].get('content_hash')==r.get('content_hash')
        for r in receipt.get('input_artifact_refs',[]))
    prior=[r for r in candidate.get('attempts',[]) if r['attempt_id']==attempt]
    if not valid or prior and prior[0]!=receipt:
        out['association_errors']=[*candidate.get('association_errors',[]),
            dict(receipt_id=receipt.get('receipt_id'),**diagnostic('ASSOCIATION','association_error'))]
    elif not prior:out['attempts']=[*candidate.get('attempts',[]),receipt]
    return out


def validate_references(summary, attempts, artifacts):
    ensure(all(i in attempts for i in summary['selected_attempt_ids']), 'OUTPUT_INVALID','Artifact is not an attempt')
    for ref in summary['selected_artifact_refs']:
        ensure(ref['artifact_id'] in artifacts and artifacts[ref['artifact_id']]['content_hash']==ref['content_hash'],
               'OUTPUT_INVALID','Unverified artifact reference')
    return summary
