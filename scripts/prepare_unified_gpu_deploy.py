"""Prepare immutable config and a CAS patch for one resident 64GB GPU Worker."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import subprocess

import yaml

from prepare_single_gpu_cpu_mode import K, ROOT

UUID = 'GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31'
CONFIG_NAME = 'antigen-unified-gpu-config-r10'
CODE_NAME = 'antigen-unified-gpu-code-r12'
GPU_TOOLS = ('proteinmpnn', 'esm-if1', 'thermompnn', 'af3')
CODE_FILES = (
    'unified_gpu_worker.py', 'resident_process.py', 'resident_worker.py',
    'resident_offline.py', 'process_control/__init__.py', 'process_control/posix.py',
    'development/__init__.py',
    'development/af3/__init__.py', 'development/af3/native_worker.py',
    'development/af3/policy.py', 'development/af3/primitives.py',
    'development/af3/profile.json', 'development/af3/result.py',
    'development/af3/source.py', 'development/af3/standard.py',
    'development/af3/worker.py', 'development/esmfold2/primitives.py',
    'development/esmfold2/quality.py')


def relocated(command):
    row = copy.deepcopy(command)
    tool = row['tool']
    environment = row['environment']
    prefix = '/opt/t01/env/' + ('proteinmpnn' if tool == 'proteinmpnn' else tool)
    if tool == 'af3':
        row['argv'][0] = '/usr/local/bin/python'
        environment.pop('PYTHONHOME', None)
        environment.pop('LD_LIBRARY_PATH', None)
        environment['PYTHONPATH'] = '/opt/t01/src'
        environment['T01_NATIVE_CWD'] = '/opt/t01/af3-app/alphafold'
        environment['T01_NATIVE_PACKAGE'] = '/opt/t01/af3-app'
        environment['T01_RESIDENT_SLOT'] = '/run/t01-slot'
        environment['T01_PRIVATE_TMP'] = '1'
        environment['T01_PRECREATE_NATIVE'] = '0'
        return row
    if tool == 'esmfold2':
        prefix = '/opt/t01/env/esmfold2'
    # The original resident image uses its base interpreter with PYTHONHOME
    # redirected into each copied tool environment.  Keep that ABI/layout: the
    # copied tool prefixes do not necessarily contain a self-contained Python
    # executable or its console-script metadata.
    row['argv'][0] = '/opt/t01/env/esmfold2/bin/python' if tool == 'esmfold2' else '/opt/t01/env/proteinmpnn/bin/python'
    environment['PYTHONHOME'] = prefix
    environment['LD_LIBRARY_PATH'] = prefix + '/lib'
    old_path = environment.get('PATH', '/usr/local/bin:/usr/bin:/bin')
    binary_path = prefix + '/bin'
    environment['PATH'] = binary_path + ':' + ':'.join(
        part for part in old_path.split(':')
        if part and part not in ('/usr/local/bin', binary_path))
    # The unified image owns /tmp and the native aliases through the per-task
    # slot.  The former standalone ESMFold2 deployment supplied this through
    # its image entrypoint; when the command is run by the shared resident
    # supervisor it must be explicit in the command environment.
    if tool == 'esmfold2':
        environment['T01_RESIDENT_SLOT'] = '/run/t01-slot'
        environment['T01_PRIVATE_TMP'] = '1'
        environment['T01_PRECREATE_NATIVE'] = '0'
    return row


def configs(current):
    gpu = json.loads(current['data']['gpu.worker.json'])
    esm = json.loads(current['data']['esmfold2.worker.json'])
    resident = json.loads(current['data']['resident.json'])
    gpu['commands'] = [relocated(row) for row in gpu['commands']]
    esm['commands'] = [relocated(row) for row in esm['commands'] if row['tool'] != 'af3']
    esm['commands'].append({
        'tool': 'af3',
        'argv': ['/alphafold3_venv/bin/python', '-B', '-m',
                 't01_phase1_real.development.af3.worker',
                 '--input-dir', '{input}', '--output-dir', '{output}/native'],
        'environment': {
            'PYTHONPATH': '/opt/t01/src',
            'PYTHONUNBUFFERED': '1',
            'T01_NATIVE_CWD': '/opt/t01/af3-app/alphafold',
            'T01_NATIVE_PACKAGE': '/opt/t01/af3-app',
            'T01_PRIVATE_TMP': '1',
            'T01_PRECREATE_NATIVE': '0',
            'T01_RESIDENT_OFFLINE': '1',
            'T01_RESIDENT_SLOT': '/run/t01-slot',
            'T01_SHARED_GPU_LOCK': '/var/lib/t01/.gpu-execution.lock',
            'T01_SOURCE_IMAGE_ID': 'sha256:35db7c1feb3368a7c72b0d1f60b295ed1473b562b61526db265fc0c446fd4373',
        },
        'memory_bytes': 274877906944,
        # AF3's successful data-search result is small, but Jackhmmer writes a
        # larger bounded Stockholm intermediate before AF3 truncates/parses it.
        'file_size_bytes': 512 * 1024 ** 2,
    })
    af3 = copy.deepcopy(esm)
    af3['commands'] = [row for row in esm['commands'] if row['tool'] == 'af3']
    esm['commands'] = [row for row in esm['commands'] if row['tool'] != 'af3']
    resident['tools'].setdefault('af3', {
        'root': '/var/lib/t01/resident/af3',
        'source_image_id': 'sha256:35db7c1feb3368a7c72b0d1f60b295ed1473b562b61526db265fc0c446fd4373',
    })
    changed = {row['tool']: row for row in gpu['commands'] + esm['commands'] + af3['commands']}
    if set(changed) != {*GPU_TOOLS, 'esmfold2'}:
        raise ValueError('Unexpected registered GPU tools')
    for tool, command in changed.items():
        if tool not in resident['tools']:
            raise ValueError('GPU tool absent from service registry')
        resident['tools'][tool]['command'] = command
    unified = {
        'version': '0.1.0', 'uuid': UUID,
        'state_root': '/var/lib/t01/resident/unified-gpu',
        'spools': [
            {'root': '/var/lib/t01/resident/gpu', 'config': '/etc/t01/gpu.worker.json'},
            {'root': '/var/lib/t01/resident/esmfold2', 'config': '/etc/t01/esmfold2.worker.json'},
            {'root': '/var/lib/t01/resident/af3', 'config': '/etc/t01/af3.worker.json'},
        ],
    }
    return {name: json.dumps(value, sort_keys=True, separators=(',', ':')) for name, value in {
        'resident.json': resident, 'gpu.worker.json': gpu,
        'esmfold2.worker.json': esm, 'af3.worker.json': af3,
        'unified-gpu.json': unified}.items()}


def manifests(current):
    data = configs(current)
    code = {}
    for relative in CODE_FILES:
        path = ROOT / 'src/t01_phase1_real' / relative
        code[relative.replace('/', '--')] = path.read_text(encoding='utf-8')
    return [
        {'apiVersion': 'v1', 'kind': 'ConfigMap',
         'metadata': {'name': CONFIG_NAME, 'namespace': 'him-ws'},
         'immutable': True, 'data': data},
        {'apiVersion': 'v1', 'kind': 'ConfigMap',
         'metadata': {'name': CODE_NAME, 'namespace': 'him-ws'},
         'immutable': True, 'data': code},
    ]


def patch(live, image):
    if not re.fullmatch(r'harbor-core\.base\.svc\.cluster\.local/qcyz/antigen-unified-gpu@sha256:[a-f0-9]{64}', image):
        raise ValueError('Immutable unified image digest required')
    if live['spec']['strategy'] != {'type': 'Recreate'} or live['spec']['replicas'] != 1:
        raise ValueError('Expected singleton Recreate deployment')
    template = copy.deepcopy(live['spec']['template'])
    spec = template['spec']
    old = [row for row in spec['containers'] if row['name'] in ('worker-gpu', 'worker-esmfold2', 'worker-unified-gpu')]
    if len(old) != 1 or old[0]['name'] not in ('worker-esmfold2', 'worker-unified-gpu'):
        raise ValueError('Expected exactly one current GPU holder')
    spec['containers'] = [row for row in spec['containers'] if row not in old]
    volumes = {row['name']: row for row in spec['volumes']}
    for required in ('runtime', 'tool-assets', 'esmfold2-models', 'slot-gpu', 'esmfold2-code', 'resident-config'):
        if required not in volumes:
            raise ValueError('Required deployment volume missing: ' + required)
    volumes.setdefault('af3-models', {
        'name': 'af3-models',
        'persistentVolumeClaim': {'claimName': 'antigen-af3-models', 'readOnly': True},
    })
    volumes.setdefault('af3-databases', {
        'name': 'af3-databases',
        'persistentVolumeClaim': {'claimName': 'antigen-af3-databases', 'readOnly': True},
    })
    volumes['resident-config']['configMap']['name'] = CONFIG_NAME
    if 'unified-gpu-code' in volumes:
        volumes['unified-gpu-code']['configMap']['name'] = CODE_NAME
    else:
        spec['volumes'].append({'name': 'unified-gpu-code', 'configMap': {'name': CODE_NAME}})
    spec['volumes'] = list(volumes.values())
    mounts = [
        {'name': 'runtime', 'mountPath': '/var/lib/t01'},
        {'name': 'tool-assets', 'mountPath': '/t01/assets', 'readOnly': True},
        {'name': 'esmfold2-models', 'mountPath': '/models', 'readOnly': True},
        {'name': 'af3-models', 'mountPath': '/af3-weights', 'readOnly': True},
        {'name': 'af3-databases', 'mountPath': '/af3-databases', 'readOnly': True},
        {'name': 'slot-gpu', 'mountPath': '/run/t01-slot'},
        {'name': 'esmfold2-code', 'mountPath': '/backend', 'readOnly': True},
        {'name': 'resident-config', 'mountPath': '/etc/t01/resident.json',
         'subPath': 'resident.json', 'readOnly': True},
        {'name': 'resident-config', 'mountPath': '/etc/t01/gpu.worker.json',
         'subPath': 'gpu.worker.json', 'readOnly': True},
        {'name': 'resident-config', 'mountPath': '/etc/t01/esmfold2.worker.json',
         'subPath': 'esmfold2.worker.json', 'readOnly': True},
        {'name': 'resident-config', 'mountPath': '/etc/t01/af3.worker.json',
         'subPath': 'af3.worker.json', 'readOnly': True},
        {'name': 'resident-config', 'mountPath': '/etc/t01/unified-gpu.json',
         'subPath': 'unified-gpu.json', 'readOnly': True},
    ]
    for relative in CODE_FILES:
        mounts.append({'name': 'unified-gpu-code',
            'mountPath': '/opt/t01/src/t01_phase1_real/' + relative,
            'subPath': relative.replace('/', '--'), 'readOnly': True})
    # AF3 runs four local Jackhmmer database searches after its combined path
    # has already loaded/checked the model.  The standalone split stages each
    # passed within 96 GiB, but r10 saturated that bound when both lifetimes
    # overlapped.  Reserve 96 GiB and retain a bounded 128 GiB ceiling.
    resources = {'requests': {'cpu': '8', 'memory': '96Gi', 'ephemeral-storage': '2Gi',
                              'nvidia.com/gpu': '1', 'nvidia.com/gpumem-percentage': '100',
                              'nvidia.com/gpucores': '100'},
                 'limits': {'cpu': '16', 'memory': '128Gi', 'ephemeral-storage': '8Gi',
                            'nvidia.com/gpu': '1', 'nvidia.com/gpumem-percentage': '100',
                            'nvidia.com/gpucores': '100'}}
    spec['containers'].append({
        'name': 'worker-unified-gpu', 'image': image, 'imagePullPolicy': 'IfNotPresent',
        'command': ['/opt/t01/supervisor/bin/python3.11', '-u', '-B', '-m',
                    't01_phase1_real.unified_gpu_worker'],
        'args': ['--config', '/etc/t01/unified-gpu.json'],
        'env': [
            {'name': 'PYTHONHOME', 'value': '/opt/t01/supervisor'},
            {'name': 'PYTHONPATH', 'value': '/opt/t01/src'},
            {'name': 'LD_LIBRARY_PATH', 'value': '/opt/t01/supervisor/lib'},
        ],
        'resources': resources,
        'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                            'runAsNonRoot': True, 'runAsUser': 10001, 'runAsGroup': 10001,
                            'capabilities': {'drop': ['ALL']}},
        'volumeMounts': mounts,
    })
    spec['runtimeClassName'] = 'nvidia'
    spec['schedulerName'] = 'hami-scheduler'
    annotations = template['metadata'].setdefault('annotations', {})
    annotations.update({'antigen-design/gpu-mode': 'unified-resident-single64',
                        'antigen-design/gpu-worker-host-profile': 'af3-combined-96-128gi-8-16cpu-r02',
                        'nvidia.com/use-gputype': 'A100-SXM-64GB',
                        'nvidia.com/use-gpuuuid': UUID})
    # The meaningful configuration hashes are carried by immutable ConfigMaps;
    # this annotation identifies the deployment mechanism without duplicating data.
    annotations['antigen-design/gpu-worker-config'] = CONFIG_NAME
    return [
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': live['metadata']['resourceVersion']},
        {'op': 'test', 'path': '/metadata/uid', 'value': live['metadata']['uid']},
        {'op': 'test', 'path': '/spec', 'value': live['spec']},
        {'op': 'replace', 'path': '/spec/template', 'value': template},
    ]


def main():
    global CONFIG_NAME, CODE_NAME
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    parser.add_argument('--config-name', default=CONFIG_NAME)
    parser.add_argument('--code-name', default=CODE_NAME)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'deploy/single-gpu/unified-worker.r09.yaml')
    parser.add_argument('--output', type=Path, default=ROOT / '.tmp/unified-gpu-worker-r15')
    args = parser.parse_args()
    CONFIG_NAME, CODE_NAME = args.config_name, args.code_name
    live = json.loads(subprocess.check_output(K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    resident_volume = next(v for v in live['spec']['template']['spec']['volumes'] if v['name'] == 'resident-config')
    current = json.loads(subprocess.check_output(K + ['get', 'configmap', resident_volume['configMap']['name'], '-o', 'json']))
    documents = manifests(current)
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    manifest_path.write_text(yaml.safe_dump_all(documents, sort_keys=False), encoding='utf-8')
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.mkdir(parents=True, exist_ok=False)
    patch_path = output / 'patch.json'
    patch_path.write_text(json.dumps(patch(live, args.image), indent=2), encoding='utf-8')
    subprocess.run(K + ['apply', '--dry-run=server', '-f', str(manifest_path)], check=True)
    subprocess.run(K + ['patch', 'deployment', 'antigen-design', '--type=json',
                         '--patch-file', str(patch_path), '--dry-run=server', '-o', 'name'], check=True)
    print('UNIFIED_GPU_DEPLOYMENT_PREPARED', manifest_path, patch_path)


if __name__ == '__main__': main()
