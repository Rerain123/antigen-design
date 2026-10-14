"""Python 2.7+ probe of the actual selected native environment, not a prediction."""
from __future__ import print_function
import json
import os
import platform
import socket
import subprocess
import sys

tool=sys.argv[1]
try:
    from importlib.metadata import distributions
    packages={d.metadata['Name'].lower().replace('_','-'):d.version for d in distributions()}
except ImportError:
    import pkg_resources
    packages={d.key:d.version for d in pkg_resources.working_set}
result=dict(tool=tool,python=platform.python_version(),executable=sys.executable,packages=packages,
            cwd=os.getcwd(),interfaces=socket.if_nameindex() if hasattr(socket,'if_nameindex') else None,
            native_entry_exists=os.path.isfile(os.environ['T01_PROBE_NATIVE_ENTRY']))
assert result['native_entry_exists']
assert not os.path.exists('/tmp/previous-execution'), 'Temporary files leaked from an earlier task'
with open('/tmp/previous-execution','w') as stream:stream.write(tool)
if os.environ.get('T01_NATIVE_PACKAGE'):
    assert os.path.isdir('/app')
    result['package']=os.path.realpath('/app')
if tool=='thermompnn':
    assert open('/app/local.yaml').read()=='environment-probe-only\n'
    assert os.path.realpath('/upstream')==os.environ['T01_NATIVE_PACKAGE']
if tool in ('proteinmpnn','esm-if1','thermompnn','deeptmhmm','bepipred'):
    import torch
    import numpy
    result.update(torch=torch.__version__,numpy=numpy.__version__,cuda_available=torch.cuda.is_available())
    if tool in ('proteinmpnn','esm-if1','thermompnn'):
        assert torch.cuda.is_available(), 'GPU unavailable; no CPU fallback'
        assert torch.cuda.device_count()==1, 'Expected one GPU allocation'
        result['gpu_name']=torch.cuda.get_device_name(0)
        result['gpu_test_value']=float(torch.tensor([2.,3.],device='cuda').sum().cpu())
        assert result['gpu_test_value']==5.
    if tool=='esm-if1':
        import esm, scipy, biotite, torch_geometric
        from esm.inverse_folding import util
    if tool=='thermompnn':
        import scipy,pytorch_lightning,omegaconf,torchmetrics,sklearn
    if tool in ('deeptmhmm','bepipred'): assert not torch.cuda.is_available()
if tool=='structure':
    import freesasa
    result['native_sasa']=freesasa.calcCoord([0.,0.,0.,4.,0.,0.],[1.7,1.7]).totalArea()
    assert result['native_sasa']>0
commands=[]
if tool=='blast':commands=[['/blast/bin/blastp','-version'],['/blast/bin/blastdbcmd','-version']]
if tool=='homology':commands=[['mmseqs','version'],['mafft','--version'],['blastp','-version']]
if tool=='netmhc':
    for path in ('/tools/src/netMHCpan-4.2/Linux_x86_64/bin/netMHCpan-4.2',
                 '/tools/src/netMHCIIpan-4.3/Linux_x86_64/bin/NetMHCIIpan-4.3'):
        commands.append([path,'-h'])
if tool=='foldx': commands=[['/app/foldx_20270131','--help']]
if tool=='aggrescan3d':
    import aggrescan,numpy,scipy
    commands=[['/opt/conda/bin/aggrescan','--help']]
result['commands']=[]
for argv in commands:
    process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    stdout,stderr=process.communicate()
    assert process.returncode==0,(argv,process.returncode,stderr.decode('utf-8','replace'))
    result['commands'].append(dict(argv=argv,exit_code=process.returncode,stdout=stdout.decode('utf-8','replace'),stderr=stderr.decode('utf-8','replace')))
try:
    socket.socket(socket.AF_INET)
except socket.error: result['internet_socket_denied']=True
else: raise AssertionError('Offline guard missing')
with open('/out/environment.json','w') as stream:json.dump(result,stream,sort_keys=True)
