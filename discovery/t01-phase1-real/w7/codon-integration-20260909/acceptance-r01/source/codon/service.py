"""N16 isolated local worker with owned process-tree stop and durable publication."""
import copy
import ctypes
import sys
import time
from ...common import RuntimeFault,encode,decode,ensure,new_id,now,sha
from ...files import publish,within,read_locked
from ... import winprocess as wp
from . import policy
from .compute import table,summarize

def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()))
    value=dict(contract_version='0.1.0',tool_id=policy.TOOL,binding=binding,evidence_kind='G0_REAL_OUTPUT',
        qualification='DEVELOPMENT_UNREVIEWED',usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,
        production_status='NOT_DEPLOYED',requires_review=True,execution=execution,status='unreliable',dna=None,
        source_receipts=execution.get('source_receipts'),null_reason=execution.get('error_code'),controlled_fault=fault,
        method_summary=dict(rule_profile=job['rule_profile'],parameters=policy.PARAMETERS,network=False,
            scope='N16 independent engineering fragments only'),warnings=[])
    if execution.get('error_code'):return value
    try:
        ensure(execution['stopped_confirmed'] is True and execution['exit_code']==0,'OUTPUT_INVALID','Worker stop not confirmed')
        if body['expression_host'] is None:
            ensure(execution['worker_started'] is False,'OUTPUT_INVALID','Conditional skip unexpectedly ran optimizer')
            value.update(status='skipped_missing_expression_host',null_reason='EXPRESSION_HOST_NOT_PROVIDED')
            return value
        observation=decode(files['output/observation.json'])
        ensure(observation['input_hashes']=={k.removeprefix('input/'):sha(v) for k,v in files.items() if k.startswith('input/')}
            and observation['request_sha256']==job['request_artifact']['sha256']
            and observation['network_guard']=='python_audit_socket_and_subprocess_denied','OUTPUT_INVALID','Worker sources/guard differ')
        dna=summarize(body,observation['result'],table(files['input/codon-table.csv']))
        ensure(files['output/initial.fasta']==fasta('unoptimized',dna['initial_dna']) and
            (dna['optimized_dna'] is None and 'output/optimized.fasta' not in files or
             dna['optimized_dna'] is not None and files['output/optimized.fasta']==fasta('optimized-engineering',dna['optimized_dna'])),
            'OUTPUT_INVALID','DNA FASTA differs from verified report')
        ensure(execution['source_receipts']==decode(files['input/source-receipts.json']),'OUTPUT_INVALID','Source receipt differs')
        ensure(decode(files['input/execution-binding.json'])=={k:job[k] for k in ('job_id','attempt_id','execution_identity')},
            'OUTPUT_INVALID','Optimizer attempt binding differs')
        value.update(status=dna['status'].lower(),dna=dna,null_reason=None,
            warnings=[dict(code=r,level='quality',severity='WARNING',message=r) for r in dna['review_reasons']])
    except (RuntimeFault,KeyError,ValueError,TypeError) as exc:
        execution.update(error_code='OUTPUT_INVALID',diagnostic=str(exc));value['null_reason']='OUTPUT_INVALID'
    return value

def fasta(label,sequence):return ('>'+label+'\n'+sequence+'\n').encode()

def dispatch(rt,job_id):
    with rt._tx() as db:
        before=rt._job(db,job_id)
        if before['state']!='queued':return before
        ensure(before['execution_profile']==policy.registered_profile() and before['rule_profile']==policy.registered_rules(),
            'PROFILE_NOT_APPROVED','N16 implementation changed after submission')
        raw=rt._input(db,before['request_artifact'],before['run_id']);body=policy.request(raw)
        fault=rt._development_fault
        ensure(fault in (None,'compute_failure','corrupt_output','interrupt_after_claim','hold_worker'), 'INVALID_REQUEST','Unknown N16 internal fault')
        value=copy.deepcopy(before);value.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
            lease_epoch=1,started_at=now())
        path=rt.attempt_path(value);publish(rt.root,path+'/input.json',raw)
        within(rt.root,path+'/input').mkdir();within(rt.root,path+'/output').mkdir()
        ex=dict(phase='local_compute',dispatcher=wp.current_identity(),tree_stopped=False,backend='owned-local-python',
            supervisor=None,container_started=False,container_id=None,network_used=False,timeout_seconds=body['timeout_seconds'],fault=fault,
            source_receipts=None,worker_started=False,job_object='Local\\'+value['execution_identity'])
        rt._execution_store(db,job_id,ex);rt._store(db,value,before,'claimed')
    if fault=='interrupt_after_claim':
        ex.update(phase='interrupted_fixture')
        with rt._tx() as db:rt._execution_store(db,job_id,ex)
        return rt.get(job_id)
    files={'input.json':raw};error=None;diagnostic=None;receipts=None;process=None;owned=None;started=time.perf_counter()
    try:
        upstream,receipts=policy.source_files(body)
        upstream['input/source-receipts.json']=encode(receipts)
        upstream['input/execution-binding.json']=encode({k:value[k] for k in ('job_id','attempt_id','execution_identity')})
        for name,data in upstream.items():publish(rt.root,path+'/'+name,data);files[name]=data
        ex['source_receipts']=receipts
        if body['expression_host'] is not None:
            if fault=='compute_failure':raise RuntimeFault('TOOL_FAILED','Controlled N16 worker failure')
            owned=wp.Job(ex['job_object'])
            limits=wp.Extended();limits.basic.flags=0x2000|0x0008|0x0200;limits.basic.active_limit=4;limits.job_memory=1024**3
            wp.ok(wp.SetJob(owned.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)))
            argv=[sys.executable,'-X','utf8',str(policy.HERE/'worker.py'),str(within(rt.root,path))]
            if fault=='hold_worker':argv=[sys.executable,'-c','import time; time.sleep(120)']
            process=wp.Process(argv,policy.HERE,owned);ex.update(worker_started=True,worker=process.identity,limits=owned.limits())
            with rt._tx() as db:rt._execution_store(db,job_id,ex)
            process.resume()
            while process.poll() is None:
                current=rt.get(job_id)
                if current['stop_reason'] or time.perf_counter()-started>body['timeout_seconds']:
                    if not current['stop_reason']:
                        with rt._tx() as db:rt._stop(db,rt._job(db,job_id),'timeout')
                    owned.stop()
                    break
                time.sleep(.05)
            while owned.active():time.sleep(.01)
            ensure(not rt.get(job_id)['stop_reason'],'STOPPED','N16 worker stopped on request/deadline')
            ensure(process.poll()==0,'TOOL_FAILED','N16 worker exited with a failure; see raw diagnostic')
            data=read_locked(within(rt.root,path+'/output/observation.json'),2*1024**2)
            files['output/observation.json']=b'{}' if fault=='corrupt_output' else data
            draft=decode(data)['result']
            for label,key in (('initial','initial_dna'),('optimized','optimized_dna')):
                if draft[key] is not None:
                    name='output/'+label+'.fasta';data=fasta('unoptimized' if label=='initial' else 'optimized-engineering',draft[key])
                    publish(rt.root,path+'/'+name,data);files[name]=data
            # Detect source/table/dependency mutation during optimization before publication.
            again,after=policy.source_files(body)
            ensure(again=={k:v for k,v in upstream.items() if k not in ('input/source-receipts.json','input/execution-binding.json')} and after==receipts,
                'HASH_MISMATCH','N16 source changed during optimization')
    except (RuntimeFault,OSError,ValueError,KeyError,TypeError) as exc:
        error=exc.code if isinstance(exc,RuntimeFault) else 'TOOL_FAILED';diagnostic=str(exc)
    finally:
        if owned:
            if owned.active():owned.stop()
            while owned.active():time.sleep(.01)
            owned.close()
        if process:process.close()
    elapsed=time.perf_counter()-started
    if elapsed>body['timeout_seconds'] and not rt.get(job_id)['stop_reason']:
        with rt._tx() as db:rt._stop(db,rt._job(db,job_id),'timeout')
    err=within(rt.root,path+'/output/error.txt')
    if err.is_file():files['stderr.txt']=read_locked(err,65536)
    actual=dict(job_id=job_id,attempt_id=value['attempt_id'],execution_identity=value['execution_identity'],exit_code=1 if error else 0,
        error_code=error,diagnostic=diagnostic,stopped_confirmed=True,backend='owned-local-python',container_id=None,
        network_used=False,elapsed_seconds=elapsed,recovered=False,source_receipts=receipts,worker_started=ex['worker_started'])
    built=result(rt.get(job_id),body,files,actual,fault);ex.update(tree_stopped=True,phase='collected',source_receipts=receipts)
    return rt._finish_development(job_id,ex,files,built)

def recover(rt,before):
    if before['state'] in ('queued','succeeded','failed','cancelled','timed_out'):return before
    ex=rt.execution(before['job_id'])
    if ex.get('phase')!='interrupted_fixture' and wp.alive(ex.get('dispatcher')) is True:return rt.get(before['job_id'])
    # KILL_ON_JOB_CLOSE owns the worker even across dispatcher death. Never infer
    # terminal state from the PID alone or rerun an interrupted optimization.
    active=wp.inspect_job(ex['job_object'],stop=True)
    if active!=0:return rt._unknown(before['job_id'],'Owned N16 process tree stop not yet confirmed')
    raw=rt._request_bytes(before);body=policy.request(raw)
    actual=dict(error_code='INTERRUPTED',diagnostic='Dispatcher lost; owned process tree confirmed stopped',
        stopped_confirmed=True,exit_code=None,recovered=True,source_receipts=ex.get('source_receipts'),worker_started=ex.get('worker_started'))
    files={'input.json':raw}
    for source in within(rt.root,rt.attempt_path(before)+'/input').glob('*'):
        if source.is_file():files['input/'+source.name]=read_locked(source,2*1024**2)
    ex.update(tree_stopped=True)
    return rt._finish_development(before['job_id'],ex,files,result(before,body,files,actual,ex.get('fault')))
