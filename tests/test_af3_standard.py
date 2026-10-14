import pytest

from src.t01_phase1_real.development.af3.native_worker import hmmer_identity
from src.t01_phase1_real.development.af3.standard import columns, select
from src.t01_phase1_real.development.af3 import policy


def test_af3_columns_allow_native_missing_auth_comp_id():
    raw = b'''data_x
loop_
_atom_site.id
_atom_site.group_PDB
_atom_site.label_asym_id
_atom_site.auth_asym_id
_atom_site.pdbx_PDB_model_num
_atom_site.label_alt_id
_atom_site.label_seq_id
_atom_site.auth_seq_id
_atom_site.label_comp_id
_atom_site.pdbx_PDB_ins_code
_atom_site.label_atom_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.B_iso_or_equiv
_atom_site.occupancy
1 ATOM A A 1 . 1 1 ALA . CA 1 2 3 90 1
#
'''
    parsed, count = columns(raw)
    assert count == 1
    assert 'auth_comp_id' not in parsed


def test_af3_numeric_zero_clash_is_accepted_and_non_binary_rejected():
    rows = [
        {'model_id': 'm0', 'seed': 1, 'sample_index': 0, 'ptm': 0.86,
         'raw_scores': {'has_clash': 0.0}},
        {'model_id': 'm1', 'seed': 1, 'sample_index': 1, 'ptm': 0.85,
         'raw_scores': {'has_clash': 0.0}},
    ]
    selected, _ = select(rows)
    assert selected['model_id'] == 'm0'

    with pytest.raises(Exception):
        select([dict(rows[0], raw_scores={'has_clash': 2.0})])


def test_af3_hmmer_identity_requires_all_explicit_executables(tmp_path):
    paths = {}
    for name in policy.HMMER_BINARIES:
        path = tmp_path / name
        path.write_text('#!/bin/sh\n', encoding='utf-8')
        paths[name] = str(path)
    assert hmmer_identity(paths) == paths
    missing = dict(paths)
    missing['nhmmer'] = str(tmp_path / 'missing-nhmmer')
    with pytest.raises(Exception, match='HMMER executable'):
        hmmer_identity(missing)


def test_af3_hmmer_arguments_are_stable_and_explicit():
    assert policy.hmmer_arguments() == (
        '--jackhmmer_binary_path=/hmmer/bin/jackhmmer',
        '--nhmmer_binary_path=/hmmer/bin/nhmmer',
        '--hmmalign_binary_path=/hmmer/bin/hmmalign',
        '--hmmsearch_binary_path=/hmmer/bin/hmmsearch',
        '--hmmbuild_binary_path=/hmmer/bin/hmmbuild',
    )


@pytest.mark.parametrize('damage', [None, 'multiple', 'invalid_memory', 'missing_uuid'])
def test_af3_assigned_gpu_uses_actual_identity(monkeypatch, damage):
    from src.t01_phase1_real.development.af3 import native_worker
    from src.t01_phase1_real.gpu_device import POLICY
    text='NVIDIA A100-SXM4-40GB, GPU-00000000-0000-4000-8000-000000000001, 40960'
    if damage=='multiple':text+='\n'+text
    elif damage=='invalid_memory':text=text.replace('40960','nan')
    elif damage=='missing_uuid':text=text.replace('GPU-00000000-0000-4000-8000-000000000001','missing')
    monkeypatch.setattr(native_worker.subprocess,'check_output',lambda *a,**k:text)
    if damage:
        with pytest.raises(Exception):native_worker.gpu_identity({'allocation_policy':POLICY})
    else:
        value=native_worker.gpu_identity({'allocation_policy':POLICY})
        assert value['memory_mib']==40960 and value['name']=='NVIDIA A100-SXM4-40GB'
