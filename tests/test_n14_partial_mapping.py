"""Synthetic partial-mapping fault injection into archived bytes; no native execution."""
import copy
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_foldx_development import recording
from t01_phase1_real.common import decode,encode,sha,RuntimeFault
from t01_phase1_real.development.foldx import result as module


def partial():
    job,body,files,execution=copy.deepcopy(recording('buildmodel-three-variants-five-runs'))
    payload=decode(files['native/payload.json'])
    bad=dict(variant_id='synthetic-unmappable',tokens=[],mapping_failed=True,mapping_failed_positions=[1])
    payload['variants'].insert(1,bad);payload['mapping_failures']=[dict(position=1,mapping_failed=True)]
    body['variants'].insert(1,dict(variant_id=bad['variant_id'],mutations=copy.deepcopy(body['variants'][0]['mutations'])))
    files['native/payload.json']=encode(payload);files['input.json']=encode(body)
    runtime=decode(files['output/runtime.json']);runtime['input_sha256']=sha(files['input.json'])
    files['output/runtime.json']=encode(runtime)
    job['request_artifact']['sha256']=sha(files['input.json'])
    return job,body,files,execution


def test_partial_batch_keeps_exact_native_ids_and_five_runs():
    job,body,files,execution=partial();value=module.result(job,body,files,execution)
    assert value['status']=='buildmodel_unreviewed'
    assert [r['variant_id'] for r in value['variant_ddg']]==[r['variant_id'] for r in body['variants'] if r['variant_id']!='synthetic-unmappable']
    assert all(r['runs']==5 and len(r['native_ddg_runs'])==5 for r in value['variant_ddg'])
    assert value['mapping_skipped_variants']==[dict(variant_id='synthetic-unmappable',positions=[1])]
    from t01_phase1_real.development.variant_report.structures import validate
    checked=validate(body,files)
    assert len(checked)==31 and not any(r.get('variant_id')=='synthetic-unmappable' for r in checked.values())


def test_partial_mapping_never_bypasses_native_pdb_validation():
    from t01_phase1_real.development.variant_report.structures import validate
    _,body,files,_=partial()
    files['output/buildmodel/target_Repair_2_0.pdb']=b'corrupted'
    with pytest.raises(RuntimeFault):validate(body,files)


def test_legacy_all_batch_mapping_skip_remains_missing():
    _,body,files,_=partial();runtime=decode(files['output/runtime.json']);runtime['tool_invoked']=False
    files['output/runtime.json']=encode(runtime)
    result=module.parse(body,files)
    assert result['status']=='unreliable_mapping' and result['rows']==[]


@pytest.mark.parametrize('all_bad',[False,True])
def test_worker_invokes_buildmodel_only_for_mappable_candidates(tmp_path,monkeypatch,all_bad):
    from t01_phase1_real.development.foldx import worker
    _,_,files,_=partial();payload=decode(files['native/payload.json'])
    if all_bad:
        payload['variant_lines']=[]
        for r in payload['variants']:r['mapping_failed']=True
    native=tmp_path/'native';native.mkdir();(native/'payload.json').write_bytes(encode(payload))
    out=tmp_path/'out';out.mkdir();calls=[]
    def paths(p):return tmp_path/str(p).lstrip('/')
    def run(argv,*args):
        calls.append(argv)
        if '--command=RepairPDB' in argv:(out/'repair/target_Repair.pdb').write_bytes(b'test repaired')
        if '--command=BuildModel' in argv:
            from t01_phase1_real.development.foldx.scan_batches import model_names
            for name in model_names(1):(Path(args[0])/name).write_bytes(b'ENGINEERING PDB FIXTURE')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(worker,'Path',paths);monkeypatch.setattr(worker,'OUT',out)
    monkeypatch.setattr(worker,'filehash',lambda *a:'synthetic-hash')
    monkeypatch.setattr(worker,'run',run)
    monkeypatch.setattr(worker.os,'sched_getaffinity',lambda *a:{0},raising=False)
    worker.main();runtime=decode((out/'runtime.json').read_bytes())
    assert len(calls)==(1 if all_bad else 1+len(payload['variant_lines'])) and runtime['tool_invoked'] is (not all_bad)
    if not all_bad:
        assert '--numberOfRuns=5' in calls[-1]
        from t01_phase1_real.development.foldx.scan_batches import unpack
        assert [unpack((out/r['archive']).read_bytes())['individual_list.txt'].decode().strip()
                for r in runtime['buildmodel_parallel']]==payload['variant_lines']
