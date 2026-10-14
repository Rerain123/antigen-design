"""Execute exactly one operator-registered resident request on one approved GPU."""
import argparse
import hashlib
import math
import os
from pathlib import Path
import signal
import subprocess
import time

from .resident_worker import commands_from_file
from .resident_process import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--uuid', required=True)
    args = parser.parse_args()
    target = Path(os.environ['T01_GPU_EXECUTION_TARGET'])
    if target.parent != args.root or target.is_symlink():
        raise ValueError('Execution outside registered spool')
    raw = (target / 'request.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != os.environ['T01_GPU_EXECUTION_SHA256']:
        raise ValueError('Request identity mismatch')
    rows = [r.split(',') for r in subprocess.check_output([
        'nvidia-smi', '--query-gpu=name,uuid,memory.total', '--format=csv,noheader,nounits'], text=True).strip().splitlines()]
    if len(rows) != 1 or rows[0][0].strip() != 'NVIDIA A100-SXM-64GB' or rows[0][1].strip() != args.uuid or not math.isfinite(float(rows[0][2])) or float(rows[0][2]) < 60000:
        raise ValueError('Expected single approved 64GB GPU')
    import json
    request = json.loads(raw)
    commands = commands_from_file(args.config)
    command = commands[request['command']['tool']]
    os.environ['T01_PROCESS_REGISTRY'] = str(args.root / '.processes')
    stopping = [False]
    signal.signal(signal.SIGTERM, lambda *unused: stopping.__setitem__(0, True))
    signal.signal(signal.SIGINT, lambda *unused: stopping.__setitem__(0, True))
    receipt = run(target, command, lambda: stopping[0])
    print(json.dumps({'event': 'gpu_once_complete', 'state': receipt['state'], 'stopped_confirmed': receipt['stopped_confirmed']}), flush=True)
    # Keep Deployment from restarting a completed worker until controller scales down.
    while not stopping[0]:
        time.sleep(1)


if __name__ == '__main__':
    main()
