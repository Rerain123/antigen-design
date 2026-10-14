"""Explicit derived address convention for verified single-chain AF3 models.

Never interpret an arbitrary experimental CIF's unknown insertion code as empty.
AF3 input positions provide the address namespace for this restricted adapter.
Coordinates, atom order and every other token remain byte-for-byte unchanged.
"""
import re

from .primitives import ensure, sha


def canonical_copy(raw, sequence):
    from .standard import columns, protein_letters_3to1
    atom, count = columns(raw)
    ensure(set(atom['group_PDB']) == {'ATOM'}
           and set(atom['auth_asym_id']) == set(atom['label_asym_id']) == {'A'}
           and set(atom['pdbx_PDB_model_num']) == {'1'}
           and set(atom['label_alt_id']) == {'.'},
           'OUTPUT_INVALID', 'AF3 address adapter requires one unambiguous protein chain')
    residues = {}; seen = set()
    for i in range(count):
        label = atom['label_seq_id'][i]; author = atom['auth_seq_id'][i]
        ensure(label.isdigit() and str(int(label)) == label and author == label
               and 1 <= int(label) <= len(sequence)
               and protein_letters_3to1.get(atom['label_comp_id'][i]) == sequence[int(label)-1]
               and atom['pdbx_PDB_ins_code'][i] in ('.', '?'),
               'OUTPUT_INVALID', 'AF3 address adapter requires exact input-position correspondence')
        key = (label, atom['label_atom_id'][i])
        ensure(key not in seen, 'OUTPUT_INVALID', 'Duplicate AF3 position/atom')
        seen.add(key); residues.setdefault(int(label), set()).add(key[1])
    ensure(set(residues) == set(range(1, len(sequence)+1))
           and all({'N','CA','C','O'} <= names for names in residues.values()),
           'OUTPUT_INVALID', 'AF3 address adapter requires complete backbone correspondence')
    # AF3 emits one atom record per line. Reject an unfamiliar layout instead
    # of reserializing arbitrary CIF content and silently changing other fields.
    lines = raw.decode('utf-8').splitlines(keepends=True)
    tags = []; in_atoms = False; rows = 0; changed = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('_atom_site.'):
            ensure(not in_atoms, 'OUTPUT_INVALID', 'Multiple AF3 atom loops')
            tags.append(stripped); continue
        if not tags: continue
        if not stripped or stripped.startswith('#'):
            if in_atoms: break
            continue
        if stripped.startswith('_') or stripped == 'loop_':
            ensure(in_atoms, 'OUTPUT_INVALID', 'Unsupported AF3 atom loop layout')
            break
        fields = list(re.finditer(r"'[^']*'|\"[^\"]*\"|\S+", line))
        ensure(len(fields) == len(tags), 'OUTPUT_INVALID', 'Unsupported AF3 atom row layout')
        column = tags.index('_atom_site.pdbx_PDB_ins_code')
        token = fields[column]
        ensure(token.group() in ('.', '?'), 'OUTPUT_INVALID', 'Literal insertion codes are not missing tokens')
        if token.group() == '?':
            lines[i] = line[:token.start()] + '.' + line[token.end():]
            changed.append(rows)
        rows += 1; in_atoms = True
    ensure(rows == count, 'OUTPUT_INVALID', 'AF3 address adapter did not cover all atoms')
    derived = ''.join(lines).encode('utf-8'); parsed, _ = columns(derived)
    ensure(all(parsed[k] == (['.']*count if k == 'pdbx_PDB_ins_code' else v)
               for k,v in atom.items()), 'OUTPUT_INVALID', 'AF3 tool copy changed another atom field')
    return derived, dict(policy_version='af3-input-position-address-v1',
        source_sha256=sha(raw), derived_sha256=sha(derived), atom_count=count,
        changed_atom_row_indices=changed, change='unknown_insertion_to_not_applicable',
        basis='verified AF3 single-chain input positions; exact author/label/sequence/backbone correspondence',
        original_retained=True, scientific_gate='CLOSED')
