"""Local trusted-operator CLI. Does not expose arbitrary commands or scientific execution."""
import argparse
import sys

from .common import TOOL, RuntimeFault, encode, new_id, profile
from .files import read_locked
from .runtime import Runtime


def main(argv=None):
    parser = argparse.ArgumentParser(description='W1 local engineering runtime (Windows, ENGINEERING_FIXTURE only)')
    parser.add_argument('--root', required=True, help='Absolute, dedicated local runtime directory')
    sub = parser.add_subparsers(dest='operation', required=True)
    sub.add_parser('profile')
    create = sub.add_parser('create-run'); create.add_argument('--key', required=True)
    stage = sub.add_parser('stage'); stage.add_argument('--run-id', required=True); stage.add_argument('--input', required=True)
    for name in ['submit', 'control']:
        cmd = sub.add_parser(name); cmd.add_argument('--input', required=True)
    for name in ['get', 'dispatch', 'cancel', 'retry', 'recover', 'wait', 'events']:
        cmd = sub.add_parser(name); cmd.add_argument('--job-id', required=True)
        if name in ['cancel', 'retry']: cmd.add_argument('--key', required=True)
    demo = sub.add_parser('demo', help='Create and execute one explicitly marked engineering fixture')
    demo.add_argument('--mode', choices=['echo', 'fail', 'sleep', 'tree', 'partial', 'wrong_identity'], default='echo')
    demo.add_argument('--delay', type=float, default=0)
    demo.add_argument('--payload', default='W1 engineering bytes')
    args = parser.parse_args(argv)
    try:
        runtime = Runtime(args.root)
        op = args.operation
        if op == 'profile': value = profile()
        elif op == 'create-run': value = runtime.create_run(args.key)
        elif op == 'stage': value = runtime.stage_request(args.run_id, read_locked(args.input, 65536))
        elif op in ['submit', 'control']: value = getattr(runtime, op)(read_locked(args.input, 65536))
        elif op in ['cancel', 'retry']:
            value = runtime.control(encode(dict(contract_version='0.1.0', operation=op, job_id=args.job_id, idempotency_key=args.key)))
        elif op == 'demo':
            run = runtime.create_run(new_id('request'))
            ref = runtime.stage_request(run['run_id'], encode(dict(mode=args.mode, delay_seconds=args.delay, payload=args.payload)))
            body = dict(contract_version='0.1.0', run_id=run['run_id'], request_id=new_id('request'),
                        idempotency_key=new_id('request'), tool_id=TOOL, node_id=None, run_mode='engineering_example',
                        request_artifact=ref, execution_profile=profile(), rule_profile=None)
            value = runtime.submit(encode(body))
            runtime.dispatch(value['job_id'])
            value = runtime.wait(value['job_id'])
        else: value = getattr(runtime, op)(args.job_id)
        print(encode(value).decode())
        return 0  # A valid API response, including a failed job, is distinct from request rejection.
    except RuntimeFault as exc:
        print(encode(exc.envelope()).decode())
        return 20
    except OSError:
        print(encode(RuntimeFault('ASSET_MISSING', 'Local storage or process operation failed').envelope()).decode())
        return 21
