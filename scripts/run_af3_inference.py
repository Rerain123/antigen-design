"""Fixed 1UBQ engineering inference; preserve all five native AF3 samples."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

from inspect_af3_data_search import inspect, sha256_file

RUN = Path('/runtime/inference-r01')
DATA = Path('/runtime/data-search-r01')
MODEL = Path('/weights/alphafold3-official-r01/af3.bin')
EXPECTED_MODEL = 'df8bbf2621f17dd3ee21c2a921e84a50bc2b80cdc0c7971cb915c2826fee1f9b'
EXPECTED_MANIFEST = '72c5fb24d43dc1c3c6be13ad8c4e8ead1625d4944fdd48b5d73fb4741894baac'


def validate_gpu(text):
    rows = [r.split(',') for r in text.strip().splitlines()]
    if len(rows) != 1 or len(rows[0]) != 3:
        raise ValueError('Exactly one GPU required')
    name, uuid, memory = [v.strip() for v in rows[0]]
    if name != 'NVIDIA A100-SXM-64GB' or not uuid.startswith('GPU-'):
        raise ValueError('Approved 64GB GPU identity required')
    if not math.isfinite(float(memory)) or float(memory) < 60000:
        raise ValueError('Insufficient visible GPU memory')
    return {'name': name, 'uuid': uuid, 'memory_MiB': float(memory)}


def write(name, value):
    (RUN / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    RUN.mkdir(exist_ok=False)
    started = time.monotonic()
    gpu = validate_gpu(subprocess.check_output(
        ['nvidia-smi', '--query-gpu=name,uuid,memory.total', '--format=csv,noheader,nounits'], text=True))
    write('gpu.json', gpu)
    print('AF3_INFERENCE_GPU_VERIFIED', json.dumps(gpu), flush=True)
    if sha256_file(DATA / 'files-manifest.json') != EXPECTED_MANIFEST:
        raise ValueError('Data-search manifest differs from independently verified receipt')
    inspect()
    if sha256_file(MODEL) != EXPECTED_MODEL:
        raise ValueError('Decompressed model hash differs')
    source = DATA / 'output/t01-1ubq-af3-data-r01/t01-1ubq-af3-data-r01_data.json'
    value = json.loads(source.read_bytes())
    sequence = value['sequences'][0]['protein']['sequence']
    if hashlib.sha256(sequence.encode()).hexdigest() != '233b4b0b8c4616095bc3249f9375fc345d32af7deaef07117d0383c51d6f19aa' or value['modelSeeds'] != [1]:
        raise ValueError('Pinned input identity differs')
    input_path = RUN / 'input.json'
    input_path.write_bytes(source.read_bytes())
    command = ['/alphafold3_venv/bin/python', '/app/alphafold/run_alphafold.py',
               '--json_path=' + str(input_path), '--model_dir=' + str(MODEL.parent),
               '--output_dir=' + str(RUN / 'output'), '--run_data_pipeline=false',
               '--run_inference=true', '--num_diffusion_samples=5', '--gpu_device=0']
    write('command.json', {'command': command, 'input_sha256': sha256_file(input_path),
                          'model_sha256': EXPECTED_MODEL, 'source_manifest_sha256': EXPECTED_MANIFEST,
                          'network_policy': 'DENY_ALL', 'gpu': gpu})
    env = {**os.environ, 'HOME': '/tmp', 'TMPDIR': '/tmp', 'PYTHONUNBUFFERED': '1'}
    print('AF3_INFERENCE_START seed=1 samples=5', flush=True)
    with (RUN / 'inference.log').open('w') as log:
        process = subprocess.Popen(command, cwd='/app/alphafold', env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='', flush=True)
            log.write(line)
            log.flush()
        code = process.wait()
    if code:
        raise RuntimeError('AF3 exited with code ' + str(code))
    samples = sorted((RUN / 'output').glob('*/seed-1_sample-*'))
    if {p.name for p in samples} != {f'seed-1_sample-{i}' for i in range(5)}:
        raise ValueError('Expected all five native sample directories')
    for sample in samples:
        for name in ('model.cif', 'confidences.json', 'summary_confidences.json'):
            path = sample / (sample.parent.name + '_' + sample.name + '_' + name)
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError('Missing native output: ' + str(path))
        summary = json.loads((sample / (sample.parent.name + '_' + sample.name + '_summary_confidences.json')).read_bytes())
        if not isinstance(summary.get('ptm'), (int, float)) or not 0 <= summary['ptm'] <= 1:
            raise ValueError('Invalid native pTM')
    files = [{'path': p.relative_to(RUN).as_posix(), 'bytes': p.stat().st_size,
              'sha256': sha256_file(p)} for p in sorted(RUN.rglob('*')) if p.is_file()]
    write('files-manifest.json', {'files': files})
    receipt = {'status': 'AF3_FIVE_NATIVE_SAMPLES_GENERATED_PENDING_INDEPENDENT_AUDIT',
               'sample_count': 5, 'elapsed_seconds': time.monotonic() - started,
               'gpu': gpu, 'files_manifest_sha256': sha256_file(RUN / 'files-manifest.json'),
               'scientific_gate': 'CLOSED', 'usable_for_pipeline': False, 'production_status': 'NOT_DEPLOYED'}
    write('receipt.json', receipt)
    print('AF3_INFERENCE_COMPLETE', json.dumps(receipt), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if RUN.exists():
            write('failure.json', {'status':'FAILED_PARTIAL_RETAINED', 'error':str(error), 'scientific_gate':'CLOSED'})
        raise
