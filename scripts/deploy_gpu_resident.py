"""Apply the reviewed permanent-GPU split; never submit scientific jobs."""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import prepare_m1_p1_deploy as common
from prepare_gpu_resident import GPU
from version_bundle import build, encode, sha

OUT = common.ROOT / 'deploy/gpu-resident/r01'
EV = common.ROOT / 'reports/gpu-resident-20261010'


def run(args, data=None):
    p = subprocess.run(common.K + args, input=None if data is None else encode(data),
                       capture_output=True, timeout=110)
    row = dict(args=args, returncode=p.returncode,
               stdout=p.stdout.decode(errors='replace'), stderr=p.stderr.decode(errors='replace'))
    with (EV / 'operations.jsonl').open('ab') as f:
        f.write(encode(row) + b'\n')
    if p.returncode:
        raise RuntimeError(row['stderr'][-2000:])
    return json.loads(p.stdout) if '-o' in args and args[args.index('-o')+1] == 'json' else row['stdout']


def checks():
    manifest = json.loads((OUT / 'source-manifest.json').read_bytes())
    assert build(common.ROOT / 'src')[1] == manifest, 'Prepared source changed'
    latest = {}
    receipts = []
    for name in ('current-root-r02.xml', 'targeted-r04.xml', 'resident-final-r01.xml'):
        p = common.ROOT / 'reports/gpu-flexible-20261010' / name
        raw = p.read_bytes(); cases = list(ET.fromstring(raw).iter('testcase'))
        if name != 'current-root-r02.xml':
            assert cases and not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
        for c in cases:
            latest[(c.get('classname'), c.get('name'))] = c
        receipts.append(dict(path=str(p.relative_to(common.ROOT)), sha256=sha(raw)))
    assert len(latest) >= 3200
    assert not any(c.find('failure') is not None or c.find('error') is not None for c in latest.values())
    value = dict(tests=len(latest), passed=sum(c.find('skipped') is None for c in latest.values()),
                 skipped=sum(c.find('skipped') is not None for c in latest.values()),
                 receipts=receipts, single_final_full_run=False, source_sha256=sha(encode(manifest)))
    (EV / 'regression.json').write_bytes(encode(value))
    return manifest


def main():
    checks()
    objects = json.loads((OUT / 'workloads.json').read_bytes())['items']
    if sys.argv[1] == 'apply':
        idle = common.idle()
        assert not idle['active_jobs'] and idle['gpu_state']['phase'] == 'idle'
        (EV / 'idle-at-apply.json').write_bytes(encode(idle))
        original = json.loads((EV / 'deployment-before.json').read_bytes())
        current = run(['get', 'deployment', 'antigen-design', '-o', 'json'])
        assert current['spec'] == original['spec'] and current['metadata']['uid'] == original['metadata']['uid']
        assert not any(o['kind'] in {'Role', 'RoleBinding', 'ServiceAccount'} for o in objects)
        for obj in objects:
            run(['create', '-f', '-', '-o', 'name'], obj)
        current = run(['get', 'deployment', 'antigen-design', '-o', 'json'])
        assert current['spec'] == original['spec']
        patch = json.loads((OUT / 'cpu.patch.json').read_bytes())
        next(p for p in patch if p['path'] == '/metadata/resourceVersion')['value'] = current['metadata']['resourceVersion']
        path = OUT / 'cpu.applied.patch.json'; path.write_bytes(encode(patch))
        run(['patch', 'deployment', 'antigen-design', '--type=json', '--patch-file', str(path), '-o', 'name'])
        print('API_ONLY_ROLLOUT_STARTED; all independent workers still at zero')
    elif sys.argv[1] == 'activate':
        current = run(['get', 'deployment', 'antigen-design', '-o', 'json'])
        expected = json.loads((OUT / 'cpu.patch.json').read_bytes())[-1]['value']
        assert current['spec']['template'] == expected
        assert current['status'].get('readyReplicas') == 1
        pods = run(['get', 'pods', '-l', 'app.kubernetes.io/name=antigen-design', '-o', 'json'])['items']
        assert not any(any(c['name'] == 'worker-unified-gpu' for c in p['spec']['containers']) for p in pods), 'Previous GPU Pod remains'
        for obj in objects:
            if obj['kind'] == 'Deployment':
                run(['scale', 'deployment', obj['metadata']['name'], '--current-replicas=0', '--replicas=1'])
        print('EIGHT_CPU_WORKERS_AND_ONE_RESIDENT_GPU_ACTIVATED')
    else:
        raise ValueError('Expected apply or activate')


if __name__ == '__main__':
    main()
