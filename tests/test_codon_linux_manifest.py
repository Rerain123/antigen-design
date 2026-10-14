import importlib.util
import json
from pathlib import Path
import zipfile
import pytest
from t01_phase1_real.common import REPO,sha,encode,RuntimeFault
from t01_phase1_real.development.codon import policy

spec=importlib.util.spec_from_file_location('codon_manifest_builder',REPO/'scripts/prepare_codon_linux_manifest.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

def test_linux_manifest_is_reproducible_from_wheels():
    value=builder.build(policy.ASSETS/'manifest.json',[REPO/'deploy/t01-phase1-real-target-v0.2/wheelhouse',REPO/'deploy/codon-linux/wheelhouse'])
    raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    assert raw==(policy.ASSETS/'manifest-linux.json').read_bytes()
    assert sha(raw)==policy.LINUX_MANIFEST_SHA256
    assert sha((policy.ASSETS/'manifest.json').read_bytes())==policy.MANIFEST_SHA256
    assert len(value['packages'])==9 and any(r['path'].endswith('.so') for r in value['packages']['numpy']['files'])

@pytest.mark.parametrize('damage',['wrong-version','missing-package','unsafe-path','windows-binary'])
def test_generator_rejects_invalid_wheel(tmp_path,damage):
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(dict(table={},packages={'demo':dict(version='1.0')})))
    if damage!='missing-package':
        with zipfile.ZipFile(tmp_path/'demo.whl','w') as z:
            z.writestr('demo-1.0.dist-info/METADATA','Name: demo\nVersion: '+('2.0' if damage=='wrong-version' else '1.0')+'\n')
            z.writestr('../escape' if damage=='unsafe-path' else 'demo/binary.pyd' if damage=='windows-binary' else 'demo.py','data')
    with pytest.raises(ValueError):builder.build(manifest,[tmp_path])

@pytest.mark.parametrize('damage',['hash','binary','version','architecture'])
def test_linux_runtime_keeps_hash_version_platform_guards(tmp_path,monkeypatch,damage):
    from test_codon_development import body
    (tmp_path/'manifest.json').write_bytes((policy.ASSETS/'manifest.json').read_bytes())
    table_raw=b'fixture';(tmp_path/'table.csv').write_bytes(table_raw)
    binary=tmp_path/'native.so';binary.write_bytes(b'fixed binary')
    manifest=dict(platform='linux-x86_64',python=[3,11],windows_manifest_sha256=policy.MANIFEST_SHA256,
        table=dict(file='table.csv',size_bytes=len(table_raw),sha256=sha(table_raw)),
        packages=dict(example=dict(version='1.0',files=[dict(path='native.so',size_bytes=12,sha256=sha(binary.read_bytes()))])))
    raw=encode(manifest);(tmp_path/'manifest-linux.json').write_bytes(raw)
    monkeypatch.setattr(policy,'ASSETS',tmp_path);monkeypatch.setattr(policy,'LINUX_MANIFEST_SHA256',sha(raw))
    monkeypatch.setattr(policy.sys,'platform','linux');monkeypatch.setattr(policy.platform,'machine',lambda:'x86_64')
    monkeypatch.setattr(policy.sysconfig,'get_paths',lambda:dict(purelib=str(tmp_path)))
    monkeypatch.setattr(policy.md,'version',lambda name:'1.0')
    assert policy.source_files(body())[1]['state']=='VERIFIED_LOCAL_TABLE_AND_DEPENDENCIES'
    if damage=='hash':(tmp_path/'manifest-linux.json').write_bytes(raw+b' ')
    elif damage=='binary':binary.write_bytes(b'other binary')
    elif damage=='version':monkeypatch.setattr(policy.md,'version',lambda name:'2.0')
    else:monkeypatch.setattr(policy.platform,'machine',lambda:'aarch64')
    with pytest.raises(RuntimeFault):policy.source_files(body())
