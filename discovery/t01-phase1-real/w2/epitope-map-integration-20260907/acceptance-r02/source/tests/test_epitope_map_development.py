"""N06/S-19 bounded map calculation and real ArtifactRef chaining tests."""
import copy
import os

import pytest

from t01_phase1_real.common import RuntimeFault, encode, new_id, now, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.bepipred import policy as bepipred
from t01_phase1_real.development.epitope_map import policy
from t01_phase1_real.development.epitope_map.result import compute
from t01_phase1_real.development.glycosylation import policy as glycosylation
from t01_phase1_real.development.netmhc import policy as netmhc

SEQ='ACDEFGHIKLMNPQRSTVWYACDEFGHIKL'
I_ALLELE='HLA-A02:01'
II_ALLELE='HLA-DPA10202-DPB11901'


@pytest.fixture
def rt(tmp_path):
    if os.name!='nt':pytest.skip('Current trusted-local task runtime requires Windows')
    return Runtime(tmp_path/'runtime')


def source_body(tool):
    if tool==bepipred.TOOL:
        return encode(dict(protein_sequence=SEQ,user_sequence_id='fixture-bepi',timeout_seconds=30))
    return encode(dict(protein_sequence=SEQ,user_sequence_id='fixture-netmhc',host_species='Homo sapiens',
        mhc_i_alleles=[I_ALLELE],mhc_ii_alleles=[II_ALLELE],timeout_seconds=30))


def _binding(job):
    return dict(run_id=job['run_id'],request_id=job['request_id'],job_id=job['job_id'],attempt_id=job['attempt_id'],
        execution_identity=job['execution_identity'],execution_profile=job['execution_profile'],
        input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(SEQ.encode()))


def _source_result(job):
    common=dict(contract_version='0.1.0',tool_id=job['tool_id'],binding=_binding(job),
        usable_for_pipeline=False,automatic_handoff=False,qualification='DEVELOPMENT_UNREVIEWED',
        evidence_kind='G0_REAL_OUTPUT',execution=dict(error_code=None,exit_code=0,stopped_confirmed=True))
    if job['tool_id']==bepipred.TOOL:
        common.update(status='raw_scores_unreviewed',raw_scores=[dict(sequence_position=index,residue=residue,
            ensemble_probability=index/100,linear_epitope_score=index/200) for index,residue in enumerate(SEQ,1)],
            postprocessing=dict(status='review_required'))
    else:
        i=dict(peptide_seq=SEQ[:9],start=1,end=9,allele=I_ALLELE,percent_rank=.1,classification='SB',core=SEQ[:9])
        ii=dict(peptide_seq=SEQ[:15],start=1,end=15,allele=II_ALLELE,percent_rank=.2,classification='SB',core=SEQ[2:11])
        common.update(status='raw_predictions_unreviewed',channels=dict(
            mhc_i=dict(status='parsed_unreviewed',hits=[i]),mhc_ii=dict(status='parsed_unreviewed',hits=[ii])))
    return common


def finish_source(rt,tool,key):
    queued=rt.submit_sequence(source_body(tool),key,tool);active=copy.deepcopy(queued)
    active.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
        lease_epoch=1,started_at=now())
    with rt._tx() as db:
        rt._store(db,active,queued,'fixture-claimed');rt._execution_store(db,queued['job_id'],{})
    return rt._finish_development(queued['job_id'],dict(tree_stopped=True),{},_source_result(active))


def n06_body(rt,bepi_job,net_job,**changes):
    value=dict(protein_sequence=SEQ,user_sequence_id='n06',bepipred_input=rt.source_input(bepi_job,bepipred.TOOL),
        netmhc_input=rt.source_input(net_job,netmhc.TOOL),
        blast_input=dict(state='not_executed',reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'),timeout_seconds=5)
    value.update(changes);return encode(value)


def test_confirmed_t_map_rules_and_unresolved_branches_remain_null():
    bepi=_source_result(dict(tool_id=bepipred.TOOL,run_id='run',request_id='request',job_id='job',attempt_id='attempt',
        execution_identity='exec',execution_profile={},request_artifact=dict(sha256='0'*64)))
    mhc=_source_result(dict(tool_id=netmhc.TOOL,run_id='run',request_id='request',job_id='job',attempt_id='attempt',
        execution_identity='exec',execution_profile={},request_artifact=dict(sha256='0'*64)))
    body=policy.request(encode(dict(protein_sequence=SEQ,user_sequence_id='unit',
        bepipred_input=dict(state='not_provided',artifact=None,reason_code=None),
        netmhc_input=dict(state='not_provided',artifact=None,reason_code=None),
        blast_input=dict(state='not_executed',reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'),timeout_seconds=5)))
    value=compute(body,dict(bepipred=bepi,netmhc=mhc));tmap=value['epitopes']['t_cell_presentation_map']
    assert tmap['residue_min_percent_rank'][:15]==[.1]*9+[.2]*6
    assert tmap['residue_inverse_minmax_score'][:9]==[1.0]*9
    assert tmap['presentation_hotspots']==[dict(start=1,end=9,epitope_level='E2-consensus',
        support='SB_DISTINCT_ALLELES_GTE_2',alleles=sorted([I_ALLELE,II_ALLELE]),allele_count=2)]
    assert value['epitopes']['b_cell_epitope_map']['regions'] is None
    assert value['epitopes']['b_cell_antigenic_hotspot_map']['hotspots'] is None
    assert value['epitopes']['density_per_residue'] is None


def test_legal_empty_netmhc_hit_sets_are_not_upstream_failure():
    mhc=_source_result(dict(tool_id=netmhc.TOOL,run_id='run',request_id='request',job_id='job',attempt_id='attempt',
        execution_identity='exec',execution_profile={},request_artifact=dict(sha256='0'*64)))
    for channel in mhc['channels'].values():channel['hits']=[]
    body=policy.request(encode(dict(protein_sequence=SEQ,user_sequence_id='empty',
        bepipred_input=dict(state='not_provided',artifact=None,reason_code=None),
        netmhc_input=dict(state='not_provided',artifact=None,reason_code=None),
        blast_input=dict(state='not_executed',reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'),timeout_seconds=5)))
    value=compute(body,dict(netmhc=mhc));tmap=value['epitopes']['t_cell_presentation_map']
    assert tmap['status']=='computed' and tmap['presentation_hotspots']==[] and tmap['evidence_regions']==[]
    assert tmap['normalization']==dict(status='not_computed',reason_code='NO_MHC_HITS',direction='1-minmax')


def test_runtime_binds_real_result_refs_and_n07_verifies_n06(rt):
    bepi=finish_source(rt,bepipred.TOOL,'bepi');mhc=finish_source(rt,netmhc.TOOL,'mhc')
    queued=rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id']),'n06',policy.TOOL)
    final=rt.dispatch(queued['job_id']);result=rt.result(final['job_id'])
    assert final['state']=='succeeded' and result['status']=='maps_unreviewed'
    assert result['execution']['sources_verified'] is True
    assert result['epitopes']['t_cell_presentation_map']['presentation_hotspots'][0]['start']==1
    hotspot=rt.n06_hotspot_input(final['job_id'],SEQ)
    assert hotspot['state']=='upstream_unavailable' and hotspot['reason_code']=='N06_HOTSPOTS_REVIEW_REQUIRED'
    n07=rt.submit_sequence(encode(dict(protein_sequence=SEQ,user_sequence_id='n07',hotspot_input=hotspot,
        timeout_seconds=5)),'n07',glycosylation.TOOL)
    n07=rt.dispatch(n07['job_id']);n07_result=rt.result(n07['job_id'])
    assert n07['state']=='succeeded'
    assert n07_result['hotspot_assessment']['source_verification']=='VERIFIED_N06_ARTIFACT_REF'
    assert n07_result['hotspot_assessment']['status']=='NOT_PERFORMED'
    assert n07_result['method_summary']['hotspot_source_artifact_validated'] is True
    assert n07_result['method_summary']['hotspot_full_chain_validated'] is False


def test_n06_reverifies_upstream_hash_at_dispatch(rt):
    bepi=finish_source(rt,bepipred.TOOL,'bepi');mhc=finish_source(rt,netmhc.TOOL,'mhc')
    queued=rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id']),'n06',policy.TOOL)
    ref=next(row for row in bepi['artifacts'] if row['role']=='result')
    with rt._db() as db:
        relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    (rt.root/relative).write_bytes(b'changed')
    final=rt.dispatch(queued['job_id'])
    assert final['state']=='failed' and final['error_code']=='HASH_MISMATCH' and final['attempt_id'] is None


def test_n06_sequence_mismatch_and_all_unavailable_are_not_silent_success(rt):
    bepi=finish_source(rt,bepipred.TOOL,'bepi');mhc=finish_source(rt,netmhc.TOOL,'mhc')
    with pytest.raises(RuntimeFault) as exc:
        rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id'],protein_sequence='A'*len(SEQ)),'mismatch',policy.TOOL)
    assert exc.value.code=='OUTPUT_INVALID'
    raw=encode(dict(protein_sequence=SEQ,user_sequence_id='none',
        bepipred_input=dict(state='not_provided',artifact=None,reason_code=None),
        netmhc_input=dict(state='not_provided',artifact=None,reason_code=None),
        blast_input=dict(state='not_executed',reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'),timeout_seconds=5))
    queued=rt.submit_sequence(raw,'none',policy.TOOL);final=rt.dispatch(queued['job_id'])
    result=rt.result(final['job_id'])
    assert final['state']=='failed' and result['null_reason']=='TOOL_FAILED' and result['epitopes'] is None


@pytest.mark.parametrize('fault',['compute_failure','corrupt_output'])
def test_n06_faults_publish_null_diagnostics(rt,fault):
    bepi=finish_source(rt,bepipred.TOOL,'bepi');mhc=finish_source(rt,netmhc.TOOL,'mhc')
    queued=rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id']),'n06',policy.TOOL)
    rt._development_fault=fault
    try:final=rt.dispatch(queued['job_id'])
    finally:rt._development_fault=None
    result=rt.result(final['job_id'])
    assert final['state']=='failed' and result['status']=='unreliable' and result['epitopes'] is None


def test_n06_interrupted_local_attempt_recovers_as_null(rt):
    bepi=finish_source(rt,bepipred.TOOL,'bepi');mhc=finish_source(rt,netmhc.TOOL,'mhc')
    queued=rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id']),'n06',policy.TOOL)
    rt._development_fault='interrupt_after_claim'
    try:running=rt.dispatch(queued['job_id'])
    finally:rt._development_fault=None
    assert running['state']=='running'
    final=rt.reconcile(running['job_id']);result=rt.result(final['job_id'])
    assert final['state']=='failed' and final['error_code']=='INTERRUPTED' and result['epitopes'] is None
