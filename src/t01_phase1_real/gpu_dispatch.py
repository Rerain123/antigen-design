"""Single-slot GPU dispatcher. Uses committed resident requests, not business jobs.

Only a dedicated GPU Deployment is changed. The service Deployment is never
restarted by this loop. Kubernetes deletion is confirmed before another mode
starts; ambiguous process receipts block replay rather than rerunning work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import time
import urllib.request

from .resident_process import atomic, command_documents_equal

TERMINAL = {'succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'}


def candidate(root, mode, commands):
    result = []
    for target in Path(root).iterdir():
        if not re.fullmatch('[a-f0-9]{32}', target.name) or target.is_symlink() or not target.is_dir():
            continue
        request_path = target / 'request.json'
        if not request_path.exists():
            continue
        if request_path.is_symlink() or request_path.stat().st_size > 1024 ** 2:
            raise ValueError('Unsafe resident request')
        raw = request_path.read_bytes()
        request = json.loads(raw)
        tool = request['command']['tool']
        if request['execution_id'] != target.name or not command_documents_equal(commands.get(tool), request['command']):
            raise ValueError('Request differs from operator command registry')
        fingerprint = hashlib.sha256(raw).hexdigest()
        receipt_path = target / 'execution.json'
        if receipt_path.exists():
            if receipt_path.is_symlink():
                raise ValueError('Symlink receipt')
            receipt = json.loads(receipt_path.read_bytes())
            if receipt.get('binding') != request['binding'] or receipt.get('request_sha256') != fingerprint:
                raise ValueError('Receipt identity mismatch')
            if receipt.get('stopped_confirmed') is True and receipt.get('state') in TERMINAL:
                continue
            # Even if an old Pod disappeared, never automatically replay uncertain work.
            result.append({'uncertain': True, 'mode': mode, 'target': str(target), 'sha256': fingerprint})
            continue
        result.append({'uncertain': False, 'mode': mode, 'target': str(target),
                       'sha256': fingerprint, 'order': request_path.stat().st_mtime_ns})
    return result


def choose(rows):
    if any(row['uncertain'] for row in rows):
        raise RuntimeError('Unconfirmed prior execution requires recovery; no GPU switch allowed')
    return min(rows, key=lambda row: (row['order'], row['mode'], row['target'])) if rows else None


def next_action(state, deployment, pods, pending):
    """Pure transition policy. State intent must be persisted before a mutation."""
    phase = state.get('phase', 'idle')
    replicas = deployment['spec'].get('replicas', 1)
    if phase == 'idle':
        if replicas != 0 or pods:
            raise RuntimeError('Idle dispatcher found an unexpected slot owner')
        if pending:
            if pending['uncertain']:
                raise RuntimeError('Unconfirmed prior execution')
            return 'reserve'
        return 'wait'
    execution = state['execution']
    if phase == 'reserved':
        annotation = deployment['spec']['template']['metadata'].get('annotations', {})
        if replicas == 1:
            if annotation.get('antigen-design/execution-sha256') != execution['sha256'] or annotation.get('antigen-design/execution-target') != execution['target']:
                raise RuntimeError('Slot deployment drift')
            return 'observe'  # A crash after patch must not submit a second workload.
        if pods:
            return 'wait'
        return 'start'
    if phase == 'running':
        annotation = deployment['spec']['template']['metadata'].get('annotations', {})
        if annotation.get('antigen-design/execution-sha256') != execution['sha256'] or annotation.get('antigen-design/execution-target') != execution['target']:
            raise RuntimeError('Running slot identity changed')
        if state.get('confirmed_terminal'):
            return 'release'
        if not pods and replicas == 0:
            raise RuntimeError('Slot disappeared before stop confirmation')
        if any(p.get('status', {}).get('phase') in ('Failed', 'Succeeded') for p in pods):
            raise RuntimeError('Worker ended without a confirmed resident receipt')
        return 'wait'
    if phase == 'releasing':
        if replicas != 0:
            return 'release'
        return 'wait' if pods else 'complete'
    raise ValueError('Unknown dispatcher phase')


class Kubernetes:
    def __init__(self, namespace, name):
        self.namespace, self.name = namespace, name
        self.base = 'https://' + os.environ['KUBERNETES_SERVICE_HOST'] + ':' + os.environ.get('KUBERNETES_SERVICE_PORT', '443')
        self.token = Path('/var/run/secrets/kubernetes.io/serviceaccount/token')
        self.tls = ssl.create_default_context(cafile='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')

    def request(self, path, method='GET', body=None):
        data = json.dumps(body).encode() if body is not None else None
        headers = {'Authorization': 'Bearer ' + self.token.read_text().strip()}
        if data is not None:
            headers['Content-Type'] = 'application/json-patch+json'
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, context=self.tls, timeout=20) as response:
            return json.load(response)

    @property
    def path(self):
        return f'/apis/apps/v1/namespaces/{self.namespace}/deployments/{self.name}'

    def deployment(self):
        return self.request(self.path)

    def pods(self):
        # Inspect all project holders, not only pods created by this dispatcher.
        return self.request(f'/api/v1/namespaces/{self.namespace}/pods')['items']

    def patch(self, live, changes):
        return self.request(self.path, 'PATCH', [
            {'op': 'test', 'path': '/metadata/uid', 'value': live['metadata']['uid']},
            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': live['metadata']['resourceVersion']},
            *changes])


def tick(config, state_path, api):
    state = json.loads(state_path.read_bytes()) if state_path.exists() else {'phase': 'idle'}
    deployment = api.deployment()
    if deployment['spec']['strategy'] != {'type': 'Recreate'}:
        raise RuntimeError('Single-slot deployment must use Recreate')
    if deployment['spec'].get('replicas', 1) not in (0, 1):
        raise RuntimeError('Multiple slot replicas are forbidden')
    all_pods = api.pods()
    pods = [p for p in all_pods if p['metadata'].get('labels', {}).get('app') == config['deployment']]
    if len(pods) > 1:
        raise RuntimeError('Multiple slot Pods are forbidden')
    for pod in all_pods:
        if pod in pods or not pod['metadata']['name'].startswith('antigen-'):
            continue
        if pod['status']['phase'] in ('Succeeded', 'Failed'):
            continue
        containers = pod['spec'].get('containers', []) + pod['spec'].get('initContainers', [])
        if any(c.get('resources', {}).get(k, {}).get('nvidia.com/gpu') for c in containers for k in ('limits', 'requests')):
            raise RuntimeError('Another project GPU holder remains')
    pending = None
    if state.get('phase', 'idle') == 'idle':
        rows = []
        for mode, definition in config['modes'].items():
            rows += candidate(definition['root'], mode, definition['commands'])
        pending = choose(rows)
    if state.get('phase') == 'running':
        target = Path(state['execution']['target'])
        receipt_path = target / 'execution.json'
        state['confirmed_terminal'] = False
        if receipt_path.exists():
            request = json.loads((target / 'request.json').read_bytes())
            receipt = json.loads(receipt_path.read_bytes())
            if receipt.get('request_sha256') != state['execution']['sha256'] or receipt.get('binding') != request['binding']:
                raise ValueError('Active receipt identity mismatch')
            state['confirmed_terminal'] = receipt.get('stopped_confirmed') is True and receipt.get('state') in TERMINAL
    action = next_action(state, deployment, pods, pending)
    if action == 'reserve':
        atomic(state_path, {'phase': 'reserved', 'execution': pending})
    elif action == 'start':
        import copy
        execution = state['execution']
        if hashlib.sha256((Path(execution['target']) / 'request.json').read_bytes()).hexdigest() != execution['sha256']:
            raise ValueError('Reserved request changed')
        template = copy.deepcopy(config['modes'][execution['mode']]['template'])
        containers = template['spec']['containers']
        if len(containers) != 1 or template['spec'].get('initContainers'):
            raise ValueError('Exactly one GPU worker container required')
        limits = containers[0].get('resources', {}).get('limits', {})
        if str(limits.get('nvidia.com/gpu')) != '1' or str(limits.get('nvidia.com/gpumem-percentage')) != '100' or str(limits.get('nvidia.com/gpucores')) != '100':
            raise ValueError('Expected one full GPU allocation')
        if template['metadata'].get('annotations', {}).get('nvidia.com/use-gputype') != 'A100-SXM-64GB':
            raise ValueError('64GB type constraint required')
        template['metadata'].setdefault('annotations', {}).update({
            'antigen-design/execution-sha256': execution['sha256'],
            'antigen-design/execution-target': execution['target']})
        template['spec']['containers'][0].setdefault('env', []).extend([
            {'name': 'T01_GPU_EXECUTION_TARGET', 'value': execution['target']},
            {'name': 'T01_GPU_EXECUTION_SHA256', 'value': execution['sha256']}])
        api.patch(deployment, [{'op': 'replace', 'path': '/spec/template', 'value': template},
                               {'op': 'replace', 'path': '/spec/replicas', 'value': 1}])
        atomic(state_path, {'phase': 'running', 'execution': execution})
    elif action == 'observe':
        atomic(state_path, {'phase': 'running', 'execution': state['execution']})
    elif action == 'release':
        atomic(state_path, {'phase': 'releasing', 'execution': state['execution']})
        api.patch(deployment, [{'op': 'replace', 'path': '/spec/replicas', 'value': 0}])
    elif action == 'complete':
        atomic(state_path, {'phase': 'idle', 'last_execution': state['execution']})
    return action


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_bytes())
    args.state.parent.mkdir(parents=True, exist_ok=True)
    # A lifetime OS lock prevents two controller processes on this shared volume.
    import fcntl
    with args.state.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        api = Kubernetes(config['namespace'], config['deployment'])
        while True:
            try:
                action = tick(config, args.state, api)
                if action != 'wait':
                    print(json.dumps({'event': 'gpu_dispatch', 'action': action}), flush=True)
            except Exception as exc:
                # Fail closed: no rollback to a second GPU and no replay of work.
                print(json.dumps({'event': 'gpu_dispatch_blocked', 'error_type': type(exc).__name__}), flush=True)
            time.sleep(2)


if __name__ == '__main__':
    main()
