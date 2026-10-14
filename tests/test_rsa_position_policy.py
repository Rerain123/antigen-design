"""Full required-position coverage, preserved raw observations and historical replay."""
import copy

import pytest

from t01_phase1_real.common import decode, encode, sha
from t01_phase1_real.development.structure.normalization import normalize, position_result, consumable_positions
from t01_phase1_real.development.structure.result import result
from t01_phase1_real.development.epitope_protection.compute import rsa_delta, geometry
from t01_phase1_real.development.developability.compute import tag_exposure, summarize, expressibility
from test_structure_development import join_fixture, actual
from test_developability_development import structure, request


def rsa(raw):
    return dict(raw_normalized_ratios=raw,position_result=position_result(raw),development_result=None,
                status='output_invalid',out_of_domain=[dict(sequence_position=i,residue='A',raw_ratio=x)
                    for i,x in enumerate(raw,1) if x is not None and x>1])


def test_raw_areas_and_outliers_are_preserved_and_missing_chain_mean_stays_null():
    m,r,a,t=join_fixture();a[0]['absolute_sasa_a2']=106.97167114774169
    old=normalize(m,r,a,t);new=normalize(m,r,a,t,per_position=True)
    assert {k:v for k,v in new.items() if k!='position_result'}==old
    assert consumable_positions(new)==[None,None,.2]
    assert new['position_result']['position_status']==['out_of_domain','missing','valid']
    assert new['position_result']['buried_fraction'] is None
    assert new['raw_normalized_ratios'][0]>1 and new['development_result'] is None
    a[0]['absolute_sasa_a2']=10
    partial=normalize(m,r,a,t,per_position=True)
    assert partial['development_result']['buried_fraction'] is None
    assert normalize(m,r,a,t)['development_result']['buried_fraction']==1/3


@pytest.mark.parametrize('bad',[1.0000000001,1.0697167114774169,None])
def test_required_set_is_complete_or_unassessed_without_subset_averaging(bad):
    a=consumable_positions(rsa([bad,.5,.6,.7]));b=consumable_positions(rsa([.1,.6,.7,.8]))
    good=rsa_delta(a,b,[2,3,4]);blocked=rsa_delta(a,b,[1,2,3,4])
    assert good['value']==pytest.approx(.1) and len(good['residues'])==3
    assert blocked['value'] is None and blocked['missing_position']==1
    assert 'residues' not in blocked


@pytest.mark.parametrize('damage',['policy','mask','value','positions','complete','length'])
def test_forged_position_result_is_rejected(damage):
    fact=rsa([1.2,.4,.5]);p=fact['position_result']
    if damage=='policy':p['policy']='allow_everything'
    elif damage=='mask':p['position_status'][0]='valid'
    elif damage=='value':p['per_residue'][0]=1.
    elif damage=='positions':p['valid_positions'].insert(0,1)
    elif damage=='complete':p['complete']=True
    else:p['per_residue'].pop()
    with pytest.raises(ValueError):consumable_positions(fact)


def test_legacy_result_is_not_reinterpreted_and_valid_endpoints_are_not_clipped():
    old=dict(raw_normalized_ratios=[1.2,.4],development_result=None)
    assert consumable_positions(old) is None
    fact=rsa([0.,1.,.3]);assert consumable_positions(fact)==[0.,1.,.3]
    assert fact['position_result']['buried_fraction']==1/3
    assert fact['position_result']['scientific_signoff'] is None


def test_invalid_rsa_does_not_prevent_independent_local_geometry():
    points={'1':dict(atoms=dict(CA=[0.,0.,0.])), '2':dict(atoms=dict(CA=[1.,0.,0.])),
            '3':dict(atoms=dict(CA=[0.,1.,0.]))}
    assert rsa_delta(consumable_positions(rsa([1.2,.4,.5])),[.2,.4,.5],[1,2,3])['value'] is None
    assert geometry(points,copy.deepcopy(points),[1,2,3])['rmsd']==pytest.approx(0.,abs=1e-12)


@pytest.mark.parametrize('invalid_position',[1,15,30])
def test_terminal_means_require_all_ten_positions_but_not_the_entire_chain(invalid_position):
    values=[.5]*30;values[invalid_position-1]=1.2
    source=structure(values);source['analysis']['rsa']=rsa(values)
    tag=tag_exposure(source)
    if invalid_position==15:
        assert tag['n_term']['mean_rsa']==tag['c_term']['mean_rsa']==.5
    else:
        affected='n_term' if invalid_position==1 else 'c_term'
        other='c_term' if invalid_position==1 else 'n_term'
        assert tag[affected] is None and tag[other]['mean_rsa']==.5
        assert tag['unavailable_positions'][affected]==[invalid_position]
        assert tag['preferred_end'] is None and not tag['reliable']
        ph=dict(status='unavailable',reliable=False,reason_code='MISSING',dg_curve=None,stable_range=None)
        summary=summarize(request(),expressibility('A'*30),tag,ph)
        dimension=summary['dimensions']['tag_exposure']
        assert dimension['value'][other]['mean_rsa']==.5
        assert dimension['normalized_score'] is None and not dimension['included_in_overall']


@pytest.mark.parametrize('tamper',[False,True])
def test_result_recomputes_position_validity_from_native_areas(actual,tamper):
    job,body,files,execution=actual
    original=result(job,body,files,copy.deepcopy(execution))
    assert original['analysis'] is not None and 'position_result' not in original['analysis']['rsa']
    report=decode(files['output/result/analysis.json'])
    from t01_phase1_real.development.structure.policy import PROFILE
    value=normalize(report['mapping'],decode(files['output/result/raw_addresses.json'])['residues'],
        decode(files['output/result/raw_residue_areas.json'])['residues'],
        decode(PROFILE.read_bytes())['normalization']['max_asa_a2'],per_position=True)
    if tamper:value['position_result']['per_residue'][0]=.999
    report['rsa']=value;files['output/result/analysis.json']=encode(report)
    files['output/result/rsa.json']=encode(dict(value,binding=report['binding']))
    runtime=decode(files['output/runtime.json'])
    runtime['native_output_sha256']={n[len('output/'):]:sha(raw) for n,raw in files.items() if n.startswith('output/result/')}
    files['output/runtime.json']=encode(runtime)
    checked=result(job,body,files,execution)
    assert (checked['analysis'] is None)==tamper


def test_report_describes_local_scope_without_rewriting_old_result():
    from t01_phase1_real.service_api.native_report import structure_blockers
    fact=rsa([1.2,.4]);snapshot=copy.deepcopy(fact)
    assert '该位置' in structure_blockers(dict(rsa=fact))[0][2]
    del fact['position_result']
    assert '归一化结果不可消费' in structure_blockers(dict(rsa=fact))[0][2]
    assert fact=={k:v for k,v in snapshot.items() if k!='position_result'}
