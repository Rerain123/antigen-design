"""Independent DNA pairing and missing/failed/lifecycle supplement, no candidate inputs."""
import argparse
import copy
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from t01_phase1_real.common import REPO,decode,encode,sha,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.local_delivery import policy as delivery,service
from t01_phase1_real.development.codon import policy as codon
from t01_phase1_real.development.variant_report import policy as report
from run_local_delivery_acceptance import src,request,write

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--batch',required=True);a=ap.parse_args();assert a.batch.replace('-','').isalnum()
    root=REPO/'var/t01-phase1-real'/('local-delivery-supplement-20260910-'+a.batch)
    batch=REPO/'discovery/t01-phase1-real/w7/local-delivery-integration-20260910'/a.batch
    assert not root.exists() and not batch.exists();batch.mkdir(parents=True);rt=Runtime(root);cases=[];guards=[]
    def finish(name,j):
        j=rt.get(j['job_id']);v=rt.result(j['job_id']) if j['artifacts'] else None
        write(batch/'cases'/name/'job.json',j);write(batch/'cases'/name/'request.json',rt._request_bytes(j))
        if v:write(batch/'cases'/name/'result.json',v)
        for r in j['artifacts']:write(batch/'cases'/name/'artifacts'/r['artifact_id'],rt.artifact_bytes(j['job_id'],r['artifact_id']))
        cases.append(dict(case=name,job_id=j['job_id'],runtime_root=str(root),state=j['state'],error_code=j['error_code']))
        print(name,j['state'],flush=True);return j,v
    def run(name,b,p=delivery,fault=None):
        j=rt.submit_sequence(encode(b),name,p.TOOL);rt._development_fault=fault
        try:rt.dispatch(j['job_id'])
        finally:rt._development_fault=None
        return finish(name,j)
    seq='ACDEFGHIKLMNPQRSTVWY';cb=dict(protein_sequence=seq,user_sequence_id='independent DNA pairing engineering fragment',expression_host='E.coli',
        host_profile=codon.PROFILE,coding_policy=codon.CODING,input_kind='INDEPENDENT_ENGINEERING_SEQUENCE',timeout_seconds=60)
    cj,cv=run('independent-dna-real',cb,codon);assert cv['dna']['optimized_checks']['all_constraints_pass']
    b=request(seq,delivery);b['expression_host']='E.coli';b['dna_bindings']=[dict(subject='WT',source=src(cj))]
    _,v=run('matched-dna-inapplicable-lineage',b);assert v['delivery']['dna'][0]['applicable'] is False and v['delivery']['dna'][0]['dna'] is None
    def reject(name,wrong):
        try:rt.submit_sequence(encode(wrong),name,delivery.TOOL)
        except RuntimeFault as exc:guards.append(dict(case=name,code=exc.code,reason=str(exc)))
        else:raise AssertionError(name+' accepted')
    wrong=copy.deepcopy(b);wrong['protein_sequence']='AAA';reject('dna-wrong-wt',wrong)
    wrong=copy.deepcopy(b);wrong['expression_host']='CHO';reject('dna-wrong-expression-host',wrong)
    wrong=copy.deepcopy(b);wrong['dna_bindings'][0]['subject']='sample-999';reject('dna-unknown-variant',wrong)
    wrong=copy.deepcopy(b);wrong['dna_bindings'][0]['source']['artifact']['sha256']='0'*64;reject('dna-damaged-ref',wrong)
    cb['expression_host']='CHO';cb['host_profile']=None;cj,_=run('dna-unsupported-real',cb,codon);assert cj['state']=='failed'
    b['expression_host']='CHO';b['dna_bindings']=[dict(subject='WT',source=src(cj))];_,v=run('failed-dna-source',b)
    assert v['delivery']['dna'][0]['source']['state']=='failed'
    rb=dict(protein_sequence=seq,user_sequence_id='explicit failed source',upstream=dict(design_audit=None,foldx=None),variant_source='N11_DESIGN_AUDIT',foldx_bindings=[],timeout_seconds=60)
    rj,_=run('failed-report-source',rb,report,'compute_failure')
    b=request(seq,delivery);b['upstream']['variant_report']=src(rj);_,v=run('upstream-failed-delivery',b);assert v['delivery']['outcome']=='UPSTREAM_FAILED'
    pending=rt.submit_sequence(encode(rb),'pending-report',report.TOOL);b['upstream']['variant_report']=src(pending)
    _,v=run('pending-report-delivery',b);assert v['delivery']['source_receipts']['variant_report']['state']=='pending'
    j=rt.submit_sequence(encode(request(seq,delivery)),'cancel',delivery.TOOL)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='cancel')))
    finish('queued-cancel',rt.dispatch(j['job_id']))
    b=request(seq,delivery);b['timeout_seconds']=1;ticks=iter([0.,2.]);original=service.time.perf_counter
    service.time.perf_counter=lambda:next(ticks)
    try:j,v=run('controlled-deadline',b)
    finally:service.time.perf_counter=original
    assert j['state']=='timed_out' and v['delivery'] is None
    original=service.sources;calls=[]
    def changed(*args):
        f,v,r=original(*args);calls.append(True)
        if len(calls)==2:r['wt_draft']['state']='changed'
        return f,v,r
    service.sources=changed
    try:j,v=run('controlled-late-source',request(seq,delivery))
    finally:service.sources=original
    assert j['error_code']=='HASH_MISMATCH' and v['delivery'] is None
    write(batch/'source/run_local_delivery_supplement.py',Path(__file__).read_bytes())
    write(batch/'guards.json',guards)
    write(batch/'index.json',dict(cases=cases,guards=guards,original_24_processed=False,scientific_handoff=False,
        files=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(batch.rglob('*')) if p.is_file()]))

if __name__=='__main__':main()
