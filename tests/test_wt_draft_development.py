"""WT engineering draft provenance, absent/failed inputs and closed-release lifecycle."""
import copy
import pytest

from t01_phase1_real.common import RuntimeFault, encode, decode, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.wt_draft import policy, service, compute
from t01_phase1_real.development.developability import policy as n10
from t01_phase1_real.development.glycosylation import policy as n07

SEQ='ACDEFGHIKLMNPQRSTVWY'


def request(**updates):
    value=dict(protein_sequence=SEQ,user_sequence_id='wt-engineering',host_species=None,organism=None,
        upstream={name:None for name in policy.PRODUCERS},timeout_seconds=30)
    value.update(updates);return value


def n10_request(sequence=SEQ):
    return dict(protein_sequence=sequence,user_sequence_id='n10-engineering',structure_input=dict(
        state='not_provided',artifact=None,reason_code=None),target_ph=None,target_ph_range=[4,8],dimension_weights=None,timeout_seconds=30)


def control(rt,job,operation,key):
    return rt.control(encode(dict(contract_version='0.1.0',operation=operation,job_id=job['job_id'],idempotency_key=key)))


def run(rt,body,key='wt',fault=None,tool=policy.TOOL):
    job=rt.submit_sequence(encode(body),key,tool);rt._development_fault=fault
    try:return rt.dispatch(job['job_id'])
    finally:rt._development_fault=None


def bound(rt,job,name='developability',**updates):
    body=request(**updates);body['upstream'][name]=service.task_source(rt,name,job['job_id']);return body


def closed(result):
    assert not result['usable_for_pipeline'] and not result['automatic_handoff']
    assert result['production_status']=='NOT_DEPLOYED' and result['scientific_signoff'] is None
    if result['draft'] is not None:
        draft=result['draft'];gate=draft['gate']
        assert gate['status'] in ('SUITABLE_FOR_DESIGN','NOT_SUITABLE_FOR_DESIGN','INPUT_INSUFFICIENT_OR_NOT_EVALUATED')
        assert gate['scientific_release_status']=='CLOSED'
        assert not any(gate[k] for k in ('n11_release','automatic_design_release','formal_wt_release','agent_c_handoff'))
        assert draft['agent_c_payload'] is None and not draft['candidate_record_complete'] and not draft['formal_wt_delivery']


def test_all_missing_is_queryable_draft_not_pass_or_scientific_rejection(tmp_path):
    rt=Runtime(tmp_path);job=run(rt,request());result=rt.result(job['job_id']);closed(result)
    draft=result['draft'];assert set(draft['checks']['missing'])==set(policy.PRODUCERS)
    assert draft['gate']['status']=='INPUT_INSUFFICIENT_OR_NOT_EVALUATED'
    assert draft['gate']['route']=='HOLD_FOR_INPUTS' and draft['gate']['business_gate_evaluated'] is False
    assert draft['checks']['executed']==[] and draft['checks']['scientific_checks_passed'] is None
    assert draft['fields']['developability']['value'] is None and draft['fields']['candidate_id']['value'] is None
    assert {r['code'] for r in draft['gate']['reasons']} >= {'OI_013_AGENT_C_PROTOCOL_UNRESOLVED','OI_014_CANDIDATE_MAPPING_INCOMPLETE','OI_021_FORMAL_GATE_AND_WT_STATE_UNSIGNED'}
    artifact=next(r['artifact'] for r in result['raw_artifacts'] if r['path']=='output/wt-draft.json')
    assert decode(rt.artifact_bytes(job['job_id'],artifact['artifact_id']))==draft


def test_real_partial_n10_retains_values_nulls_and_published_provenance(tmp_path):
    rt=Runtime(tmp_path);up=run(rt,n10_request(),tool=n10.TOOL);body=bound(rt,up)
    job=run(rt,body,'draft');result=rt.result(job['job_id']);closed(result)
    baseline=rt.result(up['job_id']);draft=result['draft']
    assert draft['fields']['developability']['value']==baseline['developability']
    assert draft['fields']['developability']['value']['overall_score'] is None
    assert draft['assessments']['developability']['observations']['steps']==baseline['steps']
    assert draft['checks']['unsigned']==['developability']
    assert 'N10_PARTIAL' in [r['code'] for r in draft['gate']['reasons']]
    assert result['source_receipts']['developability']['verified_artifacts']==up['artifacts']
    assert rt.submit_sequence(encode(body),'draft',policy.TOOL)==job
    assert rt.dispatch(job['job_id'])==job


@pytest.mark.parametrize('state',['compute_failure','queued_cancel','pending','preflight_failure'])
def test_failed_pending_and_no_result_upstream_are_distinct(tmp_path,state):
    rt=Runtime(tmp_path);up=rt.submit_sequence(encode(n10_request()),'up',n10.TOOL)
    if state=='compute_failure':
        rt._development_fault='compute_failure';up=rt.dispatch(up['job_id']);rt._development_fault=None
    elif state=='queued_cancel':up=control(rt,up,'cancel','up-cancel')
    elif state=='preflight_failure':
        # A changed execution profile is a no-attempt failure; preserve the input bytes.
        from t01_phase1_real.development.developability import service as upstream_service
        original=upstream_service.policy.registered_profile
        try:
            upstream_service.policy.registered_profile=lambda:dict(original(),sha256='0'*64)
            up=rt.dispatch(up['job_id'])
        finally:upstream_service.policy.registered_profile=original
    body=bound(rt,up);job=run(rt,body,'draft');result=rt.result(job['job_id']);closed(result)
    expected='pending' if state=='pending' else 'failed'
    assert result['draft']['assessments']['developability']['state']==expected
    assert result['draft']['fields']['developability']['value'] is None
    if state!='compute_failure':assert not result['draft']['assessments']['developability']['executed']


def test_n07_unperformed_shielding_false_does_not_become_pass(tmp_path):
    rt=Runtime(tmp_path);body=dict(protein_sequence=SEQ,user_sequence_id='scan',timeout_seconds=5,
        hotspot_input=dict(state='not_provided',hotspots=None,source=None,reason_code=None))
    up=run(rt,body,tool=n07.TOOL);job=run(rt,bound(rt,up,'glycosylation'),'draft');result=rt.result(job['job_id'])
    original=rt.result(up['job_id']);assert original['glycosylation']['site_count']==0
    assert original['glycosylation']['shielding_risk'] is False
    assert result['draft']['fields']['glycosylation']['value']['shielding_risk'] is None
    assert result['draft']['fields']['glycosylation']['value']['sites']==[]
    assert result['draft']['assessments']['glycosylation']['observations']['glycosylation']==original['glycosylation']


@pytest.mark.parametrize('change',['sequence','artifact_hash','attempt','wrong_tool','missing_ref','foreign_scope','request_bytes','raw_bytes'])
def test_forged_or_damaged_sources_rejected_before_admission(tmp_path,change):
    rt=Runtime(tmp_path);up=run(rt,n10_request(),tool=n10.TOOL);body=bound(rt,up)
    ref=body['upstream']['developability']['artifact']
    if change=='sequence':body['protein_sequence']='A'*len(SEQ)
    elif change=='artifact_hash':ref['sha256']='0'*64
    elif change=='attempt':ref['attempt_id']='t01p1r-attempt-'+'0'*32
    elif change=='wrong_tool':body['upstream']['domains']=body['upstream'].pop('developability');body['upstream']['developability']=None
    elif change=='missing_ref':body['upstream']['developability']['artifact']=None
    elif change=='foreign_scope':rt=Runtime(tmp_path,scope='another-scope')
    else:
        target=up['request_artifact'] if change=='request_bytes' else next(a for a in up['artifacts'] if a['role']=='raw')
        with rt._db() as db:row=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(target['artifact_id'],)).fetchone()
        path=rt.root/row['relative_path'];path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(RuntimeFault):rt.submit_sequence(encode(body),'bad-draft',policy.TOOL)


def test_post_admission_source_damage_blocks_execution_and_new_retry(tmp_path):
    rt=Runtime(tmp_path);up=run(rt,n10_request(),tool=n10.TOOL);body=bound(rt,up)
    job=rt.submit_sequence(encode(body),'draft',policy.TOOL);ref=body['upstream']['developability']['artifact']
    with rt._db() as db:row=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
    path=rt.root/row['relative_path'];original=path.read_bytes();path.write_bytes(original+b' ')
    failed=rt.dispatch(job['job_id']);assert failed['state']=='failed' and failed['attempt_id'] is None
    with pytest.raises(RuntimeFault):control(rt,failed,'retry','bad-retry')
    path.write_bytes(original);retry=control(rt,failed,'retry','fixed-retry')
    final=rt.dispatch(retry['job_id']);assert final['state']=='succeeded' and final['job_id']!=job['job_id']
    closed(rt.result(final['job_id']))


@pytest.mark.parametrize('fault,expected',[('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID'),('interrupt_after_claim','INTERRUPTED')])
def test_local_failures_recovery_and_retry(tmp_path,fault,expected):
    rt=Runtime(tmp_path);job=run(rt,request(),fault=fault)
    if fault=='interrupt_after_claim':job=rt.reconcile(job['job_id'])
    assert job['state']=='failed' and job['error_code']==expected
    result=rt.result(job['job_id']);assert result['draft'] is None;closed(result)
    retried=control(rt,job,'retry','retry');final=rt.dispatch(retried['job_id'])
    assert final['state']=='succeeded' and final['attempt_id']!=job['attempt_id'];closed(rt.result(final['job_id']))


def test_running_cancel_and_timeout_clear_draft(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);original=service.evaluate
    def cancel(body,files):
        control(rt,job,'cancel','running-cancel');return original(body,files)
    job=rt.submit_sequence(encode(request()),'cancel',policy.TOOL)
    monkeypatch.setattr(service,'evaluate',cancel);final=rt.dispatch(job['job_id'])
    assert final['state']=='cancelled' and rt.result(final['job_id'])['draft'] is None
    monkeypatch.setattr(service,'evaluate',original)
    clock=iter([0,100]);monkeypatch.setattr(service.time,'perf_counter',lambda:next(clock))
    final=run(rt,request(),'timeout');assert final['state']=='timed_out' and rt.result(final['job_id'])['draft'] is None


@pytest.mark.parametrize('field,value',[('automatic_handoff',True),('scientific_signoff',{'reviewer':'self'}),('gate_threshold',0.5),
    ('protein_sequence','AA*'),('timeout_seconds',True)])
def test_request_cannot_supply_release_controls_or_invalid_inputs(field,value):
    body=request();body[field]=value
    with pytest.raises(RuntimeFault):policy.request(encode(body))


def r57(topology=None,confidence=None,domains=None,**context):
    sequence='A'*500
    body=policy.request(encode(request(protein_sequence=sequence,design_context=dict(
        pathogen_type=context.get('pathogen_type'),membrane_design_confirm=context.get('membrane_design_confirm',False),
        low_conf_design_confirm=context.get('low_conf_design_confirm',False)))))
    receipts={name:dict(state='missing') for name in policy.PRODUCERS};values={}
    if topology is not None:
        receipts['topology']['state']='available';values['topology']=dict(topology=topology)
    if confidence is not None:
        receipts['structure']['state']='available'
        values['structure']=dict(analysis=dict(quality=dict(quality=dict(confidence=confidence))))
    if domains is not None:
        receipts['domains']['state']='available';values['domains']=dict(analysis=dict(functional_domains=domains))
    return compute.evaluate_design_applicability(body,values,receipts)


@pytest.mark.parametrize('topology',[dict(tm_count=3,outside_length=300),
    dict(tm_count=1,outside_length=99),dict(tm_count=1,outside_length=100)])
def test_r57_first_three_membrane_conditions_route_to_wt(topology):
    gate=r57(topology,'high')
    assert gate['status']=='NOT_SUITABLE_FOR_DESIGN' and gate['route']=='WT_PATH_REVIEW'
    assert gate['design_skip_reason']=='membrane_expected_poor' and gate['basis']['is_membrane'] is True


def test_r57_enveloped_tm_cross_confirmation_and_explicit_membrane_confirmation():
    topology=dict(tm_count=1,outside_length=200);domains=[dict(type='TMhelix',start=100,end=120)]
    gate=r57(topology,'high',domains,pathogen_type='virus_enveloped')
    assert gate['status']=='NOT_SUITABLE_FOR_DESIGN'
    assert gate['basis']['r57_membrane_conditions']['enveloped_tm_cross_confirmed'] is True
    confirmed=r57(topology,'high',domains,pathogen_type='virus_enveloped',membrane_design_confirm=True)
    assert confirmed['status']=='SUITABLE_FOR_DESIGN' and confirmed['design_mode']=='EXTRACELLULAR_RESTRICTED'
    assert confirmed['constraints']==['EXTRACELLULAR_ONLY','TM_AND_INSIDE_FIXED']


def test_r57_optional_pathogen_null_does_not_trigger_fourth_condition_but_enveloped_needs_domains():
    topology=dict(tm_count=1,outside_length=200);tm=[dict(type='TMhelix',start=100,end=120)]
    unspecified=r57(topology,'high',tm)
    assert unspecified['status']=='SUITABLE_FOR_DESIGN'
    assert unspecified['basis']['r57_membrane_conditions']['enveloped_tm_cross_confirmed'] is False
    unknown_domains=r57(topology,'high',pathogen_type='virus_enveloped')
    assert unknown_domains['basis']['required_missing']==['FUNCTIONAL_DOMAINS']
    non_enveloped=r57(topology,'high',pathogen_type='virus_non_enveloped')
    assert non_enveloped['status']=='SUITABLE_FOR_DESIGN' and non_enveloped['basis']['is_membrane'] is False


def test_r57_low_confidence_is_definitive_and_confirmation_is_a_caveat():
    skipped=r57(None,'low')
    assert skipped['status']=='NOT_SUITABLE_FOR_DESIGN' and skipped['design_skip_reason']=='skipped_low_confidence'
    soluble=dict(tm_count=0,outside_length=500)
    confirmed=r57(soluble,'low',[],low_conf_design_confirm=True)
    assert confirmed['status']=='SUITABLE_FOR_DESIGN' and confirmed['design_mode']=='LOW_CONFIDENCE_CONFIRMED_REVIEW'
    assert confirmed['constraints']==['LOW_CONFIDENCE_RESULT_CAVEAT']
    assert confirmed['quality_flags']==['skipped_low_confidence']


def test_r57_combined_membrane_and_low_confidence_keeps_both_reasons():
    gate=r57(dict(tm_count=3,outside_length=300),'low')
    assert gate['design_skip_reason']=='membrane_expected_poor'
    assert {row['code'] for row in gate['decision_reasons']}=={
        'R57_MEMBRANE_DESIGN_CONFIRMATION_REQUIRED','R57_LOW_CONFIDENCE_DESIGN_CONFIRMATION_REQUIRED'}


def test_r57_high_confidence_soluble_route_is_business_only():
    gate=r57(dict(tm_count=0,outside_length=500),'high',[])
    assert gate['status']=='SUITABLE_FOR_DESIGN' and gate['suitable_for_design'] is True
    assert gate['design_mode']=='FULL_PROTEIN_REVIEW' and gate['scientific_release_status']=='CLOSED'
    assert gate['n11_release'] is False and gate['decision_reasons']==[]


@pytest.mark.parametrize('context',[{},
    dict(pathogen_type='fungus',membrane_design_confirm=False,low_conf_design_confirm=False),
    dict(pathogen_type=None,membrane_design_confirm=1,low_conf_design_confirm=False)])
def test_r57_context_is_exact_and_typed(context):
    with pytest.raises(RuntimeFault):policy.request(encode(request(design_context=context)))


def test_producer_slots_are_registered_and_wt_has_own_identity():
    from t01_phase1_real.development.registry import spec
    assert all(spec(tool).TOOL==tool for tool in policy.PRODUCERS.values())
    assert spec(policy.TOOL).NODE=='N18' and policy.TOOL not in policy.PRODUCERS.values()


@pytest.mark.parametrize('mutation',['signoff','profile','binding_hash','result_sequence','foreign_raw','failed_state'])
def test_registered_bytes_with_inconsistent_identity_or_qualification_still_rejected(tmp_path,mutation):
    rt=Runtime(tmp_path);up=run(rt,n10_request(),tool=n10.TOOL)
    ref=next(r for r in up['artifacts'] if r['role']=='result');value=rt.result(up['job_id'])
    if mutation=='signoff':value['scientific_signoff']={'reviewer':'unregistered'}
    elif mutation=='profile':value['binding']['execution_profile']['sha256']='0'*64
    elif mutation=='binding_hash':value['binding']['input_sha256']='0'*64
    elif mutation=='result_sequence':value['binding']['sequence_sha256']='0'*64
    elif mutation=='foreign_raw':value['raw_artifacts'][0]['artifact']['job_id']='t01p1r-job-'+'0'*32
    else:value['execution']['error_code']='TOOL_FAILED'
    raw=encode(value);ref.update(sha256=sha(raw),size_bytes=len(raw))
    with rt._tx() as db:
        row=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
        (rt.root/row['relative_path']).write_bytes(raw)
        db.execute('UPDATE artifacts SET data=? WHERE id=?',(encode(ref).decode(),ref['artifact_id']))
        db.execute('UPDATE jobs SET data=? WHERE id=?',(encode(up).decode(),up['job_id']))
    with pytest.raises(RuntimeFault):rt.submit_sequence(encode(bound(rt,up)),'reject',policy.TOOL)


def test_source_change_during_assembly_fails_closed(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);up=run(rt,n10_request(),tool=n10.TOOL);body=bound(rt,up)
    ref=body['upstream']['developability']['artifact']
    with rt._db() as db:row=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
    path=rt.root/row['relative_path'];original=service.evaluate
    def damage(body,files):
        value=original(body,files);path.write_bytes(path.read_bytes()+b' ');return value
    monkeypatch.setattr(service,'evaluate',damage)
    job=run(rt,body,'damage');assert job['state']=='failed'
    assert rt.result(job['job_id'])['draft'] is None
