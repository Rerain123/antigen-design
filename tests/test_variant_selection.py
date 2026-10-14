"""Synthetic contract cases for backend selection; no scientific run evidence."""
import copy
import pytest
from t01_phase1_real.common import encode, decode
from t01_phase1_real.development.variant_report.selection import evaluate, protection, diversity
from t01_phase1_real.service_api.user_report import render


def fixture():
    row=dict(id='sample-1',sample_number=1,sequence='KAAA',sequence_sha256='test-only',
        mutations=[dict(position=1,wt='A',mut='K')],non_standard=False,exclusion_reasons=[],
        engineering_hard_filter={'flags':dict(constraint_override=False,burden_exceeded=False)},
        burden={'values':{'count':1}},foldx=None,s28_validation={'passed':True,'reason':'S28_PASSED'},
        n13={'observation':dict(hotspot_positions=[],validation_positions=[])})
    components=dict(developability={'dimension_weights':dict(solubility=1,aggregation=0,ph_stability=0,
        tag_exposure=0,expressibility=0,stability_ddg=0)},
        solubility=dict(reliable=True,status='computed_unreviewed',global_score=1.2),
        aggregation=dict(reliable=False,status='unavailable',global_score=None,reason_code='NOT_RUN'),
        expressibility=dict(status='computed_unreviewed',score=.8),
        ph_stability=dict(status='unavailable',reliable=False,dg_curve=None,reason_code='NOT_RUN'),
        tag_exposure=dict(status='unavailable',reliable=False,n_term=None,reason_code='NOT_RUN'))
    obs={'representatives':[dict(sample_number=1,sources={'fixture':'SYNTHETIC_ONLY'},
        results={'developability':components})]}
    files={'input/design_audit-request.json':encode({'objective':'general'}),'input/m1-observations.json':encode(obs)}
    audit={'permissions':{'per_residue':[dict(position=1,constraint_state='RESTRICTED')]}}
    return row,components,obs,files,audit


def run(row,obs,files,audit):
    files=dict(files,**{'input/m1-observations.json':encode(obs)})
    return evaluate({},files,[row],audit)


def test_backend_chain_computes_reference_only_with_provenance():
    row,dev,obs,files,audit=fixture(); before=copy.deepcopy((row,obs,audit))
    result=run(row,obs,files,audit)
    assert decode(encode(result))==result  # Publication replays exact JSON facts.
    assert result['top20']==['sample-1'] and result['computed'][0]['score']==pytest.approx(.9316666666666666)
    assert result['computed'][0]['family']=='charge_tuning'
    assert result['inventory'][0]['recomputation_sources']=={'fixture':'SYNTHETIC_ONLY'}
    assert result['sc10']['overall_pass'] is True and result['sc10']['formal_pass'] is None
    assert not result['usable_for_pipeline'] and not result['formal_ranking_changed']
    assert (row,obs,audit)==before


@pytest.mark.parametrize('fault',['overall','s28','burden','permissions','objective','n13'])
def test_missing_inputs_never_produce_a_reference_rank(fault):
    row,dev,obs,files,audit=fixture()
    if fault=='overall':dev['solubility'].update(reliable=False,reason_code='CAMSOL_INCOMPLETE')
    if fault=='s28':row['s28_validation']['passed']=None
    if fault=='burden':row['engineering_hard_filter']['flags']['burden_exceeded']=None
    if fault=='permissions':audit['permissions']['per_residue']=[]
    if fault=='objective':files.pop('input/design_audit-request.json')
    if fault=='n13':row['n13']=None
    result=run(row,obs,files,audit)
    assert result['top20']==[] and result['inventory'][0]['state']=='UNDETERMINED'
    assert result['sc10']['overall_pass'] is None


def test_exclusion_and_non_standard_not_rehabilitated_by_high_score():
    row,dev,obs,files,audit=fixture();row['non_standard']=True
    row['exclusion_reasons']=[dict(code='R35_DETERIORATION_EXCEEDED')]
    result=run(row,obs,files,audit)
    assert result['status']=='ALL_EXCLUDED' and not result['computed']
    assert set(result['inventory'][0]['exclusion_reasons'])=={'R35_DETERIORATION_EXCEEDED','NON_STANDARD_CONSTRAINT_OVERRIDE'}


def structured():
    return dict(hotspot_positions=[1],validation_positions=[1],l1={'value':True},
        l2={'engineering_threshold_pass':True},l3={'hotspot':{'engineering_threshold_pass':True},
        'functional_rmsd':1.,'functional_reason':None},l4={'engineering_threshold_pass':False})


def test_l4_penalty_or_soft_mutation_is_applied_once():
    row,dev,obs,files,audit=fixture();row['n13']['observation']=structured()
    audit['permissions']['per_residue'][0]['constraint_state']='SOFT'
    result=run(row,obs,files,audit)
    assert result['computed'][0]['score']==pytest.approx(.7416666666666667)
    row['n13']['observation']['l4']={}
    result=run(row,obs,files,audit)
    assert 'L4_UNAVAILABLE_TREATED_PASS_FOR_RANKING_ONLY' in result['inventory'][0]['warnings']
    assert result['computed'][0]['score']==pytest.approx(.8316666666666667)


def test_n13_failed_layer_excludes_even_if_other_layers_unknown():
    row,dev,obs,files,audit=fixture();o=structured();row['n13']['observation']=o
    o['l2']={};o['l1']['value']=False
    assert run(row,obs,files,audit)['inventory'][0]['state']=='EXCLUDED'
    o['l1']['value']=True
    result=run(row,obs,files,audit)
    assert result['inventory'][0]['state']=='RANKABLE'
    assert 'L2_UNAVAILABLE_OMITTED_FROM_AND_DEGRADED_VALIDATION' in result['inventory'][0]['warnings']
    o['l3']['hotspot']={}
    assert run(row,obs,files,audit)['inventory'][0]['state']=='UNDETERMINED'


def test_no_hotspot_does_not_erase_e4_and_no_structure_neutral_is_explicit():
    row,_,_,_,_=fixture();o=structured();row['n13']['observation']=o
    o['hotspot_positions']=[];o['l1']['value']=None;o['l3']['hotspot']['engineering_threshold_pass']=False
    assert protection(row)['structural'] is False
    row['n13']=None;row['s28_validation'].update(reason='S28_PREDICTION_FAILED_RETAIN_R35')
    assert protection(row)['norm']==1.
    row['s28_validation']['passed']=None
    assert protection(row)['norm'] is None


def test_s40_backfills_ddg_and_sc10_checks_overall_not_weighted_score():
    row,dev,obs,files,audit=fixture();dev['solubility']['global_score']=-.804
    result=run(row,obs,files,audit)
    assert result['computed'][0]['score']>.3 and result['sc10']['overall_pass'] is False
    assert result['sc10']['action']=='WT_FALLBACK_BELOW_THRESHOLD'
    dev['solubility']['global_score']=-.8
    assert run(row,obs,files,audit)['sc10']['overall_pass'] is True
    dev['developability']['dimension_weights']['stability_ddg']=1
    row['foldx']={'ddg_foldx':-2.}
    result=run(row,obs,files,audit)
    assert result['inventory'][0]['developability']['stability_ddg']==-2.
    assert result['computed'][0]['overall']==pytest.approx((.3+1/(1+__import__('math').exp(-1)))/2)


def test_diversity_strict_identity_boundary_family_rotation_and_quota():
    ranked=[dict(id='a',family='charge_tuning'),dict(id='duplicate',family='charge_tuning'),
            dict(id='boundary',family='charge_tuning'),dict(id='different',family='mixed')]
    seqs={'a':'A'*20,'duplicate':'A'*20,'boundary':'C'+'A'*19,'different':'D'*20}
    result=diversity(ranked,seqs)
    assert result['ids']==['a','different','boundary']
    assert result['rejected'][0]['id']=='duplicate'
    result=diversity([dict(id=a,family='mixed') for a in 'ACDEFGH'],{a:a*20 for a in 'ACDEFGH'})
    assert len(result['ids'])==5 and all(r['reason']=='FAMILY_QUOTA' for r in result['rejected'])


def test_html_discloses_missing_and_threshold_failure():
    row,dev,obs,files,audit=fixture();dev['solubility']['global_score']=-1.
    result=run(row,obs,files,audit)
    html=render({'variant_report':{'engineering_selection':result}}).decode()
    assert '综合筛选参考' in html and '低于 0.30' in html and '不自动交接' in html
    dev['solubility'].update(reliable=False,reason_code='CAMSOL_INCOMPLETE')
    html=render({'variant_report':{'engineering_selection':run(row,obs,files,audit)}}).decode()
    assert '可开发性总分尚未取得' in html and '不补分、不生成排名' in html


@pytest.mark.parametrize('objective',['general','solubility','thermostability'])
def test_pareto_then_objective_and_stable_inventory_tie_order(objective):
    row,dev,obs,files,audit=fixture()
    rows=[];representatives=[]
    for i,(seq,overall,ddg,count) in enumerate([('KAAA',.8,2.,1),('CAAA',.6,-2.,1),('DAAA',.5,3.,2),('EAAA',.8,2.,1)],1):
        r=copy.deepcopy(row);r.update(id='sample-'+str(i),sample_number=i,sequence=seq,foldx={'ddg_foldx':ddg})
        r['burden']['values']['count']=count;rows.append(r)
        rep=copy.deepcopy(obs['representatives'][0]);rep['sample_number']=i
        rep['results']['developability']['solubility']['global_score']=overall*4-2
        representatives.append(rep)
    files['input/m1-observations.json']=encode({'representatives':representatives})
    files['input/design_audit-request.json']=encode({'objective':objective})
    result=evaluate({},files,rows,audit)
    assert result['pareto_ids']==['sample-1','sample-2','sample-4']
    assert result['ranked_front'][0]==('sample-2' if objective=='thermostability' else 'sample-1')
    assert result['ranked_front'].index('sample-1')<result['ranked_front'].index('sample-4')
