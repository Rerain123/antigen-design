"""Bounded local audit lifecycle using the existing task store and cancellation fence."""
import copy
import time
from ...common import RuntimeFault,encode,decode,ensure,new_id,now,sha
from ...files import publish,within
from ...winprocess import current_identity
from . import policy
from .source import sources
from .compute import evaluate

def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()))
    value=dict(contract_version='0.1.0',tool_id=policy.TOOL,binding=binding,evidence_kind='G0_REAL_OUTPUT',
        qualification='DEVELOPMENT_UNREVIEWED',usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,
        production_status='NOT_DEPLOYED',requires_review=True,execution=execution,status='unreliable',report=None,scientific_gate='NOT_EVALUATED',
        source_receipts=execution.get('source_receipts'),null_reason=execution.get('error_code'),controlled_fault=fault,
        method_summary=dict(rule_profile=job['rule_profile'],network=False,
            scope='N14/N15 per-variant engineering report only'),warnings=[])
    if execution.get('error_code'):return value
    try:
        ensure(execution['stopped_confirmed'] is True and execution['exit_code']==0 and execution['network_used'] is False,
            'OUTPUT_INVALID','No clean local Variant report execution')
        observation=decode(files['output/observation.json'])
        ensure(observation['input_hashes']=={k:sha(v) for k,v in files.items() if k.startswith('input/')},
            'OUTPUT_INVALID','WT observation source hashes differ')
        computed=evaluate(body,files)
        ensure(observation['result']==computed and files['output/variant-report.json']==encode(computed)
            and decode(files['input/source-receipts.json'])==execution['source_receipts'],
            'OUTPUT_INVALID','Variant report differs from verified source facts')
        value.update(status='variant_report_unreviewed',report=computed,null_reason=None,
            warnings=[dict(code=r['code'],level='quality',severity='WARNING',message=r['code']) for r in computed['review_reasons']])
    except (RuntimeFault,KeyError,ValueError,TypeError) as exc:
        execution.update(error_code='OUTPUT_INVALID',diagnostic=str(exc));value.update(null_reason='OUTPUT_INVALID')
    return value


def dispatch(rt,job_id):
    with rt._tx() as db:
        before=rt._job(db,job_id)
        if before['state']!='queued':return before
        try:
            ensure(before['execution_profile']==policy.registered_profile() and before['rule_profile']==policy.registered_rules(),
                'PROFILE_NOT_APPROVED','Variant report implementation changed after submission')
            raw=rt._input(db,before['request_artifact'],before['run_id']);body=policy.request(raw)
            upstream,_,receipts=sources(rt,db,body)
        except RuntimeFault as exc:
            value=copy.deepcopy(before);value.update(state='failed',finished_at=now(),error_code=exc.code,scientific_disposition='rejected')
            rt._store(db,value,before,'preflight_failed');return value
        fault=rt._development_fault
        ensure(fault in (None,'compute_failure','corrupt_output','interrupt_after_claim'),'INVALID_REQUEST','Unknown internal WT fault')
        value=copy.deepcopy(before);value.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
            lease_epoch=1,started_at=now())
        path=rt.attempt_path(value);fasta=('>'+policy.sequence_id(body['protein_sequence'])+'\n'+body['protein_sequence']+'\n').encode()
        publish(rt.root,path+'/input.json',raw);publish(rt.root,path+'/input.fasta',fasta)
        for name,data in upstream.items():publish(rt.root,path+'/'+name,data)
        within(rt.root,path+'/output').mkdir()
        ex=dict(phase='local_compute',dispatcher=current_identity(),supervisor=None,tree_stopped=False,backend='trusted-local-in-process',
            container_started=False,container_id=None,network_used=False,timeout_seconds=body['timeout_seconds'],fault=fault,
            source_receipts=receipts)
        rt._execution_store(db,job_id,ex);rt._store(db,value,before,'claimed')
    if fault=='interrupt_after_claim':
        with rt._tx() as db:
            ex=rt._execution(db,job_id);ex.update(phase='interrupted_fixture',tree_stopped=True);rt._execution_store(db,job_id,ex)
        return rt.get(job_id)
    files={'input.json':raw,'input.fasta':fasta,**upstream};error=None;diagnostic=None
    started=time.perf_counter()
    try:
        if fault=='compute_failure':raise RuntimeFault('TOOL_FAILED','Controlled Variant report calculation failure')
        draft=evaluate(body,files)
        observation=encode(dict(input_hashes={k:sha(v) for k,v in files.items() if k.startswith('input/')},result=draft))
        if fault=='corrupt_output':observation=b'{}'
        for name,data in (('output/observation.json',observation),('output/variant-report.json',encode(draft))):
            publish(rt.root,path+'/'+name,data);files[name]=data
        with rt._db() as db:_,_,after=sources(rt,db,body)
        ensure(after==receipts,'HASH_MISMATCH','Report upstream changed during assembly')
    except (RuntimeFault,OSError,ValueError,KeyError,TypeError) as exc:
        error=exc.code if isinstance(exc,RuntimeFault) else 'TOOL_FAILED';diagnostic=str(exc)
    elapsed=time.perf_counter()-started
    if elapsed>body['timeout_seconds']:
        error='TIMEOUT';diagnostic='Variant report deadline exceeded'
        with rt._tx() as db:
            current=rt._job(db,job_id)
            if current['stop_reason'] is None:rt._stop(db,current,'timeout')
    actual=dict(job_id=job_id,attempt_id=value['attempt_id'],execution_identity=value['execution_identity'],exit_code=1 if error else 0,
        error_code=error,diagnostic=diagnostic,stopped_confirmed=True,backend='trusted-local-in-process',container_id=None,
        network_used=False,elapsed_seconds=elapsed,recovered=False,source_receipts=receipts)
    built=result(rt.get(job_id),body,files,actual,fault);ex=rt.execution(job_id);ex.update(tree_stopped=True,phase='collected')
    return rt._finish_development(job_id,ex,files,built)
