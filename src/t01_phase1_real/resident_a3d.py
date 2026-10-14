"""Nested N10 execution on the existing resident spool, with durable stop ownership."""
from datetime import datetime, timezone
from pathlib import Path
import time
from types import SimpleNamespace

from .common import RuntimeFault, decode, encode, ensure, sha
from .files import read_locked, publish
from .resident_execution import configuration, registered
from .resident_process import (prepare, cancel, inventory, verify_inputs, safe_path,
                                encoded, command_documents_equal)
from .deployment.a3d import Pending
from .development.developability.aggrescan3d import IMAGE_ID, PYTHON_VERSION


def binding(job):
    return {k:job[k] for k in ('job_id','attempt_id','execution_identity')}


def context(rt,job,ex):
    config,fingerprint=configuration()
    command=registered(config['tools'].get('aggrescan3d'),'aggrescan3d',IMAGE_ID)
    volume=Path(config['runtime_volume_root']).resolve()
    root=Path(config['tools']['aggrescan3d']['root'])
    ensure(root.is_absolute() and root.resolve().is_relative_to(volume) and rt.root.resolve().is_relative_to(volume),
           'FORBIDDEN','N10 and resident A3D must share the runtime volume')
    target=safe_path(root,sha(encode(dict(binding(job),tool='aggrescan3d')))[:32])
    if ex.get('a3d_resident_target'):
        ensure(str(target)==ex['a3d_resident_target'] and fingerprint==ex['a3d_resident_config_sha256'],
               'PROFILE_NOT_APPROVED','Nested A3D configuration changed')
    return target,command,fingerprint


def receipt_for(target,job,command,input_hash):
    raw=read_locked(target/'request.json',1024**2)
    request=decode(raw)
    ensure(request['binding']==binding(job) and request['execution_id']==target.name
           and command_documents_equal(command, request['command'])
           and request['inputs']['input.pdb']['sha256']==input_hash,
           'OUTPUT_INVALID','Nested A3D request identity differs')
    if not (target/'execution.json').exists():return raw,request,None
    receipt=decode(read_locked(target/'execution.json',1024**2))
    ensure(receipt['backend']=='resident-process' and receipt['binding']==binding(job)
           and receipt['execution_id']==target.name and receipt['request_sha256']==sha(raw),
           'OUTPUT_INVALID','Nested A3D stop receipt identity differs')
    return raw,request,receipt


def pending(rt,job_id,reason):
    with rt._tx() as db:
        ex=rt._execution(db,job_id)
        ex.update(phase='a3d_resident_pending',dispatcher=None,a3d_resident_diagnostic=reason)
        rt._execution_store(db,job_id,ex)
    raise Pending(reason)


def run(rt,job,body,execution,files):
    job_id=job['job_id'];ex=rt.execution(job_id)
    target,command,fingerprint=context(rt,job,ex)
    input_raw=files['input/a3d-structure.pdb'];input_hash=sha(input_raw)
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(job['started_at'].replace('Z','+00:00'))).total_seconds()
    remaining=max(1,int(body['timeout_seconds']-elapsed))
    with rt._tx() as db:
        ex=rt._execution(db,job_id)
        ex.update(a3d_resident_target=str(target),a3d_resident_config_sha256=fingerprint,
                  a3d_resident_input_sha256=input_hash)
        rt._execution_store(db,job_id,ex)
    execution['command'].update(runtime='resident-process',network='seccomp-local-sockets-only-v1')
    execution['command'].pop('container_name',None)
    execution['command'].pop('pull',None)
    stopped=False
    try:
        current=rt.get(job_id)
        prepare(target.parent,target.name,binding(job),command,{'input.pdb':input_raw},remaining,
                cancel_requested=bool(current['stop_reason']) or elapsed>=body['timeout_seconds'])
        deadline=time.monotonic()+remaining
        while True:
            current=rt.get(job_id)
            if current['stop_reason'] or time.monotonic()>=deadline:
                if not current['stop_reason']:
                    with rt._tx() as db:rt._stop(db,rt._job(db,job_id),'timeout')
                cancel(target)
            raw,request,receipt=receipt_for(target,job,command,input_hash)
            if receipt and receipt.get('stopped_confirmed') is True:
                stopped=True;break
            if time.monotonic()>deadline+20:
                pending(rt,job_id,'A3D stop receipt pending')
            time.sleep(.2)
        with rt._tx() as db:
            ex=rt._execution(db,job_id)
            ex.update(a3d_resident_stop_confirmed=True,a3d_resident_receipt=receipt)
            rt._execution_store(db,job_id,ex)
        verify_inputs(target,request)
        ensure(receipt['outputs']==inventory(target),'OUTPUT_INVALID','A3D output inventory changed')
        for name in receipt['outputs']:
            data=read_locked(safe_path(target,name),32*1024**2)
            files['output/a3d-resident/'+name[7:]]=data
            if name.startswith('output/native/'):
                relative='output/a3d-native/'+name[len('output/native/'):]
                publish(rt.root,rt.attempt_path(job)+'/'+relative,data)
        execution['resident']=dict(request=request,receipt=receipt)
        if receipt['state']!='succeeded':
            return SimpleNamespace(returncode=124 if receipt['state']=='timed_out' else 1,stdout=b'',
                                   stderr=files.get('output/a3d-resident/stderr.txt',b''))
        native=decode(files['output/a3d-resident/native/execution.json'])
        ensure(receipt['exit_code']==0 and native['exit_code']==0 and native['input_sha256']==input_hash
               and native['python']==PYTHON_VERSION,'OUTPUT_INVALID','A3D native runtime differs')
        return SimpleNamespace(returncode=0,stdout=files['output/a3d-resident/native/stdout.txt'],
                               stderr=files['output/a3d-resident/native/stderr.txt'])
    except Pending:
        raise
    except (RuntimeFault,OSError,ValueError,KeyError,TypeError) as exc:
        if not stopped and (target/'request.json').exists():
            cancel(target);pending(rt,job_id,str(exc))
        raise


def validate(execution,files,job=None):
    """Revalidate the nested evidence when a published N10 result is consumed."""
    evidence=execution['resident'];request=evidence['request'];receipt=evidence['receipt']
    ensure(receipt['backend']=='resident-process' and receipt['binding']==request['binding']
           and receipt['execution_id']==request['execution_id'] and receipt['request_sha256']==sha(encoded(request))
           and receipt['stopped_confirmed'] is True,'OUTPUT_INVALID','A3D resident evidence mismatch')
    if job is not None:
        ensure(receipt['binding']==binding(job),'OUTPUT_INVALID','A3D belongs to a different N10 attempt')
    env=request['command']['environment']
    ensure(request['command']['tool']=='aggrescan3d' and env.get('T01_SOURCE_IMAGE_ID')==IMAGE_ID
           and env.get('T01_RESIDENT_OFFLINE')=='1','OUTPUT_INVALID','A3D source/offline command differs')
    ensure(request['inputs']['input.pdb']['sha256']==sha(files['input/a3d-structure.pdb']),
           'OUTPUT_INVALID','A3D resident input differs')
    for name,row in receipt['outputs'].items():
        raw=files['output/a3d-resident/'+name[7:]]
        ensure(len(raw)==row['size_bytes'] and sha(raw)==row['sha256'],'OUTPUT_INVALID','A3D resident output changed')
    if execution['status']=='executed':
        observation=decode(files['output/a3d-resident/executor-observation.json'])
        ensure(receipt['state']=='succeeded' and receipt['exit_code']==0 and observation['source_image_id']==IMAGE_ID
               and observation['machine']=='x86_64' and observation['network_restriction']=='seccomp-local-sockets-only-v1',
               'OUTPUT_INVALID','A3D execution isolation differs')
        paths={'A3D.csv':'run/A3D.csv','folded_stats.json':'run/tmp/folded_stats','input_output.txt':'run/tmp/input_output',
               'config.ini':'run/config.ini','output.pdb':'run/output.pdb','sasa.out':'run/tmp/sasa.out',
               'stdout.txt':'stdout.txt','stderr.txt':'stderr.txt'}
        for suffix,path in paths.items():
            ensure(files['output/a3d.'+suffix]==files['output/a3d-resident/native/'+path],
                   'OUTPUT_INVALID','A3D parsed file differs from native output')


def cleanup_interrupted(rt,job,ex):
    """Only cancel an existing owned request; never stage or rerun during recovery."""
    if ex.get('a3d_resident_stop_confirmed'):return True
    try:
        target,command,_=context(rt,job,ex)
        if not (target/'request.json').exists():return True
        _,_,receipt=receipt_for(target,job,command,ex['a3d_resident_input_sha256'])
        cancel(target)
        if not receipt or receipt.get('stopped_confirmed') is not True:return False
        with rt._tx() as db:
            saved=rt._execution(db,job['job_id'])
            saved.update(a3d_resident_stop_confirmed=True,a3d_resident_receipt=receipt)
            rt._execution_store(db,job['job_id'],saved)
        return True
    except (RuntimeFault,OSError,ValueError,KeyError,TypeError):return False
