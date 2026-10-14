"""CPU-owned GPU lifecycle; scientific requests keep their resident identities.

A GPU session drains the existing three queues, then parks without accepting
new work. The CPU controller scales its dedicated Deployment to zero and waits
for Pod deletion before starting another session. Neither component creates a
business job or replays an uncertain scientific execution.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import signal
import time
import uuid

from .gpu_dispatch import Kubernetes
from .resident_process import atomic, run
from . import unified_gpu_worker as unified

SESSION_ENV = 'T01_GPU_SESSION_ID'
POD_ENV = 'T01_GPU_POD_UID'
SESSION_ANNOTATION = 'antigen-design/gpu-session'
LABEL = 'antigen-design/gpu-demand-slot'
STARTUP_FAILURES = {'ErrImagePull', 'ImagePullBackOff', 'InvalidImageName',
                    'CreateContainerConfigError', 'CreateContainerError', 'RunContainerError'}


def session_file(state_root, session):
    if not re.fullmatch('[a-f0-9]{32}', session):
        raise ValueError('Invalid GPU session identity')
    return Path(state_root) / 'on-demand' / (session + '.json')


def normalized_template(template):
    value = copy.deepcopy(template)
    value['metadata'].setdefault('annotations', {}).pop(SESSION_ANNOTATION, None)
    env = value['spec']['containers'][0]['env']
    selected = [row for row in env if row['name'] == SESSION_ENV]
    if len(selected) != 1 or set(selected[0]) != {'name', 'value'}:
        raise ValueError('Expected a single literal GPU session environment')
    selected[0]['value'] = 'UNASSIGNED'
    return value


def contains(actual, expected):
    """Allow API-defaulted object fields, but no additional list entries."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v)
                                              for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            contains(a, b) for a, b in zip(actual, expected))
    return actual == expected


def record(path):
    value, digest = unified.read_json(Path(path))
    if not isinstance(value, dict):
        raise ValueError('GPU lifecycle record must be an object')
    return value, digest


def worker_state(state_root):
    path = Path(state_root) / 'state.json'
    return record(path)[0] if path.exists() or path.is_symlink() else {'phase': 'idle'}


def cancel_unstarted(spools, rows, execute=run):
    """Called only after the GPU Deployment is zero and every slot Pod is gone."""
    for row in rows:
        target = Path(row['target'])
        if row['uncertain']:
            raise RuntimeError('Unconfirmed execution needs recovery')
        if not (target / 'cancel').exists():
            continue
        if (target / 'execution.json').exists():
            raise RuntimeError('Cancellation raced an execution receipt')
        receipt = execute(target, spools[target.parent][row['tool']], lambda: True)
        request, digest = unified.read_json(target / 'request.json')
        if (receipt.get('state') != 'cancelled' or receipt.get('stopped_confirmed') is not True
                or receipt.get('binding') != request['binding']
                or receipt.get('request_sha256') != digest):
            raise RuntimeError('Pre-start cancellation was not confirmed')


def tick(config, spools, state_path, api, *, cancel_execute=run, new_session=lambda: uuid.uuid4().hex):
    state_path = Path(state_path)
    state = record(state_path)[0] if state_path.exists() or state_path.is_symlink() else {'phase': 'idle'}
    live = api.deployment()
    if (live['metadata']['name'] != config['deployment']
            or live['spec']['strategy'] != {'type': 'Recreate'}
            or live['spec'].get('replicas') not in (0, 1)
            or not contains(normalized_template(live['spec']['template']), config['template'])):
        raise RuntimeError('GPU slot deployment differs from approved template')
    actual_spec = live['spec']['template']['spec']
    for kind in ('containers', 'initContainers'):
        for actual, expected in zip(actual_spec.get(kind, []), config['template']['spec'].get(kind, [])):
            if actual.get('resources', {}) != expected.get('resources', {}):
                raise RuntimeError('GPU slot resource requests changed')
    if state.get('deployment_uid', live['metadata']['uid']) != live['metadata']['uid']:
        raise RuntimeError('GPU slot deployment was replaced')
    all_pods = api.pods()
    pods = [p for p in all_pods if p['metadata'].get('labels', {}).get(LABEL) == config['deployment']]
    replicas = live['spec']['replicas']
    phase = state['phase']

    def save(**updates):
        state.update(updates)
        atomic(state_path, state)

    def release(reason, quarantine=False):
        save(phase='releasing', release_reason=reason, quarantine=quarantine)
        api.patch(live, [{'op': 'replace', 'path': '/spec/replicas', 'value': 0}])
        return 'release'

    # Finish a committed release even if new work arrived or a receipt is faulty.
    if phase == 'releasing':
        if replicas:
            api.patch(live, [{'op': 'replace', 'path': '/spec/replicas', 'value': 0}])
            return 'release'
        if pods:
            return 'wait_for_pod_deletion'
        save(phase='blocked' if state.get('quarantine') else 'idle')
        return 'blocked' if state.get('quarantine') else 'released'
    if phase == 'blocked':
        raise RuntimeError('GPU released; uncertain session needs operator recovery')
    if phase not in {'idle', 'starting', 'active'}:
        raise ValueError('Unknown GPU lifecycle state')
    if phase != 'idle' and replicas:
        template = live['spec']['template']
        active_session = next(row['value'] for row in template['spec']['containers'][0]['env']
                              if row['name'] == SESSION_ENV)
        if template['metadata'].get('annotations', {}).get(SESSION_ANNOTATION) != state['session'] or active_session != state['session']:
            raise RuntimeError('Active GPU session changed')
    if phase != 'idle':
        if len(pods) > 1:
            return release('multiple_slot_pods', True)
        if pods:
            pod = pods[0]
            pod_uid = pod['metadata']['uid']
            if state.get('pod_uid', pod_uid) != pod_uid:
                return release('replacement_pod', True)
            if not state.get('pod_uid'):
                save(pod_uid=pod_uid)
            statuses = (pod.get('status', {}).get('containerStatuses', [])
                        + pod.get('status', {}).get('initContainerStatuses', []))
            if (pod.get('status', {}).get('phase') in {'Succeeded', 'Failed'}
                    or any(c.get('restartCount', 0) for c in statuses)):
                return release('worker_ended_or_restarted', True)
            if any(c.get('state', {}).get('waiting', {}).get('reason') in STARTUP_FAILURES for c in statuses):
                return release('container_startup_failed', True)
        receipt_path = session_file(config['state_root'], state['session'])
        if receipt_path.exists() or receipt_path.is_symlink():
            try:
                receipt, _ = record(receipt_path)
            except (OSError, ValueError, KeyError, TypeError):
                return release('invalid_session_receipt', True)
            if receipt.get('session') != state['session'] or receipt.get('pod_uid') != state.get('pod_uid'):
                return release('session_receipt_identity_mismatch', True)
            if receipt.get('phase') == 'blocked':
                return release('worker_blocked', True)
            if receipt.get('phase') == 'quiescent':
                try:
                    idle = worker_state(config['state_root'])['phase'] == 'idle'
                    rows = unified.pending(spools)
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    return release('invalid_execution_evidence', True)
                if receipt.get('stopped_confirmed') is not True or not idle or any(r['uncertain'] for r in rows):
                    return release('stop_not_confirmed', True)
                return release('queue_drained')
            if receipt.get('phase') != 'active':
                return release('invalid_session_receipt', True)

    if phase == 'idle':
        if replicas or pods:
            raise RuntimeError('Unowned GPU slot must be stopped before activation')
        for p in all_pods:
            if not p['metadata']['name'].startswith('antigen-') or p.get('status', {}).get('phase') in {'Failed', 'Succeeded'}:
                continue
            cs = p['spec'].get('containers', []) + p['spec'].get('initContainers', [])
            if any(c.get('resources', {}).get(k, {}).get('nvidia.com/gpu') for c in cs for k in ('requests', 'limits')):
                raise RuntimeError('Another project GPU holder remains')
        if worker_state(config['state_root'])['phase'] != 'idle':
            raise RuntimeError('Prior unified GPU owner needs recovery')
        rows = unified.pending(spools)
        if any(r['uncertain'] for r in rows):
            raise RuntimeError('Unconfirmed execution needs recovery')
        cancel_unstarted(spools, rows, cancel_execute)
        rows = unified.pending(spools)
        if not rows:
            return 'idle'
        session = new_session()
        if session_file(config['state_root'], session).exists():
            raise RuntimeError('GPU session identity was already used')
        atomic(state_path, dict(phase='starting', session=session, deployment_uid=live['metadata']['uid']))
        return 'reserved'

    annotation = live['spec']['template']['metadata'].get('annotations', {}).get(SESSION_ANNOTATION)
    env = live['spec']['template']['spec']['containers'][0]['env']
    env_index = next(i for i, row in enumerate(env) if row['name'] == SESSION_ENV)
    if replicas and (annotation != state['session'] or env[env_index]['value'] != state['session']):
        raise RuntimeError('Active GPU session changed')
    if phase == 'starting' and not replicas:
        if pods:
            return 'wait_for_pod_deletion'
        if worker_state(config['state_root'])['phase'] != 'idle':
            raise RuntimeError('Prior unified GPU owner needs recovery')
        cancel_unstarted(spools, unified.pending(spools), cancel_execute)
        if not unified.pending(spools):
            save(phase='idle')
            return 'cancelled_before_start'
        api.patch(live, [
            {'op': 'add', 'path': '/spec/template/metadata/annotations/antigen-design~1gpu-session', 'value': state['session']},
            {'op': 'replace', 'path': f'/spec/template/spec/containers/0/env/{env_index}/value', 'value': state['session']},
            {'op': 'replace', 'path': '/spec/replicas', 'value': 1}])
        # If this process crashes, the persisted intent observes this same patch.
        save(phase='active')
        return 'start'
    if phase == 'starting':
        save(phase='active')
        return 'observe'
    if not replicas or (state.get('pod_uid') and not pods):
        return release('slot_disappeared', True)
    try:
        rows = unified.pending(spools)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return release('invalid_execution_evidence', True)
    # A cancelled request must not wait for a busy GPU just to acknowledge cancel.
    if rows and all((Path(r['target']) / 'cancel').exists() for r in rows):
        return release('all_requests_cancelled')
    if not rows and not receipt_path.exists():
        # Work may have been cancelled/completed before this session acquired a
        # GPU. It should not retain a pending reservation for an empty queue.
        return release('no_pending_requests')
    return 'wait'


def drain(spools, state_root, session, pod_uid, stopping, execute=run):
    """Run under the same lifetime owner.lock as the former permanent worker."""
    path = session_file(state_root, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        prior, _ = record(path)
        if prior.get('session') == session and prior.get('pod_uid') == pod_uid and prior.get('phase') in {'quiescent', 'blocked'}:
            return prior  # A restarted container must park, never consume new work.
        value = dict(session=session, pod_uid=pod_uid, phase='blocked', diagnostic='session_restarted')
        atomic(path, value)
        return value
    atomic(path, dict(session=session, pod_uid=pod_uid, phase='active'))
    try:
        while not stopping():
            result = unified.tick(spools, Path(state_root) / 'state.json', stopping, execute)
            if result is None:
                if worker_state(state_root)['phase'] != 'idle':
                    raise RuntimeError('Cannot release an active owner')
                value = dict(session=session, pod_uid=pod_uid, phase='quiescent', stopped_confirmed=True)
                atomic(path, value)
                return value
        value = dict(session=session, pod_uid=pod_uid, phase='stopping')
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError) as exc:
        value = dict(session=session, pod_uid=pod_uid, phase='blocked', diagnostic=type(exc).__name__)
    atomic(path, value)
    return value


def main():
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['controller', 'worker'])
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    controller = unified.read_json(args.config)[0] if args.mode == 'controller' else None
    path = controller['worker_config'] if controller else args.config
    config, spools = unified.configured(path)
    state_root = Path(config['state_root'])
    state_root.mkdir(parents=True, exist_ok=True)
    for root in spools:
        root.mkdir(parents=True, exist_ok=True)
    if controller and controller['state_root'] != str(state_root):
        raise ValueError('Controller/worker state directories differ')
    os.environ['T01_PROCESS_REGISTRY'] = str(state_root / '.processes')
    lifecycle = state_root / 'on-demand'
    lifecycle.mkdir(parents=True, exist_ok=True)
    lock_path = lifecycle / 'controller.lock' if controller else state_root / 'owner.lock'
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    stopping = [False]
    signal.signal(signal.SIGTERM, lambda *unused: stopping.__setitem__(0, True))
    signal.signal(signal.SIGINT, lambda *unused: stopping.__setitem__(0, True))
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if controller:
            api = Kubernetes(controller['namespace'], controller['deployment'])
            while not stopping[0]:
                try:
                    result = tick(controller, spools, lifecycle / 'controller.json', api)
                    if result not in {'wait', 'idle', 'wait_for_pod_deletion'}:
                        print(json.dumps(dict(event='gpu_on_demand', action=result)), flush=True)
                except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                    print(json.dumps(dict(event='gpu_on_demand_blocked', diagnostic=type(exc).__name__)), flush=True)
                time.sleep(2)
        else:
            device = unified.gpu_guard(config['uuid'])
            # Keep observed hardware after the ephemeral GPU Pod is removed.
            session_path = session_file(state_root, os.environ[SESSION_ENV])
            device_path = session_path.with_name(session_path.stem + '-gpu.json')
            observation = dict(session=os.environ[SESSION_ENV], pod_uid=os.environ[POD_ENV], device=device)
            if device_path.exists() or device_path.is_symlink():
                if record(device_path)[0] != observation:
                    raise RuntimeError('GPU session hardware identity changed')
            else:
                atomic(device_path, observation)
            print(json.dumps(device), flush=True)
            print(json.dumps(drain(spools, state_root, os.environ[SESSION_ENV], os.environ[POD_ENV], lambda: stopping[0])), flush=True)
            # A Deployment uses restartPolicy=Always. Stay parked until scale-down;
            # otherwise Kubernetes would restart it and retain the GPU reservation.
            while not stopping[0]:
                time.sleep(.25)
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    main()
