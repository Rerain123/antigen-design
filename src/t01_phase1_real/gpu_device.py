"""User-authorized scheduler-selected hardware; no claim of model capacity."""
import math
import re

POLICY = 'scheduler-assigned-exclusive-v1'


def valid_identity(value):
    return (isinstance(value, dict) and set(value) == {'name', 'uuid', 'memory_mib'}
            and isinstance(value['name'], str) and 0 < len(value['name'].strip()) <= 256
            and isinstance(value['uuid'], str)
            and re.fullmatch(r'GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value['uuid']) is not None
            and type(value['memory_mib']) in (int, float)
            and math.isfinite(value['memory_mib']) and value['memory_mib'] > 0)


def valid_cuda_observation(value):
    """Record actual CUDA hardware, while callers still enforce software/assets."""
    capability = value.get('gpu_capability')
    return (value.get('gpu_allocation_policy') == POLICY and value.get('gpu_count') == 1
            and type(value.get('gpu_count')) is int
            and isinstance(value.get('gpu_name'), str) and 0 < len(value['gpu_name'].strip()) <= 256
            and isinstance(capability, (list, tuple)) and len(capability) == 2
            and all(type(v) is int for v in capability) and capability[0] > 0 and capability[1] >= 0)
