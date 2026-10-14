import json
import hashlib
from scripts.prepare_esmfold2_capacity import render, NAME, ROOT

def test_capacity_is_isolated_and_pins_native_sources():
    network,cm,job=render()['items']
    p=json.loads(cm['data']['profile.json']);r=json.loads(cm['data']['request.json'])
    assert p['max_sequence_length']==len(r['inputs']['sequence'])==393
    assert p['scientific_gate']=='CLOSED' and r['asset_profile_id']==p['id']
    assert json.loads((ROOT/'src/t01_phase1_real/development/esmfold2/profile.json').read_bytes())['max_sequence_length']==999
    assert cm['immutable'] and job['spec']['backoffLimit']==0 and job['spec']['activeDeadlineSeconds']==1800
    assert network['spec']['egress']==[] and network['spec']['podSelector']['matchLabels']=={'app':NAME}
    pod=job['spec']['template']['spec'];c=pod['containers'][0]
    assert pod['affinity']['podAffinity']['requiredDuringSchedulingIgnoredDuringExecution']
    assert c['resources']['limits']['nvidia.com/gpumem']==32768
    assert next(m for m in c['volumeMounts'] if m['name']=='models')['readOnly']
    # Historical capacity393-r01 retains its original native implementation.
    # New hardware observation code must not rewrite that frozen experiment.
    assert hashlib.sha256(cm['data']['run_structure.py'].encode()).hexdigest() == '8763edf2b8d08f79708680792b1ba9c4e7ecff3abc1aea1d331e6a9e0d61a21d'
    compile(cm['data']['launch.py'],'capacity-launch','exec')
    assert "root.mkdir(exist_ok=False)" in cm['data']['launch.py']
    assert '/shared/.gpu-execution.lock' in cm['data']['launch.py']
