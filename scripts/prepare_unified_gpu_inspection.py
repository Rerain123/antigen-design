"""Render a zero-GPU, offline import check for the unified runtime image."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
NAME = 'antigen-unified-gpu-inspect-r06'
IMAGES = {
    'gpu': 'harbor-core.base.svc.cluster.local/qcyz/antigen-design-resident-gpu@sha256:2079483853695089e1924d839221aa016481bc9e822b6e436dae8277a428ab8a',
    'esmfold2': 'harbor-core.base.svc.cluster.local/qcyz/antigen-esmfold2@sha256:372545ebe3469a3d32269c27033d19624d713d75ca162dbe6fff5dafed44f77f',
    'af3': 'harbor-core.base.svc.cluster.local/qcyz/antigen-af3@sha256:35db7c1feb3368a7c72b0d1f60b295ed1473b562b61526db265fc0c446fd4373',
}

SCRIPT = r'''set -eu
test ! -e /dev/nvidia0
echo UNIFIED_ENV_IMPORT_START
env -i HOME=/tmp TMPDIR=/tmp PATH=/opt/t01/supervisor/bin:/usr/bin:/bin PYTHONHOME=/opt/t01/supervisor LD_LIBRARY_PATH=/opt/t01/supervisor/lib PYTHONPATH=/opt/t01/src \
  /opt/t01/supervisor/bin/python3.11 -B -c 'import ssl,sqlite3,ctypes;import t01_phase1_real.resident_worker;print("supervisor",t01_phase1_real.resident_worker.__file__)'
env -i HOME=/tmp TMPDIR=/tmp PATH=/opt/t01/env/proteinmpnn/bin:/usr/bin:/bin PYTHONHOME=/opt/t01/env/proteinmpnn LD_LIBRARY_PATH=/opt/t01/env/proteinmpnn/lib CUDA_VISIBLE_DEVICES= \
  /opt/t01/env/proteinmpnn/bin/python -B -c 'import numpy,torch;print("proteinmpnn",torch.__version__,numpy.__version__,torch.cuda.is_available())'
find /opt/t01/env/esm-if1 -maxdepth 10 -type d \( -name site-packages -o -name 'esm*' \) -print
env -i HOME=/tmp TMPDIR=/tmp PATH=/opt/t01/env/esm-if1/bin:/usr/bin:/bin PYTHONHOME=/opt/t01/env/esm-if1 LD_LIBRARY_PATH=/opt/t01/env/esm-if1/lib CUDA_VISIBLE_DEVICES= \
  /opt/t01/env/proteinmpnn/bin/python -B -c 'import sys,numpy,torch,biotite,scipy,torch_geometric;print("esm-if1-base",sys.executable,torch.__version__,numpy.__version__,torch.cuda.is_available(),"asset-package-deferred")'
env -i HOME=/tmp TMPDIR=/tmp PATH=/opt/t01/env/thermompnn/bin:/usr/bin:/bin PYTHONHOME=/opt/t01/env/thermompnn LD_LIBRARY_PATH=/opt/t01/env/thermompnn/lib CUDA_VISIBLE_DEVICES= WANDB_MODE=disabled \
  /opt/t01/env/proteinmpnn/bin/python -B -c 'import Bio,numpy,omegaconf,pandas,pytorch_lightning,sklearn,scipy,torch,torchmetrics;print("thermompnn",torch.__version__,numpy.__version__,torch.cuda.is_available())'
env -i HOME=/tmp TMPDIR=/tmp PATH=/alphafold3_venv/bin:/usr/bin:/bin CUDA_VISIBLE_DEVICES= JAX_PLATFORMS=cpu \
  /alphafold3_venv/bin/python -B -c 'import jax;from alphafold3.common import folding_input;from alphafold3.model import model;print("af3",jax.__version__,jax.devices())'
echo UNIFIED_ENV_IMPORT_PASS
'''


def documents(image):
    if not re.fullmatch(r'harbor-core\.base\.svc\.cluster\.local/qcyz/antigen-unified-gpu@sha256:[a-f0-9]{64}', image):
        raise ValueError('Immutable unified image digest required')
    labels = {'app': NAME}
    config = {'apiVersion': 'v1', 'kind': 'ConfigMap',
              'metadata': {'name': NAME, 'namespace': 'him-ws'},
              'immutable': True, 'data': {'inspect.sh': SCRIPT}}
    policy = {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
              'metadata': {'name': NAME, 'namespace': 'him-ws'},
              'spec': {'podSelector': {'matchLabels': labels},
                       'policyTypes': ['Ingress', 'Egress'], 'ingress': [], 'egress': []}}
    mounts = [
        {'name': 'slot', 'mountPath': '/run/t01-slot'},
        {'name': 'inspection', 'mountPath': '/inspection', 'readOnly': True},
    ]
    pod = {
        'restartPolicy': 'Never', 'automountServiceAccountToken': False,
        'imagePullSecrets': [{'name': 'harbor'}],
        'securityContext': {'runAsNonRoot': True, 'runAsUser': 10001,
                            'runAsGroup': 10001, 'fsGroup': 10001},
        'initContainers': [{
            'name': 'slot-init', 'image': image,
            'command': ['/bin/sh', '-ec',
                        'mkdir -p /run/t01-slot/tmp && ln -s /opt/t01/af3-app /run/t01-slot/package'],
            'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'},
                          'limits': {'cpu': '1', 'memory': '128Mi'}},
            'securityContext': {'allowPrivilegeEscalation': False,
                                'capabilities': {'drop': ['ALL']}},
            'volumeMounts': [{'name': 'slot', 'mountPath': '/run/t01-slot'}],
        }],
        'containers': [{
            'name': 'inspect', 'image': image,
            'command': ['/bin/sh', '/inspection/inspect.sh'],
            'resources': {'requests': {'cpu': '1', 'memory': '4Gi'},
                          'limits': {'cpu': '4', 'memory': '16Gi'}},
            'securityContext': {'allowPrivilegeEscalation': False,
                                'readOnlyRootFilesystem': True,
                                'capabilities': {'drop': ['ALL']}},
            'volumeMounts': mounts,
        }],
        'volumes': [
            {'name': 'slot', 'emptyDir': {'sizeLimit': '2Gi'}},
            {'name': 'inspection', 'configMap': {'name': NAME, 'defaultMode': 365}},
        ],
    }
    job = {'apiVersion': 'batch/v1', 'kind': 'Job',
           'metadata': {'name': NAME, 'namespace': 'him-ws'},
           'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 1800,
                    'template': {'metadata': {'labels': labels}, 'spec': pod}}}
    return [config, policy, job]


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--image', required=True)
    args = parser.parse_args()
    output = ROOT / 'deploy/single-gpu/environment-inspect.r06.yaml'
    output.write_text(yaml.safe_dump_all(documents(args.image), sort_keys=False), encoding='utf-8')
    print(output)


if __name__ == '__main__': main()
