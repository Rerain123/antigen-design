"""Prepare one guarded ESMFold2 worker after AF3 jobs have released the card."""
import copy
import json
import subprocess
from prepare_single_gpu_cpu_mode import ROOT, K

OUT = ROOT / '.tmp/single-gpu-esmfold-r01'
GUARD = '''import os, subprocess
rows=[r.split(',') for r in subprocess.check_output(['nvidia-smi','--query-gpu=name,uuid,memory.total','--format=csv,noheader,nounits'],text=True).strip().splitlines()]
if len(rows)!=1 or rows[0][0].strip()!='NVIDIA A100-SXM-64GB' or rows[0][1].strip()!='GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31' or float(rows[0][2])<60000:
    raise RuntimeError('Single approved 64GB GPU identity mismatch: '+repr(rows))
print('ESMFOLD2_SINGLE_GPU_GUARD_PASS',rows,flush=True)
os.execvp('python',['python','-u','-B','-m','t01_phase1_real.resident_worker','--root','/var/lib/t01/resident/esmfold2','--config','/etc/t01/esmfold2.worker.json'])
'''


def make_patch(live, original):
    if live['spec']['template']['metadata']['annotations'].get('antigen-design/gpu-mode') != 'cpu-maintenance':
        raise ValueError('Expected CPU maintenance mode')
    target = copy.deepcopy(live['spec']['template'])
    if any(c.get('resources',{}).get('limits',{}).get('nvidia.com/gpu') for c in target['spec']['containers']):
        raise ValueError('Existing GPU holder')
    worker = copy.deepcopy(next(c for c in original['spec']['template']['spec']['containers'] if c['name']=='worker-esmfold2'))
    for kind in ('requests','limits'):
        worker['resources'][kind] = {k:v for k,v in worker['resources'][kind].items() if not k.startswith('nvidia.com/')}
        worker['resources'][kind].update({'nvidia.com/gpu':'1','nvidia.com/gpumem-percentage':'100','nvidia.com/gpucores':'100'})
    worker['command'] = ['python','-u','-B','-c',GUARD]
    worker.pop('args',None)
    target['spec']['containers'].append(worker)
    target['spec']['runtimeClassName']='nvidia'
    target['spec']['schedulerName']='hami-scheduler'
    target['metadata']['annotations'].update({'antigen-design/gpu-mode':'esmfold2-single64',
        'nvidia.com/use-gputype':'A100-SXM-64GB',
        'nvidia.com/use-gpuuuid':'GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31'})
    return [{'op':'test','path':'/metadata/resourceVersion','value':live['metadata']['resourceVersion']},
            {'op':'test','path':'/metadata/uid','value':live['metadata']['uid']},
            {'op':'test','path':'/spec','value':live['spec']},
            {'op':'replace','path':'/spec/template','value':target}]


if __name__ == '__main__':
    live=json.loads(subprocess.check_output(K+['get','deployment','antigen-design','-o','json']))
    original=json.loads((ROOT/'.tmp/single-gpu-cpu-r01/before.json').read_bytes())
    patch=make_patch(live,original)
    OUT.mkdir(exist_ok=False)
    path=OUT/'patch.json'
    path.write_text(json.dumps(patch,indent=2),encoding='utf-8')
    subprocess.run(K+['patch','deployment','antigen-design','--type=json','--patch-file',str(path),'--dry-run=server','-o','name'],check=True)
    print('ESMFOLD_SINGLE_GPU_PATCH_PREPARED',path)
