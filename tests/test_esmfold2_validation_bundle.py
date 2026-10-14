import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def bundle():
    return list(yaml.safe_load_all((ROOT / 'deploy/esmfold2-standard/validation.r02.rancher.yaml').read_text(encoding='utf-8')))


def test_bundle_preserves_offline_profile_and_isolates_attempt():
    policy, config, job = bundle()
    pod = job['spec']['template']['spec']
    worker = pod['containers'][0]
    assert policy['spec']['podSelector']['matchLabels'] == job['spec']['template']['metadata']['labels']
    assert policy['spec']['policyTypes'] == ['Egress'] and policy['spec']['egress'] == []
    assert json.loads(config['data']['profile.json']) == json.loads((ROOT / 'deploy/esmfold2-standard/profile.server.json').read_text())
    assert config['immutable'] is True
    assert json.loads(config['data']['request.json'])['request_id'] == 'esmfold2-engineering-002'
    assert worker['args'][3] == '/runs/engineering-r02'
    assert next(v for v in pod['volumes'] if v['name'] == 'config')['configMap']['name'] == config['metadata']['name']
    assert next(v for v in worker['volumeMounts'] if v['name'] == 'models')['readOnly'] is True
    assert 'ttlSecondsAfterFinished' not in job['spec']
    assert job['spec']['backoffLimit'] == 0


@pytest.mark.parametrize('fail', [False, True])
def test_log_wrapper_preserves_arguments_and_does_not_mask_failure(tmp_path, fail):
    _, _, job = bundle()
    worker = job['spec']['template']['spec']['containers'][0]
    target = tmp_path / 'worker.py'
    target.write_text('import sys\nassert sys.argv[1:] == ' + repr(worker['args']) + '\n' +
                      ('raise RuntimeError("fixture failure")\n' if fail else 'print("FIXTURE_RAN")\n'))
    code = worker['command'][-1].replace('"/opt/t01/run_structure.py"', repr(str(target)))
    result = subprocess.run([sys.executable, '-u', '-B', '-c', code, *worker['args']], capture_output=True, text=True)
    assert 'ESMFOLD2_VALIDATION_START' in result.stdout
    assert (result.returncode != 0) == fail
    assert ('ESMFOLD2_VALIDATION_COMPLETED' in result.stdout) == (not fail)
