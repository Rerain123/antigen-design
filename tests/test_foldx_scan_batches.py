"""Batch storage/coverage against archived native bytes; no new FoldX runs."""
import copy
import io
import zipfile
import pytest
from t01_phase1_real.common import decode,encode,sha
from t01_phase1_real.development.foldx import scan_batches as batches
from t01_phase1_real.development.foldx.result import result
from test_foldx_development import recording


def zipped(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,raw in files.items():archive.writestr(name,raw)
    return stream.getvalue()


def batched():
    job,body,files,execution=copy.deepcopy(recording('positionscan-two-positions'))
    runtime=decode(files['output/runtime.json']);payload=decode(files['native/payload.json'])
    members={n[len('output/positionscan/'):]:v for n,v in files.items() if n.startswith('output/positionscan/')}
    files={n:v for n,v in files.items() if not n.startswith('output/positionscan/')}
    raw=zipped(members);files['output/batches/0000.zip']=raw
    command=runtime['commands'].pop('positionscan');command['argv'][-1]='--output-dir=/out/batches/0000'
    plan=batches.plan(payload)
    runtime['scan_batches']=[dict(plan[0],**command,archive='batches/0000.zip',sha256=sha(raw),size_bytes=len(raw),
        members=len(members),expanded_bytes=sum(map(len,members.values())))]
    files['output/scan-plan.json']=encode(dict(positions_per_batch=16,batches=plan,repair_reused=True))
    files['output/scan-progress.json']=encode(dict(completed=runtime['scan_batches'],total=len(plan)))
    return job,body,files,execution,runtime


def finalize(files,runtime):
    runtime['native_output_sha256']={n[7:]:sha(v) for n,v in files.items() if n.startswith('output/') and n!='output/runtime.json'}
    files['output/runtime.json']=encode(runtime)


def test_archived_native_values_survive_batch_storage_exactly():
    original=result(*recording('positionscan-two-positions'))
    job,body,files,ex,runtime=batched();finalize(files,runtime)
    value=result(job,body,files,ex)
    assert value['null_reason'] is None,value
    assert [{k:v for k,v in r.items() if k!='source'} for r in value['ddg_results']]==[
        {k:v for k,v in r.items() if k!='source'} for r in original['ddg_results']]
    assert value['native_completeness']['batch_count']==1
    assert value['native_completeness']['repair_reused'] is True
    assert all('.zip!/' in r['source'] for r in value['ddg_results'])


@pytest.mark.parametrize('damage',['missing','hash','mapping','extra','plan','progress','pdb','corrupt_zip'])
def test_partial_or_tampered_batches_never_publish_scores(damage):
    job,body,files,ex,runtime=batched();archive='output/batches/0000.zip';record=runtime['scan_batches'][0]
    if damage=='missing':del files[archive]
    elif damage=='hash':record['sha256']='0'*64
    elif damage=='mapping':record['scan_tokens']=[]
    elif damage=='extra':files['output/batches/0001.zip']=files[archive]
    elif damage=='plan':files['output/scan-plan.json']=encode({})
    elif damage=='progress':files['output/scan-progress.json']=encode(dict(completed=[],total=1))
    else:
        members=batches.unpack(files[archive]);del members['HIS1_target_Repair.pdb']
        files[archive]=zipped(members) if damage=='pdb' else b'invalid'
        record.update(sha256=sha(files[archive]),size_bytes=len(files[archive]),members=len(members),expanded_bytes=sum(map(len,members.values())))
    if damage not in ('plan','progress'):files['output/scan-progress.json']=encode(dict(completed=runtime['scan_batches'],total=1))
    finalize(files,runtime)
    value=result(job,body,files,ex)
    assert value['null_reason']=='OUTPUT_INVALID' and value['ddg_results'] is None


@pytest.mark.parametrize('count',[1,16,17,40,500,999])
def test_batch_plan_preserves_complete_order_without_duplicates(count):
    payload=dict(scan_tokens=[f'AA{i}a' for i in range(1,count+1)],position_mapping=[dict(position=i) for i in range(1,count+1)])
    plan=batches.plan(payload)
    assert [t for b in plan for t in b['scan_tokens']]==payload['scan_tokens']
    assert [t for b in plan for t in b['position_mapping']]==payload['position_mapping']
    assert all(1<=len(b['scan_tokens'])<=16 for b in plan)


def test_two_batch_merge_requires_every_position_and_preserves_global_order():
    from t01_phase1_real.development.foldx.result import _positionscan,AA3
    from t01_phase1_real.development.foldx import policy
    payload=dict(scan_tokens=[f'AA{i}a' for i in range(1,18)],
        position_mapping=[dict(position=i,pdb_resseq=i,chain='A',wt='A') for i in range(1,18)])
    plan=batches.plan(payload);files={};records=[]
    for b in plan:
        members={};lines=[]
        for mapping in b['position_mapping']:
            i=mapping['position'];lines.append(f'ALAA{i}A\t0')
            for aa in policy.ALPHABET:
                lines.append(f'ALAA{i}{aa}\t{0 if aa=="A" else i/10}')
                members[f'{AA3[aa]}{i}_target_Repair.pdb']=b'ENGINEERING FIXTURE'
            members[f'energies_{i}_target_Repair.txt']=b'ENGINEERING FIXTURE'
        members['PS_target_scanning_output.txt']='\n'.join(lines).encode()
        directory=f"batches/{b['index']:04d}";raw=zipped(members);files['output/'+directory+'.zip']=raw
        records.append(dict(b,archive=directory+'.zip',sha256=sha(raw),size_bytes=len(raw),members=len(members),
            expanded_bytes=sum(map(len,members.values())),exit_code=0,
            argv=['/app/foldx_20270131','--command=PositionScan','--pdb=target_Repair.pdb',
                  '--pdb-dir=/out/repair','--positions='+','.join(b['scan_tokens']),'--output-dir=/out/'+directory]))
    files['output/scan-plan.json']=encode(dict(positions_per_batch=16,batches=plan,repair_reused=True))
    files['output/scan-progress.json']=encode(dict(completed=records,total=2))
    rows,stats=_positionscan(payload,dict(scan_batches=records),files)
    assert len(rows)==340 and stats['batch_count']==2
    assert [(r['position'],r['rank_foldx']) for r in rows]==[(p,r) for p in range(1,18) for r in range(1,21)]
    with pytest.raises(Exception):_positionscan(payload,dict(scan_batches=list(reversed(records))),files)


def test_seal_roundtrip_preserves_bytes_before_removing_batch_directory(tmp_path):
    folder=tmp_path/'batches'/'0000';folder.mkdir(parents=True)
    (folder/'pdb').write_bytes(b'ATOMS\n'*300);(folder/'scores').write_bytes(b'ddg\n')
    receipt=batches.seal(folder,folder.with_suffix('.zip'))
    restored=batches.unpack(folder.with_suffix('.zip').read_bytes())
    assert restored=={'pdb':b'ATOMS\n'*300,'scores':b'ddg\n'}
    assert not folder.exists() and receipt['members']==2


@pytest.mark.parametrize('name',['../escape','/absolute','bad\\path','a/../b','C:relative'])
def test_archive_paths_cannot_escape(name):
    raw=zipped({name:b'data'})
    if name=='bad\\path':raw=raw.replace(b'bad/path',b'bad\\path') # Windows ZipInfo normalizes separators.
    with pytest.raises(ValueError):batches.unpack(raw)


def test_unbounded_or_invalid_archives_and_wrong_delete_target_rejected(tmp_path,monkeypatch):
    with pytest.raises(ValueError):batches.unpack(b'invalid')
    folder=tmp_path/'valuable';folder.mkdir();(folder/'data').write_text('keep')
    with pytest.raises(ValueError):batches.seal(folder,folder.with_suffix('.zip'))
    assert (folder/'data').read_text()=='keep'
    monkeypatch.setattr(batches,'MAX_EXPANDED',5)
    with pytest.raises(ValueError):batches.unpack(zipped({'large':b'X'*6}))
