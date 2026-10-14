"""Fixed offline Docker backend with exact ownership checks and no arbitrary commands."""
import json
import subprocess

from ..common import RuntimeFault, encode, ensure, sha
from ..files import publish, within, read_locked
from .policy import IMAGE, PACKAGE, HERE, SLOT
from .registry import spec
from .structure import policy as structure
from .bepipred import policy as bepipred
from .netmhc import policy as netmhc
from .blast import policy as blast


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
    worker_name={structure.TOOL:'structure-development',bepipred.TOOL:'bepipred-development',netmhc.TOOL:'netmhc-development',
        blast.TOOL:'blast-development'}
    inherited=({'Description':'NCBI BLAST','Maintainer':'camacho@ncbi.nlm.nih.gov','Vendor':'NCBI/NLM/NIH','Version':'2.17.0',
        'org.opencontainers.image.ref.name':'ubuntu','org.opencontainers.image.version':'22.04'} if job['tool_id']==blast.TOOL else {})
    return {**inherited,'t01.worker':worker_name.get(job['tool_id'],'deeptmhmm-development'),'t01.root':sha(str(root).casefold().encode()),
            **{'t01.'+k:job[k] for k in ['run_id','job_id','attempt_id','execution_identity']}}


def inspect(root,identity=None):
    r=call(root,['inspect',identity or SLOT])
    if r.returncode:
        if b'no such object:' in r.stderr.lower() or b'no such container:' in r.stderr.lower(): return None
        raise RuntimeFault('ASSET_MISSING','Docker inspect failed; execution state unknown: '+r.stderr.decode(errors='replace')[:4096])
    return json.loads(r.stdout)[0]


def owned(root,job,info):
    return info is not None and info['Config']['Labels']==labels(root,job) and info['Config']['Image']==spec(job['tool_id']).IMAGE


def command(root,job,path,timeout,database_path=None):
    if job['tool_id']==structure.TOOL:return structure_command(root,job,path,timeout)
    if job['tool_id']==bepipred.TOOL:return bepipred_command(root,job,path,timeout)
    if job['tool_id']==netmhc.TOOL:return netmhc_command(root,job,path,timeout)
    if job['tool_id']==blast.TOOL:return blast_command(root,job,path,timeout,database_path)
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


def structure_command(root,job,path,timeout):
    argv=['create','--pull','never','--name',structure.SLOT]
    for key,val in labels(root,job).items():argv+=['--label',key+'='+val]
    argv+=['--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--pids-limit','64','--memory','1g','--memory-swap','1g','--cpus','2','--cpuset-cpus','0-1',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=128m','--env','PYTHONUNBUFFERED=1','--env','MPLCONFIGDIR=/tmp/matplotlib',
        '--mount',f'type=bind,source={structure.REPO/"src/t01_structure_mapping"},target=/code/t01_structure_mapping,readonly']
    # Explicit original source and input mounts; no root/project-wide writable mount.
    for source,target in [(structure.HERE,'/worker'),(structure.PROFILE,'/profile.json')]:
        argv+=['--mount',f'type=bind,source={source},target={target},readonly']
    for name in ['input.json','input.structure','binding.json']:
        argv+=['--mount',f'type=bind,source={within(root,path+"/"+name)},target=/{name},readonly']
    argv+=['--mount',f'type=bind,source={within(root,path+"/output")},target=/out',
        '--workdir','/worker','--entrypoint','timeout',structure.IMAGE,'--signal=KILL',str(timeout),'python','-B','/worker/worker.py']
    return argv


def bepipred_command(root,job,path,timeout):
    argv=['create','--pull','never','--name',bepipred.SLOT]
    for key,val in labels(root,job).items():argv+=['--label',key+'='+val]
    argv+=['--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--pids-limit','512','--memory','10g','--memory-swap','10g','--cpus','8','--cpuset-cpus','0-7',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=512m','--env','TORCH_HOME=/torch','--env','CUDA_VISIBLE_DEVICES=-1',
        '--mount',f'type=bind,source={bepipred.PACKAGE},target=/app,readonly',
        '--mount',f'type=bind,source={bepipred.MODELS},target=/torch/hub/checkpoints,readonly',
        '--mount',f'type=bind,source={bepipred.HERE/"worker.py"},target=/probe.py,readonly',
        '--mount',f'type=bind,source={within(root,path+"/input.fasta")},target=/input.fasta,readonly',
        '--mount',f'type=bind,source={within(root,path+"/output")},target=/out',
        '--workdir','/app','--entrypoint','timeout',bepipred.IMAGE,'--signal=KILL',str(timeout),'python','-B','/probe.py']
    return argv


def netmhc_command(root,job,path,timeout):
    argv=['create','--pull','never','--name',netmhc.SLOT]
    for key,val in labels(root,job).items():argv+=['--label',key+'='+val]
    argv+=['--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--pids-limit','128','--memory','4g','--memory-swap','4g','--cpus','4','--cpuset-cpus','0-3',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=512m','--env','PYTHONUNBUFFERED=1',
        '--mount',f'type=bind,source={netmhc.HERE/"worker.py"},target=/worker.py,readonly',
        '--mount',f'type=bind,source={within(root,path+"/input.json")},target=/input.json,readonly',
        '--mount',f'type=bind,source={within(root,path+"/input.fasta")},target=/input.fasta,readonly',
        '--mount',f'type=bind,source={within(root,path+"/output")},target=/out',
        '--workdir','/worker','--entrypoint','timeout',netmhc.IMAGE,'--signal=KILL',str(timeout),'python','-B','/worker.py']
    return argv


def blast_command(root,job,path,timeout,database_path):
    ensure(database_path is not None,'ASSET_MISSING','N03 database was not resolved')
    argv=['create','--pull','never','--name',blast.SLOT]
    for key,val in labels(root,job).items():argv+=['--label',key+'='+val]
    argv+=['--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--pids-limit','64','--memory','2g','--memory-swap','2g','--cpus','2','--cpuset-cpus','0-1',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=128m','--env','PYTHONUNBUFFERED=1',
        '--mount',f'type=bind,source={blast.HERE/"worker.py"},target=/worker.py,readonly',
        '--mount',f'type=bind,source={within(root,path+"/input.json")},target=/input.json,readonly',
        '--mount',f'type=bind,source={within(root,path+"/input.fasta")},target=/input.fasta,readonly',
        '--mount',f'type=bind,source={database_path},target=/database,readonly',
        '--mount',f'type=bind,source={within(root,path+"/output")},target=/out',
        '--workdir','/','--entrypoint','timeout',blast.IMAGE,'--signal=KILL',str(timeout),'python3','-B','/worker.py']
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
