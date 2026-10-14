"""N07/S-12 development contract, calculation and lifecycle guards."""
import itertools
from pathlib import Path

import pytest

from t01_phase1_real.common import RuntimeFault, encode, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.glycosylation import policy
from t01_phase1_real.development.glycosylation.result import scan


def hotspot(state='not_provided',hotspots=None,source=None,reason_code=None):
    return dict(state=state,hotspots=hotspots,source=source,reason_code=reason_code)


def source(digest='a'*64):
    return dict(node_id='N06',source_id='w3-contract-fixture',sha256=digest)


def body(sequence='NNST',context=None):
    return dict(protein_sequence=sequence,user_sequence_id='用户别名',
        hotspot_input=context if context is not None else hotspot(),timeout_seconds=5)


@pytest.fixture
def rt(tmp_path):
    return Runtime(tmp_path/'runtime')


@pytest.mark.parametrize('sequence',['','a','NXST','NN*T','NN T','NNST\n',None,'A'*20001])
def test_invalid_sequence_rejected_before_admission(rt,sequence):
    with pytest.raises(RuntimeFault,match='uppercase AA20'):
        rt.submit_sequence(encode(body(sequence)),f'bad-{str(sequence)[:4]}',policy.TOOL)


@pytest.mark.parametrize('change',[{'timeout_seconds':0},{'timeout_seconds':61},{'user_sequence_id':None},
    {'extra':True}])
def test_exact_request_contract(change):
    value=body();value.update(change)
    with pytest.raises(RuntimeFault):policy.request(encode(value))


def test_exhaustive_triplets_match_only_n_x_s_or_t_with_x_not_proline():
    alphabet='ACDEFGHIKLMNPQRSTVWY'
    for triplet in map(''.join,itertools.product(alphabet,repeat=3)):
        observed=scan(body(triplet))['glycosylation']['sites']
        expected=[1] if triplet[0]=='N' and triplet[1]!='P' and triplet[2] in 'ST' else []
        assert observed==expected


def test_overlap_and_expression_hint_use_one_based_sequon_n_positions():
    result=scan(body('NNSTAAANPSAAANAT'))
    assert result['glycosylation']==dict(sites=[1,2,14],site_count=3,shielding_risk=False,expression_hint='真核表达优先')
    assert result['sequons']==[dict(position=1,sequon='NNS'),dict(position=2,sequon='NST'),dict(position=14,sequon='NAT')]
    assert result['hotspot_assessment']['status']=='NOT_PERFORMED'


def test_no_sequon_is_a_valid_nonnull_empty_result(rt):
    job=rt.submit_sequence(encode(body('ANPSAAAA')), 'empty',policy.TOOL)
    final=rt.dispatch(job['job_id']);result=rt.result(final['job_id'])
    assert final['state']=='succeeded' and result['status']=='completed_empty'
    assert result['glycosylation']==dict(sites=[],site_count=0,shielding_risk=False,expression_hint=None)
    assert result['hotspot_assessment']['status']=='NOT_PERFORMED'
    assert result['usable_for_pipeline'] is result['automatic_handoff'] is False


def test_exact_twenty_aa_hotspot_counts_boundary_n_coordinates(rt):
    chars=list('A'*25)
    for position,motif in [(1,'NAS'),(20,'NAT'),(23,'NVT')]:chars[position-1:position+2]=motif
    sequence=''.join(chars)
    context=hotspot('available',[dict(start=1,end=20)],source(),None)
    final=rt.dispatch(rt.submit_sequence(encode(body(sequence,context)),'hotspot',policy.TOOL)['job_id'])
    result=rt.result(final['job_id'])
    assert result['glycosylation']==dict(sites=[1,20,23],site_count=3,shielding_risk=True,expression_hint='真核表达优先')
    assert result['hotspot_assessment']['windows']==[
        dict(start=1,end=20,site_positions=[1,20],site_count=2,shielding_risk=True)]
    assert result['hotspot_assessment']['source']==source()
    assert result['method_summary']['hotspot_full_chain_validated'] is False


@pytest.mark.parametrize('context',[hotspot('available',[dict(start=1,end=19)],source(),None),
    hotspot('available',[dict(start=0,end=19)],source(),None),
    hotspot('available',[dict(start=1,end=20)],None,None),
    hotspot('available',None,source(),None),
    hotspot('not_provided',[],None,None),
    hotspot('upstream_unavailable',None,source(None),None)])
def test_ambiguous_or_inconsistent_hotspot_contract_is_rejected(context):
    with pytest.raises(RuntimeFault):policy.request(encode(body('A'*30,context)))


def test_empty_available_and_upstream_unavailable_remain_distinct(rt):
    available=hotspot('available',[],source(),None)
    unavailable=hotspot('upstream_unavailable',None,source(None),'N06_FAILED')
    one=rt.dispatch(rt.submit_sequence(encode(body('NAS',available)),'available-empty',policy.TOOL)['job_id'])
    two=rt.dispatch(rt.submit_sequence(encode(body('NAS',unavailable)),'upstream-failed',policy.TOOL)['job_id'])
    r1,r2=rt.result(one['job_id']),rt.result(two['job_id'])
    assert r1['hotspot_assessment']['status']=='NOT_PERFORMED'
    assert r1['hotspot_assessment']['input_state']=='available'
    assert r2['hotspot_assessment']['status']=='NOT_PERFORMED'
    assert r2['hotspot_assessment']['upstream_reason_code']=='N06_FAILED'
    assert r1['glycosylation']['shielding_risk'] is r2['glycosylation']['shielding_risk'] is False


def test_atomic_idempotency_and_additive_schema_registration(rt):
    raw=encode(body('NAS'))
    first=rt.submit_sequence(raw,'same',policy.TOOL);second=rt.submit_sequence(raw,'same',policy.TOOL)
    assert first==second and first['node_id']=='N07' and first['rule_profile']==policy.registered_rules()
    with pytest.raises(RuntimeFault,match='different bytes'):
        rt.submit_sequence(encode(body('NAT')),'same',policy.TOOL)
    assert first['evidence_kind']=='G0_REAL_OUTPUT' and first['review_required'] and not first['usable_for_pipeline']


def test_queued_cancel_retry_and_result_artifacts(rt):
    job=rt.submit_sequence(encode(body('NAS')),'cancel-original',policy.TOOL)
    cancelled=rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=job['job_id'],idempotency_key='cancel')))
    assert cancelled['state']=='cancelled' and cancelled['stop_confirmed']
    retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=job['job_id'],idempotency_key='retry')))
    final=rt.dispatch(retry['job_id']);result=rt.result(final['job_id'])
    assert final['state']=='succeeded' and retry['retry_of_job_id']==job['job_id']
    assert result['binding']['input_sha256']==job['request_artifact']['sha256']
    assert result['binding']['sequence_sha256']==sha(b'NAS')
    assert any(row['path']=='output/observation.json' for row in result['raw_artifacts'])


@pytest.mark.parametrize('fault,error',[('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID')])
def test_local_compute_failures_never_emit_scientific_values(rt,fault,error):
    job=rt.submit_sequence(encode(body('NAS')),'fault-'+fault,policy.TOOL)
    rt._development_fault=fault
    try:final=rt.dispatch(job['job_id'])
    finally:rt._development_fault=None
    result=rt.result(final['job_id'])
    assert final['state']=='failed' and final['error_code']==error
    assert result['glycosylation'] is result['sequons'] is result['hotspot_assessment'] is None
    assert result['status']=='unreliable' and not result['usable_for_pipeline']


def test_interrupted_local_claim_recovers_as_failure_and_can_retry(rt):
    job=rt.submit_sequence(encode(body('NAS')),'interrupted',policy.TOOL)
    rt._development_fault='interrupt_after_claim'
    try:claimed=rt.dispatch(job['job_id'])
    finally:rt._development_fault=None
    assert claimed['state']=='running'
    recovered=rt.recover(job['job_id']);result=rt.result(job['job_id'])
    assert recovered['state']=='failed' and recovered['error_code']=='INTERRUPTED'
    assert result['glycosylation'] is None
    retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=job['job_id'],idempotency_key='retry-interrupted')))
    assert rt.dispatch(retry['job_id'])['state']=='succeeded'


def test_published_result_hash_is_enforced(rt):
    final=rt.dispatch(rt.submit_sequence(encode(body('NAS')),'tamper',policy.TOOL)['job_id'])
    ref=next(row for row in final['artifacts'] if row['role']=='result')
    path=Path(rt.root)/rt.attempt_path(final)/'published'/(ref['artifact_id']+'.bin')
    path.write_bytes(path.read_bytes()+b' controlled-damage')
    with pytest.raises(RuntimeFault) as caught:
        rt.result(final['job_id'])
    assert caught.value.code=='HASH_MISMATCH'
