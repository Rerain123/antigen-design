"""BLAST worker deployment must match the service command without changing its Pod limit."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_m1_p4_nr_worker_fix as fix


def test_worker_command_must_match_service_exactly():
    old={'version':'0.1.0','commands':[{'tool':'blast','argv':['/worker'],
        'environment':{'T01_DATABASE_ROOT':'/t01/databases/blast'},
        'memory_bytes':fix.previous.OLD_ADDRESS_LIMIT}]}
    expected=dict(old['commands'][0],memory_bytes=fix.previous.NEW_ADDRESS_LIMIT)
    changed=fix.changed_worker(old,expected)
    assert changed['commands']==[expected]
    assert old['commands'][0]['memory_bytes']==fix.previous.OLD_ADDRESS_LIMIT
    with pytest.raises(AssertionError):
        fix.changed_worker(old,dict(expected,argv=['/different']))


def test_patch_mounts_only_worker_command_and_keeps_pod_limit():
    live={'metadata':{'resourceVersion':'r','uid':'u'},
        'spec':{'replicas':1,'strategy':{'type':'Recreate'},'template':{'spec':{
            'containers':[{'name':'service','volumeMounts':[]},
                {'name':'worker-blast','resources':{'limits':{'memory':'8Gi'}},'volumeMounts':[]}],
            'volumes':[{'name':'resident-config','configMap':{'name':fix.previous.NEW_CONFIG}}]}}}}
    ops=fix.patch(live)
    assert ops[2]['path']=='/spec/template/spec/containers/1/volumeMounts/-'
    assert ops[2]['value']=={'name':fix.VOLUME,'mountPath':'/opt/t01/worker.json',
        'subPath':'worker.json','readOnly':True}
    assert ops[3]['value']=={'name':fix.VOLUME,'configMap':{'name':fix.NAME}}
    assert live['spec']['template']['spec']['containers'][1]['resources']['limits']['memory']=='8Gi'
