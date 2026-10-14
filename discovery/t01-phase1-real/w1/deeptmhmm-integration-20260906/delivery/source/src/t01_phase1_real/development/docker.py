"""Fixed offline Docker backend with exact ownership checks and no arbitrary commands."""
import json
import subprocess

from ..common import RuntimeFault, encode, ensure, sha
from ..files import publish, within, read_locked
from .policy import IMAGE, PACKAGE, HERE, SLOT


def client(root):
    config=within(root,'docker-client/config.json')
    if not config.exists():
        try: publish(root,'docker-client/config.json',b'{}')
        except FileExistsError: pass
    ensure(read_locked(config,1024)==b'{}','FORBIDDEN','Dedicated Docker client must contain no credentials/settings')
    return ['docker','--config',str(config.parent),'--host','npipe:////./pipe/dockerDesktopLinuxEngine']


def call(root,args,timeout=20):
    try:
        return subprocess.run(client(root)+args,capture_output=True,timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise RuntimeFault('ASSET_MISSING','Local Docker operation unavailable or timed out') from exc


def labels(root,job):
    return {'t01.worker':'deeptmhmm-development','t01.root':sha(str(root).casefold().encode()),
            **{'t01.'+k:job[k] for k in ['run_id','job_id','attempt_id','execution_identity']}}


def inspect(root,identity=None):
    r=call(root,['inspect',identity or SLOT])
    if r.returncode:
        if b'no such object:' in r.stderr.lower() or b'no such container:' in r.stderr.lower(): return None
        raise RuntimeFault('ASSET_MISSING','Docker inspect failed; execution state unknown: '+r.stderr.decode(errors='replace')[:4096])
    return json.loads(r.stdout)[0]


def owned(root,job,info):
    return info is not None and info['Config']['Labels']==labels(root,job) and info['Config']['Image']==IMAGE


def command(root,job,path,timeout):
    argv=['create','--pull','never','--name',SLOT]
    for key,val in labels(root,job).items(): argv+=['--label',key+'='+val]
    argv+=['--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--pids-limit','512','--memory','10g','--memory-swap','10g','--cpus','8','--cpuset-cpus','0-7',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=512m','--env','CUDA_VISIBLE_DEVICES=-1','--env','PYTHONUNBUFFERED=1',
        '--mount',f'type=bind,source={PACKAGE},target=/app,readonly',
        '--mount',f'type=bind,source={within(root,path+"/input.fasta")},target=/input.fasta,readonly',
        '--mount',f'type=bind,source={HERE/"container_probe.py"},target=/probe.py,readonly',
        '--mount',f'type=bind,source={within(root,path+"/output")},target=/out',
        '--workdir','/app','--entrypoint','timeout',IMAGE,'--signal=KILL',str(timeout),'python','-B','/probe.py']
    return argv


def stop(root,job,info):
    ensure(owned(root,job,info),'FORBIDDEN','Refuse to stop a foreign container')
    if info['State']['Running']:
        r=call(root,['kill',info['Id']])
        if r.returncode:
            after=inspect(root,info['Id'])
            ensure(owned(root,job,after) and not after['State']['Running'],'ASSET_MISSING','Container stop unconfirmed')
    after=inspect(root,info['Id'])
    ensure(owned(root,job,after) and not after['State']['Running'],'ASSET_MISSING','Container stop unconfirmed')
    return after
