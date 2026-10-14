import importlib.util
import io
from pathlib import Path
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('delivery_auditor',ROOT/'scripts/audit_local_delivery_evidence.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
BASE=ROOT/'discovery/t01-phase1-real/w7/local-delivery-integration-20260910'

@pytest.mark.parametrize('name',['acceptance-r01','supplement-r01','supplement-r02'])
def test_real_archives(name):assert audit.audit(BASE/name)['passed']

def test_zip_rejects_corrupted_payload_and_extra_entry():
    import json
    raw=(BASE/'acceptance-r01/cases/real24-all-excluded-delivery/package.zip').read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries={n:z.read(n) for n in z.namelist()};expected=json.loads(entries['data.json'])
    for key,data in (('data.json',b'{}'),('unregistered.txt',b'new')):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for name,value in dict(entries,**{key:data}).items():z.writestr(name,value)
        with pytest.raises(AssertionError):audit.package(out.getvalue(),expected)
