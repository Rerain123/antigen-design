"""Local B1 input facts. No alignment, scientific source inference or qualification."""
from __future__ import annotations

import math
import re

from Bio.PDB.Polypeptide import is_aa

from .cif_facts import FactError, Source, read_cif
from .probe import AA, NUCLEIC, sha

VERSION = '0.1.0'
ABSENT = dict(value=None, raw_value=None, missing='absent', style=None, location=None)
ADDRESS_FIELDS = ('auth_asym_id', 'auth_seq_id', 'pdbx_PDB_ins_code', 'auth_comp_id',
                  'label_asym_id', 'label_seq_id', 'label_entity_id', 'label_comp_id',
                  'label_atom_id', 'auth_atom_id', 'label_alt_id', 'pdbx_PDB_model_num', 'group_PDB', 'id')
NUMERIC_FIELDS = ('Cartn_x', 'Cartn_y', 'Cartn_z', 'occupancy', 'B_iso_or_equiv')
METADATA_PREFIXES = ('_exptl.', '_refine.', '_reflns.', '_em_3d_reconstruction.',
                     '_entity_src_gen.', '_entity_src_nat.', '_pdbx_entity_src_syn.',
                     '_entity.', '_struct.', '_ma_model_list.', '_ma_qa_metric.',
                     '_database_2.', '_pdbx_database_status.')
RESOLUTION_FIELDS = {'_refine.ls_d_res_high', '_reflns.d_resolution_high',
                     '_em_3d_reconstruction.resolution'}


def diagnostic(code, message, location=None):
    return dict(code=code, message=message, location=location)


def _finite(field, name):
    value = field['value']
    if value is None:
        raise FactError('INPUT_UNSUPPORTED', 'Missing coordinate field: ' + name, field['location'])
    if re.fullmatch(r'[+-]?[0-9.]+\([0-9]+\)(?:[eE][+-]?[0-9]+)?', value):
        raise FactError('INPUT_UNSUPPORTED', 'CIF numeric uncertainty syntax requires a separate coordinate reader', field['location'])
    try:
        number = float(value)
    except ValueError as exc:
        raise FactError('PARSE_FAILED', 'Invalid numeric coordinate field: ' + name, field['location']) from exc
    if not math.isfinite(number):
        raise FactError('PARSE_FAILED', 'Non-finite coordinate field: ' + name, field['location'])
    return number


def cif_rows(items):
    columns = {key.split('.', 1)[1]: item['values'] for key, item in items.items() if key.startswith('_atom_site.')}
    size = len(columns.get('id', []))
    if not size:
        raise FactError('PARSE_FAILED', 'No atom_site rows')
    if any(len(values) != size for values in columns.values()):
        raise FactError('PARSE_FAILED', 'Ragged atom_site category')
    rows = []
    for index in range(size):
        fields = {name: columns[name.lower()][index] if name.lower() in columns else dict(ABSENT)
                  for name in (*ADDRESS_FIELDS, *NUMERIC_FIELDS)}
        fields = {name: dict(field, source_field=items['_atom_site.' + name.lower()]['field_name'],
                             field_location=items['_atom_site.' + name.lower()]['field_location'])
                  if '_atom_site.' + name.lower() in items else field for name, field in fields.items()}
        rows.append(dict(row_index=index + 1, fields=fields))
    return rows


def pdb_rows(source):
    rows, models, active = [], [], None
    explicit, ended = False, False
    offset = 1 if source.text.startswith('\ufeff') else 0
    diagnostics = []
    slices = {'id': (6, 11), 'label_atom_id': (12, 16), 'auth_atom_id': (12, 16), 'label_alt_id': (16, 17),
              'auth_comp_id': (17, 20), 'label_comp_id': (17, 20), 'auth_asym_id': (21, 22),
              'auth_seq_id': (22, 26), 'pdbx_PDB_ins_code': (26, 27),
              'Cartn_x': (30, 38), 'Cartn_y': (38, 46), 'Cartn_z': (46, 54),
              'occupancy': (54, 60), 'B_iso_or_equiv': (60, 66), 'group_PDB': (0, 6)}
    for line in source.text.removeprefix('\ufeff').splitlines(keepends=True):
        record = line[:6].strip()
        if record == 'MODEL':
            if active is not None or rows and not explicit or ended:
                diagnostics.append(diagnostic('PARSE_FAILED', 'Nested/mixed MODEL or MODEL after END'))
            explicit = True
            field = source.field(offset + 10, min(offset + 14, offset + len(line.rstrip('\r\n'))), line[10:14].strip(), style='fixed')
            if not re.fullmatch(r'[0-9]+', field['value'] or ''):
                diagnostics.append(diagnostic('PARSE_FAILED', 'Invalid PDB MODEL serial', field['location']))
            if any(m['value'] == field['value'] for m in models):
                diagnostics.append(diagnostic('PARSE_FAILED', 'Duplicate PDB MODEL serial', field['location']))
            models.append(field)
            active = field
        elif record == 'ENDMDL':
            if active is None:
                diagnostics.append(diagnostic('PARSE_FAILED', 'ENDMDL without MODEL'))
            elif not any(r['fields']['pdbx_PDB_model_num'] == active for r in rows):
                diagnostics.append(diagnostic('PARSE_FAILED', 'Empty PDB MODEL'))
            active = None
        elif record == 'END':
            if active is not None:
                diagnostics.append(diagnostic('PARSE_FAILED', 'END before ENDMDL'))
            ended = True
        elif record in {'ATOM', 'HETATM'}:
            if ended or explicit and active is None:
                diagnostics.append(diagnostic('PARSE_FAILED', 'Coordinate record outside MODEL or after END'))
            if len(line.rstrip('\r\n')) < 66:
                diagnostics.append(diagnostic('PARSE_FAILED', 'Truncated PDB coordinate record', source.field(offset, offset + len(line))['location']))
            fields = {name: dict(ABSENT) for name in (*ADDRESS_FIELDS, *NUMERIC_FIELDS)}
            for name, (start, end) in slices.items():
                if start >= len(line.rstrip('\r\n')):
                    continue
                value = line[start:end].strip()
                if name == 'auth_asym_id':
                    value = line[start:end]  # A blank PDB chain is a literal one-character identifier.
                fields[name] = source.field(offset + start, min(offset + end, offset + len(line.rstrip('\r\n'))), value, style='fixed')
            fields['pdbx_PDB_model_num'] = active or dict(ABSENT)
            rows.append(dict(row_index=len(rows) + 1, fields=fields))
        offset += len(line)
    if active is not None:
        diagnostics.append(diagnostic('PARSE_FAILED', 'MODEL is missing ENDMDL'))
    if not rows:
        diagnostics.append(diagnostic('PARSE_FAILED', 'No PDB coordinate rows'))
    return rows, diagnostics, models


def metadata_facts(source, fmt, items):
    entries, diagnostics = [], []

    def add(name, field, group, row_index=None):
        entry = dict(field_name=name, group=group, row_index=row_index, **field)
        entry['parsed_number'] = None
        if field['missing'] or field['value'] in ('', None):
            entry['parse_status'] = 'missing'
        elif group == 'resolution':
            try:
                number = float(field['value'])
                if not math.isfinite(number) or number <= 0:
                    raise ValueError('Invalid resolution')
                entry.update(parsed_number=number, parse_status='numeric')
            except ValueError:
                entry['parse_status'] = 'unparseable'
                diagnostics.append(diagnostic('METADATA_UNPARSEABLE', name, field['location']))
        else:
            entry['parse_status'] = 'raw_text'
        entries.append(entry)

    if fmt == 'mmcif':
        for key, item in items.items():
            if not key.startswith(METADATA_PREFIXES):
                continue
            group = ('method' if key == '_exptl.method' else 'resolution' if key in RESOLUTION_FIELDS
                     else 'source' if key.startswith(('_entity_src_', '_pdbx_entity_src_syn.')) else 'context')
            for index, field in enumerate(item['values'], 1):
                add(item['field_name'], field, group, index)
    elif fmt == 'pdb':
        offset = 1 if source.text.startswith('\ufeff') else 0
        for line in source.text.removeprefix('\ufeff').splitlines(keepends=True):
            raw = line.rstrip('\r\n')
            record = line[:6].strip()
            if record in {'EXPDTA', 'REMARK', 'SOURCE', 'COMPND'}:
                add(record, source.field(offset, offset + len(raw), raw, style='record'), 'context')
                if record == 'EXPDTA':
                    add('EXPDTA.method', source.field(offset + 10, offset + len(raw), raw[10:], style='fixed'), 'method')
                elif record == 'REMARK' and raw[7:10].strip() == '2':
                    match = re.search(r'RESOLUTION\.\s*(.*?)(?:\s+ANGSTROMS\.?\s*)?$', raw, re.I)
                    if match:
                        start, end = match.span(1)
                        add('REMARK.2.resolution', source.field(offset + start, offset + end, match[1].strip(), style='fixed'), 'resolution')
                elif record in {'SOURCE', 'COMPND'}:
                    # Every complete key:value segment is captured; unparsed continuations
                    # remain in the complete record above and carry an explicit diagnostic.
                    body = raw[10:]
                    for match in re.finditer(r'([A-Z][A-Z0-9_ ]*):\s*([^;]*)(;|$)', body):
                        start, end = match.span(2)
                        add(record + '.' + match[1].strip(), source.field(offset + 10 + start, offset + 10 + end,
                            match[2], style='fixed'), 'source')
                    if body.strip() and (':' not in body or not body.rstrip().endswith(';')):
                        diagnostics.append(diagnostic('METADATA_CONTINUATION_UNRESOLVED', record + ' record retained without concatenating fields',
                                                      source.field(offset, offset + len(raw))['location']))
            offset += len(line)
    groups = {}
    for group in ('method', 'resolution', 'source'):
        rows = [entry for entry in entries if entry['group'] == group]
        values = [e['parsed_number'] if e['parse_status'] == 'numeric' else e['value'] for e in rows if e['parse_status'] != 'missing']
        groups[group] = dict(present=bool(rows), occurrence_count=len(rows), distinct_values=list(dict.fromkeys(values)))
        if not rows or not values:
            diagnostics.append(diagnostic('METADATA_MISSING', group))
        if len(rows) > 1:
            diagnostics.append(diagnostic('METADATA_MULTIPLE_VALUES', group + ': retained all occurrences'))
        if group in {'method', 'resolution'} and len(set(values)) > 1:
            diagnostics.append(diagnostic('METADATA_VALUES_DIFFER', group + ': potential conflict; no value chosen'))
    # Different values for the same source tag may refer to different entities.
    # Report them with their row locations; scientific conflict arbitration is deferred.
    for name in dict.fromkeys(e['field_name'] for e in entries if e['group'] == 'source'):
        values = {e['value'] for e in entries if e['field_name'] == name and e['value'] is not None}
        if len(values) > 1:
            diagnostics.append(diagnostic('METADATA_VALUES_DIFFER', name + ': retain entity/record context'))
    return dict(entries=entries, groups=groups, diagnostics=diagnostics,
                assessment=dict(source=None, plddt=None, missing_atom_fraction=None,
                                scientific_disposition='not_evaluated'))


def _identity(field):
    return field['value'], field['missing']


def consumer_address(fields, fmt):
    """Conservative *lossless* field projection, not consumer or mapping approval."""
    chain, seq, code = (fields[k] for k in ('auth_asym_id', 'auth_seq_id', 'pdbx_PDB_ins_code'))
    reasons = []
    integer = None
    if chain['value'] in (None, ''):
        reasons.append('AUTHOR_CHAIN_MISSING')
    value = seq['value']
    if not value or not re.fullmatch(r'(?:0|-[1-9][0-9]*|[1-9][0-9]*)', value):
        reasons.append('AUTHOR_ID_NOT_CANONICAL_INTEGER')
    elif len(value) > 16 or abs(int(value)) > 2**53 - 1:
        reasons.append('AUTHOR_ID_OUTSIDE_INTEROPERABLE_INTEGER_RANGE')
    else:
        integer = int(value)
    insertion = code['value']
    if code['missing'] == 'not_applicable':
        insertion = ''
    elif code['missing']:
        reasons.append('INSERTION_CODE_UNKNOWN_OR_ABSENT')
    elif len(insertion) > 1:
        reasons.append('INSERTION_CODE_TOO_LONG')
    mapping_reasons = list(reasons)
    pdb_reasons = list(reasons)
    if chain['value'] is not None and (len(chain['value']) != 1 or not chain['value'].isascii()
                                        or not (chain['value'].isalnum() or chain['value'] == ' ')):
        pdb_reasons.append('CHAIN_NOT_PDB_CHARACTER')
    if integer is not None and not -999 <= integer <= 9999:
        pdb_reasons.append('RESSEQ_OUTSIDE_PDB_COLUMNS')
    if insertion and (not insertion.isascii() or not insertion.isalnum()):
        pdb_reasons.append('ICODE_NOT_PDB_CHARACTER')
    foldx_reasons = list(pdb_reasons)
    if insertion:
        foldx_reasons.append('FOLDX_TOKEN_HAS_NO_ICODE_FIELD')
    if chain['value'] == ' ':
        foldx_reasons.append('FOLDX_BLANK_CHAIN_UNVALIDATED')
    return {name: dict(representable=not why, blockers=why,
                       address=dict(chain_id=chain['value'], res_seq=integer, insertion_code=insertion) if not why else None,
                       scientific_qualification='NOT_EVALUATED')
            for name, why in [('integer_mapping_v0_1', mapping_reasons),
                              ('pdb_fixed_columns', pdb_reasons), ('foldx_position_token', foldx_reasons)]}


def address_facts(rows, fmt, model_records=()):
    models, model_index, residues, diagnostics = [], {}, {}, []
    seen_atoms, seen_serials = set(), set()
    model_names = {}
    for serial in model_records:
        key = _identity(serial)
        if key not in model_index:
            model_index[key] = len(models)
            models.append(dict(model_index=len(models), model_serial=serial['value'], chains=[]))
    for row in rows:
        fields = row['fields']
        serial = fields['pdbx_PDB_model_num']
        model_key = _identity(serial)
        if model_key not in model_index:
            model_index[model_key] = len(models)
            models.append(dict(model_index=len(models), model_serial=serial['value'], chains=[]))
            if serial['value'] is not None:
                if not re.fullmatch(r'[0-9]+', serial['value']) or len(serial['value']) > 16:
                    diagnostics.append(diagnostic('INPUT_UNSUPPORTED', 'Unsupported model identifier', serial['location']))
                else:
                    canonical = int(serial['value'])
                    if canonical in model_names:
                        diagnostics.append(diagnostic('INPUT_UNSUPPORTED', 'Model spellings collapse to the same integer', serial['location']))
                    model_names[canonical] = serial['value']
            elif serial['missing'] != 'absent':
                diagnostics.append(diagnostic('INPUT_UNSUPPORTED', 'Model identifier is unknown', serial['location']))
        mi = model_index[model_key]
        row['model_index'] = mi
        for name in NUMERIC_FIELDS:
            try:
                _finite(fields[name], name)
            except FactError as exc:
                diagnostics.append(diagnostic(exc.code, str(exc), exc.location))
        for name in ('id', 'group_PDB', 'label_comp_id', 'label_atom_id'):
            if fields[name]['value'] in (None, ''):
                diagnostics.append(diagnostic('INPUT_UNSUPPORTED', 'Missing atom identifier: ' + name, fields[name]['location']))
        if fields['group_PDB']['value'] not in {'ATOM', 'HETATM'}:
            diagnostics.append(diagnostic('PARSE_FAILED', 'Unknown coordinate record group', fields['group_PDB']['location']))
        if fmt == 'pdb' and not re.fullmatch(r'-?[0-9]+', fields['auth_seq_id']['value'] or ''):
            diagnostics.append(diagnostic('INPUT_UNSUPPORTED', 'Nondecimal PDB resSeq dialect retained; no hybrid-36 decoding', fields['auth_seq_id']['location']))
        if fields['auth_asym_id']['value'] in (None, '') or fields['auth_seq_id']['value'] in (None, ''):
            diagnostics.append(diagnostic('INPUT_UNSUPPORTED', 'Author address is missing; label identifiers are not a fallback', fields['auth_seq_id']['location']))
        key = (mi, *(_identity(fields[k]) for k in ('auth_asym_id', 'auth_seq_id', 'pdbx_PDB_ins_code',
                'label_asym_id', 'label_seq_id', 'label_entity_id', 'label_comp_id', 'auth_comp_id', 'group_PDB')))
        atom_key = (key, _identity(fields['label_atom_id']), _identity(fields['label_alt_id']))
        serial_key = (mi if fmt == 'pdb' else None, _identity(fields['id']))
        if atom_key in seen_atoms or serial_key in seen_serials:
            diagnostics.append(diagnostic('PARSE_FAILED', 'Duplicate atom identity/serial; no row dropped', fields['id']['location']))
        seen_atoms.add(atom_key)
        seen_serials.add(serial_key)
        if key not in residues:
            name = fields['label_comp_id']['value'] or ''
            protein = name in AA or is_aa(name) or (fields['group_PDB']['value'] == 'ATOM' and name not in NUCLEIC)
            residues[key] = dict(residue_id='raw-residue-' + str(len(residues) + 1), model_index=mi,
                address={k: _identity(fields[k]) for k in ('auth_asym_id', 'auth_seq_id', 'pdbx_PDB_ins_code',
                    'label_asym_id', 'label_seq_id', 'label_entity_id', 'label_comp_id', 'auth_comp_id', 'group_PDB')},
                atom_rows=[], residue_name=name, one_letter=AA.get(name),
                residue_class='standard_amino_acid' if name in AA else 'nonstandard_or_unknown_amino_acid' if protein else 'nonprotein',
                consumers=consumer_address(fields, fmt))
        residue = residues[key]
        residue['atom_rows'].append(row['row_index'])
        row['residue_id'] = residue['residue_id']
    # A consumer projection cannot erase a label address or a missing-value distinction.
    for profile in ('integer_mapping_v0_1', 'pdb_fixed_columns', 'foldx_position_token'):
        projected = {}
        for residue in residues.values():
            result = residue['consumers'][profile]
            if result['representable']:
                address = result['address']
                key = (residue['model_index'], address['chain_id'], address['res_seq'], address['insertion_code'])
                projected.setdefault(key, []).append(residue)
        for group in projected.values():
            if len(group) > 1:
                for residue in group:
                    residue['consumers'][profile].update(representable=False, address=None,
                                                        blockers=['CONSUMER_ADDRESS_COLLISION'])
    for model in models:
        chains = {}
        for residue in residues.values():
            if residue['model_index'] != model['model_index']:
                continue
            chain_key = tuple(residue['address']['auth_asym_id'])
            chain = chains.setdefault(chain_key, dict(chain_id=chain_key[0], chain_missing=chain_key[1],
                label_chain_ids=[], residue_ids=[], protein_residue_count=0, nonprotein_residue_count=0, residue_letters=[]))
            label = residue['address']['label_asym_id'][0]
            if label not in chain['label_chain_ids']:
                chain['label_chain_ids'].append(label)
            chain['residue_ids'].append(residue['residue_id'])
            if residue['residue_class'] != 'nonprotein':
                chain['protein_residue_count'] += 1
                chain['residue_letters'].append(residue['one_letter'])
            else:
                chain['nonprotein_residue_count'] += 1
        for chain in chains.values():
            chain['seq_extracted'] = ''.join(chain['residue_letters']) if all(chain['residue_letters']) else None
        model['chains'] = list(chains.values())
    return dict(rows=rows, residues=list(residues.values()), models=models, model_records=list(model_records), atom_count=len(rows),
                diagnostics=diagnostics, identity_policy='Full typed author and label tuples; no split, renumbering or chain truncation',
                classification_policy='Existing probe AA/is_aa/ATOM-nonnucleic observation; no production alphabet approval')


def inspect_input(data, *, declared_format, model_index=None, chain_selector='AUTO'):
    """Return three independent facts even on rejection; raw bytes are caller-owned."""
    common = dict(facts_version=VERSION, structure_sha256=sha(data), scientific_disposition='not_evaluated',
                  usable_for_pipeline=False)
    preflight = dict(**common, declared_format=declared_format, detected_format=None,
        requested_selection=dict(model_index=model_index, chain_selector=chain_selector),
        status='rejected', error_code=None, diagnostics=[], models=[], auto_candidates=[], ingestion_observation=None)
    source, fmt, items, rows, errors, model_records = Source(''), None, {}, [], [], []
    try:
        if not data:
            raise FactError('PARSE_FAILED', 'Empty structure file')
        if data.startswith((b'\x1f\x8b', b'PK\x03\x04', b'BCIF')) or b'\x00' in data:
            raise FactError('INPUT_UNSUPPORTED', 'Compressed/binary structure branch is not supported')
        try:
            source = Source(data.decode('utf-8'))
        except UnicodeDecodeError as exc:
            raise FactError('INPUT_UNSUPPORTED', 'Input is outside the UTF-8 text branch') from exc
        meaningful = next((line.strip().lstrip('\ufeff') for line in source.text.splitlines()
                           if line.strip() and not line.lstrip().startswith('#')), '')
        if meaningful.lower().startswith('data_'):
            fmt = 'mmcif'
        elif any(line[:6].strip() in {'ATOM', 'HETATM', 'HEADER', 'MODEL', 'EXPDTA', 'REMARK', 'SOURCE', 'COMPND', 'END'}
                 for line in source.text.splitlines()):
            fmt = 'pdb'
        else:
            raise FactError('INPUT_UNSUPPORTED', 'Unrecognized structure content; no path/URL lookup is performed')
        preflight['detected_format'] = fmt
        if fmt == 'mmcif':
            if source.text.lstrip('\ufeff').startswith('#\\#CIF_2.0'):
                raise FactError('INPUT_UNSUPPORTED', 'CIF 2.0 is outside this reader')
            items = read_cif(source)
            rows = cif_rows(items)
        else:
            rows, errors, model_records = pdb_rows(source)
    except FactError as exc:
        errors.append(diagnostic(exc.code, str(exc), exc.location))
    metadata = dict(**common, **metadata_facts(source, fmt, items))
    metadata['extraction_status'] = 'complete' if fmt and (fmt == 'pdb' or items) else 'unavailable'
    if metadata['extraction_status'] == 'unavailable':
        metadata['diagnostics'].extend(errors)
    addresses = dict(**common, **address_facts(rows, fmt, model_records))
    errors.extend(addresses['diagnostics'])
    preflight['models'] = addresses['models']
    if declared_format not in {'PDB', 'CIF', 'MMCIF'}:
        errors.insert(0, diagnostic('INPUT_UNSUPPORTED', 'Unsupported declared format'))
    elif fmt and fmt != ('pdb' if declared_format == 'PDB' else 'mmcif'):
        errors.insert(0, diagnostic('FORMAT_MISMATCH', 'Declared format differs from detected content'))
    models = addresses['models']
    selected_model = None
    if model_index is not None and (type(model_index) is not int or model_index < 0):
        errors.append(diagnostic('SELECTION_NOT_FOUND', 'model_index must be a nonnegative integer'))
    elif model_index is None:
        if len(models) == 1:
            selected_model = models[0]
        elif len(models) > 1:
            errors.append(diagnostic('SELECTION_REQUIRED', 'Multiple MODELs require an explicit model_index'))
    else:
        selected_model = next((m for m in models if m['model_index'] == model_index), None)
        if models and selected_model is None:
            errors.append(diagnostic('SELECTION_NOT_FOUND', 'Requested model_index does not exist'))
    if selected_model:
        chains = selected_model['chains']
        protein_chains = [c for c in chains if c['protein_residue_count']]
        preflight['auto_candidates'] = [c['chain_id'] for c in protein_chains]
        chain = None
        if chain_selector == 'AUTO':
            chain = protein_chains[0] if protein_chains else None
            if not chain:
                errors.append(diagnostic('SELECTION_NOT_PROTEIN', 'Selected MODEL contains no protein chain'))
            elif len(protein_chains) > 1:
                preflight['diagnostics'].append(diagnostic('AUTO_MULTIPLE_PROTEIN_CHAINS', 'First protein chain is only an ingestion observation'))
        else:
            chain = next((c for c in chains if c['chain_id'] == chain_selector), None)
            if chain is None:
                errors.append(diagnostic('SELECTION_NOT_FOUND', 'Requested author chain does not exist; no AUTO fallback'))
            elif not chain['protein_residue_count']:
                errors.append(diagnostic('SELECTION_NOT_PROTEIN', 'Requested chain contains no protein'))
        if chain and not errors:
            preflight['ingestion_observation'] = dict(chain_used=chain['chain_id'], auto_selected=chain_selector == 'AUTO',
                model_index=selected_model['model_index'], seq_extracted=chain['seq_extracted'])
    preflight['diagnostics'].extend(errors)
    preflight['status'] = 'rejected' if errors else 'ready_for_review'
    preflight['error_code'] = errors[0]['code'] if errors else None
    addresses['complete'] = bool(rows) and not any(e['code'] == 'PARSE_FAILED' for e in errors)
    return dict(preflight=preflight, raw_metadata=metadata, raw_addresses=addresses)
