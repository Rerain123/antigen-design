"""N05 admission and official-format parser tests before licensed CLI execution."""
from concurrent.futures import ThreadPoolExecutor
import os

import pytest

from t01_phase1_real.common import REPO, RuntimeFault, decode, encode, sha, validate as old_validate
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.contracts import validate
from t01_phase1_real.development.netmhc import policy
from t01_phase1_real.development.netmhc.result import parse_channel

SEQ='MRYGFVRKKHRGLFLTTVAALPIWNPISEFVKWYKSHKLSQHCIRICGHLCQKHLDMFLSVIGQRWPIDVFSSVFDHQVSAIGSDIIWWFLKLFLVSFFFFF'
I_ALLELE='HLA-A02:01'
II_ALLELE='HLA-DPA10202-DPB11901'
OFFICIAL=REPO/'discovery/t01-phase1-real/w2/netmhc-integration-20260907/official'


def body(**changes):
    value=dict(protein_sequence=SEQ,user_sequence_id='../id | 用户\n metadata only',host_species='Homo sapiens',
        mhc_i_alleles=[I_ALLELE],mhc_ii_alleles=[II_ALLELE],timeout_seconds=180)
    value.update(changes);return encode(value)


def mhc_i(*rows,header='%Rank_EL'):
    ident=policy.sequence_id(SEQ)
    default=(
        f'1 {I_ALLELE} MRYGFVRKK MRYGFVRKK 0 0 0 0 0 MRYGFVRKK {ident} 0.9 9.0 <= SB',
        f'5 {I_ALLELE} FVRKKHRGLF FVRKKHRG 0 0 0 0 0 FVRKKHRGLF {ident} 0.5 2.0 <= WB',
        f'22 {I_ALLELE} PIWNPISEF PIWNPISEF 0 0 0 0 0 PIWNPISEF {ident} 0.1 20.0')
    values=rows or default
    return ('# NetMHCpan version 4.2e\n'
        f' Pos MHC Peptide Core Of Gp Gl Ip Il Icore Identity Score_EL {header} BindLevel\n'
        + '\n'.join(values)+'\n').encode()


def mhc_ii(*rows,header='%Rank_EL'):
    ident=policy.sequence_id(SEQ)
    default=(
        f'22 {II_ALLELE} PIWNPISEFVKWYKS 1 KYWKVFESI 0.641 1 {ident} 0.147204 8.15 NA',
        f'29 {II_ALLELE} EFVKWYKSHKLSQHC 3 KWYKSHKLS 0.536 0 {ident} 0.128036 9.16 NA <= WB')
    values=rows or default
    return ('# NetMHCIIpan version 4.3k\n'
        f' Pos MHC Peptide Of Core Core_Rel Inverted Identity Score_EL {header} Exp_Bind BindLevel\n'
        + '\n'.join(values)+'\n').encode()


@pytest.fixture
def rt(tmp_path):
    if os.name!='nt':pytest.skip('Current trusted-local task runtime requires Windows')
    return Runtime(tmp_path/'runtime')


@pytest.mark.parametrize('sequence',['','A'*14,'A'*20001,'acdefghiklmnpqr','ACDEFGHIKLMNPQX','ACDEFGHIKLMNPQ*','ACDEFGHIKLMN PQ',None])
def test_invalid_sequence_precedes_n05_admission(rt,sequence):
    with pytest.raises(RuntimeFault):rt.submit_sequence(body(protein_sequence=sequence),'bad',policy.TOOL)
    with rt._db() as db:
        assert all(db.execute('SELECT count(*) FROM '+name).fetchone()[0]==0 for name in ['runs','jobs','artifacts','idempotency'])


@pytest.mark.parametrize('changes',[
    dict(host_species=''),dict(host_species=' human '),dict(host_species=None),dict(mhc_i_alleles=[]),dict(mhc_i_alleles=[I_ALLELE]*2),
    dict(mhc_i_alleles=['HLA A02:01']),dict(mhc_ii_alleles=[]),dict(mhc_ii_alleles=[II_ALLELE]*16),dict(timeout_seconds=True),
    dict(timeout_seconds=0),dict(timeout_seconds=901),dict(threshold=.5),dict(command='arbitrary')])
def test_exact_request_requires_explicit_alleles_and_no_science_parameters(changes):
    with pytest.raises(RuntimeFault):policy.request(body(**changes))


def test_n05_atomic_registration_and_schema_extension(rt):
    raw=body()
    with ThreadPoolExecutor(4) as pool:
        jobs=list(pool.map(lambda _:Runtime(rt.root).submit_sequence(raw,'same',policy.TOOL),range(8)))
    assert len({job['job_id'] for job in jobs})==1
    job=jobs[0]
    assert job['tool_id']==policy.TOOL and job['node_id']=='N05' and not job['usable_for_pipeline'] and job['review_required']
    validate(job,'job')
    with pytest.raises(RuntimeFault):old_validate(job,'job')
    with pytest.raises(RuntimeFault) as exc:rt.submit_sequence(raw+b' ','same',policy.TOOL)
    assert exc.value.code=='IDEMPOTENCY_CONFLICT'


def test_user_provided_archives_and_local_academic_image_are_pinned():
    receipt=policy.verify_assets()
    assert receipt['status']=='READY' and receipt['qualification']=='LOCAL_ACADEMIC_DEVELOPMENT'
    assert receipt['image_id']==policy.IMAGE and receipt['license_record']['commercial_or_production_permission_inferred'] is False
    assert receipt['components']['mhc_i']['observed_version']=='NetMHCpan version 4.2e'
    assert receipt['components']['mhc_ii']['observed_version']=='NetMHCIIpan version 4.3k'
    assert policy.allele_inventory('mhc_i')[I_ALLELE]=='HLA-A*02:01'
    assert policy.allele_inventory('mhc_ii')[II_ALLELE]==II_ALLELE


def test_admission_rejects_alleles_absent_from_pinned_package_inventories():
    with pytest.raises(RuntimeFault) as exc:policy.request(body(mhc_i_alleles=['HLA-NOT-REAL']))
    assert exc.value.code=='INVALID_REQUEST' and 'package-local' in exc.value.message
    with pytest.raises(RuntimeFault) as exc:policy.request(body(mhc_ii_alleles=['HLA-NOT-REAL']))
    assert exc.value.code=='INVALID_REQUEST' and 'package-local' in exc.value.message


def test_public_official_snapshots_are_bound_but_not_treated_as_packages():
    source=decode((OFFICIAL/'source.json').read_bytes())
    assert source['qualification']=='PUBLIC_WEB_SERVICE_REFERENCE_ONLY' and not source['standalone_package_substitute']
    for entry in source['files']:
        raw=(OFFICIAL/entry['path']).read_bytes()
        assert len(raw)==entry['bytes'] and sha(raw)==entry['sha256']


def test_mhc_i_parser_maps_one_based_coordinates_and_consumes_bindlevel():
    value=parse_channel(mhc_i(),SEQ,[I_ALLELE],'mhc_i')
    assert value['status']=='parsed_unreviewed' and value['version']=='4.2e' and len(value['hits'])==3
    first=value['hits'][0]
    assert first['start']==1 and first['end']==9 and first['peptide_seq']==SEQ[:9]
    # Native label wins even though the synthetic rank would not meet the project SB threshold.
    assert first['percent_rank']==9.0 and first['classification']=='SB' and first['bind_level_raw']=='<= SB'
    assert [hit['classification'] for hit in value['hits']]==['SB','WB','NB']


def test_mhc_i_parser_accepts_package_native_display_allele_alias():
    ident=policy.sequence_id(SEQ)
    row=f'1 HLA-A*02:01 MRYGFVRKK MRYGFVRKK 0 0 0 0 0 MRYGFVRKK {ident} 0.9 0.1 <= SB'
    value=parse_channel(mhc_i(row),SEQ,[I_ALLELE],'mhc_i')
    assert value['status']=='parsed_unreviewed' and value['hits'][0]['allele']=='HLA-A*02:01'


def test_mhc_ii_parser_skips_inverted_and_preserves_core():
    value=parse_channel(mhc_ii(),SEQ,[II_ALLELE],'mhc_ii')
    assert value['status']=='parsed_unreviewed' and value['version']=='4.3k'
    assert value['observed_rows']==2 and value['skipped_inverted_rows']==1 and len(value['hits'])==1
    hit=value['hits'][0]
    assert hit['start']==29 and hit['end']==43 and hit['core']=='KWYKSHKLS' and hit['classification']=='WB'


def test_one_bad_row_is_partial_and_good_rows_remain():
    ident=policy.sequence_id(SEQ)
    good=f'1 {I_ALLELE} MRYGFVRKK MRYGFVRKK 0 0 0 0 0 MRYGFVRKK {ident} 0.9 0.1 <= SB'
    bad=f'5 OTHER FVRKKHRGLF FVRKKHRG 0 0 0 0 0 FVRKKHRGLF {ident} 0.5 2.0 <= WB'
    value=parse_channel(mhc_i(good,bad),SEQ,[I_ALLELE],'mhc_i')
    assert value['status']=='partial' and len(value['hits'])==1 and value['parse_failures']==1
    assert value['warnings'][0]['code']=='ROW_PARSE_FAILED'


@pytest.mark.parametrize('raw,kind,alleles',[
    (mhc_i(header='Rnk_EL'),'mhc_i',[I_ALLELE]),
    (mhc_ii(header='%Rank'),'mhc_ii',[II_ALLELE]),
    (b'# NetMHCpan version 4.1\n','mhc_i',[I_ALLELE]),
    (b'not utf8 \xff','mhc_ii',[II_ALLELE])])
def test_channel_level_format_or_version_failure_is_unavailable(raw,kind,alleles):
    value=parse_channel(raw,SEQ,alleles,kind)
    assert value['status']=='unavailable' and value['hits']==[] and value['warnings'][0]['code']=='OUTPUT_INVALID'


def test_all_native_rows_invalid_marks_only_that_channel_unavailable():
    ident=policy.sequence_id(SEQ)
    bad=f'1 OTHER MRYGFVRKK MRYGFVRKK 0 0 0 0 0 MRYGFVRKK {ident} 0.9 0.1 <= SB'
    value=parse_channel(mhc_i(bad),SEQ,[I_ALLELE],'mhc_i')
    assert value['status']=='unavailable' and value['observed_rows']==1 and value['parse_failures']==1
    assert value['warnings'][-1]['code']=='ALL_ROWS_FAILED'
