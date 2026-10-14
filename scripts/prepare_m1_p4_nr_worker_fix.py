"""Mount a BLAST worker command matching the service's nr LMDB address limit."""
import argparse
import hashlib
import json
import subprocess

import yaml

import inspect_m1_p4_n03_progress as progress
import prepare_m1_p1_deploy as common
import prepare_m1_p4_nr_lmdb_fix as previous


NAME = 'antigen-m1-p4-blast-worker-config-r01'
VOLUME = 'p4-blast-worker-config'
OUT = common.ROOT / 'deploy/m1-p4/nr-lmdb-worker-r03'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_to_roll():
    tasks=[]
    for batch in ('r08','r09'):
        row=json.loads((progress.BASE/batch/'batch.json').read_bytes())
        tasks.append(dict(batch=batch,owner=row['owner'],job_id=row['job_id']))
    rows=common.remote(progress.CODE,tasks)
    assert {r['batch'] for r in rows} == {'r08','r09'}
    assert all(r['parent_state']=='stop_requested' and r['blast_state']=='stop_requested'
        and r['cancel_marker'] and r['resident_state'] is None
        and not r['native_runtime_started'] and not r['native_runtime_finished'] for r in rows)
    active=common.idle()
    expected={job for r in rows for job in (r['parent_job_id'],r['blast_job_id'])}
    assert {r['job_id'] for r in active['active_jobs']} == expected
    assert all(r['state']=='stop_requested' for r in active['active_jobs'])
    assert active['gpu_state']['phase']=='idle'
    return rows


def changed_worker(worker, service_command):
    assert worker['version']=='0.1.0' and len(worker['commands'])==1
    old=worker['commands'][0]
    assert old['tool']=='blast' and old['memory_bytes']==previous.OLD_ADDRESS_LIMIT
    new=json.loads(json.dumps(worker))
    new['commands'][0]['memory_bytes']=previous.NEW_ADDRESS_LIMIT
    assert new['commands'][0]==service_command
    return new


def patch(live):
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    spec=live['spec']['template']['spec']
    assert next(v['configMap']['name'] for v in spec['volumes'] if v['name']=='resident-config')==previous.NEW_CONFIG
    assert not any(v['name']==VOLUME for v in spec['volumes'])
    worker=[(i,c) for i,c in enumerate(spec['containers']) if c['name']=='worker-blast']
    assert len(worker)==1
    i,c=worker[0]
    assert c['resources']['limits']['memory']=='8Gi'
    assert not any(m['mountPath']=='/opt/t01/worker.json' for m in c['volumeMounts'])
    return [dict(op='test',path='/metadata/resourceVersion',value=live['metadata']['resourceVersion']),
        dict(op='test',path='/metadata/uid',value=live['metadata']['uid']),
        dict(op='add',path=f'/spec/template/spec/containers/{i}/volumeMounts/-',
             value=dict(name=VOLUME,mountPath='/opt/t01/worker.json',subPath='worker.json',readOnly=True)),
        dict(op='add',path='/spec/template/spec/volumes/-',
             value=dict(name=VOLUME,configMap=dict(name=NAME)))]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()
    safe=safe_to_roll()
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    service=json.loads(subprocess.check_output(common.K+['get','configmap',previous.NEW_CONFIG,'-o','json']))
    service_command=json.loads(service['data']['resident.json'])['tools']['blast']['command']
    worker_raw=subprocess.check_output(common.K+['exec','deployment/antigen-design','-c','worker-blast',
        '--','cat','/opt/t01/worker.json'])
    worker=json.loads(worker_raw)
    new=changed_worker(worker,service_command)
    new_raw=json.dumps(new,sort_keys=True,separators=(',',':'))+'\n'
    operations=patch(live)
    if args.apply:
        preflight=json.loads((OUT/'preflight.json').read_bytes())
        assert preflight['deployment_resource_version']==live['metadata']['resourceVersion']
        assert preflight['old_worker_sha256']==sha(worker_raw)
        assert preflight['new_worker_sha256']==sha(new_raw.encode())
        assert yaml.safe_load((OUT/'configmap.yaml').read_text(encoding='utf-8'))['data']['worker.json']==new_raw
        subprocess.run(common.K+['create','-f',str(OUT/'configmap.yaml')],check=True)
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json',
            '--patch-file',str(OUT/'deployment.patch.json')],check=True)
        return
    cm=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),
        immutable=True,data={'worker.json':new_raw})
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'configmap.yaml').write_text(yaml.safe_dump(cm,sort_keys=False),encoding='utf-8')
    (OUT/'deployment.patch.json').write_text(json.dumps(operations,indent=2)+'\n',encoding='utf-8')
    (OUT/'preflight.json').write_text(json.dumps(dict(
        reason='Worker image command retained 8GiB virtual address limit; service had 1TiB',
        stopped_unstarted_batches=[r['batch'] for r in safe],
        old_worker_sha256=sha(worker_raw),new_worker_sha256=sha(new_raw.encode()),
        deployment_uid=live['metadata']['uid'],
        deployment_resource_version=live['metadata']['resourceVersion'],
        deployment_generation=live['metadata']['generation'],
        worker_pod_physical_memory_limit='8Gi'),indent=2)+'\n',encoding='utf-8')
    subprocess.run(common.K+['create','--dry-run=server','-f',str(OUT/'configmap.yaml')],check=True)
    subprocess.run(common.K+['patch','deployment','antigen-design','--type=json',
        '--patch-file',str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)


if __name__=='__main__':main()
