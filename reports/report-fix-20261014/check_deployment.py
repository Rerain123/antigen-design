import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import deploy_report_export as deploy

base = deploy.base
values = []
for name in base.NAMES:
    d = base.run(['get', 'deployment', name, '-o', 'json'])
    values.append(dict(name=name, generation=d['metadata']['generation'],
                       observed=d['status'].get('observedGeneration'),
                       replicas=d['spec']['replicas'], ready=d['status'].get('readyReplicas', 0),
                       updated=d['status'].get('updatedReplicas', 0),
                       annotations=d['spec']['template']['metadata'].get('annotations', {}),
                       images=[c['image'] for c in d['spec']['template']['spec']['containers']]))
pods = base.run(['get', 'pods', '-l', 'app.kubernetes.io/name=antigen-design', '-o', 'json'])['items']
out = dict(deployments=values, pods=[dict(name=p['metadata']['name'],
    created=p['metadata']['creationTimestamp'], phase=p['status']['phase'],
    terminating=bool(p['metadata'].get('deletionTimestamp')),
    containers=[dict(name=c['name'], ready=c['ready'], restarts=c['restartCount'], image_id=c.get('imageID'))
                for c in p['status'].get('containerStatuses', [])]) for p in pods])
base.save('current-cluster.json', out)
print(json.dumps(dict(api=values[0], ready=sum(v['ready'] == v['updated'] == v['replicas'] == 1 for v in values),
                      api_pods=[p for p in out['pods'] if any(c['name'] == 'service' for c in p['containers'])]), ensure_ascii=False))
