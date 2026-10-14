import importlib.util
import pytest
from t01_phase1_real.common import REPO,encode,sha

@pytest.mark.parametrize('error',['hash','size','escape'])
def test_corrupt_index_rejected_before_evidence_pass(tmp_path,error):
    spec=importlib.util.spec_from_file_location('n13audit',REPO/'scripts/audit_epitope_protection_evidence.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    batch=tmp_path/'batch';batch.mkdir();raw=b'evidence';(batch/'file').write_bytes(raw)
    row=dict(path='file',bytes=len(raw),sha256=sha(raw))
    if error=='hash':row['sha256']='0'*64
    elif error=='size':row['bytes']+=1
    else:row['path']='../outside';(tmp_path/'outside').write_bytes(raw)
    (batch/'index.json').write_bytes(encode(dict(status='PASS',files=[row])))
    with pytest.raises(AssertionError):module.audit(batch)
