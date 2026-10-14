"""WT original atom ledger, retaining author IDs and missing sidechain atoms."""
from t01_structure_mapping.freesasa_consumer import prepare,ConsumerError
from ...common import decode,ensure,sha

SIDECHAINS=dict(A='CB',R='CB CG CD NE CZ NH1 NH2',N='CB CG OD1 ND2',D='CB CG OD1 OD2',C='CB SG',
    Q='CB CG CD OE1 NE2',E='CB CG CD OE1 OE2',G='',H='CB CG ND1 CD2 CE1 NE2',I='CB CG1 CG2 CD1',
    L='CB CG CD1 CD2',K='CB CG CD CE NZ',M='CB CG SD CE',F='CB CG CD1 CD2 CE1 CE2 CZ',P='CB CG CD',
    S='CB OG',T='CB OG1 CG2',W='CB CG CD1 CD2 NE1 CE2 CE3 CZ2 CZ3 CH2',Y='CB CG CD1 CD2 CE1 CE2 CZ OH',V='CB CG1 CG2')


def geometry(body,files):
    if 'input/structure-result.json' not in files:return dict(status='unavailable',reason='STRUCTURE_UNAVAILABLE',residues=None)
    source=decode(files['input/structure-result.json']);mapping=(source.get('analysis') or {}).get('mapping')
    if not mapping or mapping.get('sequence')!=body['protein_sequence'] or not mapping.get('target_chain_id'):
        return dict(status='unavailable',reason='STRUCTURE_MAPPING_UNAVAILABLE',residues=None)
    try:
        original=files['input/structure-original.bin']
        facts={n:decode(files['input/'+n+'.json']) for n in ('preflight','raw_metadata','raw_addresses')}
        ensure(sha(original)==source['binding']['structure_sha256'],'HASH_MISMATCH','WT structure original differs')
        ensure(all(v['binding']==source['binding'] for v in facts.values()),'OUTPUT_INVALID','WT structure facts differ')
        ledger=prepare(original,facts,route='native_atoms',model_index=mapping['model_index'],context_chain_ids=[mapping['target_chain_id']])
        indexed={}
        for atom in ledger['atoms']:
            key=(atom['chain_id'],atom['author_seq_id'],atom['insertion_code'])
            atoms=indexed.setdefault(key,{})
            ensure(atom['atom_name'] not in atoms,'OUTPUT_INVALID','Ambiguous WT atom')
            atoms[atom['atom_name']]=atom
        residues={};missing=[]
        for row in mapping['entries']:
            pos=row['sequence_position'];address=row['structure_residue']
            if address is None:missing.append(pos);continue
            key=(address['chain_id'],str(address['res_seq']),address['insertion_code'])
            atoms=indexed.get(key,{})
            residues[str(pos)]=dict(address=address,wt_residue=row['sequence_residue'],
                atoms={n:a['coordinate_tool'] for n,a in atoms.items()},
                raw_rows={n:a['raw_row_index'] for n,a in atoms.items()},
                missing_heavy_atoms=sorted(set(('N CA C O '+SIDECHAINS[row['sequence_residue']]).split())-set(atoms)))
        return dict(status='mapped_original_atoms_unreviewed',reason=None,residues=residues,missing_positions=missing,
            source_structure_sha256=sha(original),mapping_sha256=sha(files['input/mapping.json']),
            coordinate_unit='angstrom',coordinate_source='WT original structure, not ProteinMPNN backbone projection',
            excluded_atoms=ledger['excluded_atoms'])
    except ConsumerError as exc:return dict(status='unavailable',reason=exc.code,residues=None)
