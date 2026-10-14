import copy
import io
import zipfile
import pytest
from t01_phase1_real.common import RuntimeFault,decode,encode,sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.wt_reference import policy as refpolicy
from t01_phase1_real.development.local_delivery import policy,service,compute

def body(p=policy):
    b=dict(protein_sequence='ACDEFGHIK',user_sequence_id='independent local assembly',upstream={n:None for n in p.PRODUCERS},timeout_seconds=60)
    if p==policy:b.update(host_species=None,expression_host=None,dna_bindings=[])
    return b
def src(j):return dict(job_id=j['job_id'],artifact=next((r for r in j['artifacts'] if r['role'] in ('result','diagnostic')),None))
def run(rt,b,p=policy,key='test'):
    j=rt.submit_sequence(encode(b),key,p.TOOL);rt.dispatch(j['job_id']);return rt.get(j['job_id'])

def verify_zip(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        m=decode(z.read('manifest.json'));assert set(z.namelist())==set(r['path'] for r in m['files'])|{'manifest.json'}
        for row in m['files']:
            data=z.read(row['path']);assert sha(data)==row['sha256'] and len(data)==row['size_bytes']
        return decode(z.read('data.json'))

def test_missing_source_package_query_and_hashes(tmp_path):
    rt=Runtime(tmp_path);b=body();j=run(rt,b);v=rt.result(j['job_id'])
    assert j['state']=='succeeded' and v['delivery']['outcome']=='DESIGN_NOT_EXECUTED'
    assert v['delivery']['best_candidate'] is None and v['delivery']['agent_c_payload'] is None
    ref=next(r['artifact'] for r in v['raw_artifacts'] if r['path']=='output/package.zip')
    assert verify_zip(rt.artifact_bytes(j['job_id'],ref['artifact_id']))==v['delivery']
    assert rt.submit_sequence(encode(b),'test',policy.TOOL)['job_id']==j['job_id']

@pytest.mark.parametrize('status,route,outcome',[
    ('NOT_SUITABLE_FOR_DESIGN','WT_PATH_REVIEW','WT_ROUTE_REVIEW_REQUIRED'),
    ('SUITABLE_FOR_DESIGN','DESIGN_PATH_REVIEW','DESIGN_ELIGIBLE_RELEASE_CLOSED'),
    ('INPUT_INSUFFICIENT_OR_NOT_EVALUATED','HOLD_FOR_INPUTS','DESIGN_INPUTS_UNAVAILABLE')])
def test_delivery_preserves_business_gate_without_formal_release(status,route,outcome):
    receipts={name:dict(state='missing') for name in policy.PRODUCERS}
    receipts.update(wt_draft=dict(state='available'),dna=[])
    gate=dict(status=status,route=route)
    files={'input/source-receipts.json':encode(receipts),
        'input/wt_draft-result.json':encode(dict(draft=dict(gate=gate)))}
    delivery=compute.evaluate(body(),files)
    assert delivery['outcome']==outcome and delivery['business_route']==route
    assert delivery['design_applicability_gate']==gate
    assert delivery['formal_wt_delivery'] is False and delivery['scientific_pass'] is None

@pytest.mark.parametrize('p,field',[(policy,'delivery'),(refpolicy,'reference')])
@pytest.mark.parametrize('fault,code',[('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID'),('interrupt_after_claim','INTERRUPTED')])
def test_failure_retry(tmp_path,p,field,fault,code):
    rt=Runtime(tmp_path);rt._development_fault=fault;j=run(rt,body(p),p)
    rt._development_fault=None
    if fault=='interrupt_after_claim':rt.recover(j['job_id'])
    assert rt.get(j['job_id'])['error_code']==code and rt.result(j['job_id'])[field] is None
    retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=j['job_id'],idempotency_key='retry')))
    assert rt.dispatch(retry['job_id'])['state']=='succeeded'

def test_same_sequence_independent_dna_never_attached(tmp_path):
    from t01_phase1_real.development.codon import policy as codon
    rt=Runtime(tmp_path);b=body();b['protein_sequence']='ACDEFGHIKLMNPQRSTVWY';b['expression_host']='E.coli'
    cb=dict(protein_sequence=b['protein_sequence'],user_sequence_id='engineering dna',expression_host='E.coli',host_profile=codon.PROFILE,
        coding_policy=codon.CODING,input_kind='INDEPENDENT_ENGINEERING_SEQUENCE',timeout_seconds=60)
    cj=run(rt,cb,codon,'codon');b['dna_bindings']=[dict(subject='WT',source=src(cj))]
    j=run(rt,b);v=rt.result(j['job_id'])['delivery'];assert v['dna'][0]['applicable'] is False and v['dna'][0]['dna'] is None
    wrong=copy.deepcopy(b);wrong['expression_host']='CHO'
    with pytest.raises(RuntimeFault):run(rt,wrong,key='wrong-host')
    wrong=copy.deepcopy(b);wrong['protein_sequence']='AAA'
    with pytest.raises(RuntimeFault):run(rt,wrong,key='wrong-seq')
    wrong=copy.deepcopy(b);wrong['dna_bindings'][0]['subject']='sample-999'
    with pytest.raises(RuntimeFault):run(rt,wrong,key='wrong-variant')

def test_deadline_cancel_and_post_source_fence(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);b=body();b['timeout_seconds']=1
    ticks=iter([0.,2.]);monkeypatch.setattr(service.time,'perf_counter',lambda:next(ticks))
    j=run(rt,b);assert j['state']=='timed_out' and rt.result(j['job_id'])['delivery'] is None
    monkeypatch.undo();j=rt.submit_sequence(encode(body()),'queued',policy.TOOL)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='cancel')))
    assert rt.dispatch(j['job_id'])['state']=='cancelled'
    original=service.sources;calls=[]
    def changed(*args):
        f,v,r=original(*args);calls.append(True)
        if len(calls)==2:r['wt_draft']['state']='changed'
        return f,v,r
    monkeypatch.setattr(service,'sources',changed);j=run(rt,body(),key='late')
    assert j['error_code']=='HASH_MISMATCH'

def test_upstream_failed_and_pending_distinct(tmp_path):
    from t01_phase1_real.development.variant_report import policy as report
    rt=Runtime(tmp_path);rb=dict(protein_sequence='ACDEFGHIK',user_sequence_id='empty report',upstream=dict(design_audit=None,foldx=None),
        variant_source='N11_DESIGN_AUDIT',foldx_bindings=[],timeout_seconds=30)
    rt._development_fault='compute_failure';rj=run(rt,rb,report,'failed-report');rt._development_fault=None
    b=body();b['upstream']['variant_report']=src(rj);j=run(rt,b)
    assert rt.result(j['job_id'])['delivery']['outcome']=='UPSTREAM_FAILED'
    pending=rt.submit_sequence(encode(rb),'pending',report.TOOL);b['upstream']['variant_report']=src(pending)
    j=run(rt,b,key='pending-delivery');assert rt.result(j['job_id'])['delivery']['source_receipts']['variant_report']['state']=='pending'

def test_published_package_tamper(tmp_path):
    rt=Runtime(tmp_path);j=run(rt,body());v=rt.result(j['job_id']);ref=next(r['artifact'] for r in v['raw_artifacts'] if r['path']=='output/package.zip')
    with rt._db() as db:p=rt.root/db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    p.write_bytes(b'bad')
    with pytest.raises(RuntimeFault):rt.artifact_bytes(j['job_id'],ref['artifact_id'])
