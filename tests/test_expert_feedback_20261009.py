"""Expert handoff boundaries, independent arithmetic and downstream qualification."""
import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from t01_phase1_real.common import RuntimeFault, decode, encode, sha
from t01_phase1_real.development import expert_feedback as expert
from t01_phase1_real.development.bepipred.postprocessing import project, native_top20_mask
from t01_phase1_real.development.design_backend import permissions, policy as design_policy, burden
from t01_phase1_real.development.developability import camsol, camsol_kernel as kernel, camsol_numerics as numeric
from t01_phase1_real.development.developability.compute import summarize
from t01_phase1_real.development.epitope_map.result import compute, prediction_type_join
from t01_phase1_real.development.epitope_protection.source import facts
from t01_phase1_real.development.epitope_protection.compute import compare
from t01_phase1_real.development.netmhc.pan import aggregate
from t01_phase1_real.development.netmhc.host_panel import readiness
from t01_phase1_real.service_api.native_report import build, peak_table
from t01_phase1_real.service_api.user_report import table, esc, number

ROOT=Path(__file__).resolve().parents[1]


def archived():
    return decode((ROOT/'reports/himat-report-review-20261009/backend-evidence.json').read_bytes())


def body(sequence):
    return dict(protein_sequence=sequence,user_sequence_id='expert-boundary-test',
        upstream={n:None for n in design_policy.PRODUCERS},user_regions=[],objective='general',
        epitope_policy='PRESERVE',epitope_mode='both',membrane_design_confirm=False,sample_numbers=[],timeout_seconds=30)


def assemble(sequence, domains, extra=None, users=()):
    request=body(sequence);request['user_regions']=list(users)
    values=dict(domains=dict(analysis=dict(functional_domains=domains,core_map=None)))
    values.update(extra or {})
    receipts={n:dict(state='available' if n in values else 'missing',artifact=None) for n in design_policy.PRODUCERS}
    return permissions.assemble(request,values,receipts,decode((design_policy.HERE/'scales.json').read_bytes()))


def raw(values, smooth=None):
    return [dict(sequence_position=i,residue='A',ensemble_probability=v,linear_epitope_score=(smooth or values)[i-1])
            for i,v in enumerate(values,1)]


def epitope(values):
    rows=raw(values);sequence='A'*len(rows)
    prediction=dict(tool_id='t01.real.bepipred',status='raw_scores_unreviewed',raw_scores=rows,
        binding=dict(sequence_sha256=sha(sequence.encode())),postprocessing=project(rows))
    request=dict(protein_sequence=sequence,blast_input=dict(state='not_executed',artifact=None,reason_code='MISSING'))
    return request,prediction


def test_original_package_and_handoff_are_byte_bound():
    receipt=expert.authority();assert receipt['version']=='expert-feedback-20261009-v1'
    params=(expert.ROOT/'camsol_params.json').read_bytes()
    assert sha(params)==(expert.ROOT/'camsol_params.json.sha256').read_text().strip()
    assert decode(params)['random_normalization']['mu_random'] is None
    current,identity=camsol.registered_parameters()
    assert current['derived_asset']['source_sha256']==sha(params)
    assert identity['authority']==receipt and identity['validation_status']=='NOT_ASSESSED'


def test_authority_tamper_rejects_use(tmp_path,monkeypatch):
    for name in decode((expert.ROOT/'receipt.json').read_bytes())['files']:
        (tmp_path/name).write_bytes((expert.ROOT/name).read_bytes())
    (tmp_path/'receipt.json').write_bytes((expert.ROOT/'receipt.json').read_bytes())
    (tmp_path/'handoff.md').write_bytes((tmp_path/'handoff.md').read_bytes()+b' ')
    monkeypatch.setattr(expert,'ROOT',tmp_path)
    with pytest.raises(RuntimeFault) as exc:expert.authority()
    assert exc.value.code=='HASH_MISMATCH'


@pytest.mark.parametrize('confidence',['high','user_high','medium','low'])
def test_chain_annotation_entirely_excluded_for_any_confidence(confidence):
    domains=[dict(type='mature_chain',start=1,end=5,confidence=confidence,source='uniprot')]
    original=copy.deepcopy(domains);result=assemble('AAAAA',domains)
    assert not result['fixed_positions'] and [r['position'] for r in result['restricted_positions']]==list(range(1,6))
    assert all(not r['evidence_source'] for r in result['per_residue'])
    assert result['annotation_exclusions'][0]['annotation']==domains[0]
    assert result['rule_authority']==expert.authority() and domains==original


def test_actual_233_chain_retains_47_independent_fixed_positions():
    data=archived();before=copy.deepcopy(data)
    domains=data['results']['domains']['analysis']['functional_domains']
    result=assemble(data['request']['protein_sequence'],domains)
    assert result['fixed_positions']==list(range(1,48))
    assert [r['position'] for r in result['restricted_positions']]==list(range(48,234)) and not result['open_positions']
    assert data==before


def test_chain_exclusion_keeps_disulfides_contacts_and_user_fixed():
    domains=[dict(type='mature_chain',start=1,end=6,confidence='high',source='uniprot'),
        dict(type='disulfide_bond',start=1,end=5,confidence='high',source='uniprot'),
        dict(type='active_site',start=2,end=2,confidence='high',source='uniprot')]
    contact=dict(start=3,end=3,sequence_position=3,epitope_level='E4-contact',evidence_source='IEDB',
        source_iedb_id='fixture',coordinate_sha256='a'*64,evidence_provenance=dict(source_iedb_id='fixture',reference_id='ref',source_artifact={'sha256':'b'*64}))
    result=assemble('AAAAAA',domains,dict(epitope_map=dict(epitopes=dict(b_cell_epitope_map=dict(regions=[contact])))),
        [dict(start=4,end=4,permission='FIXED',allowed_residues=None,source_id='explicit')])
    assert result['fixed_positions']==[1,2,3,4,5] and [r['position'] for r in result['restricted_positions']]==[6]


def test_functional_empty_is_null_and_l3_has_no_synthetic_chain_object():
    domains=[dict(type='mature_chain',start=1,end=3,confidence='high',source='uniprot')]
    filtered=expert.functional_regions(domains);assert filtered==[] and domains
    record=dict(sample_number=1,sequence='GAA',mutations=[dict(position=1,wt_residue='A',mut_residue='G',source='ProteinMPNN')])
    result=burden.compute('AAA',record,dict(residues={}),filtered,[],'general',decode((design_policy.HERE/'scales.json').read_bytes()))
    assert result['values']['functional_proximity'] is None
    assert 'FUNCTIONAL_CONFIRMED_EMPTY_NO_COMPARISON_OBJECT' in result['review_reasons']
    values=dict(domains=dict(analysis=dict(lookup=dict(status='hit'),functional_domains=domains)))
    side=facts(dict(protein_sequence='AAA',upstream={'structure':None}),{},values,{})
    assert side['domains']==[] and side['domain_analysis']['functional_domains']==domains
    comparison=compare('AAA','GAA',dict(wt=side,variant=side))
    assert comparison['l3']['functional_domains']==[] and comparison['l3']['functional_rmsd'] is None
    assert comparison['l3']['functional_reason']=='NO_DOMAINS_TO_VALIDATE'
    unchanged=dict(sample_number=1,sequence='AAA',mutations=[])
    zero=burden.compute('AAA',unchanged,dict(residues={}),[],[],'general',decode((design_policy.HERE/'scales.json').read_bytes()))
    assert zero['values']['functional_proximity'] is None and zero['values']['count']==0


@pytest.mark.parametrize('domains,status,excluded',[([], 'PASS',['functional_proximity']),
                                                   (None,'NOT_ASSESSED',[])])
def test_v2_geometry_distinguishes_empty_functional_inventory_from_missing(domains,status,excluded):
    from t01_phase1_real.development.workflow.revision_v2_runtime import geom
    record=dict(sample_number=1,sequence='GAA',mutations=[dict(position=1,wt='A',mut='G')])
    data=dict(snapshot=dict(original_wt_seq='AAA'),scales=decode((design_policy.HERE/'scales.json').read_bytes()),
        audit=dict(geometry=dict(residues={}),domain_intervals=domains,epitope_hotspot_intervals=[]))
    geom(record,data)
    assert record['geometry_check']['check_status']==status
    assert record['geometry_check']['excluded_dimensions']==excluded
    assert record['geometry_check']['observation']['values']['functional_proximity'] is None


def test_hotspot_merge_precedes_length_filter_and_preserves_both_means():
    rows=raw([.3]*3+[.1]*2+[.4]*3,[.01]*8);before=copy.deepcopy(rows)
    result=project(rows);peak=result['linear_peaks_threshold'][0]
    assert (peak['start'],peak['end'],peak['positive_count'],peak['bridge_count'],peak['longest_positive_run'])==(1,8,6,2,3)
    assert peak['positive_fraction']==.75 and peak['mean_score_all']==pytest.approx(2.3/8)
    assert peak['mean_score_positive']==pytest.approx(.35) and peak['mean_score']==peak['mean_score_all']
    assert result['selected_project_score']=='ensemble_probability' and rows==before


def test_threshold_is_strict_and_positive_count_filter_is_not_enabled():
    result=project(raw([.1512]+[.4]*2+[.1]+[.4]*2+[.1]+[.4]*2))
    peak=result['linear_peaks_threshold'][0]
    assert peak['start']==2 and peak['end']==9 and peak['positive_count']==6
    # 2+2, relying on a two-residue bridge, is also allowed by total-length rule.
    small=project(raw([.4]*2+[.1]*2+[.4]*2))['linear_peaks_threshold'][0]
    assert small['positive_count']==4 and small['end']==6
    assert not result['canonical_parameters']['positive_count_hard_filter']


def test_top20_floor_stable_tie_and_low_score_are_disclosed():
    result=project(raw([.05]*8))
    assert sum(native_top20_mask([.05]*8))==2
    assert result['top20_audit']['count']==1 and result['top20_audit']['selected_positions']==[1]
    assert result['top20_audit']['tie_split'] and result['top20_audit']['tied_positions']==list(range(1,9))
    assert result['linear_peaks_threshold']==result['linear_peaks_top20']==[]
    assert result['top20_audit']['usage']=='REPORT_COMPARISON_ONLY_NOT_S19'


def test_s19_consumes_only_threshold_branch_and_not_top20():
    request,prediction=epitope([.1]*30)
    assert prediction['postprocessing']['linear_peaks_top20'][0]['end']==6
    result=compute(request,{'bepipred':prediction})
    bmap=result['epitopes']['b_cell_epitope_map']
    assert bmap['regions']==[] and bmap['linear_peaks_top20']
    assert result['epitopes']['density_per_residue']==[0.]*30
    assert result['epitopes']['b_cell_antigenic_hotspot_map']['hotspots']==[]


def test_s19_rejects_tampered_postprocessing_and_degenerate_scores_stay_unknown():
    request,prediction=epitope([.3]*30)
    result=compute(request,{'bepipred':prediction})
    assert result['epitopes']['b_cell_epitope_map']['regions'][0]['norm_score'] is None
    assert result['epitopes']['density_per_residue'] is None
    prediction['postprocessing']['linear_peaks'][0]['positive_count']=7
    with pytest.raises(RuntimeFault):compute(request,{'bepipred':prediction})


def test_assay_type_join_applies_only_to_overlap_and_keeps_prediction_e1():
    request,prediction=epitope([.2,.3,.4,.5,.6,.5,.4,.3,.2])
    bmap=compute(request,{'bepipred':prediction})['epitopes']['b_cell_epitope_map']
    prior=dict(epitope_regions=[dict(start=3,end=5,epitope_type='T',source_iedb_id='e3')],contact_residues=[])
    prediction_type_join(bmap,prior)
    assert [(r['start'],r['end'],r['epitope_type']) for r in bmap['regions']]==[(1,2,None),(3,5,'T'),(6,9,None)]
    assert all(r['epitope_level']=='E1-single' and r['evidence_source']=='prediction' for r in bmap['regions'])
    assert bmap['regions'][1]['norm_score']==pytest.approx((.5+.75+1)/3)


@pytest.mark.parametrize('kind',['B','mixed'])
def test_literature_interval_uses_available_predictor_norm_without_borrowing_across_channels(kind):
    from test_epitope_map_development import _source_result,SEQ,blast
    job=dict(tool_id=blast.TOOL,run_id='run',request_id='req',job_id='job',attempt_id='attempt',
        execution_identity='exec',execution_profile={},request_artifact=dict(sha256='0'*64))
    source=_source_result(job)
    prior=dict(database_id='engineering-n03',iedb_hit=True,evidence_level='literature_supported',
        epitope_regions=[dict(start=2,end=7,e_level='E3-region',source_iedb_id='99',reference_id='123',epitope_type=kind)],contact_residues=[])
    source.update(scope='N03_LOCAL_IEDB_PRIOR',iedb_prior=prior)
    source['search'].update({n:prior[n] for n in ('iedb_hit','evidence_level','epitope_regions','contact_residues')})
    rows=[dict(sequence_position=i,residue=a,ensemble_probability=(i-1)/len(SEQ),linear_epitope_score=.9) for i,a in enumerate(SEQ,1)]
    prediction=dict(tool_id='t01.real.bepipred',status='raw_scores_unreviewed',raw_scores=rows,
        binding=dict(sequence_sha256=sha(SEQ.encode())),postprocessing=project(rows))
    request=dict(protein_sequence=SEQ,blast_input=dict(state='available',artifact={'sha256':'fixture'},reason_code=None))
    result=compute(request,dict(blast=source,bepipred=prediction));maps=result['epitopes']
    region=next(r for r in maps['b_cell_epitope_map']['regions'] if r['epitope_level']=='E3-region')
    expected=sum(range(1,7))/6/(len(SEQ)-1)
    assert region['norm_score']==pytest.approx(expected)
    assert region['normalization_evidence']['source']=='BEPIPRED_RAW_ENSEMBLE_SEQUENCE_MINMAX_INTERVAL_MEAN_ALL'
    if kind=='mixed':
        tregion=maps['t_cell_presentation_map']['evidence_regions'][0]
        assert tregion.get('norm_score') is None and maps['density_per_residue'] is None
    else:assert maps['density_per_residue'] is not None


def test_literature_norm_missing_or_degenerate_predictor_is_not_filled():
    from t01_phase1_real.development.epitope_map.result import literature_prediction_norm
    assert literature_prediction_norm(None,dict(start=1,end=3),None)=={}
    request,prediction=epitope([.3]*15)
    bmap=compute(request,dict(bepipred=prediction))['epitopes']['b_cell_epitope_map']
    result=literature_prediction_norm(bmap,dict(start=1,end=3),None)
    assert result['norm_score'] is None and result['normalization_evidence']['status']=='NOT_ASSESSED'


def test_wt_summary_preserves_new_postprocessing_and_report_method():
    from t01_phase1_real.development.wt_draft import compute as wt,policy
    from test_wt_draft_development import request,SEQ
    params=policy.request(encode(request()));rows=[dict(sequence_position=i,residue=a,
        ensemble_probability=.2,linear_epitope_score=.3) for i,a in enumerate(SEQ,1)]
    processed=project(rows)
    value=dict(raw_scores=rows,postprocessing=processed,method_summary=dict(project='20261009'))
    receipts={n:dict(state='available' if n=='bepipred' else 'missing') for n in policy.PRODUCERS}
    result=wt.assemble(params,dict(bepipred=value),receipts)
    observed=result['assessments']['bepipred']['observations']
    assert observed['postprocessing']==processed and observed['method_summary']==value['method_summary']
    assert not result['assessments']['bepipred']['scientifically_accepted']


@pytest.mark.parametrize('sequence',['A','ADK','IKIKIKI','WEDKRIHAC','ACDEFGHIKLMNPQRSTVWY'])
def test_camsol_kernel_agrees_with_independent_scalar_equations(sequence):
    params,_=camsol.registered_parameters();terms=kernel.raw_profile(kernel.encode_sequence(sequence),params,details=True)
    expected=numeric.corrected_profile(sequence,params,pattern_counts=terms['pattern_counts'])
    assert terms['eq2_complete']==pytest.approx(expected,abs=1e-12)
    if sequence=='A':assert terms['eq1_raw']==pytest.approx([.96018],abs=1e-10)


def test_alternating_patterns_count_only_overlapping_five_residue_windows():
    params,_=camsol.registered_parameters()
    assert kernel.pattern_counts(kernel.encode_sequence('IKIKIKI'),params).tolist()==[[1,2,3,3,3,2,1]]
    assert kernel.pattern_counts(kernel.encode_sequence('IKIK'),params).tolist()==[[0,0,0,0]]
    assert kernel.pattern_counts(kernel.encode_sequence('IIIIIII'),params).tolist()==[[0]*7]


@pytest.mark.parametrize('sequence,ph,expected',[('ARA',12.48,.5),('AYA',11.,-.5),('ACA',14.,0.)])
def test_hh_arg_tyr_cys_are_explicit(sequence,ph,expected):
    params,_=camsol.registered_parameters()
    assert kernel.hh_charges(kernel.encode_sequence(sequence),params,ph)[0,1]==pytest.approx(expected)


def test_hh_changes_eq1_only_and_does_not_infer_histidine_tags():
    params,_=camsol.registered_parameters();encoded=kernel.encode_sequence('ADHHHKA')
    neutral=kernel.raw_profile(encoded,params,details=True);ph=kernel.raw_profile(encoded,params,target_ph=6.,details=True)
    assert ph['eq3_gatekeeper']==neutral['eq3_gatekeeper'] and ph['eq1_raw']!=neutral['eq1_raw']
    natural=kernel.hh_charges(encoded,params,6.);tagged=kernel.hh_charges(encoded,params,6.,[3,4,5])
    assert natural[0,2]>tagged[0,2] and tagged[0,2]==.5
    with pytest.raises(RuntimeFault):kernel.hh_charges(encoded,params,6.,[1])


@pytest.mark.parametrize('ph',[-1e300,1e300])
def test_hh_extreme_finite_values_do_not_overflow(ph):
    params,_=camsol.registered_parameters()
    assert np.isfinite(kernel.raw_profile(kernel.encode_sequence('DCEYHKR'),params,target_ph=ph)).all()


def test_calibration_receipt_uses_20m_positions_and_two_independent_fixed_reference_checks():
    params,identity=camsol.registered_parameters();receipt=decode((camsol.CURRENT_ASSETS/'calibration.json').read_bytes())
    assert receipt['length']==200 and receipt['ddof']==0 and receipt['all_positions_included']
    assert receipt['main']['count']==20000000 and receipt['main']['sequence_count']==100000
    assert [c['sequence_count'] for c in receipt['main']['checkpoints']]==[10000,50000,100000]
    assert [c['seed'] for c in receipt['checks']]==[4402,4403]
    for check in receipt['checks']:
        assert check['count']==20000000
        assert check['normalized_with_main']['mean']==pytest.approx((check['mean']-receipt['main']['mean'])/receipt['main']['population_std'])
    assert params['random_normalization']['mu_random']==receipt['main']['mean']
    assert receipt['statistics_status']=='CANDIDATE_STATISTICS_NO_PREDECLARED_ACCEPTANCE_TOLERANCE'
    assert receipt['validation_status']=='NOT_ASSESSED' and not receipt['scientific_consumption']


@pytest.mark.parametrize('name',['camsol_params.json','camsol_params.json.sha256','calibration.json'])
def test_registered_camsol_asset_and_sidecar_tamper_rejects(tmp_path,monkeypatch,name):
    for path in camsol.CURRENT_ASSETS.iterdir():(tmp_path/path.name).write_bytes(path.read_bytes())
    path=tmp_path/name;path.write_bytes(path.read_bytes()+b' ' if name!='camsol_params.json.sha256' else b'0'*64)
    monkeypatch.setattr(camsol,'CURRENT_ASSETS',tmp_path)
    with pytest.raises(RuntimeFault) as exc:camsol.assess('AAAAAA')
    assert exc.value.code=='HASH_MISMATCH'


def test_missing_camsol_asset_has_no_placeholder_score(tmp_path,monkeypatch):
    monkeypatch.setattr(camsol,'CURRENT_ASSETS',tmp_path)
    with pytest.raises(RuntimeFault) as exc:camsol.assess('AAAAA')
    assert exc.value.code=='DEPENDENCY_MISSING'


def test_camsol_kernel_change_requires_new_calibration_version(tmp_path,monkeypatch):
    assets=tmp_path/'assets/camsol-20261009-v1';assets.mkdir(parents=True)
    for path in camsol.CURRENT_ASSETS.iterdir():(assets/path.name).write_bytes(path.read_bytes())
    for name in ('camsol_kernel.py','calibration.py'):
        (tmp_path/name).write_bytes((camsol.CURRENT_ASSETS.parent.parent/name).read_bytes())
    path=tmp_path/'camsol_kernel.py';path.write_bytes(path.read_bytes()+b'\n# changed kernel\n')
    monkeypatch.setattr(camsol,'CURRENT_ASSETS',assets)
    with pytest.raises(RuntimeFault) as exc:camsol.assess('AAAAA')
    assert exc.value.code=='HASH_MISMATCH'


def test_null_statistics_reject_before_scoring(tmp_path,monkeypatch):
    params=decode((camsol.CURRENT_ASSETS/'camsol_params.json').read_bytes());params['random_normalization']['mu_random']=None
    encoded=encode(params)
    for path in camsol.CURRENT_ASSETS.iterdir():(tmp_path/path.name).write_bytes(path.read_bytes())
    (tmp_path/'camsol_params.json').write_bytes(encoded);(tmp_path/'camsol_params.json.sha256').write_text(sha(encoded))
    monkeypatch.setattr(camsol,'CURRENT_ASSETS',tmp_path);monkeypatch.setattr(camsol,'CURRENT_PARAMETER_SHA256',sha(encoded))
    with pytest.raises(RuntimeFault) as exc:camsol.assess('AAAAA')
    assert exc.value.code=='DEPENDENCY_MISSING'


def test_numerical_camsol_is_visible_but_excluded_from_overall():
    sol=camsol.assess('IKIKIKIKIK',5.)
    result=summarize(dict(dimension_weights=None),dict(status='computed_unreviewed',score=.5),
        dict(status='unknown',reliable=False,reason_code='MISSING',n_term=None),dict(status='unknown',reliable=False,reason_code='MISSING',dg_curve=None),solubility=sol)
    dim=result['dimensions']['solubility']
    assert dim['value']['global_score']==sol['global_score']
    assert not dim['included_in_overall'] and dim['normalized_score'] is None and result['overall_score'] is None
    assert not sol['scientific_consumption'] and set(sol['method_summary']['validation_groups'].values())=={'NOT_PERFORMED'}
    from t01_phase1_real.development.workflow.revision_v2 import freeze
    frozen=freeze(result['dimensions'],dict(sha256='fixture'))
    assert 'solubility' not in frozen['M0']
    assert frozen['exclusions']['solubility']=='CAMSOL_SCIENTIFIC_VALIDATION_NOT_COMPLETED'


def test_pig_ii_missing_is_unknown_not_confirmed_empty():
    panel=dict(channels=dict(mhc_i=dict(count=1,alleles=['SLA-1:0101']),mhc_ii=dict(count=0,alleles=[])))
    request=dict(protein_sequence='A'*15,mhc_i_alleles=['SLA-1:0101'],mhc_ii_alleles=[])
    result=dict(binding=dict(sequence_sha256=sha(('A'*15).encode())),panel_selection=dict(mode='explicit_alleles'),
        channels={k:dict(status='unavailable') for k in ('mhc_i','mhc_ii')})
    channels,_=aggregate('A'*15,panel,[(request,result,{})])
    assert channels['mhc_ii']['hits'] is channels['mhc_ii']['observed_rows'] is None
    assert channels['mhc_ii']['assessment_status']=='NOT_ASSESSED'
    ready=readiness('猪')
    assert ready['channels']['mhc_i']['allele_count']==76 and ready['channels']['mhc_ii']['allele_count']==0
    assert not ready['substitution_applied']


def test_report_shows_new_rule_and_numerical_qualifications():
    domains=[dict(type='mature_chain',start=1,end=6,confidence='high',source='uniprot')]
    permitted=assemble('AAAAAA',domains);sol=camsol.assess('AAAAAA')
    dimension=dict(value=sol,source=sol['tool'],exclusion_reason=sol['reason_code'])
    observation=dict(developability=dict(dimensions=dict(solubility=dimension)))
    view=dict(wt_draft=dict(assessments=dict(developability=dict(observations=observation))))
    node=dict(node_id='N11',state='succeeded',origin='INTERNAL_FACT',result=dict(audit=dict(permissions=permitted)))
    result=build(view,{},dict(nodes=dict(design_inputs=node),run_id='fixture',job_id='fixture',workflow_package_sha256='fixture'))
    assert '已采用10月9日专家裁决' in result['permissions']
    assert '全序列溶解度分数' in result['developability'] and '不纳入综合评分' in result['developability']
    text=peak_table(project(raw([.2]*3+[.1]*2+[.3]*3)),table,esc,number)
    assert '不是实验验证的线性表位' in text and '向下取整' in text


def test_report_shows_hotspot_numbers_without_experimental_claim():
    maps=dict(b_cell_antigenic_hotspot_map=dict(status='computed_unreviewed',
        hotspots=[dict(start=2,end=10,weighted_score=.634567,in_outside_region=False)]),density_per_residue=[.5]*15)
    view=dict(wt_draft=dict(assessments=dict(epitope_map=dict(observations=dict(epitopes=maps)))))
    text=build(view,{})['epitope']
    assert '2–10' in text and '0.634567' in text and '逐残基加权合成分数' in text
    assert '不等同于实验证实' in text
