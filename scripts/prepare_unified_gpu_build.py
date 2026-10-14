"""Server-side zero-GPU assembly from already-qualified immutable environments."""
from pathlib import Path
import yaml

from prepare_af3_environment_build import documents as base_documents
from prepare_unified_gpu_inspection import IMAGES

ROOT = Path(__file__).resolve().parents[1]
NAME = 'antigen-unified-gpu-build-r04'
DESTINATION = 'harbor-core.base.svc.cluster.local/qcyz/antigen-unified-gpu:resident-r04'
# Reuse only the rootless builder cache from the stopped r01 candidate. The
# scientific image output is new and has a new tag; no runtime data is reused.
CACHE = 'antigen-unified-gpu-build-cache-r01'

DOCKERFILE = f'''FROM {IMAGES['gpu']} AS gpu
FROM {IMAGES['esmfold2']} AS esmfold2
FROM {IMAGES['af3']}
USER 0
WORKDIR /
COPY --from=gpu /opt/t01 /opt/t01
COPY --from=gpu /usr/local /opt/t01/env/proteinmpnn
COPY --from=esmfold2 /usr/local /opt/t01/env/esmfold2
COPY setup.py /opt/t01/unified-setup.py
RUN /opt/t01/env/proteinmpnn/bin/python3.10 -B /opt/t01/unified-setup.py
ENV PYTHONHOME=/opt/t01/supervisor LD_LIBRARY_PATH=/opt/t01/supervisor/lib PYTHONPATH=/opt/t01/src PYTHONDONTWRITEBYTECODE=1
RUN /opt/t01/supervisor/bin/python3.11 -B -c "import ssl, ctypes, sqlite3; print('SUPERVISOR_IMPORT_PASS')"
USER 10001:10001
ENTRYPOINT ["/opt/t01/supervisor/bin/python3.11", "-u", "-B", "-m", "t01_phase1_real.unified_gpu_worker"]
CMD ["--config", "/etc/t01/unified-gpu.json"]
'''

# These operations affect only the fresh derived image, never a mounted asset.
# AF3's editable source path remains /app/alphafold when its slot is selected.
SETUP = '''from pathlib import Path
import os
import shutil
app=Path('/app')
if not (app/'alphafold/run_alphafold.py').is_file(): raise RuntimeError('AF3 source layout differs')
shutil.copytree(app, '/opt/t01/af3-app', symlinks=True)
if not Path('/opt/t01/af3-app/alphafold/run_alphafold.py').is_file(): raise RuntimeError('AF3 source copy failed')
shutil.rmtree(app)
slot=Path('/run/t01-slot'); slot.mkdir(parents=True,exist_ok=True)
os.chown(slot,10001,10001)
(slot/'package').symlink_to('/opt/t01/af3-app')
aliases={'/app':'package','/input.json':'current/input/input.json','/input.fasta':'current/input/input.fasta',
 '/input.structure':'current/input/input.structure','/input.pdb':'current/input/input.pdb',
 '/binding.json':'current/input/binding.json','/native':'current/input/native','/out':'current/output/native',
 '/upstream':'upstream','/database':'database'}
for name,target in aliases.items():
 p=Path(name)
 if p.exists() or p.is_symlink(): raise RuntimeError('Unexpected alias collision: '+name)
 p.symlink_to(slot/target)
# GPU tools retain their existing per-execution temporary directory convention.
shutil.copytree('/tmp', '/opt/t01/unified-build-tmp', symlinks=True)
shutil.rmtree('/tmp')
Path('/tmp').symlink_to(slot/'tmp')
(slot/'tmp').symlink_to('/opt/t01/unified-build-tmp')
print('UNIFIED_ENV_LAYOUT_READY')
'''


def documents():
    config, policy, pvc, job = base_documents()
    old = config['metadata']['name']
    # Mechanical identity substitution in the known build template, not shell text.
    for doc in (config, policy, job):
        doc['metadata']['name'] = NAME
    config['data'] = {'buildkitd.toml': config['data']['buildkitd.toml'],
                      'Dockerfile': DOCKERFILE, 'setup.py': SETUP}
    policy['spec']['podSelector']['matchLabels']['app'] = NAME
    pvc['metadata']['name'] = CACHE
    pvc['spec']['resources']['requests']['storage'] = '100Gi'
    template = job['spec']['template']
    template['metadata']['labels']['app'] = NAME
    pod = template['spec']
    pod.pop('initContainers')
    for vol in pod['volumes']:
        if vol['name'] == 'config': vol['configMap']['name'] = NAME
        if vol['name'] == 'state': vol['persistentVolumeClaim']['claimName'] = CACHE
    builder = pod['containers'][0]
    builder['volumeMounts'].append(dict(name='config', mountPath='/context', readOnly=True))
    builder['command'] = ['/bin/sh','-ec',f'''umask 077
echo UNIFIED_GPU_BUILD_START
buildctl-daemonless.sh build --frontend dockerfile.v0 --local context=/context --local dockerfile=/context --opt filename=Dockerfile --opt platform=linux/amd64 --output type=image,name={DESTINATION},push=true --metadata-file /workspace/build-metadata.json
echo UNIFIED_GPU_BUILD_PUSHED
cat /workspace/build-metadata.json
''']
    assert old not in yaml.safe_dump_all([config,policy,pvc,job])
    return [config, policy, pvc, job]


if __name__ == '__main__':
    output = ROOT / 'deploy/single-gpu/environment-build.r04.yaml'
    output.write_text(yaml.safe_dump_all(documents(), sort_keys=False), encoding='utf-8')
    print(output)
