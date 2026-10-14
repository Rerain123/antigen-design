"""Parse local coordinates and propose exact, order-preserving mappings for review."""
from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path
import re
import warnings

import Bio
from Bio.PDB import MMCIFParser, PDBParser
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from Bio.PDB.Polypeptide import is_aa
from Bio.PDB.PDBExceptions import PDBConstructionException

from . import __version__

AA = dict(zip(['ALA', 'ARG', 'ASN', 'ASP', 'CYS', 'GLU', 'GLN', 'GLY', 'HIS', 'ILE', 'LEU', 'LYS', 'MET', 'PHE', 'PRO', 'SER', 'THR', 'TRP', 'TYR', 'VAL'], 'ARNDCEQGHILKMFPSTWYV'))
NUCLEIC = {'A', 'C', 'G', 'U', 'I', 'DA', 'DC', 'DG', 'DT', 'DI', 'DU'}


class ProbeError(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_sequence(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if sum(line.startswith('>') for line in lines) > 1 or any(line.startswith('>') for line in lines[1:]):
        raise ProbeError('Sequence file must contain one FASTA record or one plain sequence')
    value = ''.join(lines[1:] if lines and lines[0].startswith('>') else lines).upper()
    if not re.fullmatch('[A-Z]+', value):
        raise ProbeError('Sequence must be nonempty ASCII letters; gaps and internal spaces are not normalized away')
    return value


def exact_embedding(sequence, observed):
    """Earliest and latest embeddings coincide iff the full exact embedding is unique.

    This is a bounded engineering candidate method, not a biological aligner/scoring policy.
    It permits missing input residues, never substitutions or inserted observed residues.
    """
    if not observed:
        return 'no_match', None
    left, cursor = [], 0
    for residue in observed:
        found = sequence.find(residue, cursor)
        if found < 0:
            return 'no_match', None
        left.append(found + 1)
        cursor = found + 1
    right, cursor = [], len(sequence)
    for residue in reversed(observed):
        found = sequence.rfind(residue, 0, cursor)
        right.append(found + 1)
        cursor = found
    if left != list(reversed(right)):
        return 'ambiguous', None
    return ('exact' if sequence == observed else 'partial_unique'), left


def _cif_preflight(text):
    raw = MMCIF2Dict(io.StringIO(text))
    required = ['group_PDB', 'id', 'label_atom_id', 'label_comp_id', 'label_asym_id',
                'label_seq_id', 'auth_asym_id', 'auth_seq_id', 'pdbx_PDB_ins_code',
                'Cartn_x', 'Cartn_y', 'Cartn_z', 'label_alt_id', 'B_iso_or_equiv', 'occupancy']
    n = len(raw.get('_atom_site.id', []))
    if not n:
        raise ProbeError('No atom_site rows')
    for key in required:
        if len(raw.get('_atom_site.' + key, [])) != n:
            raise ProbeError(f'Missing/ragged atom_site.{key}; author numbering must not fall back to label numbering')
    for key in ['pdbx_PDB_model_num', 'label_entity_id']:
        if '_atom_site.' + key in raw and len(raw['_atom_site.' + key]) != n:
            raise ProbeError(f'Ragged atom_site.{key}')
    asym = None
    if any(k.startswith('_struct_asym.') for k in raw):
        ids, entities = raw.get('_struct_asym.id', []), raw.get('_struct_asym.entity_id', [])
        if not ids or len(ids)!=len(entities) or len(ids)!=len(set(ids)):
            raise ProbeError('Missing/ragged/duplicate struct_asym identifiers')
        asym = dict(zip(ids, entities))
    metadata = {}
    for i in range(n):
        auth = raw['_atom_site.auth_seq_id'][i]
        if not re.fullmatch(r'-?\d+', auth):
            raise ProbeError(f'Noninteger author residue ID {auth!r}; preserve raw evidence for explicit iCode/identifier review')
        chain = raw['_atom_site.auth_asym_id'][i]
        if chain in {'.', '?'}:
            raise ProbeError('Unknown author chain ID; cannot silently use label chain')
        insertion = raw['_atom_site.pdbx_PDB_ins_code'][i]
        insertion = '' if insertion in {'.', '?'} else insertion
        if len(insertion) > 1:
            raise ProbeError('Insertion code longer than one character requires review')
        model_text = raw.get('_atom_site.pdbx_PDB_model_num', ['0'] * n)[i]
        if not re.fullmatch(r'\d+', model_text):
            raise ProbeError('Invalid atom_site model number')
        model = int(model_text)
        comp = raw['_atom_site.label_comp_id'][i]
        het = raw['_atom_site.group_PDB'][i]
        key = (model, chain, int(auth), insertion, comp, het)
        label = (raw['_atom_site.label_asym_id'][i], raw['_atom_site.label_seq_id'][i],
                 raw.get('_atom_site.label_entity_id', [None] * n)[i])
        if asym is not None and (label[0] not in asym or label[2] != asym[label[0]]):
            raise ProbeError('atom_site label chain/entity conflicts with struct_asym')
        if key in metadata and metadata[key] != label:
            raise ProbeError('Author residue address maps to multiple label addresses')
        metadata[key] = label
    return raw, metadata


def _polymer_entities(raw):
    """Read explicit entity sequence positions; never infer missing sequence or resolve microheterogeneity."""
    keys = ['_entity_poly_seq.' + name for name in ['entity_id', 'num', 'mon_id']]
    if not any(key.startswith('_entity_poly_seq.') for key in raw):
        return None
    size = len(raw.get(keys[0], []))
    if not size or any(len(raw.get(key, [])) != size for key in keys):
        raise ProbeError('Missing/ragged entity_poly_seq columns')
    hetero = raw.get('_entity_poly_seq.hetero', ['n'] * size)
    if len(hetero) != size:
        raise ProbeError('Ragged entity_poly_seq.hetero')
    entities = {}
    for entity, number, name, variant in zip(*(raw[k] for k in keys), hetero):
        row = entities.setdefault(entity, {'rows':[], 'sequence':None, 'supported':False})
        row['rows'].append({'num':number, 'mon_id':name, 'hetero':variant})
    for row in entities.values():
        rows = row['rows']
        if not all(re.fullmatch(r'[1-9]\d*', r['num']) and r['mon_id'] in AA and r['hetero'] == 'n' for r in rows):
            continue
        rows.sort(key=lambda r:int(r['num']))
        if [int(r['num']) for r in rows] != list(range(1, len(rows)+1)):
            continue
        row['sequence'] = ''.join(AA[r['mon_id']] for r in rows)
        row['supported'] = True
    return entities


def _entity_positions(sequence, records, entities):
    identifiers = {r.get('label_entity_id') for r in records}
    if len(identifiers) != 1 or None in identifiers:
        return 'unsupported', None, 'Missing or mixed label_entity_id'
    entity = entities.get(next(iter(identifiers)))
    if not entity or not entity['supported']:
        return 'unsupported', None, 'Incomplete, nonstandard or microheterogeneous entity sequence'
    if entity['sequence'] != sequence:
        return 'different_sequence', None, 'Full entity sequence differs from input; no unreviewed fragment alignment'
    labels = [r['label_seq_id'] for r in records]
    if not all(label and re.fullmatch(r'[1-9]\d*', label) for label in labels):
        return 'unsupported', None, 'Missing/nonpositive entity sequence position'
    positions = [int(label) for label in labels]
    if positions != sorted(set(positions)) or any(p > len(sequence) for p in positions):
        return 'unsupported', None, 'Duplicate, unordered or out-of-range entity sequence position'
    if any(sequence[p-1] != r['one_letter'] for p,r in zip(positions, records)):
        return 'unsupported', None, 'Coordinate residue differs from the declared entity residue'
    return ('exact' if len(records)==len(sequence) else 'partial_unique'), positions, None


def parse_local(path):
    path = Path(path)
    data = path.read_bytes()
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ProbeError('Coordinate file must be text, not a binary database index') from exc
    meaningful = next((line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')), '')
    fmt = 'mmcif' if meaningful.startswith('data_') else 'pdb'
    if fmt == 'pdb' and not any(line.startswith(('ATOM  ', 'HETATM')) for line in text.splitlines()):
        raise ProbeError('No recognizable PDB coordinate records or mmCIF data block')
    if Bio.__version__ != '1.88':
        raise ProbeError(f'Probe was tested with Biopython 1.88; found {Bio.__version__}')
    raw, metadata = _cif_preflight(text) if fmt == 'mmcif' else ({}, {})
    entities = _polymer_entities(raw) if fmt == 'mmcif' else None
    parser = (MMCIFParser(auth_chains=True, auth_residues=True, PERMISSIVE=False, QUIET=False)
              if fmt == 'mmcif' else PDBParser(PERMISSIVE=False, QUIET=False))
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            structure = parser.get_structure('local_input', io.StringIO(text))
        parser_warnings = [str(w.message) for w in caught]
    except (ValueError, KeyError, IndexError, TypeError, PDBConstructionException) as exc:
        raise ProbeError(f'Strict {fmt} parse failed: {exc}') from exc
    models = []
    for model in structure:
        chains = []
        serial = model.serial_num
        for chain in model:
            residues = []
            for residue in chain.get_unpacked_list():
                hetero, number, insertion = residue.id
                name = residue.resname.strip()
                atoms = residue.get_unpacked_list()
                for atom in atoms:
                    numbers = [*atom.coord, atom.bfactor, atom.occupancy]
                    if any(v is None or not math.isfinite(float(v)) for v in numbers):
                        raise ProbeError('Non-finite or missing coordinate/occupancy/B-factor')
                atom_names = sorted({atom.name for atom in atoms})
                protein = name in AA or is_aa(name) or (hetero == ' ' and name not in NUCLEIC)
                label = metadata.get((serial, chain.id, number, insertion.strip(), name, 'ATOM' if hetero == ' ' else 'HETATM'))
                record = {'chain_id': chain.id, 'res_seq': number, 'insertion_code': insertion.strip(),
                          'hetero_flag': hetero, 'residue_name': name, 'one_letter': AA.get(name) if protein else None,
                          'residue_class': 'standard_amino_acid' if name in AA else 'nonstandard_or_unknown_amino_acid' if protein else 'nonprotein',
                          'atom_names': atom_names, 'altlocs': sorted({atom.altloc.strip() for atom in atoms}),
                          'atom_count_including_altlocs': len(atoms),
                          'label_asym_id': label[0] if label else None,
                          'label_seq_id': label[1] if label else None,
                          'label_entity_id': label[2] if label else None}
                residues.append(record)
            protein_rows = [r for r in residues if r['residue_class'] != 'nonprotein']
            chains.append({'chain_id': chain.id, 'residues': residues, 'protein_residue_count': len(protein_rows)})
        models.append({'model_index': model.id, 'model_serial': serial if fmt == 'mmcif' or any(line.startswith('MODEL ') for line in text.splitlines()) else None, 'chains': chains})
    if not models or not any(c['residues'] for m in models for c in m['chains']):
        raise ProbeError('No parsed residues')
    raw_atom_count = len(raw['_atom_site.id']) if fmt == 'mmcif' else sum(line.startswith(('ATOM  ', 'HETATM')) for line in text.splitlines())
    parsed_atom_count = sum(r['atom_count_including_altlocs'] for m in models for c in m['chains'] for r in c['residues'])
    if raw_atom_count != parsed_atom_count:
        raise ProbeError(f'Parser lost atom records: input={raw_atom_count}, parsed={parsed_atom_count}')
    return {'inventory_version': '0.1.0', 'structure_sha256': sha(data), 'format': fmt,
            'parser': {'name': 'Biopython', 'version': Bio.__version__, 'strict': True,
                       'chain_namespace': 'auth_asym_id' if fmt == 'mmcif' else 'pdb_chain_id'},
            'warnings': parser_warnings, 'models': models, 'raw_atom_count': raw_atom_count, 'parsed_atom_count': parsed_atom_count,
            'polymer_entities': entities,
            'reported_metadata': {key: raw[key] for key in ['_exptl.method', '_refine.ls_d_res_high', '_em_3d_reconstruction.resolution'] if key in raw},
            'metadata_assessment': {'structure_source': 'NOT_INFERRED', 'plddt': 'NOT_INFERRED_FROM_B_FACTOR', 'missing_atom_fraction': None}}


def propose(sequence, inventory, *, evidence_kind, model_index=None, requested_chain=None):
    if not re.fullmatch('[A-Z]+', sequence):
        raise ProbeError('Expected normalized sequence')
    issues = []
    def issue(code, message):
        issues.append({'code': code, 'message': message})
    model = None
    if model_index is None and len(inventory['models']) == 1:
        model = inventory['models'][0]
    elif model_index is not None:
        model = next((m for m in inventory['models'] if m['model_index'] == model_index), None)
        if model is None:
            issue('MODEL_NOT_FOUND', 'Requested model_index does not exist')
    else:
        issue('MODEL_SELECTION_REQUIRED', 'Multiple models; an explicit model selection and its review are required')
    candidates = []
    selected = None
    ingestion_chain = None
    if model:
        protein_chains = [c for c in model['chains'] if c['protein_residue_count']]
        ingestion_chain = requested_chain if requested_chain is not None else protein_chains[0]['chain_id'] if protein_chains else None
        if requested_chain is None and len(protein_chains) > 1:
            issue('INGESTION_AUTO_CHAIN', 'First protein chain is an ingestion observation only, not proof of design-chain identity')
        for chain in protein_chains:
            records = [r for r in chain['residues'] if r['residue_class'] != 'nonprotein']
            labels = {r['label_asym_id'] for r in records if r['label_asym_id'] is not None}
            # mmCIF label order can differ from author numbers or row order.
            duplicate_label = False
            if inventory['format'] == 'mmcif' and len(labels) == 1 and all(r['label_seq_id'] and r['label_seq_id'].isdigit() for r in records):
                records = sorted(records, key=lambda r: int(r['label_seq_id']))
                if len({r['label_seq_id'] for r in records}) != len(records):
                    duplicate_label = True
                    issue('DUPLICATE_LABEL_POSITION', f"Chain {chain['chain_id']}: duplicate label_seq_id")
            keys = [(r['res_seq'], r['insertion_code']) for r in records]
            unsupported = (any(r['one_letter'] is None for r in records) or len(keys) != len(set(keys)) or len(labels) > 1 or duplicate_label)
            observed = ''.join(r['one_letter'] or 'X' for r in records)
            state, positions = ('unsupported', None) if unsupported else exact_embedding(sequence, observed)
            if not unsupported and inventory.get('polymer_entities') is not None:
                anchored, anchored_positions, problem = _entity_positions(sequence, records, inventory['polymer_entities'])
                if anchored == 'different_sequence':
                    # Retain the old ambiguous/no-match diagnostic, but never promote a fragment match.
                    if state in {'exact', 'partial_unique'}:
                        state, positions = 'unsupported', None
                else:
                    state, positions = anchored, anchored_positions
                if problem:
                    issue('ENTITY_MAPPING_REVIEW', f"Chain {chain['chain_id']}: {problem}")
            candidates.append({'chain_id': chain['chain_id'], 'observed_sequence': observed, 'match_status': state, 'positions': positions, 'residues': records})
        possible = [c for c in candidates if c['match_status'] in {'exact', 'partial_unique', 'ambiguous', 'unsupported'}]
        if len(possible) == 1 and possible[0]['match_status'] in {'exact', 'partial_unique'}:
            selected = possible[0]
            if requested_chain is not None and selected['chain_id'] != requested_chain:
                issue('REQUESTED_CHAIN_MISMATCH', 'Requested ingestion chain differs from the unique sequence candidate')
                selected = None
        else:
            issue('MAPPING_NOT_UNIQUE', 'No unique supported chain/position mapping; inspect candidates without choosing a first match')
        if any(c['match_status'] == 'unsupported' for c in candidates):
            issue('UNSUPPORTED_RESIDUE_OR_ADDRESS', 'Unknown residue, duplicate author address or multiple label chains requires review')
    entries = [{'sequence_position': i + 1, 'sequence_residue': letter, 'structure_residue': None, 'reason': 'unresolved_mapping'} for i, letter in enumerate(sequence)]
    if selected:
        for entry in entries:
            entry['reason'] = 'missing_structure_residue'
        for pos, residue in zip(selected['positions'], selected['residues']):
            entries[pos - 1]['structure_residue'] = {k: residue[k] for k in ('chain_id', 'res_seq', 'insertion_code', 'hetero_flag', 'residue_name')}
            entries[pos - 1]['reason'] = 'mapped'
        if any(e['structure_residue'] is None for e in entries):
            issue('PARTIAL_MAPPING', 'Missing input positions are null; the explicit entity/ordered placement remains a candidate requiring review')
        if any(any(a for a in r['altlocs']) for r in selected['residues']):
            issue('ALTLOC_REVIEW', 'All alternate atom identifiers were retained; no conformer was chosen for downstream calculation')
        if any(not {'N', 'CA', 'C', 'O'}.issubset(r['atom_names']) for r in selected['residues']):
            issue('BACKBONE_ATOMS_ABSENT', 'Named backbone atoms are absent at some mapped residues; no missing-atom percentage is inferred')
    issue('G1_REVIEW_PENDING', 'This local probe cannot approve scientific mapping or automatic handoff')
    return {'mapping_version': '0.1.0', 'artifact_type': 't01.real.structure_mapping',
            'evidence_kind': evidence_kind, 'mapping_status': 'unverified' if selected else 'unreliable',
            'review_required': True, 'usable_for_pipeline': False,
            'sequence': sequence, 'sequence_sha256': sha(sequence.encode()), 'structure_sha256': inventory['structure_sha256'],
            'format': inventory['format'], 'model_index': model['model_index'] if model else None,
            'model_serial': model['model_serial'] if model else None,
            'selection': {'requested_model_index': model_index, 'requested_chain_id': requested_chain},
            'ingestion_chain_id': ingestion_chain, 'target_chain_id': selected['chain_id'] if selected else None,
            'fixed_chain_ids': [c['chain_id'] for c in model['chains'] if selected and c['chain_id'] != selected['chain_id']] if model else [],
            'method': {'id': 'entity_label_or_exact_subsequence' if inventory.get('polymer_entities') is not None else 'exact_ordered_subsequence',
                       'version': '0.1.0', 'acceptance_threshold': None},
            'parser': inventory['parser'], 'producer_version': __version__,
            'chain_candidates': [{k: c[k] for k in ('chain_id', 'observed_sequence', 'match_status', 'positions')} for c in candidates],
            'entries': entries, 'issues': issues, 'review': None}
