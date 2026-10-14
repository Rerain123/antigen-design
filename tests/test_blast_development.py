"""N03 local BLAST admission, database identity, parsing and runtime registration."""
import json
import os
import threading
import time
from pathlib import Path

import pytest

from t01_phase1_real.common import RuntimeFault, encode, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development import docker
from t01_phase1_real.development.blast import policy
from t01_phase1_real.development.blast.result import parse_hsps, result

SEQ='MKWVTFISLLFLFSSAYSRGVFRRDTHKSEIAHRFKDLGE'


def test_real_iedb_bidirectional_indels_can_exceed_both_sequence_lengths():
    fixture=Path(__file__).parents[1]/'discovery/t01-phase1-real/m1-p4-20260922/iedb-gapped-hsp-regression-r01.json'
    data=json.loads(fixture.read_bytes())
    rows=parse_hsps(('\n'.join(data['rows'])+'\n').encode(),data['request'])
    assert len(rows)==5
    assert all(row['alignment_length']>max(row['query_length'],row['subject_length']) for row in rows)
    fields=data['rows'][0].split('\t');fields[15]='-'+fields[15];fields[16]='-'+fields[16];fields[3]=str(int(fields[3])+1)
    with pytest.raises(RuntimeFault,match='double-gap'):parse_hsps(('\t'.join(fields)+'\n').encode(),data['request'])


def body(**changes):
    value=dict(protein_sequence=SEQ,user_sequence_id='../metadata only',database_id='engineering-n03',
        database_manifest_sha256='a'*64,thresholds=dict(identity_percent_min=70.0,query_coverage_percent_min=80.0),
        timeout_seconds=30)
    value.update(changes);return encode(value)


def make_database(root,qualification='ENGINEERING_FIXTURE'):
    folder=root/'engineering-n03';folder.mkdir(parents=True)
    files={'source.fasta':b'>eng_exact\n'+SEQ.encode()+b'\n','engineering.phr':b'phr','engineering.pin':b'pin',
        'engineering.psq':b'psq','engineering.pdb':b'pdb'}
    for name,raw in files.items():(folder/name).write_bytes(raw)
    manifest=dict(schema_version='0.1.0',database_id='engineering-n03',qualification=qualification,
        purpose='N03 isolated engineering fixture',created_at='2026-09-07T00:00:00+08:00',
        source=dict(name='project engineering FASTA',version='2026-09-07',release_date='2026-09-07',
            license='project test fixture',reference='tests/fixtures/blast-engineering.fasta'),
        blast=dict(db_prefix='engineering',dbtype='prot',blastdb_version=5,title='fixture',sequence_count=1,
            makeblastdb_version='makeblastdb: 2.17.0+',builder_identity=policy.IMAGE),
        files=[dict(path=name,role='source_fasta' if name=='source.fasta' else 'index',bytes=len(raw),sha256=sha(raw))
            for name,raw in sorted(files.items())])
    raw=encode(manifest);(folder/'manifest.json').write_bytes(raw)
    return raw,folder


@pytest.mark.parametrize('sequence',['','A'*8,'A'*20001,'lowercase','ACDEFGHIKX','ACDE FGHIK',None])
def test_request_rejects_invalid_sequence(sequence):
    with pytest.raises(RuntimeFault):policy.request(body(protein_sequence=sequence))


@pytest.mark.parametrize('changes',[dict(database_id='../db'),dict(database_id='C:path'),dict(database_manifest_sha256='x'*64),
    dict(thresholds={'identity_percent_min':70}),dict(thresholds={'identity_percent_min':True,'query_coverage_percent_min':80}),
    dict(timeout_seconds=0),dict(timeout_seconds=14401),dict(command='blastp arbitrary')])
def test_request_has_exact_database_identity_and_no_command_surface(changes):
    with pytest.raises(RuntimeFault):policy.request(body(**changes))


def test_request_accepts_long_target_database_deadline():
    assert policy.request(body(timeout_seconds=14400))['timeout_seconds']==14400


def test_target_blast_resource_profile_is_explicitly_wide_enough_for_nr():
    assert policy.LIMITS == dict(memory=16*1024**3,cpus=4,cpuset='0-3',pids=64)


def test_pinned_official_engine_receipt_is_separate_from_database_licence():
    receipt=policy.verify_assets()
    assert receipt['image_id']==policy.IMAGE and receipt['observed_versions']['blastp']=='blastp: 2.17.0+'
    assert receipt['platform']=={'os':'linux','architecture':'amd64'}
    assert receipt['license_record']['database_licence_inferred'] is False


def test_database_manifest_verifies_every_source_and_index_byte(tmp_path):
    raw,folder=make_database(tmp_path);value=policy.request(body(database_manifest_sha256=sha(raw)))
    receipt=policy.verify_database(tmp_path,value)
    assert receipt['mount_path']==str(folder) and receipt['qualification']=='ENGINEERING_FIXTURE'
    assert receipt['blast']['db_prefix']=='engineering' and len(receipt['files'])==5
    (folder/'engineering.psq').write_bytes(b'changed')
    with pytest.raises(RuntimeFault) as exc:policy.verify_database(tmp_path,value)
    assert exc.value.code=='HASH_MISMATCH'


def test_iedb_manifest_binds_metadata_and_rejects_modified_evidence(tmp_path):
    raw,folder=make_database(tmp_path)
    manifest=json.loads(raw);metadata=b'registered IEDB evidence fixture'
    (folder/'evidence.sqlite3').write_bytes(metadata)
    manifest.update(schema_version='0.3.0',iedb=dict(metadata_path='evidence.sqlite3',source_sql_sha256='c'*64,
        source_snapshot='unit-fixture',mapping_version='iedb-n03-v1'))
    manifest['files'].append(dict(path='evidence.sqlite3',role='iedb_metadata',bytes=len(metadata),sha256=sha(metadata)))
    raw=encode(manifest);(folder/'manifest.json').write_bytes(raw)
    value=policy.request(body(database_manifest_sha256=sha(raw)))
    assert policy.verify_database(tmp_path,value)['iedb']==manifest['iedb']
    (folder/'evidence.sqlite3').write_bytes(b'tampered')
    with pytest.raises(RuntimeFault) as exc:policy.verify_database(tmp_path,value)
    assert exc.value.code=='HASH_MISMATCH'


def test_target_database_cache_reuses_hash_after_stat_check_and_invalidates_on_change(tmp_path,monkeypatch):
    raw,folder=make_database(tmp_path,qualification='TARGET_DATABASE_UNREVIEWED')
    value=policy.request(body(database_manifest_sha256=sha(raw)))
    original=policy._hash_file;calls=[]
    def counted(path):
        calls.append(path)
        return original(path)
    monkeypatch.setattr(policy,'_hash_file',counted)
    first=policy.verify_database(tmp_path,value)
    assert first['qualification']=='TARGET_DATABASE_UNREVIEWED' and calls
    calls.clear()
    second=policy.verify_database(tmp_path,value)
    assert second==first and calls==[]
    (folder/'engineering.psq').write_bytes(b'changed')
    with pytest.raises(RuntimeFault) as exc:policy.verify_database(tmp_path,value)
    assert exc.value.code=='HASH_MISMATCH' and calls


def test_persisted_target_receipt_restores_runtime_mount_path(tmp_path,monkeypatch):
    raw,folder=make_database(tmp_path,qualification='TARGET_DATABASE_UNREVIEWED')
    manifest_hash=sha(raw)
    verified=policy._verify_database_uncached(tmp_path,policy.request(body(database_manifest_sha256=manifest_hash)))
    persisted=tmp_path/'target-receipt.json'
    persisted.write_bytes(encode(dict(status='VERIFIED_FULL_SHA256',database_id='engineering-n03',
        manifest_sha256=manifest_hash,mount_path=str(folder),pvc_claim='antigen-n03-nr',
        pvc_subpath='nr-20250624/raw',receipt={k:v for k,v in verified.items() if k!='mount_path'} | {
            'files':[verified['files'][0]]*2227})))
    monkeypatch.setattr(policy,'PERSISTED_TARGET_RECEIPT',persisted)
    restored=policy._load_persisted_target_receipt(folder,folder/'manifest.json','engineering-n03',manifest_hash)
    assert restored is not None and restored['mount_path']==str(folder)


def test_target_database_cache_serializes_concurrent_first_verification(tmp_path,monkeypatch):
    raw,_=make_database(tmp_path,qualification='TARGET_DATABASE_UNREVIEWED')
    value=policy.request(body(database_manifest_sha256=sha(raw)))
    original=policy._hash_file;calls=[]
    def counted(path):
        calls.append(path)
        time.sleep(0.005)
        return original(path)
    monkeypatch.setattr(policy,'_hash_file',counted)
    results=[];errors=[]
    def verify():
        try:results.append(policy.verify_database(tmp_path,value))
        except BaseException as exc:errors.append(exc)
    threads=[threading.Thread(target=verify) for _ in range(2)]
    for thread in threads:thread.start()
    for thread in threads:thread.join()
    assert not errors and len(results)==2 and results[0]==results[1]
    assert len(calls)==len(results[0]['files'])


def test_database_unavailable_and_manifest_mismatch_are_not_no_hit(tmp_path):
    value=policy.request(body())
    with pytest.raises(RuntimeFault) as exc:policy.verify_database(None,value)
    assert exc.value.code=='ASSET_MISSING'
    raw,_=make_database(tmp_path)
    with pytest.raises(RuntimeFault) as exc:policy.verify_database(tmp_path,value)
    assert exc.value.code=='HASH_MISMATCH' and sha(raw)!='a'*64


def row(**changes):
    fields=dict(qseqid=policy.sequence_id(SEQ),sseqid='eng_exact',pident='100.000',length=str(len(SEQ)),mismatch='0',
        gapopen='0',qstart='1',qend=str(len(SEQ)),sstart='1',send=str(len(SEQ)),evalue='1e-30',bitscore='100',
        qlen=str(len(SEQ)),slen=str(len(SEQ)),qcovhsp='100',qseq=SEQ,sseq=SEQ,stitle='exact engineering target')
    fields.update(changes)
    order=('qseqid','sseqid','pident','length','mismatch','gapopen','qstart','qend','sstart','send','evalue','bitscore',
        'qlen','slen','qcovhsp','qseq','sseq','stitle')
    return ('\t'.join(fields[name] for name in order)+'\n').encode()


def test_hsp_parser_maps_one_based_query_and_marks_threshold_result():
    parsed=parse_hsps(row(),policy.request(body()))
    assert len(parsed)==1 and parsed[0]['query_start']==1 and parsed[0]['query_end']==len(SEQ)
    assert parsed[0]['percent_identity']==100 and parsed[0]['query_coverage_percent']==100
    assert parsed[0]['passes_registered_thresholds'] is True


def test_hsp_below_threshold_is_retained_but_not_qualified():
    parsed=parse_hsps(row(pident='69.999'),policy.request(body()))
    assert len(parsed)==1 and parsed[0]['passes_registered_thresholds'] is False


@pytest.mark.parametrize('raw',[b'bad\trow\n',row(qseq='A'*len(SEQ)),row(qcovhsp='99'),row(qstart='0'),b'bad utf8 \xff'])
def test_hsp_parser_rejects_malformed_identity_coordinates_or_encoding(raw):
    with pytest.raises(RuntimeFault):parse_hsps(raw,policy.request(body()))


@pytest.mark.skipif(os.name!='nt',reason='Current trusted-local task runtime requires Windows')
def test_atomic_runtime_registration_and_additive_schema(tmp_path):
    raw,_=make_database(tmp_path/'dbroot');request=body(database_manifest_sha256=sha(raw))
    rt=Runtime(tmp_path/'runtime',blast_database_root=tmp_path/'dbroot')
    first=rt.submit_sequence(request,'same',policy.TOOL);second=rt.submit_sequence(request,'same',policy.TOOL)
    assert first==second and first['tool_id']==policy.TOOL and first['node_id']=='N03'
    assert first['usable_for_pipeline'] is False and first['review_required'] is True
    with pytest.raises(RuntimeFault) as exc:rt.submit_sequence(body(database_manifest_sha256=sha(raw),user_sequence_id='changed'),'same',policy.TOOL)
    assert exc.value.code=='IDEMPOTENCY_CONFLICT'


def test_docker_command_is_fixed_offline_readonly_and_mounts_only_registered_database(tmp_path):
    raw,folder=make_database(tmp_path/'dbroot');request=policy.request(body(database_manifest_sha256=sha(raw)))
    receipt=policy.verify_database(tmp_path/'dbroot',request)
    root=tmp_path/'runtime';root.mkdir();(root/'attempt').mkdir();(root/'attempt/input.json').write_bytes(body())
    (root/'attempt/input.fasta').write_bytes(b'>x\n'+SEQ.encode()+b'\n');(root/'attempt/output').mkdir()
    job=dict(tool_id=policy.TOOL,run_id='run-0123456789abcdef',job_id='job-0123456789abcdef',
        attempt_id='attempt-0123456789abcdef',execution_identity='exec-attempt-0123456789abcdef')
    argv=docker.command(root,job,'attempt',30,receipt['mount_path'])
    assert '--network' in argv and argv[argv.index('--network')+1]=='none' and '--read-only' in argv
    mounts=[argv[i+1] for i,v in enumerate(argv) if v=='--mount']
    assert any('target=/database,readonly' in value and str(folder) in value for value in mounts)
    assert argv[-4:]==['30','python3','-B','/worker.py']


def test_execution_failure_is_unavailable_not_no_hit():
    job=dict(tool_id=policy.TOOL,run_id='r',request_id='q',job_id='j',attempt_id='a',execution_identity='e',
        execution_profile={},request_artifact={'sha256':'b'*64})
    execution=dict(error_code='ASSET_MISSING',diagnostic='database unavailable',exit_code=None)
    value=result(job,policy.request(body()),{},execution)
    assert value['status']=='unreliable' and value['search'] is None and value['null_reason']=='ASSET_MISSING'
    assert value['warnings'][0]['code']=='ASSET_MISSING' and value['search'] is not {'search_status':'no_hit'}
