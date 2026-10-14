"""Prepare a source-only repair and isolated, non-dispatching replay Pod."""
import copy
import json
import latency_maintenance as m
import prepare_version_unification as bundle
from deploy_terminal_sync import run, NAMES
from version_bundle import encode,sha

OUT=m.common.ROOT/'deploy/controller-latency/r03'
POD='antigen-controller-latency-candidate-r03'


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    live={n:run(['get','deployment',n,'-o','json']) for n in NAMES}
    assert live['antigen-design']['spec']['replicas']==0
    (m.EV/'deployments-paused.json').write_bytes(encode(live))
    templates={}
    for n,d in live.items():
        normalized=copy.deepcopy(d);normalized['spec']['replicas']=1
        cm,patch,rollback,manifest=bundle.render(normalized)
        templates[n]=patch[-1]['value']
        (OUT/(n+'.patch.json')).write_bytes(encode(patch))
        (OUT/(n+'.rollback.json')).write_bytes(encode(rollback))
    (OUT/'source-manifest.json').write_bytes(encode(manifest))
    (OUT/'templates.json').write_bytes(encode(templates))
    (OUT/'configmaps.json').write_bytes(encode(cm))
    for obj in cm.get('items',[cm]):
        run(['create','--dry-run=server','-f','-','-o','name'],obj)
        run(['create','-f','-','-o','name'],obj)
    pod=json.loads((m.EV/'maintenance-pod.json').read_bytes())
    pod['metadata']['name']=POD
    pod['metadata']['labels']={'app.kubernetes.io/name':POD,'app.kubernetes.io/component':'maintenance'}
    pod['spec']['initContainers']=templates['antigen-design']['spec']['initContainers']
    pod['spec']['volumes']=templates['antigen-design']['spec']['volumes']
    (m.EV/'candidate-pod.json').write_bytes(encode(pod))
    run(['create','-f','-','-o','name'],pod)
    print(json.dumps(dict(pod=POD,files=len(manifest),source_sha256=sha(encode(manifest)))))


if __name__=='__main__':prepare()
