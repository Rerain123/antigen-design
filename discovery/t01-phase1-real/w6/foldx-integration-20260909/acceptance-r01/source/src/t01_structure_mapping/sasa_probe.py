"""Development-only PDB preparation and address joins; never approves a scientific mapping."""
from collections import Counter
import io
import math
from pathlib import Path

from Bio.PDB import MMCIFParser, PDBIO, PDBParser, Select

from .probe import AA, ProbeError, parse_local, sha


def address(row):
    return tuple(row[k] for k in ('chain_id', 'res_seq', 'insertion_code', 'hetero_flag', 'residue_name'))


def atom_key(row):
    return address(row)+(row['atom_name'], row['altloc'])


def prepare_pdb(path, output_path, *, model_index, context_chain_ids):
    """Write a derived PDB only after explicit selection and representability checks."""
    path, output_path = Path(path), Path(output_path)
    if output_path.exists():
        raise ProbeError('Refusing to overwrite derived PDB')
    inventory = parse_local(path)
    if type(model_index) is not int:
        raise ProbeError('Explicit model_index is required for the raw SASA probe')
    selected = next((m for m in inventory['models'] if m['model_index']==model_index), None)
    if selected is None:
        raise ProbeError('MODEL_NOT_FOUND')
    if not context_chain_ids or len(context_chain_ids)!=len(set(context_chain_ids)):
        raise ProbeError('Explicit, unique context chain IDs required')
    chain_ids = {c['chain_id'] for c in selected['chains']}
    if not set(context_chain_ids).issubset(chain_ids):
        raise ProbeError('Unknown context chain')
    if any(len(c)!=1 or not c.isascii() or not 32<=ord(c)<=126 for c in context_chain_ids):
        raise ProbeError('Author chain ID cannot be represented in PDB; no truncation or renaming')
    for chain in selected['chains']:
        for residue in chain['residues']:
            if residue['hetero_flag']=='W':
                continue
            if residue['residue_name'] not in AA or residue['hetero_flag']!=' ':
                raise ProbeError('Nonstandard/nonprotein context requires separate review; cannot silently discard it')
    parser = MMCIFParser(auth_chains=True, auth_residues=True, PERMISSIVE=False, QUIET=True) if inventory['format']=='mmcif' else PDBParser(PERMISSIVE=False, QUIET=True)
    structure = parser.get_structure('original', str(path))
    expected, excluded, issues = [], [], []
    for model in structure:
        for chain in model:
            for residue in chain.get_unpacked_list():
                for atom in residue.get_unpacked_list():
                    base = {'chain_id':chain.id, 'res_seq':residue.id[1], 'insertion_code':residue.id[2].strip(),
                            'hetero_flag':residue.id[0], 'residue_name':residue.resname,
                            'atom_name':atom.name, 'altloc':atom.altloc.strip(), 'model_index':model.id}
                    reason = ('unselected_model' if model.id!=model_index else 'outside_explicit_context' if chain.id not in context_chain_ids
                              else 'water' if residue.id[0]=='W' else 'hydrogen_or_deuterium' if atom.element in {'H','D'} else None)
                    if reason:
                        excluded.append({**base, 'reason':reason})
                        continue
                    if not -999<=residue.id[1]<=9999:
                        raise ProbeError('Author residue number cannot be represented in PDB')
                    if atom.altloc.strip():
                        raise ProbeError('Explicit altloc choice is required; no parser-default conformer')
                    if not residue.id[2].isascii() or not 32<=ord(residue.id[2])<=126:
                        raise ProbeError('Insertion code cannot be represented in PDB')
                    if any(len(f'{float(v):8.3f}')!=8 for v in atom.coord):
                        raise ProbeError('Coordinate cannot be represented in PDB')
                    if any(len(f'{float(v):6.2f}')!=6 for v in [atom.occupancy,atom.bfactor]):
                        raise ProbeError('Occupancy/B-factor cannot be represented in PDB')
                    if atom.occupancy!=1:
                        issues.append({'code':'OCCUPANCY_REVIEW', 'address':list(atom_key(base)), 'occupancy':atom.occupancy})
                    expected.append({**base, 'coordinate_source':[float(v) for v in atom.coord], 'element':atom.element,
                                     'occupancy':atom.occupancy, 'bfactor':atom.bfactor})
    if not expected or len(expected)+len(context_chain_ids)>99999:
        raise ProbeError('Empty or unrepresentable atom inventory')
    if len({atom_key(a) for a in expected})!=len(expected):
        raise ProbeError('Ambiguous atom addresses before conversion')

    class Selection(Select):
        def accept_model(self, model):
            return model.id==model_index

        def accept_chain(self, chain):
            return chain.id in context_chain_ids

        def accept_residue(self, residue):
            return residue.id[0]==' ' and residue.resname in AA

        def accept_atom(self, atom):
            return atom.element not in {'H','D'}

    writer = PDBIO()
    writer.set_structure(structure[model_index])
    stream = io.StringIO()
    writer.save(stream, Selection())
    pdb = stream.getvalue()
    roundtrip = PDBParser(PERMISSIVE=False, QUIET=True).get_structure('derived', io.StringIO(pdb))
    parsed = []
    for residue in roundtrip.get_residues():
        for atom in residue.get_unpacked_list():
            parsed.append({'chain_id':residue.parent.id,'res_seq':residue.id[1],'insertion_code':residue.id[2].strip(),
                           'hetero_flag':residue.id[0],'residue_name':residue.resname,
                           'atom_name':atom.name,'altloc':atom.altloc.strip(),'element':atom.element,
                           'coordinate_pdb':[float(v) for v in atom.coord]})
    if Counter(atom_key(a) for a in expected)!=Counter(atom_key(a) for a in parsed):
        raise ProbeError('Conversion changed atom/residue identity or count')
    actual = {atom_key(a):a for a in parsed}
    for row in expected:
        other = actual[atom_key(row)]
        if row['element']!=other['element'] or [f'{v:.3f}' for v in row['coordinate_source']]!=[f'{v:.3f}' for v in other['coordinate_pdb']]:
            raise ProbeError('Conversion changed element or coordinates beyond PDB display precision')
        row['coordinate_pdb'] = other['coordinate_pdb']
    data = pdb.encode('ascii')
    output_path.write_bytes(data)
    return {'scope':'DEVELOPMENT_PDB_PREPARATION', 'source_sha256':inventory['structure_sha256'],
            'derived_pdb_sha256':sha(data),'selected_model_index':model_index,
            'source_model_serial':selected['model_serial'], 'context_chain_ids':context_chain_ids,
            'atoms':expected,'excluded_atoms':excluded,'issues':issues,
            'identity_and_pdb_precision_roundtrip':'PASS','scientific_approval':None,'usable_for_pipeline':False}


def align_absolute_sasa(mapping, residues):
    """Join by full source address; row order must never determine sequence position."""
    by_address = {}
    for row in residues:
        key = address(row)
        if key in by_address:
            raise ProbeError('Duplicate raw SASA residue address')
        area = row['absolute_sasa_a2']
        if isinstance(area, bool) or not isinstance(area, (int,float)) or not math.isfinite(area) or area<0:
            raise ProbeError('Invalid raw SASA area; no zero/null substitution')
        by_address[key] = area
    if mapping['target_chain_id'] is None:
        return {'status':'NO_UNIQUE_MAPPING', 'aligned_absolute_sasa_a2':None, 'usable_for_pipeline':False}
    values = []
    seen = set()
    for entry in mapping['entries']:
        residue = entry['structure_residue']
        if residue is None:
            if entry['reason']!='missing_structure_residue':
                raise ProbeError('Unresolved position cannot be treated as missing')
            values.append(None)
        else:
            key = address(residue)
            if key in seen or key not in by_address:
                raise ProbeError('Mapped residue missing from raw SASA or duplicate mapping address')
            seen.add(key)
            values.append(by_address[key])
    target_keys = {k for k in by_address if k[0]==mapping['target_chain_id']}
    if seen!=target_keys:
        raise ProbeError('Raw target residues are not completely covered by mapping')
    return {'status':'ALIGNED_FOR_DEVELOPMENT_REVIEW', 'aligned_absolute_sasa_a2':values,
            'mapping_status':mapping['mapping_status'],'usable_for_pipeline':False}
