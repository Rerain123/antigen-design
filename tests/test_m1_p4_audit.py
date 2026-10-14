"""Auditor tamper rejection against isolated copies of fresh engineering evidence."""
import json
import shutil
import sys
import pytest
from t01_phase1_real.common import REPO
sys.path.insert(0,str(REPO/'scripts'))
from audit_m1_p4 import audit

ROOT=REPO/'discovery/t01-phase1-real/m1-p4-20260922'


@pytest.mark.parametrize('batch',['r03','r04'])
def test_actual_service_branch_audits(batch):
    result=audit(ROOT/batch)
    assert result['status'].endswith('_PASS') and not result['p4_m1_complete']
    assert not result['target_nr_accepted'] and not result['usable_for_pipeline']


@pytest.mark.parametrize('damage',['run','request','result','archive','origin'])
def test_auditor_rejects_altered_records(tmp_path,damage):
    folder=tmp_path/'evidence';shutil.copytree(ROOT/'r04',folder)
    if damage=='archive':
        with (folder/'native-evidence.zip').open('ab') as f:f.write(b'tamper')
    else:
        path=folder/('workflow-snapshot.json' if damage in ('run','origin') else 'structure.json')
        value=json.loads(path.read_bytes())
        if damage=='run':value['job']['run_id']='foreign-run'
        elif damage=='origin':value['nodes']['structure']['origin']='HISTORICAL_REUSE'
        elif damage=='request':value['request']['protein_sequence']='A'*76
        else:value['result']['binding']['sequence_sha256']='0'*64
        path.write_text(json.dumps(value),encoding='utf-8')
    with pytest.raises(AssertionError):audit(folder)
