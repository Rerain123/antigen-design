"""Offline assembly of pinned native environments and their fixed commands.

This module builds local images only. It does not push images or alter a cluster.
"""
from pathlib import Path
import json

from .resident_process import Command

SOURCES = {
 'structure': ('t01-freesasa-g0:2.2.1-20260905','bb6c6b5ce1add12dc9bda3538a218568a9e80c048c12525fc130eaa970dbb9e5'),
 'deeptmhmm': ('t01-deeptmhmm-academic:1.0-cpu-20260905','7f85781fadf8c89ddbafced691d05006caf6881b06aa5b9bae4bd531393bcd72'),
 'bepipred': ('t01-bepipred-development:3.0-bp3-0.0.12.7-20260906','e1aff495e254ca4da513286f4ada0e1e0a071a2ffd9e0bc8ae3d2e6c91384149'),
 'netmhc': ('t01-netmhc-academic:4.2e-4.3k-20260907','c0a7239d4005484c1248b78de91bf7a76acffe0ed41f52614a54b6c20b3cf094'),
 'blast': ('ncbi/blast:2.17.0','81f118d2e4f7e11494d27fdbb99c9430423105afff50c4ae158db41d58a3fc57'),
 'homology': ('t01-homology-development:20260907','3679b2d22c59629380e47db3af59c7b4c3741e6330ab6962aa51ce526c67d32d'),
 'foldx': ('t01-foldx-development:5-academic-20260909-r02','66539e081922ce4c4fb504c9906feb64044ce668033e63fdc9299d020af8c851'),
 'aggrescan3d': ('lcbio/a3d_server:latest','c9e5a38b7d7f22c0b76678c5135ec4bf1af47cf77e8c9547a3bb4b9f7f2e938b'),
 'proteinmpnn': ('t01-proteinmpnn-development:8907e667-cu128-20260908','5b6baa8ebc5660bd3de9cf8b6d1694c7de35fadd23fea6cd7a8352a536e3f3af'),
 'esm-if1': ('t01-esm-if1-development:2b369911-cu128-20260908','926d4619df9759cd2417dcc9056b7bd648dca1d2adf15631aaad2e84a88d39cc'),
 'thermompnn': ('t01-thermompnn-development:2b04fd37-cu128-20260908','3cbd3c12b792a8b344347e6e9171d03deb7c5a115a6c4b8af27b84847dfdd847'),
}
SUPERVISOR = ('python:3.11-slim-bookworm', '528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84')
GPU = ('proteinmpnn','esm-if1','thermompnn')
GROUPS = {k:(k,) for k in SOURCES if k not in GPU}
GROUPS['gpu'] = GPU
PACKAGES = dict(deeptmhmm='deeptmhmm-academic-1.0-0a7a6c5d009e',bepipred='bepipred-3.0-98bedf2471e0',
                proteinmpnn='proteinmpnn-8907e6671bfb',thermompnn='thermompnn-2b04fd370e39',
                foldx='foldx-20270131', **{'esm-if1':'esm-if1-2b369911bb5b'})


def command(tool):
    interpreter = '/usr/bin/python3' if tool=='blast' else '/opt/conda/bin/python' if tool=='aggrescan3d' else '/usr/local/bin/python'
    worker = 'container_probe.py' if tool=='deeptmhmm' else 'developability/a3d_worker.py' if tool=='aggrescan3d' else tool.replace('-','_')+'/worker.py'
    env = dict(T01_RESIDENT_OFFLINE='1', T01_RESIDENT_SLOT='/run/t01-slot', T01_PRIVATE_TMP='1',
               T01_SOURCE_IMAGE_ID='sha256:'+SOURCES[tool][1], OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='2',
               MKL_NUM_THREADS='2', PYTHONUNBUFFERED='1', MPLCONFIGDIR='/tmp/matplotlib',
               PATH='/usr/local/bin:/usr/bin:/bin:/blast/bin:/opt/conda/bin')
    if tool in PACKAGES:
        env['T01_NATIVE_PACKAGE']='/t01/assets/'+PACKAGES[tool]
        env['T01_NATIVE_CWD']='/app'
        env['PYTHONPATH']='/app'
    if tool in ('deeptmhmm','bepipred'): env['CUDA_VISIBLE_DEVICES']='-1'
    if tool=='bepipred': env['TORCH_HOME']='/torch'
    if tool in GPU:
        env.update(CUDA_CACHE_PATH='/tmp/cuda', LD_LIBRARY_PATH='/usr/local/lib', T01_JOB_ID='{job_id}')
        if tool!='proteinmpnn': env['PYTHONHOME']='/opt/t01/env/'+tool
    if tool=='thermompnn': env.update(T01_THERMOMPNN_LAYOUT='1',WANDB_MODE='disabled',TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD='1')
    if tool in ('blast','homology'): env['T01_DATABASE_ROOT']='/t01/databases/'+tool
    if tool=='homology':
        env['PATH']='/opt/blast/bin:'+env['PATH']
        env['LD_LIBRARY_PATH']='/blast/lib'
    if tool=='aggrescan3d': env['LD_LIBRARY_PATH']='/opt/conda/lib'
    # Address-space ceilings are distinct from resident memory/container limits.
    # CUDA maps large virtual ranges; constrain physical memory on the container.
    address_gib = 256 if tool in GPU else 24 if tool in ('deeptmhmm','bepipred') else 8
    return Command(tool,(interpreter,'-B','/opt/t01/src/t01_phase1_real/development/'+worker),
                   tuple(sorted(env.items())),address_gib*1024**3)


def layout(tool):
    aliases = {'/input.json':'current/input/input.json','/input.fasta':'current/input/input.fasta',
               '/input.structure':'current/input/input.structure','/input.pdb':'current/input/input.pdb',
               '/binding.json':'current/input/binding.json','/native':'current/input/native',
               '/out':'current/output/native','/app':'package','/upstream':'upstream','/database':'database'}
    links = {k:'/run/t01-slot/'+v for k,v in aliases.items()}
    links['/code']='/opt/t01/src'
    links['/tmp']='/run/t01-slot/tmp'
    if tool in ('structure','homology'): links['/worker']='/opt/t01/src/t01_phase1_real/development/'+tool
    links['/torch/hub/checkpoints']='/t01/assets/bepipred-esm2-650m'
    return links


def dockerfile(group):
    tools = GROUPS[group]
    lines=['FROM '+SUPERVISOR[0]+' AS supervisor']
    if group=='gpu':
        lines += ['FROM '+SOURCES[t][0]+' AS '+t for t in GPU[1:]]
        lines += ['FROM '+SOURCES['proteinmpnn'][0]]
        lines += ['COPY --from='+t+' /usr/local /opt/t01/env/'+t for t in GPU[1:]]
    elif group=='aggrescan3d':
        lines += ['FROM '+SOURCES[group][0]+' AS native','FROM '+SOURCES['structure'][0],
                  'COPY --from=native /opt/conda /opt/conda']
    else: lines += ['FROM '+SOURCES[group][0]]
    lines += ['USER 0','COPY --from=supervisor /usr/local /opt/t01/supervisor',
              'COPY src /opt/t01/src','COPY profile.json /profile.json','COPY setup.py /opt/t01/setup.py',
              'COPY '+group+'.worker.json /opt/t01/worker.json',
              'ENV PYTHONHOME=/opt/t01/supervisor LD_LIBRARY_PATH=/opt/t01/supervisor/lib PYTHONPATH=/opt/t01/src PYTHONDONTWRITEBYTECODE=1',
              'RUN /opt/t01/supervisor/bin/python3.11 -B /opt/t01/setup.py '+group,
              'USER 10001:10001','WORKDIR /',
              'ENTRYPOINT ["/opt/t01/supervisor/bin/python3.11","-B","-m","t01_phase1_real.resident_worker"]',
              'CMD ["--root","/var/lib/t01/resident/'+group+'","--config","/opt/t01/worker.json"]']
    return '\n'.join(lines)+'\n'


def setup(group):
    import os
    import shutil
    slot=Path('/run/t01-slot');slot.mkdir(parents=True,exist_ok=True);os.chown(slot,10001,10001)
    root=Path('/var/lib/t01/resident/'+group);root.mkdir(parents=True,exist_ok=True);os.chown(root,10001,10001)
    for name,destination in layout(group).items():
        path=Path(name)
        if path.is_symlink(): raise ValueError('Unexpected existing alias: '+name)
        if path.exists():
            if name=='/tmp' and path.is_dir():
                # Retain original build-time leftovers in the derived image;
                # each scientific execution receives a fresh /tmp instead.
                shutil.copytree(path,'/opt/t01/source-image-tmp',symlinks=True)
                shutil.rmtree(path)  # Fixed /tmp in this new image build only.
            elif path.is_dir() and not any(path.iterdir()): path.rmdir()
            else: raise ValueError('Refusing to replace source image content: '+name)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.symlink_to(destination)


def configuration():
    return dict(version='0.1.0',runtime_volume_root='/var/lib/t01',tools={
        tool:dict(root='/var/lib/t01/resident/'+group,source_image_id='sha256:'+SOURCES[tool][1],
                  command=command(tool).document()) for group,rows in GROUPS.items() for tool in rows})
