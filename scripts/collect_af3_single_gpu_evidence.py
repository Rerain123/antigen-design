"""Save redacted Kubernetes evidence and independent audit; never mutate cluster."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'discovery/t01-phase1-real/af3-target-20260920/single-gpu-r01'
K = ['C:/Program Files/Docker/Docker/resources/bin/kubectl.exe', '--kubeconfig',
     str(ROOT / '.tmp/himat.kubeconfig'), '-n','him-ws','--request-timeout=30s']
JOBS = ['antigen-af3-gpu64-probe-r01', 'antigen-af3-inference-r01', 'antigen-af3-inference-inspect-r01']


def call(*args):
    return subprocess.check_output(K + list(args))


def save(name, data):
    path = OUT / name
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    for name in JOBS:
        job = json.loads(call('get','job',name,'-o','json'))
        pods = json.loads(call('get','pods','-l','job-name='+name,'-o','json'))['items']
        rows = []
        for p in pods:
            rows.append({'name':p['metadata']['name'],'node':p['spec'].get('nodeName'),
                         'phase':p['status']['phase'], 'annotations':{k:v for k,v in p['metadata'].get('annotations',{}).items() if k.startswith(('hami.io/','nvidia.com/'))},
                         'containers':[{'name':c['name'],'image':c['image'],'resources':c.get('resources',{})} for c in p['spec']['containers']],
                         'container_statuses':p['status'].get('containerStatuses',[])})
        save(name+'.json',{'job_status':job['status'],'pods':rows})
        log = call('logs','job/'+name)
        save(name+'.log',log)
        if name.endswith('inference-inspect-r01'):
            line = next(v for v in log.decode().splitlines() if v.startswith('AF3_INFERENCE_AUDIT_PASS '))
            save('audit-summary.json',json.loads(line.split(' ',1)[1]))
    deployment=json.loads(call('get','deployment','antigen-design','-o','json'))
    pods=json.loads(call('get','pods','-o','json'))['items']
    holders=[p['metadata']['name'] for p in pods if p['metadata']['name'].startswith('antigen-') and p['status']['phase'] not in ('Succeeded','Failed') and any(c.get('resources',{}).get('limits',{}).get('nvidia.com/gpu') for c in p['spec']['containers'])]
    save('current-mode.json',{'generation':deployment['metadata']['generation'],
                            'ready_replicas':deployment['status'].get('readyReplicas',0),
                            'mode':deployment['spec']['template']['metadata']['annotations'].get('antigen-design/gpu-mode'),
                            'containers':[c['name'] for c in deployment['spec']['template']['spec']['containers']],
                            'active_project_gpu_pods':holders,'scientific_gate':'CLOSED','production_status':'NOT_DEPLOYED'})
    save('evidence-manifest.json',{'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(OUT.iterdir()) if p.is_file()]})
    print('AF3_EVIDENCE_SAVED',OUT)


if __name__ == '__main__':
    main()
