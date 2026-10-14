"""N10 trusted-local partial lifecycle with authenticated structure provenance."""
import copy
import subprocess
import sys
import time

import Bio

from ...common import RuntimeFault, encode, decode, ensure, new_id, now, sha
from ...files import publish, within
from ...winprocess import current_identity
from . import policy
from .compute import compute
from .propka import VERSION as PROPKA_VERSION, parameters as propka_parameters, project_preparation_pdb


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
    files={'input/structure-result.json':raw}
    receipt=dict(state=state,verified=True,artifact=item['artifact'],upstream_state=job['state'],
        upstream_error=job['error_code'],coordinate_space='mature')
    if source is not None and source.get('analysis'):
        refs=[row['artifact'] for row in source['raw_artifacts'] if row['path']=='input.structure']
        ensure(len(refs)==1,'OUTPUT_INVALID','N10 original structure artifact missing')
        original=rt.artifact_bytes(job['job_id'],refs[0]['artifact_id'])
        ensure(sha(original)==source['binding']['structure_sha256'],'OUTPUT_INVALID','N10 original structure bytes mismatch')
        media=source['analysis']['input']['structure_artifact']['media_type']
        files['input/structure-original.pdb' if media=='chemical/x-pdb' else 'input/structure-original.bin']=original
        receipt.update(original_structure_sha256=sha(original),original_structure_media_type=media)
        if media!='chemical/x-pdb':
            refs=[row['artifact'] for row in source['raw_artifacts'] if row['path']=='output/result/preparation.json']
            ensure(len(refs)<=1,'OUTPUT_INVALID','N10 duplicate structure preparations')
            if refs:
                prepared=rt.artifact_bytes(job['job_id'],refs[0]['artifact_id'])
                ensure(decode(prepared)['binding']==source['binding'],'OUTPUT_INVALID','N10 structure preparation binding mismatch')
                files['input/structure-preparation.json']=prepared;receipt['preparation_sha256']=sha(prepared)
            else:receipt['preparation_unavailable']='UPSTREAM_PREPARATION_NOT_EMITTED'
    return files,source,receipt


def evaluate(body,files):
    source=decode(files['input/structure-result.json']) if body['structure_input']['state']=='available' else None
    execution=decode(files['output/propka-execution.json'])
    return compute(body,source,files.get('output/propka.pka'),execution)


def run_propka(rt,path,body,source,files):
    execution=dict(status='not_run',reason_code=None,tool='PROPKA',version=PROPKA_VERSION,network_used=False,
        command=None,exit_code=None,stdout_sha256=None,stderr_sha256=None)
    if source is None:
        execution['reason_code']='STRUCTURE_NOT_AVAILABLE';return execution
    report=source.get('analysis')
    if not isinstance(report,dict):
        execution['reason_code']='STRUCTURE_ANALYSIS_NOT_AVAILABLE';return execution
    mapping=report.get('mapping')
    if not isinstance(mapping,dict) or not isinstance(mapping.get('target_chain_id'),str) or len(mapping['target_chain_id'])!=1:
        execution['reason_code']='STRUCTURE_MAPPING_NOT_UNIQUE';return execution
    params=propka_parameters(body['target_ph_range']);chain=mapping['target_chain_id']
    if 'input/structure-original.pdb' in files:
        propka_input=files['input/structure-original.pdb'];input_mode='unchanged_source_pdb'
    elif 'input/structure-preparation.json' in files:
        propka_input=project_preparation_pdb(decode(files['input/structure-preparation.json']),chain)
        input_mode='verified_n02_atom_ledger_pdb_projection'
    else:
        execution['reason_code']='STRUCTURE_FORMAT_NOT_SUPPORTED_FOR_PROPKA_DEVELOPMENT';return execution
    files['input/propka-structure.pdb']=propka_input
    publish(rt.root,path+'/input/propka-structure.pdb',propka_input)
    output_dir=within(rt.root,path+'/output/propka');output_dir.mkdir()
    input_path=within(rt.root,path+'/input/propka-structure.pdb')
    command=[sys.executable,'-m','propka',str(input_path),'-c',chain,'-w',str(params['start']),str(params['end']),
        str(params['step']),'-g',str(params['start']),str(params['end']),str(params['grid_step']),'-q']
    execution['command']=dict(module='propka',chain=chain,input_mode=input_mode,input_sha256=sha(propka_input),
        window=[params['start'],params['end'],params['step']],grid=[params['start'],params['end'],params['grid_step']],quiet=True)
    try:
        proc=subprocess.run(command,cwd=output_dir,capture_output=True,timeout=body['timeout_seconds'],
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except subprocess.TimeoutExpired as exc:
        stdout=exc.stdout or b'';stderr=exc.stderr or b''
        files['output/propka.stdout.txt']=stdout;files['output/propka.stderr.txt']=stderr
        execution.update(status='failed',reason_code='PROPKA_TIMEOUT',stdout_sha256=sha(stdout),stderr_sha256=sha(stderr))
        return execution
    stdout=proc.stdout;stderr=proc.stderr
    files['output/propka.stdout.txt']=stdout;files['output/propka.stderr.txt']=stderr
    execution.update(exit_code=proc.returncode,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr))
    output=output_dir/'propka-structure.pka'
    if proc.returncode!=0 or not output.is_file() or output.stat().st_size==0:
        execution.update(status='failed',reason_code='PROPKA_FAILED' if proc.returncode else 'PROPKA_OUTPUT_MISSING')
        return execution
    raw=output.read_bytes();ensure(len(raw)<=32*1024**2,'OUTPUT_INVALID','PROPKA output exceeds limit')
    files['output/propka.pka']=raw
    execution.update(status='executed',reason_code=None,output_sha256=sha(raw),output_size_bytes=len(raw))
    return execution


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()))
    value=dict(contract_version='0.1.0',tool_id=policy.TOOL,binding=binding,evidence_kind='G0_REAL_OUTPUT',
        qualification='DEVELOPMENT_UNREVIEWED',usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,
        production_status='NOT_DEPLOYED',requires_review=True,execution=execution,status='unreliable',developability=None,
        steps=None,null_reason=execution.get('error_code'),controlled_fault=fault,method_summary=dict(biopython=Bio.__version__,
            propka=PROPKA_VERSION,rule_profile=policy.registered_rules(),network=False,
            scope='S-36a/S-38-development/S-39/S-40-partial'),warnings=[])
    if execution.get('error_code'):return value
    try:
        ensure(execution['stopped_confirmed'] is True and execution['exit_code']==0 and execution['network_used'] is False,
            'OUTPUT_INVALID','No clean local N10 partial execution')
        observation=decode(files['output/observation.json'])
        ensure(observation['input_hashes']=={k:sha(v) for k,v in files.items() if k.startswith('input/')},
            'OUTPUT_INVALID','N10 source observation hashes mismatch')
        ensure(observation['tool_output_hashes']=={k:sha(v) for k,v in files.items() if k.startswith('output/propka')},
            'OUTPUT_INVALID','N10 PROPKA output hashes mismatch')
        computed=evaluate(body,files)
        ensure(observation['result']==computed,'OUTPUT_INVALID','N10 observation differs from verified recomputation')
        value.update(status='partial_developability_unreviewed',developability=computed['developability'],steps={k:computed[k]
            for k in ('expressibility','tag_exposure','ph_stability','completed_steps','pending_steps','n10_status')},null_reason=None,
            source_receipt=execution['source_receipt'],warnings=list(dict.fromkeys(
                computed['tag_exposure']['warnings']+computed['ph_stability']['warnings'])))
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
            upstream,source,receipt=sources(rt,db,body)
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
        ex=dict(phase='local_compute',dispatcher=current_identity(),supervisor=None,tree_stopped=False,backend='trusted-local-hybrid',
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
        propka_execution=run_propka(rt,path,body,source,files)
        encoded_execution=encode(propka_execution);publish(rt.root,path+'/output/propka-execution.json',encoded_execution)
        files['output/propka-execution.json']=encoded_execution
        for name,data in files.items():
            if name.startswith('output/propka') and name!='output/propka-execution.json':publish(rt.root,path+'/'+name,data)
        observation=encode(dict(input_hashes={k:sha(v) for k,v in files.items() if k.startswith('input/')},
            tool_output_hashes={k:sha(v) for k,v in files.items() if k.startswith('output/propka')},result=evaluate(body,files)))
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
        error_code=error,diagnostic=diagnostic,stopped_confirmed=True,backend='trusted-local-hybrid',container_id=None,
        network_used=False,elapsed_seconds=elapsed,recovered=False,source_receipt=receipt)
    built=result(rt.get(job_id),body,files,actual,fault);ex=rt.execution(job_id);ex.update(tree_stopped=True,phase='collected')
    return rt._finish_development(job_id,ex,files,built)
