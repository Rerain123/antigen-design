"""Render a stopped on-demand GPU topology from an observed Deployment.

Local preparation only: no Kubernetes calls, resource creation or task submission.
The dedicated GPU controller remains at zero until an operator has verified
RBAC, the CPU-only rollout and the absence of the former GPU holder.
"""
import argparse
import copy
import json
from pathlib import Path
import re

from prepare_version_unification import render as source_render
from version_bundle import encode, sha
from t01_phase1_real.gpu_on_demand import LABEL, POD_ENV, SESSION_ENV, normalized_template

SLOT = 'antigen-design-gpu-demand'
CONTROLLER = 'antigen-design-gpu-controller'


def pin_node(spec, node):
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', node):
        raise ValueError('An observed approved GPU node name is required')
    if spec.get('nodeName') or spec.get('affinity'):
        raise ValueError('Existing node affinity requires explicit migration review')
    spec['affinity'] = {'nodeAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': {
        'nodeSelectorTerms': [{'matchFields': [{'key': 'metadata.name', 'operator': 'In', 'values': [node]}]}]}}}


def prune_volumes(spec):
    used = {m['name'] for c in spec['containers'] + spec.get('initContainers', []) for m in c.get('volumeMounts', [])}
    spec['volumes'] = [v for v in spec['volumes'] if v['name'] in used]
    if {v['name'] for v in spec['volumes']} != used:
        raise ValueError('A container volume is missing')


def cpu_visibility(container):
    container['env'] = [e for e in container.get('env', []) if e['name'] != 'NVIDIA_VISIBLE_DEVICES']
    container['env'].append(dict(name='NVIDIA_VISIBLE_DEVICES', value='void'))


def deployment(name, namespace, template):
    return dict(apiVersion='apps/v1', kind='Deployment', metadata=dict(name=name, namespace=namespace),
                spec=dict(replicas=0, strategy=dict(type='Recreate'),
                          selector=dict(matchLabels=template['metadata']['labels']), template=template))


def render(live, worker_config, node, source_root, *, flexible_gpu=False, split_cpu_workers=False):
    if live['metadata']['name'] != 'antigen-design' or live['metadata']['namespace'] != 'him-ws':
        raise ValueError('Expected existing project deployment')
    namespace = live['metadata']['namespace']
    package, source_patch, _, manifest = source_render(live, source_root)
    template = next(p['value'] for p in source_patch if p['op'] == 'replace' and p['path'] == '/spec/template')
    original = copy.deepcopy(template)
    original_spec = original['spec']
    gpu = [c for c in original_spec['containers'] if c['name'] == 'worker-unified-gpu']
    if len(gpu) != 1 or len(original_spec['containers']) != 10:
        raise ValueError('Expected the current ten-container deployment')
    gpu = copy.deepcopy(gpu[0])
    for kind in ('requests', 'limits'):
        resources = gpu['resources'][kind]
        if any(str(resources.get(k)) != v for k, v in {
            'nvidia.com/gpu': '1', 'nvidia.com/gpucores': '100', 'nvidia.com/gpumem-percentage': '100'}.items()):
            raise ValueError('Expected the existing full-card GPU allocation')
        if 'nvidia.com/gpumem' in resources:
            raise ValueError('Absolute GPU memory cap conflicts with full-card allocation')
    if not flexible_gpu and original['metadata']['annotations'].get('nvidia.com/use-gpuuuid') != worker_config['uuid']:
        raise ValueError('Worker and deployment GPU identities differ')
    if set(row['root'].rsplit('/', 1)[-1] for row in worker_config['spools']) != {'gpu', 'esmfold2', 'af3'}:
        raise ValueError('All current GPU tool queues must remain connected')
    extra = []
    if flexible_gpu:
        # A new immutable file changes allocation policy, not native commands.
        worker_config = dict(worker_config, version='0.2.0', uuid=None)
        config_name = 'antigen-gpu-assigned-' + sha(encode(worker_config))[:12]
        extra.append(dict(apiVersion='v1', kind='ConfigMap', metadata=dict(name=config_name, namespace=namespace),
                          immutable=True, data={'unified-gpu.json': encode(worker_config).decode()}))
        original_spec['volumes'].append(dict(name='assigned-gpu-config', configMap=dict(name=config_name)))
        for m in gpu['volumeMounts']:
            if m['mountPath'] == '/etc/t01/unified-gpu.json':
                m['name'] = 'assigned-gpu-config'
        original['metadata']['annotations'] = {k: v for k, v in original['metadata'].get('annotations', {}).items()
                                                if not k.startswith('nvidia.com/')}
        original['metadata']['annotations']['antigen-design/gpu-worker-config'] = config_name

    # API and CPU workers retain their images, commands and mounts, and explicitly
    # hide devices even on nodes whose default container runtime is NVIDIA.
    cpu = copy.deepcopy(original)
    cpu['spec']['containers'] = [c for c in cpu['spec']['containers'] if c['name'] != 'worker-unified-gpu']
    for c in cpu['spec']['containers'] + cpu['spec'].get('initContainers', []):
        if any(k.startswith('nvidia.com/') for values in c.get('resources', {}).values() for k in values):
            raise ValueError('Unexpected second GPU requester')
        cpu_visibility(c)
    cpu['spec'].pop('runtimeClassName', None)
    cpu['spec']['schedulerName'] = 'default-scheduler'
    cpu['metadata']['annotations'] = {k: v for k, v in cpu['metadata'].get('annotations', {}).items()
                                      if not k.startswith('nvidia.com/') and not k.startswith('antigen-design/gpu-')}
    cpu['metadata']['annotations']['antigen-design/gpu-mode'] = 'on-demand-cpu-control'
    pin_node(cpu['spec'], node)
    prune_volumes(cpu['spec'])
    cpu_workers = []
    if split_cpu_workers:
        for container in cpu['spec']['containers']:
            if container['name'] == 'service':
                continue
            name = 'antigen-design-' + container['name']
            worker_template = copy.deepcopy(cpu)
            worker_template['metadata']['labels'] = {'app.kubernetes.io/name': 'antigen-design',
                'app.kubernetes.io/component': 'cpu-worker', 'antigen-design/worker': container['name']}
            worker_template['spec']['containers'] = [copy.deepcopy(container)]
            worker_template['spec']['automountServiceAccountToken'] = False
            prune_volumes(worker_template['spec'])
            cpu_workers.append(deployment(name, namespace, worker_template))
        cpu['spec']['containers'] = [c for c in cpu['spec']['containers'] if c['name'] == 'service']
        prune_volumes(cpu['spec'])

    slot = copy.deepcopy(original)
    slot['metadata']['labels'] = {'app.kubernetes.io/name': 'antigen-design',
                                 'app.kubernetes.io/component': 'gpu-demand', LABEL: SLOT}
    slot['metadata']['annotations']['antigen-design/gpu-mode'] = 'on-demand-drain'
    gpu['command'] = ['/opt/t01/supervisor/bin/python3.11', '-u', '-B', '-m', 't01_phase1_real.gpu_on_demand']
    gpu['args'] = ['worker', '--config', '/etc/t01/unified-gpu.json']
    gpu['env'] += [{'name': SESSION_ENV, 'value': 'UNASSIGNED'},
                   {'name': POD_ENV, 'valueFrom': {'fieldRef': {'apiVersion': 'v1', 'fieldPath': 'metadata.uid'}}}]
    slot['spec']['containers'] = [gpu]
    slot['spec']['automountServiceAccountToken'] = False
    pin_node(slot['spec'], node)
    prune_volumes(slot['spec'])
    settings = dict(version='0.1.0', namespace=namespace, deployment=SLOT,
                    state_root=worker_config['state_root'], worker_config='/etc/t01/unified-gpu.json',
                    template=normalized_template(slot))
    settings_name = CONTROLLER + '-' + sha(encode(settings))[:12]
    cm = dict(apiVersion='v1', kind='ConfigMap', metadata=dict(name=settings_name, namespace=namespace),
              immutable=True, data={'controller.json': encode(settings).decode()})

    service = next(c for c in original_spec['containers'] if c['name'] == 'service')
    control = copy.deepcopy(original)
    control['metadata'] = dict(labels={'app.kubernetes.io/name': 'antigen-design',
                                      'app.kubernetes.io/component': 'gpu-controller'},
                               annotations={'antigen-design/source-sha256': sha(encode(manifest))})
    spec = control['spec']
    spec.pop('runtimeClassName', None)
    spec['schedulerName'] = 'default-scheduler'
    spec['serviceAccountName'] = CONTROLLER
    spec['automountServiceAccountToken'] = True
    registry_mounts = [copy.deepcopy(m) for m in gpu['volumeMounts'] if m['name'] in {'resident-config', 'assigned-gpu-config'}]
    source_mounts = [copy.deepcopy(m) for m in service['volumeMounts']
                     if m['name'] == 'project-source' and m['mountPath'].startswith('/app/src/')]
    spec['containers'] = [dict(name='controller', image=service['image'], imagePullPolicy='IfNotPresent',
        command=['python', '-u', '-B', '-m', 't01_phase1_real.gpu_on_demand'],
        args=['controller', '--config', '/etc/t01/on-demand/controller.json'],
        env=[dict(name='PYTHONPATH', value='/app/src'), dict(name='NVIDIA_VISIBLE_DEVICES', value='void')],
        resources=dict(requests=dict(cpu='100m', memory='128Mi'), limits=dict(cpu='1', memory='512Mi')),
        securityContext=copy.deepcopy(gpu['securityContext']),
        volumeMounts=[dict(name='runtime', mountPath='/var/lib/t01'),
                      dict(name='on-demand-config', mountPath='/etc/t01/on-demand', readOnly=True),
                      *registry_mounts, *source_mounts])]
    for initializer in spec.get('initContainers', []):
        cpu_visibility(initializer)
    spec['volumes'].append(dict(name='on-demand-config', configMap=dict(name=settings_name)))
    pin_node(spec, node)
    prune_volumes(spec)
    sa = dict(apiVersion='v1', kind='ServiceAccount', metadata=dict(name=CONTROLLER, namespace=namespace))
    role = dict(apiVersion='rbac.authorization.k8s.io/v1', kind='Role',
        metadata=dict(name=CONTROLLER, namespace=namespace), rules=[
            dict(apiGroups=['apps'], resources=['deployments'], resourceNames=[SLOT], verbs=['get', 'patch']),
            dict(apiGroups=[''], resources=['pods'], verbs=['list'])])
    binding = dict(apiVersion='rbac.authorization.k8s.io/v1', kind='RoleBinding',
        metadata=dict(name=CONTROLLER, namespace=namespace),
        roleRef=dict(apiGroup='rbac.authorization.k8s.io', kind='Role', name=CONTROLLER),
        subjects=[dict(kind='ServiceAccount', name=CONTROLLER, namespace=namespace)])
    offline = dict(apiVersion='networking.k8s.io/v1', kind='NetworkPolicy',
        metadata=dict(name=SLOT + '-offline', namespace=namespace),
        spec=dict(podSelector=dict(matchLabels={LABEL: SLOT}),
                  policyTypes=['Ingress', 'Egress'], ingress=[], egress=[]))
    objects = (package['items'] if package['kind'] == 'List' else [package]) + extra + cpu_workers + [
        cm, sa, role, binding, offline, deployment(SLOT, namespace, slot), deployment(CONTROLLER, namespace, control)]
    patch = [dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
             dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
             dict(op='test', path='/spec/template', value=live['spec']['template']),
             dict(op='replace', path='/spec/template', value=cpu)]
    rollback = [dict(op='test', path='/spec/template', value=cpu),
                dict(op='replace', path='/spec/template', value=live['spec']['template'])]
    return objects, patch, rollback, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', required=True, type=Path)
    parser.add_argument('--worker-config', required=True, type=Path)
    parser.add_argument('--node', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--flexible-gpu', action='store_true', help='Accept the scheduler-assigned physical GPU')
    parser.add_argument('--split-cpu-workers', action='store_true', help='Render eight independent stopped CPU workers')
    args = parser.parse_args()
    live = json.loads(args.live.read_bytes())
    cm = json.loads(args.worker_config.read_bytes())
    worker = json.loads(cm['data']['unified-gpu.json'])
    objects, patch, rollback, manifest = render(live, worker, args.node, Path(__file__).resolve().parents[1] / 'src',
        flexible_gpu=args.flexible_gpu, split_cpu_workers=args.split_cpu_workers)
    args.output.mkdir(parents=True, exist_ok=False)
    admin = [o for o in objects if o['kind'] in {'ServiceAccount', 'Role', 'RoleBinding'}]
    workloads = [o for o in objects if o not in admin]
    for name, value in [('admin-rbac.json', dict(apiVersion='v1', kind='List', items=admin)),
                        ('workloads.json', dict(apiVersion='v1', kind='List', items=workloads)),
                        ('cpu.patch.json', patch), ('rollback.patch.json', rollback), ('source-manifest.json', manifest)]:
        (args.output / name).write_bytes(encode(value))
    receipt = dict(status='LOCAL_PREPARED_STOPPED_NOT_DEPLOYED', source_sha256=sha(encode(manifest)),
        files=len(manifest), original_generation=live['metadata']['generation'], node=args.node,
        cpu_gpu_requests=0, gpu_replicas=0, controller_replicas=0,
        gpu_allocation='scheduler-assigned-exclusive-v1' if args.flexible_gpu else 'pinned-64gb',
        cpu_worker_deployments=8 if args.split_cpu_workers else 0,
        storage_constraint='RWO volumes require all components on the selected node; GPU UUID is not pinned',
        admin_grant='admin-rbac.json', stopped_workloads='workloads.json', gpu_worker_network='deny-all',
        activation_requires=['fresh workload/idle and source validation', 'dedicated Role and RoleBinding',
                             'CPU-only rollout and previous GPU Pod termination',
                             'shared-volume, API connectivity and real lifecycle acceptance'],
        rollback_requires=['stop controller first', 'scale GPU slot to zero and confirm all slot Pods deleted',
                           'stop all independent CPU workers and confirm their Pods deleted',
                           'only then restore original CPU/GPU combined template'],
        new_scientific_jobs=0, cluster_mutations=0)
    (args.output / 'preparation.json').write_bytes(encode(receipt))
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
