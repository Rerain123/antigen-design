import importlib.util
from pathlib import Path


def module():
    path = Path(__file__).parents[1] / 'scripts/prepare_resident_compatibility_deploy.py'
    spec = importlib.util.spec_from_file_location('resident_compatibility_deploy', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_service_overlay_contains_source_aware_structure_validator():
    value = module()
    configmap = value.service_configmap('him-ws')
    key = 'af3-development--structure--result.py'
    assert configmap['metadata']['name'] == 'antigen-af3-service-code-r07'
    assert configmap['immutable'] is True
    assert key in configmap['data']
    assert 'verified_prediction_quality' in configmap['data'][key]
    assert "source=prediction_source" in configmap['data'][key]


def test_service_patch_mounts_structure_validator_at_import_path():
    value = module()
    template = {'spec': {'containers': [
        {'name': 'service', 'volumeMounts': []},
    ], 'volumes': []}}
    value.replace_service_overlay(template)
    service = template['spec']['containers'][0]
    mount = next(row for row in service['volumeMounts']
                 if row['mountPath'].endswith('/development/structure/result.py'))
    assert mount['name'] == 'af3-service-code'
    assert mount['subPath'] == 'af3-development--structure--result.py'
    assert template['spec']['volumes'][-1]['configMap']['name'] == 'antigen-af3-service-code-r07'
