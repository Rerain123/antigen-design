import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_m1_p4_nr_lmdb_fix as fix


def test_only_blast_virtual_address_limit_changes():
    resident = {'tools': {
        'blast': {'command': {'memory_bytes': fix.OLD_ADDRESS_LIMIT,
                              'environment': {'T01_DATABASE_ROOT': '/t01/databases/blast'}}},
        'foldx': {'command': {'memory_bytes': 123}},
    }}
    data = {name: '{}' for name in ('af3.worker.json', 'esmfold2.worker.json',
                                    'gpu.worker.json', 'unified-gpu.json')}
    data['resident.json'] = json.dumps(resident)
    old = {'immutable': True, 'data': data}
    changed = fix.changed_config(old)
    assert old['data']['resident.json'] == json.dumps(resident)
    assert changed['resident.json'] != old['data']['resident.json']
    assert json.loads(changed['resident.json'])['tools']['blast']['command']['memory_bytes'] == fix.NEW_ADDRESS_LIMIT
    assert json.loads(changed['resident.json'])['tools']['foldx'] == resident['tools']['foldx']


def test_deployment_patch_only_switches_immutable_config_reference():
    live = {'metadata': {'resourceVersion': '2', 'uid': 'u'},
            'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'},
                     'template': {'spec': {
                         'containers': [{'name': 'worker-blast', 'resources': {'limits': {'memory': '8Gi'}}}],
                         'volumes': [{'name': 'other'},
                                     {'name': 'resident-config', 'configMap': {'name': fix.OLD_CONFIG}}]}}}}
    operations = fix.patch(live)
    assert operations[-1] == {'op': 'replace',
                              'path': '/spec/template/spec/volumes/1/configMap/name',
                              'value': fix.NEW_CONFIG}
    live['spec']['template']['spec']['containers'][0]['resources']['limits']['memory'] = '16Gi'
    with pytest.raises(AssertionError):
        fix.patch(live)
