"""Persistent monotone task accounting; reservations and child insertion share a transaction."""
from ...common import ensure, encode, sha
from .revision_contract import VERSION, finite


def new(config):
    return dict(shared_contract_version=VERSION,calculation_config_id=config['calculation_config_id'],
        config_sha256=sha(encode(config)),reservations={},attempts={},observed_objects={},outcomes=[])


def reserve(ledger, config, key, stage, objects, requested=0, internal_runs=1):
    ensure(ledger['config_sha256']==sha(encode(config)),'OUTPUT_INVALID','Budget configuration changed on resume')
    ensure(stage in ('proposal','formal','esm_if1','structure','analysis','l4','foldx') and type(requested) is int and requested>=0
           and type(internal_runs) is int and internal_runs>0,'OUTPUT_INVALID','Invalid budget reservation')
    record=dict(stage=stage,objects=sorted(set(objects)),requested=requested,internal_runs=internal_runs)
    prior=ledger['reservations'].get(key)
    if prior is not None:
        ensure(prior==record,'OUTPUT_INVALID','Budget reservation identity conflict');return True
    rows=[r for r in ledger['reservations'].values() if r['stage']==stage]
    unique=set(o for r in rows for o in r['objects'])|set(objects)
    limit={'structure':config['structure_eval_max'],'l4':config['l4_eval_max'],'foldx':config['foldx_variant_max']}.get(stage)
    if limit is not None and len(unique)>limit:return False
    if stage=='formal' and sum(r['requested'] for r in rows)+requested>sum(config['formal_round_sizes']):return False
    if stage=='proposal' and sum(r['requested'] for r in rows)+requested>config['presampling_n']:return False
    if stage in config['call_limits'] and len(rows)>=config['call_limits'][stage]:return False
    if stage in config['time_limits']:
        elapsed=[r.get('execution_seconds') for r in ledger['attempts'].values() if r['stage']==stage]
        if any(v is None for v in elapsed) or sum(elapsed)>=config['time_limits'][stage]:return False
    ledger['reservations'][key]=record
    return True


def observe(ledger, key, attempt):
    ensure(key in ledger['reservations'],'OUTPUT_INVALID','Unreserved attempt')
    ensure(attempt.get('attempt_id') and attempt.get('execution_status') in ('RUNNING','SUCCEEDED','PARTIAL','ERROR'),
           'OUTPUT_INVALID','Real attempt identity and lifecycle required')
    for name in ('queue_seconds','execution_seconds'):
        ensure(attempt.get(name) is None or finite(attempt[name]) and attempt[name]>=0,'OUTPUT_INVALID','Invalid timing')
    aid=attempt['attempt_id'];old=ledger['attempts'].get(aid)
    if old and old['execution_status']!='RUNNING':
        ensure(old==dict(attempt,reservation_id=key,stage=ledger['reservations'][key]['stage']),
               'OUTPUT_INVALID','Conflicting terminal attempt receipt');return
    ledger['attempts'][aid]=dict(attempt,reservation_id=key,stage=ledger['reservations'][key]['stage'])


def observe_objects(ledger,key,hashes):
    ensure(key in ledger['reservations'],'OUTPUT_INVALID','Unreserved generation')
    value=list(hashes);prior=ledger.setdefault('observed_objects',{}).get(key)
    ensure(prior is None or prior==value,'OUTPUT_INVALID','Generation inventory changed after observation')
    ledger['observed_objects'][key]=value


def summary(ledger,config):
    from .revision_v2 import enabled
    result={}
    stages=('proposal','formal','esm_if1','structure')+(('analysis',) if enabled(config) else ())+('l4','foldx')
    for stage in stages:
        rows=[r for r in ledger['reservations'].values() if r['stage']==stage]
        attempts=[r for r in ledger['attempts'].values() if r['stage']==stage]
        objects={o for r in rows for o in r['objects']}
        generated=[h for key,hashes in ledger.get('observed_objects',{}).items()
                   if ledger['reservations'][key]['stage']==stage for h in hashes]
        if stage in ('proposal','formal'):objects=set(generated)
        limit={'structure':config['structure_eval_max'],'l4':config['l4_eval_max'],'foldx':config['foldx_variant_max']}.get(stage)
        result[stage]=dict(requested=sum(r['requested'] for r in rows),generated=len(generated),unique_objects=len(objects),
            reserved_calls=len(rows),attempts=len(attempts),failed_attempts=sum(r['execution_status']=='ERROR' for r in attempts),
            internal_runs=sum(r['internal_runs'] for r in attempts) if all(r.get('internal_runs') is not None for r in attempts) else None,
            cache_hits=sum(r.get('cache_hit') is True for r in attempts),
            queue_seconds=sum(r['queue_seconds'] for r in attempts) if all(r.get('queue_seconds') is not None for r in attempts) else None,
            execution_seconds=sum(r['execution_seconds'] for r in attempts) if all(r.get('execution_seconds') is not None for r in attempts) else None,
            budget_status='NOT_APPLICABLE' if limit is None else 'EXHAUSTED' if len(objects)>=limit else 'AVAILABLE',
            call_limit_status='NOT_APPLICABLE' if stage not in config['call_limits'] else 'EXHAUSTED' if len(rows)>=config['call_limits'][stage] else 'AVAILABLE',
            time_limit_status='NOT_APPLICABLE' if stage not in config['time_limits'] else 'UNKNOWN' if any(r.get('execution_seconds') is None for r in attempts) else
                'EXHAUSTED' if sum(r['execution_seconds'] for r in attempts)>=config['time_limits'][stage] else 'AVAILABLE',
            actual_concurrency=None,concurrency_reason='Requires native overlap timestamps')
    return result


def retry_reason(*,system_errors,budget_available,designable,original_pass,round_index):
    if system_errors:return 'SYSTEMIC_ERROR'
    if not designable:return 'no_designable_positions'
    if budget_available is not True:return 'budget_exhausted' if budget_available is False else 'configuration_incomplete'
    if original_pass:return 'S28_ORIGINAL_PASS'
    if round_index>=2:return 'FORMAL_ROUNDS_EXHAUSTED'
    return None
