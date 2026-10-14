"""Operator-approved controller upgrade; existing job/input identities survive.

No MCP request approves profile changes. This is deployment recovery, not a
scientific retry, a new run, or a change to scientific configuration.
"""
import copy
from ..common import TERMINAL,encode,ensure,now,sha


def accepted(job,execution,current):
    if job['execution_profile']==current:return True
    r=execution.get('controller_upgrade') or {}
    return (r.get('job_id')==job['job_id'] and r.get('run_id')==job['run_id'] and
            r.get('from_profile')==job['execution_profile'] and r.get('to_profile')==current and
            r.get('request_sha256')==job['request_artifact']['sha256'] and
            r.get('authorization') in ('USER_REQUESTED_CONTROLLER_REPAIR_20261008','USER_REQUESTED_LATENCY_MAINTENANCE_20261010') and
            r.get('checkpoint_sha256') is not None)


def authorize(rt,jid,target_profile,checkpoint_sha256,*,authorization='USER_REQUESTED_CONTROLLER_REPAIR_20261008',maintenance=None):
    """Operator calls this only for the tested deployment's exact profile."""
    with rt._tx() as db:
        ensure(authorization in ('USER_REQUESTED_CONTROLLER_REPAIR_20261008','USER_REQUESTED_LATENCY_MAINTENANCE_20261010') and
               (maintenance is not None)==(authorization=='USER_REQUESTED_LATENCY_MAINTENANCE_20261010'),
               'INVALID_REQUEST','Explicit maintenance receipt required')
        job=rt._job(db,jid);ex=rt._execution(db,jid)
        ensure(job['tool_id']=='t01.real.local_workflow' and job['state']=='running' and
               not job['stop_reason'] and not ex.get('dispatcher') and
               not ex.get('pending_confirmation') and not ex.get('fatal_error'),
               'INVALID_STATE','Controller must be quiescent and recoverable')
        ensure(sha(encode(ex))==checkpoint_sha256,'INVALID_STATE','Repair checkpoint changed')
        ensure(set(target_profile)=={'id','version','sha256'} and
               target_profile['id']==job['execution_profile']['id'] and
               len(target_profile['sha256'])==64,'INVALID_REQUEST','Explicit tested controller profile required')
        for row in ex.get('nodes',{}).values():
            if not row.get('job_id'):continue
            child=rt._job(db,row['job_id'])
            ensure(child['run_id']==job['run_id'] and child['state'] in TERMINAL and
                   (not child.get('attempt_id') or rt._execution(db,child['job_id']).get('tree_stopped') is True),
                   'INVALID_STATE','Existing children must be stopped before controller upgrade')
        receipt=dict(job_id=jid,run_id=job['run_id'],from_profile=job['execution_profile'],
            to_profile=copy.deepcopy(target_profile),request_sha256=job['request_artifact']['sha256'],
            checkpoint_sha256=checkpoint_sha256,authorized_at=now(),
            authorization=authorization,
            deadline_reset=False,budget_reset=False,scientific_consent_added=False)
        ensure(not ex.get('controller_upgrade'),'INVALID_STATE','Controller already has an upgrade receipt')
        if maintenance is not None:
            receipt['maintenance']=copy.deepcopy(maintenance)
        ex['controller_upgrade']=receipt
        rt._execution_store(db,jid,ex)
        rt._store(db,copy.deepcopy(job),job,'controller_upgrade_authorized')
        return receipt
