"""Strict local loader for published ESMC weights into the pinned Biohub model.

Layout reference (exact concatenation; no trained-value changes):
Biohub/esm@43b4548b86762edfa747b07d5f440aad3c33acee
esm/models/esmc/checkpoint_layout.py, published_to_native.
All original assets remain read-only. No remote code or network access.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import time

ROOT_KEYS = {'embed.weight': 'esmc.embed_tokens.weight',
             'transformer.norm.weight': 'esmc.norm.weight'}
BLOCK_KEYS = {
    'attn.layernorm_qkv.layer_norm_weight': ('input_layernorm.weight',),
    'attn.layernorm_qkv.layer_norm_bias': ('input_layernorm.bias',),
    'attn.q_ln.weight': ('self_attn.q_norm.weight',),
    'attn.k_ln.weight': ('self_attn.k_norm.weight',),
    'attn.out_proj.weight': ('self_attn.o_proj.weight',),
    'ffn.layer_norm_weight': ('post_attention_layernorm.weight',),
    'ffn.layer_norm_bias': ('post_attention_layernorm.bias',),
    'ffn.fc2_weight': ('mlp.down_proj.weight',),
    'attn.layernorm_qkv.weight': ('self_attn.q_proj.weight', 'self_attn.k_proj.weight', 'self_attn.v_proj.weight'),
    'ffn.fc1_weight': ('mlp.gate_proj.weight', 'mlp.up_proj.weight'),
}
HEAD_KEYS = {'lm_head.' + key for key in ('dense.weight', 'dense.bias',
             'layer_norm.weight', 'layer_norm.bias', 'decoder.weight', 'decoder.bias')}


def source_keys(name):
    if name in ROOT_KEYS:
        return (ROOT_KEYS[name],)
    parts = name.split('.')
    if len(parts) < 4 or parts[:2] != ['transformer', 'blocks'] or not parts[2].isdigit():
        raise ValueError('Unknown native ESMC key: ' + name)
    leaves = BLOCK_KEYS['.'.join(parts[3:])]
    return tuple(f'esmc.layers.{parts[2]}.{leaf}' for leaf in leaves)


def validate_config(raw):
    expected = {'model_type': 'esmc', 'hidden_size': 2560, 'num_attention_heads': 40,
                'num_key_value_heads': 40, 'num_hidden_layers': 80, 'head_dim': 64,
                'intermediate_size': 6912, 'vocab_size': 64, 'attention_bias': False,
                'mlp_bias': False, 'hidden_act': 'silu', 'attention_dropout': 0.0,
                'pad_token_id': 1, 'mask_token_id': 32}
    if any(raw.get(k) != v for k, v in expected.items()):
        raise ValueError('Unsupported published ESMC configuration')
    if raw.get('rope_parameters') != {'rope_theta': 10000.0, 'rope_type': 'default'}:
        raise ValueError('Unsupported ESMC rotary configuration')


def load_encoder(root, config, device, dtype, *, validate_only=False):
    """Materialize every native parameter from verified local checkpoint tensors."""
    import torch
    from accelerate import init_empty_weights
    from accelerate.utils import set_module_tensor_to_device
    from safetensors import safe_open
    from transformers.models.esmc.modeling_esmc import ESMCModel

    index = json.loads((root / 'model.safetensors.index.json').read_bytes())['weight_map']
    with init_empty_weights(include_buffers=False):
        encoder = ESMCModel(config)
    expected = dict(encoder.named_parameters())
    plan = {name: source_keys(name) for name in expected}
    consumed = [key for keys in plan.values() for key in keys]
    if len(consumed) != len(set(consumed)):
        raise ValueError('Duplicate checkpoint tensor mapping')
    if set(index) != set(consumed) | HEAD_KEYS:
        raise ValueError('ESMC checkpoint has missing or unexpected parameter keys')

    with ExitStack() as stack:
        handles = {}
        for filename in sorted(set(index.values())):
            if Path(filename).name != filename or '/' in filename or '\\' in filename:
                raise ValueError('Unsafe ESMC shard name')
            handles[filename] = stack.enter_context(safe_open(str(root / filename), framework='pt', device='cpu'))
        actual = {}
        for filename, handle in handles.items():
            for key in handle.keys():
                if key in actual:
                    raise ValueError('Duplicate key in ESMC shard files')
                actual[key] = filename
        if actual != index:
            raise ValueError('ESMC shard headers differ from index')
        # Check the entire mapping before allocating any real model parameter.
        for name, keys in plan.items():
            shapes = [handles[index[k]].get_slice(k).get_shape() for k in keys]
            shape = [sum(s[0] for s in shapes), *shapes[0][1:]]
            if any(s[1:] != shapes[0][1:] for s in shapes) or tuple(shape) != tuple(expected[name].shape):
                raise ValueError('ESMC tensor shape mismatch: ' + name)
        print('ESMC_KEY_MAPPING_VERIFIED', len(expected), len(consumed), flush=True)
        if validate_only:
            return {'native_parameters': len(expected), 'source_encoder_tensors': len(consumed),
                    'checkpoint_tensors': len(index), 'tensor_values_loaded': False}
        last = time.monotonic()
        for count, (name, keys) in enumerate(plan.items(), 1):
            tensors = [handles[index[k]].get_tensor(k) for k in keys]
            for tensor in tensors:
                if tensor.dtype != torch.float32 or not torch.isfinite(tensor).all().item():
                    raise ValueError('Non-finite or unexpected dtype in ESMC parameter: ' + name)
            value = tensors[0] if len(tensors) == 1 else torch.cat(tensors, dim=0)
            set_module_tensor_to_device(encoder, name, device, value=value, dtype=dtype)
            del value, tensors
            if time.monotonic() - last >= 30:
                print('ESMC_PARAMETER_LOAD_PROGRESS', count, len(plan), flush=True)
                last = time.monotonic()
    if any(p.is_meta for p in encoder.parameters()):
        raise ValueError('ESMC parameters remain uninitialized')
    encoder.to(device=device, dtype=dtype).eval()
    for parameter in encoder.parameters():
        parameter.requires_grad_(False)
    receipt = {'native_parameters_loaded': len(expected), 'source_encoder_tensors': len(consumed),
               'omitted_masked_lm_head_keys': sorted(HEAD_KEYS), 'missing_keys': [],
               'unexpected_keys': [], 'layout': 'published_split_to_native_fused',
               'source_layout_reference': 'Biohub/esm@43b4548b86762edfa747b07d5f440aad3c33acee',
               'precision': str(dtype)}
    print('ESMC_PARAMETERS_STRICTLY_LOADED', len(expected), 'missing=0 unexpected=0', flush=True)
    return encoder, receipt


def load_esmc_strict(model, root):
    import torch
    from transformers.models.esmc.configuration_esmc import ESMCConfig
    raw = json.loads((root / 'config.json').read_bytes())
    validate_config(raw)
    config = ESMCConfig(d_model=raw['hidden_size'], n_heads=raw['num_attention_heads'],
                        n_layers=raw['num_hidden_layers'], vocab_size=raw['vocab_size'],
                        pad_token_id=raw['pad_token_id'], mask_token_id=raw['mask_token_id'])
    model._esmc, receipt = load_encoder(root, config, model.device, torch.bfloat16)
    model._esmc_fp8 = False
    return receipt


def require_clean_loading(info, label):
    failures = {key: info.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs') if info.get(key)}
    if failures:
        raise ValueError(label + ' checkpoint loading incomplete: ' + json.dumps(failures))
