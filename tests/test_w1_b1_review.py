"""Review contract negative tests; fixtures never become scientific qualification."""
import copy
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import check_w1_b1_review as check


def pair(name='map'):
    raw=(check.CONTRACT/'examples'/(name+'-request.json')).read_bytes()
    return check.strict_json(raw),check.read(check.CONTRACT/'examples'/(name+'-result.json')),raw


def test_prepared_evidence_and_actual_reparse():
    result=check.verify(reparse=True)
    assert result['case_count']==23 and result['production_status']=='NOT_DEPLOYED'


@pytest.mark.parametrize('field,value',[
    ('host_species','  '),('protein_sequence','aRg'),('protein_sequence','AR G'),('protein_sequence',''),
    ('protein_sequence_sha256','0'*64),('inventory_artifact',None),('run_id','t01p1m-run-example'),
    ('command','fetch online'),('structure_artifact',None),('contract_status','APPROVED')])
def test_invalid_requests_and_scientific_promotion_rejected(field,value):
    request,_,_=pair();request[field]=value
    with pytest.raises(ValueError): check.validate_request(request)


@pytest.mark.parametrize('ref_field,field,value',[
    ('structure_artifact','run_id','t01p1r-run-other'),('inventory_artifact','attempt_id','t01p1r-attempt-other'),
    ('structure_artifact','role','result'),('inventory_artifact','job_id',None)])
def test_cross_scope_and_incomplete_producer_rejected(ref_field,field,value):
    request,_,_=pair();request[ref_field][field]=value
    if field=='attempt_id': request[ref_field]['job_id']=None
    with pytest.raises(ValueError): check.validate_request(request)


@pytest.mark.parametrize('field,value',[
    ('usable_for_pipeline',True),('mapping_status','verified'),('review_required',False),
    ('scientific_disposition','accepted'),('outcome','parsed'),('error_code','PARSE_FAILED'),
    ('unresolved_metadata',dict(source='user_experimental',missing_atom_fraction=0,plddt=.9))])
def test_results_cannot_claim_science_or_confuse_ingestion(field,value):
    request,result,raw=pair();result[field]=value
    with pytest.raises(ValueError): check.validate_result(result,request,raw)


@pytest.mark.parametrize('field', ['run_id','request_id','job_id','attempt_id','request_sha256','sequence_sha256','structure_sha256'])
def test_result_wrong_binding_rejected(field):
    request,result,raw=pair()
    result['binding'][field]='0'*64 if field.endswith('sha256') else 't01p1r-'+field.replace('_id','')+'-different'
    with pytest.raises(ValueError): check.validate_result(result,request,raw)


def test_same_logical_json_different_bytes_not_same_request():
    request,result,raw=pair()
    with pytest.raises(ValueError,match='byte'): check.validate_result(result,request,raw+b' ')


def test_ingestion_auto_is_not_mapping_approval():
    request,result,raw=pair('ingest')
    assert check.validate_result(result,request,raw)['mapping_status'] is None
    result['mapping_status']='unverified'
    with pytest.raises(ValueError): check.validate_result(result,request,raw)


def test_rejected_result_has_no_normal_output():
    request,result,raw=pair()
    result.update(outcome='rejected',output_artifact=None,mapping_status=None,error_code='INPUT_UNSUPPORTED')
    check.validate_result(result,request,raw)
    result['output_artifact']=pair()[1]['output_artifact']
    with pytest.raises(ValueError): check.validate_result(result,request,raw)


def test_tampered_scientific_claim_in_recorded_case(tmp_path):
    batch=tmp_path/'evidence';shutil.copytree(check.BATCH,batch)
    path=batch/'results/B103-pdb-icode/mapping.json'
    data=check.read(path);data['mapping_status']='verified'
    path.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError,match='hash'): check.verify(batch)


@pytest.mark.parametrize('path',['../escape','/absolute','C:/outside','a\\b'])
def test_evidence_manifest_path_escape(path):
    with pytest.raises(ValueError): check.local_path(check.BATCH,path)
