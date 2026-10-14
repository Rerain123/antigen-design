"""Prepare independent CPU workers and one permanently reserved exclusive GPU.

Rendering only. Stage at zero replicas, retire the combined Pod, then activate
each worker once. No autoscaler, service account or Kubernetes API credentials.
"""
import argparse
import json
from pathlib import Path

from prepare_gpu_on_demand import render as demand_render, SLOT, CONTROLLER
from t01_phase1_real.gpu_on_demand import LABEL, POD_ENV, SESSION_ENV
from version_bundle import encode, sha

GPU = 'antigen-design-gpu-resident'


def render(live, worker_config, node, source_root):
    objects, patch, rollback, manifest = demand_render(
        live, worker_config, node, source_root, flexible_gpu=True, split_cpu_workers=True)
    result = []
    for obj in objects:
        name = obj['metadata']['name']
        if obj['kind'] in {'ServiceAccount', 'Role', 'RoleBinding'} or name.startswith(CONTROLLER):
            continue
        if obj['kind'] == 'Deployment' and name == SLOT:
            obj['metadata']['name'] = GPU
            spec = obj['spec']; template = spec['template']
            template['metadata']['labels'][LABEL] = GPU
            template['metadata']['labels']['app.kubernetes.io/component'] = 'gpu-resident'
            spec['selector']['matchLabels'] = dict(template['metadata']['labels'])
            template['metadata']['annotations']['antigen-design/gpu-mode'] = 'resident-exclusive'
            pod = template['spec']; pod.pop('serviceAccountName', None)
            pod['automountServiceAccountToken'] = False
            worker = pod['containers'][0]
            worker['command'] = ['/opt/t01/supervisor/bin/python3.11', '-u', '-B', '-m',
                                 't01_phase1_real.unified_gpu_worker']
            worker['args'] = ['--config', '/etc/t01/unified-gpu.json']
            worker['env'] = [e for e in worker['env'] if e['name'] not in {SESSION_ENV, POD_ENV}]
        elif obj['kind'] == 'NetworkPolicy' and name == SLOT + '-offline':
            obj['metadata']['name'] = GPU + '-offline'
            obj['spec']['podSelector']['matchLabels'][LABEL] = GPU
        if obj['kind'] == 'Deployment':
            obj['spec']['template']['metadata']['annotations']['antigen-design/gpu-mode'] = (
                'resident-exclusive' if obj['metadata']['name'] == GPU else 'cpu-independent')
        result.append(obj)
    patch[-1]['value']['metadata']['annotations']['antigen-design/gpu-mode'] = 'cpu-independent'
    # rollback's test shares the exact new API template with patch.
    return result, patch, rollback, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('live', 'worker-config', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--node', required=True)
    args = parser.parse_args()
    live = json.loads(args.live.read_bytes())
    worker = json.loads(json.loads(args.worker_config.read_bytes())['data']['unified-gpu.json'])
    objects, patch, rollback, manifest = render(live, worker, args.node, Path(__file__).resolve().parents[1] / 'src')
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in [('workloads.json', dict(apiVersion='v1', kind='List', items=objects)),
                        ('cpu.patch.json', patch), ('rollback.patch.json', rollback),
                        ('source-manifest.json', manifest)]:
        (args.output / name).write_bytes(encode(value))
    receipt = dict(status='PREPARED_NOT_DEPLOYED', source_sha256=sha(encode(manifest)),
        files=len(manifest), original_generation=live['metadata']['generation'], node=args.node,
        gpu_mode='resident-exclusive', gpu_deployment=GPU, gpu_target_replicas=1,
        cpu_worker_deployments=8, staged_worker_replicas=0, idle_gpu_release=False,
        controller_deployed=False, additional_rbac_required=False,
        gpu_selection='scheduler-assigned; no fixed UUID or memory capacity',
        storage_constraint='RWO shared volumes require one selected node',
        activation_requires=['fresh idle and live template validation', 'stage workloads at zero',
            'roll out API-only deployment and confirm old combined Pod gone',
            'scale eight CPU workers and GPU resident to one; verify shared queues and source hashes'],
        rollback_requires=['stop all independent workers and confirm Pods gone before restoring combined template'],
        cluster_mutations=0, scientific_jobs_submitted=0)
    (args.output / 'preparation.json').write_bytes(encode(receipt))
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
