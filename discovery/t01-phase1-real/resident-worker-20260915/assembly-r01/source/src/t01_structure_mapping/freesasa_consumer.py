"""B1 facts to a bounded FreeSASA development input. Never grants R-58 approval."""
from __future__ import annotations

import io
import json
import math

from Bio.PDB import PDBParser

from .cif_facts import Source, read_cif
from .input_facts import inspect_input
from .probe import AA, sha

ROUTES = {'pdb_file', 'native_atoms'}
FACT_NAMES = ('preflight', 'raw_metadata', 'raw_addresses')


class ConsumerError(ValueError):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.details = details


def require(condition, code, message, details=None):
    if not condition:
        raise ConsumerError(code, message, details)


def _portable(value):
    return json.loads(json.dumps(value, allow_nan=False))


def load_preparation(folder, profile_bytes):
    """Recheck the self-contained bundle inside the tool process, before FreeSASA."""
    def read(name):
        def pairs(items):
            result = {}
            for key, value in items:
                require(key not in result, 'INVALID_JSON', 'Duplicate JSON key')
                result[key] = value
            return result
        return json.loads((folder / name).read_bytes(), object_pairs_hook=pairs,
                          parse_constant=lambda value: require(False, 'INVALID_JSON', 'Non-finite JSON constant'))

    record, prepared = read('consumer_result.json'), read('preparation.json')
    require(record['status'] == 'READY_FOR_TOOL_PROBE', 'PREPARATION_REJECTED', 'No invocation for rejected preparation')
    require(sha((folder / 'preparation.json').read_bytes()) == record['preparation_sha256'],
            'PREPARATION_HASH_MISMATCH', 'Prepared atom ledger changed')
    request, result, registry = (read('b1_input/' + name + '.json') for name in ('request', 'result', 'artifacts'))
    data = (folder / 'b1_input/input.structure').read_bytes()
    selection = read('consumer_selection.json')
    expected_binding = dict(b1_binding=result['binding'],
        b1_result_sha256=sha((folder / 'b1_input/result.json').read_bytes()),
        b1_structure_artifact=request['structure_artifact'], b1_fact_artifacts=result['fact_artifacts'],
        consumer_selection_sha256=sha((folder / 'consumer_selection.json').read_bytes()), profile_sha256=sha(profile_bytes))
    require(prepared['binding'] == record['binding'] == expected_binding,
            'CONSUMER_BINDING_MISMATCH', 'Consumer binding differs from exact upstream bytes, selection or profile')
    binding = result['binding']
    request_bytes = (folder / 'b1_input/request.json').read_bytes()
    require(binding['request_sha256'] == sha(request_bytes) and binding['run_id'] == request['run_id']
            and binding['request_id'] == request['request_id']
            and binding['sequence_sha256'] == request['protein_sequence_sha256'] == sha(request['protein_sequence'].encode())
            and binding['structure_sha256'] == request['structure_artifact']['sha256'] == sha(data),
            'B1_BINDING_MISMATCH', 'B1 request/result/structure/sequence binding differs')
    require(request['tool_id'] == 't01.real.ingest_structure'
            and result['tool_id'] == 't01.dev.structure_input_facts'
            and result['identity_scope'] == registry['identity_scope'] == 'LOCAL_PROBE_NOT_RUNTIME_ISSUED'
            and result['outcome'] == 'recorded' and result['error_code'] is None
            and result['scientific_disposition'] == 'not_evaluated'
            and result['usable_for_pipeline'] is False and result['production_status'] == 'NOT_DEPLOYED'
            and result['host_species'] == request['host_species']
            and result['source_declaration'] == request['source_declaration'],
            'B1_DISPOSITION_MISMATCH', 'B1 provenance or unapproved disposition changed')
    require(registry['request'] == dict(path='request.json', sha256=sha(request_bytes), size_bytes=len(request_bytes))
            and registry['result'] == dict(path='result.json', sha256=expected_binding['b1_result_sha256']),
            'B1_REGISTRY_MISMATCH', 'B1 request/result registry changed')
    refs = {'input.structure': request['structure_artifact'],
            **{name + '.json': result['fact_artifacts'][name] for name in FACT_NAMES}}
    require(len(registry['artifacts']) == len(refs)
            and len({r['artifact_id'] for r in refs.values()}) == len(refs),
            'B1_REGISTRY_MISMATCH', 'B1 artifact set is incomplete or duplicated')
    seen = set()
    for entry in registry['artifacts']:
        name, ref = entry['path'], entry['ref']
        require(name in refs and name not in seen and ref == refs[name], 'B1_REGISTRY_MISMATCH', 'Foreign or duplicate artifact')
        content = (folder / 'b1_input' / name).read_bytes()  # Name checked against the fixed set first.
        require(sha(content) == ref['sha256'] and len(content) == ref['size_bytes'] and ref['run_id'] == binding['run_id'],
                'B1_ARTIFACT_MISMATCH', 'B1 artifact bytes or run differs')
        if name != 'input.structure':
            require(ref['job_id'] == binding['job_id'] and ref['attempt_id'] == binding['attempt_id'],
                    'B1_BINDING_MISMATCH', 'B1 artifact belongs to another attempt')
        seen.add(name)
    facts = {name: read('b1_input/' + name + '.json') for name in FACT_NAMES}
    require(all(fact['binding'] == binding for fact in facts.values())
            and facts['preflight']['requested_selection'] == request['selection']
            and facts['preflight']['declared_format'] == request['declared_format'],
            'B1_BINDING_MISMATCH', 'B1 fact pairing/selection differs')
    fresh = prepare(data, facts, **selection)
    pdb = fresh.pop('pdb_text')
    require(_portable(fresh) == {key: value for key, value in prepared.items() if key != 'binding'},
            'PREPARATION_CONTENT_MISMATCH', 'Prepared input cannot be reproduced from exact B1 facts')
    require(record['route'] == fresh['route'] and record['usable_for_pipeline'] is False
            and record['scientific_approval'] is None and record['production_status'] == 'NOT_DEPLOYED',
            'CONSUMER_DISPOSITION_MISMATCH', 'Preparation claims approval or a different route')
    if pdb is not None:
        require((folder / 'prepared.pdb').read_bytes() == pdb.encode('ascii'), 'PDB_HASH_MISMATCH', 'Derived PDB changed')
    else:
        require(not (folder / 'prepared.pdb').exists(), 'UNDECLARED_ROUTE_ARTIFACT', 'Native route must not have a derived PDB')
    return prepared, record


def _element_fields(data, fmt, count):
    source = Source(data.decode('utf-8'))
    if fmt == 'mmcif':
        item = read_cif(source).get('_atom_site.type_symbol')
        require(item is not None and len(item['values']) == count, 'ELEMENT_UNAVAILABLE', 'Explicit atom_site.type_symbol is required')
        return [dict(field, source_field=item['field_name']) for field in item['values']]
    fields, offset = [], 1 if source.text.startswith('\ufeff') else 0
    for line in source.text.removeprefix('\ufeff').splitlines(keepends=True):
        if line[:6].strip() in {'ATOM', 'HETATM'}:
            require(len(line.rstrip('\r\n')) >= 78, 'ELEMENT_UNAVAILABLE', 'Explicit PDB element columns are required')
            fields.append(dict(source.field(offset + 76, offset + 78, line[76:78].strip(), style='fixed'), source_field='PDB.element'))
        offset += len(line)
    require(len(fields) == count, 'ATOM_COUNT_MISMATCH', 'Element records do not cover the B1 atom inventory')
    return fields


def prepare(data, facts, *, route, model_index, context_chain_ids):
    """Re-read exact B1 bytes, enforce context, and retain a bijective raw/tool ledger."""
    require(route in ROUTES, 'ROUTE_UNSUPPORTED', 'Select pdb_file or native_atoms explicitly')
    pf = facts['preflight']
    fresh = inspect_input(data, declared_format=pf['declared_format'], **pf['requested_selection'])
    for name in fresh:
        supplied = {key: value for key, value in facts[name].items() if key != 'binding'}
        require(_portable(fresh[name]) == _portable(supplied), 'FACTS_SOURCE_MISMATCH', 'B1 facts differ from the original structure', name)
    require(pf['status'] == 'ready_for_review', 'B1_PREFLIGHT_REJECTED', 'Rejected B1 facts cannot feed a consumer', pf['error_code'])
    require(type(model_index) is int and model_index == pf['ingestion_observation']['model_index'],
            'MODEL_SELECTION_MISMATCH', 'Explicit consumer MODEL must match the B1 ingestion selection')
    require(isinstance(context_chain_ids, list) and bool(context_chain_ids)
            and all(isinstance(c, str) for c in context_chain_ids) and len(context_chain_ids) == len(set(context_chain_ids)),
            'CONTEXT_SELECTION_INVALID', 'Explicit unique context chain list is required')
    raw = facts['raw_addresses']
    model = next(m for m in raw['models'] if m['model_index'] == model_index)
    available = {chain['chain_id'] for chain in model['chains']}
    require(set(context_chain_ids) <= available, 'CONTEXT_CHAIN_NOT_FOUND', 'A context author chain is missing')
    require(pf['ingestion_observation']['chain_used'] in context_chain_ids, 'INGESTION_CHAIN_EXCLUDED', 'Context must include the B1 ingestion chain')
    elements = _element_fields(data, pf['detected_format'], raw['atom_count'])
    residues = {r['residue_id']: r for r in raw['residues']}
    atoms, excluded, element_evidence, token_addresses, keys = [], [], [], {}, set()
    for row, element in zip(raw['rows'], elements):
        fields = row['fields']
        residue = residues[row['residue_id']]
        def value(key):
            return fields[key]['value']
        name, chain, author, insertion = (value(k) for k in ('label_comp_id', 'auth_asym_id', 'auth_seq_id', 'pdbx_PDB_ins_code'))
        record = dict(raw_row_index=row['row_index'], raw_residue_id=row['residue_id'], raw_address=residue['address'])
        if row['model_index'] != model_index:
            excluded.append(dict(record, reason='unselected_model'))
            continue
        water = name in {'HOH', 'WAT'} and value('group_PDB') == 'HETATM'
        require(water or name in AA and value('group_PDB') == 'ATOM', 'CONTEXT_REVIEW_REQUIRED',
                'Selected MODEL has nonstandard/nonprotein context; no silent HETATM removal', record)
        if chain not in context_chain_ids:
            excluded.append(dict(record, reason='outside_explicit_context'))
            continue
        if water:
            excluded.append(dict(record, reason='water'))
            continue
        symbol = element['value']
        require(symbol is not None and symbol in {'C', 'N', 'O', 'S', 'P', 'H', 'D'},
                'ELEMENT_UNAVAILABLE', 'Missing or unsupported explicit element; no element guessing', dict(record, element=element))
        element_evidence.append(dict(raw_row_index=row['row_index'], field=element))
        if symbol in {'H', 'D'}:
            excluded.append(dict(record, reason='hydrogen_or_deuterium'))
            continue
        require(value('auth_comp_id') in (None, name), 'RESIDUE_NAMESPACE_CONFLICT', 'Author/label residue names differ', record)
        atom_name = value('label_atom_id')
        require(value('auth_atom_id') in (None, atom_name), 'ATOM_NAMESPACE_CONFLICT', 'Author/label atom names differ', record)
        require(bool(atom_name) and atom_name.isascii() and atom_name.isalnum() and len(atom_name) <= 4,
                'ATOM_NAME_UNSUPPORTED', 'Atom name cannot be represented without changing it', record)
        require(atom_name[0] == symbol, 'ATOM_ELEMENT_CONFLICT',
                'Explicit element differs from the supported standard heavy-atom name', record)
        require(chain is not None and len(chain) == 1 and chain.isascii() and (chain.isalnum() or chain == ' '),
                'CHAIN_UNREPRESENTABLE', 'FreeSASA requires one chain character; no truncation or alias', record)
        require(fields['pdbx_PDB_ins_code']['missing'] in (None, 'not_applicable'),
                'ICODE_UNKNOWN', 'Unknown/absent iCode cannot be interpreted as empty', record)
        insertion = '' if fields['pdbx_PDB_ins_code']['missing'] == 'not_applicable' else insertion
        require(len(insertion) <= 1 and (not insertion or insertion.isascii() and insertion.isalnum()),
                'ICODE_UNREPRESENTABLE', 'Unsupported literal iCode', record)
        require(author is not None and bool(author) and author.isascii() and not any(c.isspace() or ord(c) < 32 for c in author),
                'AUTHOR_ID_UNREPRESENTABLE', 'Unsupported author token; it will not be normalized', record)
        require(fields['label_alt_id']['missing'] == 'not_applicable' or fields['label_alt_id']['missing'] is None and value('label_alt_id') == '',
                'ALTLOC_REVIEW_REQUIRED', 'No implicit choice of alternate conformer', record)
        occupancy, bfactor = (float(value(k)) for k in ('occupancy', 'B_iso_or_equiv'))
        require(occupancy == 1.0, 'OCCUPANCY_REVIEW_REQUIRED', 'Non-full occupancy requires a reviewed context; no weighting', record)
        token = author + insertion
        token_key = (chain, token)
        require(token_key not in token_addresses or token_addresses[token_key] == residue['residue_id'],
                'FREE_RESIDUE_TOKEN_COLLISION', 'Distinct raw residue identities collapse to one FreeSASA token', record)
        token_addresses[token_key] = residue['residue_id']
        atom_key = (*token_key, name, atom_name)
        require(atom_key not in keys, 'FREE_ATOM_COLLISION', 'Duplicate FreeSASA atom identity', record)
        keys.add(atom_key)
        coords = [float(value(k)) for k in ('Cartn_x', 'Cartn_y', 'Cartn_z')]
        atom = dict(record, chain_id=chain, author_seq_id=author, insertion_code=insertion,
                    tool_residue_token=token, residue_name=name, atom_name=atom_name, element=symbol,
                    tool_atom_name=f' {atom_name:<3}' if len(atom_name) < 4 else atom_name,
                    coordinate_source=coords, coordinate_tool=coords, occupancy=occupancy, bfactor=bfactor)
        if route == 'pdb_file':
            projection = residue['consumers']['pdb_fixed_columns']
            require(projection['representable'], 'PDB_ADDRESS_UNREPRESENTABLE', 'B1 PDB field projection is blocked', projection['blockers'])
            require(all(len(f'{v:8.3f}') == 8 for v in coords) and all(len(f'{v:6.2f}') == 6 for v in (occupancy, bfactor)),
                    'PDB_NUMBER_UNREPRESENTABLE', 'Coordinates/occupancy/B-factor overflow PDB columns', record)
            atom['coordinate_tool'] = [float(f'{v:.3f}') for v in coords]
        atoms.append(atom)
    require(bool(atoms), 'EMPTY_CONTEXT', 'No supported heavy protein atoms remain')
    pdb_text = None
    if route == 'pdb_file':
        require(len(atoms) <= 99999, 'PDB_ATOM_COUNT_UNREPRESENTABLE', 'PDB atom serial range exceeded')
        lines = [f"ATOM  {i:5d} {a['tool_atom_name']} {a['residue_name']:>3} {a['chain_id']}{int(a['author_seq_id']):4d}{a['insertion_code'] or ' '}   "
                 + ''.join(f'{v:8.3f}' for v in a['coordinate_tool']) + f"{a['occupancy']:6.2f}{a['bfactor']:6.2f}          {a['element']:>2}  "
                 for i, a in enumerate(atoms, 1)]
        pdb_text = '\n'.join(lines + ['END']) + '\n'
        _roundtrip_pdb(pdb_text, atoms)
    require(len(atoms) + len(excluded) == raw['atom_count'], 'ATOM_LEDGER_INCOMPLETE', 'Every source row must be retained or explicitly excluded')
    return dict(consumer_version='0.1.0', scope='B1_FREESASA_DEVELOPMENT_CONSUMER', route=route,
        structure_sha256=sha(data), selected_model_index=model_index, source_model_serial=model['model_serial'],
        context_chain_ids=context_chain_ids, atoms=atoms, excluded_atoms=excluded, element_evidence=element_evidence,
        pdb_text=pdb_text, pdb_sha256=sha(pdb_text.encode('ascii')) if pdb_text else None,
        preparation_status='READY_FOR_TOOL_PROBE', mapping_status='NOT_EVALUATED',
        scientific_approval=None, usable_for_pipeline=False, normal_rsa_result=None, buried_fraction=None)


def _roundtrip_pdb(text, atoms):
    parsed = PDBParser(PERMISSIVE=False, QUIET=True).get_structure('derived', io.StringIO(text))
    expected = {(a['chain_id'], int(a['author_seq_id']), a['insertion_code'], a['residue_name'], a['atom_name']): a for a in atoms}
    seen = set()
    for residue in parsed.get_residues():
        for atom in residue.get_unpacked_list():
            key = (residue.parent.id, residue.id[1], residue.id[2].strip(), residue.resname, atom.name)
            require(key in expected and key not in seen, 'PDB_ROUNDTRIP_IDENTITY', 'PDB conversion changed or duplicated an atom')
            target = expected[key]
            require(atom.element == target['element'] and [f'{float(v):.3f}' for v in atom.coord] == [f'{v:.3f}' for v in target['coordinate_tool']],
                    'PDB_ROUNDTRIP_COORDINATE', 'PDB conversion changed element/coordinate identity')
            seen.add(key)
    require(len(seen) == len(expected), 'PDB_ROUNDTRIP_COUNT', 'PDB conversion lost atoms')


def validate_tool_atoms(preparation, observed):
    """Join by verified tool keys, never by array order."""
    expected = {(a['chain_id'], a['tool_residue_token'], a['residue_name'], a['atom_name']): a for a in preparation['atoms']}
    seen, joined = set(), []
    require(len(expected) == len(preparation['atoms']), 'FREE_ATOM_COLLISION', 'Duplicate prepared tool key')
    for row in observed:
        require(type(row['tool_atom_index']) is int, 'TOOL_INDEX_MISMATCH', 'Tool atom indices must be integers')
        key = tuple(row[k] for k in ('chain_id', 'tool_residue_token', 'residue_name', 'atom_name'))
        require(key in expected and key not in seen, 'TOOL_IDENTITY_MISMATCH', 'FreeSASA changed, merged or duplicated an atom', row)
        bound = expected[key]
        require(row['coordinate'] == bound['coordinate_tool'], 'TOOL_COORDINATE_MISMATCH', 'FreeSASA coordinate differs from prepared input', row)
        require(isinstance(row['radius'], (int, float)) and not isinstance(row['radius'], bool) and math.isfinite(row['radius']) and row['radius'] > 0,
                'UNKNOWN_PROTOR_RADIUS', 'Invalid tool radius; no radius guessing', row)
        joined.append(dict(row, raw_row_index=bound['raw_row_index'], raw_residue_id=bound['raw_residue_id'], raw_address=bound['raw_address']))
        seen.add(key)
    require(len(seen) == len(expected), 'TOOL_ATOM_COUNT_MISMATCH', 'FreeSASA lost atoms')
    require({r['tool_atom_index'] for r in joined} == set(range(len(joined))),
            'TOOL_INDEX_MISMATCH', 'Tool atom index set is not complete/unique')
    return joined


def join_areas(preparation, observed, areas):
    """Map indexed tool results through a verified atom ledger to full raw identities."""
    joined = validate_tool_atoms(preparation, observed)
    expected_indices = set(range(len(joined)))
    require({r['tool_atom_index'] for r in joined} == expected_indices and len(joined) == len(expected_indices),
            'TOOL_INDEX_MISMATCH', 'Tool atom index set is not complete/unique')
    by_index = {}
    for row in areas:
        index, area = row['tool_atom_index'], row['absolute_sasa_a2']
        require(type(index) is int and index not in by_index and index in expected_indices, 'AREA_INDEX_MISMATCH', 'Duplicate/foreign area index')
        require(not isinstance(area, bool) and isinstance(area, (int, float)) and math.isfinite(area) and area >= 0,
                'INVALID_NUMERIC_OUTPUT', 'Area must be finite and nonnegative')
        by_index[index] = area
    require(set(by_index) == expected_indices, 'AREA_COUNT_MISMATCH', 'Area index set is incomplete')
    residues = {}
    # Source order makes output stable even if observations/results arrive shuffled.
    for atom in sorted(joined, key=lambda a: a['raw_row_index']):
        entry = residues.setdefault(atom['raw_residue_id'], dict(raw_residue_id=atom['raw_residue_id'],
            raw_address=atom['raw_address'], source_atom_rows=[], atom_areas_a2=[]))
        entry['source_atom_rows'].append(atom['raw_row_index'])
        entry['atom_areas_a2'].append(by_index[atom['tool_atom_index']])
    for entry in residues.values():
        entry['absolute_sasa_a2'] = math.fsum(entry.pop('atom_areas_a2'))
    return dict(status='RAW_IDENTITY_JOINED_FOR_REVIEW', residues=list(residues.values()),
                normal_rsa_result=None, buried_fraction=None, mapping_status='NOT_EVALUATED', usable_for_pipeline=False)
