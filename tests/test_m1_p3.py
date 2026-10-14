import copy
import importlib.util
import sys
from pathlib import Path
import pytest
from t01_phase1_real.common import RuntimeFault, decode, encode
from t01_phase1_real.development.local_delivery import m1, compute
from test_local_delivery_development import body, verify_zip


def delivery_files():
    receipts={n:dict(state='missing') for n in ('wt_draft','variant_report','wt_reference')}
    receipts.update(variant_report=dict(state='available'),dna=[])
    report=dict(outcome='ALL_EXCLUDED',records=[dict(id='sample-1',disposition='EXCLUDED',exclusion_reasons=[])],
                ranked_candidates=None,pareto_front=None,best_candidate=None,m1_test=dict(records=[]))
    return {'input/source-receipts.json':encode(receipts),
            'input/variant_report-result.json':encode(dict(report=report)),
            'input/m1-p3-scans.json':encode(dict(verified_scan_jobs=2,engines={}))}


def test_all_excluded_n16_and_preview_zip():
    files=delivery_files();request=body();request['host_species']='Homo sapiens'
    data=compute.evaluate(request,files)
    assert data['n16']['reason_code']=='NO_QUALIFIED_CANDIDATE'
    assert data['n16']['dna'] is None and data['n16']['expression_host'] is None
    assert data['agent_c_preview']['sent'] is False and data['agent_c_preview']['payload'] is None
    assert data['scientific_release_gate']=='CLOSED' and data['usable_for_pipeline'] is False
    assert verify_zip(compute.package(request,files,data)['output/package.zip'])==data


def test_missing_new_scans_and_false_exclusion_rejected():
    files=delivery_files();del files['input/m1-p3-scans.json']
    with pytest.raises(RuntimeFault):compute.evaluate(body(),files)
    files=delivery_files();r=decode(files['input/variant_report-result.json'])
    r['report']['records'][0]['disposition']='UNDETERMINED'
    files['input/variant_report-result.json']=encode(r)
    with pytest.raises(RuntimeFault):compute.evaluate(body(),files)


def test_scope_only_explicit_open_covered_and_not_protected():
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'scripts'))
    from run_m1_p3_probe import scope,read
    p=root/'discovery/t01-phase1-real/m1-p1-20260921/r01'
    structure=read(p/'structure.json');topology=read(p/'topology.json');constraints=read(p/'design.json')['request']['constraints']
    selected=scope(structure,topology,constraints)
    assert selected['scan_positions']==[3] and selected['excluded_positions']==[1,2,76]
    constraints=copy.deepcopy(constraints);constraints['open_positions']=[1,2,76]
    with pytest.raises(AssertionError):scope(structure,topology,constraints)


def test_actual_resident_scan_receipts_and_scope_rejections():
    from types import SimpleNamespace
    root=Path(__file__).resolve().parents[1]/'discovery/t01-phase1-real'
    rows={}
    for folder in ('m1-p1-20260921/r01','m1-p2-20260921/r01','m1-p3-20260922/r01'):
        for path in (root/folder).glob('*.json'):
            value=decode(path.read_bytes())
            if isinstance(value,dict) and value.get('job') and value.get('request'):
                rows[value['job']['job_id']]=value
    p2=decode((root/'m1-p2-20260921/r01/final-report.json').read_bytes())
    ref=decode((root/'m1-p3-20260922/r01/wt-reference.json').read_bytes())
    rt=SimpleNamespace(_job=lambda db,jid:rows[jid]['job'],
        _request_bytes=lambda job:encode(rows[job['job_id']]['request']),result=lambda jid:rows[jid]['result'])
    request=dict(upstream=dict(variant_report=dict(job_id=p2['job']['job_id'])))
    files={'input/variant_report-request.json':encode(p2['request']),
           'input/wt_reference-request.json':encode(ref['request'])}
    values=dict(variant_report=p2['result'],wt_reference=ref['result'])
    m1.scan_facts(rt,None,request,files,values)
    facts=decode(files['input/m1-p3-scans.json'])
    assert facts['verified_scan_jobs']==2
    assert facts['engines']['thermompnn']['native_prediction_count']==1520
    assert facts['engines']['foldx']['displayed_positions']==[3]
    jid=ref['request']['upstream']['foldx']['job_id'];original=copy.deepcopy(rows[jid])
    for change in ('protected_scope','missing_exclusions','old_scan','no_offline_receipt'):
        rows[jid]=copy.deepcopy(original)
        if change=='protected_scope':rows[jid]['request']['scan_positions']=[2]
        elif change=='missing_exclusions':rows[jid]['request']['fixed_positions']=[]
        elif change=='old_scan':rows[jid]['job']['started_at']='2000-01-01T00:00:00Z'
        else:rows[jid]['result']['execution']['resident_observation'].pop('network_restriction')
        with pytest.raises(RuntimeFault):m1.scan_facts(rt,None,request,files,values)


def test_export_rejects_hash_and_existing_bytes_mismatch(tmp_path):
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'scripts'))
    from audit_m1_p3 import write_verified,AUDIT
    from t01_phase1_real.common import sha
    import base64
    compile(AUDIT,'p3-audit','exec')
    item=dict(data=base64.b64encode(b'valid').decode(),artifact=dict(size_bytes=5,sha256=sha(b'valid')))
    path=tmp_path/'artifact.bin';assert write_verified(path,item)==b'valid'
    bad=copy.deepcopy(item);bad['artifact']['sha256']='0'*64
    with pytest.raises(AssertionError):write_verified(path,bad)
    path.write_bytes(b'corrupt')
    with pytest.raises(AssertionError):write_verified(path,item)


@pytest.mark.parametrize('change',['different_self','duplicate_mutant','reference_not_first'])
def test_native_foldx_reference_and_self_are_distinct_observations(change):
    from test_foldx_development import recording
    from t01_phase1_real.development.foldx.result import _positionscan,AA3
    _,_,files,_=recording('positionscan-two-positions')
    payload=decode(files['native/payload.json']);runtime=decode(files['output/runtime.json'])
    name=next(n for n in files if n.endswith('_scanning_output.txt'))
    lines=files[name].decode().splitlines();mp=payload['position_mapping'][0]
    token=AA3[mp['wt']]+mp['chain']+str(mp['pdb_resseq'])+mp['wt']
    indexes=[i for i,line in enumerate(lines) if line.split('\t')[0]==token]
    assert len(indexes)==2
    if change=='different_self':lines[indexes[-1]]=token+'\t0.00261674'
    elif change=='duplicate_mutant':lines.append(next(line for line in lines if not line.startswith(token+'\t')))
    else:lines[0],lines[1]=lines[1],lines[0]
    files=dict(files);files[name]=('\n'.join(lines)+'\n').encode()
    if change!='different_self':
        with pytest.raises(RuntimeFault):_positionscan(payload,runtime,files)
    else:
        rows,_=_positionscan(payload,runtime,files)
        row=next(r for r in rows if r['position']==mp['position'] and r['mut']==mp['wt'])
        assert row['ddg_foldx']==row['native_wt_self_ddg']==0.00261674
        assert row['native_wt_reference_ddg']==0
