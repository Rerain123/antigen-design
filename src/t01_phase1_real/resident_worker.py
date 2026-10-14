"""Static resident worker polling a shared execution spool, without network APIs.

The control plane stages executions using resident_process.prepare. This process
alone launches commands registered in its operator-owned configuration. It does
not create business jobs, infer scientific results, or access Kubernetes/Docker.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import sys
import time

from .resident_process import Command, DEFAULT_FILE_SIZE_BYTES, encoded, run


def commands_from_file(path):
    document = json.loads(Path(path).read_bytes())
    if not isinstance(document, dict) or set(document) != {'version', 'commands'} or document['version'] != '0.1.0':
        raise ValueError('Expected resident worker configuration v0.1.0')
    rows = document['commands']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 32: raise ValueError('Bounded command registry required')
    registry = {}
    for row in rows:
        required = {'tool', 'argv', 'environment', 'memory_bytes'}
        if not isinstance(row, dict) or not (required <= set(row) <= required | {'file_size_bytes'}):
            raise ValueError('Exact registered command fields required')
        if not isinstance(row['argv'], list) or not isinstance(row['environment'], dict): raise ValueError('Invalid command')
        command = Command(row['tool'], tuple(row['argv']), tuple(sorted(row['environment'].items())),
                          row['memory_bytes'], row.get('file_size_bytes', DEFAULT_FILE_SIZE_BYTES))
        command.document()
        if command.tool in registry: raise ValueError('Duplicate tool registration')
        registry[command.tool] = command
    return registry


def cycle(root, commands, stopping=lambda: False):
    """One serialized scan. Diagnostic failures never become successful receipts."""
    results = []
    for target in sorted(Path(root).iterdir()):
        if stopping(): break
        if not re.fullmatch(r'[a-f0-9]{32}', target.name): continue
        if target.is_symlink() or not target.is_dir(): continue
        request_path = target / 'request.json'
        if not request_path.exists(): continue  # input staging has not been committed
        try:
            if request_path.is_symlink() or request_path.stat().st_size > 1024 ** 2: raise ValueError('Invalid execution request')
            state_path = target / 'execution.json'
            if state_path.is_symlink(): raise ValueError('Execution receipt symlink')
            if state_path.exists() and json.loads(state_path.read_bytes()).get('stopped_confirmed') is True: continue
            request = json.loads(request_path.read_bytes())
            tool = request['command']['tool']
            if tool not in commands: raise ValueError('Tool is not registered in this worker')
            result = run(target, commands[tool], stopping)
            results.append(dict(execution_id=target.name, state=result['state'], stopped_confirmed=result['stopped_confirmed']))
        except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            results.append(dict(execution_id=target.name, state='unconfirmed', diagnostic=str(exc)))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'linux': raise RuntimeError('Resident worker requires Linux')
    if not args.root.is_absolute() or not args.config.is_absolute(): raise ValueError('Absolute operator paths required')
    if args.root.is_symlink() or args.config.is_symlink(): raise ValueError('Worker configuration/root symlink')
    args.root.mkdir(parents=True, exist_ok=True)
    # Keep stop ownership evidence beside the execution spool across restarts.
    os.environ['T01_PROCESS_REGISTRY'] = str(args.root / '.processes')
    commands = commands_from_file(args.config)
    stopping = [False]
    def stop(signum, frame): stopping[0] = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    print(encoded(dict(event='resident_worker_ready', tools=sorted(commands))).decode(), flush=True)
    prior = {}
    while not stopping[0]:
        for row in cycle(args.root, commands, lambda: stopping[0]):
            if prior.get(row['execution_id']) != row:
                print(encoded(row).decode(), flush=True)
                prior[row['execution_id']] = row
        if args.once: break
        time.sleep(.25)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
