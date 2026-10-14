"""One permanently allocated GPU, one serial process owner, no cluster API.

Scientific commands remain isolated executables. A durable cross-spool intent
prevents an uncertain execution in one environment being bypassed by another.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time

from .resident_process import atomic, command_documents_equal, run
from .resident_worker import commands_from_file
from .gpu_device import POLICY, valid_identity

TERMINAL = {'succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'}


def read_json(path):
    if path.is_symlink() or path.stat().st_size > 1024 ** 2:
        raise ValueError('Unsafe worker record')
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def configured(path):
    config, _ = read_json(Path(path))
    if (set(config) != {'version', 'uuid', 'state_root', 'spools'}
            or config['version'] not in {'0.1.0', '0.2.0'}):
        raise ValueError('Expected unified GPU worker configuration v0.1.0 or v0.2.0')
    if config['version'] == '0.2.0' and config['uuid'] is not None:
        raise ValueError('Scheduler-selected configuration must not pin a GPU UUID')
    if config['version'] == '0.1.0' and (not isinstance(config['uuid'], str)
            or not re.fullmatch(r'GPU-[0-9a-f-]{36}', config['uuid'])):
        raise ValueError('Exact physical GPU UUID required')
    state_root = Path(config['state_root'])
    if not state_root.is_absolute() or state_root.is_symlink():
        raise ValueError('Absolute non-symlink state directory required')
    spools = {}
    all_tools = set()
    for row in config['spools']:
        if set(row) != {'root', 'config'}:
            raise ValueError('Unexpected spool fields')
        root, registry = Path(row['root']), Path(row['config'])
        if not root.is_absolute() or root.is_symlink() or not registry.is_absolute() or registry.is_symlink():
            raise ValueError('Unsafe operator spool/config path')
        commands = commands_from_file(registry)
        if root in spools or all_tools.intersection(commands):
            raise ValueError('Duplicate spool/tool registration')
        spools[root] = commands
        all_tools.update(commands)
    if not spools or len(spools) > 8:
        raise ValueError('Bounded nonempty spool registry required')
    return config, spools


def request_identity(target, commands, *, allow_completed=False):
    if target.is_symlink() or not re.fullmatch('[a-f0-9]{32}', target.name):
        raise ValueError('Unsafe execution directory')
    request, fingerprint = read_json(target / 'request.json')
    if request['execution_id'] != target.name:
        raise ValueError('Execution ID mismatch')
    receipt_path = target / 'execution.json'
    uncertain = False
    if receipt_path.exists() or receipt_path.is_symlink():
        receipt, _ = read_json(receipt_path)
        if receipt.get('request_sha256') != fingerprint or receipt.get('binding') != request['binding']:
            raise ValueError('Receipt identity mismatch')
        completed = receipt.get('stopped_confirmed') is True and receipt.get('state') in TERMINAL
        # Completed requests from a prior environment are immutable history.
        # Only new/pending requests must match this deployment's command registry.
        if completed and not allow_completed:
            return None
        uncertain = not completed
    tool = request['command']['tool']
    if tool not in commands or not command_documents_equal(commands[tool], request['command']):
        raise ValueError('Request differs from registered command')
    return dict(target=str(target), sha256=fingerprint, tool=tool, uncertain=uncertain,
                order=(target / 'request.json').stat().st_mtime_ns)


def pending(spools):
    result = []
    for root, commands in spools.items():
        for target in root.iterdir():
            if not re.fullmatch('[a-f0-9]{32}', target.name):
                continue
            if target.is_symlink():
                raise ValueError('Execution symlink')
            if not target.is_dir() or not (target / 'request.json').exists():
                continue
            row = request_identity(target, commands)
            if row is not None:
                result.append(row)
    return result


def tick(spools, state_path, stopping=lambda: False, execute=run):
    """Run at most one request; never clear ownership on an ambiguous exit."""
    state = read_json(state_path)[0] if state_path.exists() else {'phase': 'idle'}
    if state.get('phase') not in {'idle', 'active'}:
        raise ValueError('Unknown unified worker state')
    rows = pending(spools)
    if state['phase'] == 'active':
        active = state['execution']
        target = Path(active['target'])
        if target.parent not in spools:
            raise ValueError('Active execution outside registered spools')
        selected = request_identity(target, spools[target.parent], allow_completed=True)
        if selected['sha256'] != active['sha256'] or selected['tool'] != active['tool']:
            raise ValueError('Active execution identity changed')
        if any(row['uncertain'] and row['target'] != str(target) for row in rows):
            raise RuntimeError('Another unconfirmed owner blocks all GPU tools')
    else:
        if any(row['uncertain'] for row in rows):
            raise RuntimeError('Unowned unconfirmed execution blocks all GPU tools')
        if not rows or stopping():
            return None
        selected = min(rows, key=lambda row: (row['order'], row['target']))
        target = Path(selected['target'])
        atomic(state_path, dict(phase='active', execution=selected))
    receipt = execute(target, spools[target.parent][selected['tool']], stopping)
    request, _ = read_json(target / 'request.json')
    if (receipt.get('stopped_confirmed') is not True or receipt.get('state') not in TERMINAL
            or receipt.get('request_sha256') != selected['sha256'] or receipt.get('binding') != request['binding']):
        raise RuntimeError('GPU process stop/receipt binding is unconfirmed')
    atomic(state_path, dict(phase='idle', last_execution=selected, last_state=receipt['state']))
    return dict(event='unified_gpu_execution_complete', tool=selected['tool'],
                execution_id=target.name, state=receipt['state'], stopped_confirmed=True)


def gpu_guard(uuid):
    raw = subprocess.check_output(['nvidia-smi', '--query-gpu=name,uuid,memory.total',
                                  '--format=csv,noheader,nounits'], text=True, timeout=20)
    rows = [row.split(',') for row in raw.strip().splitlines()]
    if len(rows) != 1 or len(rows[0]) != 3:
        raise RuntimeError('Exactly one GPU required')
    name, observed_uuid, memory = [v.strip() for v in rows[0]]
    capacity = float(memory)
    if uuid is None:
        observed = dict(name=name, uuid=observed_uuid, memory_mib=capacity)
        if not valid_identity(observed):
            raise RuntimeError('Invalid scheduler-assigned GPU identity')
        return dict(event='UNIFIED_SINGLE_GPU_GUARD_PASS', allocation_policy=POLICY, **observed)
    if name != 'NVIDIA A100-SXM-64GB' or observed_uuid != uuid or not math.isfinite(capacity) or capacity < 65536:
        raise RuntimeError('Approved 64GB GPU identity mismatch')
    return dict(event='UNIFIED_SINGLE_GPU_GUARD_PASS', name=name, uuid=uuid, memory_mib=capacity)


def main():
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config, spools = configured(args.config)
    state_root = Path(config['state_root'])
    state_root.mkdir(parents=True, exist_ok=True)
    for root in spools:
        root.mkdir(parents=True, exist_ok=True)
    # All spools now share one process ownership registry. Never migrate a live
    # request from the former per-environment registry into this deployment.
    os.environ['T01_PROCESS_REGISTRY'] = str(state_root / '.processes')
    descriptor = os.open(state_root / 'owner.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        device = gpu_guard(config['uuid'])
        atomic(state_root / 'device.json', device)
        print(json.dumps(device), flush=True)
        stopping = [False]
        signal.signal(signal.SIGTERM, lambda *args: stopping.__setitem__(0, True))
        signal.signal(signal.SIGINT, lambda *args: stopping.__setitem__(0, True))
        print(json.dumps(dict(event='unified_gpu_worker_ready', tools=sorted(t for c in spools.values() for t in c))), flush=True)
        prior_error = None
        while not stopping[0]:
            try:
                result = tick(spools, state_root / 'state.json', lambda: stopping[0])
                if result: print(json.dumps(result), flush=True)
                prior_error = None
            except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                if str(exc) != prior_error:
                    print(json.dumps(dict(event='unified_gpu_blocked', diagnostic=str(exc))), flush=True)
                    prior_error = str(exc)
            time.sleep(.25)
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    main()
