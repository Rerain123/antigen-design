"""The report rollout must remain bound to the reviewed sources and results."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def release(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    # The rollout scripts configure shared helpers at import time. Restore them
    # so this guard test cannot change another deployment test's environment.
    import deploy_report_storage
    base=deploy_report_storage.base
    for owner,names in ((base,('OUT','EV','regression','prior_task')),
                        (deploy_report_storage,('PREVIOUS','EXPECTED'))):
        for name in names:monkeypatch.setattr(owner,name,getattr(owner,name))
    spec=importlib.util.spec_from_file_location('scientific_report_rollout_test',ROOT/'scripts/deploy_scientific_report.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_superseded_reviewed_report_cannot_be_redeployed(release):
    # The October 11 receipt remains frozen; later report changes must use their
    # own reviewed release instead of silently reopening this old deployment.
    with pytest.raises(AssertionError,match='Reviewed source changed'):
        release.regression()
    assert release.release.EXPECTED=={'t01_phase1_real/service_api/user_report.py',
                                     't01_phase1_real/service_api/native_report.py'}


def test_changed_reviewed_source_blocks_rollout(release,monkeypatch,tmp_path):
    review=json.loads((release.REVIEW/'closeout.json').read_bytes())
    review['sources'][0]['sha256']='0'*64
    (tmp_path/'closeout.json').write_text(json.dumps(review),'utf-8')
    monkeypatch.setattr(release,'REVIEW',tmp_path)
    with pytest.raises(AssertionError,match='Reviewed source changed'):
        release.regression()
