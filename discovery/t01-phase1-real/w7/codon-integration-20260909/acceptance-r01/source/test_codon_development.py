import copy
import threading
import time
import pytest
from t01_phase1_real.common import RuntimeFault,decode,encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.codon import policy,compute,service

def body(seq='ACDEFGHIKLMNPQRSTVWY'):
    return dict(protein_sequence=seq,user_sequence_id='independent synthetic engineering fragment',expression_host='E.coli',
        host_profile=policy.PROFILE,coding_policy=policy.CODING,input_kind='INDEPENDENT_ENGINEERING_SEQUENCE',timeout_seconds=60)

def run(rt,b=None,key='test',fault=None):
    j=rt.submit_sequence(encode(b or body()),key,policy.TOOL);rt._development_fault=fault
    rt.dispatch(j['job_id']);rt._development_fault=None
    return rt.get(j['job_id'])

def test_real_engineering_and_idempotency(tmp_path):
    rt=Runtime(tmp_path);j=run(rt)
    assert j['state']=='succeeded',rt.result(j['job_id'])
    v=rt.result(j['job_id']);d=v['dna']
    assert d['status']=='OPTIMIZED_ENGINEERING' and d['optimized_checks']['all_constraints_pass']
    assert d['cai_score'] is None and v['usable_for_pipeline'] is False
    assert rt.submit_sequence(encode(body()),'test',policy.TOOL)['job_id']==j['job_id']
    assert all(rt.artifact_bytes(j['job_id'],r['artifact_id']) for r in j['artifacts'])

def test_true_no_solution_fallback(tmp_path):
    rt=Runtime(tmp_path);j=run(rt,body('WWWWWW'));v=rt.result(j['job_id'])
    assert j['state']=='succeeded' and v['status']=='optimization_incomplete',v
    assert v['dna']['optimized_dna'] is None and v['dna']['returned_kind']=='unoptimized_fallback'
    assert v['dna']['initial_checks']['violations']==['GC_OUT_OF_RANGE']
    assert v['dna']['optimizer_failure']['code']=='NO_SOLUTION'

@pytest.mark.parametrize('host,profile,code',[(None,None,None),('CHO',None,'UNSUPPORTED_EXPRESSION_HOST'),
    ('E.coli',None,'HOST_PROFILE_REQUIRED'),('BHK-21',None,'UNSUPPORTED_EXPRESSION_HOST'),('VERO',None,'UNSUPPORTED_EXPRESSION_HOST')])
def test_host_routes(tmp_path,host,profile,code):
    rt=Runtime(tmp_path);b=body();b.update(expression_host=host,host_profile=profile);j=run(rt,b);v=rt.result(j['job_id'])
    assert j['error_code']==code and v['dna'] is None
    assert v['execution']['worker_started'] is False
    if host is None:assert v['status']=='skipped_missing_expression_host'

@pytest.mark.parametrize('seq',['','acde','ACX','AC*',' A','A\n','A'*1001])
def test_invalid_proteins(seq):
    with pytest.raises(RuntimeFault):policy.request(encode(body(seq)))

@pytest.mark.parametrize('field,value',[('host_species','E.coli'),('input_kind','CANDIDATE'),('coding_policy','guess'),('timeout_seconds',True)])
def test_no_implicit_business_or_policy(field,value):
    b=body();b[field]=value
    with pytest.raises(RuntimeFault):policy.request(encode(b))

def test_constraints_both_strands_and_edges():
    from Bio.Seq import Seq
    for motif in ('GGTCTC','GAGACC','GAAGAC','GTCTTC'):
        v=compute.checks(motif,str(Seq(motif).translate()))
        assert any(x.startswith('RESTRICTION_SITE') for x in v['violations'])
    for seq,expected in [('GCGGCGAATAATAAA',True),('GCGGCGGCGAATAAA',True),('GCGGCGGCGGCGGCG',False)]:
        assert compute.checks(seq,str(Seq(seq).translate()))['gc_passed']==expected

def test_table_semantic_and_mutated_output():
    raw=(policy.ASSETS/'e_coli_316407.csv').read_bytes();t=compute.table(raw)
    with pytest.raises(RuntimeFault):compute.table(raw+b'\n'+raw.splitlines(keepends=True)[1])
    obs=compute.optimize(body(),raw);obs['optimized_dna']='A'*57
    with pytest.raises(RuntimeFault):compute.summarize(body(),obs,t)

@pytest.mark.parametrize('change,code',[('missing','CODON_TABLE_MISSING'),('tamper','HASH_MISMATCH')])
def test_table_source_guards(tmp_path,monkeypatch,change,code):
    assets=tmp_path/'assets';assets.mkdir()
    for p in policy.ASSETS.iterdir():(assets/p.name).write_bytes(p.read_bytes())
    if change=='missing':(assets/'e_coli_316407.csv').unlink()
    else:(assets/'e_coli_316407.csv').write_bytes(b'wrong')
    monkeypatch.setattr(policy,'ASSETS',assets)
    with pytest.raises(RuntimeFault) as e:policy.source_files(body())
    assert e.value.code==code

@pytest.mark.parametrize('fault,code',[('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID'),('interrupt_after_claim','INTERRUPTED')])
def test_failure_recovery_retry(tmp_path,fault,code):
    rt=Runtime(tmp_path);j=run(rt,fault=fault)
    if fault=='interrupt_after_claim':rt.recover(j['job_id'])
    assert rt.get(j['job_id'])['error_code']==code and rt.result(j['job_id'])['dna'] is None
    retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=j['job_id'],idempotency_key='retry')))
    rt.dispatch(retry['job_id']);assert rt.get(retry['job_id'])['state']=='succeeded'

def test_real_timeout_and_active_cancel(tmp_path):
    rt=Runtime(tmp_path);b=body();b['timeout_seconds']=2;j=run(rt,b,fault='hold_worker')
    assert j['state']=='timed_out' and rt.result(j['job_id'])['dna'] is None
    rt._development_fault='hold_worker';j=rt.submit_sequence(encode(body()),'active',policy.TOOL)
    errors=[]
    def dispatch():
        try:rt.dispatch(j['job_id'])
        except Exception as exc:errors.append(exc)
    thread=threading.Thread(target=dispatch);thread.start()
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if rt.execution(j['job_id']).get('worker_started'):break
        time.sleep(.05)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='cancel')))
    thread.join(15);assert not thread.is_alive() and not errors
    assert rt.get(j['job_id'])['state']=='cancelled' and rt.result(j['job_id'])['dna'] is None

def test_published_tamper(tmp_path):
    rt=Runtime(tmp_path);j=run(rt);ref=next(r for r in j['artifacts'] if r['role']=='result')
    with rt._db() as db:path=rt.root/db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    path.write_bytes(b'{}')
    with pytest.raises(RuntimeFault):rt.result(j['job_id'])

def test_request_tamper_before_dispatch(tmp_path):
    rt=Runtime(tmp_path);j=rt.submit_sequence(encode(body()),'source',policy.TOOL)
    with rt._db() as db:path=rt.root/db.execute('SELECT relative_path FROM artifacts WHERE id=?',(j['request_artifact']['artifact_id'],)).fetchone()[0]
    path.write_bytes(encode(body('AAAA')))
    with pytest.raises(RuntimeFault) as exc:rt.dispatch(j['job_id'])
    assert exc.value.code=='HASH_MISMATCH'

def test_late_source_change_rejected(tmp_path,monkeypatch):
    original=policy.source_files;calls=[]
    def changed(b):
        files,receipt=original(b);calls.append(True)
        if len(calls)==2:receipt['dependency_manifest_sha256']='0'*64
        return files,receipt
    monkeypatch.setattr(policy,'source_files',changed)
    rt=Runtime(tmp_path);j=run(rt)
    assert j['error_code']=='HASH_MISMATCH' and rt.result(j['job_id'])['dna'] is None

def test_queued_cancel_and_idempotency_conflict(tmp_path):
    rt=Runtime(tmp_path);j=rt.submit_sequence(encode(body()),'same',policy.TOOL)
    with pytest.raises(RuntimeFault) as exc:rt.submit_sequence(encode(body('AAA')),'same',policy.TOOL)
    assert exc.value.code=='IDEMPOTENCY_CONFLICT'
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='cancel')))
    assert rt.dispatch(j['job_id'])['state']=='cancelled'

def test_worker_offline_guard():
    from t01_phase1_real.development.codon.worker import deny_external
    for event in ('socket.connect','socket.__new__','subprocess.Popen','os.system'):
        with pytest.raises(PermissionError):deny_external(event,())

def test_manifest_tamper_without_repin(tmp_path,monkeypatch):
    (tmp_path/'manifest.json').write_bytes(b'{}');monkeypatch.setattr(policy,'ASSETS',tmp_path)
    with pytest.raises(RuntimeFault) as exc:policy.source_files(body())
    assert exc.value.code=='HASH_MISMATCH'
