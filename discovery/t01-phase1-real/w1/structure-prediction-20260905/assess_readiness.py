"""Recompute source/asset/resource facts. Never load a scientific model."""
import ast
import json
from pathlib import Path
import tomllib

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]
OFFICIAL = BATCH/'official_sources'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checkpoint(metadata):
    rows = [row for row in metadata['siblings'] if row['rfilename'].endswith('.safetensors')]
    require(rows, 'Missing checkpoint inventory')
    seen = set()
    result = []
    for row in rows:
        name = row['rfilename']
        require(name not in seen and '/' not in name and '\\' not in name, 'Unsafe or duplicate checkpoint name')
        seen.add(name)
        lfs = row.get('lfs') or {}
        require(isinstance(lfs.get('sha256'), str) and len(lfs['sha256']) == 64 and all(c in '0123456789abcdef' for c in lfs['sha256']), 'Missing remote content hash')
        require(type(row.get('size')) is int and row['size'] > 0 and row['size'] == lfs.get('size'), 'Invalid checkpoint size')
        result.append(dict(filename=name, bytes=row['size'], remote_sha256=lfs['sha256'], local_bytes_verified=False))
    return result


def compare_release(old_metadata, new_metadata, old_config, new_config):
    def identity(metadata):
        return {r['filename']:(r['bytes'],r['remote_sha256']) for r in checkpoint(metadata)}
    return dict(may_revision=old_metadata['sha'], current_revision=new_metadata['sha'],
                checkpoint_metadata_equal=identity(old_metadata)==identity(new_metadata),
                config_equal=old_config==new_config,
                scope='REMOTE_METADATA_COMPARISON_ONLY; no local weight verification or runtime equivalence')


def parameter_memory(backbone_parameters, fold_parameters, gpu_bytes):
    require(all(type(x) is int and x > 0 for x in (backbone_parameters,fold_parameters,gpu_bytes)), 'Invalid resource input')
    # Source loader defaults to ESMC bf16; fold checkpoint is float32.
    estimated = backbone_parameters*2 + fold_parameters*4
    return dict(esm_backbone_dtype='bf16',fold_checkpoint_dtype='float32',
                estimated_parameter_bytes=estimated,gpu_total_bytes=gpu_bytes,
                exceeds_total_gpu_even_before_activations=estimated>gpu_bytes,
                scope='Checkpoint-parameter estimate; excludes activations/allocator/CCD and does not measure an actual OOM')


def fold_defaults(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node,ast.FunctionDef) and node.name=='fold':
            return {arg.arg:ast.literal_eval(value) for arg,value in zip(node.args.kwonlyargs,node.args.kw_defaults) if value is not None}
    raise ValueError('No fold entry point')


def derive():
    environment = read(BATCH/'environment.json')
    gpu = read(BATCH/'gpu_visibility.json')
    require(gpu['exit_code']==0 and gpu['model_execution']=='NOT_RUN','Unexpected GPU visibility probe')
    gpu_name,gpu_memory,driver,capability = [s.strip() for s in gpu['stdout'].strip().split(',')]
    gpu_bytes = int(gpu_memory.split()[0])*1024**2
    docker = next(r for r in environment['observations'] if 'info' in r['command'])
    docker_info = json.loads(docker['stdout'])
    os_info = json.loads(next(r['stdout'] for r in environment['observations'] if 'Win32_OperatingSystem' in ' '.join(r['command'])))
    models = {}
    backbone = read(OFFICIAL/'hf/ESMC-6B/metadata.json')
    for name in ['ESMFold2','ESMFold2-Fast']:
        current = read(OFFICIAL/'hf'/name/'metadata.json')
        may = read(OFFICIAL/'hf'/name/'may-metadata.json')
        config = read(OFFICIAL/'hf'/name/'config.json')
        may_config = read(OFFICIAL/'hf'/name/'may-config.json')
        models[name] = dict(repository='biohub/'+name,public_gated=current['gated'],
                           identity=compare_release(may,current,may_config,config),
                           checkpoint=checkpoint(current),backbone_repository=config['esmc_id'],
                           msa_encoder_enabled=config['msa_encoder']['enabled'],
                           memory=parameter_memory(backbone['safetensors']['total'],current['safetensors']['total'],gpu_bytes))
    ccd = next(r for r in read(OFFICIAL/'hf/ESMFold2/metadata.json')['siblings'] if r['rfilename']=='ccd.pkl')
    ccd_may = next(r for r in read(OFFICIAL/'hf/ESMFold2/may-metadata.json')['siblings'] if r['rfilename']=='ccd.pkl')
    esm_project = tomllib.loads((OFFICIAL/'esm/pyproject.toml').read_text())['project']
    defaults = fold_defaults((OFFICIAL/'esm/esm/models/esmfold2/processor.py').read_text())
    backbone_files = checkpoint(backbone)
    total = {name:sum(f['bytes'] for f in models[name]['checkpoint']+backbone_files)+ccd['size'] for name in models}
    af3_readme = (OFFICIAL/'af3/README.md.txt').read_text()
    require('https://storage.googleapis.com/alphafold3/af3.bin.zst' in af3_readme,'Unverified AF3 parameter URL')
    usage = read(ROOT/'docs/project/sources/PHASE1_W1_STRUCTURE_ASSET_AVAILABILITY_20260905.json')
    require(usage['exact_user_reply']=='暂无','Asset user fact drift')
    return dict(status='PREPARATION_COMPLETE_EXECUTION_NOT_READY',model_execution='NOT_RUN',production_status='NOT_DEPLOYED',
        user_assets='NONE_PROVIDED',
        local_profile=dict(gpu=gpu_name,gpu_total_bytes=gpu_bytes,driver=driver,compute_capability=capability,
                           host_ram_bytes=os_info['TotalVisibleMemorySize']*1024,docker_ram_bytes=docker_info['memory_bytes'],
                           disk_d_free_bytes=environment['disks']['D:/']['free'],gpu_container_visible=True,
                           framework_kernel_compatibility='NOT_TESTED'),
        af3=dict(source_commit=read(OFFICIAL/'af3/commit.json')['sha'],version_policy='EXPERT_UNPINNED; lock actual deployment commit',
                 parameter_source='https://storage.googleapis.com/alphafold3/af3.bin.zst',
                 parameter_header=read(BATCH/'af3_weight_header.json'),
                 license='Source Apache-2.0; separate model/output terms, organization/use applicability not confirmed',
                 weights_downloaded=False,full_database_documented_download_bytes_approx=252*10**9,
                 full_database_documented_unpacked_bytes_approx=630*10**9,
                 disk_headroom_after_documented_unpacked_bytes=environment['disks']['D:/']['free']-630*10**9,
                 recommended_host_ram_bytes=64*10**9,
                 disposition='FULL_PIPELINE_NOT_READY; separate approved local data preparation and GPU inference possible',
                 full_database_not_required_for='Inference-only with authentic precomputed MSA/template inputs; not MSA-free substitution'),
        esmfold2=dict(source_commit=read(OFFICIAL/'esm/commit.json')['sha'],source_package_version=esm_project['version'],
                      requires_python=esm_project['requires-python'],may_source_commit=read(OFFICIAL/'esm/may-commits.json')[0]['sha'],
                      version_policy='Expert May 2026 family identified; variant and deployment runtime still to freeze',
                      models=models,backbone=dict(repository='biohub/ESMC-6B',revision=backbone['sha'],files=backbone_files),
                      ccd=dict(repository='biohub/ESMFold2',filename='ccd.pkl',bytes=ccd['size'],remote_sha256=ccd['lfs']['sha256'],
                               may_current_metadata_equal=ccd['lfs']==ccd_may['lfs'],local_bytes_verified=False),
                      essential_download_bytes_excluding_small_metadata=total,fold_wrapper_defaults=defaults,
                      plddt_source_fact='Model raw API [0,1]; confirm per-field export scale with real outputs before production',
                      ptm_source_fact='Scalar supported by current processor; runtime evidence NOT_RUN',
                      disposition='DEFAULT_CORESIDENT_GPU_PROFILE_EXCEEDS_LAPTOP_MEMORY_ESTIMATE; needs suitable GPU or separately validated offload profile'),
        next_actions=['Obtain a concrete target hardware/storage profile',
                      'Confirm AF3 model/output terms applicability before obtaining/using weights',
                      'Pin ESMFold2 variant, code, dependencies, backbone and CCD before scoped download',
                      'Stage local AF3 MSA/template assets or authentic precomputed data; no online query fallback',
                      'Run prepared short inputs offline, then actual output validation and scientific G1 review'])


if __name__=='__main__':
    target = BATCH/'readiness.json'
    require(not target.exists(),'Preserve existing assessment')
    result = derive()
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k in ['status','model_execution','production_status','local_profile']}))
