"""Verify the mounted BLAST nr address-space fix without exposing configuration."""
import hashlib
import json
import subprocess

import prepare_m1_p1_deploy as common
import prepare_m1_p4_nr_lmdb_fix as fix


def main():
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    config = json.loads(subprocess.check_output(common.K + ['get', 'configmap', fix.NEW_CONFIG, '-o', 'json']))
    spec = live['spec']['template']['spec']
    assert live['status'].get('readyReplicas') == 1
    assert next(v['configMap']['name'] for v in spec['volumes'] if v['name'] == 'resident-config') == fix.NEW_CONFIG
    assert next(c['resources']['limits']['memory'] for c in spec['containers'] if c['name'] == 'worker-blast') == '8Gi'
    original = json.loads(config['data']['resident.json'])
    assert original['tools']['blast']['command']['memory_bytes'] == fix.NEW_ADDRESS_LIMIT
    mounted = common.remote("""import hashlib,json
from pathlib import Path
raw=Path('/etc/t01/resident.json').read_bytes()
value=json.loads(raw)
print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),
    'blast_address_space_bytes':value['tools']['blast']['command']['memory_bytes'],
    'blast_database_root':value['tools']['blast']['command']['environment']['T01_DATABASE_ROOT']}))
""")
    assert mounted['sha256'] == hashlib.sha256(config['data']['resident.json'].encode()).hexdigest()
    assert mounted['blast_address_space_bytes'] == fix.NEW_ADDRESS_LIMIT
    assert mounted['blast_database_root'] == '/t01/databases/blast'
    evidence = dict(status='P4_NR_LMDB_CONFIG_DEPLOYED_PASS',
                    deployment_generation=live['metadata']['generation'],
                    configmap=fix.NEW_CONFIG,
                    mounted_resident_sha256=mounted['sha256'],
                    blast_virtual_address_limit_bytes=fix.NEW_ADDRESS_LIMIT,
                    worker_pod_physical_memory_limit='8Gi',
                    scientific_release_gate='CLOSED', usable_for_pipeline=False,
                    production_status='NOT_DEPLOYED')
    out = common.ROOT / 'discovery/t01-phase1-real/m1-p4-20260922/nr-lmdb-deployment-r02.json'
    assert not out.exists()
    out.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(evidence['status'], out)


if __name__ == '__main__':
    main()
