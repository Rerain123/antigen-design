"""Delivery lineage failure/fallback checks using explicit synthetic envelopes."""
import copy
import io
import zipfile
import pytest
from t01_phase1_real.common import RuntimeFault,encode,decode
from t01_phase1_real.development.local_delivery import source,compute,policy,m1


@pytest.mark.parametrize('state,optimized,code',[
    ('succeeded',True,None),('succeeded',False,'UNOPTIMIZED_DNA_FALLBACK'),
    ('failed',False,'UNSUPPORTED_EXPRESSION_HOST')])
def test_candidate_dna_delivery_retains_native_success_fallback_and_failure(monkeypatch,state,optimized,code):
    from t01_phase1_real.development.codon import lineage,service
    report_src={'job_id':'n15','artifact':None};dna_src={'job_id':'n16','artifact':None}
    body=dict(protein_sequence='AAA',expression_host='E.coli',host_species='pig',
        upstream=dict(wt_draft=None,variant_report=report_src,wt_reference=None),
        dna_bindings=[dict(subject='candidate',source=dna_src)])
    req=dict(protein_sequence='ACA',expression_host='E.coli',input_kind='VERIFIED_N15_ENGINEERING_CANDIDATE',
        candidate_source=dict(source=report_src,candidate_id='candidate'))
    dna=dict(initial_dna='GCGTGCGCG',optimized_dna='GCGTGCGCG' if optimized else None)
    value=dict(dna=dna,status='optimized_engineering' if optimized else 'optimization_incomplete',execution={})
    proof={'input/candidate-lineage.json':encode({'synthetic_only':True})}
    calls=[]
    def registered(rt,db,b,*,producers,enricher):
        if producers==policy.PRODUCERS:
            return {},{'variant_report':{'report':{'records':[dict(id='candidate',sequence='ACA')]}}},{n:dict(state='missing') for n in producers}
        assert b['protein_sequence']=='ACA'
        files={'input/dna-request.json':encode(req)}
        values={'dna':value} if state=='succeeded' else {}
        receipts={'dna':dict(state='available' if values else 'failed',error_code=code)}
        enricher(rt,db,b,files,values,receipts)
        return files,values,receipts
    class RT:
        def _job(self,db,jid):return dict(run_id='same-run',job_id=jid)
    monkeypatch.setattr(source,'registered',registered)
    monkeypatch.setattr(source,'native',lambda *a:copy.deepcopy(proof))
    monkeypatch.setattr(m1,'scan_facts',lambda *a:None)
    monkeypatch.setattr(lineage,'verify',lambda *a:calls.append(a[-1]) or proof)
    monkeypatch.setattr(service,'result',lambda *a:copy.deepcopy(value))
    files,_,receipts=source.sources(RT(),None,body)
    r=receipts['dna'][0]
    assert calls==['same-run'] and r['reason']==code
    assert r['applicable']==(state=='succeeded') and r['dna']==(dna if state=='succeeded' else None)
    req['candidate_source']['candidate_id']='foreign'
    with pytest.raises(RuntimeFault,match='another report'):source.sources(RT(),None,body)


def test_report_package_exports_exact_dna_fallback_with_source():
    d=dict(outcome='ENGINEERING_RECORDS_REVIEW_REQUIRED',subject={'sequence_sha256':'fixture'},variant_report=None,
        missing_conditions=[],dna=[dict(subject='candidate-with-untrusted/path',source={'fixture':True},
            source_status='optimization_incomplete',reason='UNOPTIMIZED_DNA_FALLBACK',dna={'initial_dna':'ATG','optimized_dna':None})])
    output=compute.package({}, {},d)
    with zipfile.ZipFile(io.BytesIO(output['output/package.zip'])) as z:
        assert z.read('dna/candidate-1-unoptimized-fallback.fasta').endswith(b'\nATG\n')
        assert decode(z.read('dna/candidate-1-source.json'))==d['dna'][0]
        assert not any('untrusted' in n for n in z.namelist())
        assert 'UNOPTIMIZED_DNA_FALLBACK' in z.read('report.md').decode()
