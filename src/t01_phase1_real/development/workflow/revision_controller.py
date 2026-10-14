"""Opt-in core workflow over existing registered native workers and transactions.

v1 and expert v2 retain separate policies and frozen identities. Missing
evidence blocks its consumer and never confers scientific release.
"""
import copy
from datetime import datetime
from ...common import TERMINAL, decode, encode, ensure, sha
from . import revision_contract as contract, revision_sampling as sampling, revision_budget as budget
from .revision_evaluation import foldx_pool, evidence_group, acceptance, task_acceptance

from .revision_runtime import CHILDREN as RUNTIME_CHILDREN

CHILDREN={**RUNTIME_CHILDREN,**{f'proposal{i}':'proteinmpnn' for i in range(2)},
          **{f'formal{i}':'proteinmpnn' for i in range(3)},
          **{f'cheap{i}':'esm_if1' for i in range(3)}}
STAGE='revision_design'


def enabled(body):return 'revision_config' in body


def _store(rt,jid,value):
    with rt._tx() as db:
        job=rt._job(db,jid)
        if job['state'] in TERMINAL or job['stop_reason']:return
        ex=rt._execution(db,jid);ex['revision_state']=value;rt._execution_store(db,jid,ex)


def inputs(rt,jid,body):
    from .service import verified,source
    from .engineering import effective
    job=rt.get(jid);rows=rt.execution(jid)['nodes']
    resolved,reason=effective(rt,body,rows)
    if reason:return None,reason
    for name in ('design_inputs','structure'):
        verified(rt,body,name,rows[name]['job_id'],job['run_id'],rows)
    # Replay permissions/mapping from actual upstream bytes, not a copied fact.
    from ..design_backend.source import sources
    from ..design_backend.compute import evaluate
    audit_job=rt.get(rows['design_inputs']['job_id']);req=decode(rt._request_bytes(audit_job))
    for ref in req['upstream'].values():
        if ref:ensure(rt.get(ref['job_id'])['run_id']==job['run_id'],'FORBIDDEN','Revision source belongs to another run')
    with rt._db() as db:files,_,_=sources(rt,db,req)
    audit=evaluate(req,files)
    ensure(audit==rt.result(audit_job['job_id'])['audit'],'OUTPUT_INVALID','Revision permission audit differs')
    conversion=audit['mask_conversion']['native/conversion.json']
    structure=rt.result(rows['structure']['job_id'])['analysis']
    low=structure.get('low_confidence_regions')
    if low is None:low=(structure.get('quality',{}).get('quality') or {}).get('low_confidence_regions')
    low_positions={p for r in low or [] for p in range(r['start'],r['end']+1)}
    snap=sampling.snapshot(body['protein_sequence'],audit['permissions'],conversion,source(rt,rows['structure'])['artifact'],
                           body['revision_config'],low_positions)
    snap['local_confidence_availability']='AVAILABLE' if low is not None else 'UNKNOWN'
    # The snapshot ID covers the complete frozen input, including availability.
    snap['permission_snapshot_id']='permission-'+sha(encode({k:v for k,v in snap.items() if k!='permission_snapshot_id'}))
    return dict(snapshot=snap,options=resolved['m1_test'],audit=audit,scales=decode(files['input/scales.json'])),None


def generation(rt,body,rows,name,run_id):
    from .service import verified,source
    from ..esm_if1.source import registered
    from ..proteinmpnn.result import parse
    from ..proteinmpnn.source import sources
    job=verified(rt,body,name,rows[name]['job_id'],run_id,rows)
    if job['state']!='succeeded':return None
    ref=source(rt,rows[name])['artifact']
    with rt._db() as db:
        _,_,value,request,native=registered(rt,db,ref,'t01.real.proteinmpnn')
        prepared,_=sources(rt,db,request,expected_run_id=run_id)
    ensure(all(native[k]==v for k,v in prepared.items()),'HASH_MISMATCH','Revision generation input changed')
    generated=parse(request,native)
    ensure(generated==value['generation'],'OUTPUT_INVALID','Revision generation differs from native output')
    return generated,ref,job


def _native_request(body,data,stage,index,opened):
    cfg=body['revision_config'];n=cfg['presampling_n']//2 if stage=='proposal_only' else cfg['formal_round_sizes'][index]
    opts=data['options'];snap=data['snapshot']
    return dict(protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
        structure_artifact=snap['wt_structure_id'],constraints=sampling.constraints(snap,opened),n_designs=n,
        sampling_temperature=.1 if stage=='proposal_only' else (.1,.3,.5)[index],
        seed=cfg['random_seeds'][index] if stage=='proposal_only' else cfg['random_seeds'][0],
        timeout_seconds=opts['timeout_seconds'],
        **({'t4_empty_fixed_confirmation':opts['t4_empty_fixed_confirmation']} if 't4_empty_fixed_confirmation' in opts else {}),
        revision_context=dict(shared_contract_version=contract.VERSION,stage=stage,
            calculation_config_id=cfg['calculation_config_id'],rule_version=cfg['rule_version'],
            permission_snapshot_id=snap['permission_snapshot_id'],reference_id=snap['reference_id'],
            sampling_constraints_sha256=sha(encode(sampling.constraints(snap,opened)))))


def reserve_child(ex,body,name,req):
    if not enabled(body) or name not in CHILDREN:return True
    if name in RUNTIME_CHILDREN:
        from .revision_runtime import reservation
        return reservation(ex,body,name,req)
    cfg=body['revision_config'];ledger=ex.setdefault('revision_ledger',budget.new(cfg))
    stage='proposal' if name.startswith('proposal') else 'formal' if name.startswith('formal') else 'esm_if1'
    objects=[] if stage!='esm_if1' else [str(n)+':'+req['n11_artifact']['sha256'] for n in req['sample_numbers']]
    return budget.reserve(ledger,cfg,name,stage,objects,requested=req.get('n_designs',0))


def account(rt,jid,name):
    rows=rt.execution(jid)['nodes'];row=rows.get(name,{})
    if not row.get('job_id'):return
    job=rt.get(row['job_id'])
    if not job.get('attempt_id'):return
    def difference(a,b):
        return max(0.,(datetime.fromisoformat(a.replace('Z','+00:00'))-datetime.fromisoformat(b.replace('Z','+00:00'))).total_seconds()) if a and b else None
    objects=None;internal_runs=None
    if job['state']=='succeeded':
        value=rt.result(job['job_id'])
        if name.startswith(('proposal','formal')):
            body=decode(rt._request_bytes(rt.get(jid)))
            generated,_,_=generation(rt,body,rows,name,job['run_id'])
            objects=[sha(r['sequence'].encode()) for r in generated['records']]
            internal_runs=len(objects) if generated['engine_runtime'].get('tool_invoked') else 0
        elif name in RUNTIME_CHILDREN:
            # Preserve known native sample/repeat counts; missing counts stay unknown.
            if RUNTIME_CHILDREN[name]=='foldx':
                native=value.get('variant_ddg')
                internal_runs=sum(len(v['native_ddg_runs']) for v in native) if isinstance(native,list) else None
            elif RUNTIME_CHILDREN[name]=='af3':
                models=(value.get('prediction') or {}).get('models')
                internal_runs=len(models) if isinstance(models,list) else None
        else:
            item=next(r for r in value['raw_artifacts'] if r['path']=='output/runtime.json')
            runtime=decode(rt.artifact_bytes(job['job_id'],item['artifact']['artifact_id']))
            internal_runs=runtime['baseline_model_calls']+runtime['variant_model_calls']
    attempt=dict(attempt_id=job['attempt_id'],job_id=job['job_id'],execution_status='SUCCEEDED' if job['state']=='succeeded' else
        'ERROR' if job['state'] in TERMINAL else 'RUNNING',
        queue_seconds=difference(job.get('started_at'),job.get('created_at')),
        execution_seconds=difference(job.get('finished_at') or job.get('ended_at'),job.get('started_at')),
        internal_runs=internal_runs,cache_hit=False)
    with rt._tx() as db:
        ex=rt._execution(db,jid);budget.observe(ex['revision_ledger'],name,attempt)
        if objects is not None:budget.observe_objects(ex['revision_ledger'],name,objects)
        rt._execution_store(db,jid,ex)


def child(rt,jid,body,name,req):
    from .service import _create_child,_record,verified
    job=rt.get(jid)
    if job['stop_reason'] or job['state'] in TERMINAL:return False
    rows=rt.execution(jid)['nodes'];row=rows.get(name,{})
    if row.get('reason_code')=='SKIPPED_BUDGET':return True
    child_id=row.get('job_id')
    if not child_id:
        child_id=_create_child(rt,jid,name,req)
        if not child_id:return rt.execution(jid)['nodes'].get(name,{}).get('reason_code')=='SKIPPED_BUDGET'
    state=verified(rt,body,name,child_id,job['run_id'],rt.execution(jid)['nodes'])
    if state['state'] not in TERMINAL:
        if state['state']=='queued':rt.dispatch(child_id)
        else:rt.recover(child_id)
        state=rt.get(child_id)
    # A separate reconciler may have completed the job before this poll. Always
    # synchronize its verified state before assembly, including that path.
    row=rt.execution(jid)['nodes'][name]
    if (row.get('state'),row.get('reason_code'))!=(state['state'],state['error_code']):
        _record(rt,jid,name,dict(row,state=state['state'],reason_code=state['error_code']))
    account(rt,jid,name)
    if state['state'] not in TERMINAL:return False
    ensure(state['state']=='succeeded' or state['error_code'] in ('TOOL_FAILED','TIMEOUT','ASSET_MISSING'),
           state['error_code'] or 'OUTPUT_INVALID','Revision child integrity failure')
    return True


def terminal_children(rt,jid):
    """Never finalize a revision while registered child results can be omitted."""
    rows=rt.execution(jid)['nodes']
    for name,row in rows.items():
        if name not in CHILDREN or not row.get('job_id'):continue
        job=rt.get(row['job_id'])
        ensure(job['state'] in TERMINAL and row.get('state')==job['state']
               and row.get('reason_code')==job['error_code'],
               'OUTPUT_INVALID',f'Revision child state not synchronized: {name}')


def assemble(rt,jid,body,data,*,sampling_only=False):
    from .service import source
    from . import revision_v2
    cfg=body['revision_config'];snap=data['snapshot'];rows=rt.execution(jid)['nodes'];run_id=rt.get(jid)['run_id']
    receipts=[];failures=[]
    for i in range(2):
        name=f'proposal{i}';row=rows.get(name,{})
        if row.get('state')!='succeeded':
            if row.get('state') in TERMINAL:failures.append(name)
            continue
        generated,ref,job=generation(rt,body,rows,name,run_id)
        expected=_native_request(body,data,'proposal_only',i,snap['eligible_positions'])
        actual=decode(rt._request_bytes(job));expected['timeout_seconds']=actual['timeout_seconds']
        ensure(actual==expected,'OUTPUT_INVALID','Proposal request context differs')
        batch=job['execution_identity']
        for record in generated['records']:
            receipts.append(dict(receipt_id=f'{job["job_id"]}:{record["sample_number"]}',draw_id=f'{batch}:{record["sample_number"]}',
                batch_id=batch,seed=cfg['random_seeds'][i],execution_ref=ref,condition_hash=sha(encode(snap)),
                source_kind='sampling_draw',delivery_kind='ORIGINAL',sequence=record['sequence']))
        if generated.get('native_wt'):
            receipts.append(dict(receipt_id=job['job_id']+':reference',draw_id=None,batch_id=batch,
                source_kind='reference_record',delivery_kind='ORIGINAL',sequence=generated['native_wt']['sequence']))
    proposal=sampling.proposals(snap,receipts,cfg);formal=[];rounds=[]
    for i in range(3):
        name=f'formal{i}';row=rows.get(name,{})
        if row.get('state')!='succeeded':continue
        generated,ref,job=generation(rt,body,rows,name,run_id)
        expected=_native_request(body,data,'formal',i,proposal['nomination_positions'])
        actual=decode(rt._request_bytes(job));expected['timeout_seconds']=actual['timeout_seconds']
        ensure(actual==expected,'OUTPUT_INVALID','Formal request context differs')
        records=sampling.formal(snap,generated['records'],proposal['nomination_positions'],cfg,formal,
                                dict(scales=data['scales'],generation_ref=ref))
        cheap=rows.get(f'cheap{i}',{});scored={}
        if cheap.get('state')=='succeeded':
            from ..esm_if1.source import registered,sources
            from ..esm_if1.result import validate_observation
            with rt._db() as db:
                _,_,value,request,files=registered(rt,db,source(rt,cheap)['artifact'],'t01.real.esm_if1')
                prepared,_=sources(rt,db,request,expected_run_id=run_id)
            ensure(all(files[k]==v for k,v in prepared.items()),'HASH_MISMATCH','ESM input changed')
            expected_numbers=[r['sample_number'] for r in records if r['disposition']=='FORMAL_POOL']
            ensure(request['sample_numbers']==expected_numbers and request['n11_artifact']==ref,
                   'OUTPUT_INVALID','Cheap scoring source or pool differs')
            ensure(request.get('shared_contract_version')==value.get('shared_contract_version')==contract.VERSION
                   and request.get('calculation_config_id')==value.get('calculation_config_id')==cfg['calculation_config_id'],
                   'OUTPUT_INVALID','CONTRACT: contract_incompatible C18 response')
            observation=validate_observation(request,files)
            # The native numeric records are authoritative; legacy automatic
            # relaxed passed values are explicitly not imported into S-28.
            ensure(value['scoring']==observation,'OUTPUT_INVALID','Published ESM numeric observations differ')
            for r in observation['records']:
                from . import revision_v2
                scored[r['sample_number']]=(revision_v2.esm(r['score'],observation['baseline']['score']) if revision_v2.enabled(cfg) else
                    sampling.esm_check(r['score'],observation['baseline']['score'],cfg['policies']['esm_near_zero']))
        for r in records:
            missing_reason=cheap.get('reason_code') or ('NOT_RUN' if not cheap.get('job_id') else 'SCORE_UNAVAILABLE')
            r['esm_if1']=scored.get(r['sample_number'],contract.check('NOT_ASSESSED',missing_reason,
                execution='ERROR' if cheap.get('state') in ('failed','timed_out') else 'NOT_RUN',score=None))
            if revision_v2.enabled(cfg):r['esm_source']=(source(rt,cheap) or {}).get('artifact')
            hard=r['constraint_check']['check_status']
            r['validation']=contract.check('FAIL' if hard=='FAIL' else 'NOT_ASSESSED',
                *r['constraint_check']['reason_codes'],*(['configuration_incomplete'] if hard!='FAIL' else []),
                execution='NOT_RUN',evaluation_profile_id='original')
            r['structure']=None;r['structure_reason']='EARLY_HARD_FAIL' if hard=='FAIL' else 'configuration_incomplete'
            r['description_score']=r['comparison_score']=r['acceptance_score']=None
            r['score_contexts']=dict(description=None,comparison=None,acceptance=None)
            r['ranking_context']=dict(group_id=None,evaluation_profile_id='original',
                evidence_group=evidence_group('original',r['validation']['check_status'],False,False),
                nonstandard=r['nonstandard'],model_disagreement=False,rank=None,group_rank=None)
            r.update(acceptance(hard,False,dict(value=None),None,nonstandard=r['nonstandard']))
        formal.extend(records);rounds.append(dict(round_index=i,requested=cfg['formal_round_sizes'][i],generated=len(records),
            unique=sum(r['disposition']=='FORMAL_POOL' for r in records),failed=sum(r['disposition']=='REJECTED' for r in records)))
    if sampling_only:
        # The proposal/formal routing decisions consume only these verified
        # sampling facts. Structure/L4/FoldX are replayed before their consumer
        # and again for the final report; do not replay them at both early gates.
        return dict(proposal_summary=proposal,formal_records=formal)
    if revision_v2.enabled(cfg):
        from .revision_sequence import attach
        attach(formal)
    from .revision_runtime import enrich,selected_foldx
    enrich(rt,jid,body,data,formal)
    ledger=rt.execution(jid).get('revision_ledger',budget.new(cfg))
    pool=selected_foldx(formal,cfg,ledger,jid)
    from .revision_structure import plan as structure_plan
    structure_allocation=structure_plan(formal,{r['candidate_id']:r['esm_if1'] for r in formal},ledger,cfg,cfg['policies']['model_roles'])
    for item,record in zip(structure_allocation,formal):
        observations=record.get('structure_observations',{})
        if observations:
            states=[v['execution_status'] for v in observations.values()]
            execution='RUNNING' if 'RUNNING' in states else 'SUCCEEDED' if all(s=='SUCCEEDED' for s in states) else (
                'PARTIAL' if 'SUCCEEDED' in states else 'ERROR' if 'ERROR' in states else 'NOT_RUN')
            item.update(contract.check(record['checks'].get('structure',record['validation']['check_status']),execution=execution),engines=list(observations))
    result=dict(shared_contract_version=contract.VERSION,calculation_config=cfg,permission_snapshot=snap,
        proposal_summary=proposal,formal_records=formal,rounds=rounds,foldx_pool=pool,run_audit=budget.summary(ledger,cfg),
        acceptance_status=task_acceptance([r['acceptance_status'] for r in formal],False),
        provisional_acceptance_status=task_acceptance([r['provisional_acceptance_status'] for r in formal],False),
        structure_allocation=structure_allocation,failed_native_stages=failures,scientific_release=False,usable_for_pipeline=False,
        coverage_complete=False,run_execution_status='PARTIAL' if formal else 'NOT_RUN',
        runtime_allocations=rt.execution(jid).get('revision_allocations',{}),
        runtime_policy_status='ENGINEERING_UNREVIEWED',
        stop_reason_codes=[],design_outcomes=[],diagnostics=[contract.diagnostic('CONFIGURATION','configuration_incomplete',
            'Missing policies: '+', '.join(k for k,v in cfg['policies'].items() if v is None))])
    from . import revision_v2
    if revision_v2.enabled(cfg):
        from .revision_v2_runtime import verify_allocations
        verify_allocations(rt,jid,body,formal)
        frozen=rt.execution(jid).get('revision_v2_frozen')
        result.update(runtime_policy_status='pending_calibration',diagnostics=[],
            frozen_wt=frozen,ranking=revision_v2.rank(formal,cfg),
            downstream_allocations=rt.execution(jid).get('revision_v2_allocations',{}))
        # Missing coverage is never converted to task-level FAIL. A fully
        # observed hard rejection needs no downstream model execution.
        complete=bool(formal) and all(r['generated']==r['requested'] for r in rounds) and not failures and (
            len(rounds)==3 or any(r['validation']['check_status']=='PASS' for r in formal)) and all(r['disposition'] in ('REJECTED','DUPLICATE','WT_CONTROL') or
            r['acceptance_status']=='FAIL' or r.get('final_evidence_complete') is True for r in formal)
        evaluated=[r for r in formal if r['disposition'] in ('FORMAL_POOL','REJECTED')]
        result.update(coverage_complete=complete,
            acceptance_status=task_acceptance([r['acceptance_status'] for r in evaluated],complete),
            provisional_acceptance_status=task_acceptance([r['provisional_acceptance_status'] for r in evaluated],complete))
    from .revision_schema import validate
    return validate(result)


def tick(rt,jid,body):
    from .service import _record
    data,reason=inputs(rt,jid,body)
    if reason=='T4_EMPTY_FIXED_CONFIRMATION_REQUIRED':
        from .confirmation import pause
        pause(rt,jid);return False
    if reason:
        _record(rt,jid,STAGE,dict(job_id=None,state='skipped',origin=None,reason_code=reason));return True
    cfg=body['revision_config'];snap=data['snapshot']
    from . import revision_v2
    if revision_v2.enabled(cfg):
        from .revision_v2_runtime import freeze
        freeze(rt,jid,body)
    def finish(outcome):
        terminal_children(rt,jid)
        fact=assemble(rt,jid,body,data);fact['design_outcomes']=[outcome];fact['stop_reason_codes']=[outcome]
        _store(rt,jid,fact)
        _record(rt,jid,STAGE,dict(job_id=None,state='succeeded',origin='INTERNAL_FACT',reason_code=outcome));return True
    if snap['mutation_budget']['K']==0 or snap['mutation_budget']['B']==0:return finish('no_designable_positions')
    if cfg['structure_eval_max']==0:return finish('budget_exhausted')
    if cfg['presampling_n']==0:return finish('no_valid_presampling')
    for i in range(2):
        if not child(rt,jid,body,f'proposal{i}',_native_request(body,data,'proposal_only',i,snap['eligible_positions'])):return False
        if rt.execution(jid)['nodes'][f'proposal{i}'].get('reason_code')=='SKIPPED_BUDGET':return finish('budget_exhausted')
    fact=assemble(rt,jid,body,data,sampling_only=True);proposal=fact['proposal_summary']
    if proposal['quarantine_receipts']:return finish('association_error')
    if not proposal['nomination_positions']:return finish('no_valid_presampling' if not proposal['valid_count'] else 'no_designable_positions')
    for i in range(3):
        if not child(rt,jid,body,f'formal{i}',_native_request(body,data,'formal',i,proposal['nomination_positions'])):return False
        rows=rt.execution(jid)['nodes']
        if rows[f'formal{i}'].get('reason_code')=='SKIPPED_BUDGET':return finish('budget_exhausted')
        if rows[f'formal{i}']['state']!='succeeded':return finish('incomplete_only')
        fact=assemble(rt,jid,body,data,sampling_only=True)
        from .service import source
        current_ref=source(rt,rows[f'formal{i}'])['artifact']
        candidates=[r for r in fact['formal_records'] if r['generation_source']==current_ref and r['disposition']=='FORMAL_POOL']
        if candidates:
            req=dict(protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
                structure_artifact=snap['wt_structure_id'],n11_artifact=current_ref,
                sample_numbers=[r['sample_number'] for r in candidates],baseline_artifact=None,timeout_seconds=900,
                shared_contract_version=contract.VERSION,calculation_config_id=cfg['calculation_config_id'])
            if not child(rt,jid,body,f'cheap{i}',req):return False
            if rt.execution(jid)['nodes'][f'cheap{i}'].get('reason_code')=='SKIPPED_BUDGET':return finish('budget_exhausted')
            # Unknown scientific policies may not be converted into PASS, nor
            # trigger more sampling. All independent observations are retained.
            from .revision_runtime import tick as runtime_tick
            if revision_v2.enabled(cfg):
                from .revision_v2_runtime import tick as runtime_tick
            fact=assemble(rt,jid,body,data)
            outcome=rt.execution(jid).get('revision_round_outcomes',{}).get(str(i))
            if outcome is None:outcome=runtime_tick(rt,jid,body,data,fact['formal_records'],i)
            if outcome is None:return False
            with rt._tx() as db:
                ex=rt._execution(db,jid);ex.setdefault('revision_round_outcomes',{})[str(i)]=outcome
                rt._execution_store(db,jid,ex)
            if outcome!='all_rejected' or i==2:return finish(outcome)
        available=cfg['structure_eval_max']>0
        reason=budget.retry_reason(system_errors=[],budget_available=available,designable=True,original_pass=False,round_index=i)
        if reason:return finish('all_rejected' if reason=='FORMAL_ROUNDS_EXHAUSTED' and
            all(r['disposition']=='REJECTED' for r in fact['formal_records']) else 'incomplete_only' if reason=='FORMAL_ROUNDS_EXHAUSTED' else reason)
    return finish('all_rejected')


def verified_fact(rt,jid,body):
    stored=rt.execution(jid).get('revision_state')
    if stored is None:return None
    terminal_children(rt,jid)
    data,reason=inputs(rt,jid,body)
    ensure(reason is None,'OUTPUT_INVALID','Revision inputs unavailable during verification')
    fresh=assemble(rt,jid,body,data);fresh['design_outcomes']=stored['design_outcomes'];fresh['stop_reason_codes']=stored['stop_reason_codes']
    ensure(fresh==stored,'OUTPUT_INVALID','Revision facts differ from registered native sources')
    return fresh
