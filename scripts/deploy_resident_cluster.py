"""Prepare/review and explicitly apply the existing nine workers to him-ws.

No image builds, pushes, database registration, or Kubernetes Job API calls.
Preparation uses only read requests and server dry-runs. All plans stay in .tmp.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t01_phase1_real import resident_assembly as assembly

OUT = ROOT / '.tmp/antigen-resident-deploy-r01'
KUBECTL = 'C:/Program Files/Docker/Docker/resources/bin/kubectl.exe'
CONFIG = ROOT / '.tmp/himat.kubeconfig'
NS = 'him-ws'
NAME = 'antigen-design'
CONFIG_NAME = 'antigen-resident-config-r01'
PROBE_NAME = 'antigen-gpu-probe-r01'
PUBLISH = ROOT / 'deploy/antigen-resident-publish-20260916-r01/publish-receipts.json'


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2).encode() + b'\n'


def save(name, value):
    (OUT / name).write_bytes(encoded(value))


def kubectl(*args, data=None):
    result = subprocess.run([KUBECTL, '--kubeconfig', str(CONFIG), '--request-timeout=45s',
                             '-n', NS, *args], input=data, capture_output=True)
    if result.returncode:
        # Deployment values and authentication credentials are never printed.
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace')[-2000:])
    return result.stdout


def get(kind, name):
    return json.loads(kubectl('get', kind, name, '-o', 'json'))


def current_pods(deployment):
    selector = ','.join(k+'='+v for k,v in deployment['spec']['selector']['matchLabels'].items())
    return json.loads(kubectl('get', 'pods', '-l', selector, '-o', 'json'))['items']


def image_map(rows):
    result = {}
    for row in rows:
        group = row['group']
        if group in result or row['status'] != 'VERIFIED':
            raise ValueError('Duplicate or unverified image')
        import re
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', row['digest']):
            raise ValueError('Invalid image digest')
        repository = 'harbor-core.base.svc.cluster.local/qcyz/antigen-design-resident-'+group
        if row['image'] != repository+':integration-20260916-r01':
            raise ValueError('Unexpected image repository/tag')
        result[group] = repository+'@'+row['digest']
    if set(result) != set(assembly.GROUPS):
        raise ValueError('All nine verified images required')
    return result


def make_target(before, images, control_image):
    """Keep the current service configuration; add fixed shared-volume workers."""
    target = copy.deepcopy(before)
    if target['replicas'] != 1 or target['strategy'] != {'type': 'Recreate'}:
        raise ValueError('Expected single-replica Recreate deployment')
    pod = target['template']['spec']
    if [c['name'] for c in pod['containers']] != ['service'] or pod.get('initContainers'):
        raise ValueError('Unexpected existing containers; review before preparing again')
    volumes = {v['name']: v for v in pod['volumes']}
    if volumes['runtime']['persistentVolumeClaim']['claimName'] != 'antigen-design-runtime':
        raise ValueError('Unexpected runtime claim')
    if pod.get('securityContext', {}).get('fsGroup') != 10001:
        raise ValueError('Expected shared-volume fsGroup 10001')
    for name in ('tool-assets', 'resident-config', *('slot-'+g for g in images)):
        if name in volumes:
            raise ValueError('Existing volume name collision')
    pod['automountServiceAccountToken'] = False
    # These exact values were observed on the successful HAMi probe Pod.
    pod['runtimeClassName'] = 'nvidia'
    pod['schedulerName'] = 'hami-scheduler'
    pulls = pod.setdefault('imagePullSecrets', [])
    if not any(v['name'] == 'harbor' for v in pulls):
        pulls.append({'name': 'harbor'})
    pod['volumes'] += [
        {'name': 'tool-assets', 'persistentVolumeClaim': {'claimName': 'antigen-design-assets'}},
        {'name': 'resident-config', 'configMap': {'name': CONFIG_NAME}},
    ]
    service = pod['containers'][0]
    service['image'] = control_image
    service.setdefault('env', []).append({'name': 'T01_RESIDENT_CONFIG_FILE', 'value': '/etc/t01/resident.json'})
    service['volumeMounts'] += [
        {'name': 'tool-assets', 'mountPath': '/app/var/t01-phase1-real/tool-assets', 'readOnly': True},
        # subPath avoids the ConfigMap symlink that the secure file reader rejects.
        {'name': 'resident-config', 'mountPath': '/etc/t01/resident.json', 'subPath': 'resident.json', 'readOnly': True},
    ]
    for group in assembly.GROUPS:
        pod['volumes'].append({'name': 'slot-'+group, 'emptyDir': {'sizeLimit': '1Gi'}})
        memory = '16Gi' if group == 'blast' else '12Gi' if group in ('bepipred', 'gpu') else '8Gi' if group in ('structure', 'deeptmhmm', 'homology', 'aggrescan3d') else '4Gi'
        limits = {'cpu': '4' if group in ('gpu', 'deeptmhmm', 'bepipred', 'blast', 'homology') else '2', 'memory': memory}
        if group == 'gpu':
            # Small-input integration allocation, not a full scientific capacity claim.
            limits.update({'nvidia.com/gpu': 1, 'nvidia.com/gpumem': 10240})
        pod['containers'].append({
            'name': 'worker-'+group, 'image': images[group], 'imagePullPolicy': 'IfNotPresent',
            'resources': {'requests': {'cpu': '250m', 'memory': '2Gi' if group == 'gpu' else '1Gi' if group in ('deeptmhmm','bepipred') else '256Mi'}, 'limits': limits},
            'securityContext': {'runAsNonRoot': True, 'runAsUser': 10001, 'runAsGroup': 10001,
                                'readOnlyRootFilesystem': True, 'allowPrivilegeEscalation': False,
                                'capabilities': {'drop': ['ALL']}},
            'volumeMounts': [
                {'name': 'runtime', 'mountPath': '/var/lib/t01'},
                {'name': 'tool-assets', 'mountPath': '/t01/assets', 'readOnly': True},
                {'name': 'slot-'+group, 'mountPath': '/run/t01-slot'},
            ],
        })
    return target


def patch_for(live, spec):
    return [{'op': 'test', 'path': '/metadata/uid', 'value': live['metadata']['uid']},
            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': live['metadata']['resourceVersion']},
            {'op': 'replace', 'path': '/spec', 'value': spec}]


def patch(live, spec, dry=False):
    path = OUT / 'request.patch.json'
    path.write_bytes(encoded(patch_for(live, spec)))
    args = ['patch', 'deployment', NAME, '--type=json', '--patch-file', str(path), '-o', 'json']
    if dry:
        args.append('--dry-run=server')
    return json.loads(kubectl(*args))


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'plan.json').exists():
        raise ValueError('Prepared plan already exists; it is retained for review/rollback')
    live = get('deployment', NAME)
    pod = current_pods(live)
    active = [p for p in pod if not p['metadata'].get('deletionTimestamp') and p['status']['phase']=='Running']
    if len(active) != 1:
        raise ValueError('One running control Pod required')
    status = active[0]['status']['containerStatuses']
    if len(status) != 1 or not status[0]['ready']:
        raise ValueError('Control Pod is not ready')
    control_image = status[0]['imageID'].removeprefix('docker-pullable://')
    if not control_image.startswith('harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:'):
        raise ValueError('Unexpected control image identity')
    for c in live['spec']['template']['spec']['containers']:
        if c.get('envFrom'):
            raise ValueError('Review environment sources before backup')
        for e in c.get('env', []):
            if 'value' in e and e['name'] != 'T01_REAL_SERVICE_CREDENTIALS_FILE':
                raise ValueError('Review literal environment before saving deployment')
    for claim in ('antigen-design-runtime', 'antigen-design-assets'):
        if get('pvc', claim)['status']['phase'] != 'Bound':
            raise ValueError('PVC is not Bound: '+claim)
    probe = get('pod', PROBE_NAME)
    if probe['status']['phase'] != 'Succeeded' or probe['spec'].get('runtimeClassName') != 'nvidia' or probe['spec'].get('schedulerName') != 'hami-scheduler':
        raise ValueError('Successful HAMi probe with expected admission settings required')
    if b'GPU_COMPUTE_PASS' not in kubectl('logs', PROBE_NAME):
        raise ValueError('Missing GPU computation evidence')
    remote_code = "import json; from t01_phase1_real.resident_assembly import configuration; print(json.dumps(configuration()))"
    remote_config = json.loads(kubectl('exec', 'deployment/'+NAME, '-c', 'service', '--', 'python', '-B', '-c', remote_code))
    config = assembly.configuration()
    if config != remote_config:
        raise ValueError('Control command configuration differs from local assembly')
    # Verify commands baked into the exact integration image build inputs too.
    build = ROOT / 'deploy/antigen-design-resident-integration-20260915-r01/configuration'
    for group, tools in assembly.GROUPS.items():
        baked = json.loads((build/(group+'.worker.json')).read_bytes())
        if baked != {'version':'0.1.0','commands':[config['tools'][t]['command'] for t in tools]}:
            raise ValueError('Baked worker/control command mismatch: '+group)
    images = image_map(json.loads(PUBLISH.read_bytes()))
    target = make_target(live['spec'], images, control_image)
    cm = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':CONFIG_NAME,'namespace':NS},
          'immutable':True,'data':{'resident.json':encoded(config).decode()}}
    save('resident-config.json', cm)
    kubectl('create', '--dry-run=server', '-f', str(OUT/'resident-config.json'), '-o', 'name')
    admitted = patch(live, target, dry=True)
    rollback = copy.deepcopy(live['spec'])
    rollback['template']['spec']['containers'][0]['image'] = control_image
    save('deployment.before.json', {'apiVersion':'apps/v1','kind':'Deployment',
         'metadata':{'name':NAME,'namespace':NS},'spec':rollback})
    save('deployment.target.json', {'apiVersion':'apps/v1','kind':'Deployment',
         'metadata':{'name':NAME,'namespace':NS},'spec':admitted['spec']})
    plan = {'uid':live['metadata']['uid'], 'before_spec':live['spec'], 'target_spec':admitted['spec'],
            'rollback_spec':rollback, 'control_image':control_image,
            'config_sha256':hashlib.sha256(encoded(cm)).hexdigest()}
    save('plan.json', plan)
    print('PREPARED_SERVER_DRY_RUN_PASS 1 control + 9 workers; GPU 10240 MiB')
    print('NO_DEPLOYMENT_CHANGED', OUT)


def apply_plan(rollback=False):
    plan = json.loads((OUT/'plan.json').read_bytes())
    live = get('deployment', NAME)
    if live['metadata']['uid'] != plan['uid']:
        raise ValueError('Deployment was recreated; retained plan cannot be applied')
    expected = plan['target_spec'] if rollback else plan['before_spec']
    desired = plan['rollback_spec'] if rollback else plan['target_spec']
    if live['spec'] == desired:
        print('ALREADY_APPLIED'); return
    if live['spec'] != expected:
        raise ValueError('Deployment changed since preparation; review drift before applying')
    if not rollback:
        cm_path = OUT/'resident-config.json'
        if hashlib.sha256(cm_path.read_bytes()).hexdigest() != plan['config_sha256']:
            raise ValueError('Prepared ConfigMap changed')
        kubectl('apply', '-f', str(cm_path))
        # Only the named temporary asset uploader is removed; PVCs are retained.
        uploader = json.loads(kubectl('get','pod','antigen-assets-upload','--ignore-not-found','-o','json') or b'null')
        if uploader:
            claims = [v.get('persistentVolumeClaim',{}).get('claimName') for v in uploader['spec'].get('volumes',[])]
            if uploader['metadata'].get('labels',{}).get('app') != 'antigen-assets-upload' or claims != ['antigen-design-assets']:
                raise ValueError('Unexpected asset uploader identity; no deletion performed')
            kubectl('delete', 'pod', 'antigen-assets-upload', '--wait=false')
            print('ASSET_UPLOAD_POD_REMOVAL_REQUESTED; PVC RETAINED', flush=True)
    updated = patch(live, desired)
    save('rollback.applied.json' if rollback else 'deployment.applied.json',
         {'uid':updated['metadata']['uid'],'generation':updated['metadata']['generation'],'spec':updated['spec']})
    print('ROLLBACK_SUBMITTED' if rollback else 'DEPLOYMENT_SUBMITTED')
    print('Run status to check image pulls and startup; no watch stream is required.')


def status():
    live = get('deployment', NAME)
    print('DEPLOYMENT', 'generation', live['metadata']['generation'], 'observed',live.get('status',{}).get('observedGeneration'),
          'ready', live.get('status',{}).get('readyReplicas',0))
    for pod in current_pods(live):
        print('POD',pod['metadata']['name'],pod['status']['phase'],pod['spec'].get('nodeName','unscheduled'))
        for c in pod['status'].get('containerStatuses',[]):
            print(' ',c['name'],'ready='+str(c['ready']),'restarts='+str(c['restartCount']),json.dumps(c['state']))
        events = json.loads(kubectl('get','events','--field-selector','involvedObject.name='+pod['metadata']['name'],'-o','json'))
        for e in sorted(events['items'],key=lambda e:e.get('lastTimestamp') or e['metadata']['creationTimestamp'])[-8:]:
            print('EVENT',e['reason'],e['message'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','apply','status','rollback'])
    action = parser.parse_args().action
    if action=='prepare': prepare()
    elif action=='status': status()
    else: apply_plan(action=='rollback')


if __name__=='__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError) as exc:
        print('STOP:',exc,file=sys.stderr)
        raise SystemExit(1)
