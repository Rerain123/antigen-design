"""Replay actual small native parallel output, plus corruption/coverage guards."""
import copy
import json
from pathlib import Path
import pytest
from t01_phase1_real.common import encode,decode,sha,RuntimeFault
from t01_phase1_real.development.foldx import parallel
from t01_phase1_real.development.foldx.result import result
from t01_phase1_real.development.variant_report.structures import validate
from test_foldx_development import recording
from test_foldx_scan_batches import finalize,zipped

ROOT=Path(__file__).resolve().parents[1]


def native():
    job,body,files,execution=copy.deepcopy(recording('buildmodel-three-variants-five-runs'))
    original=decode(files['output/runtime.json'])
    root=ROOT/'reports/n14-performance-20260928/production-worker-r01/output'
    assert (root/'runtime.json').is_file(), 'Required recorded native parallel fixture missing'
    files={n:v for n,v in files.items() if not n.startswith('output/')}
    files.update({'output/'+p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()})
    runtime=decode(files['output/runtime.json'])
    # Use the archived transport identity for isolated parser fault injection;
    # this test is not a fresh runtime deployment receipt.
    for k in ('network_interfaces','cpu_affinity'):
        runtime[k]=original[k]
    finalize(files,runtime)
    return job,body,files,execution,runtime


def test_all_native_rounds_and_pdbs_keep_exact_candidate_mapping():
    j,b,f,e,r=native();value=result(j,b,f,e)
    assert value['null_reason'] is None and len(value['variant_ddg'])==3
    assert len(validate(b,f))==31
    assert value['variant_ddg'][1]['native_ddg_runs']==[2.13256,2.45616,2.24278,2.61513,2.39109]
    assert value['variant_ddg'][1]['source'].startswith('output/buildmodel/batches/0002.zip!/')
    assert value['warnings'][0]['code']==parallel.MARKER


@pytest.mark.parametrize('fault',['candidate','command','hash','missing','extra','progress','plan','mutation','round','pdb'])
def test_corrupt_or_incomplete_parallel_output_never_publishes(fault):
    j,b,f,e,r=native();record=r['buildmodel_parallel'][0];name='output/'+record['archive']
    if fault=='candidate':record['variant_id']='wrong'
    elif fault=='command':record['argv'][-2]='--numberOfRuns=1'
    elif fault=='hash':record['sha256']='0'*64
    elif fault=='missing':del f[name]
    elif fault=='extra':f['output/buildmodel/batches/9999.zip']=f[name]
    elif fault=='progress':f['output/buildmodel-progress.json']=encode({})
    elif fault=='plan':f['output/buildmodel-plan.json']=encode({})
    else:
        members=parallel.unpack(f[name])
        if fault=='mutation':members['individual_list.txt']=b'AA1V;\n'
        elif fault=='round':del members['target_Repair_1_4.pdb']
        else:members['target_Repair_1_0.pdb']=b'corrupt structure'
        f[name]=zipped(members)
        record.update(sha256=sha(f[name]),size_bytes=len(f[name]),members=len(members),expanded_bytes=sum(map(len,members.values())))
    if fault!='progress':
        f['output/buildmodel-progress.json']=encode(dict(marker=parallel.MARKER,total=3,active=[],completed=r['buildmodel_parallel']))
    finalize(f,r)
    if fault=='pdb':
        with pytest.raises(RuntimeFault):validate(b,f)
    else:
        assert result(j,b,f,e)['null_reason']=='OUTPUT_INVALID'


def test_parallel_notice_is_visible_in_html_and_markdown_and_package():
    from t01_phase1_real.development.local_delivery import compute,policy
    from t01_phase1_real.service_api.user_report import render
    from test_local_delivery_development import body,verify_zip
    receipts={n:dict(state='missing') for n in policy.PRODUCERS};receipts.update(variant_report=dict(state='available'),dna=[])
    report=dict(outcome='ALL_EXCLUDED',records=[],engineering_adjustments=[dict(code=parallel.MARKER,message=parallel.NOTICE)])
    files={'input/source-receipts.json':encode(receipts),'input/variant_report-result.json':encode(dict(report=report))}
    data=compute.evaluate(body(),files)
    assert parallel.NOTICE in compute.readable(data).decode()
    assert parallel.NOTICE in render(data).decode()
    assert parallel.MARKER not in render(data).decode()  # Internal identifier stays in the raw package.
    assert verify_zip(compute.package(body(),files,data)['output/package.zip'])['variant_report']['engineering_adjustments']==report['engineering_adjustments']


def test_failed_parallel_attempt_keeps_notice_without_scores():
    j,b,f,e,r=native();e['error_code']='TIMEOUT'
    value=result(j,b,f,e)
    assert value['variant_ddg'] is None
    assert [w['code'] for w in value['warnings']]==[parallel.MARKER,'TIMEOUT']
