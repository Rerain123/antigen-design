import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / 'deploy/esmfold2-standard'
spec = importlib.util.spec_from_file_location('strict_loader', DEPLOY / 'esmc_strict_loader.py')
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)


def test_projection_order_is_qkv_and_gate_up():
    assert loader.source_keys('transformer.blocks.79.attn.layernorm_qkv.weight') == tuple(
        'esmc.layers.79.self_attn.' + p + '_proj.weight' for p in ('q', 'k', 'v'))
    assert loader.source_keys('transformer.blocks.0.ffn.fc1_weight') == (
        'esmc.layers.0.mlp.gate_proj.weight', 'esmc.layers.0.mlp.up_proj.weight')


@pytest.mark.parametrize('key', ['missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs'])
def test_loading_failures_are_fatal(key):
    with pytest.raises(ValueError, match='incomplete'):
        loader.require_clean_loading({key: ['failure']}, 'ESMFold2')


def test_full_registered_config_and_key_coverage():
    assets = ROOT / 'var/t01-phase1-real/structure-models/esmfold2-standard-20260916-r01/models/ESMC-6B'
    if not assets.exists():
        pytest.skip('local registered assets unavailable')
    config = json.loads((assets / 'config.json').read_bytes())
    loader.validate_config(config)
    config['num_hidden_layers'] = 79
    with pytest.raises(ValueError):
        loader.validate_config(config)
    names = list(loader.ROOT_KEYS) + [f'transformer.blocks.{i}.{k}' for i in range(80) for k in loader.BLOCK_KEYS]
    keys = [k for n in names for k in loader.source_keys(n)]
    index = json.loads((assets / 'model.safetensors.index.json').read_bytes())['weight_map']
    assert len(names) == 802 and len(set(keys)) == len(keys) == 1042
    assert set(index) == set(keys) | loader.HEAD_KEYS


def test_r03_bundle_preserves_assets_and_failure_evidence():
    policy, config, job = list(yaml.safe_load_all((DEPLOY / 'validation.r03.rancher.yaml').read_text()))
    assert config['data']['esmc_strict_loader.py'] == (DEPLOY / 'esmc_strict_loader.py').read_text()
    assert config['data']['run_structure.py'] == (DEPLOY / 'run_structure.r03.py').read_text()
    assert json.loads(config['data']['profile.json']) == json.loads((DEPLOY / 'profile.server.json').read_text())
    worker = job['spec']['template']['spec']['containers'][0]
    assert worker['args'][3] == '/runs/engineering-r03'
    assert job['metadata']['name'] == 'antigen-esmfold2-validation-r03'
    assert 'ttlSecondsAfterFinished' not in job['spec']
    assert job['spec']['backoffLimit'] == 0 and policy['spec']['egress'] == []
    assert 'require_clean_loading(loading_info' in config['data']['run_structure.py']
    assert 'model.load_esmc(' not in config['data']['run_structure.py']
    assert 'checkpoint-loading.json' in config['data']['run_structure.py']
    assert 'torch.linalg.svd' not in config['data']['esmc_strict_loader.py']
