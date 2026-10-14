"""N06/S-19 bounded map calculation and real ArtifactRef chaining tests."""
import copy
import os

import pytest

from t01_phase1_real.common import RuntimeFault, encode, new_id, now, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.bepipred import policy as bepipred
from t01_phase1_real.development.blast import policy as blast
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
    if tool==blast.TOOL:
        return encode(dict(protein_sequence=SEQ,user_sequence_id='fixture-blast',database_id='engineering-n03',
            database_manifest_sha256='a'*64,thresholds=dict(identity_percent_min=70.0,
                query_coverage_percent_min=80.0),timeout_seconds=30))
    return encode(dict(protein_sequence=SEQ,user_sequence_id='fixture-netmhc',host_species='Homo sapiens',
        mhc_i_alleles=[I_ALLELE],mhc_ii_alleles=[II_ALLELE],timeout_seconds=30))


def _binding(job):
    value=dict(run_id=job['run_id'],request_id=job['request_id'],job_id=job['job_id'],attempt_id=job['attempt_id'],
        execution_identity=job['execution_identity'],execution_profile=job['execution_profile'],
        input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(SEQ.encode()))
    if job['tool_id']==blast.TOOL:
        value.update(database_id='engineering-n03',database_manifest_sha256='a'*64)
    return value


def _source_result(job,blast_hit=True,database_mismatch=False):
    common=dict(contract_version='0.1.0',tool_id=job['tool_id'],binding=_binding(job),
        usable_for_pipeline=False,automatic_handoff=False,qualification='DEVELOPMENT_UNREVIEWED',
        evidence_kind='G0_REAL_OUTPUT',execution=dict(error_code=None,exit_code=0,stopped_confirmed=True))
    if job['tool_id']==bepipred.TOOL:
        common.update(status='raw_scores_unreviewed',raw_scores=[dict(sequence_position=index,residue=residue,
            ensemble_probability=index/100,linear_epitope_score=index/200) for index,residue in enumerate(SEQ,1)],
            postprocessing=dict(status='review_required'))
    elif job['tool_id']==netmhc.TOOL:
        i=dict(peptide_seq=SEQ[:9],start=1,end=9,allele=I_ALLELE,percent_rank=.1,classification='SB',core=SEQ[:9])
        ii=dict(peptide_seq=SEQ[:15],start=1,end=15,allele=II_ALLELE,percent_rank=.2,classification='SB',core=SEQ[2:11])
        common.update(status='raw_predictions_unreviewed',channels=dict(
            mhc_i=dict(status='parsed_unreviewed',hits=[i]),mhc_ii=dict(status='parsed_unreviewed',hits=[ii])))
    else:
        hsp=dict(hsp_index=1,query_id='fixture',subject_id='subject-1',subject_title='engineering fixture',
            percent_identity=100.0,alignment_length=len(SEQ),mismatches=0,gap_opens=0,query_start=1,
            query_end=len(SEQ),subject_start=1,subject_end=len(SEQ),query_length=len(SEQ),subject_length=len(SEQ),
            query_coverage_percent=100.0,native_query_coverage_percent=100.0,evalue=0.0,bit_score=100.0,
            query_alignment=SEQ,subject_alignment=SEQ,passes_registered_thresholds=True)
        raw=[hsp] if blast_hit else [];qualified=list(raw);manifest='b'*64 if database_mismatch else 'a'*64
        common.update(status='similarity_hits_unreviewed' if blast_hit else 'no_qualifying_similarity_hit',
            scientific_signoff=None,production_status='NOT_DEPLOYED',
            database=dict(database_id='engineering-n03',manifest_sha256=manifest,qualification='ENGINEERING_FIXTURE',
                purpose='unit engineering fixture',source=dict(name='fixture'),blast=dict(db_prefix='engineering')),
            search=dict(search_status='hit' if blast_hit else 'no_hit',raw_hsp_count=len(raw),
                qualifying_hsp_count=len(qualified),raw_hsps=raw,qualifying_hsps=qualified,iedb_hit=None,
                evidence_level=None,epitope_regions=None,contact_residues=None))
    return common


def finish_source(rt,tool,key):
    queued=rt.submit_sequence(source_body(tool),key,tool);active=copy.deepcopy(queued)
    active.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
        lease_epoch=1,started_at=now())
    with rt._tx() as db:
        rt._store(db,active,queued,'fixture-claimed');rt._execution_store(db,queued['job_id'],{})
    return rt._finish_development(queued['job_id'],dict(tree_stopped=True),{},_source_result(active))


def finish_blast_source(rt,key,hit=True,database_mismatch=False,error=None):
    queued=rt.submit_sequence(source_body(blast.TOOL),key,blast.TOOL);active=copy.deepcopy(queued)
    active.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
        lease_epoch=1,started_at=now())
    with rt._tx() as db:
        rt._store(db,active,queued,'fixture-claimed');rt._execution_store(db,queued['job_id'],{})
    value=_source_result(active,hit,database_mismatch)
    if error:
        value.update(status='unreliable',null_reason=error,search=None)
        value['execution'].update(error_code=error,exit_code=1)
    return rt._finish_development(queued['job_id'],dict(tree_stopped=True),{},value)


def n06_body(rt,bepi_job,net_job,blast_job=None,**changes):
    value=dict(protein_sequence=SEQ,user_sequence_id='n06',bepipred_input=rt.source_input(bepi_job,bepipred.TOOL),
        netmhc_input=rt.source_input(net_job,netmhc.TOOL),
        blast_input=rt.source_input(blast_job,blast.TOOL) if blast_job else dict(
            state='not_executed',artifact=None,reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'),timeout_seconds=5)
    value.update(changes);return encode(value)


def test_confirmed_t_map_rules_and_source_bound_empty_hotspot():
    bepi=_source_result(dict(tool_id=bepipred.TOOL,run_id='run',request_id='request',job_id='job',attempt_id='attempt',
        execution_identity='exec',execution_profile={},request_artifact=dict(sha256='0'*64)))
    mhc=_source_result(dict(tool_id=netmhc.TOOL,run_id='run',request_id='request',job_id='job',attempt_id='attempt',
        execution_identity='exec',execution_profile={},request_artifact=dict(sha256='0'*64)))
    body=policy.request(encode(dict(protein_sequence=SEQ,user_sequence_id='unit',
        bepipred_input=dict(state='not_provided',artifact=None,reason_code=None),
        netmhc_input=dict(state='not_provided',artifact=None,reason_code=None),
        blast_input=dict(state='not_executed',artifact=None,reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'),timeout_seconds=5)))
    value=compute(body,dict(bepipred=bepi,netmhc=mhc));tmap=value['epitopes']['t_cell_presentation_map']
    assert tmap['residue_min_percent_rank'][:15]==[.1]*9+[.2]*6
    assert tmap['residue_inverse_minmax_score'][:9]==[1.0]*9
    assert tmap['presentation_hotspots']==[dict(start=1,end=9,epitope_level='E2-consensus',
        support='SB_DISTINCT_ALLELES_GTE_2',alleles=sorted([I_ALLELE,II_ALLELE]),allele_count=2)]
    assert value['epitopes']['b_cell_epitope_map']['regions'] is None
    hotspot=value['epitopes']['b_cell_antigenic_hotspot_map']
    assert hotspot['status']=='computed_empty_unreviewed' and hotspot['hotspots']==[]
    assert hotspot['proof']['maximum_possible_score']==.35
    assert hotspot['proof']['comparison']=='STRICT_GREATER_THAN'
    assert value['epitopes']['density_per_residue'] is None


def test_legal_empty_netmhc_hit_sets_are_not_upstream_failure():
    mhc=_source_result(dict(tool_id=netmhc.TOOL,run_id='run',request_id='request',job_id='job',attempt_id='attempt',
        execution_identity='exec',execution_profile={},request_artifact=dict(sha256='0'*64)))
    for channel in mhc['channels'].values():channel['hits']=[]
    body=policy.request(encode(dict(protein_sequence=SEQ,user_sequence_id='empty',
        bepipred_input=dict(state='not_provided',artifact=None,reason_code=None),
        netmhc_input=dict(state='not_provided',artifact=None,reason_code=None),
        blast_input=dict(state='not_executed',artifact=None,reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'),timeout_seconds=5)))
    value=compute(body,dict(netmhc=mhc));tmap=value['epitopes']['t_cell_presentation_map']
    assert tmap['status']=='computed' and tmap['presentation_hotspots']==[] and tmap['evidence_regions']==[]
    assert tmap['normalization']==dict(status='not_computed',reason_code='NO_MHC_HITS',direction='1-minmax')
    assert value['epitopes']['b_cell_antigenic_hotspot_map']['proof']['maximum_possible_score']==.5


@pytest.mark.parametrize('kind,b_count,t_count',[('B',1,0),('T',0,1),('mixed',1,1),('unknown',1,0)])
def test_iedb_regions_keep_provenance_and_invalidate_predictor_only_empty_proof(kind,b_count,t_count):
    def fixture(tool):
        return _source_result(dict(tool_id=tool,run_id='run',request_id='request',job_id='job',attempt_id='attempt',
            execution_identity='exec',execution_profile={},request_artifact=dict(sha256='0'*64)))
    prior=dict(database_id='engineering-n03',iedb_hit=True,evidence_level='literature_supported',
        epitope_regions=[dict(start=3,end=7,e_level='E3-region',source_iedb_id='99',reference_id='123',epitope_type=kind)],
        contact_residues=[])
    source=fixture(blast.TOOL);source.update(scope='N03_LOCAL_IEDB_PRIOR',iedb_prior=prior)
    source['search'].update({n:prior[n] for n in ('iedb_hit','evidence_level','epitope_regions','contact_residues')})
    artifact=dict(sha256='a'*64)
    body=dict(protein_sequence=SEQ,blast_input=dict(state='available',artifact=artifact,reason_code=None))
    value=compute(body,dict(blast=source,bepipred=fixture(bepipred.TOOL)))
    maps=value['epitopes'];b=maps['b_cell_epitope_map'].get('regions') or []
    t=(maps['t_cell_presentation_map'] or {}).get('evidence_regions') or []
    assert (len(b),len(t))==(b_count,t_count)
    for region in b+t:
        assert region['evidence_provenance']==dict(source_iedb_id='99',reference_id='123',source_artifact=artifact)
    assert maps['b_cell_antigenic_hotspot_map']['hotspots'] is None
    assert maps['b_cell_antigenic_hotspot_map']['proof'] is None


def test_runtime_binds_real_result_refs_and_n07_verifies_n06(rt):
    bepi=finish_source(rt,bepipred.TOOL,'bepi');mhc=finish_source(rt,netmhc.TOOL,'mhc')
    queued=rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id']),'n06',policy.TOOL)
    final=rt.dispatch(queued['job_id']);result=rt.result(final['job_id'])
    assert final['state']=='succeeded' and result['status']=='maps_unreviewed'
    assert result['execution']['sources_verified'] is True
    assert result['epitopes']['t_cell_presentation_map']['presentation_hotspots'][0]['start']==1
    hotspot=rt.n06_hotspot_input(final['job_id'],SEQ)
    assert hotspot['state']=='available' and hotspot['hotspots']==[] and hotspot['reason_code'] is None
    n07=rt.submit_sequence(encode(dict(protein_sequence=SEQ,user_sequence_id='n07',hotspot_input=hotspot,
        timeout_seconds=5)),'n07',glycosylation.TOOL)
    n07=rt.dispatch(n07['job_id']);n07_result=rt.result(n07['job_id'])
    assert n07['state']=='succeeded'
    assert n07_result['hotspot_assessment']['source_verification']=='VERIFIED_N06_ARTIFACT_REF'
    assert n07_result['hotspot_assessment']['status']=='NOT_PERFORMED'
    assert n07_result['hotspot_assessment']['source_hotspot_status']=='computed_empty_unreviewed'
    assert n07_result['method_summary']['hotspot_source_artifact_validated'] is True
    assert n07_result['method_summary']['hotspot_full_chain_validated'] is False
    assert n07_result['method_summary']['hotspot_scientific_consumption'] is False
    assert any(row['code']=='N06_EMPTY_HOTSPOT_BOUND_UNREVIEWED' for row in n07_result['warnings'])


def test_n03_hit_no_hit_and_unavailable_are_reconnected_without_epitope_semantics(rt):
    bepi=finish_source(rt,bepipred.TOOL,'bepi-blast');mhc=finish_source(rt,netmhc.TOOL,'mhc-blast')
    hit=finish_blast_source(rt,'blast-hit')
    queued=rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id'],hit['job_id']),'n06-blast-hit',policy.TOOL)
    final=rt.dispatch(queued['job_id']);value=rt.result(final['job_id']);fact=value['blast_similarity']
    assert final['state']=='succeeded' and fact['state']=='available' and fact['search_status']=='hit'
    assert fact['raw_hsp_count']==fact['qualifying_hsp_count']==1
    assert fact['database']['database_id']=='engineering-n03' and fact['database']['manifest_sha256']=='a'*64
    assert fact['interpretation']=='ORDINARY_PROTEIN_SIMILARITY_ONLY'
    assert fact['iedb_evidence'] is fact['epitope_evidence_level'] is fact['epitope_regions'] is fact['contact_residues'] is None
    assert value['method_summary']['blast_source_bound'] and not value['method_summary']['iedb_evidence_generated']

    no_hit=finish_blast_source(rt,'blast-no-hit',hit=False)
    queued=rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id'],no_hit['job_id']),
        'n06-blast-no-hit',policy.TOOL)
    value=rt.result(rt.dispatch(queued['job_id'])['job_id'])['blast_similarity']
    assert value['state']=='available' and value['search_status']=='no_hit'
    assert value['raw_hsp_count']==value['qualifying_hsp_count']==0

    failed=finish_blast_source(rt,'blast-failed',error='TOOL_FAILED')
    queued=rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id'],failed['job_id']),
        'n06-blast-unavailable',policy.TOOL)
    result=rt.result(rt.dispatch(queued['job_id'])['job_id'])
    assert result['status']=='maps_unreviewed' and result['blast_similarity']['state']=='upstream_unavailable'
    assert result['blast_similarity']['reason_code']=='TOOL_FAILED'
    assert any(row['code']=='N03_UPSTREAM_UNAVAILABLE' for row in result['warnings'])


def test_n03_source_sequence_database_and_hash_are_reverified(rt):
    bepi=finish_source(rt,bepipred.TOOL,'bepi-blast-invalid');mhc=finish_source(rt,netmhc.TOOL,'mhc-blast-invalid')
    source=finish_blast_source(rt,'blast-sequence')
    body=encode(dict(protein_sequence='A'*len(SEQ),user_sequence_id='blast-mismatch',
        bepipred_input=dict(state='not_provided',artifact=None,reason_code=None),
        netmhc_input=dict(state='not_provided',artifact=None,reason_code=None),
        blast_input=rt.source_input(source['job_id'],blast.TOOL),timeout_seconds=5))
    with pytest.raises(RuntimeFault) as exc:rt.submit_sequence(body,'blast-sequence-mismatch',policy.TOOL)
    assert exc.value.code=='OUTPUT_INVALID'

    bad_database=finish_blast_source(rt,'blast-db-mismatch',database_mismatch=True)
    queued=rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id'],bad_database['job_id']),
        'n06-blast-db-mismatch',policy.TOOL)
    final=rt.dispatch(queued['job_id']);value=rt.result(final['job_id'])
    assert final['state']=='failed' and final['error_code']=='OUTPUT_INVALID' and value['blast_similarity'] is None

    intact=finish_blast_source(rt,'blast-tamper')
    queued=rt.submit_sequence(n06_body(rt,bepi['job_id'],mhc['job_id'],intact['job_id']),
        'n06-blast-tamper',policy.TOOL)
    ref=next(row for row in intact['artifacts'] if row['role']=='result')
    with rt._db() as db:
        relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    (rt.root/relative).write_bytes(b'changed')
    final=rt.dispatch(queued['job_id'])
    assert final['state']=='failed' and final['error_code']=='HASH_MISMATCH' and final['attempt_id'] is None


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
        blast_input=dict(state='not_executed',artifact=None,reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'),timeout_seconds=5))
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
