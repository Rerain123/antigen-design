"""Overlay isolation and standalone verification payload guards."""
import copy
import sys
import pytest
from t01_phase1_real.common import REPO
sys.path.insert(0,str(REPO/'scripts'))
import prepare_n13_local_rmsd as deploy
import verify_n13_local_rmsd as verify


def live():
    return dict(metadata=dict(uid='test-uid',resourceVersion='42'),spec=dict(replicas=1,strategy=dict(type='Recreate'),
        template=dict(spec=dict(volumes=[dict(name='old',configMap=dict(name='old'))],containers=[dict(name='service',
            volumeMounts=[dict(name='old',mountPath='/app/src/t01_phase1_real/'+deploy.FILES[0],subPath='old',readOnly=True),
                dict(name='database',mountPath='/var/lib/t01/databases',readOnly=True)],args=['unchanged']),
            dict(name='worker',args=['untouched'])]))))


def test_overlay_is_immutable_scoped_and_has_concurrency_fences():
    original=live();before=copy.deepcopy(original);cm,patch,rollback=deploy.render(original)
    assert original==before and cm['immutable']
    assert len(cm['binaryData'])==len(deploy.FILES)==4
    assert patch[:2]==[dict(op='test',path='/metadata/uid',value='test-uid'),
        dict(op='test',path='/metadata/resourceVersion',value='42')]
    mounts=patch[2]['value'];assert len(mounts)==5
    assert mounts[0]==before['spec']['template']['spec']['containers'][0]['volumeMounts'][1]
    assert rollback[0]['value']==mounts
    assert rollback[1]['value']==before['spec']['template']['spec']['containers'][0]['volumeMounts']


def test_overlay_refuses_non_singleton_and_existing_overlay():
    b=live();b['spec']['replicas']=2
    with pytest.raises(AssertionError):deploy.render(b)
    b=live();b['spec']['template']['spec']['volumes'].append(dict(name=deploy.NAME))
    with pytest.raises(AssertionError):deploy.render(b)


def test_verification_remote_compiles_without_task_submission():
    import ast
    tree=ast.parse(verify.REMOTE)
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in
        ('submit_sequence','submit_sequence_in_run','submit_structure','dispatch','create_run')
        and not (isinstance(n.func.value,ast.Name) and n.func.value.id=='adapter') for n in ast.walk(tree))


def test_regression_gate_requires_every_failure_to_pass(tmp_path,monkeypatch):
    monkeypatch.setattr(deploy,'EVIDENCE',tmp_path)
    (tmp_path/'full-r01.junit.xml').write_text('<testsuite><testcase classname="a" name="bad"><failure/></testcase><testcase classname="a" name="good"/></testsuite>')
    rerun=tmp_path/'utf8-recheck-r01.junit.xml'
    for content in ('<testcase classname="a" name="other"/>','<testcase classname="a" name="bad"><skipped/></testcase>'):
        rerun.write_text('<testsuite>'+content+'</testsuite>');assert not deploy.regression_passed()
    rerun.write_text('<testsuite><testcase classname="a" name="bad"/></testsuite>')
    assert deploy.regression_passed()
