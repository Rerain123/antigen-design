"""Literal engineering cases for B1 -> FreeSASA, never scientific area references."""
from b1_engineering_cases import ROOT, cif


def alanines(addresses=('42', '43'), icodes=None, chains=None):
    """Small synthetic heavy-atom geometries, with an independently declared identity."""
    icodes = icodes or ['.'] * len(addresses)
    chains = chains or ['A'] * len(addresses)
    geometry = [('N', 'N', 0, 0, 0), ('CA', 'C', 1.45, .2, 0),
                ('C', 'C', 2.04, 1.59, .1), ('O', 'O', 1.4, 2.6, .3), ('CB', 'C', 1.94, -.78, 1.02)]
    rows = []
    for position, (author, icode, chain) in enumerate(zip(addresses, icodes, chains), 1):
        for name, element, x, y, z in geometry:
            rows.append(dict(auth_seq_id=author, pdbx_PDB_ins_code=icode, auth_asym_id=chain,
                label_asym_id='LABEL_' + chain, label_seq_id=str(position), label_entity_id='1',
                auth_atom_id=name, label_atom_id=name, type_symbol=element,
                Cartn_x=str(x + 4.5 * (position - 1)), Cartn_y=str(y), Cartn_z=str(z)))
    return rows


def cases():
    result = []
    def add(name, data=None, *, route='native_atoms', error=None, tool_error=None, atoms=10, residues=2,
            authors=None, fmt='MMCIF', b1_model=0, consumer_model=0, context=None, source=None,
            b1_error=None, exclusions=None, scope='SYNTHETIC_ENGINEERING_FIXTURE'):
        result.append(dict(id='F-' + name, data=cif(alanines()) if data is None else data,
            declared_format=fmt, sequence='AA', b1_selection=dict(model_index=b1_model, chain_selector='A'),
            consumer_selection=dict(route=route, model_index=consumer_model, context_chain_ids=['A'] if context is None else context),
            source=source, evidence_scope=scope,
            expected=dict(preparation_error=error, tool_error=tool_error, b1_error=b1_error,
                atom_count=atoms if not error else None, residue_count=residues if not error else None,
                authors=authors, excluded_reasons=exclusions)))
    for route in ['pdb_file', 'native_atoms']:
        tag = 'pdb' if route == 'pdb_file' else 'native'
        add('integer-' + tag, route=route, authors=['42', '43'])
        add('icode-' + tag, cif(alanines(['42', '42'], ['.', 'A'])), route=route, authors=['42', '42'])
        add('negative-' + tag, cif(alanines(['-9', '-8'])), route=route, authors=['-9', '-8'])
        add('char-' + tag, cif(alanines(['43A', '44B'])), route=route, authors=['43A', '44B'],
            error='PDB_ADDRESS_UNREPRESENTABLE' if tag == 'pdb' else None)
        add('leading-zero-' + tag, cif(alanines(['043', '43'])), route=route, authors=['043', '43'],
            error='PDB_ADDRESS_UNREPRESENTABLE' if tag == 'pdb' else None)
        add('char-icode-collision-' + tag, cif(alanines(['43A', '43'], ['.', 'A'])), route=route,
            error='PDB_ADDRESS_UNREPRESENTABLE' if tag == 'pdb' else 'FREE_RESIDUE_TOKEN_COLLISION')
        add('numeric-icode-collision-' + tag, cif(alanines(['4', '42'], ['2', '.'])), route=route,
            error='FREE_RESIDUE_TOKEN_COLLISION')
        add('context-ab-' + tag, cif(alanines(chains=['A', 'B'])), route=route, context=['A', 'B'], authors=['42', '43'])
    add('long-author-native', cif(alanines(['12345678901234567890', '+43'])), authors=['12345678901234567890', '+43'])
    add('long-chain', cif(alanines(chains=['A', 'AUTH_LONG'])), context=['A', 'AUTH_LONG'], error='CHAIN_UNREPRESENTABLE')
    add('unknown-icode', cif(alanines(icodes=['?', '.'])), error='ICODE_UNKNOWN')
    add('literal-question-icode', cif(alanines(icodes=["'?'", '.'])), error='ICODE_UNREPRESENTABLE')
    add('wrong-model', consumer_model=1, error='MODEL_SELECTION_MISMATCH')
    add('empty-context', context=[], error='CONTEXT_SELECTION_INVALID')
    add('duplicate-context', context=['A', 'A'], error='CONTEXT_SELECTION_INVALID')
    add('missing-context-chain', context=['A', 'Z'], error='CONTEXT_CHAIN_NOT_FOUND')
    add('excluded-ingestion-chain', cif(alanines(chains=['A', 'B'])), context=['B'], error='INGESTION_CHAIN_EXCLUDED')
    add('context-a', cif(alanines(chains=['A', 'B'])), atoms=5, residues=1, authors=['42'], exclusions={'outside_explicit_context': 5})
    rows = alanines()
    for r in rows[:5]:
        r.update(pdbx_PDB_model_num='3')
    for r in rows[5:]:
        r.update(pdbx_PDB_model_num='9')
    add('selected-second-model', cif(rows), b1_model=1, consumer_model=1, atoms=5, residues=1,
        authors=['43'], exclusions={'unselected_model': 5})
    rows = alanines()
    for r in rows[5:]:
        r['label_seq_id'] = '3'  # A missing label position is not an invented sequence alignment.
    add('label-gap', cif(rows), authors=['42', '43'])
    rows = alanines(['42', '42'])
    for r in rows[5:]:
        r['label_asym_id'] = 'OTHER_LABEL'
    add('label-namespace-collision', cif(rows), error='FREE_RESIDUE_TOKEN_COLLISION')
    for name, edits, error in [
        ('altloc', dict(label_alt_id='A'), 'ALTLOC_REVIEW_REQUIRED'),
        ('partial-occupancy', dict(occupancy='0.45'), 'OCCUPANCY_REVIEW_REQUIRED'),
        ('zero-occupancy', dict(occupancy='0'), 'OCCUPANCY_REVIEW_REQUIRED'),
        ('unknown-element', dict(type_symbol='?'), 'ELEMENT_UNAVAILABLE'),
        ('conflicting-element', dict(type_symbol='C'), 'ATOM_ELEMENT_CONFLICT'),
        ('atom-namespace', dict(auth_atom_id='CA'), 'ATOM_NAMESPACE_CONFLICT'),
        ('residue-namespace', dict(auth_comp_id='GLY'), 'RESIDUE_NAMESPACE_CONFLICT'),
        ('nonprotein', dict(group_PDB='HETATM', label_comp_id='HEM', auth_comp_id='HEM'), 'CONTEXT_REVIEW_REQUIRED'),
    ]:
        rows = alanines()
        rows[0].update(edits)
        add(name, cif(rows), error=error)
    rows = alanines()
    rows[0].update(auth_atom_id='NX', label_atom_id='NX')
    add('unknown-protor-radius', cif(rows), tool_error='UNKNOWN_PROTOR_RADIUS')
    rows = alanines()
    rows.extend([dict(group_PDB='HETATM', label_comp_id='HOH', auth_comp_id='HOH', label_atom_id='O', auth_atom_id='O', type_symbol='O'),
                 dict(label_seq_id='1', auth_seq_id='42', label_asym_id='LABEL_A', label_atom_id='H', auth_atom_id='H', type_symbol='H')])
    add('water-hydrogen-ledger', cif(rows), authors=['42', '43'], exclusions={'water': 1, 'hydrogen_or_deuterium': 1})
    for route in ['native_atoms', 'pdb_file']:
        rows = alanines()
        rows[0]['Cartn_x'] = '0.123456789'
        add('precision-' + route, cif(rows), route=route)
    add('metadata', cif(alanines(), metadata="_exptl.method 'X-RAY DIFFRACTION'\n_entity_src_gen.pdbx_gene_src_scientific_name 'FILE HOST'"))
    add('rejected-b1', cif(alanines()), fmt='PDB', error='B1_PREFLIGHT_REJECTED', b1_error='FORMAT_MISMATCH')
    original = 'tests/fixtures/structure_mapping/real/1UBQ.cif'
    historical = 'discovery/t01-phase1-real/w1/r58-freesasa-boundaries-20260905/prepared/inputs/original/prepared.pdb'
    add('original-1ubq', (ROOT / original).read_bytes(), error='ICODE_UNKNOWN', source=original, scope='UNCHANGED_LOCAL_REAL_INPUT')
    add('historical-derived-1ubq', (ROOT / historical).read_bytes(), fmt='PDB', route='pdb_file',
        error='OCCUPANCY_REVIEW_REQUIRED', source=historical, scope='UNCHANGED_HISTORICAL_ENGINEERING_DERIVATIVE')
    return result


def assert_prepared(case, prepared):
    expected = case['expected']
    assert len(prepared['atoms']) == expected['atom_count']
    assert len({a['raw_residue_id'] for a in prepared['atoms']}) == expected['residue_count']
    if expected['authors'] is not None:
        found = {}
        for atom in prepared['atoms']:
            found.setdefault(atom['raw_residue_id'], atom['author_seq_id'])
        assert list(found.values()) == expected['authors']
    if expected['excluded_reasons'] is not None:
        from collections import Counter
        assert dict(Counter(a['reason'] for a in prepared['excluded_atoms'])) == expected['excluded_reasons']
    assert prepared['normal_rsa_result'] is prepared['buried_fraction'] is prepared['scientific_approval'] is None
    assert prepared['usable_for_pipeline'] is False and prepared['mapping_status'] == 'NOT_EVALUATED'
