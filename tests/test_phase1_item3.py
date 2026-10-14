"""Expert-defined N10 terms, missing-dimension semantics and source isolation."""
import math

import pytest

from t01_phase1_real.common import RuntimeFault
from t01_phase1_real.development.developability import camsol
from t01_phase1_real.development.developability.compute import summarize
from t01_phase1_real.development.developability.service import sources


def test_c44_hand_reference_and_boundary_denominators():
    params=camsol.parameters()
    assert camsol.intrinsic_terms('A',params)['eq1_raw']==pytest.approx([.96018],abs=.00001)
    value=camsol.intrinsic_terms('ADK',params)
    assert value['eq2_smoothing_term']==pytest.approx([sum(value['eq1_raw'])/3]*3)
    assert value['eq3_gatekeeper'][0]==pytest.approx(-math.exp(-1/200)+math.exp(-16/200))
    assert value['normalized_profile'] is None and value['eq2_complete'] is None


@pytest.mark.parametrize('ph',[None,5.0])
def test_c44_registered_numerical_result_does_not_grant_scientific_qualification(ph):
    result=camsol.assess('AAAAA',ph)
    assert result['ph_used']==('neutral' if ph is None else ph)
    assert math.isfinite(result['global_score']) and len(result['per_residue'])==5
    assert not result['reliable'] and result['consistency_status']=='NOT_ASSESSED'
    assert result['blocked_dependencies']==['CAMSOL_REFERENCE_VALIDATION_NOT_COMPLETED']


def test_c44_asset_tamper_rejected(tmp_path,monkeypatch):
    path=tmp_path/'camsol_params.json';path.write_bytes(camsol.ASSET.read_bytes()+b' ')
    path.with_suffix('.json.sha256').write_text(camsol.ASSET_SHA256)
    monkeypatch.setattr(camsol,'ASSET',path)
    with pytest.raises(RuntimeFault,match='hash mismatch'):camsol.parameters()


def summary(solubility=None,ddg=None):
    return summarize(dict(dimension_weights=dict.fromkeys(('solubility','aggregation','ph_stability',
        'tag_exposure','expressibility','stability_ddg'),1)),
        dict(status='computed_unreviewed',score=.5),
        dict(status='unknown',reliable=False,n_term=None,reason_code='MISSING'),
        dict(status='unreliable',reliable=False,dg_curve=[1],reason_code='LOW_QUALITY'),
        solubility=solubility,stability_ddg=ddg)


def test_s40_observed_unreliable_is_missing_not_zero():
    value=summary()
    assert value['dev_dims_available']==1 and value['dev_dims_observed']==2
    assert 'ph_stability' in value['missing_dimensions']
    assert value['dimensions']['ph_stability']['normalized_score'] is None
    assert value['overall_score'] is None


@pytest.mark.parametrize('raw,expected',[(-10,0),(0,.5),(10,1)])
def test_s40_c44_clip_and_available_weight_renormalization(raw,expected):
    # Abstract numeric fixture, not a calibrated CamSol result or science claim.
    value=summary(dict(status='computed',reliable=True,global_score=raw),0)
    assert value['overall_score']==pytest.approx((expected+.5+.5)/3)
    assert value['dev_dims_available']==3
    assert not value['automatic_design_release']


@pytest.mark.parametrize('ddg,expected',[(2000,0),(-2000,1),(0,.5)])
def test_s40_ddg_stable_sigmoid(ddg,expected):
    assert summary(ddg=ddg)['dimensions']['stability_ddg']['normalized_score']==expected


def test_n10_cross_run_structure_is_rejected_before_consumption():
    class Runtime:
        def _registered_result_artifact(self,*args):
            return dict(run_id='other'),b'{}',{}
    with pytest.raises(RuntimeFault,match='another run'):
        sources(Runtime(),None,dict(structure_input=dict(state='available',artifact=dict(run_id='other'))),'current')
