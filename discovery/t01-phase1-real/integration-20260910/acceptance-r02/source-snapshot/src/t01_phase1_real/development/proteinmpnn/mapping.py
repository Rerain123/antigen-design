"""Exact source atom ledger to canonical PDB and native hard-constraint indices."""
import math
from t01_structure_mapping.freesasa_consumer import prepare, ConsumerError
from t01_structure_mapping.probe import AA
from ...common import RuntimeFault, encode, ensure, sha

BACKBONE=('N','CA','C','O')
ALPHABET='ACDEFGHIKLMNPQRSTVWY'


def project(body,source,original,facts):
    mapping=source.get('analysis',{}).get('mapping')
    ensure(isinstance(mapping,dict) and mapping.get('target_chain_id') is not None,
        'OUTPUT_INVALID','ProteinMPNN requires one uniquely mapped design chain')
    target=mapping['target_chain_id'];entries=mapping.get('entries',[])
    ensure(mapping.get('sequence')==body['protein_sequence'] and len(entries)==len(body['protein_sequence'])
        and all(r.get('reason')=='mapped' and r.get('structure_residue') is not None for r in entries),
        'OUTPUT_INVALID','Incomplete structure mapping; no missing design positions are inferred')
    candidates=mapping['chain_candidates']
    ensure(sum(c['match_status'] in ('exact','partial_unique','ambiguous','unsupported') for c in candidates)==1,
        'OUTPUT_INVALID','Ambiguous design-chain candidate set')
    chains=[c['chain_id'] for c in candidates]
    ensure(chains and len(chains)<=8 and len(chains)==len(set(chains))
        and all(len(c)==1 and c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789' for c in chains),
        'OUTPUT_INVALID','Unsupported ProteinMPNN chain namespace or context size')
    try:
        ledger=prepare(original,facts,route='native_atoms',model_index=mapping['model_index'],context_chain_ids=chains)
    except ConsumerError as exc:raise RuntimeFault('OUTPUT_INVALID','Structure ledger rejected: '+exc.code+' / '+str(exc)) from exc
    residues={}
    for atom in ledger['atoms']:
        key=(atom['chain_id'],atom['author_seq_id'],atom['insertion_code'])
        if key not in residues:residues[key]=dict(name=atom['residue_name'],atoms={},raw_residue_id=atom['raw_residue_id'])
        ensure(residues[key]['name']==atom['residue_name'] and atom['atom_name'] not in residues[key]['atoms'],
            'OUTPUT_INVALID','Duplicate or inconsistent backbone residue identity')
        residues[key]['atoms'][atom['atom_name']]=atom
    target_keys=[]
    for index,row in enumerate(entries,1):
        address=row['structure_residue'];key=(address['chain_id'],str(address['res_seq']),address['insertion_code'])
        ensure(row['sequence_position']==index and row['sequence_residue']==body['protein_sequence'][index-1]
            and key in residues and key[0]==target and AA.get(residues[key]['name'])==row['sequence_residue'],
            'OUTPUT_INVALID','FIXED/RESTRICTED coordinate conversion cannot be proven')
        target_keys.append(key)
    ensure(len(set(target_keys))==len(target_keys) and set(target_keys)=={k for k in residues if k[0]==target},
        'OUTPUT_INVALID','Target mapping does not bijectively cover structure residues')
    rows=[];lines=[];chain_sequences={};serial=0
    for chain in chains:
        keys=target_keys if chain==target else [k for k in residues if k[0]==chain]
        ensure(0<len(keys)<=1000,'OUTPUT_INVALID','Bounded complete protein chain required')
        chain_sequences[chain]=''.join(AA[residues[k]['name']] for k in keys)
        for tool_position,key in enumerate(keys,1):
            residue=residues[key]
            ensure(all(name in residue['atoms'] for name in BACKBONE),'OUTPUT_INVALID','Backbone atoms missing; generation is not started')
            rows.append(dict(chain_id=chain,author_resseq=key[1],insertion_code=key[2],
                raw_residue_id=residue['raw_residue_id'],tool_pdb_resseq=tool_position,tool_position=tool_position,
                sequence_position=tool_position if chain==target else None,residue=AA[residue['name']],
                designed_chain=chain==target))
            for name in BACKBONE:
                atom=residue['atoms'][name];coords=atom['coordinate_tool']
                ensure(all(type(v) in (int,float) and math.isfinite(v) and len(f'{v:8.3f}')==8
                    and abs(float(f'{v:.3f}')-v)<1e-9 for v in coords),'OUTPUT_INVALID','Coordinate projection would lose source precision')
                serial+=1
                lines.append(f"ATOM  {serial:5d}  {name:<3} {residue['name']:>3} {chain}{tool_position:4d}    "+
                    ''.join(f'{v:8.3f}' for v in coords)+f"{1.0:6.2f}{atom['bfactor']:6.2f}          {atom['element']:>2}  ")
    ensure(sum(map(len,chain_sequences.values()))<=1000,'INVALID_REQUEST','Total context exceeds the engineering resource limit')
    constraints=body['constraints'];fixed=constraints['fixed_positions'];restricted=constraints['restricted_positions']
    masks={chain:[] for chain in chains};masks[target]=fixed
    omits={chain:[] for chain in chains}
    for item in restricted:
        omits[target].append([[item['position']],''.join(a for a in ALPHABET+'X' if a not in item['allowed_residues'])])
    # Both native fixed and omit arrays index parsed chain positions, not author labels.
    # Canonical PDB resSeq is intentionally equal to that index, with reversible provenance.
    conversion=dict(target_chain=target,fixed_chains=[c for c in chains if c!=target],chain_sequences=chain_sequences,
        rows=rows,source_structure_sha256=sha(original),model_index=mapping['model_index'],
        coordinate_policy='backbone_only_exact_coordinates_canonical_1_based_resseq',
        excluded_atoms=[dict(raw_row_index=a['raw_row_index'],reason='non_backbone_atom') for a in ledger['atoms'] if a['atom_name'] not in BACKBONE]
            +ledger['excluded_atoms'],mapping_failed_count=0,scientific_mapping_signed=False)
    return {'native/target.pdb':('\n'.join(lines+['END'])+'\n').encode('ascii'),
        'native/chain_id.jsonl':encode({'target':[[target],conversion['fixed_chains']]}),
        'native/fixed_positions.jsonl':encode({'target':masks}),
        'native/omit_AA.jsonl':encode({'target':omits}),
        'native/conversion.json':encode(conversion)}
