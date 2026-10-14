import importlib.util
from pathlib import Path

import pytest


def module():
    path = Path(__file__).parents[1] / 'scripts/audit_unified_gpu_entry_guard.py'
    spec = importlib.util.spec_from_file_location('unified_gpu_entry_guard', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def fixtures():
    uuid = 'GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31'
    gpu = {'name': 'worker-unified-gpu', 'resources': {
        'requests': {'nvidia.com/gpu': '1', 'nvidia.com/gpumem-percentage': '100', 'nvidia.com/gpucores': '100'},
        'limits': {'nvidia.com/gpu': '1', 'nvidia.com/gpumem-percentage': '100', 'nvidia.com/gpucores': '100'},
    }}
    deployment = {
        'metadata': {'name': 'antigen-design', 'generation': 47},
        'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'}, 'template': {
            'metadata': {'labels': {'app': 'antigen-design'}, 'annotations': {
                'antigen-design/gpu-mode': 'unified-resident-single64',
                'nvidia.com/use-gputype': 'A100-SXM-64GB',
                'nvidia.com/use-gpuuuid': uuid,
            }},
            'spec': {'automountServiceAccountToken': False, 'containers': [
                {'name': 'service'}, gpu,
            ]},
        }},
        'status': {'observedGeneration': 47, 'readyReplicas': 1, 'updatedReplicas': 1},
    }
    deployments = {'items': [deployment]}
    pods = {'items': [{
        'metadata': {'name': 'antigen-design-abc'},
        'spec': {'nodeName': 'k8s-a100-02', 'containers': [gpu]},
        'status': {'phase': 'Running'},
    }]}
    resident = {'tools': {name: {'command': {'tool': name}} for name in module().GPU_TOOLS}}
    unified = {'uuid': uuid, 'spools': [
        {'root': '/var/lib/t01/resident/gpu'},
        {'root': '/var/lib/t01/resident/esmfold2'},
        {'root': '/var/lib/t01/resident/af3'},
    ]}
    return deployment, deployments, pods, resident, unified, {'phase': 'idle', 'pending': []}


def test_single_unified_holder_and_inactive_legacy_entries_pass():
    result = module().audit_documents(*fixtures())
    assert result['status'] == 'UNIFIED_GPU_OLD_ENTRY_GUARD_PASS'
    assert result['gpu_holder']['containers'] == ['worker-unified-gpu']
    assert result['registered_gpu_tools'] == ['af3', 'esm-if1', 'esmfold2', 'proteinmpnn', 'thermompnn']


@pytest.mark.parametrize('damage', ['second-holder', 'legacy-container', 'active-dispatcher', 'pending', 'token'])
def test_old_or_ambiguous_entry_cannot_pass_guard(damage):
    values = list(fixtures())
    deployment, deployments, pods, resident, unified, state = values
    if damage == 'second-holder':
        pods['items'].append(dict(pods['items'][0], metadata={'name': 'antigen-other'}))
    elif damage == 'legacy-container':
        deployment['spec']['template']['spec']['containers'].append({'name': 'worker-gpu'})
    elif damage == 'active-dispatcher':
        deployments['items'].append({
            'metadata': {'name': 'antigen-design-gpu-slot'},
            'spec': {'replicas': 1}, 'status': {'readyReplicas': 1},
        })
    elif damage == 'pending':
        state['pending'] = [{'tool': 'esmfold2'}]
    else:
        deployment['spec']['template']['spec']['automountServiceAccountToken'] = True
    with pytest.raises(ValueError):
        module().audit_documents(*values)
