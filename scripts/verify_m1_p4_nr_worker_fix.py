"""Verify BLAST worker and service command parity after the immutable mount rollout."""
import hashlib
import json
import subprocess

import prepare_m1_p1_deploy as common
import prepare_m1_p4_nr_lmdb_fix as previous
import prepare_m1_p4_nr_worker_fix as fix


def main():
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['status'].get('readyReplicas')==1
    spec=live['spec']['template']['spec']
    worker=next(c for c in spec['containers'] if c['name']=='worker-blast')
    assert worker['resources']['limits']['memory']=='8Gi'
    assert dict(name=fix.VOLUME,mountPath='/opt/t01/worker.json',subPath='worker.json',readOnly=True) in worker['volumeMounts']
    assert next(v['configMap']['name'] for v in spec['volumes'] if v['name']==fix.VOLUME)==fix.NAME
    service_cm=json.loads(subprocess.check_output(common.K+['get','configmap',previous.NEW_CONFIG,'-o','json']))
    service_command=json.loads(service_cm['data']['resident.json'])['tools']['blast']['command']
    worker_cm=json.loads(subprocess.check_output(common.K+['get','configmap',fix.NAME,'-o','json']))
    worker_raw=subprocess.check_output(common.K+['exec','deployment/antigen-design','-c','worker-blast',
        '--','cat','/opt/t01/worker.json'])
    assert worker_raw.decode()==worker_cm['data']['worker.json']
    worker_command=json.loads(worker_raw)['commands'][0]
    assert worker_command==service_command
    assert worker_command['memory_bytes']==previous.NEW_ADDRESS_LIMIT
    mounted=common.remote("""import hashlib,json
from pathlib import Path
raw=Path('/etc/t01/resident.json').read_bytes()
value=json.loads(raw)
print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),
    'blast_command':value['tools']['blast']['command']}))
""")
    assert mounted['blast_command']==worker_command
    value=dict(status='P4_NR_BLAST_SERVICE_WORKER_CONFIG_MATCH_PASS',
        deployment_generation=live['metadata']['generation'],
        service_configmap=previous.NEW_CONFIG,worker_configmap=fix.NAME,
        service_resident_sha256=mounted['sha256'],
        worker_config_sha256=hashlib.sha256(worker_raw).hexdigest(),
        blast_virtual_address_limit_bytes=worker_command['memory_bytes'],
        worker_pod_physical_memory_limit='8Gi',
        scientific_release_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')
    out=common.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/nr-lmdb-worker-deployment-r03.json'
    assert not out.exists()
    out.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(value['status'],out)


if __name__=='__main__':main()
