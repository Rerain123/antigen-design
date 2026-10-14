"""Source/asset/plan checks; no model download or scientific inference."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT/'discovery/t01-phase1-real/w1/structure-prediction-20260905'


def load(name):
    spec = importlib.util.spec_from_file_location('prediction_'+name,BATCH/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_snapshot_does_not_claim_model_execution():
    result = load('verify_evidence').verify()
    assert result['model_execution']=='NOT_RUN'
    assert result['expert_sources_unchanged']==22
    assert result['prepared_cases']==5


def test_may_model_identity_separate_from_runtime_and_local_availability():
    result = load('assess_readiness').derive()
    models = result['esmfold2']['models']
    for model in models.values():
        assert model['identity']['checkpoint_metadata_equal']
        assert model['identity']['config_equal']
        assert model['checkpoint'][0]['local_bytes_verified'] is False
    assert models['ESMFold2']['msa_encoder_enabled'] is True
    assert models['ESMFold2-Fast']['msa_encoder_enabled'] is False
    assert models['ESMFold2']['checkpoint'] != models['ESMFold2-Fast']['checkpoint']


def test_backbone_and_ccd_are_included_in_asset_budget():
    result = load('assess_readiness').derive()['esmfold2']
    assert len(result['backbone']['files'])==6
    assert result['ccd']['bytes']==417306584
    for model,total in result['essential_download_bytes_excluding_small_metadata'].items():
        assert total > 26*10**9
        assert total == sum(r['bytes'] for r in result['backbone']['files']+result['models'][model]['checkpoint'])+result['ccd']['bytes']


def test_default_memory_is_estimate_not_actual_oom():
    result = load('assess_readiness').derive()
    for model in result['esmfold2']['models'].values():
        assert model['memory']['exceeds_total_gpu_even_before_activations']
        assert 'estimate' in model['memory']['scope']
    assert result['local_profile']['framework_kernel_compatibility']=='NOT_TESTED'
    assert result['model_execution']=='NOT_RUN'


@pytest.mark.parametrize('values',[(0,1,2),(1,-1,2),(1,1,0),(True,1,2),(1,1,1.5)])
def test_invalid_resource_values_rejected(values):
    with pytest.raises(ValueError):
        load('assess_readiness').parameter_memory(*values)


def test_checkpoint_change_is_detected_without_equating_release_names():
    audit = load('assess_readiness')
    metadata = json.loads((BATCH/'official_sources/hf/ESMFold2/metadata.json').read_text())
    changed = copy.deepcopy(metadata)
    next(r for r in changed['siblings'] if r['rfilename']=='model.safetensors')['lfs']['sha256']='0'*64
    assert not audit.compare_release(metadata,changed,{}, {})['checkpoint_metadata_equal']
    assert not audit.compare_release(metadata,metadata,{'a':1},{'a':2})['config_equal']


@pytest.mark.parametrize('mode',['missing_hash','wrong_size','duplicate','unsafe_path','empty'])
def test_invalid_remote_model_inventory_is_rejected(mode):
    audit = load('assess_readiness')
    data = {'siblings':[dict(rfilename='model.safetensors',size=10,lfs=dict(size=10,sha256='a'*64))]}
    row = data['siblings'][0]
    if mode=='missing_hash': row['lfs'].pop('sha256')
    if mode=='wrong_size': row['size']=11
    if mode=='duplicate': data['siblings'].append(copy.deepcopy(row))
    if mode=='unsafe_path': row['rfilename']='../model.safetensors'
    if mode=='empty': data['siblings']=[]
    with pytest.raises(ValueError): audit.checkpoint(data)


def test_actual_fold_defaults_do_not_come_from_example_or_checkpoint_config():
    audit = load('assess_readiness')
    result = audit.derive()['esmfold2']['fold_wrapper_defaults']
    assert (result['num_loops'],result['num_sampling_steps'],result['num_diffusion_samples'])==(20,200,1)
    assert result['lm_dropout']==0.3
    assert result['seed'] is None
    with pytest.raises(ValueError): audit.fold_defaults('x=1')


def test_af3_prepared_msa_fields_are_not_silently_emptied():
    data = json.loads((BATCH/'validation/af3_full_pipeline_input.json').read_text())
    protein = data['sequences'][0]['protein']
    assert set(protein)=={'id','sequence'}
    assert len(protein['sequence'])==76
    plan = json.loads((BATCH/'validation/plan.json').read_text())
    assert all(c['execution_status']=='DECLARED_NOT_RUN' for c in plan['cases'])


def test_evidence_tampering_and_path_escape_are_detected(tmp_path):
    verifier = load('verify_evidence')
    (tmp_path/'x.txt').write_bytes(b'bad')
    with pytest.raises(ValueError,match='hash mismatch'):
        verifier.verify_files(tmp_path,[dict(path='x.txt',bytes=3,sha256='0'*64)])
    with pytest.raises(ValueError,match='Unsafe'):
        verifier.verify_files(tmp_path,[dict(path='../x.txt',bytes=3,sha256='0'*64)])
