"""Lossless N14 native storage; numerical equality uses archived real outputs."""
import copy
import pytest
from t01_phase1_real.common import encode,decode,sha
from t01_phase1_real.development.foldx import scan_batches as batches
from t01_phase1_real.development.foldx.result import result
from test_foldx_development import recording
from test_foldx_scan_batches import finalize,zipped


def packaged(tmp_path):
    job,body,files,execution=copy.deepcopy(recording('buildmodel-three-variants-five-runs'))
    folder=tmp_path/'buildmodel';folder.mkdir()
    original={n:v for n,v in files.items() if n.startswith('output/buildmodel/') and n.endswith('.pdb')}
    for name,raw in original.items():(folder/name.split('/')[-1]).write_bytes(raw)
    runtime=decode(files['output/runtime.json'])
    runtime['buildmodel_archives']=batches.seal_models(folder,3)
    for name in original:del files[name]
    for r in runtime['buildmodel_archives']:
        files['output/'+r['archive']]=(tmp_path/r['archive']).read_bytes()
    return job,body,files,execution,runtime,original


def test_archived_real_five_run_scores_and_all_pdb_bytes_identical(tmp_path):
    original=result(*recording('buildmodel-three-variants-five-runs'))
    j,b,f,e,r,models=packaged(tmp_path);finalize(f,r)
    restored={}
    for item in r['buildmodel_archives']:
        restored.update({'output/buildmodel/'+n:raw for n,raw in batches.unpack(f['output/'+item['archive']]).items()})
    assert restored==models
    fresh=result(j,b,f,e)
    assert fresh['null_reason'] is None
    assert fresh['variant_ddg']==original['variant_ddg']
    assert fresh['native_completeness']==original['native_completeness']


@pytest.mark.parametrize('damage',['hash','missing_archive','missing_run','member_hash','index','extra_archive','raw_duplicate'])
def test_damaged_native_models_cannot_publish_scores(tmp_path,damage):
    j,b,f,e,r,models=packaged(tmp_path);item=r['buildmodel_archives'][0];name='output/'+item['archive']
    if damage=='hash':item['sha256']='0'*64
    elif damage=='missing_archive':del f[name]
    elif damage=='member_hash':item['member_sha256'][next(iter(item['member_sha256']))]='0'*64
    elif damage=='index':item['index']=2
    elif damage=='extra_archive':f['output/buildmodel/batches/0004.zip']=f[name]
    elif damage=='raw_duplicate':f.update(models)
    else:
        members=batches.unpack(f[name]);members.pop(next(iter(members)));f[name]=zipped(members)
        item.update(sha256=sha(f[name]),size_bytes=len(f[name]))
    finalize(f,r);fresh=result(j,b,f,e)
    assert fresh['null_reason']=='OUTPUT_INVALID' and fresh['variant_ddg'] is None


@pytest.mark.parametrize('count',[24,40])
def test_full_pool_models_fit_unchanged_resident_inventory(tmp_path,count):
    from t01_phase1_real.resident_process import inventory
    folder=tmp_path/'output/native/buildmodel';folder.mkdir(parents=True)
    expected={}
    for i in range(1,count+1):
        for name in batches.model_names(i):
            raw=(name+'\nENGINEERING STORAGE FIXTURE\n').encode()*100
            (folder/name).write_bytes(raw);expected[name]=sha(raw)
    rows=batches.seal_models(folder,count)
    actual={}
    for r in rows:actual.update({n:sha(raw) for n,raw in batches.unpack((tmp_path/'output/native'/r['archive']).read_bytes()).items()})
    assert actual==expected and len(inventory(tmp_path))==count
