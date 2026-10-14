"""Verify deployed N03 target code, manifest identity and read-only mounts."""
import hashlib
import json
import subprocess
from pathlib import Path
import prepare_m1_p1_deploy as common
import prepare_m1_p4_nr_deploy as deployment

OUT = common.ROOT / 'discovery/t01-phase1-real/m1-p4-20260922/nr-deployment-verification-r01.json'
MANIFEST = common.ROOT / 'discovery/t01-phase1-real/m1-p4-20260922/nr-manifest-r01.json'


def main():
    expected = {name: hashlib.sha256((common.ROOT / 'src/t01_phase1_real' / name).read_bytes()).hexdigest()
                for name in deployment.FILES}
    manifest_hash = json.loads(MANIFEST.read_bytes())['result']['manifest_sha256']
    code = """import hashlib,json,sys
from pathlib import Path
paths=json.load(sys.stdin)
print(json.dumps({name:hashlib.sha256(Path('/app/src/t01_phase1_real',name).read_bytes()).hexdigest()
                  for name in paths}))
"""
    mounted = common.remote(code, expected)
    assert mounted == expected
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    assert live['spec']['replicas'] == 1 and live['spec']['strategy'] == {'type': 'Recreate'}
    assert live['status'].get('observedGeneration') == live['metadata']['generation']
    assert live['status'].get('readyReplicas') == live['status'].get('updatedReplicas') == 1
    spec = live['spec']['template']['spec']
    volumes = {v['name']: v for v in spec['volumes']}
    assert volumes[deployment.VOLUME]['persistentVolumeClaim'] == dict(claimName='antigen-n03-nr', readOnly=True)
    assert volumes[deployment.NAME]['configMap']['name'] == deployment.NAME
    for container, path in (('service', deployment.SERVICE_MOUNT), ('worker-blast', deployment.WORKER_MOUNT)):
        row = next(c for c in spec['containers'] if c['name'] == container)
        mounts = [m for m in row['volumeMounts'] if m['mountPath'] == path]
        assert len(mounts) == 1
        assert mounts[0] == dict(name=deployment.VOLUME, mountPath=path,
                                 subPath=deployment.SUBPATH, readOnly=True)
    def observed(container, folder):
        script = "import hashlib,json,pathlib; p=pathlib.Path(" + repr(folder) + ")/'manifest.json'; print(json.dumps({'exists':p.is_file(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))"
        interpreter = ['python', '-B'] if container == 'service' else ['/usr/bin/python3', '-E', '-B']
        args = common.K + ['exec', 'deployment/antigen-design', '-c', container, '--',
                           *interpreter, '-c', script]
        return json.loads(subprocess.check_output(args, timeout=90))
    service = observed('service', deployment.SERVICE_MOUNT)
    worker = observed('worker-blast', deployment.WORKER_MOUNT)
    assert service == worker == dict(exists=True, sha256=manifest_hash)
    result = dict(status='P4_NR_DEPLOYED_READONLY_PASS', deployment_generation=live['metadata']['generation'],
                  mounted_code_sha256=mounted, manifest_sha256=manifest_hash,
                  service_mount=deployment.SERVICE_MOUNT, worker_mount=deployment.WORKER_MOUNT,
                  read_only=True, target_database_qualification='TARGET_DATABASE_UNREVIEWED',
                  scientific_release_gate='CLOSED', usable_for_pipeline=False,
                  production_status='NOT_DEPLOYED')
    assert not OUT.exists()
    OUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(result['status'])


if __name__ == '__main__':
    main()
