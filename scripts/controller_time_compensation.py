"""Operator-only, evidence-bound continuation of a timed-out v2 checkpoint.

No deployed model code changes. A new parent receives only the remaining
effective time; terminal source jobs, native attempts and scientific budgets
remain immutable. This is not a public retry or an automatic timeout bypass.
"""
import copy
import math
from datetime import datetime
from t01_phase1_real.common import TERMINAL, encode, decode, ensure, sha, now, new_id
from t01_phase1_real.development.workflow import policy, service

AUTHORIZATION = 'USER_REQUESTED_COMPENSATE_CONTROLLER_OUTAGE_20261008'
OPERATION = 'controller_outage_continuation'


def delta(end, start):
    return (datetime.fromisoformat(end.replace('Z', '+00:00')) -
            datetime.fromisoformat(start.replace('Z', '+00:00'))).total_seconds()


def remaining_time(job, execution, body, evidence):
    ensure(evidence.get('authorization') == AUTHORIZATION and
           evidence.get('job_id') == job['job_id'] and evidence.get('run_id') == job['run_id'] and
           evidence.get('checkpoint_sha256') == sha(encode(execution)),
           'FORBIDDEN', 'Compensation must bind the exact authorized checkpoint')
    start, end = evidence['outage_start'], evidence['outage_end']
    lost = delta(end, start)
    ensure(lost > 0 and delta(start, execution['started_at']) >= 0 and
           delta(job['finished_at'], end) >= 0, 'INVALID_REQUEST', 'Outage is outside this execution')
    charged = delta(job['finished_at'], execution['started_at']) - execution.get('confirmation_wait_seconds', 0)
    ensure(0 < lost <= charged, 'INVALID_REQUEST', 'Invalid clock compensation')
    remaining = math.floor(body['timeout_seconds'] - charged + lost)
    ensure(0 < remaining <= body['timeout_seconds'], 'INVALID_STATE', 'No compensated time remains')
    return dict(original_timeout_seconds=body['timeout_seconds'],charged_before_seconds=charged,
                outage_credit_seconds=lost,consumed_effective_seconds=charged-lost,
                remaining_seconds=remaining,source_finished_at=job['finished_at'],
                formula='floor(original_timeout - charged_before + outage_credit)')


def prepare(rt, source_id, evidence):
    from t01_phase1_real.development.workflow import revision_controller, revision_v2_runtime, revision_v2
    from t01_phase1_real.service_api.controller_recovery import accepted
    job=rt.get(source_id);old=rt.execution(source_id)
    ensure(job['tool_id']==policy.TOOL and job['state']=='timed_out' and job['error_code']=='TIMEOUT' and
           job['stop_reason']=='timeout' and old.get('tree_stopped') is True and
           not old.get('dispatcher') and not old.get('pending_confirmation') and not old.get('fatal_error') and
           not old.get('continuation'), 'INVALID_STATE', 'Only the original stopped timeout checkpoint can continue')
    body=policy.request(rt._request_bytes(job))
    ensure(revision_v2.enabled(body.get('revision_config',{})) and body['configuration']==service.configuration(rt) and
           accepted(job,old,policy.registered_profile()), 'PROFILE_NOT_APPROVED', 'Same deployed v2 configuration required')
    clock=remaining_time(job,old,body,evidence)
    ensure(old.get('revision_v2_frozen') and old.get('revision_ledger') and
           not old.get('revision_state'), 'INVALID_STATE', 'Expected unfinished v2 checkpoint')
    rows=copy.deepcopy(old['nodes']);removed=[]
    for name,row in list(rows.items()):
        if row.get('job_id'):
            child=service.verified(rt,body,name,row['job_id'],job['run_id'],old['nodes'])
            ensure(child['state'] in TERMINAL and (not child.get('attempt_id') or
                   rt.execution(child['job_id']).get('tree_stopped') is True),
                   'INVALID_STATE', 'All reused children must be stopped')
            row.update(state=child['state'],reason_code=child.get('error_code'),
                       prior_origin=row.get('origin'),origin='SAME_RUN_REUSE')
        elif row.get('reason_code')=='N05_DOWNSTREAM_TIME_RESERVE':
            # Only an unadmitted time-reserve placeholder is reopened. An
            # already computed map must not silently acquire different inputs.
            ensure(name.endswith('_netmhc') and not rows.get(name[:-6]+'epitope_map',{}).get('job_id'),
                   'INVALID_STATE','Time-reserve source already has a downstream consumer')
            removed.append(name);del rows[name]
    revision_v2_runtime.verified_freeze(rt,source_id,body)
    data,reason=revision_controller.inputs(rt,source_id,body)
    ensure(reason is None,'OUTPUT_INVALID','Original permissions unavailable')
    fact=revision_controller.assemble(rt,source_id,body,data)
    ensure(rt.get(source_id)==job and rt.execution(source_id)==old,'INVALID_STATE','Checkpoint changed during replay')
    return job,body,old,rows,clock,dict(formal_records=len(fact['formal_records']),
            reopened_unadmitted_nodes=removed,read_only_replay=True)


def create(rt, source_id, evidence, prepared):
    """Caller verifies owner, evidence and deployed bytes before invocation."""
    fingerprint=encode(evidence);key=source_id
    with rt._tx() as db:
        def action():
            source,body,old,rows,clock,replay=prepared
            ensure(rt._job(db,source_id)==source and rt._execution(db,source_id)==old,
                   'INVALID_STATE','Verified checkpoint changed')
            ensure(remaining_time(source,old,body,evidence)==clock,'INVALID_STATE','Clock calculation changed')
            # Existing parent request remains immutable. Only the new parent's
            # remaining wall-clock allowance changes, never scientific inputs.
            request_body=dict(body,timeout_seconds=clock['remaining_seconds'])
            policy.request(encode(request_body))
            ref=rt._stage(db,source['run_id'],encode(request_body),policy.TOOL)
            request=service.envelope(source['run_id'],ref,policy,'controller-credit-'+sha(source_id.encode())[:32])
            rt._admit(db,request)
            before=rt._new_job(db,request,encode(request),retry_of=source_id)
            job=copy.deepcopy(before);started=now()
            job.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
                       lease_epoch=1,started_at=started)
            ex=copy.deepcopy(old)
            original_upgrade=ex.pop('controller_upgrade',None)
            ex.update(nodes=copy.deepcopy(rows),phase='scheduling',tree_stopped=False,dispatcher=None,
                      started_at=started,confirmation_wait_seconds=0,pending_confirmation=None)
            ex['continuation']=dict(kind='USER_AUTHORIZED_CONTROLLER_TIME_COMPENSATION',
                source_job_id=source_id,source_run_id=source['run_id'],source_execution_sha256=sha(encode(old)),
                source_request_sha256=source['request_artifact']['sha256'],source_execution_profile=source['execution_profile'],
                prior_controller_upgrade=original_upgrade,authorization=evidence['authorization'],
                compensation_evidence=copy.deepcopy(evidence),clock=clock,
                stopped_between_parents_seconds=delta(started,source['finished_at']),
                reused_children={n:r['job_id'] for n,r in rows.items() if r.get('job_id')},
                candidate_generation_repeated=False,scientific_consent_added=False,
                scientific_budgets_reset=False,replay=replay)
            rt._execution_store(db,job['job_id'],ex)
            rt._store(db,job,before,OPERATION)
            return job
        return rt._idempotent(db,OPERATION,key,fingerprint,action)
