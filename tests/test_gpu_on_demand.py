import copy
import json
from pathlib import Path
import sys

import pytest

from t01_phase1_real import gpu_on_demand as demand
from t01_phase1_real import unified_gpu_worker as unified
from t01_phase1_real.resident_process import Command, atomic, prepare


def finish(target, state='succeeded', stopped=True):
    request, digest = unified.read_json(target / 'request.json')
    value = dict(state=state, stopped_confirmed=stopped, binding=request['binding'], request_sha256=digest)
    atomic(target / 'execution.json', value)
    return value


class API:
    def __init__(self, template):
        self.live = dict(metadata=dict(name='slot', uid='deployment-uid', resourceVersion='1'),
                         spec=dict(replicas=0, strategy=dict(type='Recreate'), template=copy.deepcopy(template)))
        self.rows = []
        self.patches = []
        self.fail_after_patch = False

    def deployment(self):
        return copy.deepcopy(self.live)

    def pods(self):
        return copy.deepcopy(self.rows)

    def patch(self, live, changes):
        assert live['metadata'] == self.live['metadata']
        self.patches.append(copy.deepcopy(changes))
        for row in changes:
            parts = [p.replace('~1', '/').replace('~0', '~') for p in row['path'].split('/')[1:]]
            dest = self.live
            for p in parts[:-1]:
                dest = dest[int(p)] if isinstance(dest, list) else dest[p]
            dest[int(parts[-1]) if isinstance(dest, list) else parts[-1]] = row['value']
        self.live['metadata']['resourceVersion'] = str(int(self.live['metadata']['resourceVersion']) + 1)
        if self.fail_after_patch:
            self.fail_after_patch = False
            raise OSError('API response lost after commit')

    def running(self, uid='pod-1', phase='Running', restart=0):
        self.rows = [dict(metadata=dict(name='slot-pod', uid=uid, labels={demand.LABEL: 'slot'}),
                          spec=dict(containers=[]), status=dict(phase=phase,
                              containerStatuses=[dict(name='worker', restartCount=restart)]))]


@pytest.fixture
def setup(tmp_path):
    state_root = tmp_path / 'state'
    state_root.mkdir()
    (state_root / 'on-demand').mkdir()
    roots = {}
    for name in ('proteinmpnn', 'esmfold2', 'af3'):
        root = tmp_path / name
        root.mkdir()
        roots[root] = {name: Command(name, ('/usr/bin/python3', '-V'))}
    template = dict(metadata=dict(annotations={}), spec=dict(containers=[dict(name='worker',
        env=[dict(name=demand.SESSION_ENV, value='UNASSIGNED')])]))
    config = dict(deployment='slot', state_root=str(state_root), template=template)
    api = API(template)
    state = state_root / 'on-demand/controller.json'
    def submit(name='af3', ident='a'):
        root = tmp_path / name
        return prepare(root, ident * 32, dict(job_id=ident, attempt_id='attempt', execution_identity=ident),
                       roots[root][name], {'input.json': b'{}'}, 10)
    def tick():
        return demand.tick(config, roots, state, api,
                           cancel_execute=lambda target, command, stopping: finish(target, 'cancelled'),
                           new_session=lambda: 'b' * 32)
    return config, roots, state, api, submit, tick


def start(setup):
    config, roots, state, api, submit, tick = setup
    target = submit()
    assert tick() == 'reserved'
    assert api.live['spec']['replicas'] == 0
    assert tick() == 'start'
    api.running()
    assert tick() == 'wait'
    return target


def test_cpu_idle_never_requests_gpu(setup):
    *_, api, submit, tick = setup
    assert tick() == 'idle'
    assert tick() == 'idle'
    assert api.patches == []


@pytest.mark.parametrize('terminal', ['succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'])
def test_full_lifecycle_releases_gpu_and_never_replays_tool(setup, terminal):
    config, roots, state, api, submit, tick = setup
    target = start(setup)
    calls = []
    def execute(target, command, stopping):
        calls.append(command.tool)
        return finish(target, terminal)
    receipt = demand.drain(roots, config['state_root'], 'b' * 32, 'pod-1', lambda: False, execute)
    assert receipt['phase'] == 'quiescent'
    assert tick() == 'release'
    assert api.live['spec']['replicas'] == 0
    assert tick() == 'wait_for_pod_deletion'
    api.rows = []
    assert tick() == 'released'
    assert tick() == 'idle'
    assert calls == ['af3']
    assert unified.read_json(target / 'execution.json')[0]['state'] == terminal


def test_arrival_after_worker_quiescence_waits_for_new_session(setup):
    config, roots, state, api, submit, tick = setup
    start(setup)
    calls = []
    def execute(target, command, stopping):
        calls.append(command.tool)
        return finish(target)
    assert demand.drain(roots, config['state_root'], 'b' * 32, 'pod-1', lambda: False, execute)['phase'] == 'quiescent'
    next_target = submit('esmfold2', 'c')
    # Even a container restart after announcing quiescence must not take it.
    demand.drain(roots, config['state_root'], 'b' * 32, 'pod-1', lambda: False, execute)
    assert calls == ['af3'] and not (next_target / 'execution.json').exists()
    assert tick() == 'release'
    assert tick() == 'wait_for_pod_deletion'
    api.rows = []
    assert tick() == 'released'
    assert demand.tick(config, roots, state, api, new_session=lambda: 'd' * 32) == 'reserved'
    assert json.loads(state.read_bytes())['session'] == 'd' * 32


def test_patch_response_loss_does_not_create_another_session(setup):
    config, roots, state, api, submit, tick = setup
    submit(); assert tick() == 'reserved'
    api.fail_after_patch = True
    with pytest.raises(OSError): tick()
    assert tick() == 'observe'
    assert len(api.patches) == 1


def test_release_response_loss_retries_only_scale_down(setup):
    config, roots, state, api, submit, tick = setup
    start(setup)
    demand.drain(roots, config['state_root'], 'b' * 32, 'pod-1', lambda: False,
                 lambda target, *args: finish(target))
    api.fail_after_patch = True
    with pytest.raises(OSError): tick()
    assert json.loads(state.read_bytes())['phase'] == 'releasing'
    assert tick() == 'wait_for_pod_deletion'
    api.rows = []
    assert tick() == 'released'


@pytest.mark.parametrize('when', ['idle', 'reserved', 'pending'])
def test_cancellation_does_not_need_a_free_gpu(setup, when):
    config, roots, state, api, submit, tick = setup
    target = submit()
    if when != 'idle': assert tick() == 'reserved'
    if when == 'pending':
        assert tick() == 'start'
        api.running(phase='Pending')
    (target / 'cancel').touch()
    if when == 'pending':
        assert tick() == 'release'
        api.rows = []
        assert tick() == 'released'
        assert tick() == 'idle'
    elif when == 'reserved':
        assert tick() == 'cancelled_before_start'
    else:
        assert tick() == 'idle'
    assert api.live['spec']['replicas'] == 0
    assert unified.read_json(target / 'execution.json')[0]['state'] == 'cancelled'
    if when != 'pending': assert api.patches == []


@pytest.mark.parametrize('fault', ['restart', 'replacement', 'failed', 'multiple', 'bad_receipt', 'blocked'])
def test_uncertain_session_releases_resource_without_replaying_science(setup, fault):
    config, roots, state, api, submit, tick = setup
    target = start(setup)
    if fault == 'restart': api.running(restart=1)
    elif fault == 'replacement': api.running(uid='pod-2')
    elif fault == 'failed': api.running(phase='Failed')
    elif fault == 'multiple': api.rows.append(copy.deepcopy(api.rows[0]))
    else:
        atomic(demand.session_file(config['state_root'], 'b' * 32), dict(
            session='b' * 32, pod_uid='wrong' if fault == 'bad_receipt' else 'pod-1', phase='blocked'))
    assert tick() == 'release'
    assert api.live['spec']['replicas'] == 0
    api.rows = []
    assert tick() == 'blocked'
    with pytest.raises(RuntimeError, match='needs operator recovery'): tick()
    assert not (target / 'execution.json').exists()


def test_unconfirmed_worker_receipt_never_announces_clean_release(setup):
    config, roots, state, api, submit, tick = setup
    target = start(setup)
    receipt = demand.drain(roots, config['state_root'], 'b' * 32, 'pod-1', lambda: False,
                           lambda target, *args: finish(target, 'running', False))
    assert receipt['phase'] == 'blocked'
    assert tick() == 'release'
    assert unified.read_json(target / 'execution.json')[0]['stopped_confirmed'] is False


@pytest.mark.parametrize('kind', ['containers', 'initializers'])
@pytest.mark.parametrize('failure', ['restart', 'image', 'config'])
def test_container_startup_failure_releases_and_quarantines(setup, kind, failure):
    config, roots, state, api, submit, tick = setup
    target = start(setup)
    status = dict(name='worker', restartCount=1 if failure == 'restart' else 0)
    if failure != 'restart':
        status['state'] = dict(waiting=dict(reason='ImagePullBackOff' if failure == 'image' else 'CreateContainerConfigError'))
    api.rows[0]['status'] = dict(phase='Pending', **{
        'containerStatuses' if kind == 'containers' else 'initContainerStatuses': [status]})
    assert tick() == 'release'
    assert api.live['spec']['replicas'] == 0
    assert tick() == 'wait_for_pod_deletion'
    api.rows = []
    assert tick() == 'blocked'
    assert not (target / 'execution.json').exists()


@pytest.mark.parametrize('reason', ['ContainerCreating', 'PodInitializing', None])
def test_pending_gpu_or_normal_container_startup_is_not_interrupted(setup, reason):
    config, roots, state, api, submit, tick = setup
    start(setup)
    api.running(phase='Pending')
    api.rows[0]['status']['conditions'] = [dict(type='PodScheduled', status='False', reason='Unschedulable')]
    if reason:
        api.rows[0]['status']['containerStatuses'][0]['state'] = dict(waiting=dict(reason=reason))
    count = len(api.patches)
    assert tick() == 'wait'
    assert api.live['spec']['replicas'] == 1 and len(api.patches) == count


@pytest.mark.parametrize('raw', [b'{broken', b'[]', b'null', b'{}'])
def test_invalid_session_record_does_not_keep_gpu_reserved(setup, raw):
    config, roots, state, api, submit, tick = setup
    target = start(setup)
    demand.session_file(config['state_root'], 'b' * 32).write_bytes(raw)
    assert tick() == 'release'
    assert api.live['spec']['replicas'] == 0
    api.rows = []
    assert tick() == 'blocked'
    assert not (target / 'execution.json').exists()


@pytest.mark.skipif(sys.platform != 'linux', reason='Real symlink protection requires Linux')
@pytest.mark.parametrize('kind', ['session', 'unified'])
def test_symlink_receipt_releases_without_writing_through_it(setup, kind):
    config, roots, state, api, submit, tick = setup
    start(setup)
    path = demand.session_file(config['state_root'], 'b' * 32)
    if kind == 'unified':
        atomic(path, dict(session='b' * 32, pod_uid='pod-1', phase='quiescent', stopped_confirmed=True))
        path = Path(config['state_root']) / 'state.json'
    outside = Path(config['state_root']) / 'untouched.json'
    outside.write_bytes(b'original')
    path.symlink_to(outside)
    assert tick() == 'release'
    assert outside.read_bytes() == b'original'
    api.rows = []
    assert tick() == 'blocked'


@pytest.mark.parametrize('receipt_phase,fault', [
    ('active', 'corrupt_request'), ('quiescent', 'active_owner'),
    ('quiescent', 'corrupt_owner'), ('quiescent', 'corrupt_request'),
    ('active', 'corrupt_execution'), ('quiescent', 'corrupt_execution'),
    ('quiescent', 'uncertain_execution')])
def test_uncertain_execution_evidence_cannot_retain_gpu_or_replay(setup, fault, receipt_phase):
    config, roots, state, api, submit, tick = setup
    target = start(setup)
    atomic(demand.session_file(config['state_root'], 'b' * 32), dict(
        session='b' * 32, pod_uid='pod-1', phase=receipt_phase, stopped_confirmed=True))
    if fault == 'active_owner':
        atomic(Path(config['state_root']) / 'state.json', dict(phase='active'))
    elif fault == 'corrupt_owner':
        (Path(config['state_root']) / 'state.json').write_bytes(b'[]')
    elif fault == 'corrupt_request':
        (target / 'request.json').write_bytes(b'{broken')
    elif fault == 'corrupt_execution':
        (target / 'execution.json').write_bytes(b'[]')
    else:
        finish(target, 'running', False)
    assert tick() == 'release'
    assert api.live['spec']['replicas'] == 0
    api.rows = []
    assert tick() == 'blocked'


def test_running_tool_receipt_is_not_mistaken_for_a_stopped_worker(setup):
    config, roots, state, api, submit, tick = setup
    target = start(setup)
    path = demand.session_file(config['state_root'], 'b' * 32)
    atomic(path, dict(session='b' * 32, pod_uid='pod-1', phase='active'))
    atomic(Path(config['state_root']) / 'state.json', dict(phase='active',
        execution=unified.request_identity(target, roots[target.parent])))
    finish(target, 'running', False)
    count = len(api.patches)
    assert tick() == 'wait'
    assert len(api.patches) == count and api.live['spec']['replicas'] == 1
    finish(target)
    atomic(Path(config['state_root']) / 'state.json', dict(phase='idle'))
    atomic(path, dict(session='b' * 32, pod_uid='pod-1', phase='quiescent', stopped_confirmed=True))
    assert tick() == 'release'


def test_queue_emptied_before_worker_start_does_not_retain_reservation(setup):
    config, roots, state, api, submit, tick = setup
    target = start(setup)
    api.running(phase='Pending')
    finish(target, 'cancelled')
    assert tick() == 'release'
    assert api.live['spec']['replicas'] == 0
    assert tick() == 'wait_for_pod_deletion'
    api.rows = []
    assert tick() == 'released'
    assert tick() == 'idle'
    assert unified.read_json(target / 'execution.json')[0]['state'] == 'cancelled'


def test_session_interrupted_before_completion_never_runs_again(setup):
    config, roots, state, api, submit, tick = setup
    start(setup)
    atomic(demand.session_file(config['state_root'], 'b' * 32), dict(session='b' * 32, pod_uid='pod-1', phase='active'))
    receipt = demand.drain(roots, config['state_root'], 'b' * 32, 'pod-1', lambda: False,
                           lambda *args: pytest.fail('must not execute'))
    assert receipt['phase'] == 'blocked'


def test_three_queues_drain_in_existing_fifo(setup):
    import os
    config, roots, state, api, submit, tick = setup
    for i, name in enumerate(('proteinmpnn', 'esmfold2', 'af3')):
        target = submit(name, str(i + 1))
        os.utime(target / 'request.json', ns=((i + 1) * 1_000_000_000,) * 2)
    calls = []
    def execute(target, command, stopping):
        calls.append(command.tool)
        return finish(target)
    demand.drain(roots, config['state_root'], 'b' * 32, 'pod-1', lambda: False, execute)
    assert calls == ['proteinmpnn', 'esmfold2', 'af3']


@pytest.mark.parametrize('drift', ['template', 'deployment_uid', 'session', 'extra_resources'])
def test_drift_is_not_overwritten(setup, drift):
    config, roots, state, api, submit, tick = setup
    start(setup)
    if drift == 'template': api.live['spec']['template']['spec']['containers'][0]['name'] = 'foreign'
    elif drift == 'deployment_uid': api.live['metadata']['uid'] = 'foreign'
    elif drift == 'extra_resources': api.live['spec']['template']['spec']['containers'][0]['resources'] = {'limits': {'nvidia.com/gpumem': '1024'}}
    else: api.live['spec']['template']['metadata']['annotations'][demand.SESSION_ANNOTATION] = 'f' * 32
    count = len(api.patches)
    with pytest.raises(RuntimeError): tick()
    assert len(api.patches) == count


def test_foreign_project_holder_or_unknown_receipt_prevents_allocation(setup):
    config, roots, state, api, submit, tick = setup
    target = submit()
    api.rows = [dict(metadata=dict(name='antigen-old', labels={}), status=dict(phase='Running'),
                     spec=dict(containers=[dict(resources=dict(limits={'nvidia.com/gpu': '1'}))]))]
    with pytest.raises(RuntimeError, match='Another project'): tick()
    api.rows = []
    finish(target, 'running', False)
    with pytest.raises(RuntimeError, match='Unconfirmed'): tick()
    assert not api.patches


def test_render_preserves_science_and_cpu_service_is_independent_of_gpu():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    from prepare_gpu_on_demand import render, SLOT, CONTROLLER
    ev = root / 'reports/gpu-on-demand-20261009'
    live = json.loads((ev / 'deployment.json').read_bytes())
    config = json.loads(json.loads((ev / 'worker-config.json').read_bytes())['data']['unified-gpu.json'])
    before = copy.deepcopy(live)
    objects, patch, rollback, manifest = render(live, config, 'k8s-a100-02', root / 'src')
    assert live == before
    cpu = patch[-1]['value']
    original = live['spec']['template']['spec']
    assert len(cpu['spec']['containers']) == 9
    for c in cpu['spec']['containers']:
        expected = copy.deepcopy(next(old for old in original['containers'] if old['name'] == c['name']))
        expected['env'] = [e for e in expected.get('env', []) if e['name'] != 'NVIDIA_VISIBLE_DEVICES']
        expected['env'].append(dict(name='NVIDIA_VISIBLE_DEVICES', value='void'))
        assert c == expected
    assert cpu['spec']['schedulerName'] == 'default-scheduler'
    assert 'runtimeClassName' not in cpu['spec']
    assert not any(k.startswith('nvidia.com/') for k in cpu['metadata']['annotations'])
    deps = {d['metadata']['name']: d for d in objects if d['kind'] == 'Deployment'}
    assert deps[SLOT]['spec']['replicas'] == deps[CONTROLLER]['spec']['replicas'] == 0
    gpu = deps[SLOT]['spec']['template']['spec']['containers'][0]
    old_gpu = next(c for c in original['containers'] if c['name'] == 'worker-unified-gpu')
    for key in ('image', 'resources', 'volumeMounts', 'securityContext'):
        assert gpu[key] == old_gpu[key]
    for dep in deps.values():
        spec = dep['spec']['template']['spec']
        assert spec['affinity'] == cpu['spec']['affinity']
        assert spec['initContainers'][0]['args'][-1] == cpu['spec']['initContainers'][0]['args'][-1]
    role = next(d for d in objects if d['kind'] == 'Role')
    assert role['rules'] == [dict(apiGroups=['apps'], resources=['deployments'], resourceNames=[SLOT], verbs=['get', 'patch']),
                              dict(apiGroups=[''], resources=['pods'], verbs=['list'])]
    offline = next(d for d in objects if d['kind'] == 'NetworkPolicy')
    assert offline['spec'] == dict(podSelector=dict(matchLabels={demand.LABEL: SLOT}),
                                   policyTypes=['Ingress', 'Egress'], ingress=[], egress=[])
    selector = {'app.kubernetes.io/name': 'antigen-design', 'app.kubernetes.io/component': 'control-plane'}
    assert all(cpu['metadata']['labels'].get(k) == v for k, v in selector.items())
    assert all(not all(d['spec']['template']['metadata']['labels'].get(k) == v for k, v in selector.items())
               for d in deps.values())
    assert rollback[-1]['value'] == before['spec']['template']
    assert 't01_phase1_real/gpu_on_demand.py' in manifest


def test_preparation_separates_admin_grant_from_stopped_workloads(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    import prepare_gpu_on_demand as prepare_deploy
    evidence = root / 'reports/gpu-on-demand-20261009'
    output = tmp_path / 'candidate'
    monkeypatch.setattr(sys, 'argv', ['prepare_gpu_on_demand', '--live', str(evidence / 'deployment.json'),
        '--worker-config', str(evidence / 'worker-config.json'), '--node', 'k8s-a100-02', '--output', str(output)])
    prepare_deploy.main()
    admin = json.loads((output / 'admin-rbac.json').read_bytes())['items']
    workloads = json.loads((output / 'workloads.json').read_bytes())['items']
    assert {o['kind'] for o in admin} == {'ServiceAccount', 'Role', 'RoleBinding'}
    assert all(o['kind'] not in {'ServiceAccount', 'Role', 'RoleBinding'} for o in workloads)
    assert all(o['spec']['replicas'] == 0 for o in workloads if o['kind'] == 'Deployment')
    assert not (output / 'objects.json').exists()
    assert json.loads((output / 'preparation.json').read_bytes())['cluster_mutations'] == 0
    original = (output / 'cpu.patch.json').read_bytes()
    with pytest.raises(FileExistsError):
        prepare_deploy.main()
    assert (output / 'cpu.patch.json').read_bytes() == original


def test_flexible_gpu_and_individual_cpu_workers_preserve_commands_mounts_and_exclusivity():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    from prepare_gpu_on_demand import render, SLOT, CONTROLLER
    ev = root / 'reports/gpu-on-demand-20261009'
    live = json.loads((ev / 'deployment.json').read_bytes())
    config = json.loads(json.loads((ev / 'worker-config.json').read_bytes())['data']['unified-gpu.json'])
    # The administrator removed fixed device annotations in the current live template.
    live['spec']['template']['metadata']['annotations'] = {
        k: v for k, v in live['spec']['template']['metadata']['annotations'].items() if not k.startswith('nvidia.com/')}
    before = copy.deepcopy(live)
    objects, patch, rollback, _ = render(live, config, 'k8s-a100-01', root / 'src',
                                         flexible_gpu=True, split_cpu_workers=True)
    assert live == before and config['version'] == '0.1.0'
    cpu = patch[-1]['value']
    assert [c['name'] for c in cpu['spec']['containers']] == ['service']
    deployments = [o for o in objects if o['kind'] == 'Deployment']
    assert len(deployments) == 10 and all(d['spec']['replicas'] == 0 for d in deployments)
    templates = [cpu] + [d['spec']['template'] for d in deployments]
    assert all(t['spec']['affinity'] == cpu['spec']['affinity'] for t in templates)
    assert all('nodeName' not in t['spec'] for t in templates)
    assert all(not any(k.startswith('nvidia.com/') for k in t['metadata']['annotations']) for t in templates)
    workers = [d for d in deployments if d['metadata']['name'] not in {SLOT, CONTROLLER}]
    original = {c['name']: c for c in before['spec']['template']['spec']['containers']}
    for dep in workers:
        t = dep['spec']['template']; c = t['spec']['containers'][0]
        assert t['metadata']['labels']['app.kubernetes.io/component'] == 'cpu-worker'
        for key in ('image', 'command', 'args', 'resources', 'volumeMounts'):
            assert c.get(key) == original[c['name']].get(key)
        assert {'name':'NVIDIA_VISIBLE_DEVICES','value':'void'} in c['env']
        assert not any(v['name'] == 'credentials' for v in t['spec']['volumes'])
    gpu = next(d for d in deployments if d['metadata']['name'] == SLOT)['spec']['template']
    for kind in ('requests', 'limits'):
        resources = gpu['spec']['containers'][0]['resources'][kind]
        assert resources['nvidia.com/gpu'] == '1'
        assert resources['nvidia.com/gpumem-percentage'] == resources['nvidia.com/gpucores'] == '100'
    assigned = next(o for o in objects if o['kind'] == 'ConfigMap' and o['metadata']['name'].startswith('antigen-gpu-assigned-'))
    assert assigned['immutable'] is True
    effective = json.loads(assigned['data']['unified-gpu.json'])
    assert effective == dict(config, version='0.2.0', uuid=None)
    for name in (SLOT, CONTROLLER):
        spec = next(d for d in deployments if d['metadata']['name'] == name)['spec']['template']['spec']
        mount = next(m for m in spec['containers'][0]['volumeMounts'] if m['mountPath'] == '/etc/t01/unified-gpu.json')
        volume = next(v for v in spec['volumes'] if v['name'] == mount['name'])
        assert volume['configMap']['name'] == assigned['metadata']['name']
    assert rollback[-1]['value'] == before['spec']['template']
