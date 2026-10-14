"""Revision §17 engineering fixtures; no native predictions or scientific claims."""
import copy
import json
from pathlib import Path
import pytest
from t01_phase1_real.common import RuntimeFault,encode,sha
from t01_phase1_real.development.workflow import revision_contract as c,revision_sampling as s,revision_budget as b
from t01_phase1_real.development.workflow import revision_evaluation as e,revision_structure as st,revision_schema as schema


def fixture(length=214):
    cfg=c.suggested_config('fixture-v1');wt='A'*length
    perms=dict(non_standard=False,per_residue=[dict(position=p,wt_residue='A',design_permission='RESTRICTED',allowed_residues='AS',evidence_source=[])
        for p in range(1,length+1)])
    conv=dict(target_chain='A',chain_sequences={'A':wt},rows=[dict(sequence_position=p,designed_chain=True,
        tool_position=p,chain_id='A',author_resseq=str(p+41),insertion_code='A' if p==2 else '',residue='A') for p in range(1,length+1)])
    snap=s.snapshot(wt,perms,conv,{'artifact_id':'wt'},cfg)
    return cfg,snap,perms,conv


def receipt(snap,cfg,number,sequence=None,seed=None,**kw):
    return dict(receipt_id='receipt-'+str(number),draw_id='draw-'+str(number),batch_id='batch-'+str(seed or cfg['random_seeds'][0]),
        source_kind='sampling_draw',delivery_kind='ORIGINAL',execution_ref={'artifact_id':'native'},
        sequence=sequence or snap['original_wt_seq'],seed=seed or cfg['random_seeds'][0],condition_hash=sha(encode(snap)),**kw)


def candidate(number=1,mutations=1):
    cfg,snap,_,_=fixture()
    scales=json.loads((Path(__file__).parents[1]/'src/t01_phase1_real/development/design_backend/scales.json').read_bytes())
    records=s.formal(snap,[dict(sample_number=number,sequence='S'*mutations+'A'*(214-mutations))],list(range(1,15)),cfg,[],
                     dict(scales=scales,generation_ref={'artifact_id':'n11'}))
    return records[0]


@pytest.mark.parametrize('length,expected',[(214,14),(999,69),(9,0)])
def test_budget_denominator(length,expected):
    _,snap,_,_=fixture(length)
    assert snap['mutation_budget']['B']==expected
    assert snap['mutation_budget']['K']==expected


@pytest.mark.parametrize('key,value',[('design_site_fraction',float('nan')),('max_mutation_fraction',1.1),
    ('max_mutations_abs',True),('structure_eval_max',-1),('presampling_n',3),('max_tool_attempts',2)])
def test_invalid_configuration_not_truncated(key,value):
    cfg=c.suggested_config('fixture');cfg[key]=value
    with pytest.raises(RuntimeFault):c.config(cfg)


def test_empty_wt_and_unknown_contract():
    cfg=c.suggested_config('fixture')
    with pytest.raises(RuntimeFault):c.budget('',cfg,[])
    cfg['shared_contract_version']='old'
    with pytest.raises(RuntimeFault,match='contract_incompatible'):c.config(cfg)


def test_permissions_sampling_and_coordinate_identity():
    cfg,snap,perms,conv=fixture()
    perms['per_residue'][0].update(design_permission='FIXED',allowed_residues='A')
    snap=s.snapshot(snap['original_wt_seq'],perms,conv,{},cfg,[2])
    assert 1 not in snap['eligible_positions'] and 2 not in snap['eligible_positions']
    assert snap['records'][1]['design_permission']=='RESTRICTED'
    assert snap['records'][1]['position_key']['author_resseq']=='43'
    assert snap['records'][1]['position_key']['insertion_code']=='A'
    assert snap['records'][1]['position_key']['tool_position']==2
    mask=s.constraints(snap,[3,4]);assert 1 in mask['fixed_positions'] and 2 in mask['fixed_positions']
    assert mask['restricted_positions']==[dict(position=3,allowed_residues='AS'),dict(position=4,allowed_residues='AS')]
    conv['rows'][0]['residue']='S'
    with pytest.raises(RuntimeFault):s.snapshot('A'*214,perms,conv,{},cfg)


@pytest.mark.parametrize('count,expected',[(14,'PASS'),(15,'FAIL'),(0,'PASS')])
def test_independent_mutation_count(count,expected):
    cfg,snap,_,_=fixture()
    v=s.inspect(snap,'S'*count+'A'*(214-count),range(1,215))
    assert v['mutation_count']==count and v['check_status']==expected
    assert s.inspect(snap,'S'*214,range(1,215),proposal=True)['check_status']=='PASS'


def test_sampling_fixed_and_chemical_hard_checks():
    _,snap,_,_=fixture()
    assert s.inspect(snap,'S'+'A'*213,[])['check_status']=='FAIL'
    r=candidate();assert r['disposition']=='FORMAL_POOL'
    assert r['constraint_check']['per_mutation_chemical'][0]['hydrophobicity']==2.6
    assert candidate(mutations=15)['disposition']=='REJECTED'


def test_reference_real_wt_duplicates_and_replay():
    cfg,snap,_,_=fixture();changed='S'+'A'*213
    rows=[receipt(snap,cfg,1,changed),receipt(snap,cfg,2,changed),receipt(snap,cfg,3)]
    rows.append(dict(rows[0],receipt_id='replayed',delivery_kind='REPLAY'))
    rows.append(dict(rows[2],receipt_id='reference',source_kind='reference_record',draw_id=None))
    result=s.proposals(snap,rows,cfg)
    assert result['valid_count']==3 and result['unique_sequences']==2
    assert result['frequencies']['1']['mutation_frequency']==2/3
    assert len(result['replayed_receipts'])==1 and len(result['excluded_receipts'])==1


def test_conflicting_or_missing_draw_identity_quarantined():
    cfg,snap,_,_=fixture();row=receipt(snap,cfg,1)
    result=s.proposals(snap,[row,dict(row,receipt_id='conflict',sequence='S'+'A'*213),
        dict(row,receipt_id='missing',draw_id=None,sequence='!')],cfg)
    assert result['valid_count']==0 and result['frequencies'] is None
    assert len(result['quarantine_receipts'])==3
    assert result['quarantine_receipts'][0]['validity_status']=='INVALID'


def test_unequal_batch_sizes_weighted_by_draw_count():
    cfg,snap,_,_=fixture()
    rows=[receipt(snap,cfg,n,'S'+'A'*213) for n in range(12)]
    rows.append(receipt(snap,cfg,13,seed=cfg['random_seeds'][1]))
    result=s.proposals(snap,rows,cfg)
    assert result['frequencies']['1']['mutation_frequency']==12/13
    assert sorted(v['valid_count'] for v in result['batches'].values())==[1,12]
    assert s.proposals(snap,list(reversed(rows)),cfg)['nomination_positions']==result['nomination_positions']


def test_cross_round_unique_and_wt_control():
    cfg,snap,_,_=fixture();first=candidate();scales=json.loads((Path(__file__).parents[1]/'src/t01_phase1_real/development/design_backend/scales.json').read_bytes())
    records=s.formal(snap,[dict(sample_number=1,sequence=first['sequence']),dict(sample_number=2,sequence='A'*214)],
        list(range(1,15)),cfg,[first],dict(scales=scales,generation_ref={}))
    assert [r['disposition'] for r in records]==['DUPLICATE','WT_CONTROL']


def test_cheap_ranking_no_relaxation():
    a=candidate();d=candidate(2,2)
    scores={a['candidate_id']:dict(check_status='PASS',score=-1),d['candidate_id']:dict(check_status='PASS',score=-1)}
    assert s.select_structure([d,a],scores,1)==[a['candidate_id']]
    assert s.esm_check(-1.1,-1,1e-9)['check_status']=='PASS'
    assert s.esm_check(-1.10001,-1,1e-9)['check_status']=='FAIL'
    assert s.esm_check(-1,-1,None)['check_status']=='NOT_ASSESSED'


def scope():return {k:'original' if k=='evaluation_profile_id' else sha(b'a') if k=='content_hash' else k for k in c.SCOPE}


@pytest.mark.parametrize('states,expected',[(('PASS','NOT_ASSESSED'),'NOT_ASSESSED'),(('FAIL','NOT_ASSESSED'),'FAIL'),
    (('PASS','PASS'),'PASS'),(('NOT_APPLICABLE','NOT_APPLICABLE'),'NOT_APPLICABLE')])
def test_four_state_aggregate(states,expected):
    sc=scope();required=dict(required_check_ids=['esm','structure'],check_roles={'esm':'mandatory','structure':'mandatory'})
    summaries=[dict(sc,summary_id=k,check_id=k,check_status=v) for k,v in zip(required['required_check_ids'],states)]
    result=c.aggregate(sc,required,summaries)
    assert result['check_status']==expected and result['passed'] is {'PASS':True,'FAIL':False}.get(expected)
    assert c.aggregate(sc,None,summaries)['check_status']=='NOT_ASSESSED'


def test_association_error_does_not_erase_prior_failure():
    row=candidate();row['check_summaries']=[dict(check_status='FAIL')]
    receipt=dict(row,receipt_id='bad',attempt_id='attempt',content_hash=sha(b'wrong'),input_artifact_refs=[])
    result=c.attach(row,receipt,{}, {})
    assert result['check_summaries']==row['check_summaries'] and result['sequence']==row['sequence']
    assert result['association_errors'][0]['reason_codes']==['association_error']
    with pytest.raises(RuntimeFault):c.validate_references(dict(selected_attempt_ids=['artifact'],selected_artifact_refs=[]),{}, {'artifact':{}})
    assert c.validate_references(dict(selected_attempt_ids=[],selected_artifact_refs=[dict(artifact_id='artifact',content_hash=sha(b'x'))]),{},
        {'artifact':dict(content_hash=sha(b'x'))})['selected_attempt_ids']==[]


def test_budget_persistence_multi_engine_and_no_double_replay():
    cfg=c.suggested_config('fixture');cfg['structure_eval_max']=1;ledger=b.new(cfg)
    assert b.reserve(ledger,cfg,'af3','structure',['same'])
    assert b.reserve(ledger,cfg,'esmfold','structure',['same'])
    saved=json.loads(json.dumps(ledger));assert b.reserve(saved,cfg,'af3','structure',['same'])
    assert not b.reserve(saved,cfg,'another','structure',['different'])
    for name in ('af3','esmfold'):
        b.observe(saved,name,dict(attempt_id=name,execution_status='ERROR',execution_seconds=1.,queue_seconds=2.,internal_runs=1))
    report=b.summary(saved,cfg)['structure']
    assert report['unique_objects']==1 and report['attempts']==report['failed_attempts']==2
    assert report['execution_seconds']==2 and report['time_limit_status']=='NOT_APPLICABLE'
    assert b.retry_reason(system_errors=[],budget_available=False,designable=True,original_pass=False,round_index=0)=='budget_exhausted'


def test_structure_route_and_atomic_calls():
    assert st.route(19,5)==['af3'];assert st.route(214,14)==['af3','esmfold2'];assert st.route(50,6)==['esmfold2']
    cfg=c.suggested_config('fixture');cfg['call_limits']['structure']=1;ledger=b.new(cfg)
    assert not st.reserve_engines(ledger,cfg,dict(candidate_id='c',content_hash='hash',engines=['af3','esmfold2']),'round')
    assert not ledger['reservations']


def test_empty_pool_does_not_dispatch_and_missing_policy_not_top20():
    empty=e.foldx_pool([],None,20,mode='variant_score',task_id='task')
    assert empty['execution_status']=='NOT_RUN' and empty['reason_codes']==['SKIPPED_EMPTY']
    assert e.foldx_pool([candidate()],None,20,mode='variant_score',task_id='task')['reason_codes']==['configuration_incomplete']
    rejected=candidate(mutations=15)
    assert e.foldx_pool([rejected],None,20,mode='variant_score',task_id='task')['reason_codes']==['SKIPPED_EMPTY']


@pytest.mark.parametrize('count,state',[(0,'NOT_RUN'),(1,'PARTIAL'),(5,'SUCCEEDED')])
def test_repetition_states_and_sample_std(count,state):
    rows=[dict(repeat_id=str(i),execution_status='SUCCEEDED',verified=True,value=float(i)) for i in range(count)]
    result=e.repeats(5,rows);assert result['execution_status']==state
    if count<2:assert result['std'] is None
    if count==0:assert result['mean'] is None
    if count==5:assert result['std']==pytest.approx(1.5811388300841898)
    assert e.repeats(5,[dict(repeat_id='f',execution_status='ERROR',verified=False,value=None)])['execution_status']=='ERROR'


def score_context():
    return dict(score_context_id='context',dimensions=['solubility','aggregation'],calculation_modes={'solubility':'sequence','aggregation':'structure'},
        normalization={'solubility':'v1','aggregation':'v1'},weights={'solubility':1,'aggregation':1},missing_policy='require_all',formula_version='weighted-normalized-mean-v1')


def test_scoring_context_missing_does_not_gain_advantage():
    context=score_context();values={k:dict(normalized=.4,reliable=True,mode=v,normalization='v1') for k,v in context['calculation_modes'].items()}
    assert e.score(values,context)['value']==.4
    values['extra']=dict(normalized=1,reliable=True)
    assert e.score(values,context)['value']==.4
    values['aggregation']['mode']='sequence';assert e.score(values,context)['value'] is None
    assert e.axes(None,None,None,None,None,14)==dict(dev=None,stab=None,epi=None,burden=None)


def test_acceptance_formal_and_provisional_negative_paths():
    policy=dict(score_context(),acceptance_config_id='a',required_check_ids=['s28'],threshold=.3,threshold_status='pending_calibration',rule_version='r')
    result=e.acceptance('PASS',True,dict(value=.2,score_context_id='context'),policy,applicable=True)
    assert result['acceptance_status']=='NOT_ASSESSED' and result['provisional_acceptance_status']=='FAIL'
    policy.update(threshold_status='calibrated',calibration_evidence_ref='fixture-only')
    assert e.acceptance('PASS',True,dict(value=.2,score_context_id='context'),policy,applicable=True)['acceptance_status']=='FAIL'
    assert e.acceptance('FAIL',False,dict(value=None),None)['acceptance_status']=='FAIL'
    assert e.task_acceptance(['FAIL','NOT_ASSESSED'],True)=='NOT_ASSESSED'
    assert e.task_acceptance([],True)=='NOT_ASSESSED'


def test_profile_group_independence_and_no_identity_dedup():
    rows=[]
    for n in range(1,8):
        row=candidate(n,n)
        row.update(axes=dict(dev=.4,stab=None,epi=None,burden=.9),evaluation_profile_id='original',evidence_group='C',
                   score_context_id='context',calculation_mode='sequence',family='same')
        rows.append(row)
    result=e.rank_groups(rows,dict(score_policy_version='fixture',weights=dict(dev=.5,burden=.1)))
    assert len(result['groups'][0]['selected'])==7 and result['global_rank'] is None
    assert all(r['rank'] is None for r in result['groups'][0]['records'])
    assert e.evidence_group('original','FAIL',False,False)=='E'
    assert e.evidence_group('relaxed','PASS',True,True)=='B'


def test_schema_and_boolean_compatibility():
    schema.validate(c.check('NOT_ASSESSED'),kind='check')
    with pytest.raises(RuntimeFault):schema.validate(dict(c.check('NOT_ASSESSED'),passed=True),kind='check')
