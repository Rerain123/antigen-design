"""Durable Docker supervision: ownership, offline limits, stop/recovery and publication."""
import argparse
from datetime import datetime, timedelta, timezone
import os
import time

from ..common import RuntimeFault, TERMINAL, decode, encode, ensure, now, sha
from ..files import no_links, publish, read_locked, read_verified, within
from ..winprocess import initialization_lock, current_identity
from . import docker, deeptmhmm
from .policy import IMAGE, registered_profile, request, sequence_id, verify_assets
from .runtime import Runtime
from .registry import spec, result as build_result
from .structure import policy as structure


def save(root,path,raw):
    """Keep the first observation; recovery verifies the recorded raw inventory."""
    dest=within(root,path)
    if dest.exists():return
    publish(root,path,raw)


def output_files(runtime,job):
    path=runtime.attempt_path(job);folder=within(runtime.root,path)
    result={};total=0
    for p in sorted(folder.rglob('*')):
        if 'published' in p.relative_to(folder).parts:continue
        no_links(p)
        if not p.is_file():continue
        raw=read_locked(p,32*1024**2);total+=len(raw)
        ensure(total<=128*1024**2 and len(result)<128,'OUTPUT_INVALID','Output exceeds bounded artifact inventory')
        result[p.relative_to(folder).as_posix()]=raw
    return result


def inspect_contract(info,tool_id=None):
    worker=spec(tool_id or 't01.real.deeptmhmm');limits=worker.LIMITS
    h=info['HostConfig']
    ensure(h['NetworkMode']=='none' and h['ReadonlyRootfs'] and h['Memory']==h['MemorySwap']==limits['memory']
        and h['NanoCpus']==limits['cpus']*10**9 and h['CpusetCpus']==limits['cpuset'] and h['PidsLimit']==limits['pids'],
        'OUTPUT_INVALID','Actual container isolation/resource policy differs')
    mounts={m['Destination']:m for m in info['Mounts']}
    readonly={'/code/t01_structure_mapping','/worker','/profile.json','/input.json','/input.structure','/binding.json'} if worker.TOOL==structure.TOOL else {'/app','/input.fasta','/probe.py'}
    ensure(set(mounts)==readonly|{'/out'} and all(not mounts[p]['RW'] for p in readonly) and mounts['/out']['RW'],
        'OUTPUT_INVALID','Container mount isolation differs')


def collect_stopped(runtime,job,info,recovered=False,error=None):
    worker=spec(job['tool_id'])
    ex=runtime.execution(job['job_id']);path=runtime.attempt_path(job)
    receipt_path=within(runtime.root,path+'/receipt.json')
    receipt=None;receipt_error=None
    if receipt_path.exists():
        try:
            raw_receipt=read_locked(receipt_path)
            ensure(sha(raw_receipt)==ex.get('receipt_sha256'),'OUTPUT_INVALID','Recovery receipt hash mismatch')
            receipt=decode(raw_receipt)
            ensure(isinstance(receipt,dict) and receipt['job_id']==job['job_id'] and receipt['attempt_id']==job['attempt_id']
                and receipt['execution_identity']==job['execution_identity'] and receipt['stopped_confirmed'] is True,
                'OUTPUT_INVALID','Recovery receipt identity mismatch')
        except (RuntimeFault,KeyError,TypeError,ValueError) as exc:
            receipt=None;receipt_error=str(exc);error='OUTPUT_INVALID'
    if recovered and not receipt:error=error or 'INTERRUPTED'
    if info is not None:
        ensure(docker.owned(runtime.root,job,info) and not info['State']['Running'],
            'INVALID_STATE','Container is foreign or running')
        inspect_contract(info,job['tool_id'])
        logs=docker.call(runtime.root,['logs',info['Id']])
        save(runtime.root,path+'/stdout.txt',logs.stdout);save(runtime.root,path+'/stderr.txt',logs.stderr)
        save(runtime.root,path+'/container-inspect.json',encode(info))
        code=info['State']['ExitCode'];oom=info['State']['OOMKilled']
        if info['State']['Status']=='created':error=error or 'INTERRUPTED'
        if code in (124,137) and ex.get('deadline') and datetime.now(timezone.utc)>=datetime.fromisoformat(ex['deadline']):
            with runtime._tx() as db:
                current=runtime._job(db,job['job_id'])
                if not current['stop_reason']:runtime._stop(db,current,'timeout')
            job=runtime.get(job['job_id'])
        error=error or ('TOOL_FAILED' if code!=0 or oom else None)
    elif receipt:
        ensure(receipt['job_id']==job['job_id'] and receipt['attempt_id']==job['attempt_id']
            and receipt['execution_identity']==job['execution_identity'] and receipt['stopped_confirmed'],
            'OUTPUT_INVALID','Recovery receipt identity mismatch')
        code=receipt['exit_code'];oom=receipt['oom_killed'];error=error or receipt['error_code']
    else:
        code=None;oom=False;error=error or 'INTERRUPTED'
    diagnostic=receipt_error or ex.get('supervisor_diagnostic') or ('Supervisor interrupted; owned container stopped' if recovered and error else error)
    actual=dict(job_id=job['job_id'],attempt_id=job['attempt_id'],execution_identity=job['execution_identity'],
        exit_code=code,oom_killed=oom,error_code=error,diagnostic=diagnostic,stopped_confirmed=True,
        image_id=worker.IMAGE,container_id=info['Id'] if info else ex.get('container_id'),recovered=recovered)
    if job['stop_reason']:
        actual['error_code']='CANCELLED' if job['stop_reason']=='cancel' else 'TIMEOUT'
    if not receipt and not receipt_path.exists():
        raw_inventory=encode({n:sha(raw) for n,raw in output_files(runtime,job).items()})
        save(runtime.root,path+'/raw-inventory.json',raw_inventory)
        actual['raw_inventory_sha256']=sha(raw_inventory)
        save(runtime.root,path+'/receipt.json',encode(actual))
        ex['receipt_sha256']=sha(encode(actual))
        with runtime._tx() as db:runtime._execution_store(db,job['job_id'],ex)
    if info is not None:
        removed=docker.call(runtime.root,['rm',info['Id']])
        save(runtime.root,path+'/container-remove.json',encode(dict(exit_code=removed.returncode,stdout=removed.stdout.decode(errors='replace'),stderr=removed.stderr.decode(errors='replace'))))
        ensure(removed.returncode==0,'ASSET_MISSING','Stopped container cleanup unconfirmed')
    if ex.get('fault')=='crash_after_receipt' and not recovered:os._exit(94)
    files={}
    try:
        files=output_files(runtime,job)
        if receipt:
            evidence_path=within(runtime.root,path+'/raw-inventory.json')
            ensure(evidence_path.is_file(),'OUTPUT_INVALID','Missing recovery raw inventory')
            expected=decode(read_locked(evidence_path))
            ensure(sha(read_locked(evidence_path))==receipt['raw_inventory_sha256'],'OUTPUT_INVALID','Recovery inventory hash changed')
            ensure(all(n in files and sha(files[n])==h for n,h in expected.items()),'OUTPUT_INVALID','Recovery raw artifact hash changed')
        body=worker.request(read_verified(runtime.root,path+'/input.json',job['request_artifact']['sha256'],job['request_artifact']['size_bytes'],65536))
        ensure(job['execution_profile']==worker.registered_profile(),'OUTPUT_INVALID','Development profile changed during execution/recovery')
        expected_fasta=('>'+sequence_id(body['protein_sequence'])+'\n'+body['protein_sequence']+'\n').encode()
        ensure(files['input.fasta']==expected_fasta,'OUTPUT_INVALID','Executed FASTA binding differs')
        value=build_result(job,body,files,actual,ex.get('fault'))
    except (RuntimeFault,KeyError,ValueError) as exc:
        files['collection-error.json']=encode(dict(error=str(exc)))
        body=worker.request(runtime._request_bytes(job))
        actual.update(error_code='OUTPUT_INVALID',diagnostic=str(exc))
        value=build_result(job,body,files,actual,ex.get('fault'))
    ex.update(tree_stopped=True,container_stopped=True,container_exit_code=code,oom_killed=oom)
    return runtime._finish_development(job['job_id'],ex,files,value)


def supervise(root,scope,job_id):
    runtime=Runtime(root,scope)
    # One collector per attempt; recovery can acquire this mutex after supervisor death.
    with initialization_lock('Local\\T01-development-'+job_id):
        job=runtime.get(job_id);ex=runtime.execution(job_id)
        worker=spec(job['tool_id'])
        if job['state'] in TERMINAL:return
        with runtime._tx() as db:
            ensure(ex['phase']=='spawn_intent' and ex['supervisor'] is None,'INVALID_STATE','Supervisor cannot register twice')
            ex.update(phase='supervising',supervisor=current_identity());runtime._execution_store(db,job_id,ex)
        path=runtime.attempt_path(job)
        try:
            ensure(job['execution_profile']==worker.registered_profile(),'PROFILE_NOT_APPROVED','Worker profile changed after dispatch')
            body=worker.request(read_verified(runtime.root,path+'/input.json',job['request_artifact']['sha256'],job['request_artifact']['size_bytes'],65536))
            receipt=worker.verify_assets()
            save(runtime.root,path+'/assets-before.json',encode(dict(verified_files=len(receipt['files']),archive_sha256=receipt['archive_sha256'])))
            image=docker.call(runtime.root,['image','inspect','--format','{{.Id}}',worker.IMAGE])
            ensure(image.returncode==0 and image.stdout.decode().strip()==worker.IMAGE,'ASSET_MISSING','Pinned image not available locally')
            cmd=docker.command(runtime.root,job,path,body['timeout_seconds'])
            save(runtime.root,path+'/command.json',encode(dict(argv=docker.client(runtime.root)+cmd,profile=job['execution_profile'],binding=docker.labels(runtime.root,job))))
            if ex.get('fault'):
                save(runtime.root,path+'/fault.json',encode(dict(kind='CONTROLLED_INTEGRATION_FAULT',name=ex['fault'],source_output_preserved=True)))
            if ex.get('fault')=='tool_failure':within(runtime.root,path+'/output/result').mkdir()
            # Docker's unique fixed slot serializes models across runtime roots/processes.
            waiting=time.monotonic()
            while True:
                job=runtime.get(job_id)
                if job['stop_reason']:return collect_stopped(runtime,job,None,error='CANCELLED')
                info=docker.inspect(runtime.root,worker.SLOT)
                if info is None:
                    created=docker.call(runtime.root,cmd,30)
                    save(runtime.root,path+'/create.json',encode(dict(exit_code=created.returncode,stdout=created.stdout.decode(errors='replace'),stderr=created.stderr.decode(errors='replace'))))
                    if created.returncode!=0 and b'Conflict' not in created.stderr:
                        raise RuntimeFault('TOOL_FAILED','Docker create failed; inspect create.json')
                    info=docker.inspect(runtime.root,worker.SLOT)
                if docker.owned(runtime.root,job,info):break
                if time.monotonic()-waiting>=900:
                    with runtime._tx() as db:runtime._stop(db,runtime._job(db,job_id),'timeout')
                    return collect_stopped(runtime,runtime.get(job_id),None,error='TIMEOUT')
                time.sleep(.2)
            ex=runtime.execution(job_id)
            ex.update(container_id=info['Id'],deadline=(datetime.now(timezone.utc)+timedelta(seconds=body['timeout_seconds'])).isoformat(),container_started=True)
            with runtime._tx() as db:runtime._execution_store(db,job_id,ex)
            started=docker.call(runtime.root,['start',info['Id']],30)
            save(runtime.root,path+'/start.json',encode(dict(exit_code=started.returncode,stdout=started.stdout.decode(errors='replace'),stderr=started.stderr.decode(errors='replace'))))
            ensure(started.returncode==0,'TOOL_FAILED','Docker start failed')
            if ex.get('fault')=='crash_after_start':os._exit(93)
            while True:
                job=runtime.get(job_id);info=docker.inspect(runtime.root,ex['container_id'])
                ensure(docker.owned(runtime.root,job,info),'ASSET_MISSING','Owned execution is unavailable')
                if not job['stop_reason'] and datetime.now(timezone.utc)>=datetime.fromisoformat(ex['deadline']):
                    with runtime._tx() as db:runtime._stop(db,runtime._job(db,job_id),'timeout')
                    job=runtime.get(job_id)
                if job['stop_reason']:info=docker.stop(runtime.root,job,info)
                if not info['State']['Running']:break
                time.sleep(.15)
            worker.verify_assets()
            save(runtime.root,path+'/assets-after.json',encode(dict(verified_files=len(receipt['files']),archive_sha256=receipt['archive_sha256'])))
            return collect_stopped(runtime,job,info)
        except (RuntimeFault,OSError,ValueError) as exc:
            with runtime._tx() as db:
                ex=runtime._execution(db,job_id);ex['supervisor_diagnostic']=str(exc);runtime._execution_store(db,job_id,ex)
            try:
                job=runtime.get(job_id);info=docker.inspect(runtime.root,runtime.execution(job_id).get('container_id') or worker.SLOT)
                if docker.owned(runtime.root,job,info):info=docker.stop(runtime.root,job,info)
                else:info=None
                return collect_stopped(runtime,job,info,error=exc.code if isinstance(exc,RuntimeFault) else 'TOOL_FAILED')
            except (RuntimeFault,OSError,ValueError) as stop_error:
                runtime._unknown(job_id,str(stop_error))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['root','scope','job-id']:p.add_argument('--'+name,required=True)
    a=p.parse_args();supervise(a.root,a.scope,a.job_id)
