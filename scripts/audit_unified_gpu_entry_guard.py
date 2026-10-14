"""Audit the live single-A100 entry guard without mutating cluster resources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
K = [
    'C:/Program Files/Docker/Docker/resources/bin/kubectl.exe',
    '--kubeconfig', str(ROOT / '.tmp/himat.kubeconfig'),
    '--request-timeout=90s', '-n', 'him-ws',
]
OUT = ROOT / 'discovery/t01-phase1-real/unified-gpu-worker-20260920/entry-guard-r01/latest.json'
GPU_TOOLS = {'af3', 'esm-if1', 'esmfold2', 'proteinmpnn', 'thermompnn'}
LEGACY_DEPLOYMENTS = {'antigen-design-gpu-slot', 'antigen-gpu-dispatcher'}


def gpu_claim(container):
    resources = container.get('resources', {})
    return any(
        str(resources.get(kind, {}).get('nvidia.com/gpu', '0')) not in ('0', 'None')
        for kind in ('requests', 'limits')
    )


def audit_documents(deployment, deployments, pods, resident, unified, worker_state):
    spec = deployment['spec']
    status = deployment.get('status', {})
    if spec.get('replicas') != 1 or spec.get('strategy') != {'type': 'Recreate'}:
        raise ValueError('Unified deployment must remain singleton Recreate')
    if status.get('observedGeneration') != deployment['metadata']['generation'] \
            or status.get('readyReplicas') != 1 or status.get('updatedReplicas') != 1:
        raise ValueError('Unified deployment is not fully observed and ready')
    template = spec['template']
    pod_spec = template['spec']
    if pod_spec.get('automountServiceAccountToken') is not False:
        raise ValueError('Unified deployment must not carry a Kubernetes API token')
    containers = pod_spec['containers']
    names = {row['name'] for row in containers}
    if {'worker-gpu', 'worker-esmfold2'} & names:
        raise ValueError('Legacy parallel GPU container is present')
    holders = [row for row in containers if gpu_claim(row)]
    if [row['name'] for row in holders] != ['worker-unified-gpu']:
        raise ValueError('Exactly the unified Worker must request a GPU')
    holder = holders[0]
    for kind in ('requests', 'limits'):
        values = holder['resources'][kind]
        if str(values.get('nvidia.com/gpu')) != '1' \
                or str(values.get('nvidia.com/gpumem-percentage')) != '100' \
                or str(values.get('nvidia.com/gpucores')) != '100':
            raise ValueError('Unified Worker must request one whole GPU')
    annotations = template['metadata'].get('annotations', {})
    if annotations.get('antigen-design/gpu-mode') != 'unified-resident-single64' \
            or annotations.get('nvidia.com/use-gputype') != 'A100-SXM-64GB' \
            or annotations.get('nvidia.com/use-gpuuuid') != unified['uuid']:
        raise ValueError('Pinned 64GB device annotations differ')

    legacy = {}
    for item in deployments['items']:
        name = item['metadata']['name']
        if name in LEGACY_DEPLOYMENTS:
            ready = item.get('status', {}).get('readyReplicas', 0) or 0
            replicas = item['spec'].get('replicas', 1)
            legacy[name] = {'replicas': replicas, 'ready_replicas': ready}
            if replicas != 0 or ready != 0:
                raise ValueError('Legacy dynamic GPU deployment is active: ' + name)

    active_gpu_pods = []
    for pod in pods['items']:
        if pod.get('status', {}).get('phase') in ('Succeeded', 'Failed'):
            continue
        claims = [row['name'] for row in pod['spec'].get('initContainers', []) + pod['spec'].get('containers', [])
                  if gpu_claim(row)]
        if claims and pod['metadata']['name'].startswith('antigen-'):
            active_gpu_pods.append({
                'name': pod['metadata']['name'],
                'node': pod['spec'].get('nodeName'),
                'containers': claims,
                'phase': pod.get('status', {}).get('phase'),
            })
    if len(active_gpu_pods) != 1 \
            or active_gpu_pods[0]['containers'] != ['worker-unified-gpu']:
        raise ValueError('Active project GPU Pod set is not the one unified holder')

    registered = {
        name for name, row in resident['tools'].items()
        if isinstance(row, dict) and isinstance(row.get('command'), dict)
        and row['command'].get('tool') in GPU_TOOLS
    }
    if registered != GPU_TOOLS:
        raise ValueError('Resident service GPU command registry differs')
    spool_roots = {row['root'] for row in unified['spools']}
    if spool_roots != {
        '/var/lib/t01/resident/gpu',
        '/var/lib/t01/resident/esmfold2',
        '/var/lib/t01/resident/af3',
    }:
        raise ValueError('Unified spool registry differs')
    if worker_state.get('phase') != 'idle' or worker_state.get('pending'):
        raise ValueError('Unified worker is not idle or has pending work')

    return {
        'status': 'UNIFIED_GPU_OLD_ENTRY_GUARD_PASS',
        'deployment_generation': deployment['metadata']['generation'],
        'gpu_holder': active_gpu_pods[0],
        'gpu_uuid': unified['uuid'],
        'gpu_type': 'NVIDIA A100-SXM-64GB',
        'registered_gpu_tools': sorted(registered),
        'spool_roots': sorted(spool_roots),
        'worker_state': worker_state,
        'legacy_deployments': legacy,
        'service_account_token_mounted': False,
        'scientific_gate': 'CLOSED',
        'usable_for_pipeline': False,
        'production_status': 'NOT_DEPLOYED',
    }


def kubectl_json(*args):
    return json.loads(subprocess.check_output(K + list(args)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        print('UNIFIED_GPU_ENTRY_GUARD_AUDIT_CHECK_PASS')
        return
    deployment = kubectl_json('get', 'deployment', 'antigen-design', '-o', 'json')
    deployments = kubectl_json('get', 'deployments', '-o', 'json')
    pods = kubectl_json('get', 'pods', '-o', 'json')
    volume = next(row for row in deployment['spec']['template']['spec']['volumes']
                  if row['name'] == 'resident-config')
    configmap = kubectl_json('get', 'configmap', volume['configMap']['name'], '-o', 'json')
    resident = json.loads(configmap['data']['resident.json'])
    unified = json.loads(configmap['data']['unified-gpu.json'])
    probe = (
        "import json;from pathlib import Path;"
        "from t01_phase1_real.unified_gpu_worker import configured,pending,read_json;"
        "config,spools=configured(Path('/etc/t01/unified-gpu.json'));"
        "state=read_json(Path(config['state_root'])/'state.json')[0];"
        "print(json.dumps(dict(state,pending=pending(spools))))"
    )
    raw = subprocess.check_output(K + [
        'exec', 'deployment/antigen-design', '-c', 'worker-unified-gpu', '--',
        '/opt/t01/supervisor/bin/python3.11', '-B', '-c', probe,
    ])
    worker_state = json.loads(raw)
    result = audit_documents(deployment, deployments, pods, resident, unified, worker_state)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(result['status'])
    print('SAVED', OUT)


if __name__ == '__main__':
    main()
