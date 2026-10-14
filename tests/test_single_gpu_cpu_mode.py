import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('cpu_mode', Path(__file__).parents[1] / 'scripts/prepare_single_gpu_cpu_mode.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    return {'metadata': {'name': 'antigen-design', 'uid': 'uid', 'resourceVersion': '42'},
            'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'}, 'template': {
                'metadata': {'annotations': {'nvidia.com/use-gputype': 'A100-SXM4-40GB', 'keep': 'yes'}},
                'spec': {'runtimeClassName': 'nvidia', 'containers': [
                    {'name': 'service', 'image': 'unchanged'},
                    {'name': 'worker-gpu', 'resources': {'limits': {'nvidia.com/gpu': 1}}},
                    {'name': 'worker-esmfold2', 'resources': {'limits': {'nvidia.com/gpu': 1}}}]}}}}


def test_cpu_mode_preserves_source_and_cpu_service():
    live = fixture()
    original = copy.deepcopy(live)
    patch = module.cpu_patch(live)
    assert live == original
    assert patch[0]['value'] == '42'
    target = patch[-1]['value']
    assert [c['name'] for c in target['spec']['containers']] == ['service']
    assert target['spec']['containers'][0]['image'] == 'unchanged'
    assert target['metadata']['annotations']['keep'] == 'yes'
    assert 'runtimeClassName' not in target['spec']


def test_unexpected_gpu_holder_rejected():
    live = fixture()
    live['spec']['template']['spec']['containers'].append(
        {'name': 'unexpected', 'resources': {'requests': {'nvidia.com/gpu': 1}}})
    with pytest.raises(ValueError, match='remaining GPU'):
        module.cpu_patch(live)


def test_overlapping_rollout_rejected():
    live = fixture()
    live['spec']['strategy'] = {'type': 'RollingUpdate'}
    with pytest.raises(ValueError, match='Recreate'):
        module.cpu_patch(live)


def test_esmfold_mode_restores_only_one_guarded_worker():
    import sys
    sys.path.insert(0,str(Path(__file__).parents[1] / 'scripts'))
    from prepare_single_gpu_esmfold_mode import make_patch
    original=fixture()
    for c in original['spec']['template']['spec']['containers'][1:]:
        c['resources']['requests']={'nvidia.com/gpu':1}
    cpu=copy.deepcopy(original)
    cpu['spec']['template']=module.cpu_patch(original)[-1]['value']
    target=make_patch(cpu,original)[-1]['value']
    holders=[c for c in target['spec']['containers'] if c.get('resources',{}).get('limits',{}).get('nvidia.com/gpu')]
    assert len(holders)==1
    assert holders[0]['name']=='worker-esmfold2'
    assert 'ESMFOLD2_SINGLE_GPU_GUARD_PASS' in holders[0]['command'][-1]
    assert target['metadata']['annotations']['nvidia.com/use-gputype']=='A100-SXM-64GB'
    with pytest.raises(ValueError,match='CPU maintenance'):
        make_patch(original,original)
