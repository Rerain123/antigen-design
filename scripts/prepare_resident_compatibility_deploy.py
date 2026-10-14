"""Prepare a CAS-protected resident compatibility rollout.

The first AF3 target run exposed a wire-format transition: the new service
included the optional default ``file_size_bytes`` field while the older CPU
resident image did not.  The first successful AF3 prediction also exposed a
stale service-side structure validator that dropped the registered AF3 source
while recomputing S-09.  This script publishes both compatibility fixes and
rolls the service/unified-worker overlays together.  It only prepares immutable
ConfigMaps and a server-dry-run JSON patch; the caller applies the generated
artifacts explicitly.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_unified_gpu_deploy as unified

K = [
    'C:/Program Files/Docker/Docker/resources/bin/kubectl.exe', '--kubeconfig',
    str(ROOT / '.tmp/himat.kubeconfig'), '--request-timeout=90s', '-n', 'him-ws'
]

SERVICE_NAME = 'antigen-af3-service-code-r07'
UNIFIED_CONFIG_NAME = 'antigen-unified-gpu-config-r11'
UNIFIED_CODE_NAME = 'antigen-unified-gpu-code-r13'
STRUCTURE_NAME = 'antigen-resident-compat-code-r01'
OUTPUT = ROOT / '.tmp/resident-compatibility-r02'
IMAGE = None

SERVICE_FILES = (
    'resident_execution.py', 'resident_process.py',
    'development/contracts.py', 'development/registry.py',
    'development/runtime.py', 'development/supervisor.py',
    'development/workflow/policy.py', 'development/workflow/service.py',
    'development/af3/__init__.py', 'development/af3/native_worker.py',
    'development/af3/policy.py', 'development/af3/primitives.py',
    'development/af3/profile.json', 'development/af3/result.py',
    'development/af3/source.py', 'development/af3/standard.py',
    'development/af3/worker.py', 'development/esmfold2/primitives.py',
    'development/esmfold2/quality.py', 'development/structure/result.py',
)


def source(relative: str) -> str:
    return (ROOT / 'src/t01_phase1_real' / relative).read_text(encoding='utf-8')


def service_configmap(namespace: str) -> dict:
    return {
        'apiVersion': 'v1', 'kind': 'ConfigMap',
        'metadata': {'name': SERVICE_NAME, 'namespace': namespace},
        'immutable': True,
        'data': {'af3-' + path.replace('/', '--'): source(path) for path in SERVICE_FILES},
    }


def structure_configmap(namespace: str) -> dict:
    return {
        'apiVersion': 'v1', 'kind': 'ConfigMap',
        'metadata': {'name': STRUCTURE_NAME, 'namespace': namespace},
        'immutable': True,
        'data': {
            'resident_process.py': source('resident_process.py'),
            'resident_worker.py': source('resident_worker.py'),
        },
    }


def replace_service_overlay(template: dict) -> None:
    spec = template['spec']
    service = next(row for row in spec['containers'] if row['name'] == 'service')
    target_paths = {'/app/src/t01_phase1_real/' + path for path in SERVICE_FILES}
    service['volumeMounts'] = [
        row for row in service.get('volumeMounts', [])
        if row.get('name') != 'af3-service-code' and row.get('mountPath') not in target_paths
    ]
    spec['volumes'] = [row for row in spec.get('volumes', []) if row['name'] != 'af3-service-code']
    spec['volumes'].append({'name': 'af3-service-code', 'configMap': {'name': SERVICE_NAME}})
    for path in SERVICE_FILES:
        service['volumeMounts'].append({
            'name': 'af3-service-code',
            'mountPath': '/app/src/t01_phase1_real/' + path,
            'subPath': 'af3-' + path.replace('/', '--'),
            'readOnly': True,
        })


def replace_structure_overlay(template: dict) -> None:
    spec = template['spec']
    worker = next(row for row in spec['containers'] if row['name'] == 'worker-structure')
    paths = {
        '/opt/t01/src/t01_phase1_real/resident_process.py',
        '/opt/t01/src/t01_phase1_real/resident_worker.py',
    }
    worker['volumeMounts'] = [
        row for row in worker.get('volumeMounts', [])
        if row.get('name') != 'resident-compat-code' and row.get('mountPath') not in paths
    ]
    spec['volumes'] = [row for row in spec.get('volumes', []) if row['name'] != 'resident-compat-code']
    spec['volumes'].append({'name': 'resident-compat-code', 'configMap': {'name': STRUCTURE_NAME}})
    worker['volumeMounts'].extend([
        {'name': 'resident-compat-code',
         'mountPath': '/opt/t01/src/t01_phase1_real/resident_process.py',
         'subPath': 'resident_process.py', 'readOnly': True},
        {'name': 'resident-compat-code',
         'mountPath': '/opt/t01/src/t01_phase1_real/resident_worker.py',
         'subPath': 'resident_worker.py', 'readOnly': True},
    ])


def prepare():
    live = json.loads(subprocess.check_output(K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    if live['metadata']['name'] != 'antigen-design' or live['spec'].get('replicas') != 1:
        raise ValueError('Expected singleton antigen-design deployment')
    if live['spec'].get('strategy') != {'type': 'Recreate'}:
        raise ValueError('Expected Recreate deployment strategy')
    gpu = next((row for row in live['spec']['template']['spec']['containers']
                if row['name'] == 'worker-unified-gpu'), None)
    if not gpu or '@sha256:' not in gpu['image']:
        raise ValueError('Expected immutable unified GPU image')
    current_volume = next(row for row in live['spec']['template']['spec']['volumes']
                          if row['name'] == 'resident-config')
    current = json.loads(subprocess.check_output(
        K + ['get', 'configmap', current_volume['configMap']['name'], '-o', 'json']))

    unified.CONFIG_NAME = UNIFIED_CONFIG_NAME
    unified.CODE_NAME = UNIFIED_CODE_NAME
    documents = unified.manifests(current)
    template = unified.patch(live, gpu['image'])[-1]['value']
    replace_service_overlay(template)
    replace_structure_overlay(template)
    documents.extend([service_configmap(live['metadata']['namespace']),
                      structure_configmap(live['metadata']['namespace'])])
    patch = [
        {'op': 'test', 'path': '/metadata/resourceVersion',
         'value': live['metadata']['resourceVersion']},
        {'op': 'test', 'path': '/metadata/uid', 'value': live['metadata']['uid']},
        {'op': 'test', 'path': '/spec', 'value': live['spec']},
        {'op': 'replace', 'path': '/spec/template', 'value': template},
    ]
    OUTPUT.mkdir(parents=True, exist_ok=False)
    (OUTPUT / 'manifests.yaml').write_text(yaml.safe_dump_all(documents, sort_keys=False), encoding='utf-8')
    (OUTPUT / 'deployment.patch.json').write_text(json.dumps(patch, indent=2) + '\n', encoding='utf-8')
    (OUTPUT / 'before.json').write_text(json.dumps({
        'resourceVersion': live['metadata']['resourceVersion'],
        'uid': live['metadata']['uid'], 'image': gpu['image'],
        'source_config': current_volume['configMap']['name'],
    }, indent=2) + '\n', encoding='utf-8')
    subprocess.run(K + ['apply', '--dry-run=server', '-f', str(OUTPUT / 'manifests.yaml')], check=True)
    subprocess.run(K + ['patch', 'deployment', 'antigen-design', '--type=json',
                         '--patch-file', str(OUTPUT / 'deployment.patch.json'),
                         '--dry-run=server', '-o', 'name'], check=True)
    print('RESIDENT_COMPATIBILITY_DEPLOYMENT_PREPARED', OUTPUT)


if __name__ == '__main__':
    prepare()
