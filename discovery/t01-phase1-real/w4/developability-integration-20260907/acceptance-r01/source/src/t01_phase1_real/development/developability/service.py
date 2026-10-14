"""N10 trusted-local partial lifecycle with authenticated structure provenance."""
import copy
import time

import Bio

from ...common import RuntimeFault, encode, decode, ensure, new_id, now, sha
from ...files import publish, within
from ...winprocess import current_identity
from . import policy
from .compute import compute


def sources(rt,db,body):
    from ..structure.policy import TOOL as structure_tool
    item=body['structure_input'];state=item['state']
    if state=='not_provided':return {},None,dict(state=state,verified=True,artifact=None)
    job,raw,value=rt._registered_result_artifact(db,item['artifact'],structure_tool)
    ensure(value['binding']['sequence_sha256']==sha(body['protein_sequence'].encode()),
        'OUTPUT_INVALID','N10 structure sequence mismatch')
    if state=='available':
        ensure(job['state']=='succeeded' and item['artifact']['role']=='result','OUTPUT_INVALID','Available structure must be a success result')
        source=value
    else:
        ensure(job['state']!='succeeded' and item['artifact']['role']=='diagnostic' and item['reason_code']==job['error_code'],
            'OUTPUT_INVALID','Structure diagnostic state/reason mismatch')
        source=None
    receipt=dict(state=state,verified=True,artifact=item['artifact'],upstream_state=job['state'],
        upstream_error=job['error_code'],coordinate_space='mature')
    return {'input/structure-result.json':raw},source,receipt


def evaluate(body,files):
    source=decode(files['input/structure-result.json']) if body['structure_input']['state']=='available' else None
    return compute(body,source)


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()))
    value=dict(contract_version='0.1.0',tool_id=policy.TOOL,binding=binding,evidence_kind='G0_REAL_OUTPUT',
        qualification='DEVELOPMENT_UNREVIEWED',usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,
        production_status='NOT_DEPLOYED',requires_review=True,execution=execution,status='unreliable',developability=None,
        steps=None,null_reason=execution.get('error_code'),controlled_fault=fault,method_summary=dict(biopython=Bio.__version__,
            rule_profile=policy.registered_rules(),network=False,scope='S-36a/S-39/S-40-partial'),warnings=[])
    if execution.get('error_code'):return value
    try:
        ensure(execution['stopped_confirmed'] is True and execution['exit_code']==0 and execution['network_used'] is False,
            'OUTPUT_INVALID','No clean local N10 partial execution')
        observation=decode(files['output/observation.json'])
        ensure(observation['input_hashes']=={k:sha(v) for k,v in files.items() if k.startswith('input/')},
            'OUTPUT_INVALID','N10 source observation hashes mismatch')
        computed=evaluate(body,files)
        ensure(observation['result']==computed,'OUTPUT_INVALID','N10 observation differs from verified recomputation')
        value.update(status='partial_developability_unreviewed',developability=computed['developability'],steps={k:computed[k]
            for k in ('expressibility','tag_exposure','completed_steps','pending_steps','n10_status')},null_reason=None,
            source_receipt=execution['source_receipt'],warnings=computed['tag_exposure']['warnings'])
    except (RuntimeFault,KeyError,ValueError,TypeError) as exc:
        execution.update(error_code='OUTPUT_INVALID',diagnostic=str(exc));value.update(null_reason='OUTPUT_INVALID')
    return value


def dispatch(rt,job_id):
    with rt._tx() as db:
        before=rt._job(db,job_id)
        if before['state']!='queued':return before
        try:
            ensure(before['execution_profile']==policy.registered_profile() and before['rule_profile']==policy.registered_rules(),
                'PROFILE_NOT_APPROVED','N10 implementation changed after submission')
            raw=rt._input(db,before['request_artifact'],before['run_id']);body=policy.request(raw)
            upstream,_,receipt=sources(rt,db,body)
        except RuntimeFault as exc:
            value=copy.deepcopy(before);value.update(state='failed',finished_at=now(),error_code=exc.code,scientific_disposition='rejected')
            rt._store(db,value,before,'preflight_failed');return value
        fault=rt._development_fault
        ensure(fault in (None,'compute_failure','corrupt_output','interrupt_after_claim'),'INVALID_REQUEST','Unknown internal N10 fault')
        value=copy.deepcopy(before);value.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
            lease_epoch=1,started_at=now())
        path=rt.attempt_path(value);fasta=('>'+policy.sequence_id(body['protein_sequence'])+'\n'+body['protein_sequence']+'\n').encode()
        publish(rt.root,path+'/input.json',raw);publish(rt.root,path+'/input.fasta',fasta)
        for name,data in upstream.items():publish(rt.root,path+'/'+name,data)
        within(rt.root,path+'/output').mkdir()
        ex=dict(phase='local_compute',dispatcher=current_identity(),supervisor=None,tree_stopped=False,backend='trusted-local-in-process',
            container_started=False,container_id=None,network_used=False,timeout_seconds=body['timeout_seconds'],fault=fault,
            source_receipt=receipt)
        rt._execution_store(db,job_id,ex);rt._store(db,value,before,'claimed')
    if fault=='interrupt_after_claim':
        with rt._tx() as db:
            ex=rt._execution(db,job_id);ex.update(phase='interrupted_fixture',tree_stopped=True);rt._execution_store(db,job_id,ex)
        return rt.get(job_id)
    files={'input.json':raw,'input.fasta':fasta,**upstream};error=None;diagnostic=None
    started=time.perf_counter()
    try:
        if fault=='compute_failure':raise RuntimeFault('TOOL_FAILED','Controlled N10 compute failure')
        observation=encode(dict(input_hashes={k:sha(v) for k,v in files.items() if k.startswith('input/')},result=evaluate(body,files)))
        if fault=='corrupt_output':observation=b'{}'
        publish(rt.root,path+'/output/observation.json',observation);files['output/observation.json']=observation
        with rt._db() as db:
            _,_,after=sources(rt,db,body)
        ensure(after==receipt,'HASH_MISMATCH','N10 structure source changed during calculation')
    except (RuntimeFault,OSError,ValueError,KeyError,TypeError) as exc:
        error=exc.code if isinstance(exc,RuntimeFault) else 'TOOL_FAILED';diagnostic=str(exc)
    elapsed=time.perf_counter()-started
    if elapsed>body['timeout_seconds']:
        error='TIMEOUT';diagnostic='N10 local deadline exceeded'
        with rt._tx() as db:rt._stop(db,rt._job(db,job_id),'timeout')
    actual=dict(job_id=job_id,attempt_id=value['attempt_id'],execution_identity=value['execution_identity'],exit_code=1 if error else 0,
        error_code=error,diagnostic=diagnostic,stopped_confirmed=True,backend='trusted-local-in-process',container_id=None,
        network_used=False,elapsed_seconds=elapsed,recovered=False,source_receipt=receipt)
    built=result(rt.get(job_id),body,files,actual,fault);ex=rt.execution(job_id);ex.update(tree_stopped=True,phase='collected')
    return rt._finish_development(job_id,ex,files,built)
