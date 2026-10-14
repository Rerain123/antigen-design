"""Same-scope provenance verification and local WT draft task lifecycle."""
import copy
import time

from ...common import RuntimeFault, TERMINAL, encode, decode, ensure, new_id, now, sha
from ...files import publish, within, read_verified
from ...winprocess import current_identity
from . import policy
from .compute import assemble


def task_source(rt,name,job_id):
    ensure(name in policy.PRODUCERS,'INVALID_REQUEST','Unknown WT upstream slot')
    job=rt.get(job_id)
    ensure(job['tool_id']==policy.PRODUCERS[name],'FORBIDDEN','WT upstream producer differs')
    refs=[r for r in job['artifacts'] if r['role'] in ('result','diagnostic')]
    ensure(len(refs)<=1,'OUTPUT_INVALID','Ambiguous terminal result')
    return dict(job_id=job_id,artifact=refs[0] if refs else None)


def sources(rt,db,body):
    files={};values={};receipts={}
    for name,tool in policy.PRODUCERS.items():
        source=body['upstream'][name]
        if source is None:
            receipts[name]=dict(state='missing',verified=False,artifact=None,attempt_id=None)
            continue
        job=rt._job(db,source['job_id'])
        ensure(job['tool_id']==tool and job['run_mode']=='g0_probe' and job['usable_for_pipeline'] is False
            and job['evidence_kind']=='G0_REAL_OUTPUT','FORBIDDEN','WT source tool/scope/qualification differs')
        request_raw=rt._input(db,job['request_artifact'],job['run_id']);up_request=decode(request_raw)
        ensure(isinstance(up_request,dict) and up_request.get('protein_sequence')==body['protein_sequence'],
            'OUTPUT_INVALID','WT upstream request sequence differs')
        if up_request.get('host_species') is not None and body['host_species'] is not None:
            ensure(up_request['host_species']==body['host_species'],'OUTPUT_INVALID','WT upstream host fact differs')
        files['input/'+name+'-request.json']=request_raw
        refs=[r for r in job['artifacts'] if r['role'] in ('result','diagnostic')]
        ensure(len(refs)<=1 and source['artifact']==(refs[0] if refs else None),
            'FORBIDDEN','WT source must name the exact published result or diagnostic')
        value=None;verified_artifacts=[]
        if refs:
            _,raw,value=rt._registered_result_artifact(db,refs[0],tool)
            binding=value['binding']
            ensure(all(binding.get(k)==job[k] for k in ('request_id','execution_identity','execution_profile'))
                and binding.get('input_sha256')==sha(request_raw)
                and binding.get('sequence_sha256')==sha(body['protein_sequence'].encode()),
                'OUTPUT_INVALID','WT upstream binding/request/profile differs')
            ensure(value.get('qualification')=='DEVELOPMENT_UNREVIEWED' and value.get('scientific_signoff') is None
                and value.get('evidence_kind')=='G0_REAL_OUTPUT' and value.get('production_status')=='NOT_DEPLOYED',
                'OUTPUT_INVALID','WT upstream scientific qualification is not registered')
            ensure(refs[0]['role']==('result' if job['state']=='succeeded' else 'diagnostic')
                and value.get('execution',{}).get('error_code')==job['error_code'],
                'OUTPUT_INVALID','WT upstream failure state differs')
            # Verify published raw evidence too; a valid result hash cannot hide damaged tool files.
            raw_refs=value.get('raw_artifacts')
            ensure(isinstance(raw_refs,list),'OUTPUT_INVALID','Upstream raw artifact manifest missing')
            for item in raw_refs:
                ensure(isinstance(item,dict) and isinstance(item.get('artifact'),dict)
                    and item['artifact'] in job['artifacts'] and item['artifact']['role'] in ('raw','log'),
                    'OUTPUT_INVALID','WT raw provenance references a foreign artifact')
            for ref in job['artifacts']:
                row=db.execute('SELECT relative_path,data FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
                ensure(row and decode(row['data'])==ref,'FORBIDDEN','WT upstream publication registry differs')
                read_verified(rt.root,row['relative_path'],ref['sha256'],ref['size_bytes'],32*1024**2)
                verified_artifacts.append(ref)
            files['input/'+name+'-result.json']=raw
        ensure(job['state']!='succeeded' or value is not None,'OUTPUT_INVALID','Successful upstream has no result')
        state='available' if job['state']=='succeeded' else 'failed' if job['state'] in TERMINAL else 'pending'
        if state=='available':values[name]=value
        receipts[name]=dict(state=state,verified=True,artifact=source['artifact'],job_id=job['job_id'],
            run_id=job['run_id'],attempt_id=job['attempt_id'],job_state=job['state'],revision=job['revision'],
            error_code=job['error_code'],request_artifact=job['request_artifact'],
            sequence_sha256=sha(body['protein_sequence'].encode()),qualification=job['scientific_disposition'],
            result_status=value.get('status') if value else None,execution_profile=job['execution_profile'],
            rule_profile=job['rule_profile'],verified_artifacts=verified_artifacts)
    files['input/source-receipts.json']=encode(receipts)
    return files,values,receipts


def evaluate(body,files):
    receipts=decode(files['input/source-receipts.json'])
    values={name:decode(files['input/'+name+'-result.json']) for name in policy.PRODUCERS
        if receipts[name]['state']=='available'}
    return assemble(body,values,receipts)


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()))
    value=dict(contract_version='0.1.0',tool_id=policy.TOOL,binding=binding,evidence_kind='G0_REAL_OUTPUT',
        qualification='DEVELOPMENT_UNREVIEWED',usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,
        production_status='NOT_DEPLOYED',requires_review=True,execution=execution,status='unreliable',draft=None,
        source_receipts=execution.get('source_receipts'),null_reason=execution.get('error_code'),controlled_fault=fault,
        method_summary=dict(rule_profile=job['rule_profile'],network=False,
            scope='W4 local Gate review / WT draft; S-42 fields, S-44 closed'),warnings=[])
    if execution.get('error_code'):return value
    try:
        ensure(execution['stopped_confirmed'] is True and execution['exit_code']==0 and execution['network_used'] is False,
            'OUTPUT_INVALID','No clean local WT draft execution')
        observation=decode(files['output/observation.json'])
        ensure(observation['input_hashes']=={k:sha(v) for k,v in files.items() if k.startswith('input/')},
            'OUTPUT_INVALID','WT observation source hashes differ')
        computed=evaluate(body,files)
        ensure(observation['result']==computed and files['output/wt-draft.json']==encode(computed)
            and decode(files['input/source-receipts.json'])==execution['source_receipts'],
            'OUTPUT_INVALID','WT draft differs from verified source facts')
        value.update(status='local_wt_draft_review_required',draft=computed,null_reason=None,
            warnings=[dict(code=r['code'],level='quality',severity='WARNING',message=r['code']) for r in computed['gate']['reasons']])
    except (RuntimeFault,KeyError,ValueError,TypeError) as exc:
        execution.update(error_code='OUTPUT_INVALID',diagnostic=str(exc));value.update(null_reason='OUTPUT_INVALID')
    return value


def dispatch(rt,job_id):
    with rt._tx() as db:
        before=rt._job(db,job_id)
        if before['state']!='queued':return before
        try:
            ensure(before['execution_profile']==policy.registered_profile() and before['rule_profile']==policy.registered_rules(),
                'PROFILE_NOT_APPROVED','WT draft implementation changed after submission')
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
        if fault=='compute_failure':raise RuntimeFault('TOOL_FAILED','Controlled WT draft calculation failure')
        draft=evaluate(body,files)
        observation=encode(dict(input_hashes={k:sha(v) for k,v in files.items() if k.startswith('input/')},result=draft))
        if fault=='corrupt_output':observation=b'{}'
        for name,data in (('output/observation.json',observation),('output/wt-draft.json',encode(draft))):
            publish(rt.root,path+'/'+name,data);files[name]=data
        with rt._db() as db:_,_,after=sources(rt,db,body)
        ensure(after==receipts,'HASH_MISMATCH','WT upstream changed during assembly')
    except (RuntimeFault,OSError,ValueError,KeyError,TypeError) as exc:
        error=exc.code if isinstance(exc,RuntimeFault) else 'TOOL_FAILED';diagnostic=str(exc)
    elapsed=time.perf_counter()-started
    if elapsed>body['timeout_seconds']:
        error='TIMEOUT';diagnostic='WT local draft deadline exceeded'
        with rt._tx() as db:
            current=rt._job(db,job_id)
            if current['stop_reason'] is None:rt._stop(db,current,'timeout')
    actual=dict(job_id=job_id,attempt_id=value['attempt_id'],execution_identity=value['execution_identity'],exit_code=1 if error else 0,
        error_code=error,diagnostic=diagnostic,stopped_confirmed=True,backend='trusted-local-in-process',container_id=None,
        network_used=False,elapsed_seconds=elapsed,recovered=False,source_receipts=receipts)
    built=result(rt.get(job_id),body,files,actual,fault);ex=rt.execution(job_id);ex.update(tree_stopped=True,phase='collected')
    return rt._finish_development(job_id,ex,files,built)
