"""Prepare a read-only AF3 source overlay for the existing service container."""
from __future__ import annotations
import argparse, copy, json
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIVE = ROOT / 'discovery/t01-phase1-real/af3-deployment-20260920/root-artifacts/af3-service-deployment-live.json'
DEFAULT_OUT = ROOT / '.tmp/af3-service-overlay-r05'
NAME = 'antigen-af3-service-code-r05'

FILES = [
    'resident_execution.py', 'resident_process.py',
    'development/contracts.py', 'development/registry.py', 'development/runtime.py',
    'development/supervisor.py',
    'development/workflow/policy.py', 'development/workflow/service.py',
    'development/af3/__init__.py', 'development/af3/native_worker.py',
    'development/af3/policy.py', 'development/af3/primitives.py',
    'development/af3/profile.json', 'development/af3/result.py',
    'development/af3/source.py', 'development/af3/standard.py',
    'development/af3/worker.py',
    'development/esmfold2/primitives.py', 'development/esmfold2/quality.py',
]

def key(path: str) -> str:
    return 'af3-' + path.replace('/', '--')

def main():
    global NAME
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', type=Path, default=DEFAULT_LIVE,
                        help='existing Deployment snapshot (default: archived read-only snapshot)')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUT,
                        help='generated overlay directory (default: .tmp/af3-service-overlay-r01)')
    parser.add_argument('--name', default=NAME, help='immutable ConfigMap name')
    args = parser.parse_args()
    NAME = args.name
    out = args.output if args.output.is_absolute() else ROOT / args.output
    if str(args.live) == '-':
        live = json.load(sys.stdin)
    else:
        live_path = args.live if args.live.is_absolute() else ROOT / args.live
        live = json.loads(live_path.read_text(encoding='utf-8-sig'))
    meta = live['metadata']; spec = live['spec']['template']['spec']
    service_i = next(i for i,c in enumerate(spec['containers']) if c['name']=='service')
    service = spec['containers'][service_i]
    if not service['image'].endswith('sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b'):
        raise ValueError('Unexpected service image')
    old_volumes = [i for i,v in enumerate(spec.get('volumes', [])) if v['name'].startswith('af3-service-code')]
    target_paths = {'/app/src/t01_phase1_real/' + rel for rel in FILES}
    old_mounts = [i for i,m in enumerate(service.get('volumeMounts', []))
                  if m['name'].startswith('af3-service-code') or m.get('mountPath') in target_paths]
    data = {}
    for rel in FILES:
        data[key(rel)] = (ROOT/'src/t01_phase1_real'/rel).read_text(encoding='utf-8')
    cm = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':NAME,'namespace':meta['namespace']},'immutable':True,'data':data}
    ops = [
        {'op':'test','path':'/metadata/resourceVersion','value':meta['resourceVersion']},
        {'op':'test','path':'/metadata/uid','value':meta['uid']},
        {'op':'test','path':f'/spec/template/spec/containers/{service_i}/image','value':service['image']},
    ]
    for i in sorted(old_mounts, reverse=True):
        ops.append({'op':'remove','path':f'/spec/template/spec/containers/{service_i}/volumeMounts/{i}'})
    for i in sorted(old_volumes, reverse=True):
        ops.append({'op':'remove','path':f'/spec/template/spec/volumes/{i}'})
    ops.append({'op':'add','path':'/spec/template/spec/volumes/-','value':{'name':'af3-service-code','configMap':{'name':NAME}}})
    for rel in FILES:
        ops.append({'op':'add','path':f'/spec/template/spec/containers/{service_i}/volumeMounts/-','value':{
            'name':'af3-service-code','mountPath':'/app/src/t01_phase1_real/'+rel,
            'subPath':key(rel),'readOnly':True}})
    out.mkdir(parents=True, exist_ok=True)
    (out/'configmap.yaml').write_text(yaml.safe_dump(cm,sort_keys=False),encoding='utf-8')
    (out/'deployment.patch.json').write_text(json.dumps(ops,indent=2)+'\n',encoding='utf-8')
    (out/'before.json').write_text(json.dumps({'resourceVersion':meta['resourceVersion'],'uid':meta['uid'],'image':service['image']},indent=2)+'\n',encoding='utf-8')
    print('AF3_SERVICE_OVERLAY_PREPARED', out)

if __name__ == '__main__': main()
