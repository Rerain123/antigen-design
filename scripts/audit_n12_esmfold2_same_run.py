"""Independently audit the saved r02 N12 same-run engineering evidence."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
from pathlib import Path
import sys

from Bio.Data.PDBData import protein_letters_3to1
from Bio.PDB.MMCIF2Dict import MMCIF2Dict


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'discovery/t01-phase1-real/esmfold2-target-20260917/n12-same-run-20260918-r02'
EXPECTED_SOURCE_PATHS = (
    't01_phase1_real/development/runtime.py',
    't01_phase1_real/development/proteinmpnn/source.py',
    't01_phase1_real/development/esm_if1/source.py',
    't01_phase1_real/development/thermompnn/source.py',
    't01_phase1_real/development/foldx/source.py',
    't01_phase1_real/development/supervisor.py',
    't01_phase1_real/development/n12_prediction_evidence.py',
    't01_phase1_real/development/esmfold2/source.py',
    't01_phase1_real/development/esmfold2/standard.py',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def result_value(row, artifact_bytes):
    refs = [item['ref'] for item in row['artifacts'] if item['ref']['role'] == 'result']
    require(len(refs) == 1, 'Expected exactly one result artifact: ' + row['job']['job_id'])
    return refs[0], json.loads(artifact_bytes[refs[0]['artifact_id']])


def cif_audit(raw, sequence):
    cif = MMCIF2Dict(io.StringIO(raw.decode('utf-8')))
    col = lambda key: cif['_atom_site.' + key]
    atom_count = len(col('id'))
    for key, values in cif.items():
        if key.startswith('_atom_site.'):
            require(len(values) == atom_count, 'Unequal atom columns')
    require(len(set(col('id'))) == atom_count, 'Duplicate atom IDs')
    require(set(col('pdbx_PDB_model_num')) == {'1'}, 'Unexpected model count')
    require(set(col('group_PDB')) == {'ATOM'}, 'Unexpected non-protein atom rows')
    require(set(col('label_asym_id')) == set(col('auth_asym_id')) == {'A'}, 'Unexpected chains')
    for axis in ('Cartn_x', 'Cartn_y', 'Cartn_z'):
        require(all(math.isfinite(float(value)) for value in col(axis)), 'Non-finite coordinates')
    residues = {}
    for index in range(atom_count):
        position = int(col('label_seq_id')[index])
        require(int(col('auth_seq_id')[index]) == position, 'Residue numbering mismatch')
        require(col('label_alt_id')[index] in ('.', '?'), 'Unexpected alternate conformation')
        require(col('pdbx_PDB_ins_code')[index] in ('.', '?'), 'Unexpected insertion code')
        residue_name = col('label_comp_id')[index]
        require(col('auth_comp_id')[index] == residue_name, 'Residue naming mismatch')
        atom_name = col('label_atom_id')[index]
        confidence = float(col('B_iso_or_equiv')[index])
        require(math.isfinite(confidence) and 0 <= confidence <= 100, 'Invalid pLDDT B factor')
        row = residues.setdefault(position, {'name': residue_name, 'atoms': set(), 'confidence': confidence})
        require(row['name'] == residue_name and row['confidence'] == confidence,
                'Inconsistent residue annotation')
        require(atom_name not in row['atoms'], 'Duplicate residue atom')
        row['atoms'].add(atom_name)
    require(sorted(residues) == list(range(1, len(sequence) + 1)), 'Incomplete residue coverage')
    observed = ''.join(protein_letters_3to1[row['name']] for _, row in sorted(residues.items()))
    require(observed == sequence, 'Structure sequence mismatch')
    require(all({'N', 'CA', 'C', 'O'} <= row['atoms'] for row in residues.values()),
            'Missing backbone atoms')
    scores = [residues[position]['confidence'] / 100 for position in sorted(residues)]
    return cif, {
        'chain_id': 'A',
        'model_count': 1,
        'residue_count': len(residues),
        'atom_count': atom_count,
        'sequence_matches': True,
        'backbone_complete': True,
        'coordinates_finite': True,
        'mean_plddt_from_cif': sum(scores) / len(scores),
        'min_plddt_from_cif': min(scores),
        'max_plddt_from_cif': max(scores),
    }


def audit():
    index = read_json(EVIDENCE / 'index.json')
    receipt = read_json(EVIDENCE / 'receipt.json')
    latest = read_json(EVIDENCE / 'latest.json')
    require(latest['receipt'] == receipt, 'Standalone receipt differs from latest receipt')
    require(index['status'] == 'PASS', 'Acceptance index is not PASS')
    require(index['scope'] == 'N12_ESMFOLD2_SAME_RUN_INDEPENDENT_ENGINEERING', 'Unexpected scope')
    require(index['run_id'] == receipt['run_id'], 'Index/receipt run mismatch')
    require(receipt['status'] == 'N12_ESMFOLD2_SAME_RUN_ENGINEERING_PASS', 'Unexpected receipt status')
    require(receipt['complete_n12_engineering_acceptance'] is True, 'Engineering completion missing')
    require(receipt['complete_scientific_n12'] is False, 'Scientific N12 unexpectedly completed')
    for value in (index, receipt):
        require(value['scientific_gate'] == 'CLOSED', 'Scientific gate unexpectedly open')
        require(value['usable_for_pipeline'] is False, 'Pipeline usability unexpectedly enabled')
        require(value['automatic_handoff'] is False, 'Automatic handoff unexpectedly enabled')
        require(value['production_status'] == 'NOT_DEPLOYED', 'Production status unexpectedly changed')

    expected_jobs = {
        receipt['structure_job_id']: 't01.real.ingest_structure',
        receipt['n11_job_id']: 't01.real.proteinmpnn',
        receipt['n12_job_id']: 't01.real.esm_if1',
        receipt['prediction_job_id']: 't01.real.esmfold2',
    }
    evidence = {row['job']['job_id']: row for row in latest['evidence']}
    require(len(evidence) == 4 and set(evidence) == set(expected_jobs), 'Unexpected evidence job set')

    indexed = index['artifacts']
    require(index['artifact_count'] == len(indexed) == 135, 'Unexpected artifact reference count')
    index_by_artifact = {}
    for entry in indexed:
        require(entry['artifact_id'] not in index_by_artifact, 'Duplicate artifact ID in index')
        index_by_artifact[entry['artifact_id']] = entry

    artifact_bytes = {}
    referenced_paths = set()
    reference_bytes = 0
    for job_id, tool_id in expected_jobs.items():
        row = evidence[job_id]
        job = row['job']
        require(job['tool_id'] == tool_id and job['run_id'] == receipt['run_id'], 'Job identity mismatch')
        require(job['state'] == 'succeeded' and job['exit_code'] == 0, 'Job did not succeed')
        require(job['run_mode'] == 'g0_probe' and job['usable_for_pipeline'] is False,
                'Job qualification boundary changed')
        require(job['evidence_kind'] == 'G0_REAL_OUTPUT' and job['review_required'] is True,
                'Job evidence boundary changed')
        for item in row['artifacts']:
            ref = item['ref']
            require(ref['artifact_id'] not in artifact_bytes, 'Duplicate artifact ID in evidence')
            raw = base64.b64decode(item['base64'], validate=True)
            require(len(raw) == ref['size_bytes'] and digest(raw) == ref['sha256'],
                    'Embedded artifact integrity failure: ' + ref['artifact_id'])
            require(ref['run_id'] == receipt['run_id'] and ref['job_id'] == job_id
                    and ref['attempt_id'] == job['attempt_id'], 'Artifact task binding mismatch')
            entry = index_by_artifact.get(ref['artifact_id'])
            require(entry is not None, 'Artifact missing from index')
            for key in ('job_id', 'artifact_id', 'sha256', 'size_bytes'):
                require(entry[key] == ref[key], 'Artifact index mismatch: ' + key)
            expected_path = f'{job_id}/{ref["sha256"]}'
            require(entry['path'] == expected_path, 'Unexpected saved artifact path')
            saved = EVIDENCE / entry['path']
            require(saved.is_file() and saved.read_bytes() == raw, 'Saved artifact bytes differ')
            artifact_bytes[ref['artifact_id']] = raw
            referenced_paths.add(entry['path'])
            reference_bytes += len(raw)
    require(len(artifact_bytes) == 135, 'Evidence artifact count mismatch')
    actual_paths = {
        path.relative_to(EVIDENCE).as_posix()
        for job_id in expected_jobs
        for path in (EVIDENCE / job_id).iterdir()
        if path.is_file()
    }
    require(actual_paths == referenced_paths, 'Saved artifact file set differs from index')

    expected_sources = {
        path: digest((ROOT / 'src' / path).read_bytes()) for path in EXPECTED_SOURCE_PATHS
    }
    require(index['source_hashes'] == expected_sources, 'Acceptance source identity differs')

    structure_ref, structure = result_value(evidence[receipt['structure_job_id']], artifact_bytes)
    n11_ref, n11 = result_value(evidence[receipt['n11_job_id']], artifact_bytes)
    n12_ref, n12 = result_value(evidence[receipt['n12_job_id']], artifact_bytes)
    prediction_ref, prediction = result_value(evidence[receipt['prediction_job_id']], artifact_bytes)
    require(receipt['linkage']['wt_structure_artifact'] == structure_ref, 'Structure result linkage mismatch')
    require(receipt['linkage']['n11_artifact'] == n11_ref, 'N11 result linkage mismatch')
    require(receipt['linkage']['scoring_artifact'] == n12_ref, 'N12 result linkage mismatch')

    require(n11['generation']['generated_count'] == 24 and len(n11['generation']['records']) == 24,
            'ProteinMPNN did not preserve 24 samples')
    require({row['sample_number'] for row in n11['generation']['records']} == set(range(1, 25)),
            'ProteinMPNN sample numbers differ')
    require(len(n12['scoring']['records']) == 24
            and {row['sample_number'] for row in n12['scoring']['records']} == set(range(1, 25)),
            'ESM-IF1 scoring records differ')
    require(len(n12['engineering_rules']['records']) == 24, 'R-35 record count differs')
    sample_number = receipt['selected_sample_number']
    require(sample_number == 1, 'Unexpected explicit sample selection')
    selected_n11 = next(row for row in n11['generation']['records'] if row['sample_number'] == sample_number)
    selected_n12 = next(row for row in n12['scoring']['records'] if row['sample_number'] == sample_number)
    selected_r35 = next(row for row in n12['engineering_rules']['records'] if row['sample_number'] == sample_number)
    require(selected_n11['sequence'] == selected_n12['sequence'], 'N11/N12 selected sequence mismatch')
    require(selected_n11['mutations'] == selected_n12['mutations'], 'N11/N12 selected mutations mismatch')
    require(selected_n12 == receipt['selected_scoring_record'], 'Selected scoring record differs')
    require(selected_r35 == receipt['selected_r35_original'], 'Original R-35 record differs')
    require(selected_r35['passed'] is False
            and selected_r35['reason_code'] == 'R35_DETERIORATION_EXCEEDED',
            'Original R-35 exclusion was not preserved')
    sequence = selected_n12['sequence']
    sequence_sha256 = digest(sequence.encode())
    require(len(sequence) == 76 and receipt['linkage']['sequence_sha256'] == sequence_sha256,
            'Selected sequence identity mismatch')
    wt = n11['generation']['native_wt']['sequence']
    require(len(wt) == len(sequence), 'WT/candidate length mismatch')
    derived_mutations = [
        {'position': index + 1, 'wt_residue': source, 'mut_residue': target, 'source': 'ProteinMPNN'}
        for index, (source, target) in enumerate(zip(wt, sequence)) if source != target
    ]
    require(derived_mutations == selected_n12['mutations'] == receipt['linkage']['mutations'],
            'Mutation list does not reproduce from WT and selected sequence')
    linkage = receipt['linkage']
    require(linkage['status'] == 'PREDICTION_LINKED_ENGINEERING_ONLY'
            and linkage['engine_selection'] == 'EXPLICIT_ENGINEERING_ONLY_NOT_R04',
            'Engineering-only prediction routing changed')
    require(linkage['validation'] is None and linkage['formal_candidates'] is None,
            'Formal validation or candidates unexpectedly appeared')

    require(prediction['binding']['run_id'] == receipt['run_id']
            and prediction['binding']['job_id'] == receipt['prediction_job_id'],
            'Prediction binding mismatch')
    require(prediction['binding']['sequence_sha256'] == sequence_sha256
            and prediction['prediction']['sequence'] == sequence,
            'Prediction sequence mismatch')
    require(prediction['prediction']['status'] == 'succeeded'
            and prediction['prediction']['scientific_gate'] == 'CLOSED'
            and prediction['prediction']['usable_for_pipeline'] is False,
            'Prediction qualification boundary changed')
    raw_rows = prediction['raw_artifacts']
    require(len(raw_rows) == 25 and len({row['path'] for row in raw_rows}) == 25,
            'Prediction raw artifact set differs')
    raw_by_path = {}
    for row in raw_rows:
        ref = row['artifact']
        require(ref['artifact_id'] in artifact_bytes, 'Prediction raw artifact was not collected')
        raw_by_path[row['path']] = artifact_bytes[ref['artifact_id']]
    raw_json = lambda name: json.loads(raw_by_path[name])
    native_request = raw_json('output/native-request.json')
    execution = raw_json('output/raw/execution.json')
    metrics = raw_json('output/raw/metrics.json')
    native_result = raw_json('output/raw/result.json')
    loading = raw_json('output/raw/checkpoint-loading.json')
    quality = raw_json('output/prediction-quality.json')
    conversion = raw_json('output/structure-conversion.json')
    require(native_request['inputs']['sequence'] == sequence
            and native_request['request_id'] == receipt['prediction_job_id'], 'Native request mismatch')
    require((execution['python'], execution['torch'], execution['cuda'], execution['gpu_name'],
             execution['gpu_capability']) ==
            ('3.12.14', '2.7.1+cu126', '12.6', 'NVIDIA A100-SXM4-40GB', [8, 0]),
            'Unexpected exact ESMFold2 environment')
    require(execution['network'] == 'disabled', 'Native execution network was not disabled')
    require(prediction['execution']['resident_observation']['network_restriction'] ==
            'seccomp-local-sockets-only-v1', 'Resident network restriction differs')
    require(prediction['execution']['stopped_confirmed'] is True
            and prediction['execution']['resident_receipt']['stopped_confirmed'] is True,
            'Prediction process stop was not confirmed')
    for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs'):
        require(loading['esmfold2'][key] == [], 'Unclean folding checkpoint: ' + key)
    require(loading['esmc']['missing_keys'] == [] and loading['esmc']['unexpected_keys'] == []
            and loading['esmc']['native_parameters_loaded'] == 802
            and loading['esmc']['source_encoder_tensors'] == 1042,
            'Unclean or incomplete ESMC checkpoint loading')
    require(native_result['sequence_sha256'] == sequence_sha256
            and native_result['structure']['sha256'] == digest(raw_by_path['output/raw/structure.cif']),
            'Native result structure identity mismatch')
    require(native_result['metrics'] == metrics, 'Native metric reference mismatch')
    require(all(math.isfinite(value) and 0 <= value <= 1 for value in metrics.values()),
            'Invalid native metric value')
    for key in ('elapsed_seconds', 'peak_gpu_memory_bytes', 'peak_process_rss_kib'):
        require(math.isfinite(execution[key]) and execution[key] > 0, 'Invalid resource metric: ' + key)

    native_cif, structure_audit = cif_audit(raw_by_path['output/raw/structure.cif'], sequence)
    require(math.isclose(structure_audit['mean_plddt_from_cif'], metrics['mean_plddt'],
                         rel_tol=0, abs_tol=1e-6), 'Mean pLDDT does not reproduce from CIF')
    require(math.isclose(structure_audit['min_plddt_from_cif'], metrics['min_plddt'],
                         rel_tol=0, abs_tol=1e-6), 'Minimum pLDDT does not reproduce from CIF')
    require(math.isclose(structure_audit['max_plddt_from_cif'], metrics['max_plddt'],
                         rel_tol=0, abs_tol=1e-6), 'Maximum pLDDT does not reproduce from CIF')
    require(len(quality['structure']['plddt_per_residue']) == 76
            and math.isclose(quality['structure']['mean_plddt'], metrics['mean_plddt'],
                             rel_tol=0, abs_tol=1e-6)
            and quality['structure']['ptm'] == metrics['ptm'], 'Quality summary mismatch')
    require(quality['scientific_gate'] == 'CLOSED' and quality['usable_for_pipeline'] is False,
            'Quality qualification boundary changed')

    tool_raw = raw_by_path['output/tool-structure.cif']
    tool_cif, tool_audit = cif_audit(tool_raw, sequence)
    require('_atom_site.occupancy' not in native_cif, 'Native occupancy unexpectedly present')
    require(set(tool_cif['_atom_site.occupancy']) == {'1.0'}, 'Tool occupancy convention differs')
    for key, value in native_cif.items():
        require(tool_cif.get(key) == value, 'Tool structure changed native field: ' + key)
    require(conversion['original_sha256'] == digest(raw_by_path['output/raw/structure.cif'])
            and conversion['derived_sha256'] == digest(tool_raw)
            and conversion['atom_rows'] == structure_audit['atom_count'] == tool_audit['atom_count'],
            'Structure conversion receipt mismatch')
    linked_prediction = linkage['prediction']
    require(linked_prediction['prediction_job_id'] == receipt['prediction_job_id'],
            'Linked prediction job mismatch')
    require(linked_prediction['native_structure_artifact']['sha256'] ==
            digest(raw_by_path['output/raw/structure.cif']), 'Linked native structure mismatch')
    require(linked_prediction['structure_artifact']['sha256'] == digest(tool_raw),
            'Linked tool structure mismatch')
    require(linked_prediction['quality_artifact']['sha256'] ==
            digest(raw_by_path['output/prediction-quality.json']), 'Linked quality mismatch')

    return {
        'schema_version': '1.0',
        'status': 'N12_ESMFOLD2_SAME_RUN_INDEPENDENT_AUDIT_PASS',
        'run_id': receipt['run_id'],
        'jobs': {
            name: {'job_id': job_id, 'tool_id': expected_jobs[job_id],
                   'attempt_id': evidence[job_id]['job']['attempt_id'], 'state': 'succeeded'}
            for name, job_id in (
                ('structure', receipt['structure_job_id']), ('n11', receipt['n11_job_id']),
                ('n12', receipt['n12_job_id']), ('prediction', receipt['prediction_job_id']))
        },
        'artifacts': {
            'reference_count': len(artifact_bytes),
            'unique_saved_file_count': len(referenced_paths),
            'reference_bytes': reference_bytes,
            'all_size_sha256_and_local_bytes_match': True,
        },
        'source_hashes': expected_sources,
        'selection': {
            'sample_number': sample_number,
            'sequence': sequence,
            'sequence_sha256': sequence_sha256,
            'residue_count': len(sequence),
            'mutation_count': len(derived_mutations),
            'esm_if1_score': selected_n12['score'],
            'r35_passed': selected_r35['passed'],
            'r35_reason_code': selected_r35['reason_code'],
            'engine_selection': linkage['engine_selection'],
        },
        'prediction': {
            'native_structure_sha256': digest(raw_by_path['output/raw/structure.cif']),
            'native_structure_size_bytes': len(raw_by_path['output/raw/structure.cif']),
            'tool_structure_sha256': digest(tool_raw),
            'tool_structure_size_bytes': len(tool_raw),
            'structure': structure_audit,
            'metrics': metrics,
            'quality': quality['quality'],
            'checkpoint': {
                'esmfold2_clean': True,
                'esmc_native_parameters_loaded': loading['esmc']['native_parameters_loaded'],
                'esmc_source_encoder_tensors': loading['esmc']['source_encoder_tensors'],
            },
            'execution': execution,
        },
        'scientific_gate': 'CLOSED',
        'usable_for_pipeline': False,
        'automatic_handoff': False,
        'production_status': 'NOT_DEPLOYED',
        'complete_n12_engineering_acceptance': True,
        'complete_scientific_n12': False,
        'limitations': [
            'Selected sample 1 retains its original R-35 exclusion and is not a formal candidate.',
            'The ESMFold2 route is explicit engineering verification, not automatic R-04 routing.',
            'No scientific accuracy or candidate qualification is established.',
            'The resident backend support limit remains 76 residues.',
        ],
    }


def main():
    require(not sys.argv[1:], 'Run without arguments')
    summary = audit()
    summary['auditor_sha256'] = digest(Path(__file__).read_bytes())
    raw = (json.dumps(summary, indent=2, ensure_ascii=False) + '\n').encode()
    output = EVIDENCE / 'audit-summary.json'
    require(not output.exists() or output.read_bytes() == raw,
            'Refusing to overwrite different audit evidence')
    output.write_bytes(raw)
    print(summary['status'])
    print('ARTIFACT_REFERENCES_VERIFIED', summary['artifacts']['reference_count'])
    print('UNIQUE_SAVED_FILES_VERIFIED', summary['artifacts']['unique_saved_file_count'])
    print('SAVED', output)


if __name__ == '__main__':
    main()
