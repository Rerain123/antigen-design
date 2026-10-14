"""Fixed, harmless byte-processing fixture. No shell, model, network or scientific tool."""
import argparse
import subprocess
import sys
import time

from .common import REPO, decode, encode, sha
from .files import publish, read_locked, within
from .winprocess import current_identity


def main():
    parser = argparse.ArgumentParser()
    for name in ['root', 'path', 'job-id', 'attempt-id', 'execution-identity']:
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    from pathlib import Path
    root = Path(args.root)
    if args.child:
        publish(root, args.path+'/child.json', encode(current_identity()))
        time.sleep(10)
        return 0
    raw = read_locked(within(root, args.path+'/input.json'))
    request = decode(raw)
    publish(root, args.path+'/worker-started.json', encode(current_identity()))
    if request['mode'] == 'tree':
        subprocess.Popen([sys.executable, '-X', 'utf8', str(REPO/'scripts/w1_runtime_worker.py'),
                          *sys.argv[1:], '--child'], cwd=within(root, args.path),
                         creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
    time.sleep(request['delay_seconds'])
    if request['mode'] == 'fail': return 7
    result = dict(job_id=args.job_id, attempt_id=args.attempt_id, execution_identity=args.execution_identity,
                  input_sha256=sha(raw), payload_sha256=sha(request['payload'].encode()), evidence_kind='ENGINEERING_FIXTURE')
    if request['mode'] == 'wrong_identity': result['attempt_id'] = 't01p1r-attempt-foreign'
    output = b'{"unfinished":' if request['mode'] == 'partial' else encode(result)
    publish(root, args.path+'/output.json', output)
    return 0
