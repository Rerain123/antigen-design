import copy
import json
import pytest
from scripts import prepare_esmfold2_backend_r03 as deploy

def fixture():
    paths=['t01_phase1_real/__init__.py']+['t01_phase1_real/development/esmfold2/'+p for p in ('source.py','standard.py')]
    items=[dict(key='source-'+str(i),path=p) for i,p in enumerate(paths)]
    data={x['key']:(deploy.ROOT/'src'/x['path']).read_bytes().decode() for x in items}
    for x in items[1:]:data[x['key']]+='\n# previous revision\n'
    pod=dict(containers=[dict(name='service',image=deploy.OLD_IMAGE),dict(name='worker-structure',volumeMounts=[dict(name='runtime',mountPath='/var/lib/t01')])],volumes=[dict(name='esmfold2-code',configMap=dict(name=deploy.OLD_CODE,items=items))])
    d=dict(metadata=dict(resourceVersion='123'),spec=dict(template=dict(spec=pod)))
    c=dict(metadata=dict(name=deploy.OLD_CODE),immutable=True,data=data)
    return d,c

def test_preserves_inputs_and_synchronizes_sources():
    d,c=fixture();before=copy.deepcopy((d,c))
    code,patch=deploy.render(d,c)
    assert (d,c)==before
    assert code['immutable'] and code['metadata']['name']==deploy.NEW_CODE
    assert [p['op'] for p in patch]==['test']*4+['replace','replace','add']
    assert patch[-1]['value']['readOnly'] is True
    assert patch[-1]['value']['subPath']==deploy.WORKER
    assert {deploy.WORKER,deploy.QUALITY}<={i['path'] for i in patch[-2]['value']['items']}
    assert code['data']['r03-structure-worker']==(deploy.ROOT/'src'/deploy.WORKER).read_bytes().decode()

@pytest.mark.parametrize('damage',['image','code','source','mount'])
def test_refuses_drift(damage):
    d,c=fixture();pod=d['spec']['template']['spec']
    if damage=='image':next(x for x in pod['containers'] if x['name']=='service')['image']='wrong'
    elif damage=='code':c['immutable']=False
    elif damage=='source':c['data']['source-0']='unexpected'
    else:next(x for x in pod['containers'] if x['name']=='worker-structure')['volumeMounts'].append(dict(mountPath='/opt/t01/src/'+deploy.WORKER))
    with pytest.raises(ValueError):deploy.render(d,c)
