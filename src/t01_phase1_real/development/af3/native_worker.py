"""Run the pinned AF3 data pipeline and five-sample inference in one owned slot."""
from __future__ import annotations

import hashlib
import importlib.metadata
import math
import os
from pathlib import Path
import subprocess
import sys

from .primitives import decode, encode, ensure, sha
from . import policy
from ...gpu_device import POLICY, valid_identity


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, value):
    path.write_bytes(encode(value))


def gpu_identity(expected):
    text = subprocess.check_output(
        ['nvidia-smi', '--query-gpu=name,uuid,memory.total', '--format=csv,noheader,nounits'], text=True)
    rows = [line.split(',') for line in text.strip().splitlines()]
    ensure(len(rows) == 1 and len(rows[0]) == 3, 'PROFILE_NOT_APPROVED', 'Exactly one visible GPU required')
    name, uuid, memory = [part.strip() for part in rows[0]]
    try:
        memory_mib = float(memory)
    except ValueError as exc:
        raise ValueError('GPU memory is not numeric') from exc
    observed = dict(name=name, uuid=uuid, memory_mib=memory_mib)
    ensure(valid_identity(observed) if expected == {'allocation_policy': POLICY} else
           name == expected['name'] and uuid == expected['uuid'] and math.isfinite(memory_mib)
           and memory_mib == expected['memory_mib'],
           'PROFILE_NOT_APPROVED', 'GPU identity does not satisfy the selected allocation policy')
    return dict(name=name, uuid=uuid, memory_mib=memory_mib)


def hmmer_identity(paths=None):
    """Verify the exact HMMER executables used by the AF3 data pipeline."""
    values = policy.HMMER_BINARIES if paths is None else paths
    result = {}
    for name, raw_path in values.items():
        path = Path(raw_path)
        ensure(path.is_file() and os.access(path, os.X_OK), 'ASSET_MISSING',
               'AF3 HMMER executable missing or not executable: ' + str(path))
        result[name] = str(path)
    return result


def database_identity(profile):
    value = profile['database']; root = Path(value['root'])
    receipt = decode(Path(value['receipt']).read_bytes())
    ensure(receipt.get('decompressed') is True and receipt.get('output_root') == root.name
           and receipt.get('file_count') == value['file_count']
           and receipt.get('total_bytes') == value['total_bytes']
           and receipt.get('status') == 'AF3_DATABASES_EXTRACTED_VERIFIED_NOT_DEPLOYED',
           'ASSET_MISSING', 'AF3 extraction receipt differs')
    ensure(all((root / relative).exists() for relative in value['required_paths']),
           'ASSET_MISSING', 'AF3 required database path missing')
    return receipt


def run(request_path, output, profile_path, prepared_msa=None):
    output.mkdir(exist_ok=False)
    request = decode(request_path.read_bytes()); profile = decode(profile_path.read_bytes())
    ensure(request['engine'] == 'alphafold3' and request['asset_profile_id'] == profile['id'],
           'PROFILE_NOT_APPROVED', 'AF3 request/profile differs')
    sequence = request['inputs']['sequence']
    ensure(request['parameters']['seed'] == 1 and request['parameters']['num_samples'] == 5,
           'PROFILE_NOT_APPROVED', 'AF3 seed/sample profile differs')
    model = Path(profile['model']['path'])
    ensure(model.is_file() and file_sha(model) == profile['model']['sha256'],
           'ASSET_MISSING', 'AF3 decompressed weight identity differs')
    database_receipt = database_identity(profile)
    hmmer = hmmer_identity()
    gpu = gpu_identity({'allocation_policy': POLICY})
    write(output / 'request.json', request)
    (output / 'profile.json').write_bytes(profile_path.read_bytes())
    write(output / 'gpu.json', gpu)
    internal_name = 't01-af3-' + sha(sequence.encode())[:16]
    from .msa import folding
    msa_only = request['parameters'].get('mode') == 'msa_only'
    ensure((prepared_msa is not None) == (request['parameters']['msa_mode'] == 'wild_type_reuse'),
           'OUTPUT_INVALID', 'MSA reuse request and staged data differ')
    if prepared_msa is not None:
        ensure(prepared_msa['source'] == request['parameters']['msa_source'], 'OUTPUT_INVALID', 'MSA source binding differs')
    folding_input = folding(sequence, request['parameters']['seed'], prepared_msa)
    write(output / 'fold-input.json', folding_input)
    app_root = Path('/opt/t01/af3-app')
    app_output = output / 'app-output'
    command = ['/alphafold3_venv/bin/python', str(app_root / 'alphafold/run_alphafold.py'),
               '--json_path=' + str(output / 'fold-input.json'),
               '--model_dir=' + str(model.parent), '--db_dir=' + profile['database']['root'],
               '--output_dir=' + str(app_output), '--run_data_pipeline=true',
               '--run_inference=' + ('false' if msa_only else 'true'),
               '--num_diffusion_samples=5', '--gpu_device=0',
               *policy.hmmer_arguments(hmmer),
               '--jackhmmer_n_cpu=' + str(profile['inference']['jackhmmer_n_cpu']),
               '--nhmmer_n_cpu=' + str(profile['inference']['nhmmer_n_cpu']),
               '--max_template_date=' + profile['inference']['max_template_date']]
    write(output / 'command.json', dict(argv=command, cwd=str(app_root / 'alphafold'),
          network='INHERITED_SECCOMP_AND_POD_DENY_ALL', input_sha256=sha(encode(folding_input))))
    environment = {**os.environ, 'HOME':'/tmp', 'TMPDIR':'/tmp', 'XDG_CACHE_HOME':'/tmp/cache',
                   'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONUNBUFFERED':'1', 'JAX_PLATFORMS':'cuda',
                   'XLA_PYTHON_CLIENT_PREALLOCATE':'false'}
    with (output / 'inference.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=app_root / 'alphafold', env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, bufsize=1)
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line); sys.stdout.flush(); log.write(line); log.flush()
        code = process.wait()
    ensure(code == 0, 'TOOL_FAILED', 'AF3 native command failed')
    samples = []
    for directory in sorted(app_output.glob('*/seed-*_sample-*')):
        parts = directory.name.replace('seed-', '').replace('sample-', '').split('_')
        ensure(len(parts) == 2 and all(part.isdigit() for part in parts),
               'OUTPUT_INVALID', 'Unexpected AF3 sample directory')
        seed, sample_index = map(int, parts)
        prefix = directory.parent.name + '_' + directory.name + '_'
        paths = {kind:(directory / (prefix + suffix)).relative_to(output).as_posix() for kind,suffix in {
            'structure':'model.cif', 'confidence':'confidences.json',
            'summary':'summary_confidences.json'}.items()}
        ensure(all((output / path).is_file() and (output / path).stat().st_size for path in paths.values()),
               'OUTPUT_INVALID', 'AF3 native sample artifact missing')
        samples.append(dict(seed=seed, sample_index=sample_index, **paths))
    ensure([(row['seed'], row['sample_index']) for row in samples] == ([] if msa_only else [(1, i) for i in range(5)]),
           'OUTPUT_INVALID', 'Expected exactly five seed-1 AF3 samples')
    execution = dict(source_image_id=profile['source_image_id'], model_sha256=file_sha(model),
        database_receipt=database_receipt, hmmer=hmmer, gpu=gpu, samples=samples,
        gpu_allocation_policy=POLICY,
        packages=dict(alphafold3=importlib.metadata.version('alphafold3'),
                      jax=importlib.metadata.version('jax')),
        scientific_gate='CLOSED', usable_for_pipeline=False, production_status='NOT_DEPLOYED')
    execution['msa_strategy'] = dict(mode='prepare_only' if msa_only else request['parameters']['msa_mode'],
        source=None if prepared_msa is None else prepared_msa['source'],
        staged_sha256=None if prepared_msa is None else sha(encode(prepared_msa)))
    write(output / 'execution.json', execution)
    files = [path for path in sorted(output.rglob('*')) if path.is_file() and path.name != 'manifest.json']
    write(output / 'manifest.json', dict(schema='t01.af3-native-files/1', files=[
        dict(path=path.relative_to(output).as_posix(), size_bytes=path.stat().st_size, sha256=file_sha(path))
        for path in files]))


if __name__ == '__main__':
    raise SystemExit('Use t01_phase1_real.development.af3.worker')
