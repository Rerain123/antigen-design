"""Stopped pre-score v2 checkpoints retain source identities, consent and costs."""
import copy
from types import SimpleNamespace
import pytest
from t01_phase1_real.common import encode,sha,now,new_id,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import continuation as ct,service,policy
from t01_phase1_real.development.workflow import revision_v2 as v,revision_controller as rc,revision_v2_runtime as vr,revision_budget as budget
from test_expert_revision_workflow import revised_body


def checkpoint(monkeypatch,model_policy=v.LEGACY_MODEL_POLICY):
    body=revised_body();body['revision_config']=v.config('continuation-test',model_policy=model_policy);body.update(configuration={},structure_artifact=None)
    source=dict(job_id='source',run_id='run',tool_id=policy.TOOL,state='cancelled',stop_reason='cancel',error_code='CANCELLED')
    prefix=policy.order(body)[:policy.order(body).index(rc.STAGE)]
    rows={n:dict(state='skipped',job_id=None) for n in prefix}
    rows['design_inputs']=dict(job_id='audit',state='succeeded')
    draft={'original':'immutable'}
    audit=dict(job_id='audit',run_id='run',state='succeeded',attempt_id='audit-attempt',artifacts=[dict(role='result',sha256='a'*64)])
    receipt=dict(job_id='source',run_id='run',audit_job_id='audit',audit_sha256='a'*64,
        draft_sha256=sha(encode(draft)),decision=True,actor='original-owner')
    rows['design']=dict(state='ready',job_id=None,confirmation=receipt)
    cfg=body['revision_config'];ledger=budget.new(cfg);jobs={'source':source,'audit':audit};requests={};generations={}
    for name,n in [('proposal0',12),('proposal1',12),('formal0',24)]:
        rows[name]=dict(job_id=name,state='succeeded',origin='NEW_EXECUTION')
        child=dict(job_id=name,run_id='run',state='succeeded',attempt_id=name+'-attempt',
            created_at='2026-09-30T00:00:00Z',started_at='2026-09-30T00:00:01Z',finished_at='2026-09-30T00:00:03Z')
        jobs[name]=child;requests[name]=encode(dict(n_designs=n))
        generations[name]=dict(records=[dict(sequence=str(i)) for i in range(n)],engine_runtime=dict(tool_invoked=True))
        budget.reserve(ledger,cfg,name,'formal' if name=='formal0' else 'proposal',[],requested=n)
        budget.observe(ledger,name,dict(attempt_id=child['attempt_id'],job_id=name,execution_status='SUCCEEDED',
            queue_seconds=1.,execution_seconds=2.,internal_runs=n,cache_hit=False))
        budget.observe_objects(ledger,name,[sha(str(i).encode()) for i in range(n)])
    ex=dict(nodes=rows,tree_stopped=True,dispatcher=None,revision_ledger=ledger,revision_v2_frozen={'fixed':'WT'},started_at=now())
    rt=SimpleNamespace(get=lambda id:jobs[id],execution=lambda id:ex if id=='source' else dict(tree_stopped=True),
        _request_bytes=lambda j:encode(body) if j['job_id']=='source' else requests[j['job_id']],
        result=lambda id:dict(audit=dict(pending_n11_request_draft=draft)))
    monkeypatch.setattr(service,'configuration',lambda rt:{})
    monkeypatch.setattr(service,'verified',lambda rt,b,n,id,run,r:jobs[id])
    monkeypatch.setattr(rc,'inputs',lambda *a:({},None))
    monkeypatch.setattr(vr,'verified_freeze',lambda *a:ex['revision_v2_frozen'])
    monkeypatch.setattr(rc,'assemble',lambda *a:{})
    monkeypatch.setattr(rc,'generation',lambda rt,b,r,n,run:(generations[n],{},jobs[n]))
    return rt,source,body,ex,jobs


def test_checkpoint_replay_preserves_native_sources_and_receipt(monkeypatch):
    rt,source,body,ex,jobs=checkpoint(monkeypatch);before=copy.deepcopy(ex)
    _,_,old,rows=ct.prepare_revision(rt,'source')
    assert ex==before and old==ex
    assert rows['design']['confirmation']==ex['nodes']['design']['confirmation']
    assert rows['formal0']['job_id']=='formal0' and rows['formal0']['origin']=='SAME_RUN_REUSE'
    assert rows['formal0']['prior_origin']=='NEW_EXECUTION'


@pytest.mark.parametrize('damage',['live','unconfirmed','dispatcher','fatal','pending','cheap','later_round','unfinished','foreign_child',
    'child_not_stopped','configuration','v1','consent_run','consent_audit','consent_parent','consent_no','ledger_reset','ledger_cost','ledger_config','missing_freeze'])
def test_only_verified_stopped_pre_score_checkpoint_allowed(monkeypatch,damage):
    rt,source,body,ex,jobs=checkpoint(monkeypatch)
    if damage=='live':source['state']='running'
    elif damage=='unconfirmed':ex['tree_stopped']=False
    elif damage=='dispatcher':ex['dispatcher']={'pid':10}
    elif damage=='fatal':ex['fatal_error']='OUTPUT_INVALID'
    elif damage=='pending':ex['pending_confirmation']={'id':'pending'}
    elif damage=='cheap':ex['nodes']['cheap0']=dict(state='succeeded',job_id='cheap')
    elif damage=='later_round':ex['nodes']['formal1']=dict(state='succeeded',job_id='formal1')
    elif damage=='unfinished':ex['nodes']['formal0']['state']='running'
    elif damage=='foreign_child':
        monkeypatch.setattr(service,'verified',lambda *a:(_ for _ in ()).throw(RuntimeFault('FORBIDDEN','foreign run')))
    elif damage=='child_not_stopped':rt.execution=lambda id:ex if id=='source' else dict(tree_stopped=False)
    elif damage=='configuration':body['configuration']={'different':True}
    elif damage=='v1':body['revision_config']=revised_body()['revision_config']
    elif damage.startswith('consent_'):
        c=ex['nodes']['design']['confirmation']
        c[{'consent_run':'run_id','consent_audit':'audit_sha256','consent_parent':'job_id','consent_no':'decision'}[damage]]='foreign' if damage!='consent_no' else False
    elif damage=='ledger_reset':ex['revision_ledger']=budget.new(body['revision_config'])
    elif damage=='ledger_cost':ex['revision_ledger']['attempts']['formal0-attempt']['execution_seconds']=0
    elif damage=='ledger_config':ex['revision_ledger']['config_sha256']='0'*64
    elif damage=='missing_freeze':ex['revision_v2_frozen']=None
    with pytest.raises(RuntimeFault):ct.prepare_revision(rt,'source')


def test_new_parent_preserves_full_budget_deadline_and_old_job(tmp_path,monkeypatch):
    rt=Runtime(tmp_path/'runtime');body=revised_body();body['revision_config']=v.config('continuation')
    source=rt.submit_workflow(encode(body),'source');jid=source['job_id']
    with rt._tx() as db:
        j=rt._job(db,jid);started='2026-09-30T00:00:01Z'
        rt._store(db,dict(j,state='running',started_at=started,attempt_id=new_id('attempt'),execution_identity='exec-source'),j,'fixture')
        rt._execution_store(db,jid,dict(nodes={},started_at=started,tree_stopped=False))
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=jid,idempotency_key='stop')))
    source=service.finish(rt,jid);body=policy.request(rt._request_bytes(source))
    with rt._tx() as db:
        ex=rt._execution(db,jid)
        ex.update(revision_ledger={'original-costs':True},revision_v2_frozen={'original-WT':True},confirmation_wait_seconds=42)
        rt._execution_store(db,jid,ex)
    old=rt.execution(jid);rows={'formal0':dict(job_id='native',state='succeeded'),
        'design':dict(confirmation={'job_id':jid,'decision':True})}
    monkeypatch.setattr(ct,'prepare_revision',lambda *a:(source,body,old,rows))
    fresh=ct.restart_candidate_analysis(rt,jid,'continue-v2');ex=rt.execution(fresh['job_id'])
    assert fresh['job_id']!=jid and fresh['run_id']==source['run_id']
    assert fresh['request_artifact']==source['request_artifact'] and rt.get(jid)==source and rt.execution(jid)==old
    assert ex['revision_ledger']==old['revision_ledger'] and ex['revision_v2_frozen']==old['revision_v2_frozen']
    assert ex['started_at']==old['started_at'] and ex['confirmation_wait_seconds']==42
    assert ex['nodes']==rows and ex['continuation']['scientific_consent_added'] is False
    assert ex['continuation']['candidate_generation_repeated'] is False
    monkeypatch.setattr(ct,'prepare_revision',lambda *a:pytest.fail('duplicate checkpoint replay'))
    assert ct.restart_candidate_analysis(rt,jid,'continue-v2')==fresh


def scored_checkpoint(monkeypatch,model_policy=v.LEGACY_MODEL_POLICY):
    rt,source,body,ex,jobs=checkpoint(monkeypatch,model_policy);body['revision_config']['structure_eval_max']=3
    # Changing the fixture configuration requires reconstructing its original
    # ledger header before adding the actual scoring reservation.
    ex['revision_ledger']['config_sha256']=sha(encode(body['revision_config']))
    cheap=dict(job_id='cheap',run_id='run',state='succeeded',attempt_id='cheap-attempt',
        created_at='2026-09-30T00:00:00Z',started_at='2026-09-30T00:00:01Z',finished_at='2026-09-30T00:00:03Z')
    msa=dict(job_id='msa',run_id='run',state='cancelled',stop_reason='cancel',error_code='CANCELLED',attempt_id='msa-attempt')
    jobs.update(cheap=cheap,msa=msa)
    ex['nodes'].update(cheap0=dict(job_id='cheap',state='succeeded',origin='NEW_EXECUTION'),
        wt_msa=dict(job_id='msa',state='reconciling',origin='NEW_EXECUTION'))
    request=dict(n11_artifact={'sha256':'f'*64},sample_numbers=[1,2,3])
    original_request=rt._request_bytes
    msa_request=dict(protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
        host_species=body['host_species'],seed=1,timeout_seconds=7200,mode='msa_only')
    rt._request_bytes=lambda j:encode(request) if j['job_id']=='cheap' else encode(msa_request) if j['job_id']=='msa' else original_request(j)
    original_result=rt.result
    rt.result=lambda id:dict(raw_artifacts=[dict(path='output/runtime.json',artifact={'artifact_id':'runtime'})]) if id=='cheap' else original_result(id)
    rt.artifact_bytes=lambda *a:encode(dict(baseline_model_calls=1,variant_model_calls=3))
    rc.reserve_child(ex,body,'cheap0',request)
    budget.observe(ex['revision_ledger'],'cheap0',dict(attempt_id=cheap['attempt_id'],job_id='cheap',execution_status='SUCCEEDED',
        queue_seconds=1.,execution_seconds=2.,internal_runs=4,cache_hit=False))
    records=[dict(candidate_id='candidate-'+str(i),sample_number=i,sequence='S'*i+'A'*(100-i),content_hash=sha(('S'*i+'A'*(100-i)).encode()),
        reference_id='fixture-wt',calculation_config_id=body['revision_config']['calculation_config_id'],rule_version=v.RULE,generation_source={'fixture':True},
        mutations=[{}]*6,disposition='FORMAL_POOL',esm_if1=dict(check_status='PASS',score=-float(i))) for i in range(1,4)]
    from t01_phase1_real.development.workflow.revision_sequence import attach
    attach(records)
    engines=['af3'] if model_policy==v.SINGLE_MODEL_POLICY else ['af3','esmfold2']
    allocation=[dict(candidate_id=r['candidate_id'],keys=[f'rx0_s{r["sample_number"]}_{e}' for e in engines]) for r in records]
    ex['revision_allocations']={'0':allocation}
    for item,r in zip(allocation,records):
        for key in item['keys']:assert budget.reserve(ex['revision_ledger'],body['revision_config'],key,'structure',[r['content_hash']])
    monkeypatch.setattr(rc,'assemble',lambda *a:dict(formal_records=records))
    return rt,source,body,ex,jobs,records


@pytest.mark.parametrize('model_policy',[v.LEGACY_MODEL_POLICY,v.SINGLE_MODEL_POLICY])
def test_stopped_msa_reuses_scoring_and_preserves_reserved_pool(monkeypatch,model_policy):
    rt,source,body,ex,jobs,records=scored_checkpoint(monkeypatch,model_policy);before=copy.deepcopy(ex)
    _,_,old,rows=ct.prepare_revision(rt,'source')
    assert old==before==ex and 'wt_msa' not in rows
    assert rows['cheap0']['job_id']=='cheap' and rows['cheap0']['origin']=='SAME_RUN_REUSE'
    assert ex['revision_ledger']['attempts']['cheap-attempt']['internal_runs']==4
    assert ex['revision_allocations']['0'][0]['keys']==(['rx0_s1_af3'] if model_policy==v.SINGLE_MODEL_POLICY else ['rx0_s1_af3','rx0_s1_esmfold2'])


@pytest.mark.parametrize('damage',['msa_running','msa_failed','msa_success','msa_request','msa_unstopped','cheap_running',
    'cheap_cost','cheap_reservation','allocation_candidate','allocation_engine','extra_binding','candidate_admitted'])
def test_scored_checkpoint_rejects_native_or_allocation_drift(monkeypatch,damage):
    rt,source,body,ex,jobs,records=scored_checkpoint(monkeypatch)
    if damage in ('msa_running','msa_failed','msa_success'):
        jobs['msa']['state']={'msa_running':'running','msa_failed':'failed','msa_success':'succeeded'}[damage]
    elif damage=='msa_request':
        original=rt._request_bytes
        rt._request_bytes=lambda j:encode({'timeout_seconds':7200,'mode':'fold_only'}) if j['job_id']=='msa' else original(j)
    elif damage=='msa_unstopped':
        original=rt.execution;rt.execution=lambda id:dict(tree_stopped=False) if id=='msa' else original(id)
    elif damage=='cheap_running':ex['nodes']['cheap0']['state']='running'
    elif damage=='cheap_cost':ex['revision_ledger']['attempts']['cheap-attempt']['internal_runs']=0
    elif damage=='cheap_reservation':ex['revision_ledger']['reservations']['cheap0']['objects']=[]
    elif damage=='allocation_candidate':ex['revision_allocations']['0'][0]['candidate_id']='foreign'
    elif damage=='allocation_engine':ex['revision_allocations']['0'][0]['keys']=['rx0_s1_esmfold2']
    elif damage=='extra_binding':ex['revision_bindings']={'rx0_s1_af3':{}}
    elif damage=='candidate_admitted':ex['nodes']['rx0_s1_af3']=dict(job_id='candidate',state='succeeded')
    with pytest.raises(RuntimeFault):ct.prepare_revision(rt,'source')


def test_t4_receipt_from_pinned_same_run_ancestor(monkeypatch):
    rt,source,body,ex,jobs,records=scored_checkpoint(monkeypatch)
    original=copy.deepcopy(ex);original['nodes']['design']['confirmation']['job_id']='ancestor'
    jobs['ancestor']=dict(source,job_id='ancestor',request_artifact={'source':'request'})
    source['request_artifact']={'source':'request'}
    ex['nodes']['design']['confirmation']=copy.deepcopy(original['nodes']['design']['confirmation'])
    ex['continuation']=dict(kind='USER_AUTHORIZED_V2_CHECKPOINT_CONTINUATION',boundary='revision_design',
        source_job_id='ancestor',source_execution_sha256=sha(encode(original)))
    old_execution=rt.execution
    rt.execution=lambda id:original if id=='ancestor' else old_execution(id)
    assert ct.prepare_revision(rt,'source')[3]['design']['confirmation']['job_id']=='ancestor'
    ex['continuation']['source_execution_sha256']='0'*64
    with pytest.raises(RuntimeFault,match='ancestor checkpoint'):ct.prepare_revision(rt,'source')
