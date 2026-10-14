import copy
import sys
from t01_phase1_real.common import REPO, encode
from t01_phase1_real.development.workflow import policy

sys.path.insert(0,str(REPO/'scripts'))
import run_m1_p1_probe as probe
import prepare_m1_p1_deploy as deploy


def test_fixed_probe_request_is_explicit_and_uses_only_registered_minimal_database():
    body,case=probe.request()
    assert policy.request(encode(body))['m1_test']==body['m1_test']
    assert len(body['protein_sequence'])==76 and body['structure']['declared_format']=='PDB'
    assert body['analysis']['blast']['database_id']=='engineering-n03'
    assert body['analysis']['homology'] is None and body['analysis']['domains'] is None
    assert not body['reuse_jobs']
    assert case['expected']['occupancy_changes'] and b'ATOM' in case['data']
    compile(probe.AUDIT,'audit','exec')


def test_deployment_patch_cannot_change_gpu_or_credentials():
    live=dict(metadata=dict(resourceVersion='1',uid='uid'),spec=dict(replicas=1,strategy=dict(type='Recreate'),
        template=dict(spec=dict(containers=[
            dict(name='service',args=['--runtime-root','/var/lib/t01/runtime'],volumeMounts=[]),
            dict(name='worker-blast',volumeMounts=[]),
            dict(name='worker-unified-gpu',resources={'limits':{'nvidia.com/gpu':'1'}})]))))
    before=copy.deepcopy(live);ops=deploy.patch(live)
    assert live==before
    assert all('/containers/2/' not in op['path'] and '/env' not in op['path'] for op in ops)
    assert ops[0]['op']=='test' and ops[0]['path']=='/metadata/resourceVersion'
    mount=next(op['value'] for op in ops if op['path'].endswith('/containers/1/volumeMounts/-'))
    assert mount['readOnly'] is True and mount['subPath']=='m1-p1-test-data/blast'
