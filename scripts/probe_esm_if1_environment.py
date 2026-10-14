"""Actual offline local checkpoint loading and comparison with official score_sequence."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import socket
import numpy as np
import torch
import esm
import biotite
import scipy
import torch_geometric
from esm.inverse_folding.util import load_coords,get_sequence_loss,score_sequence

assert torch.cuda.is_available()
with torch.serialization.safe_globals([argparse.Namespace]):
    model,alphabet=esm.pretrained.load_model_and_alphabet_local('/app/weights/esm_if1_gvp4_t16_142M_UR50.pt')
model=model.eval().cuda();torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
coords,seq=load_coords('/reference.pdb','A')
with torch.no_grad():
    native=score_sequence(model,alphabet,coords,seq)
    loss,padding=get_sequence_loss(model,alphabet,coords,seq)
reduced=float(-np.sum(loss*~padding)/np.sum(~padding))
assert np.isfinite(native).all() and abs(native[0]-reduced)<1e-6
print(json.dumps(dict(python=platform.python_version(),torch=torch.__version__,numpy=np.__version__,cuda=torch.version.cuda,
    biotite=biotite.__version__,scipy=scipy.__version__,torch_geometric=torch_geometric.__version__,
    gpu_name=torch.cuda.get_device_name(0),gpu_capability=list(torch.cuda.get_device_capability(0)),
    network_interfaces=socket.if_nameindex(),official_scores=list(map(float,native)),loss_mean=reduced,
    model_parameter_count=sum(p.numel() for p in model.parameters()),reference_sequence=seq,
    reference_sha256=hashlib.sha256(Path('/reference.pdb').read_bytes()).hexdigest(),
    reference_kind='SYNTHETIC_GEOMETRY_API_NUMERICAL_EQUIVALENCE_ONLY',model_calls=2,
    pip_freeze=Path('/esm-if1-pip-freeze.txt').read_text(),dpkg=Path('/esm-if1-dpkg.txt').read_text(),
    pip_install=json.loads(Path('/esm-if1-pip-install.json').read_text()),
    base_pip_install=json.loads(Path('/proteinmpnn-pip-install.json').read_text()),
    distributions={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}),sort_keys=True))
