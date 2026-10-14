"""B2 review contract failure semantics and independent raw/source consistency checks."""
import copy
import json
from pathlib import Path
import sys

import pytest
from jsonschema.exceptions import ValidationError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from b2_review_contract import CONTRACT,BATCH,read,sha,make_request,make_result,raw_record,validate_request,validate_result,input_findings,replay_case,load_original
from check_w1_b2_review import check_examples,check_reference_inventory,reference_comparison


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()


@pytest.fixture
def normal_pair():
    request=make_request('unit','A'*12,'user | ../../metadata only')
    data=encoded(request)
    raw=raw_record(request['internal_sequence_id'],request['protein_sequence'],'IIIMMOOOOSSS','SP+TM')
    return request,data,make_result(request,data,raw=raw)


def test_all_predeclared_literal_cases():
    rows=check_examples()
    assert len(rows)==20 and all(r['status']=='PASS' for r in rows)


@pytest.mark.parametrize('sequence,findings',[
    ('',['EMPTY_SEQUENCE']),('aCDEFGHIK',['SEQUENCE_NOT_NORMALIZED']),('ACDE FGHI',['SEQUENCE_NOT_NORMALIZED']),
    ('ACDEFGHI*',['INVALID_SEQUENCE_SYMBOL']),('ACDEFGHI-',['INVALID_SEQUENCE_SYMBOL']),
    ('ACDEFGHIＡ',['INVALID_SEQUENCE_SYMBOL']),('AAAAAAAA',['UPSTREAM_DEFAULT_LENGTH_GUARD']),
    ('AAAAAAAAA',[]),('A'*29,[]),('A'*30,[]),('A'*991,[]),('A'*992,['LENGTH_BEYOND_RECORDED_SAMPLES']),
    ('ACDEFGHIX',['NON_AA20_REQUIRES_REVIEW']),('ACDEFGHIO',['NON_AA20_REQUIRES_REVIEW']),
    ('ACDEFGHIU',['NON_AA20_REQUIRES_REVIEW']),('ACDEFGHIB',['NON_AA20_REQUIRES_REVIEW']),
    ('ACDEFGHIZ',['NON_AA20_REQUIRES_REVIEW']),('ACDEFGHIJ',['NON_AA20_REQUIRES_REVIEW']),
])
def test_declared_input_review_boundaries(sequence,findings):
    assert input_findings(sequence)==findings


def test_safe_internal_id_does_not_use_original_label(normal_pair):
    request,data,result=normal_pair
    validate_result(result,request,data)
    assert request['internal_sequence_id']=='t01seq_'+sha(b'A'*12)
    assert request['user_sequence_id']=='user | ../../metadata only'
    assert result['id_pairing']=='SAFE_INTERNAL_ID'
    assert result['usable_for_pipeline'] is False


@pytest.mark.parametrize('field,value',[
    ('internal_sequence_id','../../escape'),('internal_sequence_id','t01seq_'+'0'*64),
    ('protein_sequence_sha256','0'*64),('profile_sha256','0'*64),('profile_id','another-profile'),
    ('structure_artifact',{}),('command','predict.py'),('protein_sequence',['ACDEFGHIK']),
])
def test_bad_request_cannot_enter_review_pair(normal_pair,field,value):
    request,_,_=normal_pair
    request[field]=value
    with pytest.raises((ValueError,ValidationError)):
        validate_request(request)


@pytest.mark.parametrize('field', ['run_id','request_id','request_sha256','sequence_sha256','profile_sha256'])
def test_cross_request_attempt_binding(normal_pair,field):
    request,data,result=normal_pair
    result['binding'][field]='0'*64 if field.endswith('sha256') else 't01p1r-run-other'
    with pytest.raises((ValueError,ValidationError)):
        validate_result(result,request,data)


def test_exact_request_bytes_are_not_reconstructed(normal_pair):
    request,data,result=normal_pair
    with pytest.raises(ValueError,match='binding'):
        validate_result(result,request,data+b' ')


@pytest.mark.parametrize('mutation', ['tm_count','outside_length','has_signal','segments','labels','signal_boundary'])
def test_scientific_array_and_counts_do_not_pass_schema_alone(normal_pair,mutation):
    request,data,result=normal_pair
    t=result['topology']
    if mutation=='tm_count': t['tm_count']=2
    elif mutation=='outside_length': t['outside_length']=5
    elif mutation=='has_signal': t['has_signal']=False
    elif mutation=='segments': t['segments'][0]['end']=4
    elif mutation=='labels': t['labels']=t['labels'][:-1]
    else: t['segments'][-1]['start']=9
    with pytest.raises(ValueError,match='disagreement'):
        validate_result(result,request,data)


@pytest.mark.parametrize('labels,kind', [('PPPOOOOOO','GLOB'),('BBBOOOOOO','BETA'),('SSPPBBOOO','BETA')])
def test_p_or_b_guard_is_driven_by_labels_and_keeps_all_positions(labels,kind):
    request=make_request('pb','A'*9);data=encoded(request)
    raw=raw_record(request['internal_sequence_id'],request['protein_sequence'],labels,kind)
    result=make_result(request,data,raw=raw)
    validate_result(result,request,data)
    assert result['topology'] is None and result['null_reason']=='PB_OUT_OF_DOMAIN'
    assert result['raw_record']['labels']==labels and len(result['raw_record']['labels'])==9
    assert result['automatic_handoff'] is False and result['interpretation_status']=='unreliable'
    assert result['warnings'][0]['level']=='failure'


@pytest.mark.parametrize('mutation', ['map_p_inside','drop_b','no_warning','auto_handoff','false_pipeline','false_signoff'])
def test_pb_cannot_be_silently_accepted(mutation):
    request=make_request('pb','A'*9);data=encoded(request)
    result=make_result(request,data,raw=raw_record(request['internal_sequence_id'],'A'*9,'PPPBBOOOO','BETA'))
    if mutation=='map_p_inside': result['raw_record']['labels']='IIIBBOOOO'
    elif mutation=='drop_b': result['raw_record']['labels']='PPPOOOO'
    elif mutation=='no_warning': result['warnings']=[]
    elif mutation=='auto_handoff': result['automatic_handoff']=True
    elif mutation=='false_pipeline': result['usable_for_pipeline']=True
    else: result['scientific_signoff']='approved'
    with pytest.raises((ValueError,ValidationError)):
        validate_result(result,request,data)


@pytest.mark.parametrize('reason',['TOOL_UNAVAILABLE','TOOL_FAILED','INVALID_OUTPUT','TIMED_OUT','CANCELLED'])
def test_failure_nulls_do_not_invent_labels(reason):
    request=make_request('failure','ACDEFGHIK');data=encoded(request)
    result=make_result(request,data,failure=reason)
    validate_result(result,request,data)
    assert result['topology'] is None and result['raw_record'] is None
    assert result['null_reason']==reason and result['interpretation_status']=='unreliable'
    if reason=='TOOL_UNAVAILABLE': assert result['warnings'][0]['message']=='拓扑预测不可用'
    result['topology']=dict(labels=['outside']*9,segments=[dict(type='outside',start=1,end=9)],tm_count=0,outside_length=9,has_signal=False)
    with pytest.raises(ValueError): validate_result(result,request,data)


@pytest.mark.parametrize('kind,labels',[('GLOB','MMMMIIIII'),('BETA','IIIOOOOOO'),('SP','IIIOOOOOO'),('UNKNOWN','IIIIIIIII')])
def test_type_label_disagreement_is_invalid_output(kind,labels):
    with pytest.raises(ValueError): raw_record('id','A'*9,labels,kind)


def test_real_raw_replay_preserves_original_id_and_exposes_guard():
    records=replay_case('coverage')
    assert len(records)==9
    beta=[r for r in records if r['type']=='BETA']
    assert len(beta)==2 and all('P' in r['labels'] and 'B' in r['labels'] for r in beta)
    assert all(r['raw_tmr_count']>0 and not any(s['label']=='M' for s in r['segments']) for r in beta)


def test_forged_raw_replay_detected_even_when_its_array_is_self_consistent():
    pair=read(BATCH/'execution/assessment.json')['replay_cases'][0]
    request_bytes=(ROOT/pair['request']['path']).read_bytes();request=json.loads(request_bytes)
    result=read(ROOT/pair['result']['path'])
    n=len(request['protein_sequence'])
    forged=raw_record(request['user_sequence_id'],request['protein_sequence'],'O'*n,'GLOB')
    candidate=make_result(request,request_bytes,raw=forged,evidence_kind='G0_RAW_REPLAY',raw_artifacts=result['raw_artifacts'])
    with pytest.raises(ValueError,match='actual source'):
        validate_result(candidate,request,request_bytes)


def test_duplicate_or_unsafe_replay_refs_are_rejected():
    pair=read(BATCH/'execution/assessment.json')['replay_cases'][0]
    request_bytes=(ROOT/pair['request']['path']).read_bytes();request=json.loads(request_bytes)
    result=read(ROOT/pair['result']['path'])
    result['raw_artifacts'].append(copy.deepcopy(result['raw_artifacts'][0]))
    with pytest.raises(ValueError,match='Duplicate'): validate_result(result,request,request_bytes)
    result['raw_artifacts'].pop();result['raw_artifacts'][0]['path']='../outside'
    with pytest.raises(ValueError,match='Unsafe'): validate_result(result,request,request_bytes)


def test_annotation_reference_is_not_an_approved_training_holdout():
    inventory=check_reference_inventory()
    assert len(inventory['public_annotations'])==4 and inventory['approved_independent_holdouts']==0
    assert all(row['independent_of_new_parser'] and not row['accepted_scientific_holdout'] for row in inventory['public_annotations'])


@pytest.mark.parametrize('text', ['>a | GLOB\nAA\nI','>a | GLOB\nAA\nIX','>a | GLOB\nAC\nII','>b | GLOB\nAA\nII',
    '>a | GLOB\nAA\nII\n>a | GLOB\nAA\nII','>a | UNKNOWN\nAA\nII'])
def test_partial_foreign_duplicate_and_bad_raw_outputs(text):
    with pytest.raises(ValueError): load_original('audit_raw').three_line(text,{'a':'AA'})


def test_region_coordinates_and_raw_tmr_count_cannot_override_labels():
    audit=load_original('audit_raw');records=audit.three_line('>a | TM\nAAAA\nIMMO',{'a':'AAAA'})
    text='##gff-version 3\n# a Length: 4\n# a Number of predicted TMRs: 2\na\tinside\t1\t1\t\t\t\t\na\tTMhelix\t2\t3\t\t\t\t\na\toutside\t4\t4\t\t\t\t\n'
    with pytest.raises(ValueError,match='count'): audit.region_table(text,records)


def test_scientific_release_does_not_depend_on_b1_and_has_explicit_requirements():
    acceptance=read(CONTRACT/'acceptance.json')
    assert 'B1 structure scientific mapping' in acceptance['independent_of']
    assert len(acceptance['release_requirements'])==6
    assert acceptance['scientific_signoff'] is None and not acceptance['production_enabled']


def test_sealed_review_evidence():
    from check_w1_b2_review import verify
    if not (BATCH/'manifest.json').exists(): pytest.skip('Review batch not sealed yet')
    result=verify()
    assert result['replayed_records']==11 and result['model_executions_this_task']==0
