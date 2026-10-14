"""Independent audit rejects damaged inventories and mismatched execution snapshots."""
import importlib.util
import shutil
import sys
import pytest
from t01_phase1_real.common import REPO,decode,encode,sha
from t01_phase1_real.development.esm_if1 import policy


@pytest.fixture
def audit_case(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('n12_audit',REPO/'scripts/audit_esm_if1_evidence.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original=REPO/'discovery/t01-phase1-real/w5/esm-if1-integration-20260908/smoke-r02'
    batch=tmp_path/'batch';folder=batch/'cases/native-baseline-and24'
    shutil.copytree(original/'cases/native-baseline-and24',folder)
    for name in ('profile.json','rules.json','assets.json'):shutil.copyfile(original/name,batch/name)
    snapshot=batch/'source/scripts/audit_esm_if1_evidence.py';snapshot.parent.mkdir(parents=True)
    shutil.copyfile(REPO/'scripts/audit_esm_if1_evidence.py',snapshot)
    job=decode((folder/'job.json').read_bytes());profile=decode((batch/'profile.json').read_bytes())
    rules=decode((batch/'rules.json').read_bytes());assets=decode((batch/'assets.json').read_bytes())
    monkeypatch.setattr(policy,'registered_profile',lambda:profile)
    monkeypatch.setattr(policy,'registered_rules',lambda:rules)
    monkeypatch.setattr(policy,'verify_assets',lambda:assets)
    index=dict(status='PASS',profile=profile,guards=[],cases=[dict(case='native-baseline-and24',**{k:job[k] for k in ('job_id','state','error_code','tool_id')})])
    def inventory():
        index['files']=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
            for p in batch.rglob('*') if p.is_file() and p.name!='index.json']
        (batch/'index.json').write_bytes(encode(index))
    inventory();output=tmp_path/'audit.json'
    monkeypatch.setattr(sys,'argv',['audit','--batch',str(batch),'--output',str(output)])
    return module,batch,folder,snapshot,index,inventory,output


def test_audit_reparses_real_baseline_and_refuses_output_overwrite(audit_case):
    module,batch,folder,snapshot,index,inventory,output=audit_case
    module.main();report=decode(output.read_bytes())
    assert report['status']=='PASS' and report['baseline_origins_verified']==1
    assert report['native_results_reparsed'][0]['variant_model_calls']==24
    with pytest.raises(AssertionError):module.main()


@pytest.mark.parametrize('damage',['inventory','snapshot','profile','artifact_reference'])
def test_audit_rejects_tamper_even_when_outer_inventory_is_refreshed(audit_case,damage):
    module,batch,folder,snapshot,index,inventory,output=audit_case
    if damage=='inventory':
        with (folder/'result.json').open('ab') as stream:stream.write(b' ')
    elif damage=='snapshot':
        snapshot.write_bytes(b'changed source');inventory()
    elif damage=='profile':
        index['profile']=dict(index['profile'],sha256='0'*64);inventory()
    else:
        job=decode((folder/'job.json').read_bytes());job['artifacts'][0]['sha256']='0'*64
        (folder/'job.json').write_bytes(encode(job));inventory()
    with pytest.raises(AssertionError):module.main()
    assert not output.exists()
