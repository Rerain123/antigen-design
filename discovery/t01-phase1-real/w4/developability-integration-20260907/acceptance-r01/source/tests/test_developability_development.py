"""N10 S-36a/S-39/S-40 partial baseline and lifecycle guards."""
import copy
import math

import pytest

from t01_phase1_real.common import RuntimeFault, encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.developability import policy
from t01_phase1_real.development.developability.compute import expressibility, tag_exposure, summarize

SEQ='ACDEFGHIKLMNPQRSTVWY'
DIMENSIONS={name:1.0 for name in policy.DIMENSIONS}


def request(**changes):
    value=dict(protein_sequence=SEQ,user_sequence_id='engineering-n10',
        structure_input=dict(state='not_provided',artifact=None,reason_code=None),target_ph=None,
        target_ph_range=[4.0,8.0],dimension_weights=None,timeout_seconds=5)
    value.update(changes);return value


def structure(rsa,confidence='high',signed=False):
    sign=dict(reviewer='algorithm') if signed else None
    return dict(qualification='SCIENTIFICALLY_SIGNED' if signed else 'DEVELOPMENT_UNREVIEWED',scientific_signoff=sign,
        analysis=dict(quality=dict(quality=dict(confidence=confidence),s11_quality_condition=confidence!='low'),
            mapping=dict(target_chain_id='A',sequence='A'*len(rsa)),rsa=dict(status='computed_unverified',error_code=None,
                out_of_domain=[],development_result=dict(per_residue=rsa),scientific_signoff=sign)))


def test_expressibility_reference_units_formula_and_bounds():
    value=expressibility(SEQ)
    assert value['mw_kda']==pytest.approx(2.3957134)
    assert value['pi']==pytest.approx(6.784552192687988)
    assert value['gravy']==pytest.approx(-.49)
    assert value['instability_index']==pytest.approx(84.74)
    assert value['aliphatic_index']==pytest.approx(58.5)
    expected=(1/(1+math.exp(-.2*(40-84.74))))*.4+math.exp(-((-.49+.25)**2)/(2*.3**2))*.3+(1/(1+math.exp(-.05*(100-2.3957134))))*.3
    assert value['score']==pytest.approx(expected) and 0<=value['score']<=1
    assert value['method']['molecular_weight_unit']=='kDa' and value['method']['biopython']=='1.88'


@pytest.mark.parametrize('value,classification',[(0.4,'exposed'),(.399999,'partial'),(.2,'partial'),(.199999,'buried')])
def test_tag_threshold_boundaries(value,classification):
    result=tag_exposure(structure([value]*20,signed=True))
    assert result['n_term']['classification']==classification


def test_tag_uses_terminal_ten_prefers_higher_and_requires_signoff_for_reliability():
    result=tag_exposure(structure([.1]*10+[.5]*10))
    assert result['n_term']==dict(mean_rsa=.1,classification='buried')
    assert result['c_term']==dict(mean_rsa=.5,classification='exposed') and result['preferred_end']=='C-term'
    assert result['status']=='computed_unreviewed' and result['reliable'] is False
    assert result['reason_code']=='RSA_SCIENTIFIC_SIGNOFF_MISSING'
    signed=tag_exposure(structure([.4]*20,signed=True))
    assert signed['reliable'] is True and signed['preferred_end']=='neither'


@pytest.mark.parametrize('source,reason',[(None,'STRUCTURE_NOT_AVAILABLE'),(structure([.2]*20,'low'),'STRUCTURE_QUALITY_LOW'),
    (structure([None]+[.2]*19),'TERMINAL_RSA_INCOMPLETE')])
def test_tag_unknown_guards(source,reason):
    value=tag_exposure(source);assert value['status']=='unknown' and value['reason_code']==reason and value['n_term'] is None


def test_out_of_domain_and_mapping_ambiguity_never_become_tag_values():
    source=structure([.5]*20,signed=True);source['analysis']['rsa'].update(out_of_domain=[{'position':1}],development_result=None,
        status='output_invalid',error_code='OUTPUT_INVALID')
    assert tag_exposure(source)['reason_code']=='OUTPUT_INVALID'
    source=structure([.5]*20,signed=True);source['analysis']['mapping']['target_chain_id']=None
    assert tag_exposure(source)['reason_code']=='STRUCTURE_MAPPING_NOT_UNIQUE'


def test_partial_summary_never_fabricates_overall_or_design_release():
    body=request(dimension_weights=DIMENSIONS);expr=expressibility(SEQ);tag=tag_exposure(None)
    value=summarize(body,expr,tag)
    assert value['dev_dims_available']==1 and value['dev_dims_reliable']==1 and value['dimensions_total']==6
    assert value['missing_dimensions']==['solubility','aggregation','ph_stability','tag_exposure','stability_ddg']
    assert value['overall_score'] is None and value['classification'] is None
    assert value['overall_status']=='incomplete_required_solubility'
    assert value['n10_complete'] is False and value['design_gate']=='NOT_EVALUATED' and not value['automatic_design_release']
    assert value['stability_ddg'] is None and len(value['risk_flags'])==len(value['mitigation_suggestions'])


@pytest.mark.parametrize('change',[dict(protein_sequence='AX'),dict(user_sequence_id=''),dict(target_ph=True),
    dict(target_ph_range=[4,4]),dict(target_ph_range=[4,4.01]),dict(dimension_weights={}),
    dict(dimension_weights=dict(DIMENSIONS,foreign=1)),dict(timeout_seconds=True),dict(extra='no')])
def test_invalid_requests(change):
    with pytest.raises(RuntimeFault):policy.request(encode(dict(request(),**change)))


def test_runtime_partial_result_idempotency_failure_and_recovery(tmp_path):
    rt=Runtime(tmp_path/'run');raw=encode(request())
    job=rt.submit_sequence(raw,'main',policy.TOOL);assert job['node_id']=='N10'
    assert rt.submit_sequence(raw,'main',policy.TOOL)['job_id']==job['job_id']
    final=rt.dispatch(job['job_id']);assert final['state']=='succeeded'
    value=rt.result(job['job_id'])
    assert value['status']=='partial_developability_unreviewed' and value['developability']['overall_score'] is None
    assert value['steps']['completed_steps']==['S-36a','S-39','S-40-partial'] and value['steps']['n10_status'].startswith('PARTIAL')
    assert value['usable_for_pipeline'] is False and value['automatic_handoff'] is False
    failed=rt.submit_sequence(raw,'failure',policy.TOOL);rt._development_fault='compute_failure'
    assert rt.dispatch(failed['job_id'])['state']=='failed';rt._development_fault=None
    interrupted=rt.submit_sequence(raw,'interrupted',policy.TOOL);rt._development_fault='interrupt_after_claim'
    rt.dispatch(interrupted['job_id']);rt._development_fault=None
    rt.recover(interrupted['job_id']);assert rt.get(interrupted['job_id'])['error_code']=='INTERRUPTED'


def test_corrupt_observation_isolated(tmp_path):
    rt=Runtime(tmp_path/'run');job=rt.submit_sequence(encode(request()),'corrupt',policy.TOOL)
    rt._development_fault='corrupt_output';final=rt.dispatch(job['job_id']);rt._development_fault=None
    assert final['state']=='failed' and rt.result(job['job_id'])['developability'] is None
