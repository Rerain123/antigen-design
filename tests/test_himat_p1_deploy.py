import base64
import copy
import importlib
from pathlib import Path

import pytest
from test_himat_esmfold2_path_fix import fixture


def test_overlay_targets_actual_native_import_and_keeps_unrelated_mounts(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    prep=importlib.import_module('prepare_himat_p1_fixes')
    live,old=fixture(prep.esm)
    spec=live['spec']['template']['spec']
    spec['containers'].append({'name':'service','volumeMounts':[
        {'name':'old','mountPath':'/app/src/t01_phase1_real/service_api/himat.py'},
        {'name':'runtime','mountPath':'/var/lib/t01'}]})
    before=copy.deepcopy((live,old))
    cms,patch,_=prep.render(live,old)
    assert (live,old)==before
    assert patch[3]['path']=='/spec/template/spec/volumes/0/configMap/name'
    assert patch[3]['value']==prep.esm.NEW_NAME
    mounts=next(p['value'] for p in patch if p['path'].endswith('/volumeMounts'))
    assert {'name':'runtime','mountPath':'/var/lib/t01'} in mounts
    assert len({m['mountPath'] for m in mounts})==len(mounts)
    assert all(any(m['mountPath']=='/app/src/t01_phase1_real/'+n and m['readOnly'] for m in mounts) for n in prep.FILES)
    for i,name in enumerate(prep.FILES):
        assert base64.b64decode(cms['items'][1]['binaryData']['p'+str(i)])==(prep.common.ROOT/'src/t01_phase1_real'/name).read_bytes()
    spec['volumes'].append({'name':prep.VOLUME})
    with pytest.raises(RuntimeError,match='already exists'):prep.render(live,old)


def test_representative_missing_allele_panel_stays_explicit():
    from test_m1_service_p4 import RecordedInputs
    from t01_phase1_real.development.workflow import service
    rt=RecordedInputs();rt.body['analysis']['netmhc']=None
    for name in ('wt_netmhc','rep1_netmhc'):
        assert service.request_for(rt,rt.body,rt.rows,name)==(None,'ALLELE_PANEL_NOT_PROVIDED')


@pytest.mark.parametrize('path,valid',[
    ('/backend/..2026_09_24_07_51_58.1981562796/t01_phase1_real/development/esmfold2/policy.py',True),
    ('/backend/t01_phase1_real/development/esmfold2/policy.py',True),
    ('/opt/t01/src/t01_phase1_real/development/esmfold2/policy.py',False)])
def test_actual_import_verifier_accepts_projected_configmap_path(monkeypatch,path,valid):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    verifier=importlib.import_module('verify_himat_esmfold2_path_fix')
    worker={'import_path':'/backend/t01_phase1_real/development/esmfold2/policy.py','resolved_import_path':path}
    if valid:verifier.verify_import_path(worker)
    else:
        with pytest.raises(RuntimeError):verifier.verify_import_path(worker)
    worker['import_path']='/opt/t01/src/t01_phase1_real/development/esmfold2/policy.py'
    with pytest.raises(RuntimeError):verifier.verify_import_path(worker)


def test_remote_native_replay_initializes_production_linux_storage(monkeypatch):
    import ast
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    verifier=importlib.import_module('verify_himat_p1_fixes')
    tree=ast.parse(verifier.REMOTE)
    install=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
                 and isinstance(n.value.func,ast.Name) and n.value.func.id=='install_platform_modules')
    consumer=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.ImportFrom)
                  and n.module=='t01_phase1_real.development.blast.result')
    assert install<consumer
    assert 'mode=ro' in verifier.REMOTE and 'PRAGMA query_only=ON' in verifier.REMOTE
