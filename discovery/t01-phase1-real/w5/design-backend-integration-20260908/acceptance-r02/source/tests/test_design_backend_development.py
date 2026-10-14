"""S27/S28 provenance, actual numeric boundaries and conservative missing-data behavior."""
import copy
import pytest
from t01_phase1_real.common import RuntimeFault,encode,decode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.design_backend import policy,permissions,burden,service


def request(seq='ACDEFGHIKLMNPQRSTVWY',**kwargs):
    return dict(protein_sequence=seq,user_sequence_id='explicit engineering audit',upstream={n:None for n in policy.PRODUCERS},
        user_regions=[],objective='general',epitope_policy='PRESERVE',epitope_mode='both',membrane_design_confirm=False,
        sample_numbers=[],timeout_seconds=30,**kwargs)


def scales():return decode((policy.HERE/'scales.json').read_bytes())


def receipts(values):return {n:dict(state='available' if n in values else 'missing',artifact=None) for n in policy.PRODUCERS}


def region(start,end,permission,allowed=None):return dict(start=start,end=end,permission=permission,allowed_residues=allowed,source_id='explicit-user-case')


def record(wt,seq):
    return dict(sample_number=1,sequence=seq,mutations=[dict(position=i,wt_residue=a,mut_residue=b,source='ProteinMPNN')
        for i,(a,b) in enumerate(zip(wt,seq),1) if a!=b])


def calculate(wt,seq,coords=None,domains=None,hotspots=None,objective='general'):
    return burden.compute(wt,record(wt,seq),dict(residues=coords),domains,hotspots,objective,scales())


def atoms(*xs):return {str(p):dict(atoms={'CB':[x,0.,0.],'CA':[x,0.,0.]}) for p,x in enumerate(xs,1)}


def test_all_missing_is_queryable_restricted_and_not_automatic_generation(tmp_path):
    rt=Runtime(tmp_path);body=request();job=rt.submit_sequence(encode(body),'missing',policy.TOOL)
    final=rt.dispatch(job['job_id']);assert final['state']=='succeeded'
    result=rt.result(job['job_id']);audit=result['audit']
    assert all(r['design_permission']=='RESTRICTED' for r in audit['permissions']['per_residue'])
    assert audit['burden_records'] is None and audit['n11_request_draft'] is None
    assert not result['usable_for_pipeline'] and not audit['automatic_generation'] and result['design_permissions'] is None
    assert rt.submit_sequence(encode(body),'missing',policy.TOOL)['job_id']==job['job_id']


@pytest.mark.parametrize('aa',list(policy.AA))
def test_positive_blosum_set_includes_wt_and_excludes_zero_negative(aa):
    body=request(aa);p=permissions.assemble(body,{},receipts({}),scales())['per_residue'][0]
    assert set(p['allowed_residues'])=={b for b in policy.AA if b==aa or scales()['blosum62'][aa][b]>0}
    if aa in 'CGP':assert p['allowed_residues']==aa


def test_user_override_of_high_domain_records_non_standard_and_conflict_blocks_export():
    values=dict(domains=dict(analysis=dict(functional_domains=[dict(type='domain',start=1,end=2,source='user_annotation',confidence='user_high')],core_map=None)))
    body=request('AAA');body['user_regions']=[region(1,1,'OPEN'),region(2,2,'FIXED'),region(2,2,'OPEN')]
    p=permissions.assemble(body,values,receipts(values),scales())
    assert p['per_residue'][0]['constraint_override'] and p['constraint_override'] and p['non_standard']
    assert p['per_residue'][0]['automatic_constraint_state']=='HARD' and p['per_residue'][0]['design_permission']=='OPEN'
    assert p['user_conflict_positions']==[2] and p['per_residue'][1]['design_permission']=='FIXED'


def test_structural_core_components_never_fill_core_map_or_disulfide_span():
    values=dict(domains=dict(analysis=dict(core_map=None,functional_domains=[dict(type='disulfide_bond',start=1,end=4,source='structure',confidence='high')],
        structure_assessment=dict(components=[dict(position=2,core_state='deep_critical')]))))
    p=permissions.assemble(request('ACCA'),values,receipts(values),scales())
    assert not p['fixed_positions'] and all(r['core_state'] is None for r in p['per_residue'])


def test_tcell_mode_is_explicit_and_only_restricts():
    values=dict(epitope_map=dict(epitopes=dict(t_cell_presentation_map=dict(presentation_hotspots=[dict(start=2,end=3)]))))
    body=request('AAAA');body['epitope_mode']='tcell_only'
    p=permissions.assemble(body,values,receipts(values),scales())
    assert 'S27_EXPLICIT_TCELL_PRESENTATION' in p['per_residue'][1]['reasons'] and not p['fixed_positions']
    body['epitope_mode']='both';p=permissions.assemble(body,values,receipts(values),scales())
    assert not p['per_residue'][1]['evidence_source']


def test_conservation_degraded_and_low_not_promoted_to_hard_or_open():
    con=dict(score_per_residue=[.95,.85,.2],conservation_confidence='high',unreliable_query_positions=[1])
    values=dict(homology=dict(analysis=dict(global_conservation_role='single_subtype',conservation=con)))
    p=permissions.assemble(request('AAA'),values,receipts(values),scales())
    assert p['per_residue'][0]['reasons']==['S27_FINAL_ELSE_RESTRICTED','conservation_degraded']
    assert 'S27_MID_CONSERVATION' in p['per_residue'][1]['reasons'] and not p['open_positions']


def test_zero_mutations_has_explicit_all_zero_despite_missing_inputs():
    r=calculate('AG','AG');v=r['values']
    assert v==dict(count=0,chemical=dict(charge=0.,hydrophobicity=0.,volume=0.,polarity=0.),
        spatial_clustering=0.,functional_proximity=0.,epitope_proximity=0.,epistasis_risk='LOW')
    assert r['engineering_thresholds']['aggregate_exceeded'] is False and r['formal_burden_exceeded'] is None


@pytest.mark.parametrize('a,b,charge,hydro,volume,exceeded',[
    ('A','G',0.,2.2,28.5,False),('F','Y',0.,4.1,3.7,False),('K','R',0.,.6,4.8,False),
    ('A','W',0.,2.7,139.2,True),('K','E',2.,.4,30.2,True),('L','R',1.,8.3,6.7,True),('H','D',1.1,.3,42.1,True)])
def test_chemical_absolute_sums_and_extreme_per_mutation(a,b,charge,hydro,volume,exceeded):
    r=calculate(a,b);row=r['per_mutation_chemical'][0]
    assert [row[k] for k in ('charge','hydrophobicity','volume')]==pytest.approx([charge,hydro,volume])
    assert row['chemical_exceeded']==exceeded and r['values']['spatial_clustering']==0
    assert r['values']['functional_proximity'] is None and r['values']['epitope_proximity'] is None


@pytest.mark.parametrize('d,clustered,epi',[(4.999,1.,'MEDIUM'),(5.,1.,'LOW'),(9.999,1.,'LOW'),(10.,0.,'LOW')])
def test_pair_distances_are_strict_at_five_and_ten(d,clustered,epi):
    r=calculate('AA','GG',atoms(0,d));assert r['values']['spatial_clustering']==clustered and r['values']['epistasis_risk']==epi


def test_gly_uses_wt_ca_missing_cb_never_falls_back_for_alanine():
    geo=atoms(0,2);del geo['1']['atoms']['CB']
    assert calculate('GA','AG',geo)['values']['epistasis_risk']=='MEDIUM'
    r=calculate('AA','GG',geo);assert r['values']['epistasis_risk'] is None and r['values']['spatial_clustering'] is None
    assert r['engineering_thresholds']['aggregate_exceeded'] is None


def test_two_adjacent_pairs_high_and_partial_geometry_not_treated_as_pass():
    r=calculate('AAA','GGG',atoms(0,3,6));assert r['values']['epistasis_risk']=='HIGH'
    assert r['engineering_thresholds']['aggregate_exceeded'] is True


@pytest.mark.parametrize('distance,expected',[(4.999,1.),(5.,1.),(5.001,0.)])
def test_proximity_inclusive_boundary_and_no_same_residue_distance_lookup(distance,expected):
    r=calculate('AA','GA',atoms(0,distance),[dict(start=2,end=2)],[])
    assert r['values']['functional_proximity']==expected and r['values']['epitope_proximity']==0
    r=calculate('AA','GA',None,[dict(start=1,end=1)],None)
    assert r['values']['functional_proximity']==1. and r['values']['epitope_proximity'] is None


@pytest.mark.parametrize('change',[dict(epitope_policy='OPTIMIZE'),dict(sample_numbers=[True]),dict(sample_numbers=[[]]),
    dict(sample_numbers=[1,1]),dict(objective='invented'),dict(timeout_seconds=True),dict(user_regions=[region(1,2,'RESTRICTED','C')])])
def test_invalid_requests(change):
    body=request();body.update(change)
    with pytest.raises(RuntimeFault):policy.request(encode(body))


@pytest.mark.parametrize('fault,error',[('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID'),('interrupt_after_claim','INTERRUPTED')])
def test_local_failure_recovery_retry(tmp_path,fault,error):
    rt=Runtime(tmp_path);job=rt.submit_sequence(encode(request()),'job',policy.TOOL);rt._development_fault=fault
    rt.dispatch(job['job_id']);rt._development_fault=None
    if fault=='interrupt_after_claim':rt.recover(job['job_id'])
    final=rt.get(job['job_id']);assert final['state']=='failed' and final['error_code']==error
    assert rt.result(job['job_id'])['audit'] is None
    retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=job['job_id'],idempotency_key='retry')))
    assert rt.dispatch(retry['job_id'])['state']=='succeeded'


@pytest.mark.parametrize('stop',['cancel','timeout'])
def test_local_active_stop_discards_computed_output(tmp_path,monkeypatch,stop):
    rt=Runtime(tmp_path);body=request();body['timeout_seconds']=1
    job=rt.submit_sequence(encode(body),'job',policy.TOOL);compute=service.evaluate
    def injected(*args):
        if stop=='cancel':rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=job['job_id'],idempotency_key='stop')))
        return compute(*args)
    if stop=='cancel':monkeypatch.setattr(service,'evaluate',injected)
    else:
        clock=iter([0.,2.]);monkeypatch.setattr(service.time,'perf_counter',lambda:next(clock))
    final=rt.dispatch(job['job_id']);assert final['state']==('cancelled' if stop=='cancel' else 'timed_out')
    assert rt.result(job['job_id'])['audit'] is None
