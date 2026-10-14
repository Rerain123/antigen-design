import importlib.util
import json
from pathlib import Path
import tempfile
import torch
from safetensors.torch import save_file
from transformers.models.esmc.configuration_esmc import ESMCConfig
from transformers.models.esmc.modeling_esmc import ESMCModel

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
loader=module('strict','/project/deploy/esmfold2-standard/esmc_strict_loader.py')
official=module('official','/project/.tmp/esmc-layout-repair/checkpoint_layout.py')
config=ESMCConfig(d_model=64,n_heads=1,n_layers=2)
reference=ESMCModel(config).eval()
raw=official.native_to_published({'esmc.'+k:v for k,v in reference.state_dict().items()})
for key in loader.HEAD_KEYS:raw[key]=torch.zeros(1)
with tempfile.TemporaryDirectory() as td:
 root=Path(td)
 def save(weights):
  save_file({k:v.contiguous() for k,v in weights.items()},str(root/'test.safetensors'))
  (root/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{k:'test.safetensors' for k in weights}}))
 save(raw)
 loaded,receipt=loader.load_encoder(root,config,'cpu',torch.float32)
 for key,value in reference.state_dict().items():assert torch.equal(value,loaded.state_dict()[key]),key
 tokens=torch.tensor([[0,5,6,7,8,2]])
 with torch.inference_mode():
  a=reference(input_ids=tokens).last_hidden_state
  b=loaded(input_ids=tokens).last_hidden_state
 assert torch.isfinite(b).all() and torch.equal(a,b)
 print('CPU_OFFICIAL_LAYOUT_ROUNDTRIP_AND_FORWARD_EXACT',receipt,flush=True)
 for failure in ['missing','unexpected','shape','nan']:
  damaged={k:v.clone() for k,v in raw.items()}
  if failure=='missing':damaged.pop('esmc.layers.0.self_attn.q_proj.weight')
  if failure=='unexpected':damaged['bogus']=torch.zeros(1)
  if failure=='shape':damaged['esmc.layers.0.self_attn.q_proj.weight']=torch.zeros(3,64)
  if failure=='nan':damaged['esmc.embed_tokens.weight'][0,0]=float('nan')
  save(damaged)
  try:loader.load_encoder(root,config,'cpu',torch.float32)
  except ValueError:print('STRICT_REJECTION_PASS',failure,flush=True)
  else:raise AssertionError(failure)
assets=Path('/assets/models/ESMC-6B')
loader.validate_config(json.loads((assets/'config.json').read_bytes()))
print('REAL_6B_HEADERS',loader.load_encoder(assets,ESMCConfig(),'cpu',torch.float32,validate_only=True),flush=True)
# CPU-only checkpoint audit: bypass import of GPU-only Triton decorators.
# This does not modify the delivered worker or claim a folding inference pass.
import sys
sys.modules['transformers.models.esmfold2.kernels'] = None
from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model
fold,info=ESMFold2Model.from_pretrained('/assets/models/ESMFold2',load_esmc=False,local_files_only=True,output_loading_info=True)
loader.require_clean_loading(info,'ESMFold2')
print('REAL_ESMFOLD2_WEIGHTS_STRICT_PASS', {k:len(v) for k,v in info.items() if isinstance(v,list)},flush=True)
