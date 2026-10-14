"""CPU-only synthetic tensor equivalence in the installed Torch interpreter."""
import json
import subprocess
import prepare_m1_p1_deploy as common
from version_bundle import encode,sha

CODE=r'''
import json,sys,torch
from torch import nn
p=json.load(sys.stdin);namespace={'__name__':'adapter_check'}
exec(compile(p['source'],'batch_adapter.py','exec'),namespace)
class Embedding(nn.Module):
    def __init__(self):super().__init__();self.calls=0
    def forward(self,pdb):self.calls+=1;return pdb+torch.randn_like(pdb)
class Model(nn.Module):
    def __init__(self):super().__init__();self.prot_mpnn=Embedding()
    def forward(self,pdb,mutations):
        features=self.prot_mpnn(pdb.clone())
        return [dict(ddG=features[m%len(pdb)].sum()*m) for m in mutations],None
whole=torch.arange(2100,dtype=torch.float32).reshape(700,3);mutations=list(range(700))
model=Model().eval();steps=[]
with torch.no_grad():
    torch.manual_seed(17);expected,_=Model().eval()(whole,mutations)
    torch.manual_seed(17);actual,_=namespace['predict'](model,whole,mutations,equal=torch.equal,progress=steps.append)
assert model.prot_mpnn.calls==1 and len(steps)==3
assert all(torch.equal(a['ddG'],b['ddG']) and a['ddG'].device.type=='cpu' for a,b in zip(actual,expected))
print(json.dumps(dict(status='PASS',type='SYNTHETIC_CPU_TENSOR_EQUIVALENCE',torch=torch.__version__,
    mutations=700,batches=3,embedding_calls=1,bitwise_equal=True,model_weights_loaded=False,gpu_used=False,
    new_jobs=0,source_sha256=p['sha256'])))
'''

if __name__=='__main__':
    path=common.ROOT/'src/t01_phase1_real/development/thermompnn/batch_adapter.py'
    # The pinned worker interpreter is read from its fixed configuration.
    query="from t01_phase1_real.unified_gpu_worker import configured; import json; _,s=configured('/etc/t01/unified-gpu.json'); print(json.dumps([dict(python=c.argv[0],env=dict(c.environment)) for cs in s.values() for c in cs.values() if c.tool=='thermompnn']))"
    raw=subprocess.check_output(common.K+['exec','deployment/antigen-design','-c','worker-unified-gpu',
        '--','/opt/t01/supervisor/bin/python3.11','-B','-c',query])
    config=json.loads(raw)[0];environment=dict(config['env'],CUDA_VISIBLE_DEVICES='')
    result=subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c','worker-unified-gpu',
        '--','env',*[k+'='+v for k,v in environment.items()],config['python'],'-B','-c',CODE],
        input=encode(dict(source=path.read_text(),sha256=sha(path.read_bytes()))),capture_output=True,timeout=60)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-3000:])
    value=json.loads(result.stdout)
    (common.ROOT/'reports/msa-scan-20260928/thermompnn-tensor-equivalence.json').write_bytes(encode(value))
    print(json.dumps(value))
