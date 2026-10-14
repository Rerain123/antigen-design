"""Expert v2 boundaries. All numeric examples are engineering fixtures."""
import copy
import pytest
from t01_phase1_real.common import RuntimeFault
from t01_phase1_real.development.workflow import revision_v2 as v,revision_contract as c
from test_expert_revision_core import fixture


def record(count=1):
    return dict(sequence='S'*count+'A'*(100-count),mutations=[dict(position=i+1,wt='A',mut='S') for i in range(count)],
        candidate_id='candidate',content_hash='a'*64,reference_id='wt',calculation_config_id='fixture',rule_version=v.RULE,
        disposition='FORMAL_POOL',constraint_check=c.check('PASS'),esm_if1=c.check('PASS'),ranking_context={},budget_B=7)


def observation(q):return dict(c.check('PASS' if q>=.5 else 'FAIL'),plddt=q,structure={'fixture':True})


@pytest.mark.parametrize('baseline,score,status',[(-.0099,-.0099,'NOT_ASSESSED'),(-.01,-.011,'PASS'),(-.01,-.01101,'FAIL'),(.01,.009,'PASS'),(0,0,'NOT_ASSESSED')])
def test_esm_decimal_boundaries(baseline,score,status):assert v.esm(score,baseline)['check_status']==status


@pytest.mark.parametrize('count,a,b,status,selected',[(6,.2,.8,'FAIL','af3'),(6,.8,.2,'PASS','af3'),(6,None,.8,'PASS','esmfold2'),(1,None,.8,'NOT_ASSESSED',None),(11,None,.8,'NOT_ASSESSED',None)])
def test_primary_failure_never_selects_passing_secondary(count,a,b,status,selected):
    obs={'esmfold2':observation(b)}
    if a is not None:obs['af3']=observation(a)
    result=v.supplier(record(count),obs)
    assert result['check_status']==status and result['selected']==selected


def test_s28_advisory_geometry_and_known_failure_priority():
    r=record();r['geometry_check']=c.check('FAIL')
    v.s28(r,{'af3':observation(.8)},v.config('fixture'))
    assert r['validation']['check_status']=='PASS'
    v.s28(r,{'af3':observation(.8)},v.config('fixture',geometry='legacy_hard'))
    assert r['validation']['check_status']=='FAIL'
    r['constraint_check']=c.check('FAIL','PERMISSION_VIOLATION')
    v.s28(r,{},v.config('fixture'))
    assert r['validation']['check_status']=='FAIL' and r['checks']['chk_struct_quality']=='NOT_ASSESSED'


def side():
    coords={str(i+1):dict(atoms={'CA':p}) for i,p in enumerate(([0,0,0],[1,0,0],[0,1,0],[1,1,0]))}
    return dict(hotspots=[dict(start=1,end=3)],e4_positions=[],iedb_prior=dict(e4_status='not_applicable'),
        domains=[],quality_condition=True,rsa=[.5]*100,geometry=coords)


def test_permission_l1_preserves_literal_identity_and_exact_local_fit():
    _,snap,_,_=fixture(100);w=side();r=record()
    p=v.protection('A'*100,r,snap,w,copy.deepcopy(w))
    assert p['passed'] is True and p['l1_identity_pass'] is False and p['new_l1_pass_legacy_identity_fail']
    assert p['l3']['objects'][0]['observation']['fit_positions']==[1,2,3]
    assert p['auxiliary_geometry_status']['check_status']=='NOT_APPLICABLE'
    broken=copy.deepcopy(w);del broken['geometry']['2']
    p=v.protection('A'*100,r,snap,w,broken)
    assert p['check_status']=='NOT_ASSESSED' and p['l3']['max_rmsd'] is None


def test_empty_targets_are_not_complete_protection():
    _,snap,_,_=fixture(100);w=side();w['hotspots']=[]
    p=v.protection('A'*100,record(),snap,w,w)
    assert p['check_status']=='NOT_APPLICABLE' and p['structural_preservation'] is None
    w['hotspots']=None
    assert v.protection('A'*100,record(),snap,w,w)['check_status']=='NOT_ASSESSED'


def empty_scored():
    r,f=scored();_,snap,_,_=fixture(100);w=side();w['hotspots']=[]
    r['protection']=v.protection('A'*100,r,snap,w,w)
    r['l4']=v.l4(None,None,r['protection'],[],profiles_match=False)
    v.score_record(r,f,v.config('fixture'))
    return r,f


def test_evidence_backed_not_applicable_enters_foldx_but_stays_reference():
    r,_=empty_scored()
    assert r['l4']['check_status']=='NOT_APPLICABLE' and r['l4']['prediction_preservation'] is None
    assert v.select([r],20,foldx=True)['selected_candidate_ids']==['candidate']
    assert r['evidence_group']=='C' and not r['final_evidence_complete']
    assert r['axes']['epi'] is None and r['acceptance_score'] is None
    assert r['provisional_acceptance_status']=='NOT_ASSESSED'


@pytest.mark.parametrize('damage',['no_proof','unknown','scope','foreign','changed_proof','l1_fail','domain_fail','domain_unknown','s28_fail','l4_missing'])
def test_not_applicable_never_bypasses_missing_evidence_or_hard_failure(damage):
    r,f=empty_scored();p=r['protection']
    if damage=='no_proof':p.pop('applicability_evidence')
    elif damage=='unknown':p['target_availability']='UNKNOWN'
    elif damage=='scope':p['target_scope_id']='foreign'
    elif damage=='foreign':r['candidate_id']='foreign'
    elif damage=='changed_proof':p['applicability_evidence']['e4_status']='partial'
    elif damage=='l1_fail':p['l1']=c.check('FAIL')
    elif damage=='domain_fail':p['auxiliary_geometry_status']=c.check('FAIL')
    elif damage=='domain_unknown':p['auxiliary_geometry_status']=c.check('NOT_ASSESSED')
    elif damage=='s28_fail':r['validation']=c.check('FAIL')
    else:r['l4']=dict(c.check('NOT_ASSESSED'),prediction_preservation=None)
    v.score_record(r,f,v.config('fixture'))
    assert v.select([r],20,foldx=True)['selected_candidate_ids']==[]


@pytest.mark.parametrize('status',[None,'unavailable','partial'])
def test_empty_hotspots_without_complete_e4_inventory_are_not_nap(status):
    _,snap,_,_=fixture(100);w=side();w['hotspots']=[]
    w['iedb_prior']=None if status is None else dict(e4_status=status)
    p=v.protection('A'*100,record(),snap,w,w)
    assert p['check_status']=='NOT_ASSESSED' and not v.confirmed_empty(p)
    assert v.l4(None,None,p,[])['check_status']=='NOT_ASSESSED'


def test_old_selection_policy_is_not_silently_reinterpreted():
    cfg=v.config('old')
    for stage in ('l4','foldx_pool'):
        cfg['policies'][stage]['selection_rule_id']='v2-stage-complete-dimension-group-dev-roundrobin-id-v1'
    with pytest.raises(RuntimeFault,match='contract_incompatible'):c.config(cfg)


@pytest.mark.parametrize('span,change,status',[(.0499,0,'NOT_ASSESSED'),(.05,.0099,'PASS'),(.05,.01,'FAIL')])
def test_l4_span_and_strict_delta_boundary(span,change,status):
    p=dict(target_positions=[1],target_availability='COMPLETE')
    result=v.l4([0,span],[change,span],p,[])
    assert result['check_status']==status


def scored(missing=False,soft=False):
    r=record();dims={'expressibility':dict(reliable=True,normalized_score=.6,source='fixture',value={})}
    frozen=v.freeze(dims,{'fixture':True});r.update(validation=c.check('PASS'),developability_dimensions={} if missing else dims,
        protection=dict(c.check('PASS'),structural_preservation=True,auxiliary_geometry_status=c.check('NOT_APPLICABLE')),
        l4=dict(c.check('FAIL' if soft else 'PASS'),prediction_preservation=not soft),
        foldx=dict(execution_status='SUCCEEDED',valid_count=5,mean=-2))
    v.score_record(r,frozen,v.config('fixture'));return r,frozen


def test_fixed_dimensions_missing_remain_unknown_and_no_calibrated_acceptance():
    r,f=scored(True)
    assert r['acceptance_score'] is None and r['provisional_acceptance_status']=='NOT_ASSESSED'
    assert r['missing_frozen_dimensions']==['expressibility'] and f['M0']==['expressibility']
    r,f=scored();assert r['provisional_acceptance_status']=='PASS' and r['acceptance_status']=='NOT_ASSESSED'
    assert f['dimension_set_id']!=f['acceptance_dimension_set_id']


def test_soft_l4_enters_foldx_but_penalty_is_once_and_no_global_rank():
    r,f=scored(soft=True)
    passing,_=scored()
    assert r['score_context_id']==passing['score_context_id']  # Outcomes do not split comparable groups.
    assert v.select([r],20,foldx=True)['selected_candidate_ids']==['candidate']
    ranked=v.rank([r],v.config('fixture'))
    assert ranked['global_rank'] is None and r['penalty']==.1
    assert r['comparison_score']==pytest.approx(r['unpenalized_score']-.1)
    assert r['axes']['epi']==pytest.approx(1/1.3)
    r['l4']['prediction_preservation']=None
    assert v.select([r],20,foldx=True)['selected_candidate_ids']==[]


def test_policy_version_and_undeclared_calibration_rejected():
    cfg=v.config('fixture');assert c.config(cfg)==cfg
    cfg['policies']['acceptance']['threshold_status']='calibrated'
    with pytest.raises(RuntimeFault):c.config(cfg)


def test_partial_e4_does_not_become_complete_and_known_failure_survives():
    _,snap,_,_=fixture(100);w=side();w['iedb_prior']['e4_status']='partial'
    r=record();p=v.protection('A'*100,r,snap,w,w)
    assert p['check_status']=='NOT_ASSESSED' and p['target_availability']=='UNKNOWN'
    snap['records'][0].update(design_permission='FIXED',allowed_residues='A')
    assert v.protection('A'*100,r,snap,w,w)['check_status']=='FAIL'


def test_group_budget_twenty_unique_and_family_roundrobin_fill():
    rows=[]
    for i in range(25):
        r,_=scored();r.update(candidate_id=f'c{i:02}',content_hash=f'{i:064x}',family='first' if i<12 else 'second')
        r['mutations']=[dict(position=i+1,wt='A',mut='S')];rows.append(r)
    selected=v.select(rows,20,foldx=True)
    assert len(selected['selected_candidate_ids'])==20 and len(selected['not_selected_for_budget'])==5
    assert v.select(list(reversed(rows)),20,foldx=True)==selected
    ranked=v.rank(rows,v.config('fixture'))['groups'][0]
    assert [r['family'] for r in ranked['selected'][:10]]==['first','second']*5
    assert len(ranked['selected'])==20  # Quota does not permanently reject remaining sequences.


def test_score_modes_and_frozen_weights_do_not_silently_change():
    r,f=scored();f['weights']['expressibility']=0
    v.score_record(r,f,v.config('fixture'));assert r['axes']['dev'] is None
    r,f=scored();r['developability_dimensions']['expressibility']['value']['mode']='different'
    v.score_record(r,f,v.config('fixture'))
    assert r['acceptance_score'] is None and r['missing_frozen_dimensions']==['expressibility']


def test_v1_budget_checkpoint_shape_unchanged():
    from t01_phase1_real.development.workflow import revision_budget as b
    cfg=c.suggested_config('fixture')
    assert set(b.summary(b.new(cfg),cfg))=={'proposal','formal','esm_if1','structure','l4','foldx'}
    cfg['call_limits']['analysis']=1
    with pytest.raises(RuntimeFault):c.config(cfg)
    cfg=v.config('fixture');cfg['call_limits']['analysis']=1
    assert c.config(cfg)==cfg and 'analysis' in b.summary(b.new(cfg),cfg)
