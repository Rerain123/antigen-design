import copy
import pytest
from scripts import prepare_esmfold2_backend_r02 as deploy


def fixture():
    path='t01_phase1_real/development/esmfold2/standard.py'
    current=(deploy.ROOT/'src'/path).read_text(encoding='utf-8')
    pod=dict(containers=[dict(name='service',image=deploy.OLD_IMAGE,env=[dict(name='KEEP',value='yes')])],
             volumes=[dict(name='esmfold2-code',configMap=dict(name=deploy.OLD_CODE,items=[dict(key='code',path=path)]))])
    d=dict(metadata=dict(resourceVersion='123'),spec=dict(template=dict(spec=pod)))
    c=dict(metadata=dict(name=deploy.OLD_CODE),immutable=True,data=dict(code=current+'\n# previous revision\n'))
    return d,c


def test_patch_only_updates_image_and_code_reference():
    d,c=fixture();before=copy.deepcopy((d,c))
    code,patch=deploy.render(d,c)
    assert (d,c)==before
    assert code['immutable'] and code['metadata']['name']==deploy.NEW_CODE
    assert [x['op'] for x in patch]==['test','test','test','replace','replace']
    assert patch[0]['value']=='123'
    assert [x['path'] for x in patch if x['op']=='replace']==[
        '/spec/template/spec/containers/0/image','/spec/template/spec/volumes/0/configMap/name']


def test_refuses_drifted_deployment_and_missing_source_change():
    d,c=fixture();d['spec']['template']['spec']['containers'][0]['image']='unexpected'
    with pytest.raises(ValueError,match='Unexpected deployment'): deploy.render(d,c)
    d,c=fixture();c['data']['code']=(deploy.ROOT/'src/t01_phase1_real/development/esmfold2/standard.py').read_text(encoding='utf-8')
    with pytest.raises(ValueError,match='Expected only'): deploy.render(d,c)
