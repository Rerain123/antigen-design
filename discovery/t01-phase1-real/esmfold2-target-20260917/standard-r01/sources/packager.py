"""Offline standard packaging of the verified r03 result; never runs a model.

This adapter supports the pinned r03 native layout only. New executions require
their own registered provenance before this adapter can accept them.
"""
import argparse
import hashlib
import json
from pathlib import Path
import uuid

import yaml

try:
    from scripts.audit_esmfold2_r03 import ROOT, EVIDENCE, REQUIRED, audit, require
except ModuleNotFoundError:
    from audit_esmfold2_r03 import ROOT, EVIDENCE, REQUIRED, audit, require

NATIVE_MANIFEST_SHA256 = 'b63863eef447cbb52046b0ea796fc45d6eb456e4e80870a6bc285d2328aa760e'
JOB_SHA256 = 'c153e894e536855c1d9f0dd6b6782d6603e5941d965e404a3e1201a5cff247af'
LOG_SHA256 = '241712728b4008c0879a4c9f6dcd21cb62e96f6482b7f0411735b1e507e46c69'
SOURCES = {
    'packager.py': 'scripts/package_esmfold2_result.py',
    'auditor.py': 'scripts/audit_esmfold2_r03.py',
    'collector.py': 'scripts/collect_esmfold2_r03.py',
    'validation.yaml': 'deploy/esmfold2-standard/validation.r03.rancher.yaml',
    'environment.json': 'deploy/esmfold2-standard/environment.json',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def regular(path):
    require(not path.is_symlink() and path.is_file(), 'Missing or linked file: ' + str(path))
    return path.read_bytes()


def build(native, job_bytes, log_bytes, sources):
    require(sha(native['manifest.json']) == NATIVE_MANIFEST_SHA256, 'Unregistered native manifest')
    require(sha(job_bytes) == JOB_SHA256 and sha(log_bytes) == LOG_SHA256, 'Unregistered execution provenance')
    job = json.loads(job_bytes)
    bundle = list(yaml.safe_load_all(sources['validation.yaml'].decode('utf-8')))
    checked = audit(native, job, bundle)
    attempt_id = str(uuid.UUID(job['metadata']['uid']))
    request = json.loads(native['request.json'])
    profile = json.loads(native['profile.json'])
    metrics = checked['metrics']
    sequence = request['inputs']['sequence']
    sequence_hash = sha(sequence.encode('ascii'))
    model_id = 'esmfold2-seed-1-sample-0'
    scores = checked['structure']['residue_plddt_0_to_1']
    # The auditor checked auth and label numbering, chain, insertion and alternates.
    # r03 exports the token score * 100 identically on every atom in each residue.
    confidence = {
        'model_id': model_id, 'sequence_sha256': sequence_hash,
        'raw_scale': '0_100',
        'raw_source': 'raw/structure.cif#_atom_site.B_iso_or_equiv',
        'normalization': 'Exported token pLDDT * 100; divide CIF B factor by 100 once.',
        'definition_source': checked['confidence_source'],
        'mean_plddt': sum(scores) / len(scores),
        'residues': [dict(sequence_position=i, amino_acid=aa, chain_id='A',
                          label_seq_id=i, auth_seq_id=i, insertion_code='',
                          plddt_raw=score * 100, plddt=score, missing_reason=None)
                     for i, (aa, score) in enumerate(zip(sequence, scores), 1)],
    }
    output = {'raw/' + name: raw for name, raw in native.items()}
    output.update({'raw/cluster-job.json': job_bytes, 'logs/cluster.log': log_bytes})
    output.update({'sources/' + name: raw for name, raw in sources.items()})
    for name in ('run_structure.py', 'esmc_strict_loader.py'):
        output['sources/' + name] = bundle[1]['data'][name].encode('utf-8')
    output['profile.json'] = native['profile.json']
    output['request.json'] = native['request.json']
    output['confidence/' + model_id + '.json'] = encode(confidence)
    parameters = {'request_parameters': request['parameters'], 'inference': profile['inference'],
                  'msa_mode': 'none', 'variant': 'standard'}
    output['parameters.json'] = encode(parameters)
    provenance = {
        'schema_version': '1.0', 'native_manifest_sha256': NATIVE_MANIFEST_SHA256,
        'asset_manifest_sha256': profile['asset_manifest_sha256'],
        'environment_manifest_sha256': profile['environment_manifest_sha256'],
        'profile_sha256': sha(native['profile.json']), 'request_sha256': sha(native['request.json']),
        'native_files': checked['source_sha256'],
        'source_files': {name: sha(raw) for name, raw in sorted(output.items())
                         if name.startswith('sources/')},
        'cluster_job_sha256': sha(job_bytes), 'cluster_log_sha256': sha(log_bytes),
        'engine_version': {'biohub_esm_commit': 'b6b0e8815dc3174a9fe9afd36b222aea57d536c5',
                           'biohub_transformers_commit': 'ef32577f55da19a4989cd7b22e004dc43a4998cb'},
        'checkpoint_loading_path': 'raw/checkpoint-loading.json',
        'source_attempt_id': attempt_id, 'source_attempt_id_kind': 'kubernetes_job_uid',
        'packaging_kind': 'offline_derivation_from_completed_r03_not_new_inference',
    }
    output['provenance.json'] = encode(provenance)
    output['execution.json'] = encode({
        'attempt_id': attempt_id, 'job_name': job['metadata']['name'],
        'start_time_utc': job['status'].get('startTime'),
        'completion_time_utc': job['status'].get('completionTime'),
        'job_succeeded': job['status']['succeeded'],
        'command': job['spec']['template']['spec']['containers'][0]['command'],
        'args': job['spec']['template']['spec']['containers'][0]['args'],
        'image': job['spec']['template']['spec']['containers'][0]['image'],
        'resource_limits': job['spec']['template']['spec']['containers'][0]['resources'],
        'native_measurements': checked['execution'],
        'gpu_inference_seconds': None, 'cpu_preparation_seconds': None,
        'driver_version': None, 'exit_code': None,
        'unavailable_reason': 'r03 did not archive a Pod exit/driver record or separate stage timings in this bundle.',
        'log_path': 'logs/cluster.log', 'log_streams': 'combined Kubernetes log; separate stdout/stderr unavailable',
        'network_policy_path': 'sources/validation.yaml', 'active_egress_probe_verified': False,
        'measurement_limits': checked['limitations'],
    })
    model = {
        'model_id': model_id, 'seed': request['parameters']['seed'], 'sample_index': 0,
        'source': 'esmfold2_predicted', 'structure_path': 'raw/structure.cif',
        'structure_sha256': sha(native['structure.cif']), 'format': 'mmcif', 'chain_id': 'A',
        'confidence_path': 'confidence/' + model_id + '.json',
        'confidence_sha256': sha(output['confidence/' + model_id + '.json']),
        'mean_plddt': confidence['mean_plddt'], 'ptm': metrics['ptm'], 'iptm': None,
        'iptm_not_applicable_reason': 'single_chain', 'raw_scores': metrics,
    }
    output['result.json'] = encode({
        'contract_version': request['contract_version'], 'request_id': request['request_id'],
        'attempt_id': attempt_id, 'status': 'succeeded', 'engine': 'esmfold2',
        'engine_version': provenance['engine_version'], 'asset_profile_id': profile['id'],
        'asset_manifest_sha256': profile['asset_manifest_sha256'],
        'environment_manifest_sha256': profile['environment_manifest_sha256'],
        'profile_sha256': sha(native['profile.json']),
        'sequence_id': request['inputs']['sequence_id'], 'sequence': sequence,
        'sequence_sha256': sequence_hash, 'host_species': request['inputs']['host_species'],
        'models': [model], 'parameters_path': 'parameters.json',
        'parameters_sha256': sha(output['parameters.json']),
        'provenance_path': 'provenance.json', 'provenance_sha256': sha(output['provenance.json']),
        'errors': [], 'warnings': [
            {'code': 'ENGINEERING_ONLY', 'message': 'Scientific qualification and automatic handoff remain closed.'},
            {'code': 'SINGLE_CHAIN_IPTM_NOT_APPLICABLE', 'message': 'Native ipTM=0 preserved in raw_scores; normalized ipTM=null.'},
            {'code': 'ARCHIVED_EXECUTION_LIMITS', 'message': 'Combined logs only; driver, Pod exit record and separate stage timings unavailable in archived bundle.'},
            {'code': 'OFFLINE_PACKAGING_ONLY', 'message': 'Existing r03 inference was packaged; no new execution or backend integration is claimed.'}],
        'scientific_gate': 'CLOSED', 'usable_for_pipeline': False, 'automatic_handoff': False,
    })
    output['manifest.json'] = encode({'schema_version': '1.0', 'files': [
        {'path': name, 'size_bytes': len(raw), 'sha256': sha(raw)} for name, raw in sorted(output.items())]})
    return output


def package(source, destination):
    source, destination = Path(source).resolve(), Path(destination).absolute()
    require(not destination.exists(), 'Output directory already exists')
    require(not destination.is_relative_to(source), 'Output must be outside native evidence')
    native = {name: regular(source / name) for name in REQUIRED | {'manifest.json'}}
    sources = {name: regular(ROOT / path) for name, path in SOURCES.items()}
    output = build(native, regular(source / 'cluster-job.json'), regular(source / 'cluster.log'), sources)
    # All semantic validation precedes writing. A manifest is published last;
    # any interrupted directory without it is incomplete and cannot pass verify.
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in output.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    verify(destination)
    return destination


def verify(folder):
    folder = Path(folder)
    require(not folder.is_symlink(), 'Linked output directory')
    paths = list(folder.rglob('*'))
    require(not any(p.is_symlink() for p in paths), 'Linked output member')
    actual = {p.relative_to(folder).as_posix(): regular(p) for p in paths if p.is_file()}
    native = {name: actual['raw/' + name] for name in REQUIRED | {'manifest.json'}}
    sources = {name: actual['sources/' + name] for name in SOURCES}
    require(all(sources[name] == regular(ROOT / path) for name, path in SOURCES.items()),
            'Packaging source snapshot differs from current registered implementation')
    expected = build(native, actual['raw/cluster-job.json'], actual['logs/cluster.log'], sources)
    require(actual == expected, 'Standard package content or manifest mismatch')
    return {'status': 'ESMFOLD2_STANDARD_PACKAGE_VERIFIED', 'files': len(actual),
            'residues': 76, 'manifest_sha256': sha(actual['manifest.json'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=EVIDENCE)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output-dir', type=Path)
    group.add_argument('--verify', type=Path)
    args = parser.parse_args()
    folder = args.verify if args.verify else package(args.source, args.output_dir)
    print(json.dumps(verify(folder), ensure_ascii=False))
    print('SAVED' if args.output_dir else 'VERIFIED', folder)


if __name__ == '__main__':
    main()
