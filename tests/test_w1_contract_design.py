"""Meaningful negative checks for the design; no production runtime is implemented here."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('w1_contract_check',ROOT/'scripts/check_w1_contract.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def job(state):
    return check.read(check.CONTRACT_ROOT/f'examples/job-{state}.json')


def test_static_evidence_keeps_runtime_and_science_unexecuted():
    result=check.verify()
    assert result['expert_sources']==22
    assert result['runtime_execution']==result['scientific_execution']=='NOT_RUN'


@pytest.mark.parametrize('text',['{"a":1,"a":2}','{"x":NaN}','{"x":Infinity}','{"x":1e999}'])
def test_ambiguous_json_rejected(text):
    with pytest.raises(ValueError): check.strict_json(text)


@pytest.mark.parametrize('key,value',[
    ('finished_at',None),('exit_code',1),('artifacts',[]),('stop_reason','cancel'),
    ('usable_for_pipeline',True),('scientific_disposition','accepted'),
    ('tool_id','t01_phase1_mock_v01.tool.fake'),('node_id','N02'),
    ('updated_at','2026-09-04T00:00:00Z'),('created_at','yesterday')])
def test_false_success_and_identity_claims_rejected(key,value):
    data=job('succeeded');data[key]=value
    with pytest.raises(ValueError): check.validate_job(data)


@pytest.mark.parametrize('state',['cancelled','timed_out'])
def test_stopped_status_requires_confirmation(state):
    data=job(state);data['stop_confirmed']=False
    with pytest.raises(ValueError,match='stop'): check.validate_job(data)


def test_cancel_intent_cannot_be_overwritten_by_success():
    before=job('stop_requested');after=job('succeeded')
    with pytest.raises(ValueError,match='transition'): check.validate_transition(before,after)


def test_terminal_state_cannot_be_reopened():
    before=job('succeeded');after=job('running');after['revision']=before['revision']+1
    with pytest.raises(ValueError,match='transition'): check.validate_transition(before,after)


@pytest.mark.parametrize('field,value',[
    ('revision',9),('submission_sha256','a'*64),('execution_identity','another-process'),
    ('attempt_id','t01p1r-attempt-another'),('started_at','2026-09-05T00:00:00Z')])
def test_recovery_cannot_change_logical_request_or_restart_execution(field,value):
    before=job('reconciling');after=job('running');after['revision']=before['revision']+1
    after[field]=value
    with pytest.raises(ValueError): check.validate_transition(before,after)


def test_same_attempt_recovery_and_stop_are_valid_snapshot_edges():
    before=job('reconciling');after=job('running');after['revision']=before['revision']+1
    after['lease_epoch']=2
    check.validate_transition(before,after)
    before=job('stop_requested');after=job('cancelled')
    check.validate_transition(before,after)


@pytest.mark.parametrize('field,value',[('run_id','another-run'),('job_id','another-job'),('attempt_id','another-attempt'),
    ('evidence_kind','PIPELINE_REAL_OUTPUT')])
def test_result_artifacts_cannot_cross_execution_identity(field,value):
    data=job('succeeded');data['artifacts'][0][field]=value
    with pytest.raises(ValueError): check.validate_job(data)


def test_duplicate_artifacts_and_self_retry_rejected():
    data=job('succeeded');data['artifacts'].append(copy.deepcopy(data['artifacts'][0]))
    with pytest.raises(ValueError,match='Duplicate'): check.validate_job(data)
    data=job('succeeded');data['retry_of_job_id']=data['job_id']
    with pytest.raises(ValueError,match='retry'): check.validate_job(data)


@pytest.mark.parametrize('field,value',[('command',['echo','injected']),('path','C:/data/input'),
    ('run_mode','pipeline'),('node_id','N01')])
def test_submit_rejects_unregistered_execution_and_engineering_promotion(field,value):
    data=check.read(check.CONTRACT_ROOT/'examples/submit.json');data[field]=value
    with pytest.raises(ValueError): check.validate_submit(data)


def test_claimed_scientific_success_does_not_grant_production_authority():
    data=job('succeeded')
    data.update(tool_id='t01.real.deeptmhmm',node_id='N02',run_mode='pipeline',scientific_disposition='accepted',
                usable_for_pipeline=True,evidence_kind='PIPELINE_REAL_OUTPUT',rule_profile=data['execution_profile'])
    data['request_artifact']['evidence_kind']='LOCAL_INPUT'
    data['artifacts'][0]['evidence_kind']='PIPELINE_REAL_OUTPUT'
    check.validate_job(data)  # Shape is not authorization.
    with pytest.raises(ValueError,match='not approved'): check.check_consumption(data)


def test_source_tamper_and_escape_rejected(tmp_path):
    (tmp_path/'source').write_bytes(b'actual')
    with pytest.raises(ValueError,match='hash'):
        check.verify_source_files(tmp_path,[dict(path='source',bytes=6,sha256='0'*64)])
    for path in ['../source','C:/source','/source','x\\source']:
        with pytest.raises(ValueError,match='Unsafe'):
            check.verify_source_files(tmp_path,[dict(path=path,bytes=6,sha256='0'*64)])


def test_transition_time_compares_instants_across_offsets():
    before=job('running');after=job('succeeded')
    before['updated_at']='2026-09-05T08:00:01+08:00'
    check.validate_transition(before,after)
    before['updated_at']='2026-09-05T08:00:03+08:00'
    with pytest.raises(ValueError,match='backwards'): check.validate_transition(before,after)


def test_queued_cancellation_cannot_invent_an_execution():
    before=job('queued');after=job('cancelled');after['revision']=1
    with pytest.raises(ValueError,match='invented'): check.validate_transition(before,after)
    after.update(attempt_id=None,execution_identity=None,lease_epoch=0,started_at=None)
    check.validate_transition(before,after)


def test_pipeline_shape_rejects_fixture_input_even_when_not_consumable():
    data=job('running')
    data.update(tool_id='t01.real.deeptmhmm',node_id='N02',run_mode='pipeline',
        evidence_kind='PIPELINE_REAL_OUTPUT',rule_profile=data['execution_profile'])
    with pytest.raises(ValueError,match='Unqualified'): check.validate_job(data)


def test_terminal_job_must_resolve_disposition_without_claiming_science():
    data=job('succeeded');data['scientific_disposition']='pending'
    with pytest.raises(ValueError,match='pending'): check.validate_job(data)


@pytest.mark.parametrize('operation',['create_run','cancel','retry'])
def test_mutating_controls_require_idempotency_key(operation):
    data=dict(contract_version='0.1.0',operation=operation)
    if operation!='create_run': data['job_id']='t01p1r-job-example'
    with pytest.raises(ValueError,match='Schema'): check.schema_check(data,'control')


def test_mock_namespace_rejected_even_when_all_references_agree():
    data=job('succeeded');data['run_id']='t01p1m-run-example'
    data['request_artifact']['run_id']=data['run_id']
    data['artifacts'][0]['run_id']=data['run_id']
    with pytest.raises(ValueError,match='namespace'): check.validate_job(data)
