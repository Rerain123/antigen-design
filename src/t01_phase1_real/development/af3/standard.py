"""Validate all native AF3 samples and derive the project structure contract."""
from __future__ import annotations

import io
import math
import shlex
from pathlib import PurePosixPath

try:
    from Bio.Data.PDBData import protein_letters_3to1
except ModuleNotFoundError:
    # The unified AF3 wrapper environment is intentionally minimal; keep the
    # canonical one-letter conversion local rather than importing Biopython.
    protein_letters_3to1 = {
        'ALA':'A','ARG':'R','ASN':'N','ASP':'D','CYS':'C','GLN':'Q',
        'GLU':'E','GLY':'G','HIS':'H','ILE':'I','LEU':'L','LYS':'K',
        'MET':'M','PHE':'F','PRO':'P','SER':'S','THR':'T','TRP':'W',
        'TYR':'Y','VAL':'V',
    }
try:
    from Bio.PDB.MMCIF2Dict import MMCIF2Dict
except ModuleNotFoundError:
    def MMCIF2Dict(handle):
        """Parse the simple scalar/loop CIF subset emitted by AF3.

        The resident AF3 environment intentionally omits Biopython. AF3 model
        files use ordinary one-line tokens in the atom loop, so a small local
        parser is sufficient while keeping the Biopython parser for richer
        development environments.
        """
        lines = handle.read().splitlines()
        result = {}
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            if not line or line.startswith('#'):
                index += 1
                continue
            if line.lower() == 'loop_':
                index += 1
                tags = []
                while index < len(lines):
                    candidate = lines[index].strip()
                    if candidate.startswith('_'):
                        tags.append(shlex.split(candidate, comments=False, posix=True)[0])
                        index += 1
                    else:
                        break
                if not tags:
                    continue
                values = []
                while index < len(lines):
                    candidate = lines[index].strip()
                    if (not candidate or candidate.startswith('#')):
                        index += 1
                        continue
                    if candidate.lower() == 'loop_' or candidate.startswith('_') or candidate.lower().startswith('data_'):
                        break
                    values.extend(shlex.split(candidate, comments=False, posix=True))
                    index += 1
                width = len(tags)
                for offset, tag in enumerate(tags):
                    result[tag] = [row[offset] for row in
                                   (values[start:start + width] for start in range(0, len(values), width))
                                   if len(row) == width]
                continue
            if line.startswith('_'):
                tokens = shlex.split(line, comments=False, posix=True)
                if len(tokens) > 1:
                    result[tokens[0]] = tokens[1]
            index += 1
        return result

from ..esmfold2.quality import assess
from .primitives import decode, encode, ensure, sha
from . import policy


def safe_name(value):
    path = PurePosixPath(value)
    ensure(isinstance(value, str) and value and not path.is_absolute() and '\\' not in value
           and '..' not in path.parts and path.as_posix() == value,
           'OUTPUT_INVALID', 'Unsafe AF3 native artifact path')
    return value


def inventory(native):
    ensure('manifest.json' in native, 'OUTPUT_INVALID', 'AF3 native manifest missing')
    manifest = decode(native['manifest.json'])
    ensure(isinstance(manifest, dict) and manifest.get('schema') == 't01.af3-native-files/1'
           and isinstance(manifest.get('files'), list) and manifest['files'],
           'OUTPUT_INVALID', 'AF3 native manifest schema differs')
    seen = set()
    for row in manifest['files']:
        ensure(isinstance(row, dict) and set(row) == {'path','size_bytes','sha256'},
               'OUTPUT_INVALID', 'AF3 native manifest row differs')
        name = safe_name(row['path'])
        ensure(name not in seen and name in native and type(row['size_bytes']) is int
               and row['size_bytes'] == len(native[name]) and row['sha256'] == sha(native[name]),
               'OUTPUT_INVALID', 'AF3 native artifact identity differs')
        seen.add(name)
    ensure(set(native) == seen | {'manifest.json'}, 'OUTPUT_INVALID', 'Unlisted AF3 native artifact')
    return manifest


def columns(raw):
    value = MMCIF2Dict(io.StringIO(raw.decode('utf-8')))
    names = ('id','group_PDB','label_asym_id','auth_asym_id','pdbx_PDB_model_num',
             'label_alt_id','label_seq_id','auth_seq_id','label_comp_id',
             'pdbx_PDB_ins_code','label_atom_id','Cartn_x','Cartn_y','Cartn_z',
             'B_iso_or_equiv','occupancy')
    result = {}
    for name in names:
        row = value.get('_atom_site.' + name)
        ensure(isinstance(row, list) and row, 'OUTPUT_INVALID', 'AF3 atom column missing: ' + name)
        result[name] = row
    count = len(result['id'])
    ensure(all(len(row) == count for row in result.values()) and len(set(result['id'])) == count,
           'OUTPUT_INVALID', 'AF3 atom table is malformed')
    return result, count


def model(native, row, sequence):
    for key in ('structure','confidence','summary'):
        safe_name(row[key]); ensure(row[key] in native, 'OUTPUT_INVALID', 'AF3 sample artifact missing')
    atom, count = columns(native[row['structure']])
    confidence_raw = decode(native[row['confidence']])
    atom_scores = confidence_raw.get('atom_plddts')
    ensure(isinstance(atom_scores, list) and len(atom_scores) == count,
           'OUTPUT_INVALID', 'AF3 atom confidence count differs')
    ensure(set(atom['label_asym_id']) == set(atom['auth_asym_id']) == {'A'}
           and set(atom['pdbx_PDB_model_num']) == {'1'} and set(atom['group_PDB']) == {'ATOM'}
           and set(atom['label_alt_id']) <= {'.','?'},
           'OUTPUT_INVALID', 'AF3 model/chain/alternate identity differs')
    residues = {}; ca = {}
    for index, raw_score in enumerate(atom_scores):
        ensure(type(raw_score) in (int,float) and math.isfinite(raw_score) and 0 <= raw_score <= 100,
               'OUTPUT_INVALID', 'AF3 atom confidence is invalid')
        score = float(atom['B_iso_or_equiv'][index])
        ensure(math.isfinite(score) and abs(score - raw_score) <= 0.011
               and all(math.isfinite(float(atom['Cartn_' + axis][index])) for axis in 'xyz'),
               'OUTPUT_INVALID', 'AF3 CIF/confidence coordinate record differs')
        occupancy = float(atom['occupancy'][index])
        ensure(math.isfinite(occupancy) and 0 <= occupancy <= 1,
               'OUTPUT_INVALID', 'AF3 occupancy is missing or out of range')
        position = int(atom['label_seq_id'][index]); residue_name = atom['label_comp_id'][index]
        auth_residue_name = atom.get('auth_comp_id', atom['label_comp_id'])[index]
        ensure(residue_name in protein_letters_3to1 and int(atom['auth_seq_id'][index]) == position
               and auth_residue_name == residue_name
               and atom['pdbx_PDB_ins_code'][index] in ('.','?'),
               'OUTPUT_INVALID', 'AF3 residue identity is ambiguous')
        record = residues.setdefault(position, dict(aa=protein_letters_3to1[residue_name], atoms=set()))
        name = atom['label_atom_id'][index]
        ensure(record['aa'] == protein_letters_3to1[residue_name] and name not in record['atoms'],
               'OUTPUT_INVALID', 'AF3 duplicate/inconsistent residue atom')
        record['atoms'].add(name)
        if name == 'CA':
            ensure(position not in ca, 'OUTPUT_INVALID', 'AF3 residue has duplicate C-alpha')
            ca[position] = score / 100
    positions = list(range(1, len(sequence) + 1))
    ensure(sorted(residues) == positions and sorted(ca) == positions
           and ''.join(residues[pos]['aa'] for pos in positions) == sequence
           and all({'N','CA','C','O'} <= residues[pos]['atoms'] for pos in positions),
           'OUTPUT_INVALID', 'AF3 sequence, C-alpha set or backbone differs')
    summary = decode(native[row['summary']])
    ptm = summary.get('ptm'); ranking = summary.get('ranking_score')
    fraction = summary.get('fraction_disordered'); clash = summary.get('has_clash')
    clash_valid = (type(clash) is bool or
                   (type(clash) in (int,float) and math.isfinite(clash) and clash in (0, 1)))
    ensure(type(ptm) in (int,float) and math.isfinite(ptm) and 0 <= ptm <= 1
           and summary.get('iptm') is None and type(ranking) in (int,float) and math.isfinite(ranking)
           and type(fraction) in (int,float) and math.isfinite(fraction) and 0 <= fraction <= 1
           and clash_valid,
           'OUTPUT_INVALID', 'AF3 single-chain summary confidence differs')
    scores = [ca[pos] for pos in positions]
    model_id = f"af3-seed-{row['seed']}-sample-{row['sample_index']}"
    normalized = dict(model_id=model_id, sequence_sha256=sha(sequence.encode()), raw_scale='0_100',
        normalization='AF3 mmCIF C-alpha B_iso_or_equiv divided by 100 once',
        definition_source='ToolSpec_结构预测获取链_v10.5 §2c and AgentA_SOP_v10.5 S-08',
        mean_plddt=math.fsum(scores)/len(scores), residues=[dict(sequence_position=pos,
        amino_acid=sequence[pos-1], chain_id='A', label_seq_id=pos, auth_seq_id=pos,
        insertion_code='', plddt_raw=scores[pos-1]*100, plddt=scores[pos-1], missing_reason=None)
        for pos in positions])
    return dict(model_id=model_id, seed=row['seed'], sample_index=row['sample_index'],
                structure=row['structure'], confidence=row['confidence'], summary_path=row['summary'],
                structure_sha256=sha(native[row['structure']]), confidence_native_sha256=sha(native[row['confidence']]),
                ptm=float(ptm), iptm=None, raw_scores=summary, scores=scores,
                normalized=normalized, atom_count=count)


def select(models):
    highest = max(row['ptm'] for row in models)
    tied = sorted((row for row in models if row['ptm'] == highest),
                  key=lambda row:(row['seed'], row['sample_index']))
    selected = tied[0]
    ensure(not bool(selected['raw_scores']['has_clash']),
           'OUTPUT_INVALID', 'Highest-pTM deterministic AF3 selection has a native clash')
    return selected, dict(primary='highest_ptm_single_chain', highest_ptm=highest,
        tied_model_ids=[row['model_id'] for row in tied], selected_model_id=selected['model_id'],
        tie_break='lowest_seed_then_sample_index_reproducibility_only',
        tie_break_scientific_preference=False, official_ranking_score_used=False,
        basis='AgentA_SOP_v10.5 S-08 and ToolSpec_结构预测获取链_v10.5 §2c; tie is an engineering reproducibility rule')


def normalize(native, body, binding, prepared_msa=None, *, canonical_addresses=True):
    inventory(native)
    expected = policy.native_request(body, binding)
    ensure(decode(native['request.json']) == expected and decode(native['profile.json']) == policy.profile(),
           'OUTPUT_INVALID', 'AF3 executed request/profile differs')
    folding = decode(native['fold-input.json'])
    from .msa import folding as expected_folding, extract
    msa_only = body.get('mode') == 'msa_only'
    ensure((prepared_msa is not None) == ('msa_source' in body), 'OUTPUT_INVALID', 'MSA staging differs')
    if prepared_msa is not None:
        ensure(prepared_msa['source'] == body['msa_source'], 'OUTPUT_INVALID', 'MSA source differs')
    ensure(folding == expected_folding(body['protein_sequence'],1,prepared_msa),
           'OUTPUT_INVALID', 'AF3 folding input differs')
    command = decode(native['command.json'])
    flags = command['argv']
    ensure(flags[:2] == ['/alphafold3_venv/bin/python','/opt/t01/af3-app/alphafold/run_alphafold.py']
           and '--run_data_pipeline=true' in flags
           and '--run_inference=' + ('false' if msa_only else 'true') in flags
           and '--run_inference=' + ('true' if msa_only else 'false') not in flags
           and '--num_diffusion_samples=5' in flags and '--gpu_device=0' in flags
           and all(flag in flags for flag in policy.hmmer_arguments())
           and command['network'] == 'INHERITED_SECCOMP_AND_POD_DENY_ALL'
           and command['input_sha256'] == sha(encode(folding)),
           'OUTPUT_INVALID', 'AF3 native command differs')
    execution = decode(native['execution.json']); profile = policy.profile()
    from ...gpu_device import POLICY, valid_identity
    ensure(execution.get('gpu_allocation_policy') in (None, POLICY), 'OUTPUT_INVALID', 'Unknown GPU allocation policy')
    assigned = execution.get('gpu_allocation_policy') == POLICY
    gpu_matches = (valid_identity(execution.get('gpu'))
                   and decode(native.get('gpu.json', b'null')) == execution['gpu']) if assigned else execution.get('gpu') == profile['device']
    ensure(execution['source_image_id'] == policy.IMAGE and execution['model_sha256'] == profile['model']['sha256']
           and execution['hmmer'] == policy.HMMER_BINARIES
           and execution['packages'] == {'alphafold3':'3.0.2','jax':'0.9.1'}
           and gpu_matches
           and execution['scientific_gate'] == 'CLOSED' and execution['usable_for_pipeline'] is False
           and execution['production_status'] == 'NOT_DEPLOYED',
           'OUTPUT_INVALID', 'AF3 execution environment differs')
    receipt = execution['database_receipt']
    ensure(receipt.get('decompressed') is True and receipt.get('output_root') == 'unpacked-r03'
           and receipt.get('file_count') == profile['database']['file_count']
           and receipt.get('total_bytes') == profile['database']['total_bytes'],
           'OUTPUT_INVALID', 'AF3 database execution receipt differs')
    samples = execution['samples']
    if 'msa_strategy' in execution or msa_only or prepared_msa is not None:
        strategy = dict(mode='prepare_only' if msa_only else expected['parameters']['msa_mode'],
            source=None if prepared_msa is None else prepared_msa['source'],
            staged_sha256=None if prepared_msa is None else sha(encode(prepared_msa)))
        ensure(execution.get('msa_strategy') == strategy, 'OUTPUT_INVALID', 'Executed MSA strategy differs')
        # All new jobs retain the native alignment with exact query identity.
        observed_msa=extract(native,body['protein_sequence'])
        if prepared_msa is not None:
            supplied=folding['sequences'][0]['protein']
            for channel,observed in observed_msa['msas'].items():
                ensure(observed==supplied[channel] if supplied[channel] else
                       sum(line.startswith('>') for line in observed.splitlines())==1,
                       'OUTPUT_INVALID','Native AF3 did not preserve supplied WT alignment rows')
    if msa_only:
        ensure(samples == [], 'OUTPUT_INVALID', 'MSA-only task must not contain predictions')
        return {'msa.json': encode(dict(extract(native,body['protein_sequence']), binding=binding,
                    mode='WT_MSA_PREPARATION_ONLY', model_inference_executed=False))}
    ensure(isinstance(samples,list) and [(row.get('seed'),row.get('sample_index')) for row in samples]
           == [(1,index) for index in range(5)]
           and all(set(row) == {'seed','sample_index','structure','confidence','summary'} for row in samples),
           'OUTPUT_INVALID', 'AF3 sample inventory differs')
    sequence = body['protein_sequence']; sequence_sha = sha(sequence.encode())
    models = [model(native,row,sequence) for row in samples]
    selected, selection = select(models)
    outputs = {}; standard_models = []
    for row in models:
        confidence_path = 'confidence/' + row['model_id'] + '.json'
        raw = encode(row['normalized']); outputs[confidence_path] = raw
        standard_models.append(dict(model_id=row['model_id'], seed=row['seed'], sample_index=row['sample_index'],
            selected=row is selected, tied_for_highest_ptm=row['model_id'] in selection['tied_model_ids'],
            source='af3_predicted', structure_path='raw/' + row['structure'],
            structure_sha256=row['structure_sha256'], format='mmcif', confidence_path=confidence_path,
            confidence_sha256=sha(raw), ptm=row['ptm'], iptm=None, raw_scores=row['raw_scores']))
    selected_confidence = encode(selected['normalized'])
    quality = assess(selected['scores'], selected['ptm'], source='af3_predicted')
    parameters = dict(request=expected['parameters'], inference=profile['inference'], selection=selection)
    provenance = dict(binding=binding, input_sha256=sha(encode(body)),
        native_sha256={name:sha(raw) for name,raw in sorted(native.items())},
        profile_sha256=sha(native['profile.json']), source_image_id=policy.IMAGE,
        model_sha256=profile['model']['sha256'], database_receipt=receipt, selection=selection)
    conversion = dict(operation='native_mmcif_reuse', source_path='raw/' + selected['structure'],
        source_sha256=selected['structure_sha256'], derived_path='tool-structure.cif',
        derived_sha256=selected['structure_sha256'], occupancy='native_verified_0_to_1',
        scientific_gate='CLOSED')
    tool_raw = native[selected['structure']]
    if canonical_addresses:
        from .tool_structure import canonical_copy
        tool_raw, address_conversion = canonical_copy(tool_raw, sequence)
        conversion.update(operation='verified_af3_address_copy', derived_sha256=sha(tool_raw),
                          address_conversion=address_conversion)
    warnings = [dict(code='ENGINEERING_ONLY',message='Scientific qualification closed'),
                dict(code='SINGLE_CHAIN_IPTM_NOT_APPLICABLE',message='Native ipTM is null for all samples')]
    if len(selection['tied_model_ids']) > 1:
        warnings.append(dict(code='PTM_TIE_REPRODUCIBILITY_SELECTION',
            message='All highest-pTM models are retained; deterministic seed/sample order is not a scientific preference'))
    standard = dict(contract_version='t01.structure-worker/0.1', request_id=binding['job_id'],
        attempt_id=binding['attempt_id'], status='succeeded', engine='alphafold3',
        engine_version=dict(alphafold3=profile['version'], commit=profile['commit']),
        asset_profile_id=profile['id'], sequence_id=body['user_sequence_id'], sequence=sequence,
        sequence_sha256=sequence_sha, host_species=body['host_species'],
        profile_sha256=provenance['profile_sha256'], model_sha256=profile['model']['sha256'],
        database_receipt=receipt, models=standard_models, selection=selection,
        parameters_path='parameters.json', parameters_sha256=sha(encode(parameters)),
        provenance_path='provenance.json', provenance_sha256=sha(encode(provenance)),
        quality=dict(path='prediction-quality.json',sha256=sha(encode(quality))),
        tool_structure=dict(path='tool-structure.cif',sha256=sha(tool_raw),
                            conversion_path='structure-conversion.json',conversion_sha256=sha(encode(conversion))),
        errors=[],warnings=warnings,scientific_gate='CLOSED',usable_for_pipeline=False,automatic_handoff=False)
    outputs.update({'result.json':encode(standard), 'confidence.json':selected_confidence,
        'parameters.json':encode(parameters), 'provenance.json':encode(provenance),
        'tool-structure.cif':tool_raw, 'structure-conversion.json':encode(conversion),
        'prediction-quality.json':encode(quality)})
    return outputs
