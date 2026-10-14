"""Audit collected r03 engineering output without changing native artifacts."""
import hashlib
import copy
import io
import json
import math
from pathlib import Path
import sys

from Bio.Data.PDBData import protein_letters_3to1
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
import yaml

try:
    from scripts.collect_esmfold2_r03 import REQUIRED, validate
except ModuleNotFoundError:
    from collect_esmfold2_r03 import REQUIRED, validate

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'discovery/t01-phase1-real/esmfold2-target-20260917/r03'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(files, job, bundle, *, expected_request_id='esmfold2-engineering-003'):
    result = validate(files, expected_request_id=expected_request_id)
    read = lambda name: json.loads(files[name + '.json'])
    request, profile, metrics = read('request'), read('profile'), read('metrics')
    execution, loading = read('execution'), read('checkpoint-loading')
    _, config, expected_job = bundle
    for name, value in [('request', request), ('profile', profile)]:
        require(value == json.loads(config['data'][name + '.json']), 'Unexpected ' + name)
    sequence = request['inputs']['sequence']
    require(result['sequence_sha256'] == hashlib.sha256(sequence.encode()).hexdigest(), 'Sequence hash mismatch')
    require(result['sequence_id'] == request['inputs']['sequence_id'], 'Sequence ID mismatch')
    require(result['metrics'] == metrics, 'Metric reference mismatch')
    require(result['engine'] == 'esmfold2' and result['variant'] == 'standard'
            and result['msa_mode'] == 'none', 'Wrong engine or MSA mode')
    require(result['structure']['chain_id'] == 'A' and result['structure']['path'] == 'structure.cif'
            and result['structure']['format'] == 'mmcif', 'Wrong structure reference')
    for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs'):
        require(loading['esmfold2'][key] == [], 'Unclean folding checkpoint')
    esmc = loading['esmc']
    require(esmc['missing_keys'] == [] and esmc['unexpected_keys'] == [], 'Unclean encoder checkpoint')
    require(esmc['native_parameters_loaded'] == 802 and esmc['source_encoder_tensors'] == 1042,
            'Incomplete encoder loading')
    require(esmc['precision'] == 'torch.bfloat16', 'Unexpected encoder precision')
    require(set(esmc['omitted_masked_lm_head_keys']) == {
        'lm_head.' + layer + '.' + kind for layer in ('decoder', 'dense', 'layer_norm')
        for kind in ('bias', 'weight')}, 'Unexpected omitted parameters')
    for key in ('asset_manifest_sha256', 'environment_manifest_sha256', 'environment_root'):
        require(execution[key] == profile[key], 'Runtime identity mismatch: ' + key)
    require(execution['gpu_name'] == 'NVIDIA A100-SXM-64GB' and execution['gpu_capability'] == [8, 0],
            'Unexpected target GPU')
    require(job['metadata']['name'] == expected_job['metadata']['name'], 'Wrong Job')
    require(job['status'].get('succeeded') == 1 and any(
        c['type'] == 'Complete' and c['status'] == 'True' for c in job['status'].get('conditions', [])),
        'Job not complete')
    expected_pod = copy.deepcopy(expected_job['spec']['template']['spec'])
    for container in expected_pod['containers']:
        container.update(terminationMessagePath='/dev/termination-log', terminationMessagePolicy='File',
                         imagePullPolicy='IfNotPresent')
        for values in container['resources'].values():
            for name, value in values.items():
                values[name] = str(value)
    for volume in expected_pod['volumes']:
        if 'configMap' in volume:
            volume['configMap']['defaultMode'] = 420
    for key in ('containers', 'volumes'):
        require(job['spec']['template']['spec'][key] == expected_pod[key],
                'Job configuration changed: ' + key)

    cif = MMCIF2Dict(io.StringIO(files['structure.cif'].decode('utf-8')))
    col = lambda key: cif['_atom_site.' + key]
    count = len(col('id'))
    for key, values in cif.items():
        if key.startswith('_atom_site.'):
            require(len(values) == count, 'Unequal atom columns')
    require(len(set(col('id'))) == count, 'Duplicate atom IDs')
    require(set(col('pdbx_PDB_model_num')) == {'1'}, 'Unexpected models')
    require(set(col('group_PDB')) == {'ATOM'}, 'Unexpected non-protein atoms')
    require(set(col('label_asym_id')) == set(col('auth_asym_id')) == {'A'}, 'Unexpected chains')
    for axis in ('Cartn_x', 'Cartn_y', 'Cartn_z'):
        require(all(math.isfinite(float(v)) for v in col(axis)), 'Non-finite coordinates')
    residues = {}
    for i in range(count):
        pos = int(col('label_seq_id')[i])
        require(int(col('auth_seq_id')[i]) == pos, 'Residue numbering mismatch')
        require(col('label_alt_id')[i] in ('.', '?') and col('pdbx_PDB_ins_code')[i] in ('.', '?'),
                'Unexpected alternate or insertion code')
        name = col('label_comp_id')[i]
        require(col('auth_comp_id')[i] == name, 'Residue naming mismatch')
        atom = col('label_atom_id')[i]
        b = float(col('B_iso_or_equiv')[i])
        require(math.isfinite(b) and 0 <= b <= 100, 'Invalid confidence')
        row = residues.setdefault(pos, {'name': name, 'atoms': set(), 'b': b})
        require(row['name'] == name and row['b'] == b, 'Inconsistent residue annotation')
        require(atom not in row['atoms'], 'Duplicate residue atom')
        row['atoms'].add(atom)
    require(sorted(residues) == list(range(1, len(sequence) + 1)), 'Incomplete residue coverage')
    observed = ''.join(protein_letters_3to1[r['name']] for _, r in sorted(residues.items()))
    require(observed == sequence, 'Structure sequence mismatch')
    require(all({'N', 'CA', 'C', 'O'} <= r['atoms'] for r in residues.values()), 'Missing backbone atoms')
    scores = [residues[pos]['b'] / 100 for pos in sorted(residues)]
    derived = {'mean_plddt': sum(scores) / len(scores), 'min_plddt': min(scores), 'max_plddt': max(scores)}
    # The fixed exporter writes token pLDDT * 100 to each atom's B factor.
    # 1e-6 accommodates float32 reduction/serialization, not scientific acceptance.
    for key, value in derived.items():
        require(math.isclose(value, metrics[key], rel_tol=0, abs_tol=1e-6), 'Confidence summary mismatch: ' + key)
    require(all(math.isfinite(v) and 0 <= v <= 1 for v in metrics.values()), 'Invalid metrics')
    for key in ('elapsed_seconds', 'peak_gpu_memory_bytes', 'peak_process_rss_kib'):
        require(math.isfinite(execution[key]) and execution[key] > 0, 'Invalid resource measurement')
    return {
        'schema_version': '1.0', 'status': 'ENGINEERING_OUTPUT_AUDIT_PASS',
        'scientific_gate': 'CLOSED', 'usable_for_pipeline': False,
        'original_file_count': len(files), 'original_bytes': sum(map(len, files.values())),
        'source_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
        'structure': {'chain_id': 'A', 'model_count': 1, 'residue_count': len(sequence),
                      'atom_count': count, 'sequence_matches': True, 'backbone_complete': True,
                      'coordinates_finite': True, 'residue_plddt_0_to_1': scores},
        'metrics': metrics, 'independent_metrics_from_cif': derived,
        'confidence_source': 'Biohub/esm@b6b0e8815dc3174a9fe9afd36b222aea57d536c5:esm/utils/structure/molecular_complex.py:858',
        'execution': execution,
        'scope': f'One {len(sequence)}-residue single-chain engineering prediction, seed 1, 3 loops, 50 sampling steps.',
        'limitations': ['No scientific accuracy or stereochemical acceptance established.',
                       'No full-length capacity or lifecycle qualification established.',
                       'NetworkPolicy configuration is not an active egress-denial test.',
                       'GPU peak is PyTorch allocated memory, not total device consumption.',
                       'Elapsed time includes integrity checks, loading and inference.',
                       'Backend task integration and N01/N12 routing remain pending.'],
    }


def main():
    require(not sys.argv[1:], 'Run without arguments')
    files = {name: (EVIDENCE / name).read_bytes() for name in REQUIRED | {'manifest.json'}}
    job = json.loads((EVIDENCE / 'cluster-job.json').read_bytes())
    bundle = list(yaml.safe_load_all((ROOT / 'deploy/esmfold2-standard/validation.r03.rancher.yaml').read_text(encoding='utf-8')))
    summary = audit(files, job, bundle)
    summary['auditor_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    raw = (json.dumps(summary, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    output = EVIDENCE / 'audit-summary.json'
    require(not output.exists() or output.read_bytes() == raw, 'Refusing to overwrite different audit evidence')
    output.write_bytes(raw)
    print(summary['status'], summary['structure']['residue_count'], summary['structure']['atom_count'])
    print('SAVED', output)


if __name__ == '__main__':
    main()
