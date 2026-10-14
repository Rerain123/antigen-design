import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_gpu_resident import render, GPU


def test_resident_split_has_no_controller_permissions_or_idle_release():
    evidence = ROOT / 'reports/gpu-flexible-20261010'
    live = json.loads((evidence / 'deployment-refresh-r04.json').read_bytes())
    config = json.loads(json.loads((evidence / 'worker-config-before.json').read_bytes())['data']['unified-gpu.json'])
    before = copy.deepcopy(live)
    objects, patch, rollback, manifest = render(live, config, 'k8s-a100-01', ROOT / 'src')
    assert live == before and config['version'] == '0.1.0'
    assert all(o['kind'] not in {'ServiceAccount', 'Role', 'RoleBinding'} for o in objects)
    assert 'gpu-controller' not in json.dumps(objects)
    deployments = [o for o in objects if o['kind'] == 'Deployment']
    assert len(deployments) == 9
    assert all(o['spec']['replicas'] == 0 for o in deployments)
    gpu = next(o for o in deployments if o['metadata']['name'] == GPU)
    template = gpu['spec']['template']; pod = template['spec']; c = pod['containers'][0]
    assert c['command'][-1] == 't01_phase1_real.unified_gpu_worker'
    assert c['args'] == ['--config', '/etc/t01/unified-gpu.json']
    assert not any(e['name'] in {'T01_GPU_SESSION_ID', 'T01_GPU_POD_UID'} for e in c['env'])
    assert pod['automountServiceAccountToken'] is False and 'serviceAccountName' not in pod
    assert not any(k.startswith('nvidia.com/') for k in template['metadata']['annotations'])
    for kind in ('requests', 'limits'):
        assert {k: v for k, v in c['resources'][kind].items() if k.startswith('nvidia.com/')} == {
            'nvidia.com/gpu': '1', 'nvidia.com/gpucores': '100', 'nvidia.com/gpumem-percentage': '100'}
    policy = next(o for o in objects if o['kind'] == 'NetworkPolicy')
    assert all(template['metadata']['labels'][k] == v for k, v in policy['spec']['podSelector']['matchLabels'].items())
    assert policy['spec']['egress'] == []
    assert [c['name'] for c in patch[-1]['value']['spec']['containers']] == ['service']
    assert rollback[0]['value'] == patch[-1]['value']
    assert rollback[-1]['value'] == before['spec']['template']
    assert 't01_phase1_real/gpu_device.py' in manifest


def test_release_verifier_accepts_only_expected_defaulting():
    import pytest
    from verify_gpu_resident import check_template
    expected = dict(spec=dict(volumes=[dict(name='config', configMap=dict(name='registered'))],
                              containers=[dict(name='gpu', resources=dict(limits={'nvidia.com/gpu': '1'}))]))
    saved = copy.deepcopy(expected)
    observed = copy.deepcopy(expected)
    observed['spec']['volumes'][0]['configMap']['defaultMode'] = 420
    check_template(observed, expected)
    assert expected == saved
    for damage in ('config', 'permissions', 'resources', 'credentials'):
        changed = copy.deepcopy(observed)
        if damage == 'config': changed['spec']['volumes'][0]['configMap']['name'] = 'unregistered'
        elif damage == 'permissions': changed['spec']['volumes'][0]['configMap']['defaultMode'] = 511
        elif damage == 'resources': changed['spec']['containers'][0]['resources']['limits']['nvidia.com/gpu'] = '2'
        else: changed['spec']['automountServiceAccountToken'] = True
        with pytest.raises(AssertionError): check_template(changed, expected)

