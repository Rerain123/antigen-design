"""Explicit operator receipt for a quiescent, source-only latency repair.

No public submit option: the operator first pauses admission and waits for all
existing children to stop. Exact source manifests constrain this migration.
"""
import copy
from datetime import datetime
from ..common import TERMINAL, REPO, encode, ensure, now, sha

AUTHORIZATION = 'USER_REQUESTED_LATENCY_MAINTENANCE_20261010'
ALLOWED = frozenset('t01_phase1_real/' + p for p in (
    'service_api/replay_cache.py',
    'development/workflow/service.py', 'development/workflow/revision_controller.py',
    'development/workflow/confirmation.py', 'development/workflow/revision_v2_runtime.py',
    'service_api/controller_recovery.py', 'service_api/controller_maintenance.py'))


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def authorize(rt, jid, checkpoint_sha256, paused_at, previous_manifest, previous_predictor):
    from ..development.workflow import policy
    from ..development.bepipred.policy import registered_profile
    from .controller_recovery import authorize as upgrade
    current = {p.relative_to(REPO/'src').as_posix(): sha(p.read_bytes())
               for package in ('t01_phase1_real', 't01_structure_mapping')
               for p in (REPO/'src'/package).rglob('*')
               if p.is_file() and p.suffix != '.pyc' and '__pycache__' not in p.parts}
    changes = {n for n in set(current) | set(previous_manifest) if current.get(n) != previous_manifest.get(n)}
    ensure(changes and changes <= ALLOWED and not set(previous_manifest) - set(current),
           'PROFILE_NOT_APPROVED', 'Maintenance changes extend beyond reviewed controller optimization')
    ended = now()
    with rt._tx() as db:
        job = rt._job(db, jid); ex = rt._execution(db, jid)
        ensure(sha(encode(ex)) == checkpoint_sha256 and not ex.get('controller_maintenance'),
               'INVALID_STATE', 'Maintenance checkpoint changed or was already resumed')
        duration = (stamp(ended) - stamp(paused_at)).total_seconds()
        ensure(stamp(ex['started_at']) <= stamp(paused_at) <= stamp(ended) and duration >= 0,
               'INVALID_REQUEST', 'Invalid observed maintenance interval')
        bp = rt._job(db, ex['nodes']['bepipred']['job_id'])
        ensure(bp['state'] == 'succeeded' and bp['run_id'] == job['run_id'] and
               bp['execution_profile'] == previous_predictor,
               'PROFILE_NOT_APPROVED', 'Original WT predictor identity differs')
    # The common upgrade transaction checks quiescence and every child again.
    receipt = upgrade(rt, jid, policy.registered_profile(), checkpoint_sha256,
                      authorization=AUTHORIZATION,
                      maintenance=dict(paused_at=paused_at, resumed_at=ended, excluded_seconds=duration,
                          previous_source_sha256=sha(encode(previous_manifest)),
                          source_sha256=sha(encode(current)), changed_sources=sorted(changes),
                          predictor_profiles=[copy.deepcopy(previous_predictor), registered_profile()],
                          scientific_sources_unchanged=True))
    return receipt


def same_predictor(job, ex, left, right):
    if left == right: return True
    if not left or not right: return False
    receipt = ex.get('controller_upgrade') or {}
    maintenance = receipt.get('maintenance') or {}
    profiles = maintenance.get('predictor_profiles', [])
    return bool(receipt.get('authorization') == AUTHORIZATION and
                receipt.get('job_id') == job['job_id'] and receipt.get('run_id') == job['run_id'] and
                receipt.get('request_sha256') == job['request_artifact']['sha256'] and
                maintenance.get('scientific_sources_unchanged') is True and len(profiles) == 2 and
                left.get('execution') in profiles and right.get('execution') in profiles and
                {k:v for k,v in left.items() if k != 'execution'} ==
                {k:v for k,v in right.items() if k != 'execution'})
