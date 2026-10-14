"""User's <1000-aa input domain is separate from native throughput evidence."""
import pytest
from t01_phase1_real.development.af3 import policy
from t01_phase1_real.development.workflow import policy as workflow
from t01_phase1_real.common import encode
from test_local_workflow import body


def request(n):
    return dict(protein_sequence=('ACDEFGHIKLMNPQRSTVWY'*50)[:n],
        user_sequence_id='capacity-boundary',host_species='pig',seed=1,timeout_seconds=7200)


@pytest.mark.parametrize('n',[9,76,77,233,500,998,999])
def test_af3_service_and_workflow_admit_full_requested_domain(n):
    b=request(n)
    assert policy.request(encode(b))==b
    native=policy.native_request(b,{'job_id':'fixture'})
    assert native['inputs']['sequence']==b['protein_sequence']
    flow=body();flow['protein_sequence']=b['protein_sequence']
    flow['prediction']=dict(engine='af3',seed=1,timeout_seconds=7200)
    flow['engineering_design']='BACKEND_EVIDENCE_V1'
    assert workflow.request(encode(flow))['prediction']['engine']=='af3'


@pytest.mark.parametrize('sequence',['A'*8,'A'*1000,'A'*999+'X','a'*77,'A'*76+'\n'])
def test_af3_rejects_outside_domain_and_invalid_characters(sequence):
    b=request(9);b['protein_sequence']=sequence
    with pytest.raises(Exception,match='9..999'):policy.request(encode(b))


def test_gpu_and_service_receive_identical_policy_overlay(monkeypatch):
    import sys
    from t01_phase1_real.common import REPO
    sys.path.insert(0,str(REPO/'scripts'))
    import prepare_n12_validation as deploy
    # The one-shot deployment CLI configures shared renderer modules. Restore
    # those globals so later deployment tests exercise their own renderer.
    for module in (deploy.base, deploy.base.renderer):
        for name in ('NAME', 'OUT', 'EVIDENCE', 'FILES', 'render'):
            monkeypatch.setattr(module, name, getattr(module, name))
    deploy.configure()
    live={'metadata':{'uid':'fixture','resourceVersion':'1'},'spec':{'replicas':1,'strategy':{'type':'Recreate'},
        'template':{'spec':{'volumes':[],'containers':[{'name':'service','volumeMounts':[]},
                                                   {'name':'worker-unified-gpu','volumeMounts':[]}]}}}}
    cm,patch,_=deploy.render(live)
    mountsets=[p['value'] for p in patch if p['path'].endswith('/volumeMounts')]
    keys=[m['subPath'] for mounts in mountsets for m in mounts if m['mountPath'].endswith('/af3/policy.py')]
    assert len(keys)==2 and keys[0]==keys[1] and keys[0] in cm['binaryData']


def test_old_af3_evidence_replay_does_not_relax_new_job_source_checks():
    import copy,json
    from t01_phase1_real.common import REPO
    from t01_phase1_real.development.af3.result import verify_source_identity
    evidence=json.loads((REPO/'reports/n12-validation-20260926/af3-input-inspection.json').read_bytes())['previous_source_profile']
    runtime={'source_sha256':evidence['source_sha256']};job={'execution_profile':evidence['profile']}
    verify_source_identity(job,request(76),runtime,historical_source=True)
    with pytest.raises(Exception,match='source changed'):verify_source_identity(job,request(76),runtime)
    with pytest.raises(Exception,match='source changed'):verify_source_identity(job,request(77),runtime,historical_source=True)
    changed=copy.deepcopy(runtime);changed['source_sha256']['policy.py']='0'*64
    with pytest.raises(Exception,match='source changed'):verify_source_identity(job,request(76),changed,historical_source=True)
