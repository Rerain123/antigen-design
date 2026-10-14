import importlib.util
from pathlib import Path


def load_script():
    path = Path(__file__).parents[1] / 'scripts/run_unified_gpu_tool_regressions.py'
    spec = importlib.util.spec_from_file_location('unified_gpu_tool_regressions', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_payload_is_fixed_resumable_serial_three_tool_regression():
    module = load_script()
    payload = module.remote_payload()
    compile(payload, 'unified-gpu-regressions-remote', 'exec')
    assert payload.count("settle('proteinmpnn'") == 1
    assert payload.count("settle('esm-if1'") == 1
    assert payload.count("settle('thermompnn'") == 1
    assert payload.index("settle('proteinmpnn'") < payload.index("settle('esm-if1'") < payload.index("settle('thermompnn'")
    assert "gpu_name') == 'NVIDIA A100-SXM-64GB'" in payload
    assert 'UNIFIED_GPU_THREE_TOOL_SERIAL_REGRESSION_PASS' in payload
    assert module.SCOPE.endswith('-r01')
