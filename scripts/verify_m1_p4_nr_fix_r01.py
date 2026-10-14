"""Verify the complete live P4 BLAST fix deployment."""
import hashlib
import json
import subprocess

import prepare_m1_p1_deploy as common


ROOT = common.ROOT
BASE = ROOT / 'discovery/t01-phase1-real/m1-p4-20260922'
OUT = BASE / 'nr-fix-deployment-r01.json'
MANIFEST = BASE / 'nr-manifest-r01.json'
SERVICE_PATHS = {
    'development/blast/policy.py': '/app/src/t01_phase1_real/development/blast/policy.py',
    'development/blast/prebuilt.py': '/app/src/t01_phase1_real/development/blast/prebuilt.py',
    'resident_process.py': '/app/src/t01_phase1_real/resident_process.py',
}
WORKER_NAME = 'development/blast/worker.py'
WORKER_PATH = '/opt/t01/src/t01_phase1_real/development/blast/worker.py'


def remote(container, code):
    interpreter = 'python' if container == 'service' else '/usr/bin/python3'
    raw = subprocess.check_output(common.K + ['exec', 'deployment/antigen-design', '-c', container,
                                               '--', interpreter, '-E', '-B', '-c', code], timeout=120)
    return json.loads(raw)


def main():
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    assert live['spec']['replicas'] == 1 and live['spec']['strategy'] == {'type': 'Recreate'}
    assert live['status']['observedGeneration'] == live['metadata']['generation']
    assert live['status']['readyReplicas'] == live['status']['updatedReplicas'] == 1
    spec = live['spec']['template']['spec']
    containers = {c['name']: c for c in spec['containers']}
    worker = containers['worker-blast']
    assert worker['resources']['limits'] == {'cpu': '4', 'memory': '16Gi'}
    mounts = {name: {m['mountPath']: m for m in containers[name]['volumeMounts']}
              for name in ('service', 'worker-blast')}
    assert mounts['service']['/var/lib/t01/m1-p1-test-data/blast/nr-20250624']['readOnly']
    assert mounts['worker-blast']['/t01/databases/blast/nr-20250624']['readOnly']
    assert mounts['worker-blast']['/blast/bin/blastp']['readOnly']
    assert mounts['service']['/app/src/t01_phase1_real/development/blast/policy.py']['name'] == 'p4-nr-fixes'
    assert mounts['worker-blast'][WORKER_PATH]['name'] == 'p4-nr-fixes'
    volume = next(v for v in spec['volumes'] if v['name'] == 'p4-nr-fixes')
    assert volume['configMap']['name'] == 'antigen-m1-p4-nr-fix-r01'
    target = next(v for v in spec['volumes'] if v['name'] == 'n03-nr-target')
    assert target['persistentVolumeClaim'] == {'claimName': 'antigen-n03-nr', 'readOnly': True}
    expected = {name: hashlib.sha256((ROOT / 'src/t01_phase1_real' / name).read_bytes()).hexdigest()
                for name in (*SERVICE_PATHS, WORKER_NAME)}
    service_code = 'import hashlib,json;from pathlib import Path;ps=' + repr(SERVICE_PATHS) + ';print(json.dumps({n:hashlib.sha256(Path(p).read_bytes()).hexdigest() for n,p in ps.items()}))'
    observed_service = remote('service', service_code)
    worker_code = 'import hashlib,json;from pathlib import Path;print(json.dumps({"development/blast/worker.py":hashlib.sha256(Path(' + repr(WORKER_PATH) + ').read_bytes()).hexdigest()}))'
    observed_worker = remote('worker-blast', worker_code)
    assert observed_service == {name: expected[name] for name in SERVICE_PATHS}
    assert observed_worker == {WORKER_NAME: expected[WORKER_NAME]}
    resident = remote('service', 'import json;from pathlib import Path;d=json.loads(Path("/etc/t01/resident.json").read_bytes());print(json.dumps(d["tools"]["blast"]["command"]))')
    assert resident['memory_bytes'] == 1024 ** 4
    worker_json = remote('worker-blast', 'import json;from pathlib import Path;print(Path("/opt/t01/worker.json").read_text())')
    assert worker_json['commands'][0]['memory_bytes'] == 1024 ** 4
    wrapper = remote('worker-blast', 'import json;from pathlib import Path;p=Path("/blast/bin/blastp");print(json.dumps({"real":Path("/blast/bin/blastp.REAL").is_file(),"wrapper":p.read_text()}))')
    assert wrapper == {'real': True, 'wrapper': '#!/bin/sh\nexec /blast/bin/blastp.REAL "$@"\n'}
    manifest_hash = json.loads(MANIFEST.read_bytes())['result']['manifest_sha256']
    observed_manifest = remote('service', 'import hashlib,json;from pathlib import Path;p=Path("/var/lib/t01/m1-p1-test-data/blast/nr-20250624/manifest.json");print(json.dumps({"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}))')
    assert observed_manifest == {'sha256': manifest_hash}
    result = {
        'status': 'P4_NR_FIX_DEPLOYED_PASS',
        'deployment_generation': live['metadata']['generation'],
        'source_hashes': expected,
        'mounted_code_hashes': {**observed_service, **observed_worker},
        'worker_limits': worker['resources']['limits'],
        'resident_blast_memory_bytes': resident['memory_bytes'],
        'worker_blast_memory_bytes': worker_json['commands'][0]['memory_bytes'],
        'direct_blast_binary': wrapper,
        'manifest_sha256': manifest_hash,
        'target_mount_read_only': True,
        'scientific_release_gate': 'CLOSED',
        'usable_for_pipeline': False,
        'production_status': 'NOT_DEPLOYED',
    }
    assert not OUT.exists()
    OUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(result['status'])


if __name__ == '__main__':
    main()

