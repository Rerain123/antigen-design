import hashlib
import json
from pathlib import Path

import pytest
import yaml

from scripts.collect_esmfold2_r03 import REQUIRED, validate


def fixture():
    files = {n: b'{}' for n in REQUIRED}
    files['structure.cif'] = b'data_fixture\n'
    files['result.json'] = json.dumps({'request_id': 'esmfold2-engineering-003',
        'status': 'predicted_engineering_unreviewed', 'scientific_gate': 'CLOSED',
        'usable_for_pipeline': False, 'structure': {'sha256': hashlib.sha256(files['structure.cif']).hexdigest()}}).encode()
    files['manifest.json'] = json.dumps({'files': [{'path': n, 'size_bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest()} for n,v in files.items()]}).encode()
    return files


def test_verified_bundle():
    assert validate(fixture())['scientific_gate'] == 'CLOSED'

def test_explicit_capacity_identity_does_not_relax_default():
    files=fixture()
    result=json.loads(files['result.json']);result['request_id']='antigen-esmfold2-capacity393-r01'
    files['result.json']=json.dumps(result).encode()
    files['manifest.json']=json.dumps({'files':[{'path':n,'size_bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in files.items() if n!='manifest.json']}).encode()
    with pytest.raises(ValueError,match='identity'):validate(files)
    assert validate(files,expected_request_id=result['request_id'])['request_id']==result['request_id']


def test_changed_bytes_rejected():
    files = fixture()
    files['structure.cif'] += b'corrupt'
    with pytest.raises(ValueError, match='integrity'):
        validate(files)


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'dir\\escape'])
def test_unsafe_manifest_path_rejected(name):
    files = fixture()
    manifest = json.loads(files['manifest.json'])
    manifest['files'][0]['path'] = name
    files['manifest.json'] = json.dumps(manifest).encode()
    with pytest.raises(ValueError, match='Unsafe'):
        validate(files)


def test_reader_is_read_only_without_gpu_or_models():
    pod = yaml.safe_load((Path(__file__).resolve().parents[1] / 'deploy/esmfold2-standard/results-reader.r03.yaml').read_text())
    container = pod['spec']['containers'][0]
    assert container['volumeMounts'] == [{'name': 'runtime', 'mountPath': '/runs', 'readOnly': True}]
    assert pod['spec']['volumes'][0]['persistentVolumeClaim']['readOnly'] is True
    assert 'nvidia.com/gpu' not in container['resources']['limits']
