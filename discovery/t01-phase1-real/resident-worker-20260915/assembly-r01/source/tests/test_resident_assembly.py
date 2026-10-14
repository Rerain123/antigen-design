import json
from pathlib import Path

from t01_phase1_real import resident_assembly as assembly
from t01_phase1_real.resident_worker import commands_from_file


def test_batch_registry_matches_worker_commands_and_has_one_gpu_root(tmp_path):
    config=assembly.configuration()
    assert len(config['tools'])==11
    assert len(assembly.GROUPS)==9
    gpu_roots={config['tools'][t]['root'] for t in assembly.GPU}
    assert gpu_roots=={'/var/lib/t01/resident/gpu'}
    for group,tools in assembly.GROUPS.items():
        path=tmp_path/(group+'.json')
        path.write_text(json.dumps(dict(version='0.1.0',commands=[assembly.command(t).document() for t in tools])))
        registered=commands_from_file(path)
        for tool in tools:
            assert registered[tool].document()==config['tools'][tool]['command']
            env=dict(registered[tool].environment)
            assert env['T01_SOURCE_IMAGE_ID']==config['tools'][tool]['source_image_id']
            assert env['T01_PRIVATE_TMP']=='1' and env['T01_RESIDENT_OFFLINE']=='1'


def test_gpu_dependencies_stay_in_separate_prefixes():
    environments={tool:dict(assembly.command(tool).environment) for tool in assembly.GPU}
    assert 'PYTHONHOME' not in environments['proteinmpnn']
    assert environments['esm-if1']['PYTHONHOME']=='/opt/t01/env/esm-if1'
    assert environments['thermompnn']['PYTHONHOME']=='/opt/t01/env/thermompnn'
    assert len({v['T01_NATIVE_PACKAGE'] for v in environments.values()})==3
    assert environments['thermompnn']['T01_THERMOMPNN_LAYOUT']=='1'


def test_old_scientific_interpreters_are_preserved():
    assert assembly.command('aggrescan3d').argv[0]=='/opt/conda/bin/python'
    assert assembly.command('blast').argv[0]=='/usr/bin/python3'
    assert assembly.command('deeptmhmm').argv[0]=='/usr/local/bin/python'
    assert assembly.layout('structure')['/tmp']=='/run/t01-slot/tmp'
