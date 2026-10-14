"""Build explicitly synthetic boundary cases from the existing local 1UBQ copy."""
from copy import deepcopy
import argparse
import importlib.util
import json
from pathlib import Path
import sys

from Bio.PDB import MMCIFIO
from Bio.PDB.MMCIF2Dict import MMCIF2Dict

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]
sys.path.insert(0, str(ROOT/'src'))
from t01_structure_mapping.probe import parse_local, propose, read_sequence, sha
from t01_structure_mapping.sasa_probe import prepare_pdb


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def generate_inputs(directory):
    source = ROOT/'tests/fixtures/structure_mapping/real/1UBQ.cif'
    data = MMCIF2Dict(str(source))
    sequence = read_sequence(ROOT/'tests/fixtures/structure_mapping/real/1UBQ.fasta')
    keys = [k for k in data if k.startswith('_atom_site.')]
    atoms = [dict(zip(keys, values)) for values in zip(*(data[k] for k in keys))]

    def val(row, name):
        return row['_atom_site.'+name]

    definitions = [
        ('original','local_input','unverified',True,'SUCCESS',[]),
        ('missing-repeat-75','synthetic_fixture','unverified',True,'SUCCESS',[75]),
        ('insertion-42A','synthetic_fixture','unverified',True,'SUCCESS',[]),
        ('negative-author','synthetic_fixture','unverified',True,'SUCCESS',[]),
        ('multichain-unique','synthetic_fixture','unverified',True,'SUCCESS',[]),
        ('multichain-ambiguous','synthetic_fixture','unreliable',True,'SUCCESS',[]),
        ('replacement-conflict','synthetic_fixture','unreliable',False,'NOT_SCHEDULED',[]),
        ('inserted-label-77','synthetic_fixture','unreliable',False,'NOT_SCHEDULED',[]),
        ('noninteger-author','synthetic_fixture','PARSE_REJECTED',False,'NOT_SCHEDULED',[]),
        ('long-author-chain','synthetic_fixture','unverified',False,'NOT_SCHEDULED',[]),
        ('numeric-icode-collision','synthetic_fixture','unverified',True,'REJECTED',[]),
        ('unknown-atom','synthetic_fixture','unverified',True,'REJECTED',[]),
    ]
    specs = []
    for name, kind, mapping_status, scheduled, expected_run, missing in definitions:
        folder = directory/name
        folder.mkdir()
        rows = deepcopy(atoms)
        altered = deepcopy(data)
        altered['data_'] = 'SYNTHETIC_'+name.replace('-','_')
        context = ['A']
        if name=='missing-repeat-75':
            rows = [r for r in rows if not(val(r,'group_PDB')=='ATOM' and val(r,'label_seq_id')=='75')]
        for row in rows:
            if val(row,'group_PDB')!='ATOM':
                continue
            pos = val(row,'label_seq_id')
            if name=='insertion-42A' and pos=='43':
                row['_atom_site.auth_seq_id']='42'; row['_atom_site.pdbx_PDB_ins_code']='A'
            if name=='negative-author' and pos=='1':
                row['_atom_site.auth_seq_id']='-1'
            if name=='replacement-conflict' and pos=='10':
                row['_atom_site.label_comp_id']=row['_atom_site.auth_comp_id']='ALA'
            if name=='inserted-label-77' and pos=='43':
                row['_atom_site.label_seq_id']='77'
            if name=='noninteger-author' and pos=='43':
                row['_atom_site.auth_seq_id']='42A'
            if name=='long-author-chain':
                row['_atom_site.auth_asym_id']='AUTH'
            if name=='numeric-icode-collision' and pos=='43':
                row['_atom_site.auth_seq_id']='4';row['_atom_site.pdbx_PDB_ins_code']='2'
            if name=='unknown-atom' and pos=='1' and val(row,'label_atom_id')=='SD':
                row['_atom_site.label_atom_id']=row['_atom_site.auth_atom_id']='ZZZ'
        if name.startswith('multichain-'):
            context = ['A','B']
            second = []
            for source_row in atoms:
                if val(source_row,'group_PDB')!='ATOM':
                    continue
                row = deepcopy(source_row)
                row['_atom_site.auth_asym_id']='B'
                row['_atom_site.label_asym_id']='C'  # label B already denotes water in 1UBQ
                if name=='multichain-unique':
                    row['_atom_site.label_entity_id']='3'  # entity 2 is the original water entity
                    if val(row,'label_seq_id')=='1':
                        if val(row,'label_atom_id') not in {'N','CA','C','O','CB'}:
                            continue
                        row['_atom_site.auth_comp_id']=row['_atom_site.label_comp_id']='ALA'
                row['_atom_site.Cartn_x']=str(float(val(row,'Cartn_x'))+8.0)
                second.append(row)
            rows += second
            if name=='multichain-unique':
                poly_keys=[k for k in data if k.startswith('_entity_poly_seq.')]
                for k in poly_keys:
                    values=deepcopy(data[k])
                    if k.endswith('.entity_id'):values=['3']*len(values)
                    if k.endswith('.mon_id'):values[0]='ALA'
                    altered[k]+=values
                # Relevant instance/entity declarations accompany the new explicit synthetic chain.
                for k, value in [('_entity.id','3'),('_entity.type','polymer'),('_struct_asym.id','C'),('_struct_asym.entity_id','3')]:
                    if k in altered: altered[k].append(value)
            else:
                altered['_struct_asym.id'].append('C');altered['_struct_asym.entity_id'].append('1')
            # Keep all categories rectangular after adding synthetic entity/instance rows.
            for prefix in ['_entity.','_struct_asym.']:
                category=[k for k in altered if k.startswith(prefix)]
                size=max(len(altered[k]) for k in category)
                for k in category: altered[k]+=['?']*(size-len(altered[k]))
        for i,row in enumerate(rows,1): row['_atom_site.id']=str(i)
        for k in keys: altered[k]=[r[k] for r in rows]
        if name=='original':
            (folder/'input.cif').write_bytes(source.read_bytes())
        else:
            writer=MMCIFIO();writer.set_dict(altered);writer.save(str(folder/'input.cif'))
        (folder/'input.fasta').write_text('>'+name+'\n'+sequence+'\n')
        if name=='long-author-chain':context=['AUTH']
        specs.append({'id':name,'evidence_kind':kind,'model_index':0,'context_chain_ids':context,
                      'mapping_expected':mapping_status,'missing_positions_expected':missing,
                      'schedule_raw':scheduled,'raw_expected':expected_run,
                      'source_parent':'tests/fixtures/structure_mapping/real/1UBQ.cif',
                      'parent_sha256':sha(source.read_bytes()),'input_sha256':sha((folder/'input.cif').read_bytes()),
                      'interpretation':'Real local reference' if name=='original' else 'Synthetic boundary; not a held-out biological reference'})
    return specs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    output=parser.parse_args().output_dir.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise SystemExit('Use a new output directory within the project')
    output.mkdir(parents=True)
    inputs = output/'inputs'
    inputs.mkdir(exist_ok=False)
    specs = generate_inputs(inputs)
    write(output/'case_spec.json', specs)  # expectations precede preparation and scientific execution
    path=ROOT/'工作流设计/02-数据契约/tool-interface-v0.1/structure_mapping/validate_mapping.py'
    spec=importlib.util.spec_from_file_location('mapping_check',path);validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
    results=[]
    for case in specs:
        folder=inputs/case['id']
        result={'id':case['id'],'mapping_status':None,'preparation_status':'NOT_ATTEMPTED','error':None}
        try:
            inventory=parse_local(folder/'input.cif')
            mapping=propose(read_sequence(folder/'input.fasta'),inventory,evidence_kind=case['evidence_kind'])
            errors=validator.validate_mapping(mapping)
            if errors: raise ValueError(str(errors))
            write(folder/'inventory.json',inventory);write(folder/'mapping.json',mapping)
            result['mapping_status']=mapping['mapping_status']
            result['missing_positions']=[e['sequence_position'] for e in mapping['entries'] if e['reason']=='missing_structure_residue']
            if case['schedule_raw'] or case['id']=='long-author-chain':
                result['preparation_status']='STARTED'
                prep=prepare_pdb(folder/'input.cif',folder/'prepared.pdb',model_index=case['model_index'],context_chain_ids=case['context_chain_ids'])
                write(folder/'preparation.json',prep)
                result['preparation_status']='PASS'
        except Exception as error:
            result['error']=str(error)
            if result['mapping_status'] is None: result['mapping_status']='PARSE_REJECTED'
            else: result['preparation_status']='REJECTED'
        result['expected_mapping_matches']=result['mapping_status']==case['mapping_expected']
        write(folder/'prepare_result.json',result);results.append(result)
    write(output/'preparation_results.json',results)
    print(json.dumps(results,indent=2))


if __name__=='__main__': main()
