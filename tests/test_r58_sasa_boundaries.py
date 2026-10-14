"""Entity-address and local SASA bridge checks; synthetic cases grant no scientific approval."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from Bio.PDB import MMCIFIO
from Bio.PDB.MMCIF2Dict import MMCIF2Dict

from t01_structure_mapping.probe import ProbeError, exact_embedding, parse_local, propose, read_sequence
from t01_structure_mapping.sasa_probe import address, align_absolute_sasa, prepare_pdb

ROOT=Path(__file__).resolve().parents[1]
BATCH=ROOT/'discovery/t01-phase1-real/w1/r58-freesasa-boundaries-20260905'
CASES=BATCH/'prepared/inputs'


def mapping(name):
    folder=CASES/name
    return propose(read_sequence(folder/'input.fasta'),parse_local(folder/'input.cif'),evidence_kind='synthetic_fixture')


@pytest.mark.parametrize('case',json.loads((BATCH/'prepared/case_spec.json').read_text()))
def test_predeclared_mapping_boundaries(case):
    if case['mapping_expected']=='PARSE_REJECTED':
        with pytest.raises(ProbeError,match='Noninteger'):
            mapping(case['id'])
        return
    value=mapping(case['id'])
    assert value['mapping_status']==case['mapping_expected']
    assert [e['sequence_position'] for e in value['entries'] if e['reason']=='missing_structure_residue']==case['missing_positions_expected']
    assert value['usable_for_pipeline'] is False and value['review_required'] is True


def test_entity_resolves_repeated_missing_glycine_without_guessing():
    value=mapping('missing-repeat-75')
    observed=value['chain_candidates'][0]['observed_sequence']
    assert exact_embedding(value['sequence'],observed)[0]=='ambiguous'
    assert value['entries'][74]['structure_residue'] is None
    assert value['entries'][75]['structure_residue']['res_seq']==76
    assert value['method']['id']=='entity_label_or_exact_subsequence'


def mutated_cif(tmp_path, mutation):
    raw=MMCIF2Dict(str(CASES/'original/input.cif'))
    mutation(raw)
    path=tmp_path/'mutation.cif'; writer=MMCIFIO();writer.set_dict(raw);writer.save(str(path))
    return path


@pytest.mark.parametrize('mutation',[
    lambda d:d['_entity_poly_seq.num'].__setitem__(1,'1'),
    lambda d:d['_entity_poly_seq.hetero'].__setitem__(0,'y'),
    lambda d:d['_entity_poly_seq.mon_id'].__setitem__(0,'UNK'),
    lambda d:d['_entity_poly_seq.num'].__setitem__(1,'999'),
])
def test_invalid_entity_table_cannot_fall_back_to_apparent_exact_match(tmp_path,mutation):
    value=propose(read_sequence(CASES/'original/input.fasta'),parse_local(mutated_cif(tmp_path,mutation)),evidence_kind='synthetic_fixture')
    assert value['mapping_status']=='unreliable'
    assert value['chain_candidates'][0]['match_status']=='unsupported'


def test_absent_entity_table_keeps_legacy_candidate_method(tmp_path):
    def remove(raw):
        for key in list(raw):
            if key.startswith('_entity_poly_seq.'):del raw[key]
    value=propose(read_sequence(CASES/'original/input.fasta'),parse_local(mutated_cif(tmp_path,remove)),evidence_kind='synthetic_fixture')
    assert value['method']['id']=='exact_ordered_subsequence' and value['mapping_status']=='unverified'


def test_duplicate_instance_metadata_is_rejected():
    # Initial synthetic construction reused water's label B. The original attempt remains evidence of the defect.
    with pytest.raises(ProbeError,match='struct_asym'):
        parse_local(BATCH/'inputs/multichain-unique/input.cif')


def test_disagreeing_atom_entity_and_instance_are_rejected(tmp_path):
    def mutate(raw): raw['_atom_site.label_entity_id'][0]='2'
    with pytest.raises(ProbeError,match='struct_asym'):
        parse_local(mutated_cif(tmp_path,mutate))


@pytest.mark.parametrize('name,chains', [('insertion-42A',['A']),('negative-author',['A']),('multichain-unique',['A','B'])])
def test_pdb_roundtrip_keeps_identity_and_original_file(tmp_path,name,chains):
    source=CASES/name/'input.cif';before=source.read_bytes()
    result=prepare_pdb(source,tmp_path/'derived.pdb',model_index=0,context_chain_ids=chains)
    assert result['identity_and_pdb_precision_roundtrip']=='PASS'
    assert source.read_bytes()==before
    assert result['usable_for_pipeline'] is False
    observed={address(a) for a in result['atoms']}
    if name=='insertion-42A':assert ('A',42,'A',' ','LEU') in observed and ('A',42,'',' ','ARG') in observed
    if name=='negative-author':assert ('A',-1,'',' ','MET') in observed
    if name=='multichain-unique':assert {a[0] for a in observed}=={'A','B'}


@pytest.mark.parametrize('model,chains',[(None,['A']),(99,['A']),(0,[]),(0,['Z']),(0,['A','A'])])
def test_preparation_requires_explicit_valid_selection(tmp_path,model,chains):
    with pytest.raises(ProbeError):
        prepare_pdb(CASES/'original/input.cif',tmp_path/'derived.pdb',model_index=model,context_chain_ids=chains)
    assert not (tmp_path/'derived.pdb').exists()


def test_unrepresentable_chain_is_rejected_without_output(tmp_path):
    with pytest.raises(ProbeError,match='no truncation'):
        prepare_pdb(CASES/'long-author-chain/input.cif',tmp_path/'derived.pdb',model_index=0,context_chain_ids=['AUTH'])
    assert not (tmp_path/'derived.pdb').exists()


@pytest.mark.parametrize('kind',['number','coordinate','altloc','nonprotein'])
def test_unsafe_conversion_context_is_rejected_before_writing(tmp_path,kind):
    def change(raw):
        for i,position in enumerate(raw['_atom_site.label_seq_id']):
            if position!='1':continue
            if kind=='number':raw['_atom_site.auth_seq_id'][i]='10000'
            if kind=='coordinate':raw['_atom_site.Cartn_x'][i]='10000.123'
            if kind=='altloc':raw['_atom_site.label_alt_id'][i]='A'
            if kind=='nonprotein':
                raw['_atom_site.group_PDB'][i]='HETATM'
                raw['_atom_site.label_comp_id'][i]=raw['_atom_site.auth_comp_id'][i]='HEM'
    source=mutated_cif(tmp_path,change)
    with pytest.raises(ProbeError):
        prepare_pdb(source,tmp_path/'derived.pdb',model_index=0,context_chain_ids=['A'])
    assert not (tmp_path/'derived.pdb').exists()


def test_portable_validator_rejects_entity_method_on_pdb():
    path=ROOT/'工作流设计/02-数据契约/tool-interface-v0.1/structure_mapping/validate_mapping.py'
    spec=importlib.util.spec_from_file_location('entity_portable_check',path)
    validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
    value=mapping('original');value['format']='pdb';value['parser']['chain_namespace']='pdb_chain_id'
    assert 'entity label mapping requires mmCIF source metadata' in validator.validate_mapping(value)


def residue_rows(value):
    return [{**e['structure_residue'],'absolute_sasa_a2':float(e['sequence_position'])} for e in value['entries'] if e['structure_residue']]


def test_join_uses_addresses_and_preserves_null_and_order():
    value=mapping('missing-repeat-75');rows=residue_rows(value)
    result=align_absolute_sasa(value,list(reversed(rows)))
    assert result['aligned_absolute_sasa_a2']==[float(i) if i!=75 else None for i in range(1,77)]
    assert result['usable_for_pipeline'] is False


@pytest.mark.parametrize('failure',['duplicate','missing','unexpected','nan','negative'])
def test_raw_area_failures_do_not_become_missing_residues(failure):
    value=mapping('original');rows=residue_rows(value)
    if failure=='duplicate':rows.append(deepcopy(rows[0]))
    if failure=='missing':rows.pop()
    if failure=='unexpected':rows.append({**rows[0],'res_seq':999})
    if failure=='nan':rows[0]['absolute_sasa_a2']=float('nan')
    if failure=='negative':rows[0]['absolute_sasa_a2']=-1
    with pytest.raises(ProbeError):align_absolute_sasa(value,rows)


def test_ambiguous_chain_does_not_get_an_aligned_result():
    assert align_absolute_sasa(mapping('multichain-ambiguous'),[])['aligned_absolute_sasa_a2'] is None


def test_reparse_detects_misrepresented_method(tmp_path):
    sys.path.insert(0,str(ROOT/'scripts'))
    from check_structure_mapping import check
    value=mapping('original');value['method']['id']='exact_ordered_subsequence'
    path=tmp_path/'mapping.json';path.write_text(json.dumps(value))
    assert any('method' in error for error in check(path,CASES/'original/input.cif',CASES/'original/input.fasta'))


def test_recorded_raw_campaign_and_source_integrity():
    spec=importlib.util.spec_from_file_location('r58_sasa_verify',BATCH/'verify_evidence.py')
    verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
    result=verifier.verify()
    assert result['status']=='PASS' and result['raw_calculations']==6
    assert result['expert_sources_unchanged']==22 and result['production_status']=='NOT_DEPLOYED'
