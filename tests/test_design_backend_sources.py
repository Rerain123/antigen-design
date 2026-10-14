"""Source availability, partial geometry and audit integrity regressions."""
import copy
import importlib.util
from pathlib import Path
import shutil
import sys
import pytest
from t01_phase1_real.common import REPO,RuntimeFault,encode,decode,sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.design_backend import policy,service
from t01_phase1_real.development.design_backend.compute import evaluate
from t01_phase1_real.development.glycosylation import policy as n07
from test_design_backend_development import request,calculate,atoms,record,scales


@pytest.mark.parametrize('status',['missing','pending','failed','available'])
def test_registered_source_state_is_never_inferred_from_nulls(tmp_path,status):
    rt=Runtime(tmp_path);body=request();upbody=dict(protein_sequence=body['protein_sequence'],user_sequence_id='source',timeout_seconds=5,
        hotspot_input=dict(state='not_provided',source=None,hotspots=None,reason_code=None))
    if status!='missing':
        job=rt.submit_sequence(encode(upbody),'up',n07.TOOL)
        if status in ('failed','available'):
            rt._development_fault='compute_failure' if status=='failed' else None
            rt.dispatch(job['job_id']);rt._development_fault=None;job=rt.get(job['job_id'])
        refs=[r for r in job['artifacts'] if r['role'] in ('result','diagnostic')]
        body['upstream']['glycosylation']=dict(job_id=job['job_id'],artifact=refs[0] if refs else None)
    new=rt.submit_sequence(encode(body),'audit',policy.TOOL);rt.dispatch(new['job_id']);value=rt.result(new['job_id'])
    assert value['source_receipts']['glycosylation']['state']==status
    assert not value['audit']['permissions']['open_positions']


def test_missing_sidechain_atoms_block_minimum_atom_distance_without_disabling_cb_pairs():
    coords=atoms(0,2);coords['2']['missing_heavy_atoms']=['CG']
    result=calculate('AA','GA',coords,[dict(start=2,end=2)],[])
    assert result['values']['functional_proximity'] is None
    assert result['engineering_thresholds']['aggregate_exceeded'] is None
    result=calculate('AA','GG',coords,[],[])
    assert result['values']['spatial_clustering']==1. and result['values']['epistasis_risk']=='MEDIUM'


def test_declared_diff_corruption_rejected_even_if_count_unchanged():
    from t01_phase1_real.development.design_backend.burden import compute
    row=record('AA','AG');row['mutations'][0]['position']=1
    with pytest.raises(RuntimeFault):compute('AA',row,dict(residues=None),None,None,'general',scales())


@pytest.mark.parametrize('status',['no_exact_match','ambiguous','hit'])
def test_domain_lookup_unknown_does_not_turn_into_measured_empty(status,tmp_path):
    rt=Runtime(tmp_path);body=request();job=rt.submit_sequence(encode(body),'base',policy.TOOL);rt.dispatch(job['job_id']);value=rt.result(job['job_id'])
    files={r['path']:rt.artifact_bytes(job['job_id'],r['artifact']['artifact_id']) for r in value['raw_artifacts']}
    receipts=decode(files['input/source-receipts.json']);receipts['domains'].update(state='available')
    files['input/source-receipts.json']=encode(receipts)
    files['input/domains-result.json']=encode(dict(analysis=dict(functional_domains=[],core_map=None,lookup=dict(status=status),review_reasons=[])))
    result=evaluate(body,files)
    assert result['domain_intervals']==([] if status=='hit' else None)


@pytest.fixture
def audit_module():
    spec=importlib.util.spec_from_file_location('design_audit_script',REPO/'scripts/audit_design_backend_evidence.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


@pytest.mark.parametrize('damage',['file','snapshot','profile'])
def test_independent_auditor_rejects_changed_evidence_before_recomputation(tmp_path,monkeypatch,audit_module,damage):
    batch=tmp_path/'batch';batch.mkdir();source=batch/'source/scripts/audit_design_backend_evidence.py';source.parent.mkdir(parents=True)
    source.write_bytes((REPO/'scripts/audit_design_backend_evidence.py').read_bytes())
    data=batch/'fact.json';data.write_bytes(b'{}')
    index=dict(status='PASS',profile=policy.registered_profile(),files=[dict(path='fact.json',bytes=2,sha256=sha(b'{}'))])
    if damage=='file':data.write_bytes(b'BAD')
    elif damage=='snapshot':source.write_bytes(b'changed')
    else:index['profile']['sha256']='0'*64
    (batch/'index.json').write_bytes(encode(index));output=tmp_path/'audit.json'
    monkeypatch.setattr(sys,'argv',['audit','--batch',str(batch),'--output',str(output)])
    with pytest.raises(AssertionError):audit_module.main()
    assert not output.exists()
