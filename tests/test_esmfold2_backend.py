"""Rebound archived bytes are contract fixtures, not new model execution evidence."""
import copy
import math
from pathlib import Path
import pytest
from t01_phase1_real.common import REPO, RuntimeFault, decode, encode, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.esmfold2 import policy
from t01_phase1_real.development.esmfold2.standard import normalize, NAMES
from t01_phase1_real.development.workflow import policy as flow, service
from t01_phase1_real.resident_process import atomic, inventory

ARCHIVE = REPO/'discovery/t01-phase1-real/esmfold2-target-20260917/r03'


def body():
    seq = decode((ARCHIVE/'request.json').read_bytes())['inputs']['sequence']
    return dict(protein_sequence=seq,user_sequence_id='new-request',host_species='Homo sapiens',seed=1,timeout_seconds=600)


def native_fixture(b, binding):
    native = {n:(ARCHIVE/n).read_bytes() for n in NAMES | {'manifest.json'}}
    request = policy.native_request(b,binding)
    native['request.json'] = encode(request)
    native['profile.json'] = encode(policy.profile())
    value=decode(native['result.json']);value.update(request_id=binding['job_id'],sequence_id=request['inputs']['sequence_id'])
    native['result.json']=encode(value)
    rehash(native)
    return native


def rehash(native):
    native['manifest.json']=encode(dict(files=[dict(path=n,size_bytes=len(native[n]),sha256=sha(native[n])) for n in sorted(NAMES)]))


@pytest.fixture
def runtime(tmp_path,monkeypatch):
    command=dict(tool='esmfold2',argv=['/usr/local/bin/python','-B','/worker.py'],memory_bytes=256*1024**3,
                 environment=dict(T01_SOURCE_IMAGE_ID=policy.IMAGE,T01_RESIDENT_OFFLINE='1'))
    path=tmp_path/'resident.json'
    path.write_bytes(encode(dict(version='0.1.0',runtime_volume_root=str(tmp_path),tools={
        'esmfold2':dict(root=str(tmp_path/'spool'),source_image_id=policy.IMAGE,command=command)})))
    monkeypatch.setenv('T01_RESIDENT_CONFIG_FILE',str(path))
    return Runtime(tmp_path/'runtime')


def complete_fixture(rt,jid,state='succeeded'):
    job=rt.get(jid); ex=rt.execution(jid); target=Path(ex['resident_target'])
    request=decode((target/'request.json').read_bytes())
    binding=decode((target/'input/binding.json').read_bytes())
    b=decode((target/'input/input.json').read_bytes())
    if state=='succeeded':
        native=native_fixture(b,binding)
        files={'raw/'+n:v for n,v in native.items()}
        files.update(normalize(native,b,binding))
        observation=dict(network_interfaces=[[1,'lo'],[2,'eth0']],cpu_affinity=[0,1],machine='x86_64',
            source_image_id=policy.IMAGE,network_restriction='seccomp-local-sockets-only-v1')
        atomic(target/'output/executor-observation.json',observation)
        files['runtime.json']=encode(dict(binding=binding,input_sha256=sha((target/'input/input.json').read_bytes()),
            source_sha256={p.name:sha(p.read_bytes()) for p in sorted(policy.HERE.iterdir()) if p.suffix in ('.py','.json')},
            network_interfaces=observation['network_interfaces'],cpu_affinity=[0,1],socket_probe='INET_INET6_DENIED',python_exit_code=0))
        for name,raw in files.items():
            p=target/'output/native'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    atomic(target/'execution.json',dict(version='0.1.0',backend='resident-process',binding=request['binding'],
        execution_id=target.name,request_sha256=sha((target/'request.json').read_bytes()),state=state,
        stopped_confirmed=True,exit_code=0 if state=='succeeded' else None,outputs=inventory(target)))
    return rt.reconcile(jid)


def test_new_task_idempotency_standard_binding_and_recovery(runtime):
    rt=runtime;b=body();first=rt.submit_sequence(encode(b),'esm-test',policy.TOOL)
    assert rt.submit_sequence(encode(b),'esm-test',policy.TOOL)==first
    j=rt.dispatch(first['job_id']);assert j['state']=='running'
    target=rt.execution(j['job_id'])['resident_target']
    rt.recover(j['job_id']);assert rt.execution(j['job_id'])['resident_target']==target
    end=complete_fixture(rt,j['job_id']);assert end['state']=='succeeded'
    value=rt.result(j['job_id'])
    assert value['prediction']['attempt_id']==j['attempt_id']
    assert value['prediction']['request_id']==j['job_id']
    assert value['prediction']['models'][0]['iptm'] is None
    assert not value['usable_for_pipeline']


def test_confidence_mean_is_stable_across_python_float_sum_versions():
    b=body();binding=dict(job_id='t01p1r-job-'+'a'*32,attempt_id='t01p1r-attempt-'+'b'*32)
    confidence=decode(normalize(native_fixture(b,binding),b,binding)['confidence.json'])
    scores=[row['plddt'] for row in confidence['residues']]
    assert confidence['mean_plddt'] == math.fsum(scores)/len(scores)
    # This fixture exercises the exact last-bit difference seen between the
    # Python 3.12 model worker and Python 3.11 control plane.
    naive_total = 0.0
    for score in scores:
        naive_total += score
    assert confidence['mean_plddt'] != naive_total/len(scores)


@pytest.mark.parametrize('gpu_name', ['NVIDIA A100-SXM-64GB', 'NVIDIA A100-SXM4-40GB'])
def test_exact_registered_a100_environments_are_accepted(gpu_name):
    b=body();binding=dict(job_id='t01p1r-job-'+'a'*32,attempt_id='t01p1r-attempt-'+'b'*32)
    native=native_fixture(b,binding)
    execution=decode(native['execution.json']);execution['gpu_name']=gpu_name
    native['execution.json']=encode(execution);rehash(native)
    assert 'result.json' in normalize(native,b,binding)


def test_unregistered_gpu_environment_is_rejected():
    b=body();binding=dict(job_id='t01p1r-job-'+'a'*32,attempt_id='t01p1r-attempt-'+'b'*32)
    native=native_fixture(b,binding)
    execution=decode(native['execution.json']);execution['gpu_name']='NVIDIA A100'
    native['execution.json']=encode(execution);rehash(native)
    with pytest.raises(RuntimeFault, match='Unregistered ESMFold2 target environment'):
        normalize(native,b,binding)


@pytest.mark.parametrize('damage', [None, 'software', 'multiple', 'capability', 'policy'])
def test_assigned_hardware_keeps_software_and_observation_validation(damage):
    b=body();binding=dict(job_id='t01p1r-job-'+'a'*32,attempt_id='t01p1r-attempt-'+'b'*32)
    native=native_fixture(b,binding)
    execution=decode(native['execution.json'])
    execution.update(gpu_name='NVIDIA RTX 4090', gpu_capability=[8,9], gpu_count=1,
                     gpu_allocation_policy='scheduler-assigned-exclusive-v1')
    if damage=='software': execution['torch']='changed'
    elif damage=='multiple': execution['gpu_count']=2
    elif damage=='capability': execution['gpu_capability']=[True,0]
    elif damage=='policy': execution['gpu_allocation_policy']='unknown'
    native['execution.json']=encode(execution);rehash(native)
    if damage:
        with pytest.raises(RuntimeFault):normalize(native,b,binding)
    else:assert 'result.json' in normalize(native,b,binding)


@pytest.mark.parametrize('state',['cancelled','timed_out'])
def test_stop_requires_receipt_and_clears_prediction(runtime,state):
    rt=runtime;j=rt.submit_sequence(encode(body()),state,policy.TOOL);rt.dispatch(j['job_id'])
    if state=='cancelled':
        rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='cancel')))
        assert rt.reconcile(j['job_id'])['state'] not in ('cancelled','succeeded')
    end=complete_fixture(rt,j['job_id'],state)
    assert end['state']==state and end['stop_confirmed']
    assert rt.result(j['job_id'])['prediction'] is None


def flow_body():
    b=body()
    return dict(protein_sequence=b['protein_sequence'],user_sequence_id=b['user_sequence_id'],host_species=b['host_species'],
        expression_host=None,organism=None,structure=None,analysis={n:None for n in flow.OPTIONS},reuse_jobs={},timeout_seconds=1800,
        prediction=dict(engine='esmfold2',seed=1,timeout_seconds=600))


def test_explicit_route_and_verified_prediction_to_structure(runtime):
    rt=runtime;j=rt.submit_workflow(encode(flow_body()),'flow');rt.dispatch(j['job_id'])
    row=rt.execution(j['job_id'])['nodes']['prediction']
    end=complete_fixture(rt,row['job_id']);assert end['state']=='succeeded'
    rows=dict(prediction=dict(row,state='succeeded'))
    req,reason=service.request_for(rt,flow_body(),rows,'structure')
    assert reason is None and req['source_declaration']['kind']=='predicted'
    assert req['structure_artifact']['job_id']==row['job_id']
    from t01_phase1_real.development.structure import policy as sp
    sp.request(encode(req))
    with rt._db() as db:
        from t01_phase1_real.development.esmfold2.standard import tool_structure
        assert rt._structure_bytes(db,req,end['run_id'])==tool_structure((ARCHIVE/'structure.cif').read_bytes())[0]
        from t01_phase1_real.development.esmfold2.source import verified
        evidence=verified(rt,db,end['job_id'],req['protein_sequence'],req['host_species'],end['run_id'],include_quality=True)
        assert evidence['structure_artifact']==req['structure_artifact']
        assert evidence['native_structure_artifact']['sha256']==sha((ARCHIVE/'structure.cif').read_bytes())
        assert evidence['quality_artifact']['sha256']==sha(encode(evidence['quality']))
        assert evidence['quality']['quality']['confidence']=='high'
        wrong=copy.deepcopy(req);wrong['protein_sequence']='A'*76
        with pytest.raises(RuntimeFault):rt._structure_bytes(db,wrong,end['run_id'])
        with pytest.raises(RuntimeFault):rt._structure_bytes(db,req,'foreign-run')
    rows['prediction']['state']='failed'
    assert service.request_for(rt,flow_body(),rows,'structure')==(None,'PREDICTION_UNAVAILABLE')


@pytest.mark.parametrize('field,value',[('seed',True),('seed',2),('protein_sequence','A'*1000),('timeout_seconds',0)])
def test_request_boundaries(field,value):
    b=body();b[field]=value
    with pytest.raises(RuntimeFault):policy.request(encode(b))


@pytest.mark.parametrize('damage',['request','sequence','confidence','checkpoint','nan'])
def test_semantic_corruption_rehashed_still_rejected(damage):
    b=body();binding=dict(job_id='t01p1r-job-'+'a'*32,attempt_id='t01p1r-attempt-'+'b'*32)
    native=native_fixture(b,binding)
    if damage=='request':native['request.json']=encode(dict(policy.native_request(b,binding),request_id='old-r03'))
    elif damage=='sequence':native['structure.cif']=native['structure.cif'].replace(b'MET',b'ALA')
    elif damage=='confidence':
        data=decode(native['metrics.json']);data['mean_plddt']=0.1;native['metrics.json']=encode(data)
    elif damage=='checkpoint':
        data=decode(native['checkpoint-loading.json']);data['esmc']['native_parameters_loaded']=1;native['checkpoint-loading.json']=encode(data)
    else:native['metrics.json']=b'{"mean_plddt":NaN}'
    rehash(native)
    with pytest.raises((RuntimeFault,KeyError,ValueError)):normalize(native,b,binding)
