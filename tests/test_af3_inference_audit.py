import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from inspect_af3_inference import AA, atom_rows, audit_sample
from prepare_af3_data_search import SEQUENCE


def sample_fixture(tmp_path):
    # Synthetic parser fixture only, never a scientific acceptance result.
    sample = tmp_path / 'target' / 'seed-1_sample-0'
    sample.mkdir(parents=True)
    aa = {value:key for key,value in AA.items()}
    fields = 'label_asym_id label_seq_id label_comp_id label_atom_id Cartn_x Cartn_y Cartn_z B_iso_or_equiv'.split()
    text = 'loop_\n' + ''.join('_atom_site.' + f + '\n' for f in fields)
    for i, residue in enumerate(SEQUENCE,1):
        for name in ('N','CA','C','O'):
            text += f'A {i} {aa[residue]} {name} 1 2 3 90\n'
    prefix = sample / 'target_seed-1_sample-0'
    Path(str(prefix)+'_model.cif').write_text(text+'#\n')
    Path(str(prefix)+'_confidences.json').write_text(json.dumps({'atom_plddts':[90]*304}))
    Path(str(prefix)+'_summary_confidences.json').write_text(json.dumps({'ptm':0.8}))
    return sample, prefix


def test_prefixed_native_names_and_ca_scale(tmp_path):
    sample, _ = sample_fixture(tmp_path)
    result = audit_sample(sample)
    assert result['residues'] == 76
    assert result['mean_ca_plddt'] == pytest.approx(0.9)


def test_mismatched_confidence_rejected(tmp_path):
    sample, prefix = sample_fixture(tmp_path)
    Path(str(prefix)+'_confidences.json').write_text(json.dumps({'atom_plddts':[89]*304}))
    with pytest.raises(ValueError,match='confidence mismatch'):
        audit_sample(sample)


def test_truncated_atom_row_rejected():
    with pytest.raises(ValueError,match='Incomplete atom row'):
        atom_rows('loop_\n_atom_site.id\n_atom_site.type_symbol\n1 C\n2\n#\n')
