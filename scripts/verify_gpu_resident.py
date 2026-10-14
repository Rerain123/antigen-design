"""Read-only verification of split resident workers; no model submissions."""
import concurrent.futures
import copy
import datetime
import json
import subprocess

import deploy_gpu_resident as deploy
import verify_version_unification as base
from version_bundle import encode


def check_template(observed, expected):
    template = copy.deepcopy(expected)
    for volume in template['spec'].get('volumes', []):
        if 'configMap' in volume:
            volume['configMap'].setdefault('defaultMode', 420)
    assert observed == template, 'template mismatch'


def main():
    manifest = deploy.checks()
    objects = json.loads((deploy.OUT / 'workloads.json').read_bytes())['items']
    expected = {o['metadata']['name']: o['spec']['template'] for o in objects if o['kind'] == 'Deployment'}
    expected['antigen-design'] = json.loads((deploy.OUT / 'cpu.patch.json').read_bytes())[-1]['value']
    deployments = deploy.run(['get', 'deployments', '-o', 'json'])['items']
    pods = deploy.run(['get', 'pods', '-l', 'app.kubernetes.io/name=antigen-design', '-o', 'json'])['items']
    ready = []
    for name, template in expected.items():
        live = next(o for o in deployments if o['metadata']['name'] == name)
        check_template(live['spec']['template'], template)
        assert live['spec']['replicas'] == 1 and live['status'].get('readyReplicas') == 1, (name, 'not ready')
        matches = [p for p in pods if not p['metadata'].get('deletionTimestamp')
                   and all(p['metadata']['labels'].get(k) == v for k, v in live['spec']['selector']['matchLabels'].items())]
        assert len(matches) == 1 and len(matches[0]['spec']['containers']) == 1
        p = matches[0]
        assert all(c['ready'] and c['restartCount'] == 0 for c in p['status']['containerStatuses'])
        ready.append(p)
    assert not any(o['metadata']['name'].startswith('antigen-design-gpu-controller') for o in deployments)
    boot = "import json,sys;p=json.load(sys.stdin);exec(compile(p.pop('code'),'resident-verification','exec'))"
    code = base.REMOTE.replace('p=json.load(sys.stdin)', '')
    code = code.replace("    extra['gpu_state']=", "    extra['device']=json.loads(Path('/var/lib/t01/resident/unified-gpu/device.json').read_bytes())\n    extra['gpu_state']=")
    def check(pod):
        c = pod['spec']['containers'][0]['name']
        python = 'python' if c == 'service' else '/opt/t01/supervisor/bin/python3.11'
        p = subprocess.run(deploy.common.K + ['exec', '-i', pod['metadata']['name'], '-c', c,
            '--', python, '-B', '-c', boot], input=encode(dict(code=code, container=c, manifest=manifest)),
            capture_output=True, timeout=150)
        assert p.returncode == 0, (c, p.stderr.decode(errors='replace')[-1800:])
        value = json.loads(next(line[7:] for line in p.stdout.decode().splitlines() if line.startswith('VERIFY=')))
        value['pod'] = pod['metadata']['name']
        return value
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(check, ready))
    gpu = next(r for r in results if r['container'] == 'worker-unified-gpu')
    assert gpu['extra']['gpu_state']['phase'] == 'idle'
    assert gpu['extra']['device']['allocation_policy'] == 'scheduler-assigned-exclusive-v1'
    service = next(r for r in results if r['container'] == 'service')
    for item in gpu['native']:
        if 'profile' in item:
            assert item['profile'] == service['extra']['profiles'][item['tool']]
    idle = deploy.common.idle(); assert not idle['active_jobs']
    result = dict(status='PASS', checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        containers=results, deployment_count=len(expected), source_files=len(manifest),
        gpu_mode='resident-exclusive', idle_gpu_retained=True, new_rbac_resources=0,
        scientific_models_executed=False, scientific_jobs_submitted=0, idle=idle)
    (deploy.EV / 'deployment-verification.json').write_bytes(encode(result))
    print(json.dumps(dict(status='PASS', deployments=len(expected), source_files=len(manifest), device=gpu['extra']['device'])))


if __name__ == '__main__':
    main()
