import importlib.util
import io
from pathlib import Path
import sys
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('workflow_auditor',ROOT/'scripts/audit_local_workflow_evidence.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

@pytest.mark.parametrize('batch',['acceptance-r01','acceptance-r02'])
def test_real_workflow_archive(batch):
    result=audit.audit(ROOT/'discovery/t01-phase1-real/integration-20260910'/batch)
    assert result['passed'] and result['new_real_model_execution']
    assert result['original_24_exclusions_preserved']

def test_manifest_integrity_rejects_tamper():
    import json
    data=dict(usable_for_pipeline=False,automatic_handoff=False,scientific_gate='CLOSED',production_status='NOT_DEPLOYED',md='EXCLUDED')
    raw=json.dumps(data).encode()
    entries={'workflow.json':raw,'manifest.json':json.dumps(dict(files=[dict(path='workflow.json',sha256=audit.sha(raw),size_bytes=len(raw))])).encode()}
    for mutation in ('none','alter','extra','duplicate'):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            for n,v in entries.items():z.writestr(n,b'{}' if mutation=='alter' and n=='workflow.json' else v)
            if mutation=='extra':z.writestr('extra',b'')
            if mutation=='duplicate':
                with pytest.warns(UserWarning):z.writestr('workflow.json',raw)
        if mutation=='none':assert audit.package(buf.getvalue())==data
        else:
            with pytest.raises(AssertionError):audit.package(buf.getvalue())
