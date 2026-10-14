import copy

import pytest

from t01_phase1_real.development.workflow import policy
from t01_phase1_real.development.workflow.engineering import MODE
from t01_phase1_real.service_api.progress import project
from t01_phase1_real.service_api.progress import execution_status


def pending():
    return {name: dict(node_id=policy.NODES[name], state='not_executed')
            for name in policy.order({'engineering_design': MODE, 'prediction': {'engine': 'esmfold2'}})}


def test_internal_steps_are_18_business_nodes_and_reconciling_blast_is_visible():
    nodes = pending()
    for name in ('prediction', 'structure', 'topology'):
        nodes[name]['state'] = 'succeeded'
    nodes['blast']['state'] = 'reconciling'
    original = copy.deepcopy(nodes)
    result = project(nodes)
    assert nodes == original
    assert result['total_nodes'] == 18 and result['completed_nodes'] == 2
    assert result['current_nodes'] == ['N03']
    assert result['node_counts']['succeeded'] == 2
    assert result['internal_step_counts']['total'] == 698  # Full 64-candidate reassessment and 20 DNA slots.
    assert result['internal_step_counts']['finished'] == 3
    assert result['node_progress']['N03']['active_steps'] == [{'step': 'blast', 'state': 'reconciling'}]


@pytest.mark.parametrize('state', ['queued', 'running', 'reconciling', 'stop_requested'])
def test_active_substeps_are_deduplicated_and_not_completed(state):
    nodes = pending()
    nodes['prediction']['state'] = nodes['structure']['state'] = state
    result = project(nodes)
    assert result['current_nodes'] == ['N01'] and result['completed_nodes'] == 0
    assert result['node_progress']['N01']['state'] == state


def test_early_wt_draft_and_representative_preselection_do_not_finish_business_nodes():
    nodes = pending()
    for name in ('wt_draft', 'rescore', 'design_audit', 'preselection'):
        nodes[name]['state'] = 'succeeded'
    result = project(nodes)
    assert result['current_nodes'] == [] and result['completed_nodes'] == 0
    assert result['node_progress']['N18']['state'] == 'waiting'
    assert result['node_progress']['N12']['state'] == 'waiting'


@pytest.mark.parametrize('state', ['failed', 'timed_out', 'cancelled', 'blocked', 'unavailable', 'skipped'])
def test_non_success_is_not_counted_as_success(state):
    nodes = pending()
    nodes['blast']['state'] = state
    result = project(nodes)
    assert result['completed_nodes'] == 1 and result['node_counts'][state] == 1
    assert result['node_counts'].get('succeeded', 0) == 0


def test_mixed_skips_failure_and_unexecuted_steps_remain_distinct():
    nodes = pending()
    for row in nodes.values():
        row['state'] = 'skipped'
    nodes['structure']['state'] = 'succeeded'
    result = project(nodes)
    assert result['completed_nodes'] == 18
    assert result['node_counts'] == {'completed_with_skips': 1, 'skipped': 17}
    nodes['prediction']['state'] = 'failed'
    nodes['structure']['state'] = 'not_executed'
    result = project(nodes)
    assert result['completed_nodes'] == 17
    assert result['node_progress']['N01']['state'] == 'failed'
    assert result['node_progress']['N01']['completed'] is False


def test_empty_snapshot_does_not_suggest_work_has_finished():
    result = project({})
    assert result['completed_nodes'] == 0 and result['total_nodes'] == 18
    assert result['node_counts'] == {'not_executed': 18}


@pytest.fixture
def worker_observation(tmp_path,monkeypatch):
    from t01_phase1_real.common import encode,sha
    from t01_phase1_real import resident_execution
    root=tmp_path/'blast';target=root/('a'*32);target.mkdir(parents=True)
    job=dict(job_id='job',run_id='run',attempt_id='attempt',execution_identity='exec',state='reconciling',tool_id='t01.real.blast')
    binding={k:job[k] for k in ('job_id','attempt_id','execution_identity')}
    raw=encode(dict(binding=binding,execution_id=target.name));(target/'request.json').write_bytes(raw)
    receipt=dict(binding=binding,execution_id=target.name,request_sha256=sha(raw),backend='resident-process',
        state='running',stopped_confirmed=False)
    class Runtime:
        def get(self,jid):assert jid=='job';return dict(job)
        def execution(self,jid):return dict(backend='resident-process',resident_target=str(target),resident_request_sha256=sha(raw))
    monkeypatch.setattr(resident_execution,'configuration',lambda:({'tools':{'blast':{'root':str(root)}}},'hash'))
    return Runtime(),job,target,receipt


def test_queued_native_execution_does_not_become_running_from_parent_state(worker_observation):
    rt,job,target,receipt=worker_observation
    assert execution_status(rt,'job','run')['phase']=='waiting_worker'
    nodes=pending();nodes['blast'].update(state='reconciling',execution=execution_status(rt,'job','run'))
    assert project(nodes)['node_progress']['N03']['active_steps'][0]['execution']['phase']=='waiting_worker'


@pytest.mark.parametrize('state,stopped,expected',[('starting',False,'worker_starting'),('running',False,'executing'),
    ('succeeded',True,'finalizing'),('failed',True,'finalizing'),('cancelled',True,'finalizing')])
def test_bound_worker_state_is_distinct_from_collection(worker_observation,state,stopped,expected):
    from t01_phase1_real.common import encode
    rt,job,target,receipt=worker_observation
    receipt.update(state=state,stopped_confirmed=stopped);(target/'execution.json').write_bytes(encode(receipt))
    assert execution_status(rt,'job','run')['phase']==expected


@pytest.mark.parametrize('fault',['foreign_run','foreign_attempt','hash_mismatch','corrupt_receipt'])
def test_unknown_or_foreign_receipt_never_claims_computation(worker_observation,fault):
    from t01_phase1_real.common import encode
    rt,job,target,receipt=worker_observation
    if fault=='foreign_attempt':receipt['binding']['attempt_id']='other'
    if fault=='hash_mismatch':receipt['request_sha256']='b'*64
    (target/'execution.json').write_bytes(b'bad' if fault=='corrupt_receipt' else encode(receipt))
    assert execution_status(rt,'job','other' if fault=='foreign_run' else 'run')['phase']=='unknown'


def test_cancelled_or_stop_requested_does_not_keep_running_display(worker_observation):
    rt,job,target,receipt=worker_observation
    job['state']='stop_requested';assert execution_status(rt,'job','run')['phase']=='stopping'
    job['state']='cancelled';assert execution_status(rt,'job','run')['phase']=='finished'


def test_service_status_attaches_only_owned_active_child_observations(worker_observation,monkeypatch):
    from types import SimpleNamespace
    from t01_phase1_real.service_api.app import Service
    rt,job,target,receipt=worker_observation
    parent=dict(job_id='parent',run_id='run',state='running',error_code=None,revision=1)
    nodes=dict(blast=dict(node_id='N03',state='reconciling',job_id='job'),
               structure=dict(node_id='N01',state='succeeded',job_id='finished-child'))
    class WorkflowRuntime:
        def get(self,jid):return parent if jid=='parent' else rt.get(jid)
        def workflow(self,jid):assert jid=='parent';return dict(nodes=nodes)
        def execution(self,jid):return rt.execution(jid)
    authorized=[]
    service=SimpleNamespace(store=SimpleNamespace(authorize_job=lambda p,j:authorized.append((p,j))),
        runtime=lambda p:WorkflowRuntime(),_job_response=Service._job_response)
    from t01_phase1_real.development.workflow import service as workflow_service
    def lifecycle_snapshot(runtime,jid,verify=True):
        assert jid=='parent' and verify is False
        return dict(nodes=nodes)
    monkeypatch.setattr(workflow_service,'snapshot',lifecycle_snapshot)
    value=Service.status(service,'owner','parent')
    assert authorized==[('owner','parent')]
    assert value['nodes']['blast']['execution']['phase']=='waiting_worker'
    assert 'execution' not in value['nodes']['structure']
    assert 'execution' not in nodes['blast']


def test_deployment_changes_only_service_mounts_and_refuses_active_apply(monkeypatch):
    import importlib
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    prep = importlib.import_module('prepare_himat_progress_fix')
    live = dict(metadata=dict(uid='uid', resourceVersion='80'), spec=dict(replicas=1, strategy={'type': 'Recreate'},
        template=dict(spec=dict(volumes=[], containers=[dict(name='worker-blast', volumeMounts=[]),
            dict(name='service', volumeMounts=[dict(name='data', mountPath='/var/lib/t01'),
                dict(name='old', mountPath='/app/src/t01_phase1_real/service_api/himat.py')])]))))
    before = copy.deepcopy(live)
    cm, patch = prep.render(live)
    assert live == before and cm['immutable']
    assert [p['op'] for p in patch[:2]] == ['test', 'test']
    mounts = patch[2]['value']
    assert patch[2]['path'].endswith('/containers/1/volumeMounts')
    assert len({m['mountPath'] for m in mounts}) == len(mounts)
    assert dict(name='data', mountPath='/var/lib/t01') in mounts
    monkeypatch.setattr(prep.common, 'idle', lambda: {'active_jobs': [{'job_id': 'active'}], 'gpu_state': {'phase': 'idle'}})
    monkeypatch.setattr('sys.argv', ['prepare_himat_progress_fix.py', '--apply'])
    monkeypatch.setattr(prep.subprocess, 'run', lambda *args, **kwargs: pytest.fail('Must not mutate cluster'))
    with pytest.raises(RuntimeError, match='active'):
        prep.main()
