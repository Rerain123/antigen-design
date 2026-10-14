"""Actual-output corruption, provenance and token-observation regression checks."""
import json
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from b2_boundary_evidence import (BATCH, assess_bundle, check_complete_output,
    read, safe_id, validate_trace, verify_files)
from check_b2_boundaries import mutate, verify


@pytest.fixture
def bundle(tmp_path):
    source=BATCH/'runs/safe-id'
    folder=tmp_path/'bundle'
    folder.mkdir()
    for name in ['input.fasta','execution.json']:
        shutil.copyfile(source/name,folder/name)
    shutil.copytree(source/'output',folder/'output')
    sequence=(folder/'input.fasta').read_text().splitlines()[1]
    return folder,sequence,safe_id(sequence)


def test_actual_safe_id_roundtrip_and_unapproved_status(bundle):
    folder,sequence,identifier=bundle
    result=assess_bundle(folder,sequence,identifier)
    assert result['status']=='COMPLETE_RAW_ONLY'
    assert result['trace']['token_count']==53
    assert result['trace']['chunk_ranges_0based_half_open']==[[0,53]]
    assert result['probability']['rows']==51
    assert result['raw_record']['labels']=='I'*51
    assert result['usable_for_pipeline'] is False
    assert result['automatic_handoff'] is False
    assert result['scientific_signoff'] is None
    assert result['topology'] is None


@pytest.mark.parametrize('fault, diagnostic',[
    ('missing-prediction','MISSING_REQUIRED_OUTPUT'),('missing-regions','MISSING_REQUIRED_OUTPUT'),
    ('missing-probability','MISSING_REQUIRED_OUTPUT'),('missing-plot','MISSING_REQUIRED_OUTPUT'),
    ('missing-report','MISSING_REQUIRED_OUTPUT'),('truncated-labels','Label length mismatch'),
    ('wrong-sequence','Input/output sequence or ID mismatch'),('wrong-id','Input/output sequence or ID mismatch'),
    ('wrong-region','Region/label disagreement'),('nan-probability','Invalid probability value'),
    ('wrong-probability-position','Probability position/AA mismatch'),('hash-tamper','ARTIFACT_HASH'),
    ('unexpected-artifact','UNDECLARED_ARTIFACT'),('invalid-plot','INVALID_PLOT_SIGNATURE'),
    ('wrong-report-id','REPORT_ID_MISMATCH'),('missing-token-trace','No such file'),
    ('wrong-token','TOKEN_RECONSTRUCTION_MISMATCH'),
])
def test_actual_output_corruption_is_diagnosed_and_not_consumable(bundle,fault,diagnostic):
    folder,sequence,identifier=bundle
    mutate(folder,fault,identifier)
    result=assess_bundle(folder,sequence,identifier)
    assert result['status']=='REJECTED'
    assert diagnostic in result['diagnostics'][0]['message']
    assert result['raw_record'] is None and result['topology'] is None
    assert result['usable_for_pipeline'] is False and result['requires_review'] is True


@pytest.mark.parametrize('field,value',[
    ('container_exit_code',1),('container_exit_code',137),('stopped_confirmed',False),
    ('timed_out',True),('oom_killed',True),
])
def test_failed_or_running_process_cannot_reuse_complete_output(bundle,field,value):
    folder,sequence,identifier=bundle
    execution=read(folder/'execution.json');execution[field]=value
    (folder/'execution.json').write_text(json.dumps(execution))
    assert (folder/'output/result/predicted_topologies.3line').is_file()
    result=assess_bundle(folder,sequence,identifier)
    assert result['status']=='REJECTED' and result['raw_record'] is None
    assert 'EXECUTION_FAILED_OR_NOT_STOPPED' in result['diagnostics'][0]['message']


def test_input_bytes_cannot_be_rebound_with_same_safe_identifier(bundle):
    folder,sequence,identifier=bundle
    (folder/'input.fasta').write_text('>'+identifier+'\n'+sequence+'A\n')
    assert 'EXECUTION_INPUT_HASH_MISMATCH' in assess_bundle(folder,sequence,identifier)['diagnostics'][0]['message']


@pytest.mark.parametrize('identifier',['../escape','name|alias','t01seq_'+'0'*64])
def test_nonbinding_or_unsafe_identifier_rejected_before_output_lookup(bundle,identifier):
    folder,sequence,_=bundle
    with pytest.raises(ValueError,match='UNSAFE_OR_NONBINDING_ID'):
        check_complete_output(folder/'output',sequence,identifier)


@pytest.mark.parametrize('name',['../escape','/absolute','C:/escape','a\\b','a//b'])
def test_artifact_inventory_rejects_path_aliases(tmp_path,name):
    with pytest.raises(ValueError,match='UNSAFE'):
        verify_files(tmp_path,[dict(path=name,sha256='0'*64,size_bytes=0)])


@pytest.mark.parametrize('change, diagnostic',[
    ('count','TOKEN_COUNT_MISMATCH'),('chunk-start','CHUNK_POSITION_GAP_OR_OVERLAP'),
    ('chunk-token','CHUNK_TOKEN_MISMATCH'),('nonfinite','INVALID_CHUNK_REPRESENTATION'),
    ('embedding-length','INVALID_EMBEDDING_SHAPE_OR_VALUES'),('missing-embedding','MISSING_TOKEN_OR_EMBEDDING_OBSERVATION'),
])
def test_raw_token_observations_require_full_consistent_coverage(bundle,change,diagnostic):
    folder,sequence,_=bundle
    events=[json.loads(line) for line in (folder/'output/token_trace.jsonl').read_text().splitlines()]
    token=events[0];chunk=next(e for e in events if e['event']=='chunk_completed')
    if change=='count':token['token_count']+=1
    elif change=='chunk-start':chunk['start']=1
    elif change=='chunk-token':chunk['token_ids'][0]=99
    elif change=='nonfinite':chunk['finite']=False
    elif change=='embedding-length':events[-1]['shape'][0]-=1
    else:events=events[:-1]
    with pytest.raises(ValueError,match=diagnostic): validate_trace(events,sequence)


def test_plan_keeps_short_inputs_and_long_token_limits_out_of_scientific_approval():
    plan=read(BATCH/'plan.json')
    lengths={len(r['sequence']) for r in plan['cases'] if r['kind']=='SYNTHETIC_LENGTH_FIXTURE'}
    assert lengths=={1,8,9,29,30,1020,1021,1022,1023}
    assert plan['stage']=='W1-08B2_SUPPLEMENTAL_DEVELOPMENT_EVIDENCE'
    assert plan['scientific_signoff'] is None and plan['production_enabled'] is False
    assert plan['limits']['parallel_models']==1 and plan['limits']['timeout_seconds']==900


def test_original_star_acceptance_is_not_project_input_support():
    from b2_review_contract import input_findings
    row=next(r for r in read(BATCH/'plan.json')['cases'] if r['id']=='invalid-symbol')
    folder=BATCH/'runs/invalid-symbol'
    assert row['outcome']=='EXPECT_EXECUTION_FAILURE'  # The unmet expectation is preserved.
    assert read(folder/'execution.json')['container_exit_code']==0
    events=[json.loads(line) for line in (folder/'output/token_trace.jsonl').read_text().splitlines()]
    assert events[0]['decoded_tokens'][-2]=='<unk>' and events[0]['token_ids'][-2]==3
    assert input_findings(row['sequence'])==['INVALID_SEQUENCE_SYMBOL']
    result=assess_bundle(folder,row['sequence'],row['internal_id'])
    assert result['status']=='REJECTED'
    assert result['diagnostics'][0]['message']=='TOKEN_RECONSTRUCTION_MISMATCH'
    assert result['usable_for_pipeline'] is False and result['topology'] is None


def test_sealed_boundary_execution_evidence():
    if not (BATCH/'manifest.json').exists():
        pytest.skip('Campaign has not yet been sealed')
    result=verify(BATCH)
    assert result['real_invocations']==13 and result['artifact_faults_rejected']==17
    assert result['production_status']=='NOT_DEPLOYED'
