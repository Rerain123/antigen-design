"""Recorded engineering evidence must remain verifiable, including deliberate corruption."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import check_w1_runtime as checker


def test_recorded_runtime_evidence():
    result=checker.verify()
    assert result['runtime_cases']==15 and result['status']=='PASS_ENGINEERING_ONLY'


def test_changed_recorded_output_rejected(tmp_path):
    batch=tmp_path/'batch';shutil.copytree(checker.DEFAULT,batch)
    path=batch/'jobs/success/job.json'
    value=json.loads(path.read_text(encoding='utf-8'));value['usable_for_pipeline']=True
    path.write_text(json.dumps(value),encoding='utf-8')
    with pytest.raises(ValueError,match='hash mismatch'): checker.verify(batch)
