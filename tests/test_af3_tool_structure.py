import copy
import pytest

from t01_phase1_real.development.af3.tool_structure import canonical_copy
from t01_phase1_real.development.af3.standard import columns
from t01_structure_mapping.input_facts import inspect_input
from t01_structure_mapping.freesasa_consumer import prepare, ConsumerError
from t01_phase1_real.common import sha


def synthetic_cif():
    tags = ('group_PDB id type_symbol label_atom_id label_alt_id label_comp_id '
            'label_asym_id label_entity_id label_seq_id pdbx_PDB_ins_code '
            'Cartn_x Cartn_y Cartn_z occupancy B_iso_or_equiv auth_seq_id '
            'auth_comp_id auth_asym_id pdbx_PDB_model_num').split()
    rows = []
    for pos in range(1, 10):
        for name, element in [('N','N'),('CA','C'),('C','C'),('O','O'),('CB','C')]:
            rows.append(f'ATOM {len(rows)+1} {element} {name} . ALA A 1 {pos} ? '
                        f'{pos*4+len(rows)%5}.0 1.0 2.0 1.0 90.0 {pos} ALA A 1\n')
    return ('data_synthetic\nloop_\n' + ''.join('_atom_site.'+t+'\n' for t in tags)
            + ''.join(rows) + '#\n').encode()


def test_verified_address_copy_unblocks_consumer_without_changing_coordinates():
    raw = synthetic_cif(); original = bytes(raw)
    facts = inspect_input(raw, declared_format='MMCIF', model_index=0, chain_selector='A')
    with pytest.raises(ConsumerError) as error:
        prepare(raw, facts, route='native_atoms', model_index=0, context_chain_ids=['A'])
    assert error.value.code == 'ICODE_UNKNOWN'
    derived, receipt = canonical_copy(raw, 'A'*9)
    facts = inspect_input(derived, declared_format='MMCIF', model_index=0, chain_selector='A')
    ledger = prepare(derived, facts, route='native_atoms', model_index=0, context_chain_ids=['A'])
    assert len(ledger['atoms']) == 45 and all(a['insertion_code']=='' for a in ledger['atoms'])
    assert raw == original and receipt['source_sha256']==sha(raw) and receipt['derived_sha256']==sha(derived)
    before, _ = columns(raw); after, _ = columns(derived)
    assert {k:v for k,v in before.items() if k!='pdbx_PDB_ins_code'} == {k:v for k,v in after.items() if k!='pdbx_PDB_ins_code'}
    assert receipt['changed_atom_row_indices']==list(range(45))
    assert canonical_copy(derived,'A'*9)[0]==derived


@pytest.mark.parametrize('old,new', [
    (b'A 1 1 ?', b'A 1 1 A'),
    (b'90.0 1 ALA', b'90.0 2 ALA'),
    (b'CA . ALA', b'CA A ALA'),
    (b' ALA A 1\n', b' ALA B 1\n'),
    (b' ? ', b" '?' "),
    (b'CA . ALA', b'CB . ALA'),
])
def test_ambiguous_or_altered_address_is_not_repaired(old,new):
    raw = synthetic_cif(); assert old in raw
    with pytest.raises(Exception): canonical_copy(raw.replace(old,new,1), 'A'*9)


def test_sequence_mismatch_is_not_repaired():
    with pytest.raises(Exception): canonical_copy(synthetic_cif(), 'G'*9)


def test_rsa_diagnostic_preserves_original_decision_and_numbers():
    from t01_phase1_real.service_api.native_report import structure_blockers
    report = dict(freesasa=dict(error_code='ICODE_UNKNOWN'), rsa=dict(
        status='output_invalid', development_result=None, out_of_domain=[
            dict(sequence_position=1,residue='M',raw_ratio=1.0697167114774169)]))
    saved = copy.deepcopy(report); rows = structure_blockers(report)
    assert [r[0] for r in rows]==['ICODE_UNKNOWN','RSA_OUT_OF_DOMAIN']
    assert '1.0697167114774169' in rows[1][1] and report == saved


def test_exact_pre_adapter_deployment_replays_only_as_historical_evidence():
    import json
    from t01_phase1_real.common import REPO, encode
    from t01_phase1_real.development.af3.result import (
        verify_source_identity, PRE_ADDRESS_SOURCE_SHA256, PRE_ADDRESS_PROFILE_SHA256)
    manifest = json.loads((REPO/'deploy/controller-latency/r03/source-manifest.json').read_bytes())
    prefix = 't01_phase1_real/development/af3/'
    recorded = {k[len(prefix):]:v for k,v in manifest.items() if k.startswith(prefix)
                and k.endswith(('.py','.json')) and '/' not in k[len(prefix):]}
    assert sha(encode(recorded))==PRE_ADDRESS_SOURCE_SHA256
    profile = dict(id='af3-v3.0.2-resident-r01', version='0.1.0', sha256=PRE_ADDRESS_PROFILE_SHA256)
    job = dict(execution_profile=profile); runtime = dict(source_sha256=recorded)
    assert verify_source_identity(job,{},runtime,historical_source=True) is False
    with pytest.raises(Exception): verify_source_identity(job,{},runtime)
    bad = copy.deepcopy(runtime); bad['source_sha256']['standard.py']='0'*64
    with pytest.raises(Exception): verify_source_identity(job,{},bad,historical_source=True)
    bad = copy.deepcopy(job); bad['execution_profile']['sha256']='0'*64
    with pytest.raises(Exception): verify_source_identity(bad,{},runtime,historical_source=True)
