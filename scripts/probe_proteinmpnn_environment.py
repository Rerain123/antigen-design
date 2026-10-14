"""Read-only pinned image/GPU probe; stdout is the reproducible environment receipt."""
import json
import importlib.metadata
from pathlib import Path
import platform
import socket
import torch
import numpy

assert torch.cuda.is_available()
x=torch.ones((32,32),device='cuda')
y=x@x
torch.cuda.synchronize()
assert float(y.sum())==32768.0
print(json.dumps(dict(python=platform.python_version(),torch=torch.__version__,numpy=numpy.__version__,cuda=torch.version.cuda,
    gpu_name=torch.cuda.get_device_name(0),gpu_capability=list(torch.cuda.get_device_capability(0)),
    gpu_total_memory=torch.cuda.get_device_properties(0).total_memory,gpu_matmul_sum=float(y.sum()),
    network_interfaces=socket.if_nameindex(),pip_freeze=Path('/proteinmpnn-pip-freeze.txt').read_text(),
    dpkg=Path('/proteinmpnn-dpkg.txt').read_text(),pip_install=json.loads(Path('/proteinmpnn-pip-install.json').read_text()),
    distributions={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}),sort_keys=True))
