import hashlib
import json
from pathlib import Path
import pytest
from t01_phase1_real.gpu_dispatch import candidate, choose, next_action, tick

EXEC = {'target': '/var/lib/t01/resident/gpu/' + 'a'*32, 'sha256': 'abc',
        'mode': 'gpu', 'order': 1, 'uncertain': False}

def deployment(replicas=0):
    return {'metadata': {'uid': 'u', 'resourceVersion': '1'},
            'spec': {'replicas': replicas, 'strategy': {'type': 'Recreate'}, 'template': {
                'metadata': {'annotations': {'antigen-design/execution-sha256': EXEC['sha256'],
                                            'antigen-design/execution-target': EXEC['target']}},
                'spec': {'containers': [{'name': 'worker'}]}}}}

def test_fifo_and_uncertainty_blocks_all_modes():
    later = dict(EXEC, order=2, mode='esmfold2')
    assert choose([later, EXEC]) == EXEC
    with pytest.raises(RuntimeError, match='Unconfirmed'):
        choose([EXEC, dict(later, uncertain=True)])

def test_old_pod_must_disappear_before_next_mode():
    state = {'phase': 'releasing', 'execution': EXEC}
    assert next_action(state, deployment(), [{'metadata': {'deletionTimestamp': 'now'}}], None) == 'wait'
    assert next_action(state, deployment(), [], None) == 'complete'

def test_restart_after_patch_observes_without_relaunch():
    state = {'phase': 'reserved', 'execution': EXEC}
    assert next_action(state, deployment(1), [], None) == 'observe'
    drift = deployment(1)
    drift['spec']['template']['metadata']['annotations']['antigen-design/execution-target'] = '/other'
    with pytest.raises(RuntimeError, match='drift'):
        next_action(state, drift, [], None)

def test_running_waits_for_terminal_stop_confirmation():
    state = {'phase': 'running', 'execution': EXEC}
    assert next_action(state, deployment(1), [{'status': {'phase': 'Running'}}], None) == 'wait'
    assert next_action(dict(state, confirmed_terminal=True), deployment(1), [], None) == 'release'
    with pytest.raises(RuntimeError, match='without a confirmed'):
        next_action(state, deployment(1), [{'status': {'phase': 'Failed'}}], None)

def test_recovery_does_not_reclaim_missing_process_evidence():
    with pytest.raises(RuntimeError, match='disappeared'):
        next_action({'phase': 'running', 'execution': EXEC}, deployment(), [], None)

def test_idle_foreign_slot_owner_rejected():
    with pytest.raises(RuntimeError, match='unexpected slot owner'):
        next_action({'phase': 'idle'}, deployment(1), [], EXEC)

def test_releasing_intent_retries_scale_down_only():
    assert next_action({'phase': 'releasing','execution':EXEC}, deployment(1), [], None) == 'release'

def test_committed_receipt_binding_and_cancellation(tmp_path):
    folder = tmp_path / ('b'*32)
    folder.mkdir()
    command = {'tool': 'esmfold2'}
    request = {'execution_id':folder.name, 'binding':{'job_id':'j'}, 'command': command}
    raw = json.dumps(request).encode()
    (folder/'request.json').write_bytes(raw)
    (folder/'cancel').touch()
    assert len(candidate(tmp_path,'esmfold2',{'esmfold2':command})) == 1
    receipt = {'binding':request['binding'], 'request_sha256':hashlib.sha256(raw).hexdigest(),
               'stopped_confirmed':True, 'state':'cancelled'}
    (folder/'execution.json').write_text(json.dumps(receipt))
    assert candidate(tmp_path,'esmfold2',{'esmfold2':command}) == []
    receipt['request_sha256']='wrong'
    (folder/'execution.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='identity'):
        candidate(tmp_path,'esmfold2',{'esmfold2':command})

def test_other_project_gpu_allocation_blocks_api_mutation(tmp_path):
    class API:
        def deployment(self): return deployment()
        def pods(self):
            return [{'metadata':{'name':'antigen-other','labels':{}},'status':{'phase':'Running'},
                     'spec':{'containers':[{'resources':{'limits':{'nvidia.com/gpu':1}}}]}}]
        def patch(self,*args): pytest.fail('must not mutate')
    with pytest.raises(RuntimeError,match='Another project GPU'):
        tick({'deployment':'slot','modes':{}},tmp_path/'state.json',API())

def test_rbac_only_named_deployment_and_read_pods():
    import yaml
    rows=list(yaml.safe_load_all((Path(__file__).parents[1]/'deploy/single-gpu/dispatcher-rbac.r01.yaml').read_text()))
    rules=rows[1]['rules']
    assert rules[0]['resourceNames']==['antigen-design-gpu-slot']
    assert rules[0]['verbs']==['get','patch']
    assert rules[1]['verbs']==['list']

@pytest.mark.parametrize('terminal', ['succeeded','failed','cancelled','timed_out','interrupted'])
def test_complete_cycle_and_release_before_next_request(tmp_path, terminal):
    import copy
    root=tmp_path/'gpu'
    root.mkdir()
    folder=root/('c'*32)
    folder.mkdir()
    command={'tool':'proteinmpnn'}
    raw=json.dumps({'execution_id':folder.name,'binding':{'job_id':'job'},'command':command}).encode()
    (folder/'request.json').write_bytes(raw)
    template={'metadata':{'annotations':{'nvidia.com/use-gputype':'A100-SXM-64GB'}},
              'spec':{'containers':[{'name':'worker','resources':{'limits':{
                  'nvidia.com/gpu':'1','nvidia.com/gpumem-percentage':'100','nvidia.com/gpucores':'100'}}}]}}
    config={'deployment':'slot','modes':{'gpu':{'root':str(root),'commands':{'proteinmpnn':command},'template':template}}}
    class API:
        def __init__(self): self.live=deployment(); self.current=[]; self.calls=[]
        def deployment(self): return copy.deepcopy(self.live)
        def pods(self): return self.current
        def patch(self, live, changes):
            self.calls.append(changes)
            for change in changes:
                if change['path']=='/spec/replicas': self.live['spec']['replicas']=change['value']
                elif change['path']=='/spec/template': self.live['spec']['template']=change['value']
    api=API()
    state=tmp_path/'state.json'
    assert tick(config,state,api)=='reserve'
    assert not api.calls
    assert tick(config,state,api)=='start'
    api.current=[{'metadata':{'name':'antigen-slot','labels':{'app':'slot'}},'status':{'phase':'Running'}}]
    assert tick(config,state,api)=='wait'
    (folder/'execution.json').write_text(json.dumps({'binding':{'job_id':'job'},'request_sha256':hashlib.sha256(raw).hexdigest(),'state':terminal,'stopped_confirmed':True}))
    assert tick(config,state,api)=='release'
    assert api.live['spec']['replicas']==0
    assert tick(config,state,api)=='wait'
    api.current=[]
    assert tick(config,state,api)=='complete'
    assert tick(config,state,api)=='wait'
    assert len(api.calls)==2

def test_generated_deployments_stopped_and_no_secret_mounts():
    import yaml
    file=Path(__file__).parents[1]/'deploy/single-gpu/dispatcher.r01.yaml'
    code, settings, slot, control=list(yaml.safe_load_all(file.read_text(encoding='utf-8')))
    assert slot['spec']['replicas']==control['spec']['replicas']==0
    config=json.loads(settings['data']['dispatch.json'])
    assert set(config['modes'])=={'gpu','esmfold2'}
    for mode in config['modes'].values():
        pod=mode['template']['spec']
        assert len(pod['containers'])==1
        assert pod['automountServiceAccountToken'] is False
        assert all('secret' not in v for v in pod['volumes'])
        assert 'podAffinity' in pod['affinity']
    assert 'nvidia.com/gpu' not in json.dumps(control['spec']['template']['spec']['containers'])
