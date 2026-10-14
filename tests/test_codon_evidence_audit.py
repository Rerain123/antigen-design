import importlib.util
import json
from pathlib import Path
import shutil
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('codon_auditor',ROOT/'scripts/audit_codon_evidence.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
ARCHIVE=ROOT/'discovery/t01-phase1-real/w7/codon-integration-20260909/acceptance-r01'

def test_real_sealed_batch():
    result=module.audit(ARCHIVE)
    assert result['passed'] and result['independently_verified_optimized']==6 and result['real_no_solution_fallback']==1

@pytest.mark.parametrize('kind',['bytes','missing','extra','publication_hash'])
def test_auditor_rejects_archive_corruption(tmp_path,kind):
    shutil.copytree(ARCHIVE,tmp_path,dirs_exist_ok=True)
    index=json.loads((tmp_path/'index.json').read_bytes())
    p=tmp_path/index['files'][0]['path']
    if kind=='bytes':p.write_bytes(b'changed')
    if kind=='missing':p.unlink()
    if kind=='extra':(tmp_path/'extra.txt').write_text('unlisted')
    if kind=='publication_hash':
        index['cases'][0]['artifacts'][0]['artifact']['sha256']='0'*64
        (tmp_path/'index.json').write_text(json.dumps(index),encoding='utf-8')
    with pytest.raises((AssertionError,OSError)):module.audit(tmp_path)
