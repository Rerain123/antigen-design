import copy
import pytest
from t01_phase1_real.common import RuntimeFault,encode
from t01_phase1_real.development.variant_report import m1
from t01_phase1_real.development.epitope_protection.compute import identity,rsa_delta


def row(n,score,excluded=True):
    return dict(id='sample-'+str(n),sample_number=n,sequence_sha256='a'*64,mutations=[{'position':2}],
        esm_if1=dict(esm_if1_score=score,passed=not excluded),disposition='EXCLUDED' if excluded else 'UNDETERMINED',
        exclusion_reasons=[dict(code='R35_DETERIORATION_EXCEEDED')] if excluded else [],n13=None,foldx=None,
        stability_source={'state':'missing'},missing_conditions=[dict(producer='variant S-40 / N10 components',reason='NOT_EXECUTED')])


def test_selection_prefers_not_excluded_but_never_imputes_missing_score():
    rows=[row(1,-1),row(2,-4,False),row(3,None,False),row(4,-2),row(5,-3)]
    assert m1.selection(rows)==[2,1,4]
    assert rows[0]['disposition']=='EXCLUDED' and rows[2]['esm_if1']['esm_if1_score'] is None


def test_all_excluded_debug_ranking_and_stable_id_ties():
    rows=[row(2,-2),row(10,-2),row(3,-3),row(4,None)]
    before=copy.deepcopy(rows)
    obs=dict(wt={},representatives=[dict(sample_number=10,sources={},results={},prediction={})])
    result=m1.ranking({'records':rows},{'input/m1-observations.json':encode(obs)})
    assert [r['candidate_id'] for r in result['records']]==['sample-10','sample-2','sample-3','sample-4']
    assert result['records'][0]['selected_for_recomputation']
    assert all(r['debug_only'] and not r['scientific_eligible'] for r in result['records'])
    assert result['records'][1]['recomputation_state']=='NOT_SELECTED_NOT_COMPUTED'
    assert result['records'][-1]['test_rank'] is None
    assert result['scientific_release_gate']=='CLOSED' and result['production_status']=='NOT_DEPLOYED'
    assert rows==before


@pytest.mark.parametrize('bad',[{}, {'wt':{},'representatives':[]}, {'wt':{},'representatives':[],'scores':[1]}])
def test_caller_scores_or_incomplete_m1_input_rejected(bad):
    with pytest.raises(RuntimeFault):m1.request(bad)


def test_empty_hotspots_do_not_pass_protection():
    assert identity('AC','AA',[])['scientific_pass'] is None
    assert identity('AC','AA',[])['value'] is None
    assert rsa_delta(None,None,[])['reason']=='EMPTY_VALIDATION_INTERVAL'
