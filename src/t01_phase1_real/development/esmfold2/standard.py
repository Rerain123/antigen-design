"""Validate native bytes and derive standard results for a bound new attempt."""
import io
import math
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from Bio.Data.PDBData import protein_letters_3to1
from .primitives import decode, encode, ensure, sha
from . import policy
from Bio.PDB.mmcifio import MMCIFIO
from .quality import assess

NAMES = {'structure.cif', 'metrics.json', 'result.json', 'execution.json', 'profile.json', 'request.json', 'checkpoint-loading.json'}
TARGET_ENVIRONMENTS = frozenset({
    ('3.12.14', '2.7.1+cu126', '12.6', 'NVIDIA A100-SXM-64GB', (8, 0)),
    ('3.12.14', '2.7.1+cu126', '12.6', 'NVIDIA A100-SXM4-40GB', (8, 0)),
})


def tool_structure(native_cif):
    """User-authorized derivative; never rewrite native CIF or existing occupancy."""
    original = MMCIF2Dict(io.StringIO(native_cif.decode()))
    ensure(set(original['_atom_site.pdbx_PDB_model_num']) == {'1'}
           and set(original['_atom_site.auth_asym_id']) == set(original['_atom_site.label_asym_id']) == {'A'}
           and set(original['_atom_site.label_alt_id']) <= {'.', '?'},
           'OUTPUT_INVALID', 'Occupancy derivative requires single-model single-chain unambiguous prediction')
    count = len(original['_atom_site.id'])
    ensure('_atom_site.occupancy' not in original, 'OUTPUT_INVALID', 'Do not replace existing occupancy')
    changed = dict(original, **{'_atom_site.occupancy': ['1.0'] * count})
    writer = MMCIFIO(); writer.set_dict(changed)
    stream = io.StringIO(); writer.save(stream)
    raw = stream.getvalue().encode()
    observed = MMCIF2Dict(io.StringIO(raw.decode()))
    ensure(observed == changed, 'OUTPUT_INVALID', 'CIF derivative altered source fields')
    return raw, dict(operation='add_missing_atom_site_occupancy', value='1.0', atom_rows=count,
        authorization='User authorization in current task, 2026-09-17',
        scope='Verified ESMFold2 single-model chain A without alternate conformations only',
        meaning='Engineering full-occupancy convention; not measured or predicted occupancy',
        original_path='raw/structure.cif', original_sha256=sha(native_cif),
        derived_path='tool-structure.cif', derived_sha256=sha(raw),
        preserved_fields=sorted(original), scientific_gate='CLOSED')


def normalize(native, body, binding):
    ensure(set(native) == NAMES | {'manifest.json'}, 'OUTPUT_INVALID', 'Unexpected native file set')
    rows = decode(native['manifest.json'])['files']
    ensure(len(rows) == len(NAMES) and {r['path'] for r in rows} == NAMES,
           'OUTPUT_INVALID', 'Native manifest inventory differs')
    for r in rows:
        ensure(len(native[r['path']]) == r['size_bytes'] and sha(native[r['path']]) == r['sha256'],
               'OUTPUT_INVALID', 'Native artifact hash mismatch')
    expected = policy.native_request(body, binding)
    ensure(decode(native['request.json']) == expected and decode(native['profile.json']) == policy.profile(),
           'OUTPUT_INVALID', 'Executed request/profile differs')
    result, metrics, execution = (decode(native[n + '.json']) for n in ('result', 'metrics', 'execution'))
    sequence = body['protein_sequence']; seqhash = sha(sequence.encode())
    ensure(result['request_id'] == binding['job_id'] and result['sequence_id'] == expected['inputs']['sequence_id']
           and result['sequence_sha256'] == seqhash and result['metrics'] == metrics
           and result['engine'] == 'esmfold2' and result['variant'] == 'standard' and result['msa_mode'] == 'none'
           and result['status'] == 'predicted_engineering_unreviewed' and result['scientific_gate'] == 'CLOSED'
           and result['usable_for_pipeline'] is False, 'OUTPUT_INVALID', 'Native result identity/qualification differs')
    ensure(result['structure'] == dict(path='structure.cif', sha256=sha(native['structure.cif']), format='mmcif', chain_id='A'),
           'OUTPUT_INVALID', 'Native structure reference differs')
    loading = decode(native['checkpoint-loading.json'])
    ensure(all(loading['esmfold2'][k] == [] for k in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')),
           'OUTPUT_INVALID', 'Folding checkpoint was not cleanly loaded')
    esmc = loading['esmc']
    ensure(esmc['missing_keys'] == esmc['unexpected_keys'] == [] and esmc['native_parameters_loaded'] == 802
           and esmc['source_encoder_tensors'] == 1042 and esmc['precision'] == 'torch.bfloat16'
           and set(esmc['omitted_masked_lm_head_keys']) == {'lm_head.' + a + '.' + b
               for a in ('decoder', 'dense', 'layer_norm') for b in ('bias', 'weight')},
           'OUTPUT_INVALID', 'Encoder checkpoint loading differs')
    for key in ('asset_manifest_sha256', 'environment_manifest_sha256', 'environment_root'):
        ensure(execution[key] == policy.profile()[key], 'OUTPUT_INVALID', 'Executed assets/environment differ')
    environment = (execution['python'], execution['torch'], execution['cuda'],
                   execution['gpu_name'], tuple(execution['gpu_capability']))
    from ...gpu_device import POLICY, valid_cuda_observation
    ensure(execution.get('gpu_allocation_policy') in (None, POLICY), 'OUTPUT_INVALID', 'Unknown GPU allocation policy')
    hardware_ok = (valid_cuda_observation(execution) and environment[:3] == ('3.12.14', '2.7.1+cu126', '12.6')
                   if execution.get('gpu_allocation_policy') == POLICY else environment in TARGET_ENVIRONMENTS)
    ensure(hardware_ok,
           'OUTPUT_INVALID', 'Unregistered ESMFold2 target environment')
    cif = MMCIF2Dict(io.StringIO(native['structure.cif'].decode()))
    col = lambda name: cif['_atom_site.' + name]
    count = len(col('id'))
    ensure(all(len(v) == count for k,v in cif.items() if k.startswith('_atom_site.'))
           and len(set(col('id'))) == count, 'OUTPUT_INVALID', 'Malformed atom table')
    ensure(set(col('label_asym_id')) == set(col('auth_asym_id')) == {'A'}
           and set(col('pdbx_PDB_model_num')) == {'1'} and set(col('group_PDB')) == {'ATOM'},
           'OUTPUT_INVALID', 'Unexpected chains, models or non-protein atoms')
    residues = {}
    for i in range(count):
        pos = int(col('label_seq_id')[i]); aa = col('label_comp_id')[i]
        ensure(int(col('auth_seq_id')[i]) == pos and col('auth_comp_id')[i] == aa
               and col('pdbx_PDB_ins_code')[i] in ('.', '?') and col('label_alt_id')[i] in ('.', '?'),
               'OUTPUT_INVALID', 'Ambiguous residue coordinates')
        score = float(col('B_iso_or_equiv')[i]); atom = col('label_atom_id')[i]
        ensure(math.isfinite(score) and 0 <= score <= 100 and all(math.isfinite(float(col(a)[i]))
               for a in ('Cartn_x', 'Cartn_y', 'Cartn_z')), 'OUTPUT_INVALID', 'Nonfinite/out-of-range structure')
        row = residues.setdefault(pos, dict(aa=aa, score=score, atoms=set()))
        ensure(row['aa'] == aa and row['score'] == score and atom not in row['atoms'],
               'OUTPUT_INVALID', 'Inconsistent/duplicate residue atom')
        row['atoms'].add(atom)
    ensure(sorted(residues) == list(range(1, len(sequence)+1)) and
           ''.join(protein_letters_3to1[residues[p]['aa']] for p in sorted(residues)) == sequence
           and all({'N','CA','C','O'} <= r['atoms'] for r in residues.values()),
           'OUTPUT_INVALID', 'Structure sequence or backbone incomplete')
    scores = [residues[p]['score']/100 for p in sorted(residues)]
    ensure(set(metrics) == {'mean_plddt','min_plddt','max_plddt','ptm','iptm'} and all(
        type(v) in (int,float) and math.isfinite(v) and 0 <= v <= 1 for v in metrics.values()),
        'OUTPUT_INVALID', 'Invalid metric values')
    # CPython 3.12 changed float summation. The model worker runs 3.12 while
    # the control plane runs 3.11, so builtin sum() can differ in the final
    # bit and break the byte-for-byte independent reconstruction below.
    # math.fsum has the same high-precision path in both runtimes.
    mean_plddt = math.fsum(scores) / len(scores)
    for key, value in [('mean_plddt', mean_plddt), ('min_plddt', min(scores)), ('max_plddt', max(scores))]:
        ensure(abs(metrics[key]-value) <= 1e-6, 'OUTPUT_INVALID', 'Confidence summary differs')
    model_id = 'esmfold2-seed-1-sample-0'
    confidence = dict(model_id=model_id, sequence_sha256=seqhash, raw_scale='0_100',
        normalization='CIF exported token pLDDT times 100; divide by 100 once',
        definition_source='Biohub/esm@b6b0e8815dc3174a9fe9afd36b222aea57d536c5:esm/utils/structure/molecular_complex.py:858',
        mean_plddt=mean_plddt, residues=[dict(sequence_position=p, amino_acid=sequence[p-1],
        chain_id='A', label_seq_id=p, auth_seq_id=p, insertion_code='', plddt_raw=residues[p]['score'],
        plddt=residues[p]['score']/100, missing_reason=None) for p in sorted(residues)])
    parameters = dict(request=expected['parameters'], inference=policy.profile()['inference'])
    provenance = dict(binding=binding, input_sha256=sha(encode(body)), native_sha256={n:sha(v) for n,v in sorted(native.items())},
        profile_sha256=sha(native['profile.json']), asset_manifest_sha256=policy.profile()['asset_manifest_sha256'],
        environment_manifest_sha256=policy.profile()['environment_manifest_sha256'])
    standard = dict(contract_version='t01.structure-worker/0.1', request_id=binding['job_id'], attempt_id=binding['attempt_id'],
        status='succeeded', engine='esmfold2', engine_version=dict(esm='b6b0e8815dc3174a9fe9afd36b222aea57d536c5',
        transformers='ef32577f55da19a4989cd7b22e004dc43a4998cb'), asset_profile_id=policy.profile()['id'],
        sequence_id=body['user_sequence_id'], sequence=sequence, sequence_sha256=seqhash, host_species=body['host_species'],
        profile_sha256=provenance['profile_sha256'], asset_manifest_sha256=provenance['asset_manifest_sha256'],
        environment_manifest_sha256=provenance['environment_manifest_sha256'],
        models=[dict(model_id=model_id, seed=1, sample_index=0, source='esmfold2_predicted', structure_path='raw/structure.cif',
            structure_sha256=sha(native['structure.cif']), format='mmcif', confidence_path='confidence.json',
            confidence_sha256=sha(encode(confidence)), ptm=metrics['ptm'], iptm=None, raw_scores=metrics)],
        parameters_path='parameters.json', parameters_sha256=sha(encode(parameters)),
        provenance_path='provenance.json', provenance_sha256=sha(encode(provenance)), errors=[],
        warnings=[dict(code='ENGINEERING_ONLY',message='Scientific qualification closed'),
                  dict(code='SINGLE_CHAIN_IPTM_NOT_APPLICABLE',message='Raw ipTM retained; standard ipTM is null')],
        scientific_gate='CLOSED', usable_for_pipeline=False, automatic_handoff=False)
    derived, conversion = tool_structure(native['structure.cif'])
    quality = assess(scores, metrics['ptm'])
    standard['quality'] = dict(path='prediction-quality.json', sha256=sha(encode(quality)))
    standard['tool_structure'] = dict(path='tool-structure.cif', sha256=sha(derived),
        conversion_path='structure-conversion.json', conversion_sha256=sha(encode(conversion)))
    return {'result.json':encode(standard), 'confidence.json':encode(confidence),
            'parameters.json':encode(parameters), 'provenance.json':encode(provenance),
            'tool-structure.cif':derived, 'structure-conversion.json':encode(conversion),
            'prediction-quality.json':encode(quality)}
