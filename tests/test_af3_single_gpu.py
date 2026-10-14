import importlib.util
from pathlib import Path
import sys
import pytest

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from run_af3_inference import validate_gpu
from prepare_af3_inference import documents


@pytest.mark.parametrize('text', [
    'NVIDIA A100-SXM4-40GB, GPU-one, 40960',
    'NVIDIA A100-SXM-64GB, GPU-one, 32768',
    'NVIDIA A100-SXM-64GB, GPU-one, 65536\nNVIDIA A100-SXM-64GB, GPU-two, 65536',
    'NVIDIA A100-SXM-64GB, GPU-one, nan'])
def test_wrong_device_or_memory_rejected(text):
    with pytest.raises(ValueError):
        validate_gpu(text)


def test_single_64gb_accepted():
    assert validate_gpu('NVIDIA A100-SXM-64GB, GPU-one, 65536')['memory_MiB'] == 65536


def test_job_single_gpu_offline_readonly_weights():
    cm, policy, job = documents()
    pod = job['spec']['template']['spec']
    assert len(pod['containers']) == 1
    assert pod['containers'][0]['resources']['limits']['nvidia.com/gpu'] == 1
    assert job['spec']['template']['metadata']['annotations']['nvidia.com/use-gputype'] == 'A100-SXM-64GB'
    assert policy['spec']['policyTypes'] == ['Ingress', 'Egress']
    assert 'egress' not in policy['spec']
    assert pod['volumes'][-1]['persistentVolumeClaim']['readOnly'] is True
    assert job['spec']['backoffLimit'] == 0
