"""Durable, owner-authorized T4 consent, bound to one immutable audit result."""
import copy
from datetime import datetime, timezone
from ...common import TERMINAL, decode, encode, ensure, now, sha

CODE='T4_EMPTY_FIXED_CONFIRMATION_REQUIRED'


def seconds(start):
    return max(0.,(datetime.now(timezone.utc)-datetime.fromisoformat(start.replace('Z','+00:00'))).total_seconds())


def elapsed(ex):
    receipt=ex.get('controller_upgrade') or {}
    maintenance=receipt.get('maintenance',{}).get('excluded_seconds',0) if receipt.get('authorization')=='USER_REQUESTED_LATENCY_MAINTENANCE_20261010' else 0
    return max(0.,seconds(ex['started_at'])-maintenance-ex.get('confirmation_wait_seconds',0)-(
        seconds(ex['pending_confirmation']['requested_at']) if ex.get('pending_confirmation') else 0)
    )


def pause(rt,jid):
    from .service import verified
    with rt._tx() as db:
        job=rt._job(db,jid);ex=rt._execution(db,jid)
        if job['state'] in TERMINAL or job['stop_reason']:return
        if ex.get('pending_confirmation'):return
        body=decode(rt._request_bytes(job));row=ex['nodes']['design_inputs']
        audit_job=verified(rt,body,'design_inputs',row['job_id'],job['run_id'],ex['nodes'])
        audit=rt.result(row['job_id'])['audit'];draft=audit['pending_n11_request_draft']
        ensure(audit.get('confirmation_required') is True and not draft['constraints']['fixed_positions'],
               'INVALID_STATE','No empty-fixed confirmation is required')
        ref=next(r for r in audit_job['artifacts'] if r['role']=='result')
        binding=dict(job_id=jid,run_id=job['run_id'],audit_job_id=row['job_id'],
                     audit_sha256=ref['sha256'],draft_sha256=sha(encode(draft)))
        pending=dict(binding,confirmation_id='t4-'+sha(encode(binding)),code=CODE,
            requested_at=now(),fixed_count=0,restricted_count=len(draft['constraints']['restricted_positions']),
            open_count=len(draft['constraints']['open_positions']),
            warning='本次未形成 FIXED 位点；重点表位峰未提供可消费结果。继续将按已审计的 RESTRICTED/OPEN 掩码设计，不能保证未知关键位点完全不变。',
            prompt='是否确认按本次审计掩码继续 N11？拒绝则仅交付已完成的分析。',
            scientific_release=False)
        if body.get('interaction_policy')=='PREAUTHORIZED_T4_CONTINUE_WITH_WARNING_V1':
            # One transaction: queries must never observe a temporary prompt
            # for a task whose owner already selected unattended operation.
            consent=dict(pending,decision=True,actor='configured:'+body['interaction_policy'],decided_at=now())
            ex.update(pending_confirmation=None,phase='scheduling')
            ex['nodes']['design']=dict(node_id='N11',job_id=None,state='ready',reason_code=None,
                                      origin=None,confirmation=consent)
            rt._execution_store(db,jid,ex);rt._store(db,copy.deepcopy(job),job,'t4_pre_authorized')
            return
        ex.update(pending_confirmation=pending,phase='awaiting_confirmation')
        ex['nodes']['design']=dict(node_id='N11',job_id=None,state='awaiting_confirmation',reason_code=CODE,origin=None)
        rt._execution_store(db,jid,ex);rt._store(db,copy.deepcopy(job),job,'t4_confirmation_requested')


def decide(rt,jid,confirmation_id,decision,actor):
    from .service import verified
    with rt._tx() as db:
        job=rt._job(db,jid);ex=rt._execution(db,jid)
        ensure(type(decision) is bool,'INVALID_REQUEST','Explicit boolean decision required')
        previous=(ex.get('nodes',{}).get('design') or {}).get('confirmation')
        if previous and previous['confirmation_id']==confirmation_id:
            ensure(previous['decision'] is decision,'IDEMPOTENCY_CONFLICT','T4 decision already recorded')
            return job
        ensure(job['state'] not in TERMINAL and not job['stop_reason'],'INVALID_STATE','Task has ended or is stopping')
        pending=ex.get('pending_confirmation')
        ensure(pending and pending['confirmation_id']==confirmation_id,'INVALID_STATE','No matching pending T4 confirmation')
        body=decode(rt._request_bytes(job))
        audit_job=verified(rt,body,'design_inputs',pending['audit_job_id'],job['run_id'],ex['nodes'])
        ref=next(r for r in audit_job['artifacts'] if r['role']=='result')
        draft=rt.result(audit_job['job_id'])['audit']['pending_n11_request_draft']
        ensure(ref['sha256']==pending['audit_sha256'] and sha(encode(draft))==pending['draft_sha256'],
               'HASH_MISMATCH','T4 audit changed before confirmation')
        consent=dict(pending,decision=decision,actor=actor,decided_at=now())
        ex['nodes']['design'].update(state='ready' if decision else 'skipped',confirmation=consent,
            reason_code=None if decision else 'T4_DESIGN_DECLINED')
        ex['confirmation_wait_seconds']=ex.get('confirmation_wait_seconds',0)+seconds(pending['requested_at'])
        ex.update(pending_confirmation=None,phase='scheduling')
        rt._execution_store(db,jid,ex);rt._store(db,copy.deepcopy(job),job,'t4_confirmation_decided')
        return job
