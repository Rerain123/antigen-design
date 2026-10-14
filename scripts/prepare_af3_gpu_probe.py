"""Render a single-device AF3/JAX probe, restricted to the approved 64GB type."""
import copy
from pathlib import Path

import yaml
from prepare_af3_data_search import documents, ROOT

NAME = 'antigen-af3-gpu64-probe-r01'
OUTPUT = ROOT / 'deploy/alphafold3/gpu64-probe.r01.rancher.yaml'
CODE = '''import json, subprocess
from pathlib import Path
rows = [r.split(',') for r in subprocess.check_output(['nvidia-smi', '--query-gpu=name,uuid,memory.total', '--format=csv,noheader,nounits'], text=True).strip().splitlines()]
if len(rows) != 1 or rows[0][0].strip() != 'NVIDIA A100-SXM-64GB':
    raise RuntimeError('Expected exactly one approved A100-SXM-64GB: ' + repr(rows))
name, uuid, memory = [v.strip() for v in rows[0]]
if float(memory) < 60000:
    raise RuntimeError('64GB device has insufficient visible memory: ' + memory)
print('AF3_GPU64_IDENTITY', json.dumps({'name': name, 'uuid': uuid, 'memory_MiB': float(memory)}), flush=True)
import jax
import jax.numpy as jnp
devices = jax.devices()
if len(devices) != 1 or devices[0].platform != 'gpu':
    raise RuntimeError('Expected exactly one JAX GPU: ' + repr(devices))
x = jnp.ones((128,128), dtype=jnp.float32)
y = (x @ x).block_until_ready()
if not bool(jnp.all(y == 128)):
    raise RuntimeError('JAX compute check failed')
receipt = {'status': 'AF3_GPU64_JAX_VERIFIED_NOT_INFERRED', 'name': name, 'uuid': uuid, 'memory_MiB': float(memory), 'jax': jax.__version__, 'scientific_gate': 'CLOSED', 'usable_for_pipeline': False}
out = Path('/runtime/gpu64-probe-r01')
out.mkdir(exist_ok=False)
(out/'receipt.json').write_text(json.dumps(receipt, indent=2))
help_result = subprocess.run(['/alphafold3_venv/bin/python', '/app/alphafold/run_alphafold.py', '--helpfull'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
(out/'entrypoint-help.txt').write_text(help_result.stdout)
for line in help_result.stdout.splitlines():
    if any(word in line for word in ('num_diffusion_samples', 'flash_attention', 'gpu_device', 'buckets')):
        print(line, flush=True)
print('AF3_GPU64_JAX_VERIFIED', json.dumps(receipt), flush=True)
'''


def probe_documents():
    base = documents()
    cm, policy, job = copy.deepcopy(base[0]), copy.deepcopy(base[1]), copy.deepcopy(base[3])
    for doc in (cm, policy, job):
        doc['metadata']['name'] = NAME
    cm['data'] = {'probe.py': CODE}
    policy['spec']['podSelector']['matchLabels'] = {'app': NAME}
    job['spec']['activeDeadlineSeconds'] = 900
    template = job['spec']['template']
    template['metadata'] = {'labels': {'app': NAME}, 'annotations': {
        'nvidia.com/use-gputype': 'A100-SXM-64GB'}}
    pod = template['spec']
    pod['runtimeClassName'] = 'nvidia'
    pod['schedulerName'] = 'hami-scheduler'
    pod['volumes'] = [v for v in pod['volumes'] if v['name'] in ('runner', 'runtime', 'tmp')]
    pod['volumes'][0]['configMap']['name'] = NAME
    c = pod['containers'][0]
    c['name'] = 'probe'
    c['command'] = ['/alphafold3_venv/bin/python', '-u', '-B', '/runner/probe.py']
    c['env'] = [{'name':'JAX_PLATFORMS','value':'cuda'}, {'name':'XLA_PYTHON_CLIENT_PREALLOCATE','value':'false'}, {'name':'HOME','value':'/tmp'}]
    c['resources'] = {'requests': {'cpu':'1','memory':'4Gi'}, 'limits': {
        'cpu':'4','memory':'16Gi','nvidia.com/gpu':1,'nvidia.com/gpumem-percentage':100,'nvidia.com/gpucores':100}}
    c['volumeMounts'] = [v for v in c['volumeMounts'] if v['name'] in ('runner','runtime','tmp') and v['mountPath'] != '/input']
    return [cm, policy, job]


if __name__ == '__main__':
    OUTPUT.write_text(yaml.safe_dump_all(probe_documents(), sort_keys=False), encoding='utf-8')
    print(OUTPUT)
