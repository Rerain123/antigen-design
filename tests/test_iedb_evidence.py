"""C20 transfer must preserve source IDs and reject misleading mappings."""
import copy
import pytest
from t01_phase1_real.development.blast.iedb import map_evidence, qualifying_subjects

SEQ='ACDEFGHIKLMNPQRSTVWY'


def evidence():
    return dict(database_id='iedb-test',metadata_sha256='a'*64,source_sql_sha256='b'*64,
        proteins=[dict(subject_id='iedb_1',sequence=SEQ)],structures=[],
        regions=[dict(subject_id='iedb_1',epitope_id='99',curated_epitope_id='123',start=3,end=7,
            mapping_status='VALIDATED_SOURCE_INTERVAL',epitope_type='B',reference_id='456',pubmed_id='789')])


def hsp(**kw):
    r=dict(subject_id='iedb_1',passes_registered_thresholds=True,percent_identity=100,
        query_coverage_percent=100,query_length=len(SEQ),subject_length=len(SEQ),query_start=1,query_end=len(SEQ),
        subject_start=1,subject_end=len(SEQ),query_alignment=SEQ,subject_alignment=SEQ,hsp_index=1)
    r.update(kw);return r


def test_exact_hit_keeps_source_coordinate_and_reference():
    r=map_evidence(SEQ,[hsp()],evidence())
    assert r['iedb_hit'] and r['evidence_level']=='literature_supported'
    row=r['epitope_regions'][0]
    assert (row['start'],row['end'],row['source_iedb_id'],row['reference_id'])==(3,7,'99','456')
    assert row['e_level']=='E3-region' and r['e4_status']=='not_applicable'


def test_no_hit_is_distinct_from_unavailable():
    r=map_evidence(SEQ,[],evidence())
    assert r['iedb_hit'] is False and r['epitope_regions']==[]
    assert r['evidence_level']=='computational_prediction'


def test_mismatch_in_epitope_rejects_transfer_but_retains_hit():
    query=SEQ[:4]+'A'+SEQ[5:]
    r=map_evidence(query,[hsp(query_alignment=query,percent_identity=94)],evidence())
    assert r['iedb_hit'] and not r['epitope_regions']
    assert r['warnings'][0]['code']=='IEDB_INTERVAL_UNMAPPABLE'
    assert r['matched_proteins'][0]['evidence_note']=='基于同源蛋白表位数据'


def test_matching_epitope_on_homolog_keeps_homology_caveat():
    query='Y'+SEQ[1:]
    r=map_evidence(query,[hsp(query_alignment=query,percent_identity=94)],evidence())
    assert r['epitope_regions'][0]['evidence_note']=='基于同源蛋白表位数据'


def test_complex_id_alone_never_produces_e4():
    e=evidence();e['structures']=[dict(subject_id='iedb_1',complex_id='12',pdb_id='1ABC')]
    r=map_evidence(SEQ,[hsp()],e)
    assert r['contact_residues']==[] and r['e4_status']=='unavailable'
    assert r['warnings'][0]['code']=='IEDB_COMPLEX_COORDINATES_UNAVAILABLE'


def test_source_sequence_mismatch_fails():
    e=evidence();e['proteins'][0]['sequence']='Y'+SEQ[1:]
    with pytest.raises(ValueError,match='Subject alignment'):map_evidence(SEQ,[hsp()],e)


def test_below_c20_threshold_never_promoted():
    assert not map_evidence(SEQ,[hsp(percent_identity=69)],evidence())['iedb_hit']
    assert not map_evidence(SEQ,[hsp(query_coverage_percent=79)],evidence())['iedb_hit']


def test_metadata_retrieval_uses_exact_coverage_not_rounded_native_value():
    def row(subject,end,identity=70):
        return '\t'.join(map(str,['query',subject,identity,end,0,0,1,end,1,end,0,50,233,233,80,'A'*end,'A'*end,'title']))
    assert qualifying_subjects('\n'.join([row('iedb_1',186),row('iedb_2',187),row('iedb_3',233,69)]))=={'iedb_2'}
