"""Audit rejects changed bytes and escaping paths before reporting success."""
import importlib.util
from pathlib import Path
import sys
import pytest
from t01_phase1_real.common import REPO,encode,sha,decode

def module():
    spec=importlib.util.spec_from_file_location('variant_evidence_audit',REPO/'scripts/audit_variant_report_evidence.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

@pytest.mark.parametrize('kind',['hash','size','escape'])
def test_corrupt_manifest_never_writes_pass(tmp_path,monkeypatch,kind):
    batch=tmp_path/'batch';batch.mkdir();raw=b'original';(batch/'probe.bin').write_bytes(raw)
    item=dict(path='probe.bin',bytes=len(raw),sha256=sha(raw))
    if kind=='hash':item['sha256']='0'*64
    if kind=='size':item['bytes']+=1
    if kind=='escape':item['path']='../outside.bin';(tmp_path/'outside.bin').write_bytes(raw)
    (batch/'index.json').write_bytes(encode(dict(status='PASS',files=[item])))
    output=tmp_path/'audit.json';monkeypatch.setattr(sys,'argv',['audit','--batch',str(batch),'--output',str(output)])
    with pytest.raises(AssertionError):module().main()
    assert not output.exists()

def test_audit_real_historical_batch(tmp_path,monkeypatch):
    batch=REPO/'discovery/t01-phase1-real/w6/variant-report-integration-20260909/acceptance-r02'
    if not (batch/'index.json').exists():pytest.skip('Local historical real-output evidence not installed')
    output=tmp_path/'audit.json';monkeypatch.setattr(sys,'argv',['audit','--batch',str(batch),'--output',str(output)])
    module().main();result=decode(output.read_bytes())
    assert result['status']=='PASS' and result['r35_exclusions_verified']==24 and result['foldx_native_runs_verified']==15
