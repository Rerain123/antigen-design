"""Predeclared B1 engineering fixtures and literal expectations, not scientific references."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ('group_PDB id type_symbol label_atom_id label_alt_id label_comp_id label_asym_id '
           'label_entity_id label_seq_id pdbx_PDB_ins_code Cartn_x Cartn_y Cartn_z occupancy '
           'B_iso_or_equiv auth_seq_id auth_comp_id auth_asym_id auth_atom_id pdbx_PDB_model_num').split()


def cif(rows=None, metadata=''):
    if rows is None:
        rows = [dict()]
    lines = ['data_B1_ENGINEERING_ONLY', metadata, 'loop_', *('_atom_site.' + key for key in COLUMNS)]
    for index, edits in enumerate(rows, 1):
        values = dict(zip(COLUMNS, ('ATOM', str(index), 'C', 'CA', '.', 'ALA', 'LABEL', '1', str(index),
                      '.', '0', '1', '2', '1', '20', str(index), 'ALA', 'A', 'CA', '7')))
        values.update(edits)
        lines.append(' '.join(values[key] for key in COLUMNS))
    return ('\n'.join(lines) + '\n#\n').encode()


def cases():
    result = []

    def add(case_id, data, expected, fmt='MMCIF', model=None, chain='AUTO', source=None, sequence='A'):
        result.append(dict(id=case_id, data=data, declared_format=fmt, model_index=model,
                           chain_selector=chain, expected=expected, source=source, sequence=sequence))

    for name, count, candidates in [('1UBQ', 660, ['A']), ('5XZC', 1547, ['A', 'B', 'C', 'D', 'E'])]:
        path = f'tests/fixtures/structure_mapping/real/{name}.cif'
        seq = ''.join((ROOT / f'tests/fixtures/structure_mapping/real/{name}.fasta').read_text().splitlines()[1:])
        add('E-real-' + name.lower(), (ROOT / path).read_bytes(), dict(error=None, atoms=count, auto=candidates, chain=candidates[0]),
            source=path, sequence=seq)
    pdb_path = 'tests/fixtures/structure_mapping/synthetic/partial-icode.pdb'
    pdb = (ROOT / pdb_path).read_bytes()
    add('E-pdb-icode', pdb, dict(error=None, atoms=8, auth_ids=['42', '42'], icodes=['', 'A'], pdb=[True, True], foldx=[True, False]), 'PDB', source=pdb_path, sequence='ARG')
    add('E-format-cif-as-pdb', cif(), dict(error='FORMAT_MISMATCH', atoms=1), 'PDB')
    add('E-format-pdb-as-cif', pdb, dict(error='FORMAT_MISMATCH', atoms=8), source=pdb_path)
    add('E-zip', b'PK\x03\x04\x00', dict(error='INPUT_UNSUPPORTED', atoms=0), 'PDB')
    add('E-url', b'https://example.invalid/structure.pdb', dict(error='INPUT_UNSUPPORTED', atoms=0), 'PDB')
    add('E-empty', b'', dict(error='PARSE_FAILED', atoms=0), 'PDB')
    add('E-broken-loop', cif() + b'loop_\n_test.a\n_test.b\none\n', dict(error='PARSE_FAILED', atoms=0))
    add('E-duplicate-tag', cif(metadata='_exptl.method NMR\n_EXPTL.METHOD X-RAY'), dict(error='PARSE_FAILED', atoms=0))
    add('E-multiple-blocks', cif() + b'data_second\n_test.x 1\n', dict(error='INPUT_UNSUPPORTED', atoms=0))
    add('E-invalid-coordinate', cif([dict(Cartn_x='not_numeric')]), dict(error='PARSE_FAILED', atoms=1))
    add('E-nan-coordinate', cif([dict(Cartn_x='nan')]), dict(error='PARSE_FAILED', atoms=1))
    add('E-numeric-uncertainty', cif([dict(Cartn_x='1.0(2)')]), dict(error='INPUT_UNSUPPORTED', atoms=1))
    add('E-missing-chain', cif(), dict(error='SELECTION_NOT_FOUND', atoms=1), chain='Z')
    add('E-label-is-not-author-selector', cif(), dict(error='SELECTION_NOT_FOUND', atoms=1), chain='LABEL')
    add('E-missing-model', cif(), dict(error='SELECTION_NOT_FOUND', atoms=1), model=7)
    multiple = cif([dict(pdbx_PDB_model_num='7'), dict(pdbx_PDB_model_num='9')])
    add('E-model-required', multiple, dict(error='SELECTION_REQUIRED', atoms=2, model_serials=['7', '9']))
    add('E-model-selected', multiple, dict(error=None, atoms=2, model_serials=['7', '9'], chain='A'), model=1)
    context = cif([dict(group_PDB='HETATM', label_comp_id='HOH', auth_comp_id='HOH', auth_asym_id='W'),
                   dict(label_comp_id='DA', auth_comp_id='DA', auth_asym_id='D'),
                   dict(auth_asym_id='P'), dict(auth_asym_id='Q')])
    add('E-auto-context', context, dict(error=None, atoms=4, auto=['P', 'Q'], all_chains=['W', 'D', 'P', 'Q'], chain='P'))
    add('E-nonprotein-chain', context, dict(error='SELECTION_NOT_PROTEIN', atoms=4), chain='W')
    add('E-no-protein', cif([dict(group_PDB='HETATM', label_comp_id='HOH', auth_comp_id='HOH')]), dict(error='SELECTION_NOT_PROTEIN', atoms=1))
    add('E-character-versus-icode', cif([dict(auth_seq_id='43A'), dict(auth_seq_id='43', pdbx_PDB_ins_code='A')]),
        dict(error=None, atoms=2, auth_ids=['43A', '43'], icodes=['.', 'A'], integer=[False, True], pdb=[False, True], foldx=[False, False]))
    add('E-author-long-chain', cif([dict(auth_asym_id='AUTHOR_CHAIN')]), dict(error=None, atoms=1, chain='AUTHOR_CHAIN', integer=[True], pdb=[False]))
    add('E-author-negative', cif([dict(auth_seq_id='-3')]), dict(error=None, atoms=1, auth_ids=['-3'], integer=[True], pdb=[True]))
    add('E-author-leading-zero', cif([dict(auth_seq_id='043'), dict(auth_seq_id='43')]), dict(error=None, atoms=2, auth_ids=['043', '43'], integer=[False, True]))
    add('E-missing-author', cif([dict(auth_seq_id='?')]), dict(error='INPUT_UNSUPPORTED', atoms=1, integer=[False]))
    add('E-quoted-question-author', cif([dict(auth_seq_id="'?'")]), dict(error=None, atoms=1, auth_ids=['?'], integer=[False]))
    add('E-unknown-icode', cif([dict(pdbx_PDB_ins_code='?')]), dict(error=None, atoms=1, integer=[False]))
    add('E-literal-dot-icode', cif([dict(pdbx_PDB_ins_code="'.'")]), dict(error=None, atoms=1, icodes=['.'], integer=[True], pdb=[False]))
    add('E-long-icode', cif([dict(pdbx_PDB_ins_code='AB')]), dict(error=None, atoms=1, integer=[False], pdb=[False]))
    add('E-projection-collision', cif([dict(auth_seq_id='1', label_asym_id='L1'), dict(auth_seq_id='1', label_asym_id='L2')]),
        dict(error=None, atoms=2, integer=[False, False], pdb=[False, False]))
    add('E-duplicate-atom', cif([dict(auth_seq_id='1', label_seq_id='1'), dict(auth_seq_id='1', label_seq_id='1')]),
        dict(error='PARSE_FAILED', atoms=2))
    metadata = """loop_
_exptl.method
'X-RAY DIFFRACTION'
'SOLUTION NMR'
loop_
_refine.entry_id
_refine.ls_d_res_high
one 1.80
two 2.40
three 'not a number'
_em_3d_reconstruction.resolution ?
_entity_src_gen.pdbx_gene_src_scientific_name 'SOURCE ORGANISM'
_entity_src_gen.pdbx_host_org_scientific_name 'EXPRESSION ORGANISM'
_struct.title
;Synthetic multiline title
second line with _tag and loop_ as text
;
"""
    add('E-cif-metadata-conflicts', cif(metadata=metadata), dict(error=None, atoms=1,
        metadata_codes=['METADATA_UNPARSEABLE', 'METADATA_MULTIPLE_VALUES', 'METADATA_VALUES_DIFFER'],
        metadata_values={'_exptl.method': ['X-RAY DIFFRACTION', 'SOLUTION NMR'], '_refine.ls_d_res_high': ['1.80', '2.40', 'not a number']}))
    head = ('EXPDTA    X-RAY DIFFRACTION\nEXPDTA   2 SOLUTION NMR\n'
            'REMARK   2 RESOLUTION.    1.80 ANGSTROMS.\nREMARK   2 RESOLUTION.    2.40 ANGSTROMS.\n'
            'REMARK   2 RESOLUTION. NOT APPLICABLE.\nREMARK 999 ENGINEERING FIXTURE ONLY\n'
            'SOURCE    MOL_ID: 1; ORGANISM_SCIENTIFIC: SOURCE ORGANISM;\n'
            'SOURCE   2 ORGANISM_SCIENTIFIC: DIFFERENT ORGANISM;\n'
            'SOURCE   3 EXPRESSION_SYSTEM: EXPRESSION ORGANISM;\nSOURCE   4 UNPARSED CONTINUATION\n')
    add('E-pdb-metadata-conflicts', head.encode() + pdb, dict(error=None, atoms=8,
        metadata_codes=['METADATA_UNPARSEABLE', 'METADATA_MULTIPLE_VALUES', 'METADATA_VALUES_DIFFER', 'METADATA_CONTINUATION_UNRESOLVED'],
        metadata_values={'REMARK.2.resolution': ['1.80', '2.40', 'NOT APPLICABLE.']}), 'PDB', source=pdb_path)
    add('E-pdb-model-unclosed', b'MODEL        9\n' + pdb.replace(b'END   \n', b''), dict(error='PARSE_FAILED', atoms=8), 'PDB', source=pdb_path)
    add('E-pdb-truncated', b'ATOM      1  CA  ALA\nEND\n', dict(error='PARSE_FAILED', atoms=1), 'PDB')
    add('E-bom-crlf', b'\xef\xbb\xbf' + cif(metadata="_exptl.method 'SOLUTION NMR'").replace(b'\n', b'\r\n'), dict(error=None, atoms=1))
    add('E-altloc-retained', cif([dict(label_seq_id='1', auth_seq_id='1', label_alt_id='A', occupancy='.5'),
                                dict(label_seq_id='1', auth_seq_id='1', label_alt_id='B', occupancy='.5')]), dict(error=None, atoms=2, residues=1))
    add('E-nonstandard-retained', cif([dict(label_comp_id='MSE', auth_comp_id='MSE', group_PDB='HETATM')]), dict(error=None, atoms=1, unknown_letters=1))
    return result


def assert_expected(expected, facts):
    """Literal file/identity expectations, declared without consulting probe output."""
    pf, raw, meta = (facts[name] for name in ('preflight', 'raw_addresses', 'raw_metadata'))
    assert pf['error_code'] == expected['error'], (pf['error_code'], expected['error'])
    assert raw['atom_count'] == expected['atoms']
    assert pf['status'] == ('ready_for_review' if expected['error'] is None else 'rejected')
    assert not pf['usable_for_pipeline'] and pf['scientific_disposition'] == 'not_evaluated'
    if expected['error']:
        assert pf['ingestion_observation'] is None
    if 'chain' in expected:
        assert pf['ingestion_observation']['chain_used'] == expected['chain']
    if 'auto' in expected:
        assert pf['auto_candidates'] == expected['auto']
    if 'all_chains' in expected:
        assert [c['chain_id'] for c in pf['models'][0]['chains']] == expected['all_chains']
    if 'model_serials' in expected:
        assert [m['model_serial'] for m in pf['models']] == expected['model_serials']
    residues = raw['residues']
    for key, field in [('auth_ids', 'auth_seq_id'), ('icodes', 'pdbx_PDB_ins_code')]:
        if key in expected:
            actual = [r['address'][field][0] if r['address'][field][1] != 'not_applicable' else '.' for r in residues]
            assert actual == expected[key], (key, actual)
    for key, profile in [('integer', 'integer_mapping_v0_1'), ('pdb', 'pdb_fixed_columns'), ('foldx', 'foldx_position_token')]:
        if key in expected:
            assert [r['consumers'][profile]['representable'] for r in residues] == expected[key], key
    if 'residues' in expected:
        assert len(residues) == expected['residues']
    if 'unknown_letters' in expected:
        assert sum(r['one_letter'] is None for r in residues) == expected['unknown_letters']
    assert set(expected.get('metadata_codes', [])) <= {d['code'] for d in meta['diagnostics']}
    for field, values in expected.get('metadata_values', {}).items():
        assert [entry['value'] for entry in meta['entries'] if entry['field_name'] == field] == values
