"""N09 local lifecycle and authenticated upstream/data collection."""
import copy
import time
from pathlib import Path
import Bio
from ...common import RuntimeFault, encode, decode, ensure, new_id, now, sha
from ...files import publish, within
from ...winprocess import current_identity
from . import policy
from .compute import compute
from .geometry import geometry

DEEP='t01.real.deeptmhmm'
STRUCTURE='t01.real.structure_analysis'


def sources(rt,db,body):
    from ..structure.policy import TOOL as structure_tool
    files={};values={};receipts={}
    for name,tool in (('topology',DEEP),('structure',structure_tool)):
        item=body[name+'_input'];state=item['state']
        if state=='not_provided':
            receipts[name]=dict(state=state,verified=True,artifact=None);continue
        job,raw,value=rt._registered_result_artifact(db,item['artifact'],tool)
        ensure(value['binding']['sequence_sha256']==sha(body['protein_sequence'].encode()),'OUTPUT_INVALID','N09 upstream sequence mismatch')
        if state=='available':
            ensure(job['state']=='succeeded' and item['artifact']['role']=='result','OUTPUT_INVALID','Available upstream must be a success result')
        else:
            ensure(item['artifact']['role']=='diagnostic' and job['state']!='succeeded' and item['reason_code']==job['error_code'],
                'OUTPUT_INVALID','Upstream diagnostic state mismatch')
        files['input/'+name+'-result.json']=raw
        values[name]=value if state=='available' else None
        receipts[name]=dict(state=state,verified=True,artifact=item['artifact'],coordinate_space='mature')
        if name=='structure' and state=='available' and value.get('analysis'):
            refs=[r['artifact'] for r in value['raw_artifacts'] if r['path']=='input.structure']
            ensure(len(refs)==1,'OUTPUT_INVALID','Structure input artifact missing')
            original=rt.artifact_bytes(job['job_id'],refs[0]['artifact_id'])
            ensure(sha(original)==value['binding']['structure_sha256'],'OUTPUT_INVALID','Structure bytes do not match source binding')
            files['input/structure-original.bin']=original
    return files,values,receipts


def evaluate(body,files):
    entries=decode(files['input/annotation-entries.json']);topology=None;geo=None
    if body['topology_input']['state']=='available':
        source=decode(files['input/topology-result.json']);topology=source.get('topology')
        if topology is not None:
            from ..raw_format import segments, LABELS
            record=source['raw_record'];expected=segments(record['labels'])
            ensure(record['sequence']==body['protein_sequence'] and len(record['labels'])==len(body['protein_sequence'])
                and topology['segments']==[{k:r[k] for k in ('type','start','end')} for r in expected]
                and topology['labels']==[LABELS[x] for x in record['labels']],'OUTPUT_INVALID','Bound topology segments/labels mismatch')
    if body['structure_input']['state']=='available':
        value=decode(files['input/structure-result.json'])
        geo=geometry(value['analysis'],files['input/structure-original.bin']) if value.get('analysis') else dict(
            status='review_required',reason='UPSTREAM_STRUCTURE_ANALYSIS_UNAVAILABLE',core_map=None,functional_domains=[])
    elif body['structure_input']['state']=='upstream_unavailable':
        geo=dict(status='upstream_unavailable',core_map=None,functional_domains=[])
    return compute(body,entries,topology,geo)


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()),
        database_id=body['database_id'],database_manifest_sha256=body['database_manifest_sha256'])
    value=dict(contract_version='0.1.0',tool_id=policy.TOOL,binding=binding,evidence_kind='G0_REAL_OUTPUT',
        qualification='DEVELOPMENT_UNREVIEWED',usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,
        production_status='NOT_DEPLOYED',requires_review=True,execution=execution,status='unreliable',analysis=None,
        null_reason=execution.get('error_code'),controlled_fault=fault,method_summary=dict(biopython=Bio.__version__,
            rule_profile=policy.registered_rules(),network=False,homology_annotation_transfer=False),warnings=[])
    if execution.get('error_code'):return value
    try:
        ensure(execution['stopped_confirmed'] is True and execution['exit_code']==0 and execution['network_used'] is False,
            'OUTPUT_INVALID','No clean local N09 execution')
        observation=decode(files['output/observation.json'])
        ensure(observation['input_hashes']=={k:sha(v) for k,v in files.items() if k.startswith('input/')},
            'OUTPUT_INVALID','N09 source observation hashes mismatch')
        computed=evaluate(body,files)
        ensure(observation['result']==computed,'OUTPUT_INVALID','N09 observation differs from verified source computation')
        value.update(status='domains_computed_unreviewed',analysis=computed,null_reason=None,
            database=execution['database_receipt'],source_receipts=execution['source_receipts'])
    except (RuntimeFault,KeyError,ValueError,TypeError) as exc:
        execution.update(error_code='OUTPUT_INVALID',diagnostic=str(exc));value.update(null_reason='OUTPUT_INVALID')
    return value


def dispatch(rt,job_id):
    with rt._tx() as db:
        before=rt._job(db,job_id)
        if before['state']!='queued':return before
        try:
            ensure(before['execution_profile']==policy.registered_profile() and before['rule_profile']==policy.registered_rules(),
                'PROFILE_NOT_APPROVED','N09 implementation changed after submission')
            raw=rt._input(db,before['request_artifact'],before['run_id']);body=policy.request(raw)
            upstream,_,receipts=sources(rt,db,body)
        except RuntimeFault as exc:
            value=copy.deepcopy(before);value.update(state='failed',finished_at=now(),error_code=exc.code,scientific_disposition='rejected')
            rt._store(db,value,before,'preflight_failed');return value
        fault=rt._development_fault
        ensure(fault in (None,'compute_failure','corrupt_output','interrupt_after_claim'),'INVALID_REQUEST','Unknown internal N09 fault')
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
    files={'input.json':raw,'input.fasta':fasta,**upstream};error=None;diagnostic=None;db_receipt=None
    started=time.perf_counter()
    try:
        db_receipt,local=policy.database(rt.domains_database_root,body)
        files.update(local)
        for name,data in local.items():publish(rt.root,path+'/'+name,data)
        if fault=='compute_failure':raise RuntimeFault('TOOL_FAILED','Controlled N09 compute failure')
        observation=encode(dict(input_hashes={k:sha(v) for k,v in files.items() if k.startswith('input/')},result=evaluate(body,files)))
        if fault=='corrupt_output':observation=b'{}'
        publish(rt.root,path+'/output/observation.json',observation);files['output/observation.json']=observation
        after,_=policy.database(rt.domains_database_root,body)
        ensure(after==db_receipt,'HASH_MISMATCH','Annotation package changed during N09 calculation')
        with rt._db() as db:
            _,_,after_sources=sources(rt,db,body)
        ensure(after_sources==receipts,'HASH_MISMATCH','N09 upstream changed during calculation')
    except (RuntimeFault,OSError,ValueError,KeyError,TypeError) as exc:
        error=exc.code if isinstance(exc,RuntimeFault) else 'TOOL_FAILED';diagnostic=str(exc)
    elapsed=time.perf_counter()-started
    if elapsed>body['timeout_seconds']:
        error='TIMEOUT';diagnostic='N09 local deadline exceeded'
        with rt._tx() as db:rt._stop(db,rt._job(db,job_id),'timeout')
    actual=dict(job_id=job_id,attempt_id=value['attempt_id'],execution_identity=value['execution_identity'],exit_code=1 if error else 0,
        error_code=error,diagnostic=diagnostic,stopped_confirmed=True,backend='trusted-local-in-process',container_id=None,
        network_used=False,elapsed_seconds=elapsed,recovered=False,database_receipt=db_receipt,source_receipts=receipts)
    built=result(rt.get(job_id),body,files,actual,fault);ex=rt.execution(job_id);ex.update(tree_stopped=True,phase='collected')
    return rt._finish_development(job_id,ex,files,built)
