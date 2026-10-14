"""Independent boundary and local real-file tests for the R-58 probe."""
import copy
import importlib.util
from itertools import combinations, product
import json
from pathlib import Path
import subprocess
import sys

import pytest

from t01_structure_mapping.probe import ProbeError, exact_embedding, parse_local, propose, read_sequence, sha

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'tests/fixtures/structure_mapping'
CONTRACT=ROOT/'工作流设计/02-数据契约/tool-interface-v0.1/structure_mapping'
spec=importlib.util.spec_from_file_location('mapping_validator_test',CONTRACT/'validate_mapping.py')
V=importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


def toy_mapping():
    return propose('ARG',parse_local(FIX/'synthetic/partial-icode.pdb'),evidence_kind='synthetic_fixture')


def test_exact_embedding_matches_exhaustive_combinatorial_oracle():
    # No aligner or coordinate parser supplies expected values.
    for n in range(1,6):
        for letters in product('AC',repeat=n):
            sequence=''.join(letters)
            for m in range(1,n+1):
                for small in product('AC',repeat=m):
                    observed=''.join(small)
                    matches=[list(p) for p in combinations(range(1,n+1),m) if ''.join(sequence[i-1] for i in p)==observed]
                    state,positions=exact_embedding(sequence,observed)
                    expected='no_match' if not matches else 'ambiguous' if len(matches)>1 else 'exact' if sequence==observed else 'partial_unique'
                    assert state==expected
                    assert positions==(matches[0] if len(matches)==1 else None)


@pytest.mark.parametrize('name,chain,model_serial',[('partial-icode.pdb','A',None),('partial-icode.cif','AUTH',7)])
def test_partial_null_and_author_insertion_identity(name,chain,model_serial):
    inventory=parse_local(FIX/'synthetic'/name)
    result=propose('ARG',inventory,evidence_kind='synthetic_fixture')
    assert V.validate_mapping(result)==[]
    assert result['mapping_status']=='unverified'
    assert result['target_chain_id']==chain
    assert result['model_serial']==model_serial
    assert [e['structure_residue'] is None for e in result['entries']]==[False,True,False]
    assert [e['structure_residue']['insertion_code'] for e in result['entries'] if e['structure_residue']]==['','A']
    assert inventory['raw_atom_count']==inventory['parsed_atom_count']==8


def test_mmcif_author_labels_and_coordinates_do_not_get_renumbered():
    inventory=parse_local(FIX/'synthetic/partial-icode.cif')
    residues=inventory['models'][0]['chains'][0]['residues']
    assert [(r['chain_id'],r['res_seq'],r['insertion_code'],r['label_asym_id'],r['label_seq_id']) for r in residues]==[('AUTH',42,'','LABEL','1'),('AUTH',42,'A','LABEL','2')]


def test_multiple_matching_chains_cannot_be_resolved_by_first_or_requested_chain():
    inventory=parse_local(FIX/'synthetic/partial-icode.pdb')
    second=copy.deepcopy(inventory['models'][0]['chains'][0])
    second['chain_id']='B'
    for r in second['residues']:
        r['chain_id']='B'
    inventory['models'][0]['chains'].append(second)
    for requested in (None,'A','B'):
        result=propose('ARG',inventory,evidence_kind='synthetic_fixture',requested_chain=requested)
        assert result['mapping_status']=='unreliable'
        assert result['target_chain_id'] is None
        assert all(e['reason']=='unresolved_mapping' for e in result['entries'])
        assert V.validate_mapping(result)==[]


def test_ingestion_first_chain_can_differ_from_unique_design_candidate():
    inventory=parse_local(FIX/'synthetic/partial-icode.pdb')
    nonmatching=copy.deepcopy(inventory['models'][0]['chains'][0])
    nonmatching['chain_id']='Z'
    for r in nonmatching['residues']:
        r.update(chain_id='Z',one_letter='W',residue_name='TRP')
    inventory['models'][0]['chains'].insert(0,nonmatching)
    result=propose('ARG',inventory,evidence_kind='synthetic_fixture')
    assert result['ingestion_chain_id']=='Z'
    assert result['target_chain_id']=='A'
    assert result['fixed_chain_ids']==['Z']
    assert V.validate_mapping(result)==[]


def test_multiple_models_need_explicit_selection():
    inventory=parse_local(FIX/'synthetic/partial-icode.pdb')
    second=copy.deepcopy(inventory['models'][0]);second['model_index']=1;second['model_serial']=2
    inventory['models'].append(second)
    result=propose('ARG',inventory,evidence_kind='synthetic_fixture')
    assert result['mapping_status']=='unreliable'
    assert result['model_index'] is None
    assert propose('ARG',inventory,evidence_kind='synthetic_fixture',model_index=1)['mapping_status']=='unverified'
    assert propose('ARG',inventory,evidence_kind='synthetic_fixture',model_index=99)['mapping_status']=='unreliable'


@pytest.mark.parametrize('replacement',['MSE','UNK'])
def test_nonstandard_residue_is_retained_and_never_converted_to_standard(tmp_path,replacement):
    text=(FIX/'synthetic/partial-icode.pdb').read_text().replace('ALA',replacement)
    path=tmp_path/'unknown.pdb';path.write_text(text)
    inventory=parse_local(path)
    first=inventory['models'][0]['chains'][0]['residues'][0]
    assert first['residue_name']==replacement and first['one_letter'] is None
    assert propose('ARG',inventory,evidence_kind='synthetic_fixture')['mapping_status']=='unreliable'


def test_altloc_atoms_are_all_preserved_for_review(tmp_path):
    lines=(FIX/'synthetic/partial-icode.pdb').read_text().splitlines(True)
    atom=lines[2]
    lines[2]=atom[:16]+'A'+atom[17:]
    other=atom[:6]+f'{99:5d}'+atom[11:16]+'B'+atom[17:]
    lines.insert(3,other)
    path=tmp_path/'alt.pdb';path.write_text(''.join(lines))
    inventory=parse_local(path)
    assert inventory['raw_atom_count']==9
    assert inventory['models'][0]['chains'][0]['residues'][0]['altlocs']==['','A','B']
    result=propose('ARG',inventory,evidence_kind='synthetic_fixture')
    assert any(i['code']=='ALTLOC_REVIEW' for i in result['issues'])


def test_duplicate_atom_is_not_silently_dropped(tmp_path):
    lines=(FIX/'synthetic/partial-icode.pdb').read_text().splitlines(True)
    lines.insert(2,lines[1])
    path=tmp_path/'dup.pdb';path.write_text(''.join(lines))
    with pytest.raises(ProbeError):parse_local(path)


@pytest.mark.parametrize('change', ['missing_auth','nonnumeric_auth','nonfinite','ragged'])
def test_mmcif_guard_cases(tmp_path,change):
    text=(FIX/'synthetic/partial-icode.cif').read_text()
    if change=='missing_auth':text=text.replace('_atom_site.auth_seq_id','_atom_site.unused_id')
    if change=='nonnumeric_auth':text=text.replace(' 42 ALA AUTH',' 42A ALA AUTH')
    if change=='nonfinite':text=text.replace(' 0 0 0 1 20 ',' nan 0 0 1 20 ',1)
    if change=='ragged':text=text.replace('ATOM 8 O O . GLY','ATOM O O . GLY')
    path=tmp_path/'bad.cif';path.write_text(text)
    with pytest.raises((ProbeError,ValueError,KeyError)):parse_local(path)


@pytest.mark.parametrize('text',['','broken file','>a\nARG\n>b\nARG\n','ARG-','AR G'])
def test_invalid_inputs_rejected(tmp_path,text):
    path=tmp_path/'bad.txt';path.write_text(text)
    with pytest.raises(ProbeError):read_sequence(path)


@pytest.mark.parametrize('change',['length','order','letter','duplicate_address','hash','chain','status','namespace','false_verified'])
def test_mapping_contract_rejects_corruption(change):
    value=toy_mapping()
    if change=='length':value['entries'].pop()
    if change=='order':value['entries'][0]['sequence_position']=3
    if change=='letter':value['entries'][0]['sequence_residue']='W'
    if change=='duplicate_address':value['entries'][2]['structure_residue']['insertion_code']=''
    if change=='hash':value['sequence_sha256']='0'*64
    if change=='chain':value['target_chain_id']='B'
    if change=='status':value['usable_for_pipeline']=True
    if change=='namespace':value['parser']['chain_namespace']='auth_asym_id'
    if change=='false_verified':value['mapping_status']='verified';value['review_required']=False
    assert V.validate_mapping(value)


def test_mapping_is_bound_to_actual_request_sequence_structure_and_status():
    value=toy_mapping()
    assert V.validate_mapping(value,sequence='ARG',structure_sha256=value['structure_sha256'],expected_status='unverified')==[]
    assert V.validate_mapping(value,sequence='AAA')
    assert V.validate_mapping(value,structure_sha256='0'*64)
    assert V.validate_mapping(value,expected_status='verified')


def test_reused_local_sample_bytes_match_original_capture_manifest():
    manifest=json.loads((FIX/'real/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    for sample in manifest['samples']:
        for f in sample['files']:
            data=(FIX/'real'/f['path']).read_bytes()
            assert sha(data)==f['sha256'] and len(data)==f['bytes']
        seq=read_sequence(FIX/'real'/f"{sample['sample_id']}.fasta")
        assert sha(seq.encode())==sample['sequence_sha256']


def test_real_1ubq_independent_sequence_maps_all_76_positions():
    structure=FIX/'real/1UBQ.cif';before=structure.read_bytes()
    inventory=parse_local(structure)
    sequence=read_sequence(FIX/'real/1UBQ.fasta')
    result=propose(sequence,inventory,evidence_kind='local_input')
    assert result['target_chain_id']=='A'
    assert len(result['entries'])==76
    assert [e['structure_residue']['res_seq'] for e in result['entries']]==list(range(1,77))
    assert result['entries'][0]['structure_residue']['residue_name']=='MET'
    assert result['entries'][-1]['structure_residue']['residue_name']=='GLY'
    assert result['mapping_status']=='unverified' and not result['usable_for_pipeline']
    assert structure.read_bytes()==before
    assert V.validate_mapping(result)==[]


def test_real_5xzc_multichain_ca_only_cannot_be_silent_success():
    inventory=parse_local(FIX/'real/5XZC.cif')
    result=propose(read_sequence(FIX/'real/5XZC.fasta'),inventory,evidence_kind='local_input')
    assert result['mapping_status']=='unreliable' and result['target_chain_id'] is None
    assert [c['chain_id'] for c in result['chain_candidates'] if c['match_status']=='ambiguous']==['B','C','D','E']
    assert all(r['atom_names']==['CA'] for m in inventory['models'] for c in m['chains'] for r in c['residues'])
    assert V.validate_mapping(result)==[]


def test_cli_writes_evidence_and_refuses_existing_output(tmp_path):
    out=tmp_path/'run'
    command=[sys.executable,str(ROOT/'scripts/probe_structure_mapping.py'),'--structure',str(FIX/'synthetic/partial-icode.pdb'),'--sequence-file',str(FIX/'synthetic/input.fasta'),'--output-dir',str(out),'--evidence-kind','synthetic_fixture']
    first=subprocess.run(command,capture_output=True)
    assert first.returncode==0,first.stderr
    before=(out/'mapping.json').read_bytes()
    second=subprocess.run(command,capture_output=True)
    assert second.returncode==20
    assert (out/'mapping.json').read_bytes()==before
    assert json.loads((out/'probe_result.json').read_text(encoding='utf-8'))['scientific_acceptance']=='NOT_RUN'


def test_reparse_checker_detects_fabricated_author_number(tmp_path):
    path=tmp_path/'mapping.json'
    value=toy_mapping()
    value['entries'][0]['structure_residue']['res_seq']=999
    path.write_text(json.dumps(value),encoding='utf-8')
    # Shape/hash binding cannot prove an address exists; the independent reparse does.
    assert V.validate_mapping(value)==[]
    result=subprocess.run([sys.executable,str(ROOT/'scripts/check_structure_mapping.py'),'--mapping',str(path),'--structure',str(FIX/'synthetic/partial-icode.pdb'),'--sequence-file',str(FIX/'synthetic/input.fasta')],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==1
    assert 'fresh local parse' in result.stdout


def test_freesasa_file_check_rejects_claiming_unverified_mapping_as_verified(tmp_path):
    spec=importlib.util.spec_from_file_location('common_interface_test',CONTRACT.parent/'validate.py')
    common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
    value=toy_mapping()
    mapping_path=tmp_path/'mapping.json';mapping_path.write_text(json.dumps(value),encoding='utf-8')
    request=common.strict_json(CONTRACT.parent/'examples/freesasa-mapping-pending/request.json')
    request['inputs']['mapping']={'path':'mapping.json','sha256':sha(mapping_path.read_bytes())}
    assert common.check_files(request,None,tmp_path,tmp_path)==[]
    request['inputs']['mapping_status']='verified'
    assert 'mapping_status does not match request' in '\n'.join(common.check_files(request,None,tmp_path,tmp_path))
