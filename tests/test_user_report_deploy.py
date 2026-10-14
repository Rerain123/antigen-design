"""Protect deferred deployment from active jobs, drift and invalid evidence."""
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import deploy_user_report as deploy


@pytest.mark.parametrize('state', [{}, {'active_jobs': []},
    {'active_jobs': [{'state': 'running'}], 'gpu_state': {'phase': 'idle'}},
    {'active_jobs': [], 'gpu_state': {'phase': 'executing'}}])
def test_missing_or_active_state_never_allows_restart(state):
    assert not deploy.is_idle(state)


def test_idle_requires_both_database_and_gpu():
    assert deploy.is_idle({'active_jobs': [], 'gpu_state': {'phase': 'idle'}})


@pytest.mark.parametrize('changed', ['source', 'generation', 'artifact'])
def test_deferred_rollout_rejects_drift(monkeypatch, tmp_path, changed):
    monkeypatch.setattr(deploy, 'OUT', tmp_path)
    monkeypatch.setattr(deploy, 'bindings', lambda: {'code': 'new' if changed == 'source' else 'same'})
    (tmp_path / 'cm').write_text('safe')
    pre = dict(bindings={'code': 'same'}, uid='u', generation=93,
               prepared_sha256={'cm': deploy.digest(tmp_path / 'cm')})
    if changed == 'artifact':
        (tmp_path / 'cm').write_text('changed')
    live = {'metadata': {'uid': 'u', 'generation': 94 if changed == 'generation' else 93}}
    with pytest.raises(RuntimeError):
        deploy.assert_unchanged(pre, live)


def test_passing_evidence_requires_all_suites_and_no_skips(tmp_path):
    path = tmp_path / 'junit.xml'
    rows = [f'<testcase classname="tests.{Path(p).stem}" name="case{i}" />'
            for p in deploy.TESTS for i in range(15)]
    path.write_text('<testsuite>' + ''.join(rows) + '</testsuite>')
    assert deploy.tests_passed(path)
    path.write_text('<testsuite>' + ''.join(rows).replace(' />', '><skipped/></testcase>', 1) + '</testsuite>')
    assert not deploy.tests_passed(path)
