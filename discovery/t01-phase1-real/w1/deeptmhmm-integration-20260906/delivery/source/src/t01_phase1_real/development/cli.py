"""Single trusted-local entry for task admission, lifecycle and immutable results."""
import argparse
from pathlib import Path

from ..common import TOOL as ENGINEERING, RuntimeFault, encode, profile
from ..files import read_locked
from .policy import TOOL, registered_profile
from .runtime import Runtime


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True)
    sub=p.add_subparsers(dest='operation',required=True)
    sub.add_parser('profile')
    c=sub.add_parser('create-run');c.add_argument('--key',required=True)
    c=sub.add_parser('stage');c.add_argument('--run-id',required=True);c.add_argument('--input',required=True)
    c.add_argument('--tool',choices=[ENGINEERING,TOOL],default=ENGINEERING)
    for name in ['submit','control']:
        c=sub.add_parser(name);c.add_argument('--input',required=True)
    for name in ['get','dispatch','cancel','retry','recover','wait','events','execution','result']:
        c=sub.add_parser(name);c.add_argument('--job-id',required=True)
        if name in ['cancel','retry']:c.add_argument('--key',required=True)
        if name=='wait':c.add_argument('--seconds',type=int,default=60)
    c=sub.add_parser('artifact');c.add_argument('--job-id',required=True);c.add_argument('--artifact-id',required=True);c.add_argument('--output',required=True)
    c=sub.add_parser('deeptmhmm',help='Atomically submit a sequence and optionally run/wait')
    group=c.add_mutually_exclusive_group(required=True);group.add_argument('--sequence');group.add_argument('--input',help='Exact JSON request file')
    c.add_argument('--user-id',default='local-input');c.add_argument('--timeout',type=int,default=900)
    c.add_argument('--key',required=True);c.add_argument('--run',action='store_true');c.add_argument('--wait',type=int,default=0)
    a=p.parse_args(argv)
    try:
        rt=Runtime(a.root);op=a.operation
        if op=='profile':value=dict(engineering=profile(),deeptmhmm=registered_profile(),production_enabled=False)
        elif op=='deeptmhmm':
            raw=read_locked(a.input,65536) if a.input else encode(dict(protein_sequence=a.sequence,user_sequence_id=a.user_id,timeout_seconds=a.timeout))
            value=rt.submit_sequence(raw,a.key)
            if a.run:value=rt.dispatch(value['job_id'])
            if a.wait:
                ensure_wait(a.wait);value=rt.wait(value['job_id'],a.wait)
            if any(r['role'] in ('result','diagnostic') for r in value['artifacts']):
                value=dict(job=value,result=rt.result(value['job_id']))
        elif op=='create-run':value=rt.create_run(a.key)
        elif op=='stage':value=rt.stage_request(a.run_id,read_locked(a.input,65536),a.tool)
        elif op in ('submit','control'):value=getattr(rt,op)(read_locked(a.input,65536))
        elif op in ('cancel','retry'):value=rt.control(encode(dict(contract_version='0.1.0',operation=op,job_id=a.job_id,idempotency_key=a.key)))
        elif op=='wait':ensure_wait(a.seconds);value=rt.wait(a.job_id,a.seconds)
        elif op=='artifact':
            raw=rt.artifact_bytes(a.job_id,a.artifact_id)
            with Path(a.output).open('xb') as f:f.write(raw)
            value=dict(artifact_id=a.artifact_id,size_bytes=len(raw),output=str(Path(a.output).absolute()))
        else:value=getattr(rt,op)(a.job_id)
        print(encode(value).decode());return 0
    except RuntimeFault as exc:print(encode(exc.envelope()).decode());return 20
    except OSError:print(encode(RuntimeFault('ASSET_MISSING','Local storage/process operation failed').envelope()).decode());return 21


def ensure_wait(seconds):
    if not 1<=seconds<=1000:raise RuntimeFault('INVALID_REQUEST','Wait must be 1..1000 seconds')
