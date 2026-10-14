"""Explicit operator continuation at N10; never resurrect a cancelled job.

The same run's completed N11/N12 sources and T4 receipt remain immutable.
All candidate N10 jobs are new executions under the current code profile.
This is deliberately not a general retry or an automatic fallback.
"""
import copy
from ...common import TERMINAL, decode, encode, ensure, new_id, now, sha
from . import policy, service, validation, design_rounds, engineering


def prepare(rt, source_job_id):
    job=rt.get(source_job_id)
    ensure(job['tool_id']==policy.TOOL and job['state']=='cancelled',
           'INVALID_STATE','N10 continuation requires an explicitly cancelled workflow')
    ex=rt.execution(source_job_id)
    ensure(ex.get('tree_stopped') is True and not ex.get('fatal_error') and not ex.get('pending_confirmation'),
           'INVALID_STATE','Source execution must be stopped without unresolved failure or confirmation')
    body=policy.request(rt._request_bytes(job))
    ensure(engineering.enabled(body) and body['configuration']==service.configuration(rt),
           'PROFILE_NOT_APPROVED','Same workflow mode and local configuration required')
    for row in ex['nodes'].values():
        if row.get('job_id'):
            child=rt.get(row['job_id'])
            ensure(child['run_id']==job['run_id'] and child['state'] in TERMINAL,
                   'INVALID_STATE','Source children must be terminal and belong to this run')
            if child.get('attempt_id'):
                ensure(rt.execution(child['job_id']).get('tree_stopped') is True,
                       'INVALID_STATE','Source child termination is unconfirmed')
    # Rebuild every completed validation from native artifacts, including hashes.
    service.snapshot(rt, source_job_id)
    schedule=policy.order(body);cut=schedule.index('c_s1_structure')
    prefix=set(schedule[:cut])
    allowed=prefix | set(validation.CHILDREN) | {'wt_msa'}
    rows={k:copy.deepcopy(v) for k,v in ex['nodes'].items() if k in allowed}
    ensure(all(n in rows and rows[n]['state'] in ('succeeded','skipped','unavailable','blocked')
               for n in schedule[:cut]),'INVALID_STATE','Incomplete prefix before candidate N10')
    active=design_rounds.active(rows)
    ensure(active.get('design',{}).get('state')=='succeeded' and
           active.get('validation',{}).get('state')=='succeeded',
           'INVALID_STATE','Completed N11 generation and S28 validation required')
    context=active['validation']['validation_source']
    fact=validation.verified_fact(rt,context['workflow_job_id'],context['node'])
    ensure(fact['run_id']==job['run_id'] and fact['review_pool'],
           'INVALID_STATE','No validated candidates for N10 continuation')
    for row in rows.values():
        if row.get('job_id'):
            row['prior_origin']=row.get('origin')
            row['origin']='SAME_RUN_REUSE'
    return job,body,ex,rows


def prepare_stability(rt, source_job_id):
    """Only the stopped pre-admission N14 capacity failure can resume here.

    Every completed upstream artifact is reverified. Old jobs and receipts are
    immutable; the new workflow starts with the exact same full N14 request.
    """
    from . import m1, candidate_developability
    job=rt.get(source_job_id);ex=rt.execution(source_job_id)
    cancelled=(job['state']=='cancelled' and job.get('stop_reason')=='cancel' and job.get('error_code')=='CANCELLED')
    ensure(job['tool_id']==policy.TOOL and (cancelled or (job['state']=='failed' and
           job['error_code'] in ('OUTPUT_INVALID','INVALID_REQUEST') and not job.get('stop_reason'))),
           'INVALID_STATE','N14 continuation requires a failed capacity checkpoint')
    row=ex.get('nodes',{}).get('stability',{})
    cancelled=cancelled and row.get('job_id') is not None and not ex.get('fatal_error')
    if cancelled:
        stopped=rt.get(row['job_id'])
        ensure(stopped['tool_id']=='t01.real.foldx' and stopped['run_id']==job['run_id'] and
               stopped['state']=='cancelled' and stopped.get('stop_reason')=='cancel' and
               rt.execution(stopped['job_id']).get('tree_stopped') is True,
               'INVALID_STATE','Cancelled N14 native process must be confirmed stopped')
    capacity=(row.get('state')=='blocked' and not row.get('job_id') and
              row.get('reason_code')=='INVALID_REQUEST' and row.get('detail')=='Request exceeds tool capacity')
    projection=(not row and ex.get('fatal_error')=='OUTPUT_INVALID' and
                ex.get('fatal_detail')=='Coordinate projection would lose source precision' and
                (ex.get('continuation') or {}).get('kind')=='USER_AUTHORIZED_N14_CONTINUATION' and
                (ex.get('continuation') or {}).get('boundary')=='stability')
    ensure(ex.get('tree_stopped') is True and not ex.get('pending_confirmation') and
           (cancelled or ((capacity or projection) and ex.get('fatal_error') in ('OUTPUT_INVALID','INVALID_REQUEST'))),
           'INVALID_STATE','N14 capacity failure must precede native admission')
    body=policy.request(rt._request_bytes(job))
    ensure(engineering.enabled(body) and body['configuration']==service.configuration(rt),
           'PROFILE_NOT_APPROVED','Same workflow mode and local configuration required')
    schedule=policy.order(body);cut=schedule.index('stability')
    allowed=set(schedule[:cut]) | set(validation.CHILDREN) | {'wt_msa'}
    ensure(not any(r.get('job_id') for n,r in ex['nodes'].items() if n not in allowed and not (cancelled and n=='stability')),
           'INVALID_STATE','N14 or downstream work was already admitted')
    rows={n:copy.deepcopy(r) for n,r in ex['nodes'].items() if n in allowed}
    ensure(all(n in rows and rows[n]['state'] in ('succeeded','skipped','unavailable','blocked')
               for n in schedule[:cut]),'INVALID_STATE','Incomplete prefix before N14')
    for name in validation.NAMES:
        if rows.get(name,{}).get('state')=='succeeded':validation.verified_fact(rt,source_job_id,name)
    active=design_rounds.active(rows)
    ensure(active.get('validation',{}).get('state')=='succeeded' and
           rows.get('preselection',{}).get('origin')=='INTERNAL_FACT',
           'INVALID_STATE','Verified N12 and preselection required')
    expected=m1.preselection(rt,body,rows);stored=rows['preselection']['fact']
    if stored!=expected:
        # gen116 changed the validation parent but left this derived reference
        # at its original checkpoint. Only that proven provenance-only drift
        # is repairable; no candidate, score or selection may change.
        prior=(ex.get('continuation') or {}).get('source_job_id')
        context=stored.get('validation_source') or {}
        ensure(prior and context.get('workflow_job_id')==prior and
               rt.get(prior)['run_id']==job['run_id'] and
               rt.execution(prior)['nodes']['preselection']['fact']==stored and
               {k:v for k,v in stored.items() if k!='validation_source'}==
               {k:v for k,v in expected.items() if k!='validation_source'},
               'OUTPUT_INVALID','Preselection changed beyond continuation provenance')
        original=validation.verified_fact(rt,prior,context['node'])
        ensure(original==active['validation']['fact'],'OUTPUT_INVALID','Original N12 fact changed')
        rows['preselection']['fact']=expected
    for name,r in rows.items():
        if not r.get('job_id'):continue
        child=service.verified(rt,body,name,r['job_id'],job['run_id'],rows)
        ensure(child['state'] in TERMINAL and child['state']==r['state'] and
               (not child.get('attempt_id') or rt.execution(child['job_id']).get('tree_stopped') is True),
               'INVALID_STATE','Source child not terminal or termination unconfirmed')
        r['prior_origin']=r.get('origin');r['origin']='SAME_RUN_REUSE'
    # Verify all actual N10 values and exact selected-structure/config requests.
    records=[dict(r,sequence_sha256=sha(r['sequence'].encode()))
             for r in rt.result(active['design']['job_id'])['generation']['records']]
    candidate_developability.observations(rt,body,rows,records,job['run_id'])
    req,reason=service.request_for(rt,body,rows,'stability')
    ensure(reason is None and req is not None and 65536<len(encode(req))<=rt._request_limit('t01.real.foldx'),
           'INVALID_STATE','Replayed N14 request does not match the repaired capacity boundary')
    if cancelled:
        ensure(encode(req)==rt._request_bytes(stopped),'HASH_MISMATCH','Cancelled N14 request changed')
    if projection:
        # The preceding admitted continuation pins all reused children and the
        # original capacity checkpoint; this is not a generic OUTPUT_INVALID retry.
        prior_id=ex['continuation']['source_job_id'];prior=rt.get(prior_id);prior_ex=rt.execution(prior_id)
        ensure(prior['run_id']==job['run_id'] and prior['state']=='failed' and
               sha(encode(prior_ex))==ex['continuation']['source_execution_sha256'] and
               ex['continuation']['reused_children']=={n:r['job_id'] for n,r in rows.items() if r.get('job_id')},
               'OUTPUT_INVALID','N14 continuation provenance changed')
        from ..foldx.source import sources
        with rt._db() as db:prepared,_=sources(rt,db,req,job['run_id'])
        # Preserve the actual design basis: new FoldX PDB must equal the native
        # WT PDB already consumed by this round's N11, byte for byte.
        value=rt.result(active['design']['job_id'])
        refs=[r['artifact'] for r in value['raw_artifacts'] if r['path']=='native/target.pdb']
        ensure(len(refs)==1 and prepared['native/target.pdb']==rt.artifact_bytes(active['design']['job_id'],refs[0]['artifact_id']),
               'OUTPUT_INVALID','FoldX projected WT differs from the native N11 design basis')
    return job,body,ex,rows


def restart_candidate_analysis(rt, source_job_id, key):
    """Caller must have explicit user authorization; no scientific consent added."""
    body=policy.request(rt._request_bytes(rt.get(source_job_id)))
    if 'revision_config' in body:
        return _restart(rt,source_job_id,key,prepare_revision,'revision_design','revision_continuation')
    if rt.get(source_job_id)['state']=='failed' or rt.execution(source_job_id).get('nodes',{}).get('stability',{}).get('job_id'):
        return _restart(rt,source_job_id,key,prepare_stability,'stability','n14_continuation')
    return _restart(rt,source_job_id,key,prepare,'c_s1_structure','n10_continuation')


def prepare_revision(rt, source_job_id):
    """Resume a stopped v2 checkpoint before candidate structure admission.

    WT, proposal and formal sources, T4 receipt and cumulative budgets retain
    their producer identities. This is not a restart of arbitrary old runs.
    """
    from . import revision_v2,revision_v2_runtime,revision_controller
    job=rt.get(source_job_id);ex=rt.execution(source_job_id)
    ensure(job['tool_id']==policy.TOOL and job['state']=='cancelled' and
           job['stop_reason']=='cancel' and job['error_code']=='CANCELLED' and
           ex.get('tree_stopped') is True and not ex.get('dispatcher') and
           not ex.get('fatal_error') and not ex.get('pending_confirmation'),
           'INVALID_STATE','v2 continuation requires a confirmed stopped checkpoint')
    body=policy.request(rt._request_bytes(job))
    ensure(engineering.enabled(body) and revision_v2.enabled(body.get('revision_config',{})) and
           body['configuration']==service.configuration(rt),
           'PROFILE_NOT_APPROVED','Same v2 policy and local configuration required')
    schedule=policy.order(body);prefix=set(schedule[:schedule.index(revision_controller.STAGE)])
    rows=copy.deepcopy(ex['nodes'])
    scored='cheap0' in rows
    allowed=prefix | {'design','proposal0','proposal1','formal0'} | ({'cheap0','wt_msa'} if scored else set())
    ensure(set(rows)<=allowed and all(rows.get(n,{}).get('state') in
           ('succeeded','skipped','unavailable','blocked') for n in prefix) and
           all(rows.get(n,{}).get('state')=='succeeded' for n in ('proposal0','proposal1','formal0')) and
           not ex.get('revision_state') and not ex.get('revision_round_outcomes') and
           not ex.get('revision_bindings') and not ex.get('revision_v2_allocations') and
           (scored or not ex.get('revision_allocations')),
           'INVALID_STATE','v2 checkpoint must precede candidate structure and downstream admission')
    if scored:
        ensure(rows['cheap0'].get('state')=='succeeded' and rows.get('wt_msa',{}).get('job_id') and
               set(ex.get('revision_allocations',{}))=={'0'},
               'INVALID_STATE','Scored v2 continuation requires a stopped first WT MSA checkpoint')
    for name,row in rows.items():
        if not row.get('job_id'):continue
        child=service.verified(rt,body,name,row['job_id'],job['run_id'],rows)
        if scored and name=='wt_msa':
            # Cancellation leaves the controller's last observed row behind.
            # Only the actual confirmed cancelled child may be replaced.
            ensure(child['state']=='cancelled' and child.get('stop_reason')=='cancel' and
                   child['error_code']=='CANCELLED','INVALID_STATE','WT MSA was not explicitly stopped')
            request=decode(rt._request_bytes(child))
            expected=dict(protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
                host_species=body['host_species'],seed=1,timeout_seconds=request['timeout_seconds'],mode='msa_only')
            ensure(0<request['timeout_seconds']<=7200 and request==expected,
                   'OUTPUT_INVALID','Stopped WT MSA request differs')
        else:ensure(child['state']==row['state'],'INVALID_STATE','v2 source child state differs')
        ensure(child['state'] in TERMINAL and
               (not child.get('attempt_id') or rt.execution(child['job_id']).get('tree_stopped') is True),
               'INVALID_STATE','v2 source child termination is unconfirmed')
    data,reason=revision_controller.inputs(rt,source_job_id,body)
    ensure(reason is None,'INVALID_STATE','v2 permission audit or T4 consent unavailable')
    consent=rows.get('design',{}).get('confirmation')
    if consent is not None:
        audit=rt.get(rows['design_inputs']['job_id']);ref=service.source(rt,rows['design_inputs'])['artifact']
        draft=rt.result(audit['job_id'])['audit']['pending_n11_request_draft']
        origin=source_job_id
        for _ in range(8):
            if origin==consent['job_id']:break
            ancestor=rt.execution(origin).get('continuation',{})
            ensure(ancestor.get('kind')=='USER_AUTHORIZED_V2_CHECKPOINT_CONTINUATION' and
                   ancestor.get('boundary')=='revision_design' and ancestor.get('source_job_id'),
                   'FORBIDDEN','v2 T4 ancestor is not a verified continuation')
            origin=ancestor['source_job_id'];prior=rt.get(origin);prior_ex=rt.execution(origin)
            ensure(prior['run_id']==job['run_id'] and prior['request_artifact']==job['request_artifact'] and
                   prior['state']=='cancelled' and prior_ex.get('tree_stopped') is True and
                   sha(encode(prior_ex))==ancestor['source_execution_sha256'],
                   'FORBIDDEN','v2 T4 ancestor checkpoint differs')
        ensure(origin==consent['job_id'] and
               rt.execution(origin)['nodes']['design']['confirmation']==consent and consent['run_id']==job['run_id'] and
               consent['audit_job_id']==audit['job_id'] and consent['audit_sha256']==ref['sha256'] and
               consent['draft_sha256']==sha(encode(draft)) and consent['decision'] is True,
               'FORBIDDEN','v2 continuation T4 receipt differs from the stopped source audit')
    frozen=revision_v2_runtime.verified_freeze(rt,source_job_id,body)
    ensure(frozen is not None and ex.get('revision_ledger'),'OUTPUT_INVALID','v2 frozen WT or cumulative ledger unavailable')
    # Reconstruct formal sequences from native bytes and check the submitted
    # contexts; no native execution, extra generation or new consent occurs.
    fact=revision_controller.assemble(rt,source_job_id,body,data)
    # Rebuild the consumed budget from real terminal child identities and
    # timestamps so a copied checkpoint cannot reset prior calls or costs.
    from datetime import datetime
    from . import revision_budget
    expected=revision_budget.new(body['revision_config'])
    def seconds(end,start):
        return max(0.,(datetime.fromisoformat(end.replace('Z','+00:00'))-
                       datetime.fromisoformat(start.replace('Z','+00:00'))).total_seconds()) if end and start else None
    for name in ('proposal0','proposal1','formal0'):
        child=rt.get(rows[name]['job_id']);request=decode(rt._request_bytes(child))
        generated,_,_=revision_controller.generation(rt,body,rows,name,job['run_id'])
        hashes=[sha(r['sequence'].encode()) for r in generated['records']]
        revision_budget.reserve(expected,body['revision_config'],name,
            'proposal' if name.startswith('proposal') else 'formal',[],requested=request['n_designs'])
        revision_budget.observe(expected,name,dict(attempt_id=child['attempt_id'],job_id=child['job_id'],
            execution_status='SUCCEEDED',queue_seconds=seconds(child['started_at'],child['created_at']),
            execution_seconds=seconds(child.get('finished_at') or child.get('ended_at'),child['started_at']),
            internal_runs=len(hashes) if generated['engine_runtime'].get('tool_invoked') else 0,cache_hit=False))
        revision_budget.observe_objects(expected,name,hashes)
    if scored:
        child=rt.get(rows['cheap0']['job_id']);request=decode(rt._request_bytes(child))
        revision_controller.reserve_child({'revision_ledger':expected},body,'cheap0',request)
        value=rt.result(child['job_id'])
        raw=next(r for r in value['raw_artifacts'] if r['path']=='output/runtime.json')
        runtime=decode(rt.artifact_bytes(child['job_id'],raw['artifact']['artifact_id']))
        revision_budget.observe(expected,'cheap0',dict(attempt_id=child['attempt_id'],job_id=child['job_id'],
            execution_status='SUCCEEDED',queue_seconds=seconds(child['started_at'],child['created_at']),
            execution_seconds=seconds(child.get('finished_at') or child.get('ended_at'),child['started_at']),
            internal_runs=runtime['baseline_model_calls']+runtime['variant_model_calls'],cache_hit=False))
        from .revision_sampling import select_structure
        from .revision_structure import scheduled_engines
        records=fact['formal_records']
        ids=select_structure(records,{r['candidate_id']:r['esm_if1'] for r in records if r['disposition']=='FORMAL_POOL'},
                             body['revision_config']['structure_eval_max'],require_sequence_metrics=True)
        allocation=[dict(candidate_id=r['candidate_id'],keys=[f'rx0_s{r["sample_number"]}_{e}' for e in scheduled_engines(len(r['sequence']),len(r['mutations']),body['revision_config'])])
            for r in records if r['disposition']=='FORMAL_POOL' and r['candidate_id'] in ids and
            scheduled_engines(len(r['sequence']),len(r['mutations']),body['revision_config'])]
        ensure(ex['revision_allocations']=={'0':allocation},'OUTPUT_INVALID','v2 stopped structure allocation differs from scored candidates')
        for item in allocation:
            record=next(r for r in records if r['candidate_id']==item['candidate_id'])
            for name in item['keys']:
                ensure(revision_budget.reserve(expected,body['revision_config'],name,'structure',[record['content_hash']]),
                       'OUTPUT_INVALID','v2 stopped structure allocation exceeded its budget')
    ensure(expected==ex['revision_ledger'],'OUTPUT_INVALID','v2 checkpoint cumulative budget differs from native attempts')
    for row in rows.values():
        if row.get('job_id'):
            row['prior_origin']=row.get('origin');row['origin']='SAME_RUN_REUSE'
    if scored:rows.pop('wt_msa')
    return job,body,ex,rows


def _restart(rt, source_job_id, key, prepare_source, boundary, operation):
    # The idempotency check precedes expensive source replay on repeated calls.
    fingerprint=encode(dict(source_job_id=source_job_id,boundary=boundary))
    with rt._db() as db:
        prior=db.execute('SELECT response,fingerprint FROM idempotency WHERE scope=? AND operation=? AND key=?',
                         (rt.scope,operation,key)).fetchone()
        if prior:
            from ...common import decode
            ensure(prior['fingerprint']==sha(fingerprint),'IDEMPOTENCY_CONFLICT','Continuation key differs')
            return rt._job(db,decode(prior['response'])['job_id'])
    source,body,old,rows=prepare_source(rt,source_job_id)
    checkpoint=sha(encode(old))
    with rt._tx() as db:
        def action():
            current=rt._job(db,source_job_id)
            ensure(current==source and sha(encode(rt._execution(db,source_job_id)))==checkpoint,
                   'INVALID_STATE','Source checkpoint changed during verification')
            request=service.envelope(source['run_id'],source['request_artifact'],policy,key)
            rt._admit(db,request)
            before=rt._new_job(db,request,encode(request),retry_of=source_job_id)
            job=copy.deepcopy(before)
            job.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
                       lease_epoch=1,started_at=now())
            # Completed facts retain their verified producer context. Rebinding
            # just N12 would invalidate N13 preselection and downstream receipts.
            ex=dict(nodes=rows,phase='scheduling',tree_stopped=False,started_at=job['started_at'],dispatcher=None,
                continuation=dict(kind='USER_AUTHORIZED_V2_CHECKPOINT_CONTINUATION' if boundary=='revision_design' else
                    'USER_AUTHORIZED_N14_CONTINUATION' if boundary=='stability' else 'USER_AUTHORIZED_N10_RESTART',source_job_id=source_job_id,
                    source_run_id=source['run_id'],source_execution_sha256=checkpoint,
                    source_execution_profile=source['execution_profile'],boundary=boundary,
                    reused_children={n:r['job_id'] for n,r in rows.items() if r.get('job_id')},
                    candidate_generation_repeated=False,scientific_consent_added=False))
            if boundary=='revision_design':
                ex.update(revision_v2_frozen=copy.deepcopy(old['revision_v2_frozen']),
                          revision_ledger=copy.deepcopy(old['revision_ledger']),
                          started_at=old['started_at'],
                          confirmation_wait_seconds=old.get('confirmation_wait_seconds',0))
                if 'cheap0' in rows:
                    stopped=rt._job(db,old['nodes']['wt_msa']['job_id'])
                    ex['revision_allocations']=copy.deepcopy(old['revision_allocations'])
                    ex['continuation'].update(cheap_scoring_repeated=False,
                        stopped_children=dict(wt_msa=dict(job_id=stopped['job_id'],state=stopped['state'],
                            attempt_id=stopped['attempt_id'],request_artifact=stopped['request_artifact'])),
                        msa_preparation_repeated=True)
            rt._execution_store(db,job['job_id'],ex)
            rt._store(db,job,before,operation)
            return job
        return rt._idempotent(db,operation,key,fingerprint,action)
